"""Codex as an executor (codedoctor/codex.py): the user's Codex does the work, Code Doctor keeps the rest - the steps
on the task page, the tests afterwards, the rules on what may leave the machine. A stand-in `codex` (a small script
streaming the same events as `codex exec --json`) does the work here."""

from __future__ import annotations

import sys
import textwrap

import pytest

from codedoctor import codex
from codedoctor.agents.daemon import Daemon
from codedoctor.ui_text import describe_tool_call

FAKE = textwrap.dedent('''
    import json, sys, pathlib
    args = sys.argv[1:]
    prompt = sys.stdin.read()
    def emit(e): print(json.dumps(e), flush=True)
    emit({"type": "thread.started", "thread_id": "t"})
    emit({"type": "turn.started"})
    if "LOGIN" in prompt:
        emit({"type": "error", "message": "unexpected status 401 Unauthorized: please log in again"})
        emit({"type": "turn.failed", "error": {"message": "unexpected status 401 Unauthorized"}})
        sys.exit(1)
    if "SLOW" in prompt:  # starts a worker of its own (as node starts codex.exe) and keeps working
        import subprocess, time
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        pathlib.Path("grandchild.pid").write_text(str(child.pid))
        emit({"type": "item.started", "item": {"id": "i1", "type": "command_execution", "command": "rg total"}})
        time.sleep(120)
    if "CANT" in prompt:  # finishes its turn without doing the task, and says so
        emit({"type": "item.completed", "item": {"id": "i9", "type": "agent_message",
              "text": "I could not export: the video tools need approval.\\n\\n**STATUS: BLOCKED**"}})
        emit({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}})
        sys.exit(0)
    target = pathlib.Path("server/shop.py").resolve()
    cmd = '"C:\\\\Windows\\\\powershell.exe" -Command "Get-Content -LiteralPath \\'%s\\'"' % target
    emit({"type": "item.started", "item": {"id": "i1", "type": "command_execution", "command": cmd, "status": "in_progress"}})
    emit({"type": "item.completed", "item": {"id": "i1", "type": "command_execution", "command": cmd, "exit_code": 0,
          "status": "completed"}})
    if args[args.index("--sandbox") + 1] != "read-only":
        target.write_text(target.read_text() + "\\n# fixed by codex\\n")
        change = {"id": "i2", "type": "file_change", "changes": [{"path": str(target), "kind": "update"}]}
        emit({"type": "item.started", "item": {**change, "status": "in_progress"}})
        emit({"type": "item.completed", "item": {**change, "status": "completed"}})
    emit({"type": "item.completed", "item": {"id": "i3", "type": "agent_message", "text": "Fixed the total in server/shop.py."}})
    emit({"type": "turn.completed", "usage": {"input_tokens": 2000, "cached_input_tokens": 1500, "output_tokens": 300}})
''')


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    script = tmp_path / "fake_codex.py"
    script.write_text(FAKE, encoding="utf-8")
    calls = []
    real = codex.argv

    def argv(conf, exe, mcp=None, model=None, effort=None, **kw):
        out = real(conf, exe, mcp, model, effort, **kw)
        calls.append(out)
        return out
    monkeypatch.setattr(codex, "argv", argv)
    monkeypatch.setattr(codex, "executable", lambda: [sys.executable, str(script)])
    return calls


async def _run(cfg, instructions="The cart total is wrong"):
    import asyncio

    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", instructions[:60], instructions, engine="codex")
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 30)
        steps = [e["data"] for e in d.s.journal.read(task_id=sub["task_id"]) if e["type"] == "tool_call"]
        return d, sub, report, steps
    finally:
        await d.halt()


async def test_codex_does_the_work_and_code_doctor_shows_and_checks_it(make_config, project, fake_codex):
    """Codex does the work; the user's rule: no sandbox of Codex's, whatever an old run_command = deny says."""
    cfg = make_config(permissions={"run_command": "deny", "write_files": True,
                                   "test_command": f'"{sys.executable}" -c "print(\'1 passed in 0.01s\')"'})
    d, sub, report, steps = await _run(cfg)
    assert report["body"]["outcome"] == "done"
    assert report["body"]["summary"].startswith("Fixed the total") and "系统跑了测试" in report["body"]["summary"]
    assert "# fixed by codex" in (project / "server/shop.py").read_text(encoding="utf-8")
    shown = [describe_tool_call(s["tool"], s["arguments"]) for s in steps]
    assert shown == ["Codex · 读取 server/shop.py", "Codex · 修改 server/shop.py"], shown
    assert report["body"]["usage"]["input_tokens"] == 2000 and report["body"]["usage"]["output_tokens"] == 300
    args = fake_codex[0]
    assert args[args.index("--sandbox") + 1] == "danger-full-access" and args[-1] == "-"  # the prompt goes on stdin
    assert 'approval_policy="never"' in args and 'web_search="disabled"' in args


async def test_only_the_users_no_makes_its_sandbox_read_only(make_config, project, fake_codex):
    """The user's rule: no read-only members and no allowlist; Codex is read-only only when the user says no in 全部问我."""
    cfg = make_config(permissions={"run_command": "allowlist", "command_allowlist": ["python -m pytest"], "write_files": False})
    d, sub, report, steps = await _run(cfg)
    args = fake_codex[0]
    assert args[args.index("--sandbox") + 1] == "danger-full-access"
    assert "# fixed by codex" in (project / "server/shop.py").read_text(encoding="utf-8")
    p = codex.prompt(cfg, {"title": "t", "instructions": "i"})
    assert "python -m pytest" not in p and "Change no files" not in p and "Run no programs" not in p
    refused = codex.argv(cfg, ["codex"], read_only=True)
    assert refused[refused.index("--sandbox") + 1] == "read-only"
    assert "Change no files" in codex.prompt(cfg, {"title": "t", "instructions": "i"}, read_only=True)


async def test_local_only_code_never_goes_to_codex(make_config, project, fake_codex):
    cfg = make_config(code_data_class="local_only", permissions={"run_command": "deny", "write_files": True})
    d, sub, report, steps = await _run(cfg)
    assert report["body"]["outcome"] == "blocked" and "仅本机" in report["body"]["summary"]
    assert fake_codex == []  # never started


async def test_not_logged_in_says_how_to_fix_it(make_config, project, fake_codex):
    cfg = make_config(permissions={"run_command": "deny", "write_files": True})
    d, sub, report, steps = await _run(cfg, "LOGIN please")
    assert report["body"]["outcome"] == "blocked" and "登录" in report["body"]["summary"]


async def test_a_turn_that_ends_without_the_work_done_is_not_done(make_config, project, fake_codex):
    cfg = make_config(permissions={"run_command": "deny", "write_files": True,
                                   "test_command": f'"{sys.executable}" -c "print(\'1 passed in 0.01s\')"'})
    d, sub, report, steps = await _run(cfg, "CANT do this")
    body = report["body"]
    assert body["outcome"] == "blocked" and "没做完" in body["summary"] and "need approval" in body["summary"]
    assert "STATUS" not in body["summary"] and "系统跑了测试" not in body["summary"]
    assert "STATUS: DONE" in codex.prompt(cfg, {"title": "t", "instructions": "i"})


def _alive(pid: int) -> bool:
    import os
    import subprocess

    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


async def test_cancelling_stops_the_engine_and_what_it_started(make_config, project, fake_codex):
    import asyncio

    from codedoctor import interface

    d = Daemon(make_config(permissions={"run_command": "deny", "write_files": True}), poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", "slow", "SLOW work", engine="codex")
        pid_file = project / "grandchild.pid"
        for _ in range(300):
            if pid_file.is_file() and pid_file.read_text():
                break
            await asyncio.sleep(0.1)
        pid = int(pid_file.read_text())
        assert _alive(pid)
        interface.cancel(d, sub["task_id"])
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 30)
    finally:
        await d.halt()
    assert report["body"]["outcome"] == "cancelled"
    for _ in range(50):
        if not _alive(pid):
            break
        await asyncio.sleep(0.1)
    assert not _alive(pid)  # not left editing the project on its own


def test_the_engines_verdict():
    from codedoctor.engines import verdict

    assert verdict("Fixed it.\nSTATUS: DONE") == ("done", "Fixed it.")
    assert verdict("No status line") == ("done", "No status line")
    assert verdict("Tried twice.\n`STATUS: FAILED`")[0] == "failed"
    assert verdict("I will say STATUS: DONE when done.\nSTATUS: BLOCKED")[0] == "blocked"  # its own line, the last one


def test_called_in_toolsets_reach_codex_through_the_bridge(make_config, project):
    from codedoctor import mcp_bridge

    d = Daemon(make_config(permissions={"run_command": "deny", "write_files": True}))
    args = codex.argv(d.s.config, ["codex"], mcp_bridge.server(d.s, ["codecut"]))
    sets = [args[i + 1] for i, a in enumerate(args) if a == "-c"]
    assert any(s.startswith("mcp_servers.codedoctor.command=") for s in sets)
    assert any(s.startswith("mcp_servers.codedoctor.args=") and "codecut" in s for s in sets)
    assert 'mcp_servers.codedoctor.default_tools_approval_mode="approve"' in sets  # else Codex declines them
    p = codex.prompt(d.s.config, {"title": "cut", "instructions": "cut it", "toolsets": ["codecut"]})
    assert "video_edit" in p and "not with the shell" in p  # its tools are deferred: it is told their names


def test_a_long_powershell_line_is_shown_as_its_command(project):
    item = {"type": "command_execution", "command": '"C:\\\\pwsh.exe" -Command "rg -n total server"'}
    assert codex.steps(item, project) == [{"tool": "Bash", "command": "rg -n total server"}]
