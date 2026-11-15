"""Before any window, in React (desktop/web_onboarding.py, web/src/Onboarding.jsx): the greeting, the first-run setup and
the card of a folder that did not open, drawn by the window's own page in the launcher. The setup is checked and saved by
the same functions as the Qt card's (first_run.problem, first_run.build_setup)."""

from __future__ import annotations

import json

import pytest

from test_web_shell import js, pump, qapp  # noqa: F401


@pytest.fixture
def launcher(qapp, monkeypatch):  # noqa: F811
    from codedoctor.desktop import launcher as launcher_mod
    from codedoctor.desktop import projects, web_chat

    if not web_chat.available():
        pytest.skip("the page is not built (web/: npx vite build)")
    monkeypatch.setenv("LUMEN_WEB_CHAT", "1")
    saved = {}
    monkeypatch.setattr(projects, "load_setup", lambda: saved.get("setup"))
    monkeypatch.setattr(projects, "save_setup", lambda setup: saved.__setitem__("setup", setup))
    lw = launcher_mod.Launcher(lambda cfg: "backend")
    opened = []
    lw.open_default = lambda: opened.append(True)  # no folder is opened (nor made in the home folder) in tests
    lw.saved, lw.opened_default = saved, opened
    lw.resize(1100, 800)
    lw.show()
    try:
        yield lw
    finally:
        qapp.setQuitOnLastWindowClosed(True)
        lw.close()


def page(qapp, lw, code, wait=3):  # noqa: F811
    class W:  # js() reads win.web.view
        web = lw.web
    return js(qapp, W, code, wait)


def test_the_greeting_then_the_setup_then_the_folder_opens(qapp, launcher):  # noqa: F811
    """The greeting, the setup and the folder; the user's rule (2026-11-13, 2026-11-15): the setup offers seven languages."""
    from codedoctor.desktop import first_run

    lw = launcher
    assert lw.web is not None
    assert pump(qapp, 20, until=lambda: page(qapp, lw, "!!document.querySelector('.ob-card.welcome .greeting')", 1)), "no greeting"
    assert page(qapp, lw, "document.querySelector('.ob-tagline').textContent") == "顺着逻辑，找到真正要紧的问题。"
    assert page(qapp, lw, "(() => { document.querySelector('.ob-foot .btn.primary').click(); return true; })()")  # 进入 Lumen
    assert pump(qapp, 5, until=lambda: page(qapp, lw, "!!document.querySelector('.ob-card.setup .ob-langs')", 1))
    # the user's rule: English, French and Chinese (2026-11-13), then Spanish, German, Italian and Portuguese (2026-11-15)
    assert page(qapp, lw, "[...document.querySelectorAll('.ob-choice')].map(b => b.textContent)") == ["English", "Français", "Español", "Deutsch", "Italiano", "Português", "简体中文"]
    first_run._KNOWN.update({"claude_code": "missing", "codex": "missing"})  # no programs asked in tests
    bad = json.loads(lw.web.bridge.finish(json.dumps({"chosen": [], "fix": True})))
    assert not bad["ok"] and bad["error"]  # nothing chosen: said, nothing saved
    bad = json.loads(lw.web.bridge.finish(json.dumps({"chosen": ["codex"], "fix": True})))
    assert not bad["ok"] and "Codex" in bad["error"]
    assert "setup" not in lw.saved and not lw.opened_default
    ok = json.loads(lw.web.bridge.finish(json.dumps({"chosen": ["api"], "preset": "ollama", "url": "http://localhost:11434/v1",
                                                     "key": "", "model": "qwen3:8b", "fix": False})))
    assert ok["ok"] and lw.opened_default == [True]
    setup = lw.saved["setup"]
    assert setup["endpoints"][0]["id"] == "ollama" and setup["agents"][0]["model"] == "qwen3:8b"
    assert setup["permissions"]["write_files"] is False and "api_key_keyring" not in setup["endpoints"][0]


def test_a_folder_that_did_not_open_says_why(qapp, launcher):  # noqa: F811
    lw = launcher
    shown = []
    lw.show_me = lambda: shown.append(True)
    lw._failed("my-site", "PermissionError: denied")
    assert pump(qapp, 20, until=lambda: "denied" in (page(qapp, lw, "(document.querySelector('.ob-card.failed') || {}).textContent || ''", 1) or ""))
    assert shown
