"""Desktop window smoke test and the one-service-per-project lock."""

from __future__ import annotations

import gc
import time

import pytest

from codedoctor.agents.daemon import Daemon
from codedoctor.store.lock import AlreadyRunning

from conftest import unique_model

tk = pytest.importorskip("tkinter")


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as e:  # no display (e.g. headless CI)
        pytest.skip(f"no display: {e}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass
    # Tk objects must be freed on the thread that created them; left to the garbage collector,
    # they can be collected on another thread later and crash the Tcl interpreter.
    del root
    gc.collect()


def test_window_runs_a_task_and_shows_progress_and_report(make_config, tk_root):
    from codedoctor.gui import App, Backend

    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py", "start_line": 6, "end_line": 7}}]},
        {"text": "根因：server/shop.py 第 6-7 行在版本不一致时直接 return None。"},
    ]})
    backend = Backend(cfg)
    app = None
    try:
        app = App(tk_root, cfg, backend)
        app.instr.insert("1.0", "点击购买没有反应")
        app.submit()
        deadline = time.time() + 15
        while time.time() < deadline:
            tk_root.update()
            app.refresh_tasks()
            app.refresh_selected()
            if "根因" in app.report.get("1.0", "end"):
                break
            time.sleep(0.05)
        report = app.report.get("1.0", "end")
        assert "【完成】" in report and "根因" in report and "ev:code:" in report
        events = [app.timeline.item(i)["values"][1] for i in app.timeline.get_children()]
        assert "调用工具：读取文件" in events and "模型给出最终回答" in events
        [row] = app.tasks.get_children()
        assert app.tasks.item(row)["values"][2] == "完成"
        # selecting the tool result shows the original file excerpt
        result_row = next(i for i in app.timeline.get_children() if app.timeline.item(i)["values"][1] == "工具结果：成功")
        app.timeline.selection_set(result_row)
        tk_root.update()
        assert "inventory_version" in app.detail.get("1.0", "end")
    finally:
        backend.close()
        del app
        gc.collect()


async def test_only_one_service_per_project(make_config):
    model = unique_model()
    cfg = make_config({model: [{"text": "ok"}]})
    first = Daemon(cfg)
    await first.start()
    second = Daemon(cfg)
    try:
        with pytest.raises(AlreadyRunning):
            await second.start()
    finally:
        await first.stop()
        await second.s.aclose()
    third = Daemon(cfg)  # released on stop
    await third.start()
    await third.stop()


def test_recent_tasks_endpoint(make_config):
    from fastapi.testclient import TestClient

    from codedoctor.api import create_app

    model = unique_model()
    with TestClient(create_app(make_config({model: [{"text": "ok"}]}), poll_s=0.05)) as client:
        sub = client.post("/tasks", json={"agent": "doctor", "title": "第一个任务", "instructions": "go"}).json()
        for _ in range(100):
            rows = client.get("/tasks").json()
            if rows and rows[0]["state"] == "finished":
                break
            time.sleep(0.02)
        assert rows[0]["id"] == sub["task_id"] and rows[0]["title"] == "第一个任务" and rows[0]["outcome"] == "done"
