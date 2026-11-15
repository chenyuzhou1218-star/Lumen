"""Evidence registry: records (schemas/evidence/evidence-record) + bytes in the blob store.

Agents only ever cite evidence ids that this registry created. A claim citing an
id that is not registered, or whose bytes no longer hash correctly, is rejected.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from codedoctor import ids
from codedoctor.currency import snapshot_version
from codedoctor.protocol.registry import validator
from codedoctor.store.blobs import BlobStore
from codedoctor.store.db import Database, dumps

RECORD_SCHEMA = "evidence/evidence-record.schema.json"
_DATA_CLASS_ORDER = ["public", "internal", "confidential", "secret", "local_only"]


class EvidenceError(ValueError):
    pass


def stricter(a: str, b: str) -> str:
    return a if _DATA_CLASS_ORDER.index(a) >= _DATA_CLASS_ORDER.index(b) else b


DATA_CLASS_CN = {"public": "公开", "internal": "内部", "confidential": "机密", "secret": "绝密", "local_only": "仅本机"}


def blocked_agents(config) -> list[str]:
    """Agents none of whose models may receive the project's code (its 代码级别 is above every service they use):
    every model call of theirs would be refused."""
    rank = data_class_rank(config.code_data_class)
    out = []
    for a in config.agents.values():
        eps = [config.endpoints.get(c.endpoint) for c in (a.primary, *a.fallbacks)]
        if eps and all(e is None or data_class_rank(e.max_data_class) < rank for e in eps):
            out.append(a.id)
    return out


def raw_blocked_services(raw: dict) -> list[str]:
    """For a configuration not saved yet: the services agents use that may not receive the project's code level."""
    level = (raw.get("project") or {}).get("code_data_class", "internal")
    eps = {e["id"]: e for e in raw.get("endpoints", [])}
    used = {a.get("endpoint") for a in raw.get("agents", []) if a.get("endpoint")}
    out = []
    for eid in sorted(used):
        e = eps.get(eid)
        if e is None:
            continue
        ceiling = e.get("max_data_class", "local_only" if e.get("local") else "internal")
        if data_class_rank(ceiling) < data_class_rank(level):
            out.append(e.get("name") or eid)
    return out


def data_class_rank(c: str) -> int:
    return _DATA_CLASS_ORDER.index(c)


class EvidenceStore:
    def __init__(self, db: Database, blobs: BlobStore):
        self.db = db
        self.blobs = blobs

    # --- registration ---------------------------------------------------------

    def register(self, record: dict) -> str:
        errors = sorted(validator(RECORD_SCHEMA).iter_errors(record), key=lambda e: e.path)
        if errors:
            raise EvidenceError(f"invalid evidence record: {errors[0].message}")
        if not self.blobs.exists(record["content"]["sha256"]):
            raise EvidenceError("evidence bytes must be stored before the record")
        with self.db.tx() as c:
            c.execute(
                "INSERT OR IGNORE INTO evidence (id, kind, sha256, created_at, doc) VALUES (?,?,?,?,?)",
                (record["id"], record["kind"], record["content"]["sha256"], record["created_at"], dumps(record)),
            )
        return record["id"]

    def add_blob(
        self,
        data: bytes,
        media_type: str,
        *,
        source: str,
        collected_by: str,
        agent_id: str | None = None,
        data_class: str = "internal",
        binding: dict | None = None,
    ) -> str:
        digest = self.blobs.put(data)
        provenance = {"source": source, "collected_by": collected_by}
        if agent_id:
            provenance["agent_id"] = agent_id
        return self.register({
            "cd_schema": "cd.evidence.record/0",
            "id": f"ev:blob:{digest}",
            "kind": "blob",
            "created_at": ids.now(),
            "content": {"sha256": digest, "media_type": media_type, "size_bytes": len(data)},
            "binding": binding or {},
            "provenance": provenance,
            "data_class": data_class,
            "redaction": {"applied": False, "policy_id": "none/0"},
            "content_trust": "untrusted",
        })

    def add_code_excerpt(
        self,
        project_root: Path,
        rel_path: str,
        start_line: int,
        end_line: int,
        *,
        agent_id: str,
        data_class: str = "confidential",
    ) -> tuple[str, str]:
        """Register lines [start_line, end_line] of a project file. Returns (evidence id, excerpt text)."""
        file_path = project_root / rel_path
        raw = file_path.read_bytes()
        lines = raw.decode("utf-8", errors="replace").splitlines(keepends=True)
        excerpt = "".join(lines[start_line - 1 : end_line])
        data = excerpt.encode("utf-8")
        digest = self.blobs.put(data)
        version = snapshot_version(project_root)
        encoded = quote(rel_path.replace("\\", "/"), safe="/._-~")
        ev_id = f"ev:code:{version}:{encoded}@{digest}:L{start_line}-L{end_line}"
        self.register({
            "cd_schema": "cd.evidence.record/0",
            "id": ev_id,
            "kind": "code",
            "created_at": ids.now(),
            "content": {"sha256": digest, "media_type": "text/plain", "size_bytes": len(data)},
            "binding": {"code_version": version},
            "provenance": {"source": "tool", "collected_by": "tools.read_file/0.1.0", "agent_id": agent_id},
            "data_class": data_class,
            "redaction": {"applied": False, "policy_id": "none/0"},
            "content_trust": "untrusted",
        })
        return ev_id, excerpt

    def add_test_run(self, project_root: Path, command: str, exit_code: int, output: str, *, agent_id: str,
                     data_class: str = "internal") -> str:
        """A command run against the project as it is now (a test or reproduction run): ev:test:<run>/<command>,
        bound to the code version, so claims can be 'reproduced' and fixes verified (ADR 0016)."""
        data = f"$ {command}\nexit {exit_code}\n{output}".encode("utf-8")
        digest = self.blobs.put(data)
        version = snapshot_version(project_root)
        ev_id = f"ev:test:{ids.ulid()}/{quote(command[:200], safe='')}"
        return self.register({
            "cd_schema": "cd.evidence.record/0",
            "id": ev_id,
            "kind": "test",
            "created_at": ids.now(),
            "content": {"sha256": digest, "media_type": "text/plain", "size_bytes": len(data)},
            "binding": {"code_version": version},
            "provenance": {"source": "tool", "collected_by": "tools.run_command/0.2.0", "agent_id": agent_id},
            "data_class": data_class,
            "redaction": {"applied": False, "policy_id": "none/0"},
            "content_trust": "untrusted",
        })

    # --- lookup ---------------------------------------------------------------

    def get(self, ev_id: str) -> dict | None:
        row = self.db.one("SELECT doc FROM evidence WHERE id = ?", (ev_id,))
        return json.loads(row["doc"]) if row else None

    def content(self, ev_id: str) -> bytes:
        rec = self.get(ev_id)
        if rec is None:
            raise EvidenceError(f"unknown evidence id {ev_id}")
        return self.blobs.get(rec["content"]["sha256"])

    def forget(self, ev_id: str) -> None:
        """Delete the content on purpose (the user's rule for screenshots); the record says so."""
        rec = self.get(ev_id)
        if rec is None or rec.get("forgotten"):
            return
        with self.db.tx() as c:
            c.execute("UPDATE evidence SET doc = ? WHERE id = ?", (dumps({**rec, "forgotten": True}), ev_id))
        self.blobs.remove(rec["content"]["sha256"])

    def check(self, ev_id: str) -> str:
        """Levels 1-2 of evidence validation: 'ok', 'missing', 'forgotten' (deleted on purpose) or 'tampered'."""
        rec = self.get(ev_id)
        if rec is None:
            return "missing"
        if rec.get("forgotten"):
            return "forgotten"
        return "ok" if self.blobs.intact(rec["content"]["sha256"]) else "tampered"
