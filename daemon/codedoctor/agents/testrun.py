"""The project's tests, run by the system - not by a model (ADR 0016).

When the project names a test command (permissions.test_command), the system runs it before the first change of an
investigation (the baseline), after every change a worker makes, and before a worker or the dispatch head may finish.
Two kinds of new failure are told apart:
- a REGRESSION: a test that passed in the baseline fails now - some change broke it; it must be fixed first;
- an OPEN test: a test that did not exist in the baseline and does not pass yet - usually a worker's test for a
  defect that is not fixed yet. It blocks the worker that wrote it, not the others.
Real run with 20 agents: one worker made payment records inconsistent inside its own file, 23 tests failed and nobody
noticed - every guardian had run out of budget. Running the tests costs no model tokens.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field

_FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)
_PASSED = re.compile(r"^PASSED (\S+)", re.M)
_SUMMARY = re.compile(r"^=*\s*((?:\d+ \w+(?:, )?)+) in [\d.]+s", re.M)
_lock = threading.Lock()
_locks: dict[str, threading.Lock] = {}


@dataclass
class Result:
    ran: bool
    exit_code: int = 0
    failed: set[str] = field(default_factory=set)
    passed: set[str] = field(default_factory=set)
    summary: str = ""
    evidence: str = ""
    output: str = ""


@dataclass
class Change:
    """Compared with the baseline."""
    result: Result
    regressions: set[str]   # passed before, fail now
    open: set[str]          # new tests that do not pass yet

    @property
    def new(self) -> set[str]:
        return self.regressions | self.open


def command(services) -> str:
    return services.config.permissions.test_command


def _argv(cmd: str) -> list[str]:
    argv = shlex.split(cmd, posix=True)
    if argv and not os.path.isabs(argv[0]):
        # Windows keeps npm as npm.CMD, which only a shell finds by the bare name: the full path is what subprocess needs
        # (Haiku check item 13: "npm test" failed with WinError 2)
        argv[0] = shutil.which(argv[0]) or argv[0]
    if "pytest" in cmd and not any(a.startswith("-r") for a in argv):
        argv.append("-rA")  # name the passing tests too, so a regression can be told from a new failing test
    return argv


def _test_file(test_id: str) -> str:
    return test_id.split("::", 1)[0]


_last: dict[str, tuple[float, "Result"]] = {}  # project root -> (when the last run started, its result)


def _lock_for(key: str) -> threading.Lock:
    with _lock:
        return _locks.setdefault(key, threading.Lock())


def run(services, agent_id: str = "system", timeout: int = 300, root=None) -> Result:
    """`root`: a work folder other than the project (an alternate pair's copy)."""
    cmd = command(services)
    if not cmd:
        return Result(ran=False)
    asked = time.monotonic()
    cwd = root or services.config.root
    key = str(cwd)
    with _lock_for(key):  # one run at a time per folder: parallel workers would otherwise race half-written files
        done = _last.get(key)
        if done and done[0] >= asked:
            # a run that started after this request already saw this change: share it (stress run with 40 agents:
            # 19 workers queued one run each behind a lock and the investigation took 39 minutes)
            return done[1]
        started = time.monotonic()
        try:
            proc = subprocess.run(_argv(cmd), cwd=cwd, capture_output=True, timeout=timeout,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            out = (proc.stdout + b"\n" + proc.stderr).decode("utf-8", errors="replace")
            code = proc.returncode
        except subprocess.TimeoutExpired:
            out, code = f"test command timed out after {timeout}s", -1
        except OSError as e:
            out, code = f"test command could not start: {e}", -1
        return _record(services, cmd, code, out, agent_id, key, started, cwd)


def _record(services, cmd, code, out, agent_id, key, started, cwd) -> Result:
    ev = services.evidence.add_test_run(cwd, cmd, code, out[-200000:], agent_id=agent_id,
                                        data_class=services.config.code_data_class)
    failed, passed = set(_FAILED.findall(out)), set(_PASSED.findall(out))
    if code not in (0, 5) and not failed:  # crashed before reporting tests (import error, syntax error)
        failed = {"<the test run itself: " + (out.strip().splitlines() or ["?"])[-1][:160] + ">"}
    m = _SUMMARY.search(out)
    res = Result(ran=True, exit_code=code, failed=failed, passed=passed,
                 summary=m.group(1) if m else f"exit code {code}", evidence=ev, output=out)
    _last[key] = (started, res)
    return res


def baseline(services, root_task: str, root=None) -> Result:
    """The tests before this investigation changed anything (run once per work folder, at its first change). Kept in
    the project's database, so a service that restarts and carries on still compares with the tests as they were
    before the change (Haiku check item 7: it used to be taken again on the already changed code)."""
    cache = services.__dict__.setdefault("_test_baseline", {})
    key = (root_task, str(root or ""))
    if key in cache:
        return cache[key]
    _ensure_baselines(services)
    row = services.db.one("SELECT doc FROM test_baselines WHERE key = ?", (_baseline_key(*key),))
    if row is not None:
        d = json.loads(row["doc"])
        cache[key] = Result(ran=True, exit_code=d["exit_code"], failed=set(d["failed"]), passed=set(d["passed"]),
                            summary=d["summary"], evidence=d["evidence"])
        return cache[key]
    cache[key] = run(services, root=root)
    if cache[key].ran:
        doc = {"exit_code": cache[key].exit_code, "failed": sorted(cache[key].failed), "passed": sorted(cache[key].passed),
               "summary": cache[key].summary, "evidence": cache[key].evidence}
        with services.db.tx() as c:
            c.execute("INSERT OR REPLACE INTO test_baselines (key, doc) VALUES (?, ?)",
                      (_baseline_key(*key), json.dumps(doc, ensure_ascii=False)))
    return cache[key]


def _baseline_key(root_task: str, root: str) -> str:
    return f"{root_task}|{root}"


def _ensure_baselines(services) -> None:
    with services.db.tx() as c:
        c.execute("CREATE TABLE IF NOT EXISTS test_baselines (key TEXT PRIMARY KEY, doc TEXT NOT NULL)")


def check(services, root_task: str, agent_id: str, root=None) -> Change:
    base = baseline(services, root_task, root)
    res = run(services, agent_id, root=root)
    known = base.passed | base.failed
    whole_run_broke = {f for f in res.failed if f.startswith("<the test run itself")} - base.failed
    regressions = {f for f in res.failed if f in base.passed} | whole_run_broke
    return Change(res, regressions, {f for f in res.failed if f not in known and f not in whole_run_broke})


def own_test_files(services, task_id: str) -> set[str]:
    """Test files this task created or changed."""
    from codedoctor.agents.ownership import is_test

    calls = {}
    out = set()
    for e in services.journal.read(task_id=task_id):
        d = e["data"]
        if e["type"] == "tool_call" and d.get("tool") in ("edit_file", "create_file"):
            calls[d.get("call_id")] = (d.get("arguments") or {}).get("path", "")
        elif e["type"] == "tool_result" and d.get("ok") and d.get("call_id") in calls:
            path = calls[d["call_id"]].replace("\\", "/").lstrip("./")
            if is_test(path):
                out.add(path)
    return out


def blocking(change: Change, own_test_files: set[str]) -> set[str]:
    """What keeps a worker from finishing: every regression, and its own new tests that do not pass."""
    return change.regressions | {f for f in change.open if _test_file(f) in own_test_files}


def describe(change: Change, own_test_files: set[str] | None = None) -> str:
    res = change.result
    if not res.ran:
        return ""
    text = f"tests now: {res.summary} (evidence {res.evidence})"
    if change.regressions:
        text += ("\nREGRESSIONS - these tests passed before this investigation and fail now; a change broke them, fix "
                 "them before anything else:\n- " + "\n- ".join(sorted(change.regressions)[:20]))
    if change.open:
        mine = {f for f in change.open if own_test_files is not None and _test_file(f) in own_test_files}
        if mine:
            text += "\nYour new tests that do not pass yet:\n- " + "\n- ".join(sorted(mine)[:20])
        others = sorted(change.open - mine)
        if others:
            text += ("\nNew tests (by this investigation) that do not pass yet - defects still open, not necessarily "
                     "yours:\n- " + "\n- ".join(others[:20]))
    if change.regressions or (own_test_files and change.open & {f for f in change.open if _test_file(f) in own_test_files}):
        text += "\n" + why_failed(res.output)
    return text


def why_failed(output: str, limit: int = 25) -> str:
    """The failing tests with their reasons, and the error lines (pytest -rA puts dozens of PASSED lines last, so
    the tail of the output may not show why anything failed)."""
    lines = output.strip().splitlines()
    out = list(dict.fromkeys(ln[:300] for ln in lines if ln.startswith(("FAILED ", "ERROR ", "E   "))))
    body = out[:limit] or [ln for ln in lines if not ln.startswith("PASSED ")][-limit:]
    return "why they fail (from the test output):\n" + "\n".join(body)


def note_edit(services, root_task: str, task_id: str, agent_id: str, path: str, old: str | None, new: str,
              regressions: set[str]) -> None:
    """One change (old None: a created file) and the regressions seen right after it, in order."""
    services.__dict__.setdefault("_edits", {}).setdefault(root_task, []).append(
        {"task": task_id, "agent": agent_id, "path": path, "old": old, "new": new, "regressions": set(regressions)})


def _culprit(edits: list[dict], regressions: set[str]) -> dict | None:
    """The earliest change still in place after which one of these regressions first appeared."""
    before: set[str] = set()
    for e in edits:
        if (e["regressions"] - before) & regressions and not e.get("undone") and not e.get("stuck"):
            return e
        before = e["regressions"]
    return None


def _undo(services, edits: list[dict], culprit: dict) -> list[dict]:
    """Undo the culprit and the later changes to the same file (newest first), all or nothing."""
    import os

    path = services.config.root / culprit["path"]
    later = [e for e in edits[edits.index(culprit):] if e["path"] == culprit["path"] and not e.get("undone")]
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    undone = []
    for e in reversed(later):
        if e["old"] is None:  # a created file: removed only if nobody changed it since
            if text != e["new"]:
                return []
            text = None
        elif text is None or not e["new"] or text.count(e["new"]) != 1:
            return []  # the change cannot be found exactly any more: leave the file alone
        else:
            text = text.replace(e["new"], e["old"], 1)
        undone.append(e)
    if text is None:
        path.unlink()
    else:
        tmp = path.with_name(path.name + ".cd-tmp")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    for e in undone:
        e["undone"] = True
    return undone


def safety_net(services, root_task: str) -> str:
    """Every agent has stopped. If a test that passed before this investigation still fails, the system undoes the
    change after which it broke - so the code is never left worse than it was - and says so. No model tokens."""
    edits = services.__dict__.get("_edits", {}).get(root_task)
    if not command(services) or not edits:
        return ""
    change = check(services, root_task, "system")
    if not change.regressions:
        return ""
    broken = set(change.regressions)
    undone: list[dict] = []
    for _ in range(10):
        culprit = _culprit(edits, change.regressions)
        if culprit is None:
            break
        done = _undo(services, edits, culprit)
        if not done:
            culprit["stuck"] = True
            continue
        undone += done
        change = check(services, root_task, "system")
        if not change.regressions:
            break
    if not undone:
        text = ("SAFETY NET: tests that passed before this investigation still fail and no change could be undone "
                "automatically:\n- " + "\n- ".join(sorted(change.regressions)[:20]))
    else:
        files = sorted({e["path"] for e in undone})
        text = (f"SAFETY NET: every agent had stopped and {len(broken)} test(s) that passed before still failed, so the "
                f"system undid {len(undone)} change(s) in {', '.join(files)} (by "
                f"{', '.join(sorted({e['agent'] for e in undone}))}). Tests now: {change.result.summary}.")
        if change.regressions:
            text += "\nStill failing:\n- " + "\n- ".join(sorted(change.regressions)[:20])
    services.journal.append("system", "state_change", {
        "state": "safety_net", "broken": sorted(broken)[:50], "undone": [{"path": e["path"], "agent": e["agent"], "task": e["task"]}
                                                                    for e in undone][:50],
        "still_failing": sorted(change.regressions)[:50], "tests": change.result.summary, "evidence": change.result.evidence},
        task_id=root_task)
    return text


def last(services, root=None) -> Result | None:
    done = _last.get(str(root or services.config.root))
    return done[1] if done else None
