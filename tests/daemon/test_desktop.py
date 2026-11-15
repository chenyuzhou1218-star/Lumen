"""Qt desktop app: a full cluster investigation driven through the real window (offscreen)."""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from codedoctor.models import scripted  # noqa: E402

from conftest import unique_model  # noqa: E402
from test_cluster import cluster_config, guardian_script, worker_script  # noqa: E402


@pytest.fixture
def qapp():
    from codedoctor.desktop.app import make_app

    return make_app()


def pump(app, seconds: float, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return False


def test_cluster_investigation_in_the_window(qapp, tmp_path):
    """The user's rules: the window is one React page (the chat is drawn there, not on the old Qt task page), and every
    worker is the hands, so the head gives it its files and the guardian states the claim."""
    from codedoctor.backend import Backend
    from codedoctor.desktop.app import MainWindow

    m = {k: unique_model(k) for k in ("dispatch", "logic", "worker", "guardian")}
    scripted.register(m["dispatch"], [
        {"tool_calls": [{"name": "consult", "arguments": {"question": "Which modules can pay a reward twice?"}}]},
        {"tool_calls": [{"name": "delegate", "arguments": {"agent": "worker-1", "title": "Check reconnect",
                                                           "instructions": "Read server/session.py",
                                                           "files": ["server/session.py"]}}]},
        {"tool_calls": [{"name": "wait_for", "arguments": {}}]},
        # the detail checklist is still open, so the head is sent back twice (ADR 0014) and keeps its answer
        *[{"text": "## 结论\n\nreconnect 会重放 settle，奖励会被**重复发放**。"}] * 3,
    ])
    scripted.register(m["logic"], [{"tool_calls": [{"name": "graph_risks", "arguments": {}}]}, {"text": "共同路径：reconnect → settle → add_gold"}])
    scripted.register(m["worker"], worker_script())
    scripted.register(m["guardian"], guardian_script())
    cfg = cluster_config(tmp_path, m)
    backend = Backend(cfg, poll_s=0.05)
    win = MainWindow(cfg, backend)
    try:
        win.show()
        assert win.pages.currentWidget() is win.home
        # a chat first (2026-11-03): with no general agent a worker answers alone; the cluster is kept, chosen here
        assert [k for k, _, _ in win.modes] == ["single", "cluster"]
        win.home.composer.set_mode("cluster")

        win.home.composer.set_text("断线重连后奖励发了两次")
        win.home.composer._send()
        from codedoctor.agents import orchestration as orch

        tid = win.task_view.task_id  # the conversation is the page's (web_chat.py); the Qt page keeps which task it is
        assert win.last_submit_ok and tid and win.web.last.get("page") == "chat"
        d = backend.daemon
        done = pump(qapp, 20, until=lambda: (orch.task_row(d.s, tid) or {}).get("state") == "finished")
        assert done and orch.task_row(d.s, tid)["outcome"] == "done", orch.task_row(d.s, tid)
        kids = orch.children(d.s, tid)
        assert [k["agent"] for k in kids] == ["head-logic", "worker-1", "guardian-1"]  # logic head, worker, guardian
        [claim] = d.s.claims.by_task(kids[2]["id"])  # the supervisor states what its worker found
        assert claim["author"]["id"] == "guardian-1"
        assert len(win.sidebar._chats) == 1  # one chat: the top-level task (its helpers are not chats)
    finally:
        win.timer.stop()
        win.closeEvent = lambda e: e.accept()
        backend.close()
        win.close()


def test_models_page_edits_and_saves(qapp, tmp_path, monkeypatch):
    from codedoctor import config as config_mod
    from codedoctor import secrets
    from codedoctor.desktop.settings_view import EndpointDialog, ModelsPage
    from test_providers import FakeKeyring

    kr = FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: kr)
    raw = {
        "cd_schema": "cd.config.project/0",
        "project": {"name": "p", "root": str(tmp_path), "data_dir": str(tmp_path / "data")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": "d"},
                   {"id": "worker-1", "role": "worker", "endpoint": "fake", "model": "w"},
                   {"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": "g", "supervises": "worker-1"}],
    }
    path = tmp_path / "cd.toml"
    config_mod.save_raw(raw, path)
    page = ModelsPage(config_mod.load(path))
    page.show_section("agents")  # settings are split into tabs; the agent rows live on "Agent 模型"
    assert len(page.rows) == 3 and not page.save_btn.isEnabled()

    # add a Kimi service with a key typed into the dialog: the key goes to the vault, not the file
    dlg = EndpointDialog(page, None, {"fake"})
    dlg.preset.setCurrentIndex(dlg.preset.findData("moonshot"))
    assert dlg.base_url.text() == "https://api.moonshot.cn/v1" and dlg.id.text() == "moonshot"
    assert dlg.key_keyring.isChecked()
    dlg.key.setText("sk-kimi-test")
    dlg.models.setPlainText("kimi-a\nkimi-b")
    dlg._accept()
    assert ("codedoctor", "moonshot") not in kr.store and dlg.typed_key == "sk-kimi-test"   # nothing written yet
    page.accept_endpoint(None, dlg.value(), dlg.typed_key)                                # waits for 保存

    page.add_pair()
    assert [r.a["id"] for r in page.rows][-2:] == ["worker-2", "guardian-2"]
    row = page.rows[-2]
    row.ep.setCurrentIndex(row.ep.findData("moonshot"))
    assert row.model.currentText() == "" and row.model.count() == 2       # old model name is not kept silently
    row.model.setCurrentText("kimi-b")
    row.fb.setText("fake/w")
    from codedoctor.desktop import settings_view
    warned = []
    monkeypatch.setattr(settings_view.QMessageBox, "exec", lambda self: 0)
    from codedoctor.desktop import dialogs
    monkeypatch.setattr(dialogs.Notice, "exec", lambda self: 0)
    monkeypatch.setattr(settings_view.QMessageBox, "warning", lambda *a: warned.append(a[2]))
    monkeypatch.setattr(settings_view.QMessageBox, "critical", lambda *a: warned.append(a[2]))
    assert page.save()
    assert kr.store[("codedoctor", "moonshot")] == "sk-kimi-test"                          # written with the config
    cfg = config_mod.load(path)
    w2 = cfg.agents["worker-2"]
    assert (w2.primary.endpoint, w2.primary.model) == ("moonshot", "kimi-b") and w2.fallbacks[0].model == "w"
    assert cfg.agents["guardian-2"].supervises == "worker-2"
    ep = cfg.endpoints["moonshot"]
    assert ep.api_key_keyring and secrets.key_status(ep) in ("keyring", "env") and "sk-kimi" not in path.read_text(encoding="utf-8")

    page.rows[-1].fb.setText("nope/x")
    assert not page.save() and "nope" in warned[-1]                      # bad fallback is refused, file unchanged
    assert config_mod.load(path).agents["guardian-2"].fallbacks == ()


def test_models_page_embedding_choice(qapp, tmp_path, monkeypatch):
    """ADR 0007: the user picks (or clears) the embedding model; the page never picks one."""
    from codedoctor import config as config_mod
    from codedoctor.desktop import settings_view
    from codedoctor.desktop.settings_view import ModelsPage

    raw = {
        "cd_schema": "cd.config.project/0",
        "project": {"name": "p", "root": str(tmp_path), "data_dir": str(tmp_path / "data")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True},
                      {"id": "ollama", "kind": "openai_compatible", "base_url": "http://127.0.0.1:11434/v1", "local": True,
                       "models": ["bge-m3", "qwen3:4b"]},
                      {"id": "claude", "kind": "anthropic", "base_url": "https://api.anthropic.com", "local": False}],
        "agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": "d"}],
    }
    path = tmp_path / "cd.toml"
    config_mod.save_raw(raw, path)
    page = ModelsPage(config_mod.load(path))
    page.show_section("memory")
    row = page.embedding
    assert [row.ep.itemData(i) for i in range(row.ep.count())] == [None, "ollama"]  # no Anthropic: it has no embeddings
    assert row.ep.currentData() is None and not row.model.isEnabled()

    warned = []
    monkeypatch.setattr(settings_view.QMessageBox, "exec", lambda self: 0)
    from codedoctor.desktop import dialogs
    monkeypatch.setattr(dialogs.Notice, "exec", lambda self: 0)
    monkeypatch.setattr(settings_view.QMessageBox, "warning", lambda *a: warned.append(a[2]))
    row.ep.setCurrentIndex(row.ep.findData("ollama"))
    assert row.model.currentText() == "" and row.model.count() == 2  # suggestions only; nothing pre-selected
    assert not page.save() and "嵌入模型名" in warned[-1]
    row.model.setCurrentText("bge-m3")
    assert page.save()
    assert config_mod.load(path).embedding == config_mod.EmbeddingConfig("ollama", "bge-m3")

    page = ModelsPage(config_mod.load(path))
    page.show_section("memory")
    assert page.embedding.ep.currentData() == "ollama" and page.embedding.model.currentText() == "bge-m3"
    page.embedding.ep.setCurrentIndex(0)
    assert page.save()
    assert config_mod.load(path).embedding is None and "memory" not in config_mod.load_raw(path)


def test_code_settings_write_permissions_and_detect_tests(qapp, tmp_path):
    """ADR 0016: the 改代码与测试 section writes raw['permissions'] that validates."""
    from codedoctor import config as config_mod
    from codedoctor.desktop.settings_view import ModelsPage

    (tmp_path / "tests").mkdir()
    raw = {"cd_schema": "cd.config.project/0",
           "project": {"name": "p", "root": str(tmp_path), "data_dir": str(tmp_path / "data")},
           "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
           "agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": "m"}]}
    path = tmp_path / "cd.toml"
    config_mod.save_raw(raw, path)
    page = ModelsPage(config_mod.load(path))
    page.show_section("code")
    assert not page.code.allow.isEnabled()  # commands are denied: the list is greyed out
    page.code.write.setChecked(True)
    page.code._detect()
    page.code.cmd.setCurrentIndex(page.code.cmd.findData("allowlist"))
    assert page.code.allow.isEnabled()
    perm = page.raw["permissions"]
    assert perm["write_files"] and "pytest" in perm["test_command"] and perm["run_command"] == "deny"  # empty list: deny
    page.code.allow.setPlainText("python -m pytest")
    assert page.raw["permissions"]["run_command"] == "allowlist" and page.dirty
    config_mod.parse(page.raw, base_dir=tmp_path)


def test_first_run_asks_once_then_any_folder_opens_with_it(qapp, tmp_path, monkeypatch):
    """2026-11-03: the language, then the AIs - once. Every folder then opens with that setup, its tests
    detected, the key in the credential store only; no project to create."""
    import json

    from codedoctor import config as config_mod, engines, secrets
    from codedoctor.desktop import first_run, projects

    monkeypatch.setenv("CODEDOCTOR_HOME", str(tmp_path / "home"))
    stored = {}
    monkeypatch.setattr(secrets, "set_key", lambda eid, key: stored.__setitem__(eid, key))
    monkeypatch.setattr(engines, "status", lambda name: {"claude_code": "missing", "codex": "ready"}[name])
    monkeypatch.setattr(engines, "models", lambda name: [{"id": "gpt-9-sol", "name": "GPT-9-Sol", "efforts": ["low"],
                                                          "default_effort": "low", "yours": True}] if name == "codex" else [])
    first_run._KNOWN.clear()
    assert projects.load_setup() is None
    w = first_run.FirstRun()
    pump(qapp, 3, until=lambda: len(w.status) == 2)
    assert w.use["codex"].isChecked() and not w.use["claude_code"].isEnabled()  # ready one ticked; missing one off
    assert w.preset.itemData(0) == "openai"
    w.use["claude_code"].setEnabled(True)
    w.use["claude_code"].setChecked(True)
    w._go(1)
    w._next()
    assert "Claude Code" in w.error.text()  # not installed: said, not saved
    w.use["claude_code"].setChecked(False)
    w.use["api"].setChecked(True)
    w.preset.setCurrentIndex(w.preset.findData("deepseek"))
    w.key.setText("sk-test-123")
    assert w.model.count() == 0 and not w.model.currentText()  # no model names written into Lumen (2026-11-10)
    done = []
    w.finished.connect(lambda: done.append(True))
    w._next()
    assert not done and w.error.text()  # a model must be picked
    from codedoctor.providers import ProbeResult

    w._tested(ProbeResult(reachable=True, models=["deepseek-v9", "deepseek-v9-think"]))  # 测试连接 with none typed
    assert [w.model.itemText(i) for i in range(w.model.count())] == ["deepseek-v9", "deepseek-v9-think"]
    assert "2" in w.test_result.text() and not w.model.currentText()
    w.model.setCurrentIndex(0)
    w._next()
    assert done, w.error.text()
    setup = projects.load_setup()
    assert [e["kind"] for e in setup["endpoints"]] == ["engine", "openai_compatible"]
    assert setup["agents"][0]["endpoint"] == "codex" and setup["agents"][0]["model"] == "gpt-9-sol"  # first chosen
    assert stored == {"deepseek": "sk-test-123"} and "sk-test" not in json.dumps(setup)

    code = tmp_path / "shop"
    (code / "tests").mkdir(parents=True)
    path = projects.for_folder(code)
    raw = config_mod.load_raw(path)
    assert raw["project"]["root"] == code.resolve().as_posix() and raw["permissions"]["write_files"]
    assert "pytest" in raw["permissions"]["test_command"]
    config_mod.parse(raw, base_dir=tmp_path)  # a Codex service is a valid configuration
    assert projects.for_folder(code) == path  # the same folder again: the same configuration
    assert projects.last_opened() == str(path.resolve())


def test_the_window_fits_a_small_screen_whatever_the_settings_page_needs(qapp, make_config, monkeypatch):
    """A real bug: the settings page (a long configuration path) needed 1350 px; every page of the window then did, it
    grew past the user's 1536 px screen and the stop button next to send was off the screen, impossible to click."""
    from codedoctor.agents import team
    from codedoctor.backend import Backend
    from codedoctor.desktop import app as app_mod

    raw = {"agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": unique_model("w")}]}
    team.add_to_raw(raw)
    cfg = make_config(agents=raw["agents"])
    win = app_mod.MainWindow(cfg, Backend(cfg, poll_s=0.2))
    try:
        win.models_page.state.setText("配置文件：" + "C:/Users/someone/AppData/Local/Temp/very/long/path/" * 6 + "x.toml")
        win.show()
        pump(qapp, 0.3)
        assert win.minimumSizeHint().width() < 1100, win.minimumSizeHint()
        win.navigate("agent_models")
        pump(qapp, 0.4)
        assert win.minimumSizeHint().width() < 1300, win.minimumSizeHint()
        win.navigate("home")
        pump(qapp, 0.3)
        area = win.screen().availableGeometry()
        win.resize(area.width() + 400, area.height() + 300)
        win.move(area.right() - 50, area.bottom() - 50)
        app_mod.fit_on_screen(win)
        pump(qapp, 0.2)
        frame = win.frameGeometry()
        assert frame.left() >= area.left() and frame.top() >= area.top(), (frame, area)
        assert frame.bottom() <= area.bottom() and (frame.right() <= area.right() or win.minimumWidth() > area.width()),             (frame, area)
    finally:
        win.timer.stop()
        win.closeEvent = lambda e: e.accept()
        win.b.close()
        win.close()


def test_settings_are_a_view_of_the_page_and_the_qt_lists_stay_hidden(qapp, make_config):
    """The user's rule: the old Qt settings pages and sidebar are gone from the screen; settings are a view of the React
    page (web_settings.py), opened where they were left, and home comes back with 帮我审查."""
    from codedoctor.backend import Backend
    from codedoctor.desktop import app as app_mod

    cfg = make_config(agents=[{"id": "doctor", "role": "general", "endpoint": "fake", "model": unique_model("s")}])
    win = app_mod.MainWindow(cfg, Backend(cfg, poll_s=0.2))
    try:
        assert "代码医生" not in win.windowTitle()
        win.show()
        pump(qapp, 0.2)
        assert win.web is not None and not win.sidebar.isVisible()
        win.navigate("settings")
        pump(qapp, 0.1)
        assert win.web.last["page"] == "settings" and not win.sidebar.isVisible()
        win.navigate("home")
        pump(qapp, 0.1)
        assert win.web.last["page"] == "home" and win.home.composer.approval == "auto"
    finally:
        win.close()
