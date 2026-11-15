"""What the terminal and the HTTP API share - the window shows the same through its own widgets: which project to open,
which agent takes a task, the investigation's progress as readable lines, and its result."""

from __future__ import annotations

import json
import os
from pathlib import Path

from codedoctor import changes
from codedoctor.agents import orchestration as orch
from codedoctor.ui_text import describe_tool_call, task_status

PART_CN = {"main": "主力修复", "backup": "补位修复", "scout": "侦察"}


# --- which project -------------------------------------------------------------------------------------------------------

def home() -> Path:
    return Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor")


def projects() -> list[dict]:
    """The projects the window has opened, most recent first: [{name, config, root}]."""
    try:
        items = json.loads((home() / "projects.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [i for i in items if isinstance(i, dict) and i.get("config")]


def find_project(name: str | None = None, cwd: str | Path | None = None) -> dict | None:
    """By name; else the project whose code folder holds the current directory (the deepest one); else the most
    recently opened."""
    items = projects()
    if name:
        return next((i for i in items if i.get("name") == name), None)
    here = Path(cwd or Path.cwd()).resolve()
    inside = []
    for i in items:
        try:
            root = Path(i.get("root") or "").resolve()
        except OSError:
            continue
        if i.get("root") and (here == root or root in here.parents):
            inside.append((len(root.parts), i))
    if inside:
        return max(inside, key=lambda x: x[0])[1]
    return items[0] if items else None


def entry_agent(cfg) -> str:
    """The agent that takes a new task: the way of working the user chose (the window preselects the same)."""
    roles = {a.role: a.id for a in reversed(list(cfg.agents.values()))}
    if cfg.cluster.mode == "dual" and "worker" in roles:
        return roles["worker"]
    if cfg.cluster.mode not in ("basic", "dual") and "head_dispatch" in roles:
        return roles["head_dispatch"]
    if "general" in roles:
        return roles["general"]
    return next(iter(cfg.agents))


# --- progress ------------------------------------------------------------------------------------------------------------

def _line(services, e: dict, rows: dict) -> str | None:
    d, who = e["data"], e["agent"]
    if e["type"] == "tool_call":
        args = d.get("arguments") if isinstance(d.get("arguments"), dict) else {}
        return f"{who}  {describe_tool_call(d.get('tool', ''), args)}"
    if e["type"] == "test_run":
        text = f"系统跑测试（{d.get('after', '')} 改动后）：{d.get('summary', '')}"
        if d.get("regressions"):
            text += f"  注意：{len(d['regressions'])} 个原来能过的测试被改坏"
        return text
    if e["type"] != "state_change":
        return None
    st = d.get("state")
    if st == "working" and str(d.get("reason", "")).startswith("task_"):
        row = rows.get(d["reason"]) or orch.task_row(services, d["reason"]) or {}
        body = orch.body_of(row) if row else {}
        part = PART_CN.get(body.get("squad", ""), "")
        kind = f"复查（{part}）" if body.get("review_of") and part else "复查" if body.get("review_of") else part or "开始"
        return f"{who}  开始{kind}：{row.get('title', '')}" if kind != "开始" else f"{who}  开始：{row.get('title', '')}"
    if st == "scout_found":
        fixer = f"补位 {d['backup']}" if d.get("backup") else "主力"
        return f"侦察发现  {d.get('test_file', '')} 没通过（{d.get('scout') or '侦察兵'}）→ 交给{fixer}修"
    if st == "safety_net":
        n = len(d.get("undone") or [])
        return f"系统兜底  撤回了 {n} 处把测试改坏的修改；测试现在：{d.get('tests', '')}" if n else None
    if st == "final_answer":
        return f"{who}  预算快用完，开始收尾"
    if st == "tests_gate":
        return f"{who}  还不能结束：有测试没通过，系统让它先修"
    return None


def progress(services, root_task: str, after_seq: int = 0, limit: int = 500) -> tuple[list[dict], int]:
    """New readable events of the investigation since `after_seq`: ([{seq, at, text}], last seq seen)."""
    tree = orch.tree(services, root_task)
    marks = ",".join("?" * len(tree))
    found = services.db.query(f"SELECT seq FROM journal WHERE task_id IN ({marks}) AND seq > ? ORDER BY seq LIMIT ?",
                              (*tree, after_seq, limit))
    if not found:
        return [], after_seq
    rows = {t: orch.task_row(services, t) for t in tree}
    out, last = [], after_seq
    for tid in tree:
        for e in services.journal.read(task_id=tid, after_seq=after_seq, limit=limit):
            text = _line(services, e, rows)
            if text:
                out.append({"seq": e["seq"], "at": e.get("at"), "text": text})
    last = found[-1]["seq"]
    out.sort(key=lambda x: x["seq"])
    return [x for x in out if x["seq"] <= last], last


# --- result --------------------------------------------------------------------------------------------------------------

def team(services, root_task: str) -> list[dict]:
    """Every subtask: who, which part, what, status, and the first line of its report."""
    out = []
    for t in orch.tree(services, root_task)[1:]:
        row = orch.task_row(services, t)
        if not row:
            continue
        body = orch.body_of(row)
        rep = orch.report_of(services, t) or {}
        summary = rep.get("summary", "")
        first = next((ln.strip() for ln in summary.splitlines() if ln.strip()), "")
        out.append({"task_id": t, "agent": row["agent"], "part": PART_CN.get(body.get("squad", ""), ""),
                    "review_of": body.get("review_of"), "title": row["title"], "status": task_status(row),
                    "state": row["state"], "outcome": row["outcome"], "first_line": first[:200]})
    return out


def result(services, task_id: str) -> dict | None:
    """The investigation as the window shows it: status, answer, team, changes, tests, scout findings."""
    row = orch.task_row(services, task_id)
    if row is None:
        return None
    rep = orch.report_of(services, task_id) or {}
    info = changes.collect(services, task_id)
    text, level = changes.verdict(info)
    usage = json.loads(row["usage"]) if isinstance(row.get("usage"), str) and row["usage"] else (row.get("usage") or {})
    return {
        "task_id": task_id, "title": row["title"], "agent": row["agent"], "state": row["state"], "outcome": row["outcome"],
        "status": task_status(row), "answer": rep.get("summary"), "usage": usage,
        "team": team(services, task_id),
        "changes": [{"path": p, "added": v[0], "removed": v[1], "by": sorted(v[2])} for p, v in sorted(info["files"].items())],
        "tests": {"verdict": text, "level": level, "runs": info["runs"],
                  "summary": (info["last"] or {}).get("summary"),
                  "regressions": (info["last"] or {}).get("regressions") or [],
                  "not_passing_yet": (info["last"] or {}).get("open") or []},
        "findings": changes.findings(info),
    }


def settled(services, task_id: str) -> bool:
    """The investigation and every subtask (guardian reviews included) are finished."""
    return all((orch.task_row(services, t) or {}).get("state") == "finished" for t in orch.tree(services, task_id))


def cancel(daemon, task_id: str) -> None:
    """Cancel the investigation; its subtasks stop with it (the window's 取消任务)."""
    row = orch.task_row(daemon.s, task_id)
    if row is None:
        raise KeyError(f"unknown task {task_id!r}")
    daemon.control(row["agent"], "cancel_task", task_id=task_id)
    for t in orch.tree(daemon.s, task_id)[1:]:
        sub = orch.task_row(daemon.s, t)
        if sub and sub["state"] != "finished":
            daemon.control(sub["agent"], "cancel_task", task_id=t)
