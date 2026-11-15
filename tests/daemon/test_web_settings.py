"""设置 in React (desktop/web_settings.py, web/src/Settings.jsx): every control changes the real setting. The project's
configuration is written on 保存 exactly as the Qt page wrote it; a key typed in the page waits for 保存 and goes only to
the credential store (here a stand-in: tests never touch Windows Credential Manager); the user's own preferences apply at once."""

from __future__ import annotations

import json

import pytest

from test_web_shell import click, js, pump, qapp  # noqa: F401  (fixtures and helpers of the real window)


@pytest.fixture
def keys(monkeypatch):
    """The credential store, in memory."""
    from codedoctor import secrets

    store: dict[str, str] = {}
    monkeypatch.setattr(secrets, "set_key", lambda eid, key: store.__setitem__(eid, key))
    monkeypatch.setattr(secrets, "delete_key", lambda eid: store.pop(eid, None))
    monkeypatch.setattr(secrets, "get_key", lambda ep: store.get(ep.id))
    monkeypatch.setattr(secrets, "key_status", lambda ep: ("keyring" if ep.id in store else "missing") if ep.api_key_keyring
                        else "not_needed")
    return store


@pytest.fixture
def window(qapp, tmp_path, monkeypatch, keys):  # noqa: F811
    from codedoctor import config as config_mod
    from codedoctor.backend import Backend
    from codedoctor.desktop import app as app_mod
    from codedoctor.desktop import web_chat
    from codedoctor.models import scripted

    if not web_chat.available():
        pytest.skip("the page is not built (web/: npx vite build)")
    monkeypatch.setenv("LUMEN_WEB_CHAT", "1")
    scripted.register("set-demo", [{"text": "ok"}] * 4)
    root = tmp_path / "site"
    root.mkdir()
    raw = {"cd_schema": "cd.config.project/0", "project": {"name": "site", "root": str(root), "data_dir": str(tmp_path / "data")},
           "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True},
                         {"id": "ollama", "name": "Ollama", "kind": "openai_compatible", "base_url": "http://localhost:11434/v1", "local": True,
                          "max_data_class": "local_only", "models": ["qwen3:8b"]}],
           "agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": "set-demo"}]}
    path = tmp_path / "codedoctor.toml"
    config_mod.save_raw(raw, path)
    cfg = config_mod.load(path)
    win = app_mod.MainWindow(cfg, Backend(cfg, poll_s=0.05))
    win.resize(1280, 820)
    win.show()
    assert pump(qapp, 20, until=lambda: js(qapp, win, "!!document.querySelector('.side .nav')", 1)), "the page did not draw"
    try:
        yield win
    finally:
        win.timer.stop()
        win.closeEvent = lambda e: e.accept()
        win.b.close()
        win.close()


def act(win, action, **data):
    return json.loads(win.web.bridge.settings_act(action, json.dumps(data)))


def test_settings_open_in_the_page_with_every_section(qapp, window):  # noqa: F811
    """The settings as the user redesigned them: the old sections are gone, and code and computer use have pages of
    their own in the list."""
    win = window
    assert click(qapp, win, ".side-foot .nav")
    assert pump(qapp, 5, until=lambda: js(qapp, win, "(document.querySelector('.settings .page-title') || {}).textContent", 1) == "服务与密钥")
    assert win.web.last["page"] == "settings" and not win.pages.isVisible()  # nothing Qt over it
    assert js(qapp, win, "[...document.querySelectorAll('.settings-nav .nav span')].map(s => s.textContent)") == \
        ["服务与密钥", "AI 模型", "长期记忆", "自动测试", "电脑操作", "外观", "用量", "功能手册"]
    assert js(qapp, win, "document.querySelectorAll('.card').length") == 2
    for i, title in ((3, "AI 模型"), (4, "长期记忆"), (5, "自动测试"), (6, "电脑操作"), (7, "外观"), (8, "用量")):
        assert click(qapp, win, f".settings-nav .nav:nth-child({i})")
        assert pump(qapp, 3, until=lambda t=title: js(qapp, win, "document.querySelector('.settings .page-title').textContent", 1) == t)
    win.navigate("knowledge")  # 结论与记忆 is drawn in React too: nothing Qt comes up over the page
    assert pump(qapp, 3, until=lambda: win.web.last.get("section") == "knowledge") and not win.pages.isVisible()


def test_a_service_and_its_key_wait_for_save(qapp, window, keys):  # noqa: F811
    """A typed key waits for 保存; the user's rule: long-term memory is one switch (how much is recalled is the system's
    choice), so there is no recall count or context size to set."""
    from codedoctor import config as config_mod

    win = window
    s = act(win, "endpoint", provider="deepseek", id="deepseek", name="DeepSeek", kind="openai_compatible", base_url="https://api.deepseek.com/v1/",
            local=False, key_mode="keyring", key="sk-test-123", data_class="internal", models="deepseek-chat\ndeepseek-chat")
    ep = next(e for e in s["endpoints"] if e["id"] == "deepseek")
    assert ep["pending"] == "typed" and ep["base_url"] == "https://api.deepseek.com/v1" and ep["models"] == ["deepseek-chat"]
    assert "sk-test-123" not in json.dumps(s) and "sk-test" not in win.web.bridge.settings_form("deepseek")  # never back to the page
    assert keys == {} and s["dirty"]  # nothing written before 保存
    bad = act(win, "endpoint", provider="custom", id="Bad Id", name="x", kind="openai_compatible", base_url="ftp://x", key_mode="none", data_class="internal")
    assert "error" in bad and "服务 ID" in bad["error"]
    assert "error" in act(win, "remove_endpoint", id="fake")  # in use: refused with who uses it
    s = act(win, "agent", id="doctor", field="endpoint", value="deepseek")
    assert next(a for a in s["agents"] if a["id"] == "doctor")["model"] == ""  # another service's model is not kept
    saved = json.loads(win.web.bridge.settings_save())
    assert not saved["ok"] and "没有选模型" in saved["error"]  # an agent without a model: nothing saved
    act(win, "agent", id="doctor", field="model", value="deepseek-chat")
    act(win, "agent", id="doctor", field="think", value="high")
    assert "error" in act(win, "agent", id="doctor", field="fallbacks", value="nowhere/model")
    act(win, "agent", id="doctor", field="fallbacks", value="ollama/qwen3:8b")
    act(win, "memory", recall=False)
    saved = json.loads(win.web.bridge.settings_save())
    assert saved["ok"], saved
    assert keys == {"deepseek": "sk-test-123"}  # only now, and only in the credential store
    raw = config_mod.load_raw(win.cfg.source)
    doctor = next(a for a in raw["agents"] if a["id"] == "doctor")
    assert doctor["endpoint"] == "deepseek" and doctor["model"] == "deepseek-chat" and doctor["params"]["reasoning"] == "high"
    assert doctor["fallbacks"] == [{"endpoint": "ollama", "model": "qwen3:8b"}] and doctor["memory"]["recall_k"] == 0
    assert "sk-test" not in (win.cfg.source.read_text(encoding="utf-8"))
    assert json.loads(win.web.bridge.settings())["dirty"] is False

    act(win, "drop_key", id="deepseek")  # 删除密钥, then 放弃修改: the key stays
    s = json.loads(win.web.bridge.settings_revert())
    assert not s["dirty"] and keys == {"deepseek": "sk-test-123"}


def test_a_test_of_a_service_answers_later(qapp, window):  # noqa: F811
    win = window
    got = []
    win.web.bridge.probed.connect(lambda text: got.append(json.loads(text)))
    win.web.bridge.settings_probe("endpoint", json.dumps({"id": "fake"}), "t1")
    assert pump(qapp, 5, until=lambda: got)
    assert got[0]["token"] == "t1" and got[0]["ok"] and "测试脚本" in got[0]["text"]


def test_appearance_applies_at_once(qapp, window):  # noqa: F811
    from codedoctor.desktop import prefs as ui_prefs

    win = window
    try:
        s = act(win, "appearance", key="mode", value="dark")
        assert s["appearance"]["values"]["mode"] == "dark" and ui_prefs.load()["mode"] == "dark"
        assert pump(qapp, 3, until=lambda: js(qapp, win, "document.documentElement.dataset.mode", 1) == "dark")
        act(win, "appearance", key="chat_width", value="wide")
        assert pump(qapp, 3, until=lambda: js(qapp, win, "document.querySelector('.app').classList.contains('cw-wide')", 1))
        assert "error" in act(win, "appearance", key="chat_width", value="huge")
        assert "error" in act(win, "appearance", key="no_such", value=1)
        assert not json.loads(win.web.bridge.settings())["dirty"]  # nothing to save: they are the user's own
    finally:
        act(win, "appearance", key="mode", value="light")
        act(win, "appearance", key="chat_width", value="normal")


def test_findings_memories_and_the_book_are_pages_of_settings(qapp, window):  # noqa: F811
    """结论与记忆 (from 长期记忆) and 功能手册 (F1) are drawn by the page too, nothing Qt over it."""
    win = window
    win.navigate("knowledge")
    assert pump(qapp, 5, until=lambda: js(qapp, win, "(document.querySelector('.settings .page-title') || {}).textContent", 1) == "结论与记忆")
    assert not win.pages.isVisible()
    k = json.loads(win.web.bridge.knowledge("notes", ""))
    assert set(k["stats"]) == {"supported", "proposed", "refuted", "notes"} and k["rows"] == []
    win.navigate("book")  # F1
    assert pump(qapp, 5, until=lambda: js(qapp, win, "(document.querySelector('.book .md h1') || {}).textContent || ''", 1) != "")
    assert json.loads(win.web.bridge.book("en"))["text"].lstrip().startswith("#")
