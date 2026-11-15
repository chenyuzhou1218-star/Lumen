"""Desktop UI for business investigations and continuous foresight (ADR 0011), on ChatGPT's real sample case."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel  # noqa: E402

from codedoctor.agents.daemon import Daemon  # noqa: E402
from tools.business_cluster_cases import plan, prepare  # noqa: E402
from tools.business_cluster_demo import configuration  # noqa: E402

from test_business_cluster import run_both  # noqa: E402


@pytest.fixture
def qapp():
    from codedoctor.desktop.app import make_app

    return make_app()


@pytest.fixture
def engine(tmp_path):
    daemon = Daemon(configuration(tmp_path, "duplicate"))
    prepare(daemon.s)
    root = daemon.submit_task("dispatch", "business", "investigate")
    doc = daemon.s.investigations.open(root["task_id"], "logic", plan("cluster-shop"))
    yield daemon, doc
    daemon.s.db.close()


def texts(widget) -> str:
    return "\n".join(lb.text() for lb in widget.findChildren(QLabel))


def test_investigation_panel_shows_the_backend_gate(qapp, engine):
    from codedoctor.desktop.task_view import TaskView

    daemon, doc = engine
    view = TaskView(daemon, [("cluster", "多 Agent 集群", "dispatch")])
    view.show_task(doc["root_task_id"])
    panel = view.inv_panel
    assert panel.isVisibleTo(view)
    shown = texts(panel)
    assert "交付被阻止" in shown and "业务实验调查" in shown and doc["id"] in shown
    assert "不是普遍的因果证明" in shown and "没有声明运行时追踪覆盖" in shown
    assert "等待执行者和监督者都独立跑完" in shown or "还没有结果" in shown
    for h in doc["plan"]["hypotheses"]:
        assert h["id"] in shown and "尚未检验" in shown

    run_both(daemon, doc)  # worker and guardian each run the distinguishing check
    view._inv_at = 0
    view.refresh()
    shown = texts(view.inv_panel)
    assert "执行者与监督者独立复现一致" in shown and "已排除（在声明的实验范围内）" in shown
    assert "与观察相符（不等于已证明）" in shown
    status = daemon.s.investigations.status(doc["id"])
    assert f"原始实验记录 {len(status['evidence'])} 条" in shown and len(status["evidence"]) == 12
    assert not view.inv_panel.update_from(daemon.s.investigations.get(doc["id"]), status)  # unchanged: not rebuilt


def test_a_task_without_investigation_shows_no_panel(qapp, engine):
    from codedoctor.desktop.task_view import TaskView

    daemon, _ = engine
    other = daemon.submit_task("dispatch", "plain", "no business investigation here")
    view = TaskView(daemon, [("cluster", "多 Agent 集群", "dispatch")])
    view.show_task(other["task_id"])
    assert not view.inv_panel.isVisibleTo(view)


def test_a_chip_never_becomes_a_window_of_its_own(qapp):
    """The stray tiny window the user saw: risk-card chips were made visible before they had a parent."""
    from PySide6.QtWidgets import QApplication

    from codedoctor.desktop.widgets import Chip, hbox

    before = {id(w) for w in QApplication.topLevelWidgets() if w.isVisible()}
    chip = Chip("高")
    assert not chip.isVisible() and id(chip) not in {id(w) for w in QApplication.topLevelWidgets() if w.isVisible()} - before
    row = hbox(chip)
    row.show()
    assert chip.isVisible()  # the wish is applied once it has a parent
    chip.set("")
    assert not chip.isVisible()
    chip.set("中")
    assert chip.isVisible()
    row.close()


def test_computer_bar_approvals_and_stop_in_the_window(qapp, make_config):
    """ADR 0012: the user approves in the window (the only place approvals can come from) and can stop everything."""
    from PySide6.QtWidgets import QPushButton

    from codedoctor.computer.desktop import FakeDesktop, Window
    from codedoctor.desktop.computer_view import ApprovalCard, ComputerBar
    from codedoctor.services import Services

    fake = FakeDesktop(wins=[Window(1, "MyGame", 10, (100, 100, 900, 700))], fg=1)
    cfg = make_config(computer={"screenshot": "on", "input": "ask", "windows": ["MyGame"]})
    s = Services.open(cfg, desktop=fake)
    daemon = type("D", (), {"s": s, "config": cfg})()
    try:
        gate = s.computer
        shot = gate.screenshot(task_id="task_01JB8Z2000000000000000TK01", agent_id="doctor")
        rec = {"id": "act_01JB8Z2000000000000000AC09", "task_id": "task_01JB8Z2000000000000000TK01", "agent": "doctor",
               "kind": "click", "args": {"x": 10, "y": 20}, "screen_point": [110, 120], "intent": "open the shop",
               "status": "pending_user", "created_at": "2026-10-25T00:00:00.000Z", "mode": "ask",
               "user_reason": "this project asks you for every such action", "view": gate._marked(shot, (10, 20), "doctor")}
        gate._save(rec)
        bar = ComputerBar(daemon)
        # no always-on bar: it shows while something waits for the user (or after an emergency stop)
        assert bar.isVisibleTo(bar.parentWidget() or bar) and not bar.stop_btn.isVisibleTo(bar)
        [card] = bar.findChildren(ApprovalCard)
        shown = texts(card)
        assert "左键单击" in shown and "open the shop" in shown and "every such action" in shown
        [approve] = [b for b in card.findChildren(QPushButton) if b.text() == "批准"]
        approve.click()
        assert gate.get(rec["id"])["status"] == "approved" and bar.sig == []  # the card is gone once decided
        assert not bar.isVisibleTo(bar.parentWidget() or bar)  # nothing waits: the bar is gone
        gate.stop("Ctrl+Alt+End")  # the emergency stop (hotkey or the top-left corner)
        bar.refresh()
        assert bar.isVisibleTo(bar.parentWidget() or bar) and "已停止" in bar.status.text()
        assert bar.stop_btn.text() == "恢复电脑操作"
        bar.stop_btn.click()
        assert gate.stopped() is None and not bar.isVisibleTo(bar.parentWidget() or bar)
    finally:
        s.db.close()


def test_computer_permissions_are_saved_from_the_models_page(qapp, tmp_path, monkeypatch):
    from codedoctor import config as config_mod
    from codedoctor.desktop import settings_view
    from codedoctor.desktop.settings_view import ModelsPage

    raw = {"cd_schema": "cd.config.project/0",
           "project": {"name": "p", "root": str(tmp_path), "data_dir": str(tmp_path / "data")},
           "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
           "agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": "d"}]}
    path = tmp_path / "cd.toml"
    config_mod.save_raw(raw, path)
    monkeypatch.setattr(settings_view.QMessageBox, "exec", lambda self: 0)
    from codedoctor.desktop import dialogs
    monkeypatch.setattr(dialogs.Notice, "exec", lambda self: 0)
    page = ModelsPage(config_mod.load(path))
    page.show_section("computer")
    c = page.computer
    c.shot.setCurrentIndex(c.shot.findData("on"))
    c.modes["input"][0].setCurrentIndex(c.modes["input"][0].findData("guardian"))
    c.windows.setPlainText("MyGame")
    c.launch.setPlainText("game = D:/games/mygame.exe --windowed")
    assert page.save()
    p = config_mod.load(path).computer
    assert (p.screenshot, p.input, p.apps, p.windows) == ("on", "guardian", "off", ("MyGame",))
    assert p.launch[0].id == "game" and p.launch[0].args == ("--windowed",)
