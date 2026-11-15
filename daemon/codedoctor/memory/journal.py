"""Journal: the complete, append-only layer of long-term memory.

Every message, model call, tool call and result is written here and never
changed. Large payloads go to the blob store; the entry keeps the hash so the
exact original can always be read back.
"""

from __future__ import annotations

import json

from codedoctor import ids
from codedoctor.store.blobs import BlobStore
from codedoctor.store.db import Database, dumps

INLINE_LIMIT = 4000  # bytes of JSON kept inline; the rest goes to a blob


class Journal:
    def __init__(self, db: Database, blobs: BlobStore):
        self.db = db
        self.blobs = blobs

    def append(
        self,
        agent: str,
        type_: str,
        data: dict,
        *,
        task_id: str | None = None,
        model: dict | None = None,
        payload: object | None = None,
    ) -> dict:
        """Append one entry. `payload` (any JSON value) is stored in full as a blob."""
        entry: dict = {
            "cd_schema": "cd.memory.journal/0",
            "id": ids.new_id("jrn"),
            "agent": agent,
            "type": type_,
            "at": ids.now(),
            "data": data,
        }
        if task_id:
            entry["task_id"] = task_id
        if model:
            entry["model"] = model
        encoded = dumps(data)
        too_big = len(encoded.encode("utf-8")) > INLINE_LIMIT
        if payload is not None or too_big:
            # The blob always holds the complete original: inline data plus the payload.
            entry["blob"] = self.blobs.put(dumps({"data": data, "payload": payload}).encode("utf-8"))
        if too_big:
            # keep the short fields every reader keys on (tool, call_id, ok, state ...); the rest is in the blob
            small = {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 200}
            entry["data"] = {**small, "truncated": True, "preview": encoded[: INLINE_LIMIT // 2]}
        with self.db.tx() as c:
            cur = c.execute(
                "INSERT INTO journal (id, agent, task_id, type, at, doc) VALUES (?,?,?,?,?,'')",
                (entry["id"], agent, task_id, type_, entry["at"]),
            )
            entry["seq"] = cur.lastrowid
            c.execute("UPDATE journal SET doc = ? WHERE seq = ?", (dumps(entry), entry["seq"]))
        return entry

    def read(
        self,
        *,
        task_id: str | None = None,
        agent: str | None = None,
        after_seq: int = 0,
        limit: int = 500,
    ) -> list[dict]:
        where, params = ["seq > ?"], [after_seq]
        if task_id:
            where.append("task_id = ?")
            params.append(task_id)
        if agent:
            where.append("agent = ?")
            params.append(agent)
        rows = self.db.query(
            f"SELECT doc FROM journal WHERE {' AND '.join(where)} ORDER BY seq LIMIT ?", (*params, limit)
        )
        return [json.loads(r["doc"]) for r in rows]

    def last(self, *, task_id: str, agent: str) -> dict | None:
        row = self.db.one("SELECT doc FROM journal WHERE task_id = ? AND agent = ? ORDER BY seq DESC LIMIT 1", (task_id, agent))
        return json.loads(row["doc"]) if row else None

    def get(self, entry_id: str) -> dict | None:
        row = self.db.one("SELECT doc FROM journal WHERE id = ?", (entry_id,))
        return json.loads(row["doc"]) if row else None

    def original(self, entry: dict) -> dict:
        """The complete original of an entry: {'data': ..., 'payload': ...}."""
        if "blob" in entry:
            return json.loads(self.blobs.get(entry["blob"]))
        return {"data": entry["data"], "payload": None}

    def count(self) -> int:
        return self.db.one("SELECT COUNT(*) AS n FROM journal")["n"]
