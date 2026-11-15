"""Claude Code as an executor (codedoctor/claude_code.py): the user's Claude Code does the work, Code Doctor keeps the
rest - the steps on the task page, the tests afterwards, the snapshot, the rules on what may leave the machine.
A stand-in `claude` (a small script streaming the same events) does the work here."""

from __future__ import annotations

import asyncio
import sys
import textwrap
from types import SimpleNamespace

import pytest

from codedoctor import claude_code
from codedoctor.agents.daemon import Daemon
from codedoctor.ui_text import describe_tool_call

FAKE = textwrap.dedent('''
    import json, sys, pathlib
    args = sys.argv[1:]
    prompt = sys.stdin.read()
    def emit(e): print(json.dumps(e), flush=True)
    emit({"type": "system", "subtype": "init", "model": "stand-in"})
    if "LOGIN" in prompt:
        emit({"type": "result", "subtype": "success", "is_error": True, "result": "Failed to authenticate: OAuth session expired",
              "num_turns": 1, "usage": {}})
        sys.exit(1)
    if "HANG" in prompt:
        import time
        time.sleep(60)
    if "GIVEUP" in prompt:
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 2, "usage": {},
              "result": "The bug is in a vendored binary I cannot change.\\nSTATUS: FAILED"})
        sys.exit(0)
    target = pathlib.Path("server/shop.py")
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": "Looking at shop.py"},
          {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": str(target.resolve())}}]}})
    emit({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "..."}]}})
    if "--allowedTools" in args and "Edit" in args[args.index("--allowedTools") + 1]:
        text = target.read_text()
        target.write_text(text + "\\n# fixed by claude\\n")
        emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t2", "name": "Edit",
              "input": {"file_path": str(target.resolve()), "old_string": "a", "new_string": "b\\nc"}}]}})
        emit({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": "ok"}]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "result": "Fixed the total in server/shop.py.",
          "num_turns": 3, "total_cost_usd": 0.01, "usage": {"input_tokens": 1200, "output_tokens": 300,
          "cache_read_input_tokens": 800}})
''')


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE, encoding="utf-8")
    calls = []
    real = claude_code.argv

    def argv(conf, exe, mcp_config=None, model=None, effort=None):
        out = real(conf, exe, mcp_config, model, effort)
        calls.append(out)
        return [sys.executable, str(script), *out[1:]]
    monkeypatch.setattr(claude_code, "argv", argv)
    monkeypatch.setattr(claude_code, "executable", lambda: "claude")
    return calls


async def _run(cfg, instructions="The cart total is wrong"):
    import asyncio

    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", instructions[:60], instructions, engine="claude_code")
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 30)
        steps = [e["data"] for e in d.s.journal.read(task_id=sub["task_id"]) if e["type"] == "tool_call"]
        return d, sub, report, steps
    finally:
        await d.halt()


async def test_claude_code_does_the_work_and_code_doctor_shows_and_checks_it(make_config, project, fake_claude):
    """Claude Code does the work; the user's rule: any command, so it always has Bash."""
    cfg = make_config(permissions={"run_command": "deny", "write_files": True,
                                   "test_command": f'"{sys.executable}" -c "print(\'1 passed in 0.01s\')"'})
    d, sub, report, steps = await _run(cfg)
    assert report["body"]["outcome"] == "done"
    assert report["body"]["summary"].startswith("Fixed the total") and "系统跑了测试" in report["body"]["summary"]
    assert "# fixed by claude" in (project / "server/shop.py").read_text(encoding="utf-8")
    shown = [describe_tool_call(s["tool"], s["arguments"]) for s in steps]
    assert shown == ["Claude Code · 读取 server/shop.py", "Claude Code · 修改 server/shop.py  （-1 +2 行）"], shown
    assert report["body"]["usage"]["input_tokens"] == 2000 and report["body"]["usage"]["output_tokens"] == 300
    args = fake_claude[0]
    allowed = args[args.index("--allowedTools") + 1]
    assert "Edit" in allowed and "Bash" in allowed  # the user's rule: any command, whatever an old run_command = deny says
    assert "WebFetch" in args[args.index("--disallowedTools") + 1]


async def test_an_old_read_only_switch_no_longer_stops_it(make_config, project, fake_claude):
    """The user's rule: no read-only members and no command allowlist; an old write_files = false still lets Claude Code
    change files and run any command."""
    cfg = make_config(permissions={"run_command": "allowlist", "command_allowlist": ["python -m pytest"], "write_files": False})
    d, sub, report, steps = await _run(cfg)
    args = fake_claude[0]
    allowed = args[args.index("--allowedTools") + 1].split(",")
    assert "Edit" in allowed and "Bash" in allowed and not [t for t in allowed if t.startswith("Bash(")]
    assert "# fixed by claude" in (project / "server/shop.py").read_text(encoding="utf-8")
    assert args[args.index("--permission-mode") + 1] == "acceptEdits"


async def test_local_only_code_never_goes_to_claude_code(make_config, project, fake_claude):
    cfg = make_config(code_data_class="local_only", permissions={"run_command": "deny", "write_files": True})
    d, sub, report, steps = await _run(cfg)
    assert report["body"]["outcome"] == "blocked" and "仅本机" in report["body"]["summary"]
    assert fake_claude == []  # never started


async def test_not_logged_in_says_how_to_fix_it(make_config, project, fake_claude):
    cfg = make_config(permissions={"run_command": "deny", "write_files": True})
    d, sub, report, steps = await _run(cfg, "LOGIN please")
    assert report["body"]["outcome"] == "blocked" and "登录" in report["body"]["summary"]


async def test_its_own_word_that_it_failed_is_kept(make_config, project, fake_claude):
    cfg = make_config(permissions={"run_command": "deny", "write_files": True})
    d, sub, report, steps = await _run(cfg, "GIVEUP please")
    assert report["body"]["outcome"] == "failed" and "vendored binary" in report["body"]["summary"]
    args = fake_claude[0]
    assert "STATUS: DONE" in args[args.index("--append-system-prompt") + 1]


def test_an_unknown_engine_is_refused(make_config):
    d = Daemon(make_config())
    with pytest.raises(KeyError):
        d.submit_task("doctor", "x", "y", engine="gpt-who")


def test_claude_code_gets_code_doctors_video_tools_through_mcp(project):
    """@CodeCut with Claude Code: Code Doctor's tools reach it as an MCP server over stdio (codedoctor/mcp_bridge.py).
    The user's rule: no sandbox, so paths outside the project work as well."""
    import json
    import subprocess

    from codedoctor import video

    if video.home() is None:
        pytest.skip("CodeCut is not installed")
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "video_edit", "arguments": {"action": "init", "project": "cut.json"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "video_edit", "arguments": {"action": "init", "project": "../outside.json"}}}]
    out = subprocess.run([sys.executable, "-m", "codedoctor.mcp_bridge", "--root", str(project), "--toolsets", "codecut"],
                         input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, encoding="utf-8",
                         timeout=120, cwd=str(project))
    answers = {a["id"]: a for a in map(json.loads, out.stdout.strip().splitlines())}
    assert answers[1]["result"]["serverInfo"]["name"] == "codedoctor"
    assert {t["name"] for t in answers[2]["result"]["tools"]} == set(video.NAMES)
    assert answers[3]["result"]["isError"] is False and (project / "cut.json").is_file()
    # the user's rule: no sandbox, so a cut may be saved outside the project too
    assert answers[4]["result"]["isError"] is False and (project.parent / "outside.json").is_file()


def test_the_bridge_is_offered_to_claude_code_for_called_in_toolsets(make_config, project):
    from codedoctor import mcp_bridge
    from codedoctor.agents.daemon import Daemon

    d = Daemon(make_config(permissions={"run_command": "deny", "write_files": True}))
    path = mcp_bridge.config_file(d.s, "task_x", ["codecut"])
    args = claude_code.argv(d.s.config, "claude", path)
    assert args[args.index("--mcp-config") + 1] == path and "--strict-mcp-config" in args
    assert "mcp__codedoctor__video_edit" in args[args.index("--allowedTools") + 1]


async def test_an_ai_that_shows_nothing_at_all_is_closed(make_config, project, fake_claude, monkeypatch):
    """The user's rule: 20 minutes without even thinking, and it is closed; the run itself may last 24 hours."""
    from codedoctor import engines

    assert engines.SILENT_S == 20 * 60 and engines.TIMEOUT_S == 24 * 3600
    monkeypatch.setattr(engines, "SILENT_S", 1.5)
    d = Daemon(make_config(), poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", "t", "HANG please", engine="claude_code")
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 30)
    finally:
        await d.halt()
    assert report["body"]["outcome"] == "failed" and "没有任何动静" in report["body"]["summary"]


async def test_waiting_for_a_member_is_not_silence(make_config, monkeypatch):
    from codedoctor import engines

    d = Daemon(make_config(), poll_s=0.05)
    root = orch_task(d)
    rt = SimpleNamespace(s=d.s)
    assert engines._waiting_on_others(rt, root) is False
    from codedoctor.agents import orchestration as orch

    orch.create_subtask(d.s, sender="doctor", recipient="doctor", title="x", instructions="y", parent_task_id=root)
    assert engines._waiting_on_others(rt, root) is True
    await d.s.aclose()


def orch_task(d):
    from codedoctor.agents import orchestration as orch

    return orch.create_subtask(d.s, sender="user", recipient="doctor", title="t", instructions="go", parent_task_id=None)["task_id"]


async def test_a_cached_read_is_told_apart_from_new_tokens(make_config, project, fake_claude):
    """A long engine run reads its history back every turn: 17 million tokens once cost 1.31 dollars."""
    from codedoctor.agents import orchestration as orch

    d, sub, report, _ = await _run(make_config(permissions={"run_command": "deny", "write_files": True}))
    assert report["body"]["usage"]["cached_tokens"] == 800
    assert orch.tree_tokens(d.s, sub["task_id"]) == 2300 and orch.tree_cached(d.s, sub["task_id"]) == 800


async def test_a_report_that_cannot_be_sent_still_ends_the_task(make_config, project, fake_claude, monkeypatch):
    """A field the schema did not know once left a chat spinning for ever."""
    from codedoctor.agents.runtime import AgentRuntime

    real, tries = AgentRuntime._finish, []

    def picky(self, msg, body, outcome, summary, found):
        tries.append(outcome)
        if len(tries) == 1:
            raise ValueError("not a valid report")
        return real(self, msg, body, outcome, summary, found)

    monkeypatch.setattr(AgentRuntime, "_finish", picky)
    _, _, report, _ = await _run(make_config(permissions={"run_command": "deny", "write_files": True}))
    assert report["body"]["outcome"] == "failed" and "not a valid report" in report["body"]["summary"]
