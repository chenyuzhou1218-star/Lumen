"""Workspace overview (ADR 0013): what the agents of one investigation did, read, ran and changed.

Everything here is read from what Code Doctor stores permanently - the journal, evidence, claims, notes,
computer actions and project snapshots - never from a model's context, so nothing disappears when a
conversation is elided or compacted.

Changes: the project need not be a git repository (the user's game is not), so a root task takes a
snapshot of the project when it starts and another when it ends: size and modification time of every
file, plus the content of text files (stored once per content in the blob store). Comparing the two
lists added, deleted and modified files and shows line diffs for text. A snapshot cannot tell who
changed a file: edits by the user or other programs during the task are included, and the overview
says so.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from pathlib import Path

from codedoctor import ids
from codedoctor.agents import orchestration as orch
from codedoctor.currency import SKIP_DIRS, parse_code_id
from codedoctor.store.db import dumps

TEXT_MAX = 512 * 1024   # larger files are compared by size and time only
MAX_FILES = 20000
MAX_DIFF_LINES = 2000


def _ensure(services) -> None:
    with services.db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS workspace_snapshots (
            task_id TEXT NOT NULL, phase TEXT NOT NULL, at TEXT NOT NULL, doc TEXT NOT NULL,
            PRIMARY KEY (task_id, phase))""")


def _scan(root: Path, blobs=None) -> tuple[dict, bool]:
    """{path: {size, mtime_ns, sha256?}} for the project; text files are hashed (and stored when `blobs` is given)."""
    files, truncated = {}, False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if len(files) >= MAX_FILES:
                truncated = True
                break
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            rel = p.relative_to(root).as_posix()
            entry = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
            if st.st_size <= TEXT_MAX:
                try:
                    data = p.read_bytes()
                except OSError:
                    data = None
                if data is not None and b"\0" not in data[:8192]:
                    entry["sha256"] = hashlib.sha256(data).hexdigest()
                    if blobs is not None:
                        blobs.put(data)
            files[rel] = entry
    return files, truncated


def snapshot(services, task_id: str, phase: str) -> dict:
    """Record the project as it is now ('start' once per task, 'end' when it finishes). Idempotent for 'start'."""
    _ensure(services)
    if phase == "start" and get(services, task_id, "start"):
        return get(services, task_id, "start")
    files, truncated = _scan(Path(services.config.root), services.blobs)
    doc = {"task_id": task_id, "phase": phase, "at": ids.now(), "files": files, "truncated": truncated}
    with services.db.tx() as c:
        c.execute("INSERT INTO workspace_snapshots VALUES (?,?,?,?) ON CONFLICT(task_id, phase) DO UPDATE SET at = excluded.at, "
                  "doc = excluded.doc", (task_id, phase, doc["at"], dumps(doc)))
    return doc


def get(services, task_id: str, phase: str) -> dict | None:
    _ensure(services)
    row = services.db.one("SELECT doc FROM workspace_snapshots WHERE task_id = ? AND phase = ?", (task_id, phase))
    return json.loads(row["doc"]) if row else None


def changes(services, task_id: str) -> dict | None:
    """Files added, deleted or modified between the task's start and its end (or now, while it runs)."""
    start = get(services, task_id, "start")
    if start is None:
        return None
    end = get(services, task_id, "end")
    after, against = (end["files"], "end") if end else (_scan(Path(services.config.root))[0], "now")
    before = start["files"]
    added = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = []
    for path in sorted(set(before) & set(after)):
        a, b = before[path], after[path]
        if "sha256" in a and "sha256" in b:
            if a["sha256"] != b["sha256"]:
                modified.append({"path": path, "text": True})
        elif (a["size"], a["mtime_ns"]) != (b["size"], b["mtime_ns"]):
            modified.append({"path": path, "text": False})
    return {"task_id": task_id, "since": start["at"], "until": end["at"] if end else None, "against": against,
            "added": added, "deleted": deleted, "modified": modified, "truncated": start["truncated"]}


def diff(services, task_id: str, path: str) -> str:
    """Unified diff of one text file between the start snapshot and the end snapshot (or the file now)."""
    start, end = get(services, task_id, "start"), get(services, task_id, "end")
    if start is None:
        return ""

    def content(snap, now: bool) -> bytes | None:
        if now:
            p = Path(services.config.root) / path
            return p.read_bytes() if p.is_file() else None
        entry = snap["files"].get(path)
        if not entry or "sha256" not in entry or not services.blobs.exists(entry["sha256"]):
            return None
        return services.blobs.get(entry["sha256"])

    old_b = content(start, False)
    new_b = content(end, False) if end else content(None, True)
    # Compare lines without their endings: a CRLF/LF switch would otherwise show every line as changed.
    old = old_b.decode("utf-8", errors="replace").splitlines() if old_b is not None else []
    new = new_b.decode("utf-8", errors="replace").splitlines() if new_b is not None else []
    lines = list(difflib.unified_diff(old, new, f"a/{path}（开始时）", f"b/{path}（{'结束时' if end else '现在'}）",
                                      n=3, lineterm=""))
    if not lines and old_b is not None and new_b is not None and old_b != new_b:
        return "（内容相同，只有换行符或文件末尾的换行不同）\n"
    if len(lines) > MAX_DIFF_LINES:
        lines = lines[:MAX_DIFF_LINES] + [f"…（差异太长，只显示前 {MAX_DIFF_LINES} 行）"]
    return "\n".join(lines) + ("\n" if lines else "")


# --- what the agents did -------------------------------------------------------------------------------

def timeline(services, root_id: str, limit: int = 2000) -> list[dict]:
    """Every action of every agent in the investigation, oldest first, from the journal."""
    tree = orch.tree(services, root_id)
    titles = {t: (orch.task_row(services, t) or {}).get("title", "") for t in tree}
    out = []
    for i in range(0, len(tree), 500):
        chunk = tree[i:i + 500]
        rows = services.db.query(
            f"SELECT doc FROM journal WHERE task_id IN ({','.join('?' * len(chunk))}) AND type IN "
            "('tool_call', 'tool_result', 'model_response', 'model_error', 'model_switch', 'budget_stop', 'stall_stop', 'state_change') "
            "ORDER BY seq", chunk)
        out += [json.loads(r["doc"]) for r in rows]
    out.sort(key=lambda e: e["seq"])
    for e in out:  # entries written before 10-30 kept only a preview of big data inline: read the original
        if e["type"] in ("tool_call", "tool_result") and e["data"].get("truncated") and "call_id" not in e["data"]:
            e["data"] = (services.journal.original(e) or {}).get("data") or e["data"]
    items, results = [], {}
    for e in out:
        if e["type"] == "tool_result":
            results[e["data"].get("call_id")] = e
    for e in out[-limit * 2:]:
        d = e["data"]
        base = {"at": e["at"], "agent": e["agent"], "task_id": e.get("task_id"), "task": titles.get(e.get("task_id"), ""), "seq": e["seq"]}
        if e["type"] == "tool_call":
            res = results.get(d.get("call_id"))
            items.append({**base, "kind": "tool", "tool": d.get("tool", "?"), "arguments": d.get("arguments", {}),
                          "ok": None if res is None else res["data"].get("ok"), "result_entry": res["id"] if res else None})
        elif e["type"] == "model_response":
            payload = services.journal.original(e).get("payload") or {}
            text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
            if text:
                items.append({**base, "kind": "answer" if not d.get("tool_calls") else "thought", "text": text})
        elif e["type"] == "model_error":
            items.append({**base, "kind": "error", "text": d.get("error", "")})
        elif e["type"] == "model_switch":
            items.append({**base, "kind": "switch", "text": d.get("to", "")})
        elif e["type"] in ("budget_stop", "stall_stop"):
            items.append({**base, "kind": "stop", "text": e["type"]})
        elif e["type"] == "state_change" and d.get("state") in ("interrupted", "resumed", "error"):
            items.append({**base, "kind": "state", "text": d["state"] + (f": {d['reason']}" if d.get("reason") else "")})
    return items[-limit:]


def files_read(services, root_id: str) -> list[dict]:
    """Project files the agents read, with the line ranges and evidence ids (citable excerpts)."""
    by_path: dict[str, dict] = {}
    for item in timeline(services, root_id):
        if item["kind"] != "tool" or not item["result_entry"]:
            continue
        res = services.journal.get(item["result_entry"])
        data = services.journal.original(res)["data"] if res["data"].get("truncated") else res["data"]
        for ev in data.get("evidence", []):
            parsed = parse_code_id(ev)
            if not parsed:
                continue
            entry = by_path.setdefault(parsed["path"], {"path": parsed["path"], "ranges": [], "evidence": [], "agents": []})
            lines = ev.rsplit(":", 1)[-1] if ev.rsplit(":", 1)[-1].startswith("L") else "全文"
            if ev not in entry["evidence"]:
                entry["evidence"].append(ev)
                entry["ranges"].append(lines)
            if item["agent"] not in entry["agents"]:
                entry["agents"].append(item["agent"])
    return sorted(by_path.values(), key=lambda f: f["path"])


def commands(services, root_id: str) -> list[dict]:
    """Terminal commands the agents ran (run_command and the computer-use terminal), with exit codes."""
    out = []
    for item in timeline(services, root_id):
        if item["kind"] != "tool" or item["tool"] not in ("run_command", "terminal"):
            continue
        exit_code, output = None, ""
        if item["result_entry"]:
            res = services.journal.get(item["result_entry"])
            output = services.journal.original(res).get("payload") or ""
            for line in output.splitlines()[:4]:
                if line.startswith("exit code") or "exit code" in line:
                    exit_code = line.rsplit(" ", 1)[-1].strip(".")
                    break
        out.append({"at": item["at"], "agent": item["agent"], "command": item["arguments"].get("command", ""),
                    "ok": item["ok"], "exit_code": exit_code, "output": output[-4000:]})
    return out


def claims_and_notes(services, root_id: str) -> dict:
    tree = orch.tree(services, root_id)
    return {"claims": [c for t in tree for c in services.claims.by_task(t)],
            "notes": [n for t in tree for n in services.notes.by_task(t) if n["kind"] != "summary"]}


# --- undo ---------------------------------------------------------------------------------------------

ENGINE_WRITES = ("Edit", "MultiEdit", "Write", "NotebookEdit", "Create", "Delete", "Rename")
_WROTE = re.compile(r"^changed (\S+?): \+(\d+) -(\d+) lines")


def written_by_agents(services, task_id: str) -> set[str]:
    """Project paths the investigation's agents wrote, from the journal (edit_file / create_file results)."""
    paths: set[str] = set()
    for tid in orch.tree(services, task_id):
        for e in services.journal.read(task_id=tid, limit=5000):
            a = e["data"].get("arguments") or {}
            if e["type"] == "tool_call" and e["data"].get("tool") in ("claude_code", "codex") and isinstance(a, dict)                     and a.get("tool") in ENGINE_WRITES and a.get("path"):
                # Claude Code and Codex write with their own tools: each step is journaled as {"tool": "Edit", "path": ...}
                paths.add(str(a["path"]).replace("\\", "/"))
                continue
            if e["type"] != "tool_result" or e["data"].get("tool") not in ("edit_file", "create_file") or not e["data"].get("ok"):
                continue
            text = str((services.journal.original(e) or {}).get("payload") or "")
            first = text.splitlines()[0] if text else ""
            if first.startswith("created "):
                m = re.search(r"changed (\S+?): ", text)
                paths.add(m.group(1) if m else first[8:])
            else:
                m = _WROTE.match(first)
                if m:
                    paths.add(m.group(1))
    return paths


def revert(services, task_id: str) -> dict:
    """Put the project back as it was when the investigation started - but only files the investigation's agents wrote
    (journal records), and only while they are still exactly as the investigation left them. Anything else changed
    during the investigation (by you or another program) is skipped and listed, never touched. Binary files and files
    whose start content was not stored are listed, never touched."""
    start, end = get(services, task_id, "start"), get(services, task_id, "end")
    out = {"restored": [], "removed": [], "skipped": []}
    if start is None or end is None:
        out["skipped"].append({"path": "*", "why": "这次调查还没结束或没有快照，不能撤回"})
        return out
    root = Path(services.config.root)
    now, _ = _scan(root)
    before, after = start["files"], end["files"]
    mine = written_by_agents(services, task_id)
    for path in sorted(set(before) | set(after)):
        a, b, cur = before.get(path), after.get(path), now.get(path)
        if a == b or (a and b and a.get("sha256") and a.get("sha256") == b.get("sha256")):
            continue  # not changed by the investigation
        if path not in mine:
            out["skipped"].append({"path": path, "why": "不是这次调查的 Agent 写的（你或别的程序改的），没有撤回"})
            continue
        if (cur or {}).get("sha256") != (b or {}).get("sha256") or (cur is None) != (b is None):
            out["skipped"].append({"path": path, "why": "调查结束后又被改过，为免覆盖你的修改，没有撤回"})
            continue
        p = root / path
        if a is None:  # created during the investigation
            if b and "sha256" in b:
                p.unlink()
                out["removed"].append(path)
            else:
                out["skipped"].append({"path": path, "why": "不是文本文件，没有删除"})
            continue
        if "sha256" not in a or not services.blobs.exists(a["sha256"]):
            out["skipped"].append({"path": path, "why": "开始时的内容没有保存（二进制或过大），无法恢复"})
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".cd-undo")
        tmp.write_bytes(services.blobs.get(a["sha256"]))
        os.replace(tmp, p)
        out["restored"].append(path)
    services.journal.append("system", "state_change", {"state": "reverted", "restored": out["restored"][:200],
                                                       "removed": out["removed"][:200],
                                                       "skipped": [s["path"] for s in out["skipped"]][:200]},
                            task_id=task_id)
    return out
