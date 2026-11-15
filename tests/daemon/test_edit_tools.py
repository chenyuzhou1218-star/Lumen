"""Changing code (ADR 0016): exact-match edits and new files, only with write_files, recorded as diff evidence."""

from __future__ import annotations

from codedoctor.agents.daemon import Daemon
from codedoctor.agents.tools import TOOLS, ToolContext, execute, usable


def ctx(d, role="worker"):
    return ToolContext(services=d.s, agent_id="doctor", role=role, task_id="task_x", model={}, call_entry_id="jrn_x",
                       thread_id="thr_x", known_agents=set())


def daemon(make_config, write=True):
    return Daemon(make_config(permissions={"run_command": "deny", "write_files": write}))


def test_edit_replaces_exactly_once_and_records_the_diff(make_config, project):
    d = daemon(make_config)
    before = (project / "server/shop.py").read_text(encoding="utf-8")
    line = next(ln for ln in before.splitlines() if ln.strip())
    res = execute(TOOLS["edit_file"], ctx(d), {"path": "server/shop.py", "old": line, "new": line + "  # fixed"})
    assert res.ok and "changed server/shop.py: +1 -1 lines" in res.content
    assert (project / "server/shop.py").read_text(encoding="utf-8") == before.replace(line, line + "  # fixed", 1)
    diff = d.s.evidence.read_bytes(res.evidence[0]).decode("utf-8") if hasattr(d.s.evidence, "read_bytes") else res.content
    assert "+" + line + "  # fixed" in diff and res.evidence[1].startswith("ev:code:")


def test_missing_or_ambiguous_text_is_refused(make_config, project):
    d = daemon(make_config)
    (project / "dup.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    assert "does not occur" in execute(TOOLS["edit_file"], ctx(d), {"path": "dup.py", "old": "y = 2", "new": "z"}).content
    assert "occurs 2 times" in execute(TOOLS["edit_file"], ctx(d), {"path": "dup.py", "old": "x = 1", "new": "x = 2"}).content
    assert execute(TOOLS["edit_file"], ctx(d), {"path": "dup.py", "old": "x = 1", "new": "x = 2", "replace_all": True}).ok
    assert (project / "dup.py").read_text(encoding="utf-8") == "x = 2\nx = 2\n"


def test_create_never_overwrites_and_stays_out_of_git(make_config, project):
    d = daemon(make_config)
    assert execute(TOOLS["create_file"], ctx(d), {"path": "tests/test_new.py", "content": "def test_x():\n    pass\n"}).ok
    assert "already exists" in execute(TOOLS["create_file"], ctx(d), {"path": "tests/test_new.py", "content": ""}).content
    assert "not changed" in execute(TOOLS["create_file"], ctx(d), {"path": ".git/hooks/x", "content": "evil"}).content


def test_an_old_read_only_switch_no_longer_stops_changes(make_config, project):
    """The user's rule: no read-only members; an old write_files = false still lets the agents change files."""
    d = daemon(make_config, write=False)
    res = execute(TOOLS["create_file"], ctx(d), {"path": "a.txt", "content": "a"})
    assert res.ok and (project / "a.txt").read_text(encoding="utf-8") == "a"
    assert usable("edit_file", d.s.config) and "edit_file" in d.agents["doctor"].tools


def test_commands_run_without_a_shell_and_pipes_run_in_one(make_config, project):
    """The user's rule: any command runs (no allowlist); a plain command runs without a shell, pipes run in PowerShell."""
    d = Daemon(make_config(permissions={"run_command": "allowlist", "command_allowlist": ["python -c"]}))
    res = execute(TOOLS["run_command"], ctx(d), {"command": 'python -c "a = 1; b = 2\nprint(a + b)"'})
    assert res.ok and "exit code: 0" in res.content and "3" in res.content  # quoted newline and ';' are just text
    piped = execute(TOOLS["run_command"], ctx(d), {"command": 'python -c "print(1)" | more'})
    assert piped.ok and "exit code: 0" in piped.content and "1" in piped.content
    assert "not in allowlist" not in execute(TOOLS["run_command"], ctx(d), {"command": "git --version"}).content


def test_a_crlf_file_is_edited_with_lf_text_and_runs_are_test_evidence(make_config, project):
    d = Daemon(make_config(permissions={"run_command": "allowlist", "command_allowlist": ["python -c"], "write_files": True}))
    (project / "w.py").write_bytes(b"def f():\r\n    return 1\r\n")
    assert execute(TOOLS["edit_file"], ctx(d), {"path": "w.py", "old": "def f():\n    return 1", "new": "def f():\n    return 2"}).ok
    assert (project / "w.py").read_bytes() == b"def f():\r\n    return 2\r\n"
    res = execute(TOOLS["run_command"], ctx(d), {"command": 'python -c "print(1)"'})
    assert res.evidence[0].startswith("ev:test:") and d.s.evidence.get(res.evidence[0])["kind"] == "test"


async def test_the_worker_is_the_hands_and_the_system_reports_its_changes(make_config, project):
    """User's design (ADR 0016): every worker only works (no read-only members); its guardian reports."""
    import asyncio

    from conftest import unique_model

    w, g = unique_model(), unique_model()
    line = next(ln for ln in (project / "server/shop.py").read_text(encoding="utf-8").splitlines() if ln.strip())
    cfg = make_config({w: [{"tool_calls": [{"name": "edit_file", "arguments": {"path": "server/shop.py", "old": line,
                                                                                  "new": line + "  # fixed"}}]},
                           {"text": "done"}], g: [{"text": "checked"}]},
                      agents=[{"id": "worker-1", "role": "worker", "endpoint": "fake", "model": w},
                              {"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": g,
                               "supervises_workers": ["worker-1"]}],
                      permissions={"run_command": "deny", "write_files": True})
    d = Daemon(cfg, poll_s=0.02)
    from codedoctor import video

    # the video tools are the hands' too, but only in an investigation started with @CodeCut (runtime._task_tools)
    # the user's rule: every command and computer use are open from the start, so the hands also run commands and
    # drive the screen; they still file no claims or reports
    from codedoctor.agents.tools import HANDS_TOOLS

    assert set(d.agents["worker-1"].tools) - set(video.NAMES) <= HANDS_TOOLS
    assert not {"submit_claim", "report_anomaly", "remember"} & set(d.agents["worker-1"].tools)
    assert "submit_claim" in d.agents["guardian-1"].tools
    await d.start()
    try:
        sub = d.submit_task("worker-1", "fix", "fix shop.py")
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
    finally:
        await d.halt()
    assert report["body"]["summary"].startswith("执行者做了什么（系统记录")
    assert "修改 server/shop.py（+1 -1 行）" in report["body"]["summary"]
    from codedoctor.agents import orchestration as orch

    [review] = [c for c in orch.children(d.s, sub["task_id"]) if orch.body_of(c).get("review_of")]
    assert "+" + line + "  # fixed" in orch.body_of(review)["instructions"]  # the diff is given to the supervisor


def test_a_code_changing_cluster_hands_out_files_one_owner_each(make_config, project):
    """ADR 0016: delegate by files; one worker per file; a worker changes only its files; unowned files are listed."""
    from codedoctor.agents import orchestration as orch, ownership

    agents = [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": "d"}]
    for i in (1, 2):
        agents += [{"id": f"worker-{i}", "role": "worker", "endpoint": "fake", "model": "w"},
                   {"id": f"guardian-{i}", "role": "guardian", "endpoint": "fake", "model": "g", "supervises_workers": [f"worker-{i}"]}]
    d = Daemon(make_config(agents=agents, permissions={"run_command": "deny", "write_files": True}))
    root = d.submit_task("head-dispatch", "fix", "fix everything")["task_id"]
    head = ToolContext(services=d.s, agent_id="head-dispatch", role="head_dispatch", task_id=root, model={},
                       call_entry_id="jrn_x", thread_id="thr_x", known_agents=set())
    code = ownership.code_files(project)
    assert code and not any(ownership.is_test(f) for f in code)
    assert "give the worker its files" in execute(TOOLS["delegate"], head, {"agent": "worker-1", "title": "a", "instructions": "x"}).content
    assert execute(TOOLS["delegate"], head, {"agent": "worker-1", "title": "a", "instructions": "x", "files": [code[0]]}).ok
    taken = execute(TOOLS["delegate"], head, {"agent": "worker-2", "title": "b", "instructions": "y", "files": [code[0]]})
    assert "one file, one worker" in taken.content
    assert ownership.unowned(d.s, root) == code[1:]
    [sub] = orch.children(d.s, root)
    mine = ToolContext(services=d.s, agent_id="worker-1", role="worker", task_id=sub["id"], model={}, call_entry_id="jrn_x",
                       thread_id="thr_x", known_agents=set())
    if len(code) > 1:
        assert execute(TOOLS["create_file"], mine, {"path": "lib_new.py", "content": "x"}).ok  # interfaces cross files
        other = (project / code[1]).read_text(encoding="utf-8").splitlines()[0]
        assert execute(TOOLS["edit_file"], mine, {"path": code[1], "old": other, "new": other + " "}).ok
    assert execute(TOOLS["create_file"], mine, {"path": "tests/test_mine.py", "content": "def test_x():\n    pass\n"}).ok
    assert {"submit_claim", "report_anomaly"} & set(d.agents["head-dispatch"].tools) == set()


async def test_the_system_runs_the_tests_after_every_change_and_before_finishing(make_config, project):
    """Live supervision (ADR 0016): a change that breaks a passing test is reported at once and blocks finishing."""
    import asyncio
    import shlex
    import sys

    from conftest import unique_model

    (project / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (project / "tests").mkdir(exist_ok=True)
    (project / "tests" / "test_calc.py").write_text("from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
                                                    encoding="utf-8")
    cmd = f"{shlex.quote(sys.executable.replace(chr(92), '/'))} -m pytest -q -p no:cacheprovider tests/test_calc.py"
    w = unique_model()
    cfg = make_config({w: [
        {"tool_calls": [{"name": "edit_file", "arguments": {"path": "calc.py", "old": "a + b", "new": "a - b"}}]},
        {"text": "done"},                                   # refused: the change broke test_add
        {"tool_calls": [{"name": "edit_file", "arguments": {"path": "calc.py", "old": "a - b", "new": "a + b"}}]},
        {"text": "done, fixed"},
    ]}, agents=[{"id": "worker-1", "role": "worker", "endpoint": "fake", "model": w}],
        permissions={"run_command": "deny", "write_files": True, "test_command": cmd})
    d = Daemon(cfg, poll_s=0.02)
    await d.start()
    try:
        sub = d.submit_task("worker-1", "fix", "change calc")
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 60)
    finally:
        await d.halt()
    calls = d.s.models.client("fake").calls
    first_edit = [m.content for m in calls[1]["messages"] if m.role == "tool"][-1]
    assert "REGRESSIONS" in first_edit and "test_add" in first_edit
    assert "cannot finish yet" in calls[2]["messages"][-1].content or any(
        "cannot finish yet" in (m.content or "") for m in calls[2]["messages"])
    assert report["body"]["outcome"] == "done" and "done, fixed" in report["body"]["summary"]


def test_a_regression_is_told_from_a_new_test_that_does_not_pass_yet():
    from codedoctor.agents import testrun

    base = testrun.Result(ran=True, passed={"tests/a.py::t1"}, failed={"tests/a.py::t0"})
    now = testrun.Result(ran=True, failed={"tests/a.py::t0", "tests/a.py::t1", "tests/b.py::t2", "tests/c.py::t3"})
    known = base.passed | base.failed
    change = testrun.Change(now, {f for f in now.failed if f in base.passed}, {f for f in now.failed if f not in known})
    assert change.regressions == {"tests/a.py::t1"} and change.open == {"tests/b.py::t2", "tests/c.py::t3"}
    assert testrun.blocking(change, {"tests/b.py"}) == {"tests/a.py::t1", "tests/b.py::t2"}  # not someone else's test


def _agent_wrote(d, task, path, how="changed"):
    """What edit_file / create_file leave in the journal (tools_edit.py): the agent's own writes."""
    tool = "create_file" if how == "created" else "edit_file"
    text = f"created {path}\nchanged {path}: +1 -0 lines" if how == "created" else f"changed {path}: +1 -1 lines"
    d.s.journal.append("doctor", "tool_result", {"tool": tool, "ok": True}, task_id=task, payload=text)


def test_undo_restores_the_start_but_never_overwrites_later_edits(make_config, project):
    """One-click undo (ADR 0016): files the investigation's agents wrote go back; a file edited afterwards is skipped."""
    from codedoctor import workspace

    d = Daemon(make_config())
    sub = d.submit_task("doctor", "t", "go")["task_id"]
    (project / "a.py").write_text("a = 1\n", encoding="utf-8")
    (project / "b.py").write_text("b = 1\n", encoding="utf-8")
    workspace.snapshot(d.s, sub, "start")
    (project / "a.py").write_text("a = 2\n", encoding="utf-8")       # written by the agent (journal)
    _agent_wrote(d, sub, "a.py")
    (project / "b.py").write_text("b = 2\n", encoding="utf-8")       # written by the agent ...
    _agent_wrote(d, sub, "b.py")
    (project / "new.py").write_text("n = 1\n", encoding="utf-8")     # created by the agent
    _agent_wrote(d, sub, "new.py", how="created")
    workspace.snapshot(d.s, sub, "end")
    (project / "b.py").write_text("b = 3  # mine\n", encoding="utf-8")  # ... and edited by the user afterwards
    res = workspace.revert(d.s, sub)
    assert (project / "a.py").read_text(encoding="utf-8") == "a = 1\n"
    assert not (project / "new.py").exists()
    assert (project / "b.py").read_text(encoding="utf-8") == "b = 3  # mine\n"
    assert [s["path"] for s in res["skipped"]] == ["b.py"] and set(res["restored"]) == {"a.py"} and res["removed"] == ["new.py"]


def test_undo_never_touches_what_the_user_changed_during_the_investigation(make_config, project):
    """Haiku check 2026-11-10, item 1: edits and new files made by the user while the investigation ran are not the
    agent's, so undo leaves them alone (it used to restore notes.txt and delete mine.txt)."""
    from codedoctor import workspace

    d = Daemon(make_config())
    sub = d.submit_task("doctor", "t", "go")["task_id"]
    (project / "notes.txt").write_text("original\n", encoding="utf-8")
    workspace.snapshot(d.s, sub, "start")
    (project / "notes.txt").write_text("the user is writing here\n", encoding="utf-8")
    (project / "mine.txt").write_text("the user's new file\n", encoding="utf-8")
    workspace.snapshot(d.s, sub, "end")
    res = workspace.revert(d.s, sub)
    assert (project / "notes.txt").read_text(encoding="utf-8") == "the user is writing here\n"
    assert (project / "mine.txt").exists()
    assert res["restored"] == [] and res["removed"] == []
    assert {s["path"] for s in res["skipped"]} == {"notes.txt", "mine.txt"}
