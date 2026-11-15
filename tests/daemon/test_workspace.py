"""Workspace overview (ADR 0013): snapshots and changes, and what the agents did, from permanent records."""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from codedoctor import workspace
from codedoctor.agents.daemon import Daemon
from codedoctor.services import Services

from conftest import unique_model

T = "task_01JB8Z2000000000000000TK01"


@pytest.fixture
def s(make_config):
    services = Services.open(make_config())
    yield services
    services.db.close()


def test_changes_since_the_start_and_line_diffs(s, project):
    (project / "logo.bin").write_bytes(b"\0\1\2" * 10)
    workspace.snapshot(s, T, "start")
    shop = project / "server" / "shop.py"
    shop.write_text(shop.read_text(encoding="utf-8").replace("return None", "raise StaleInventory()"), encoding="utf-8")
    (project / "server" / "new.py").write_text("print('hi')\n", encoding="utf-8")
    (project / "README.md").unlink()
    (project / "logo.bin").write_bytes(b"\0\1\2" * 11)
    ch = workspace.changes(s, T)
    assert ch["against"] == "now"
    assert ch["added"] == ["server/new.py"] and ch["deleted"] == ["README.md"]
    assert {m["path"]: m["text"] for m in ch["modified"]} == {"server/shop.py": True, "logo.bin": False}
    lines = workspace.diff(s, T, "server/shop.py").splitlines()
    assert any(ln.startswith("-") and "return None" in ln for ln in lines)
    assert any(ln.startswith("+") and "raise StaleInventory()" in ln for ln in lines)
    assert "+print('hi')" in workspace.diff(s, T, "server/new.py")
    assert "-Shop demo" in workspace.diff(s, T, "README.md")


def test_line_endings_do_not_make_every_line_a_change(s, project):
    shop = project / "server" / "shop.py"
    lf = shop.read_bytes().replace(b"\r\n", b"\n")
    shop.write_bytes(lf)
    workspace.snapshot(s, T, "start")
    shop.write_bytes(lf.replace(b"\n", b"\r\n").replace(b"return None", b"return 0"))
    d = workspace.diff(s, T, "server/shop.py")
    changed = [ln for ln in d.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    assert len(changed) == 2 and "return None" in changed[0] and "return 0" in changed[1]
    shop.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert "只有换行符" in workspace.diff(s, T, "server/shop.py")


def test_the_end_snapshot_freezes_what_the_task_changed(s, project):
    workspace.snapshot(s, T, "start")
    (project / "a.txt").write_text("during the task\n", encoding="utf-8")
    workspace.snapshot(s, T, "end")
    (project / "b.txt").write_text("after the task\n", encoding="utf-8")
    (project / "a.txt").write_text("edited later\n", encoding="utf-8")
    ch = workspace.changes(s, T)
    assert ch["against"] == "end" and ch["added"] == ["a.txt"]
    assert "+during the task" in workspace.diff(s, T, "a.txt")  # what it was when the task ended, not now


def test_start_snapshot_is_taken_once(s, project):
    first = workspace.snapshot(s, T, "start")
    (project / "x.txt").write_text("x", encoding="utf-8")
    assert workspace.snapshot(s, T, "start") == first


async def test_a_run_leaves_snapshots_timeline_files_and_commands(make_config, project):
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py", "start_line": 1, "end_line": 7}}]},
        {"tool_calls": [{"name": "run_command", "arguments": {"command": "python --version"}}]},
        {"text": "Root cause: early return."},
    ]}, permissions={"run_command": "allowlist", "command_allowlist": ["python --version"]})
    d = Daemon(cfg, poll_s=0.02)
    await d.start()
    try:
        sub = d.submit_task("doctor", "why", "Why does buy do nothing?")
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 15)
    finally:
        await d.halt()
    try:
        s = d.s
        tid = sub["task_id"]
        assert workspace.get(s, tid, "start") and workspace.get(s, tid, "end")
        tl = workspace.timeline(s, tid)
        assert [i["tool"] for i in tl if i["kind"] == "tool"] == ["read_file", "run_command"]
        assert all(i["ok"] for i in tl if i["kind"] == "tool")
        assert tl[-1]["kind"] == "answer" and "early return" in tl[-1]["text"]
        [f] = workspace.files_read(s, tid)
        assert f["path"] == "server/shop.py" and f["ranges"] == ["L1-L7"] and f["agents"] == ["doctor"]
        [c] = workspace.commands(s, tid)
        assert c["command"] == "python --version" and c["exit_code"] == "0" and "Python" in c["output"]
        assert workspace.changes(s, tid)["added"] == []
    finally:
        await d.s.aclose()


async def test_subtasks_take_no_snapshot(make_config):
    """Only the investigation (root task) is snapshotted; its subtasks share it."""
    from codedoctor.agents import orchestration as orch

    model = unique_model()
    cfg = make_config({model: [{"text": "ok"}]})
    d = Daemon(cfg, poll_s=0.02)
    await d.start()
    try:
        root = d.submit_task("doctor", "root", "go")
        await asyncio.wait_for(d.wait_for_report(root["task_id"]), 10)
        sub = orch.create_subtask(d.s, sender="doctor", recipient="doctor", title="child", instructions="go",
                                  parent_task_id=root["task_id"])
        for _ in range(200):
            if orch.task_row(d.s, sub["task_id"])["state"] == "finished":
                break
            await asyncio.sleep(0.02)
    finally:
        await d.halt()
    assert workspace.get(d.s, root["task_id"], "start") is not None
    assert workspace.get(d.s, sub["task_id"], "start") is None
    await d.s.aclose()


def test_panel_in_the_task_view(make_config, project):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from codedoctor.desktop.app import make_app
    from codedoctor.desktop.task_view import TaskView

    make_app()
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py"}}]},
        {"text": "done"},
    ]})
    d = Daemon(cfg, poll_s=0.02)

    async def go():
        await d.start()
        try:
            sub = d.submit_task("doctor", "why", "look")
            await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
            return sub["task_id"]
        finally:
            await d.halt()

    tid = asyncio.run(go())
    try:
        (project / "server" / "shop.py").write_text("changed after the task\n", encoding="utf-8")  # not counted: task ended
        view = TaskView(d, [("single", "单 Agent", "doctor")])
        view.resize(1400, 900)
        view.show()
        view.show_task(tid)
        assert view.ws_toggle.isVisible() and not view.workspace.isVisible()
        view.set_workspace_open(True)
        ws = view.workspace
        assert ws.isVisible() and not view.ws_toggle.isVisible()
        assert [ws.tabs.tabText(i) for i in range(ws.tabs.count())] == ["改动", "时间线", "读过的文件", "命令与操作", "结论与记忆"]
        assert "读取 server/shop.py" in ws.timeline.list.item(0).text()
        assert ws.files.list.item(0).text().startswith("server/shop.py")
        for _ in range(100):
            QApplication.processEvents()
            if ws._changes is not None:
                break
            time.sleep(0.02)
        assert "开始 → 结束" in ws.changes_note.text() and ws.changes.list.item(0).text() == "没有文件变化。"
        ws.timeline.list.setCurrentRow(0)
        assert "结果" in ws.timeline.detail.toPlainText() and "evidence: ev:code:" in ws.timeline.detail.toPlainText()
        view.set_workspace_open(False)
        assert view.ws_toggle.isVisible()
        view.close()
    finally:
        asyncio.run(d.s.aclose())
