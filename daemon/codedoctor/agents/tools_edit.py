"""Changing code: exact-match edits and new files inside the project (ADR 0016).

Offered only when the project allows write_files, and only to the roles that do the work (worker, investigator,
general); guardians and heads never edit. Every change is recorded as evidence - the unified diff plus the changed
lines as they now read - so a guardian can review exactly what changed and re-run the tests against it.
An edit must name text that occurs exactly once (or say replace_all): a stale or ambiguous edit is refused instead
of landing in the wrong place, which also makes two workers editing one file safe.
"""

from __future__ import annotations

import difflib
import os
import threading

from codedoctor.agents.tools import (DEFAULT_TOOLS, SKIP_DIRS, TOOLS, Tool, ToolContext, ToolResult, _code_class, _err, _obj,
                                     _safe_path, root_of)

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock(path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(str(path).lower(), threading.Lock())


def _allowed(ctx: ToolContext) -> str | None:
    if not ctx.services.config.permissions.write_files:
        return "changing files is disabled in this project's permissions (write_files = false)"
    return None


def _squad_role(ctx: ToolContext) -> str | None:
    from codedoctor.agents import orchestration as orch

    return orch.body_of(orch.task_row(ctx.services, ctx.task_id) or {}).get("squad")


def _origin(ctx: ToolContext, root_task: str, test: str) -> str:
    """'  [failed on the original code: found a bug]' / '  [passed on the original code: old behaviour]' for a test
    written in a squad investigation (its original copy exists); nothing otherwise. One run per test file."""
    from codedoctor.agents import squad

    path = test.split("::", 1)[0]
    if not squad.original_dir(ctx.services, root_task).exists():
        return ""
    seen = ctx.services.__dict__.setdefault("_on_original", {})
    if (root_task, path) not in seen:
        seen[(root_task, path)] = squad.passes_on_original(ctx.services, root_task, path)
    on_original = seen[(root_task, path)]
    if on_original is None:
        return ""
    return "  [passed on the original code: old behaviour]" if on_original else "  [failed on the original code: found a bug]"


def _scout_refuses(ctx: ToolContext, rel: str) -> str | None:
    from codedoctor.agents.ownership import is_test

    if _squad_role(ctx) == "scout" and not is_test(rel):
        return (f"{rel} is not a test file: a scout writes tests only (tests/...), the fixers change the code. Put "
                "your check in a test file.")
    return None


def _tests_after(ctx: ToolContext, rel: str = "", old: str | None = None, new: str = "",
                 undoable: bool = True) -> tuple[str, list[str]]:
    """Live supervision: the system runs the project's tests after the change and reports new failures at once.
    The change is remembered with what broke right after it, so the system can undo it if nobody repairs it."""
    from codedoctor.agents import orchestration as orch, testrun

    if not testrun.command(ctx.services):
        return "", []
    root_task = orch.root_of(ctx.services, ctx.task_id)
    before = testrun.last(ctx.services, ctx.root)  # the run just before this change (anyone's)
    change = testrun.check(ctx.services, root_task, ctx.agent_id, root=ctx.root)
    # Tests written in this investigation are not in the baseline, so breaking one was not a "regression". A real
    # run: a fixer added the duplicate-borrow guard, a contradictory scout test then failed, and it deleted the guard
    # again - flipping the scout test that confirmed the fix back to failing. Say it the moment it happens.
    flipped = sorted({f for f in change.result.failed if before and f in before.passed} - change.regressions)
    flip_note = ""
    if flipped and rel:
        fixed = sorted(f for f in change.result.passed if before and f in before.failed)
        # 20 agents wrote two scout tests that borrow one book over and over; both looked as valid as the one that
        # found the double-borrow bug. Whether a test failed on the ORIGINAL code tells them apart.
        flip_note = ("\n\nBROKEN JUST NOW - these passed in the run right before this change and fail after it:\n- "
                     + "\n- ".join(f + _origin(ctx, root_task, f) for f in flipped[:12]))
        if fixed:
            flip_note += "\nThis change made these pass:\n- " + "\n- ".join(f + _origin(ctx, root_task, f) for f in fixed[:8])
        flip_note += ("\nThe two groups may contradict each other: the README and the task decide which is right. A test "
                      "that FAILED on the original code found a bug; one that PASSED there only describes the old "
                      "behaviour, which may be the very bug - unless the README backs it, the bug-finding test wins. Do "
                      "not satisfy one test by undoing a fix another test confirms; if a test is wrong, say so in one "
                      "line instead of changing code for it.")
    if rel and undoable and not ctx.root:  # the safety net watches the project, not an alternate's copy
        testrun.note_edit(ctx.services, root_task, ctx.task_id, ctx.agent_id, rel, old, new, change.regressions)
    res = change.result
    found = ""
    if rel and _squad_role(ctx) == "scout":
        from codedoctor.agents import squad

        failing = {f for f in change.open if f.split("::", 1)[0] == rel}
        warned = ctx.services.__dict__.setdefault("_scout_warned", set())
        if not failing and rel not in warned and squad.passes_on_original(ctx.services, root_task, rel):
            warned.add(rel)
            found = (f"\n\nSCOUT: {rel} passes even on the ORIGINAL code, from before anyone changed anything - so it "
                     "does not reproduce a bug. If your scenario is one of the complaints in the task, your test misses "
                     "it: reproduce exactly what the user reported (the same steps and values, and check the state "
                     "after, e.g. the second booking/borrow/charge really refused, counts and balances unchanged) with "
                     "edit_file. If the scenario is a rule that already held, keep the test and go on.")
        if failing:
            told = squad.scout_found(ctx.services, root_task, ctx.task_id, rel, failing, testrun.why_failed(res.output, 12))
            found = (f"\n\nSCOUT: your test fails, so it found a bug (or the test is wrong - check it against the spec). "
                     f"The system handed it to {told} fixer(s) now. Do not change it to pass; go on with your next scenario.")
    from codedoctor.agents import orchestration as orch

    base = testrun.baseline(ctx.services, orch.root_of(ctx.services, ctx.task_id), root=ctx.root)  # cached: taken before the first change
    ctx.services.journal.append("system", "test_run", {"after": ctx.agent_id, "exit_code": res.exit_code,
                                                       "summary": res.summary, "regressions": sorted(change.regressions)[:50],
                                                       "open": sorted(change.open)[:50], "new_failures": sorted(change.new)[:50],
                                                       "failed": sorted(res.failed), "baseline_failed": sorted(base.failed),
                                                       "evidence": res.evidence}, task_id=ctx.task_id)
    mine = testrun.own_test_files(ctx.services, ctx.task_id)
    return "\n\n" + testrun.describe(change, mine) + flip_note + found, [res.evidence]


def _baseline_first(ctx: ToolContext) -> None:
    """Record the failures that existed before this investigation's first change."""
    from codedoctor.agents import orchestration as orch, testrun

    if testrun.command(ctx.services):
        testrun.baseline(ctx.services, orch.root_of(ctx.services, ctx.task_id), root=ctx.root)


def _foreign(ctx: ToolContext, rel: str) -> str:
    from codedoctor.agents.ownership import foreign_note

    return foreign_note(ctx.services, ctx.task_id, rel)


def _protected(rel: str) -> str | None:
    parts = rel.split("/")
    if any(part in SKIP_DIRS for part in parts[:-1]) or rel in (".", ""):
        return f"{rel} is inside {', '.join(p for p in parts if p in SKIP_DIRS) or 'the project root'}: not changed"
    return None


def _write(p, text: str) -> None:
    tmp = p.with_name(p.name + ".cd-tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, p)


def _record(ctx: ToolContext, rel: str, before: str, after: str, tool: str) -> tuple[str, list[str], str]:
    """Diff evidence plus an excerpt of the changed region as it now reads. Returns (summary, evidence, diff)."""
    diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{rel}", f"b/{rel}", n=2))
    ev = [ctx.services.evidence.add_blob(diff.encode("utf-8"), "text/x-diff", source="tool",
                                         collected_by=f"tools.{tool}/0.1.0", agent_id=ctx.agent_id,
                                         data_class=_code_class(ctx))]
    new_lines = after.splitlines()
    first = next((i for i, (a, b) in enumerate(zip(before.splitlines(), new_lines)) if a != b),
                 min(len(before.splitlines()), len(new_lines)))
    if new_lines:
        start = max(1, first + 1 - 2)
        end = min(len(new_lines), start + max(4, after.count("\n") - before.count("\n") + 6))
        code_ev, _ = ctx.services.evidence.add_code_excerpt(root_of(ctx), rel, start, end,
                                                            agent_id=ctx.agent_id, data_class=_code_class(ctx))
        ev.append(code_ev)
    added = sum(1 for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---"))
    return f"changed {rel}: +{added} -{removed} lines", ev, diff


def edit_file(ctx: ToolContext, args: dict) -> ToolResult:
    if (why := _allowed(ctx)):
        return _err(why)
    p, rel = _safe_path(ctx, args["path"])
    if (why := _protected(rel)):
        return _err(why)
    if not p.is_file():
        return _err(f"{rel} is not a file (use create_file for a new one)")
    if (why := _scout_refuses(ctx, rel)):
        return _err(why)
    old, new = args["old"], args["new"]
    if old == new:
        return _err("old and new are the same: nothing to change")
    _baseline_first(ctx)
    with _lock(p):
        before = p.read_bytes().decode("utf-8")
        if "\r\n" in before and before.count(old) == 0:  # read_file shows lines; a CRLF file needs CRLF to match
            old, new = (t.replace("\r\n", "\n").replace("\n", "\r\n") for t in (old, new))
        n = before.count(old)
        if n == 0:
            return _err(f"the text to replace does not occur in {rel} (it may have changed since you read it: read_file "
                        "it again and copy the exact text, including indentation)")
        if n > 1 and not args.get("replace_all"):
            return _err(f"the text to replace occurs {n} times in {rel}: include more surrounding lines so it is "
                        "unique, or set replace_all")
        after = before.replace(old, new) if args.get("replace_all") else before.replace(old, new, 1)
        _write(p, after)
    summary, ev, diff = _record(ctx, rel, before, after, "edit_file")
    tests, test_ev = _tests_after(ctx, rel, old, new, undoable=n == 1)
    return ToolResult(ok=True, content=f"{summary}{_foreign(ctx, rel)}\nevidence: {', '.join(ev)}\n{diff[:4000]}{tests}", evidence=ev + test_ev,
                      data_class=_code_class(ctx))


def create_file(ctx: ToolContext, args: dict) -> ToolResult:
    if (why := _allowed(ctx)):
        return _err(why)
    p, rel = _safe_path(ctx, args["path"])
    if (why := _protected(rel)):
        return _err(why)
    if (why := _scout_refuses(ctx, rel)):
        return _err(why)
    _baseline_first(ctx)
    with _lock(p):
        if p.exists():
            return _err(f"{rel} already exists: change it with edit_file")
        p.parent.mkdir(parents=True, exist_ok=True)
        _write(p, args["content"])
    summary, ev, _ = _record(ctx, rel, "", args["content"], "create_file")
    tests, test_ev = _tests_after(ctx, rel, None, args["content"])
    return ToolResult(ok=True, content=f"created {rel}\n{summary}\nevidence: {', '.join(ev)}{tests}", evidence=ev + test_ev,
                      data_class=_code_class(ctx))


EDIT_TOOLS = ("edit_file", "create_file")
for _t in [
    Tool("edit_file", "Change a project file: replace the exact text `old` (copied from read_file, including indentation; "
                      "it must occur exactly once unless replace_all) with `new`. Returns the diff as evidence.",
         _obj({"path": {"type": "string"}, "old": {"type": "string", "minLength": 1}, "new": {"type": "string"},
               "replace_all": {"type": "boolean"}}, ["path", "old", "new"]),
         edit_file, effect_class="external", retry_safe=False),
    Tool("create_file", "Create a new project file (for example a regression test). Never overwrites.",
         _obj({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
         create_file, effect_class="external", retry_safe=False),
]:
    TOOLS[_t.name] = _t
for _role in ("general", "worker", "investigator", "guardian"):  # guardian: fixes what its review finds
    DEFAULT_TOOLS[_role] = [*DEFAULT_TOOLS[_role], *EDIT_TOOLS]
if "submit_claim" not in DEFAULT_TOOLS["guardian"]:
    DEFAULT_TOOLS["guardian"] = [*DEFAULT_TOOLS["guardian"], "submit_claim"]  # offered only with write_files (usable)
if "run_command" not in DEFAULT_TOOLS["guardian"]:
    DEFAULT_TOOLS["guardian"] = [*DEFAULT_TOOLS["guardian"], "run_command"]  # re-run the tests against a fix
