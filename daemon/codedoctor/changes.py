"""What an investigation changed and what the system's last test run says (ADR 0016) - shared by the window, the
terminal and the HTTP API. Read from the journal; nothing here calls a model."""

from __future__ import annotations

import re

from codedoctor.agents import orchestration as orch

_CHANGED = re.compile(r"^changed (\S+?): \+(\d+) -(\d+) lines")


_cache: dict[str, tuple[tuple, dict]] = {}  # root task -> (journal signature, result)


def collect(services, root_task: str) -> dict:
    """{"files": {path: [added, removed, {agents}]}, "last": test_run data or None, "runs": n}. The task page asks
    every second; the journal is read again only when the investigation wrote something new."""
    tree = orch.tree(services, root_task)
    marks = ",".join("?" * len(tree))
    sig = (len(tree), services.db.one(f"SELECT MAX(seq) AS n FROM journal WHERE task_id IN ({marks})", tree)["n"])
    hit = _cache.get(root_task)
    if hit and hit[0] == sig:
        return hit[1]
    result = _collect(services, tree)
    _cache[root_task] = (sig, result)
    return result


def _collect(services, tree: list[str]) -> dict:
    files: dict[str, list] = {}
    found: dict[str, dict] = {}  # scout test file -> the system's record of the finding (squad, ADR 0016 item 14)
    last, runs = None, 0
    for tid in tree:
        for e in services.journal.read(task_id=tid, limit=5000):
            d = e["data"]
            if e["type"] == "state_change" and d.get("state") == "scout_found":
                found.setdefault(d["test_file"], d)
            elif e["type"] == "state_change" and d.get("state") == "backup_dispatch":
                for t in d.get("tasks") or []:
                    row = orch.task_row(services, t) or {}
                    for f in orch.body_of(row).get("files") or []:
                        if f in found and not found[f].get("backup"):
                            found[f] = {**found[f], "backup": row.get("agent")}
            elif e["type"] == "test_run":
                runs += 1
                if last is None or e["seq"] > last[0]:
                    last = (e["seq"], d)
            elif e["type"] == "tool_result" and d.get("tool") in ("edit_file", "create_file") and d.get("ok"):
                text = str((services.journal.original(e) or {}).get("payload") or "")
                first = text.splitlines()[0] if text else ""
                if first.startswith("created "):
                    m2 = re.search(r"changed (\S+?): \+(\d+) -(\d+) lines", text)
                    path, add, rem = (m2.group(1), int(m2.group(2)), int(m2.group(3))) if m2 else (first[8:], 0, 0)
                else:
                    m = _CHANGED.match(first)
                    if not m:
                        continue
                    path, add, rem = m.group(1), int(m.group(2)), int(m.group(3))
                entry = files.setdefault(path, [0, 0, set()])
                entry[0] += add
                entry[1] += rem
                entry[2].add(e["agent"])
    return {"files": files, "last": last[1] if last else None, "runs": runs, "found": found}


def verdict(info: dict) -> tuple[str, str]:
    """(short text, level) for the test state; level is none / red / amber / green."""
    last = info["last"]
    if last is None:
        return ("还没有跑过测试" if info["files"] else "还没有修改", "none")
    reg, opn = last.get("regressions") or [], last.get("open") or []
    if reg:
        return (f"{len(reg)} 个原来能过的测试被改坏了", "red")
    if opn:
        return (f"还有 {len(opn)} 个新写的测试没通过", "amber")
    summary = str(last.get("summary", ""))
    if last.get("exit_code") not in (0, None) or re.search(r"\b\d+ (failed|errors?)\b", summary):
        # not a green light either; and only said to be "failed before this work" when the record shows every failing
        # test was already failing in the baseline (taken before the first change)
        failed, base_failed = last.get("failed"), last.get("baseline_failed")
        if failed and base_failed is not None and set(failed) <= set(base_failed):
            return (f"测试没有全过（{summary}）：失败的测试在这次修改之前就没过（基线里已记录），这次没有改坏新的", "amber")
        return (f"测试没有全过（{summary}）", "amber")
    return (f"测试全部通过（{summary}）", "green")


def findings(info: dict) -> list[dict]:
    """The scouts' findings: [{test, path, scout, fixer, fixed}] - fixed by the system's last test run."""
    still = {x.split("::", 1)[0] for x in ((info["last"] or {}).get("open") or [])
             + ((info["last"] or {}).get("regressions") or [])}
    out = []
    for path, d in sorted((info.get("found") or {}).items()):
        out.append({"test": path.rsplit("/", 1)[-1].removesuffix(".py").removeprefix("test_scout_"), "path": path,
                    "scout": d.get("scout"), "fixer": d.get("backup") or "主力", "fixed": path not in still})
    return out
