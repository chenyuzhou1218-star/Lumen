"""The window as the user asked for it on 2026-11-05: what it must do, more than how it must look."""

from __future__ import annotations

import time

import pytest

from conftest import unique_model

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402


@pytest.fixture()
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def pump(app, seconds: float, until=None) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(.01)
    return False


def window(make_config):
    from codedoctor.backend import Backend
    from codedoctor.desktop import app as app_mod

    cfg = make_config(agents=[{"id": "doctor", "role": "general", "endpoint": "fake", "model": unique_model("w")}])
    return app_mod.MainWindow(cfg, Backend(cfg, poll_s=0.2))


def test_a_second_window_on_the_same_folder_just_opens(make_config):
    """A real complaint: opening Lumen twice ended on a card asking to choose a folder."""
    from codedoctor.desktop.launcher import another_window
    from codedoctor.store.lock import AlreadyRunning

    cfg = make_config()
    seen = []

    def factory(c):
        seen.append(c.data_dir)
        if len(seen) == 1:
            raise AlreadyRunning("busy")
        return "backend"

    opened, backend = another_window(cfg, factory)
    assert backend == "backend" and opened.data_dir == cfg.data_dir / "windows" / "1"


def test_lumen_opens_with_no_card_on_the_screen(make_config, qapp, monkeypatch):
    """The user's rule (2026-11-10): no 正在打开 card; nothing on the screen until the window is ready, and that moment
    does not end the program. A folder that does not open gets the one card: why, and 打开文件夹 - drawn by the page
    (web_onboarding.py) when it is built, as the whole start is now."""
    import threading

    from PySide6.QtWidgets import QMainWindow

    from codedoctor import config as config_mod
    from codedoctor.desktop import launcher as launcher_mod
    from codedoctor.desktop import projects

    cfg = make_config()
    monkeypatch.setattr(projects, "load_setup", lambda: {})
    monkeypatch.setattr(projects, "ensure_team", lambda path: None)
    monkeypatch.setattr(projects, "register", lambda *a: None)
    monkeypatch.setattr(config_mod, "load", lambda path: cfg)
    gate = threading.Event()

    def factory(c):
        gate.wait(10)
        return "backend"

    main, opened, shown = QMainWindow(), [], []
    lw = launcher_mod.Launcher(factory, "shop.toml")
    lw.show_me = lambda: shown.append(True)
    lw.opened.connect(lambda c, b, t: (opened.append(b), main.show()))
    try:
        pump(qapp, .3)
        assert not lw.isVisible() and not shown and not qapp.quitOnLastWindowClosed()
        gate.set()
        assert pump(qapp, 10, lambda: opened)
        assert opened == ["backend"] and not shown and not lw.isVisible() and qapp.quitOnLastWindowClosed()
        main.close()

        def broken(path):
            raise ValueError("no such file")
        monkeypatch.setattr(config_mod, "load", broken)
        lw.open_config("broken.toml")
        assert pump(qapp, 10, lambda: shown)
        if lw.web is not None:
            view = lw.web.bridge.last
            assert view["page"] == "failed" and "broken" in view["title"] and "no such file" in view["why"]
        else:
            assert "broken" in lw.opening.text.text() and "no such file" in lw.opening.why.text()
            assert not lw.opening.pick.isHidden()
        assert qapp.quitOnLastWindowClosed()
    finally:
        gate.set()
        qapp.setQuitOnLastWindowClosed(True)
        lw.close()


def test_claude_has_all_its_models_and_nothing_is_called_default():
    from codedoctor import claude_code
    from codedoctor.desktop import i18n

    listed = claude_code.models()
    names = [m["name"] for m in listed]
    for model in ("Fable 5.2", "Fable 5.1", "Opus 5.5", "Sonnet 5.5", "Haiku 5.5", "Fable 5", "Opus 5", "Sonnet 5", "Opus 4.8",
                  "Opus 4.7", "Opus 4.6", "Sonnet 4.6", "Haiku 4.5"):
        assert model in names
    assert not any("default" in m["id"].lower() or "default" in m["name"].lower() for m in listed)
    assert len({m["id"] for m in listed}) == len(listed) and all(m["id"].startswith("claude-") for m in listed)
    by = {m["name"]: m for m in listed}
    assert by["Opus 5.5"]["yours"] and sum(m["yours"] for m in listed) == 1  # what Claude Code runs by default
    assert by["Opus 4.6"]["efforts"] == ["low", "medium", "high", "max"] and by["Haiku 4.5"]["efforts"] == []
    assert by["Fable 5.2"]["efforts"] == ["low", "medium", "high", "xhigh", "max"]
    assert i18n.tr("choose_model")


def test_a_new_claude_model_shows_without_changing_lumen(claude_menu):
    """The user's rule (2026-11-10): Lumen lists what Claude Code lists now, never a list of its own."""
    from codedoctor import claude_code, engines

    claude_menu.insert(2, {"value": "claude-fable-9", "resolvedModel": "claude-fable-9", "displayName": "Fable 9",
                           "supportsEffort": True, "supportedEffortLevels": ["low", "max", "turbo"]})
    del claude_menu[-1]  # one that is gone from Claude Code goes from Lumen too
    claude_code.refresh()
    listed = claude_code.models()
    assert listed[0]["name"] == "Opus 5.5" and listed[1] == {"id": "claude-fable-9", "name": "Fable 9", "efforts": ["low", "max"],
                                                            "default_effort": None, "yours": False}
    assert "Sonnet 4.6" not in [m["name"] for m in listed]
    engines.check_choice("claude_code", "claude-fable-9", "max")
    with pytest.raises(ValueError):
        engines.check_choice("claude_code", "claude-sonnet-4-6", None)
    claude_code._menu = None  # another run of Lumen: the list kept on disk answers at once, before Claude Code does
    assert [m["id"] for m in claude_code.models()] == [m["id"] for m in listed]


def test_the_message_box_shows_only_what_the_user_chose(make_config, qapp):
    """The user's rule (2026-11-12): with nothing chosen the box shows no model and fills in none; what the user picks is
    what it shows and sends."""
    from codedoctor.desktop import prefs as ui_prefs

    ui = ui_prefs.load()
    ui["last_pick"], ui["last_level"] = {}, ""
    ui_prefs.save(ui)
    win = window(make_config)
    try:
        c = win.home.composer
        assert not c.model_btn.model_text and not c.model_choice
        assert "model" not in c.options() and "engine" not in c.options()  # nothing chosen: nothing filled in
        win.apply_pick(c, {"endpoint": "fake", "model": "picked-model"}, None)
        assert "picked-model" in c.model_btn.model_text
        assert c.options()["model"] == {"endpoint": "fake", "model": "picked-model"}
    finally:
        win.close()


def test_the_left_side_has_no_person_and_no_folder_chips(make_config, qapp):
    win = window(make_config)
    try:
        assert not hasattr(win.sidebar.rail, "avatar")
        assert not hasattr(win.home, "strip")
        win.sidebar.set_key_problems(["DeepSeek"])
        assert win.sidebar.rail.settings.alert
    finally:
        win.close()


def test_the_browser_searches_by_itself():
    """The user's rule (2026-11-13): Google by default, Bing when chosen."""
    from codedoctor.desktop.browser import typed_url

    assert typed_url("1+1等于几").startswith("https://www.google.com/search?q=")
    assert typed_url("1+1", "bing").startswith("https://www.bing.com/search?q=")
    assert typed_url("python.org") == "https://python.org"


def test_browser_and_terminal_open_beside_the_chat(make_config, qapp):
    win = window(make_config)
    try:
        win.show()
        page = win.pages.currentWidget()
        win.navigate("terminal")
        pump(qapp, .1)
        assert win.dock.isVisible() and win.dock.current == "terminal" and win.pages.currentWidget() is page
        win.navigate("terminal")
        assert not win.dock.isVisible()
    finally:
        win.close()


def test_links_open_in_the_browser_on_the_right(make_config, qapp, monkeypatch):
    from codedoctor.desktop import widgets

    win = window(make_config)
    try:
        opened = []
        monkeypatch.setattr(win, "open_link", opened.append)
        monkeypatch.setattr(widgets, "link_handler", win.open_link)
        widgets.open_link("https://example.com/a")
        assert opened == ["https://example.com/a"]
    finally:
        win.close()


def test_the_terminal_is_a_real_shell_that_remembers(tmp_path, qapp):
    from codedoctor.desktop.dock import Terminal

    (tmp_path / "sub").mkdir()
    t = Terminal(str(tmp_path))
    try:
        t.start()
        assert pump(qapp, 15, lambda: not t.busy), "the shell never came up"
        t.edit.setText("cd sub")
        t.run()
        assert pump(qapp, 10, lambda: not t.busy)
        t.edit.setText("Write-Output 'hello-你好'; (Get-Location).Path")
        t.run()
        assert pump(qapp, 10, lambda: not t.busy)
        text = t.out.toPlainText()
        assert "hello-你好" in text and text.rstrip().endswith("sub")
    finally:
        t.shutdown()


def test_cards_never_run_off_the_window(qapp):
    from codedoctor.desktop.widgets import CardGrid

    cards = [QLabel(str(i)) for i in range(4)]
    grid = CardGrid(cards, 400)
    grid.resize(600, 200)
    grid.show()
    pump(qapp, .05)
    assert grid.columns == 1
    grid.resize(900, 200)
    pump(qapp, .05)
    assert grid.columns == 2


def test_appearance_settings_change_the_sheet():
    """Large text is the page's own step (16 -> 18 px, x 1.125), so the Qt parts and the page grow alike."""
    from codedoctor.desktop import theme

    before = dict(theme.C)
    try:
        theme.configure({"accent": "violet", "font_size": "large", "corners": "full"})
        sheet = theme.qss()
        assert theme.ACCENTS["violet"][0] in sheet and "font-size: 32px" in sheet  # 28 px x 1.125
    finally:
        theme.configure({})
        theme.C.update(before)


def test_every_member_has_a_figure():
    from codedoctor.agents import team
    from codedoctor.desktop.team_ui import TEAM_ART

    for m in team.MEMBERS:
        assert (TEAM_ART / f"{m.id}.png").stat().st_size > 10000


@pytest.mark.parametrize("width", [860, 1040, 1400])
def test_nothing_runs_off_the_window_at_any_size(make_config, qapp, width):
    """The user's screenshots: 添加服务 cut in half, cards cut off. Every settings page, at every size."""
    from PySide6.QtWidgets import QWidget

    win = window(make_config)
    try:
        win.show()
        win.resize(width, 640)
        for page in ("services", "agent_models", "memory", "appearance"):
            win.navigate(page)
            pump(qapp, .25)
            scroll = win.models_page.scroll
            assert scroll.widget().width() <= scroll.viewport().width() + 1, page
            over = [w for w in win.findChildren(QWidget) if w.isVisible() and w.mapTo(win, w.rect().topRight()).x() > win.width() + 1]
            assert not over, (page, [type(w).__name__ for w in over][:5])
    finally:
        win.close()


def test_working_in_the_foreground_is_a_choice_that_stays(qapp):
    from codedoctor.desktop.settings_view import ComputerSettings

    raw = {"computer": {"screenshot": "on", "background": False}}
    panel = ComputerSettings(raw)
    assert panel.where.currentData() is False
    panel.shot.setCurrentIndex(0)
    panel.modes["input"][0].setCurrentIndex(2)
    assert raw["computer"]["background"] is False, "touching the panel does not lose it"
    panel.where.setCurrentIndex(0)
    assert "background" not in raw["computer"]


def test_a_picture_in_an_answer_fits_a_narrow_window(qapp, tmp_path):
    from PySide6.QtGui import QColor, QPixmap

    from codedoctor.desktop.task_view import PictureCard

    pix = QPixmap(1280, 720)
    pix.fill(QColor("#336699"))
    pix.save(str(tmp_path / "final.png"))
    card = PictureCard(tmp_path / "final.png")
    assert card.minimumSizeHint().width() < 200
    assert card.heightForWidth(320) == 180 and card.heightForWidth(2000) == 360, "as wide as the answer, and no wider"
    card.resize(320, 180)
    assert card.grab().toImage().pixelColor(160, 90).name() == "#336699"
    assert PictureCard(tmp_path / "missing.png").heightForWidth(320) == 0


def test_the_browser_is_ready_before_the_window_shows(make_config, qapp):
    """A real bug (2026-11-10): the first click on 浏览器 froze, the whole window vanished and came back (Qt remade it for
    the first web view), and the tab looked empty. The first page is made before the window is shown, and says what it is."""
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    win = window(make_config)
    try:
        win.prepare()
        assert len(win.browser.views) == 1 and not win.isVisible()
        win.show()
        win.navigate("browser")
        assert win.dock.isVisible() and win.browser.stack.currentWidget() is win.browser.start
        texts = [w.text() for w in win.browser.start.findChildren(QLabel)]
        assert "Lumen 浏览器" in texts and win.browser.start.edit.placeholderText()
    finally:
        win.browser.shutdown()
        win.close()
