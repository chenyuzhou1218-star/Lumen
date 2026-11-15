"""The window drawn in React (desktop/web_chat.py, web/src): the real window, offscreen, with a scripted model. The page is
read and clicked with JavaScript, as a user would; what it asks Python for goes over the real QWebChannel."""

from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("PySide6.QtWebEngineWidgets")

from conftest import unique_model  # noqa: E402


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
    return bool(until and until())


def js(app, win, code: str, wait: float = 5):
    """The value of a JavaScript expression in the page (JSON-able)."""
    box = {}
    win.web.view.page().runJavaScript(f"JSON.stringify((() => {{ return {code}; }})())", 0, lambda r: box.setdefault("r", r))
    pump(app, wait, until=lambda: "r" in box)
    return json.loads(box["r"]) if box.get("r") not in (None, "") else None


def click(app, win, selector: str) -> bool:
    return js(app, win, f"(() => {{ const el = document.querySelector({json.dumps(selector)}); if (!el) return false; el.click(); return true; }})()")


def type_into(app, win, selector: str, text: str) -> None:
    """Typing as React sees it: the native setter, then an input event."""
    js(app, win, f"""(() => {{ const el = document.querySelector({json.dumps(selector)});
        const set = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set;
        set.call(el, {json.dumps(text)}); el.dispatchEvent(new Event('input', {{ bubbles: true }})); return true; }})()""")


@pytest.fixture
def window(qapp, make_config, monkeypatch):
    from codedoctor.backend import Backend
    from codedoctor.desktop import app as app_mod
    from codedoctor.desktop import web_chat
    from codedoctor.models import scripted

    if not web_chat.available():
        pytest.skip("the page is not built (web/: npx vite build)")
    monkeypatch.setenv("LUMEN_WEB_CHAT", "1")
    model = unique_model("web")
    scripted.register(model, [{"text": "好的，**做完了**。\n\n```py\nprint('hi')\n```"}] * 6)
    cfg = make_config(agents=[{"id": "doctor", "role": "general", "endpoint": "fake", "model": model}])
    win = app_mod.MainWindow(cfg, Backend(cfg, poll_s=0.05))
    win.resize(1280, 820)
    win.show()
    assert pump(qapp, 20, until=lambda: js(qapp, win, "!!document.querySelector('.side .nav')", 1)), "the page did not draw"
    win.web.bridge.set_model("home", json.dumps({"endpoint": "fake", "model": model}))  # nothing is chosen for the user
    try:
        yield win
    finally:
        win.timer.stop()
        win.closeEvent = lambda e: e.accept()
        win.b.close()
        win.close()


def test_the_whole_window_is_the_page(qapp, window):
    win = window
    assert win.web is not None and not win.sidebar.isVisible()  # the Qt list is kept for its data, never shown
    assert not win.pages.isVisible() and not win.tool_view.isVisible()  # nothing Qt lies over the new chat
    texts = js(qapp, win, "[...document.querySelectorAll('.side .nav span')].map(e => e.textContent)")
    assert texts[:3] == ["新聊天", "搜索聊天", "插件"] and "设置" in texts
    assert js(qapp, win, "document.querySelector('.folder.here .folder-name span').textContent") == "shop-demo"
    assert js(qapp, win, "document.querySelector('.hello h1').textContent") == "今天想做点什么？"
    # every button inside the window, none cut off
    assert js(qapp, win, """[...document.querySelectorAll('button')].filter(b => b.offsetParent).every(b => {
        const r = b.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth + 0.5; })""")


def test_a_message_sent_from_the_page_becomes_a_chat_in_the_list(qapp, window):
    win = window
    type_into(qapp, win, ".composer textarea", "把首页改好看一点")
    assert click(qapp, win, ".composer .send")
    assert pump(qapp, 20, until=lambda: js(qapp, win, "(document.querySelector('.md') || {}).textContent || ''", 1).startswith("好的"))
    assert win.web.last["page"] == "chat"
    assert js(qapp, win, "document.querySelector('.bubble').textContent") == "把首页改好看一点"
    assert js(qapp, win, "!!document.querySelector('.code-bar .copy')")  # code blocks have their copy button
    assert pump(qapp, 5, until=lambda: js(qapp, win, "document.querySelectorAll('.folder.here .chat-row').length", 1) == 1)
    assert pump(qapp, 5, until=lambda: js(qapp, win, "(document.querySelector('.chat-row.on .chat-title span') || {}).textContent", 1)
                == "把首页改好看一点")  # the open chat is lit on the window's next refresh

    # rename, pin and put away from the list, as the old list did (chat_tools, pins.json)
    chat_id = win.task_view.chat_id
    win.web.bridge.rename(chat_id, "首页改版")
    assert pump(qapp, 3, until=lambda: js(qapp, win, "(document.querySelector('.chat-row.on .chat-title span') || {}).textContent", 1) == "首页改版")
    assert js(qapp, win, "document.querySelector('.chat-head h2').textContent") in ("首页改版", "把首页改好看一点")
    win.web.bridge.pin(chat_id)
    assert pump(qapp, 3, until=lambda: js(qapp, win, "[...document.querySelectorAll('.side-list h4')].map(h => h.textContent).includes('置顶')", 1))
    assert chat_id in win.sidebar.pins
    win.web.bridge.pin(chat_id)
    win.web.bridge.hide_chat(chat_id)
    assert pump(qapp, 3, until=lambda: js(qapp, win, "document.querySelectorAll('.chat-row').length", 1) == 0)
    win.bring_chats_back = lambda: None


def test_the_sidebar_buttons_open_the_browser_and_the_terminal_beside(qapp, window):
    """The browser opens on the right; the page gets narrower, so the sidebar folds to its narrow column, and the
    button there shows it is open."""
    win = window
    lit = "!!document.querySelector('.side-top .mini.on, .rail .rail-btn.on')"
    win.navigate("browser")  # Chromium's first start for the browser can take seconds
    assert pump(qapp, 15, until=lambda: js(qapp, win, lit, 1))
    assert win.dock.isVisible() and win.dock.current == "browser"
    if win.web.width() < 880:
        assert js(qapp, win, "!!document.querySelector('.rail')")
    win.navigate("browser")
    assert pump(qapp, 8, until=lambda: not js(qapp, win, lit, 1))
    assert pump(qapp, 3, until=lambda: js(qapp, win, "!!document.querySelector('.side')", 1))  # room again: the list is back


def test_the_sidebar_folds_to_a_narrow_column_and_back(qapp, window):
    win = window
    win.toggle_sidebar()  # Ctrl+B
    assert pump(qapp, 3, until=lambda: js(qapp, win, "!!document.querySelector('.rail')", 1))
    win.toggle_sidebar()
    assert pump(qapp, 3, until=lambda: js(qapp, win, "!!document.querySelector('.side')", 1))


def test_what_the_page_is_told(qapp, window):
    from codedoctor.desktop import web_chat

    win = window
    side = web_chat.side_json(win)
    assert side["folders"][0]["here"] and side["folders"][0]["name"] == "shop-demo"
    assert side["chats"] == [] and side["docks"] == [] and side["keys_missing"] == []
    boot = web_chat.boot_json(win)
    assert boot["lang"] == "zh" and boot["catalog"] == {}
    assert set(boot["prefs"]) >= {"send_key", "chat_width", "show_tokens", "accent_colours"}
    win.web.place("tool", (0, 0, 300, 200))  # an @ tool not asked for: its room alone does not show it
    assert not win.tool_view.isVisible()


def test_the_plugins_page_lists_the_tools_and_opens_one(qapp, window, monkeypatch):
    from codedoctor import makers

    opened = []
    monkeypatch.setattr(makers, "open_app", lambda tool, extra="": opened.append((tool, extra)) or True)  # no window in tests
    win = window
    win.plugins_page.load = lambda: setattr(win.plugins_page, "plugins", [])  # CodeTools is not started in tests
    assert click(qapp, win, ".side-nav .nav:nth-child(3)")  # 插件
    assert pump(qapp, 5, until=lambda: (js(qapp, win, "document.querySelectorAll('.pcard').length", 1) or 0) >= 10)
    assert win.web.last == {"page": "plugins"} and not win.pages.isVisible()
    type_into(qapp, win, ".searchbox input", "codecut")
    assert pump(qapp, 3, until=lambda: js(qapp, win, "document.querySelectorAll('.pcard').length", 1) == 1)
    assert click(qapp, win, ".pcard")
    assert pump(qapp, 3, until=lambda: opened == [("codecut", "")])


def test_the_terminal_is_a_real_powershell_drawn_in_the_page(qapp, window):
    """The user's words: a terminal has to show its words - PowerShell's own banner and prompt, a cursor, and what a
    command printed. It runs in a real console (conpty.py) and xterm.js draws it, white or black with the window."""
    from codedoctor.desktop import conpty

    if not conpty.available():
        pytest.skip("no pseudo console on this Windows")
    win = window
    screen = "(document.querySelector('.xterm-rows') || {}).textContent || ''"
    try:
        win.navigate("terminal")
        assert pump(qapp, 25, until=lambda: "PS " in (js(qapp, win, screen, 1) or "")), js(qapp, win, screen)
        assert "Windows PowerShell" in js(qapp, win, screen)
        assert js(qapp, win, "!!document.querySelector('.term.light .xterm-cursor-layer, .term.light .xterm-cursor, .term.light .xterm')")
        win.web.bridge.term_input("echo lumen-$((6*7))\r")
        assert pump(qapp, 15, until=lambda: "lumen-42" in (js(qapp, win, screen, 1) or ""))
        win.dock.ai_ran("spark", "npm test")  # what the team ran is listed above, not typed into the user's shell
        assert pump(qapp, 3, until=lambda: js(qapp, win, "(document.querySelector('.term-head .ran') || {}).textContent || ''", 1) == "sparknpm test1")
        win.apply_appearance({"mode": "dark"})  # the window's dark mode: the terminal turns black with every page
        assert pump(qapp, 3, until=lambda: js(qapp, win, "document.documentElement.dataset.mode === 'dark' && !!document.querySelector('.term.dark')", 1))
    finally:
        win.apply_appearance({"mode": "light"})
        win.dock.shutdown()


def test_the_thinking_slider_sets_the_level_and_the_row_stays_one_line(qapp, window):
    """思考 is a slider in the model menu: ← → move it a stop and the level really changes (the box's Composer). The row
    under the words never breaks into two lines, at any width (a real bug in the user's screenshot, 2026-11-11)."""
    win = window
    c = win.home.composer
    assert click(qapp, win, ".composer .pill.model")
    assert pump(qapp, 3, until=lambda: js(qapp, win, "!!document.querySelector('.pop.models .think-track')", 1))
    assert js(qapp, win, "getComputedStyle(document.querySelector('.pop.models')).position") == "absolute"
    keys = js(qapp, win, "[...document.querySelectorAll('.think-stops button')].map(b => b.textContent)")
    before = c.level
    js(qapp, win, """(() => { const s = document.querySelector('.think-track'); s.focus();
        s.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true})); return true; })()""")
    assert pump(qapp, 3, until=lambda: c.level != before), (before, keys)
    assert js(qapp, win, "document.querySelector('.think-head b').textContent") in keys
    rows = []
    for width in (1280, 900, 700):
        win.resize(width, 800)
        pump(qapp, 0.6)
        rows.append(js(qapp, win, """(() => { const r = document.querySelector('.composer .row'); const kids = [...r.children].filter(k => k.offsetParent);
            const mids = kids.map(k => Math.round(k.getBoundingClientRect().top + k.getBoundingClientRect().height / 2));
            return Math.max(...mids) - Math.min(...mids) <= 1 && r.getBoundingClientRect().height < 44; })()"""))
    assert all(rows), rows


def test_an_at_tool_gets_its_frame_from_the_page(qapp, window, monkeypatch):
    """@CodeCut above the chat: the page draws its name, the word while it starts and why it did not; the Qt widget is only
    the tool's own window, shown once it is in place. The user's rules (2026-11-13): no 允许 row - a tool works as the chat's
    批准方式 says - and the tool is a pane beside the chat."""
    from codedoctor.desktop import tool_view

    win = window
    tv = win.tool_view
    started = []
    monkeypatch.setattr(tv, "_start", lambda tool, root, key: started.append(key))  # no tool program in tests
    assert not tool_view.needs_permission("codecut", win.cfg)
    tv.show_tool("codecut", str(win.cfg.root), win.cfg)
    win.web.set_tool(True, "CodeCut")
    assert started and tv.frameless and not hasattr(tv, "ask")  # no Qt row of its own any more
    assert pump(qapp, 3, until=lambda: js(qapp, win, "(document.querySelector('.tool-bar b') || {}).textContent", 1) == "CodeCut")
    assert not tv.isVisible()  # starting: the page shows that, nothing native lies over it yet
    assert not js(qapp, win, "!!document.querySelector('.tool-ask')")  # nothing to allow
    tv._failed(tv.current, "这个工具没有打开（它的窗口没有出来）。")
    assert pump(qapp, 3, until=lambda: "没有打开" in (js(qapp, win, "(document.querySelector('.tool-wait.failed') || {}).textContent || ''", 1) or ""))
    # the tool is a pane beside the chat (2026-11-13: the narrow tool pane), not a band above it: both keep their room
    tool_w, chat_w = js(qapp, win, "(() => { const p = document.querySelector('.tool-pane'); "
                                   "return [p.getBoundingClientRect().width, p.previousElementSibling.getBoundingClientRect().width]; })()")
    assert tool_w >= 419 and chat_w >= 359
    win.web.set_tool(False)


def test_the_browser_frame_is_the_pages_and_the_pages_are_chromium(qapp, window, tmp_path):
    """Tabs, the address bar, the start page and Ray's panel are drawn by the page (light or dark with it); a web page is
    Chromium, lying in the room left for it. The Qt bars are never shown. Since 2026-11-13 the native view stays while the
    panel shows the browser (no flash between tabs): a new tab is its start page again."""
    win = window
    page = tmp_path / "hello.html"
    page.write_text("<title>Hello page</title><h1>hi</h1>", encoding="utf-8")
    win.navigate("browser")
    assert pump(qapp, 20, until=lambda: js(qapp, win, "!!document.querySelector('.b-start .b-search')", 1))
    b = win.browser
    assert b.frameless and not b.bar.isVisibleTo(b) and not b.strip.isVisibleTo(b)
    assert b.stack.currentWidget() is b.start  # a blank tab: the start page
    win.web.bridge.browser_go(page.as_uri())
    assert pump(qapp, 15, until=lambda: js(qapp, win, "(document.querySelector('.b-address input') || {}).value || ''", 1).endswith("hello.html"))
    assert pump(qapp, 5, until=lambda: b.isVisible())  # the page itself: Chromium over the room the frame left
    slot = js(qapp, win, "(() => { const r = document.querySelector('.browser-slot').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
    g = b.geometry()
    assert abs(g.x() - slot[0]) <= 2 and abs(g.y() - slot[1]) <= 2 and abs(g.width() - slot[2]) <= 2
    win.web.bridge.browser_act("new")
    assert pump(qapp, 5, until=lambda: js(qapp, win, "document.querySelectorAll('.b-tab').length", 1) == 2)
    assert pump(qapp, 3, until=lambda: b.stack.currentWidget() is b.start)  # the new tab is the start page again
    win.web.bridge.browser_close(1)
    assert pump(qapp, 5, until=lambda: js(qapp, win, "document.querySelectorAll('.b-tab').length", 1) == 0)  # one tab: no strip


def test_details_are_drawn_under_the_answer(qapp, window):
    """详细 opens under the answer, in the page: the status and time, every panel that has something, and the workspace
    overview's lists with a detail for a row; 记住 puts the answer into the project's long-term memory."""
    win = window
    win.web.bridge.send("home", "看看首页")
    assert pump(qapp, 20, until=lambda: js(qapp, win, "(document.querySelector('.md') || {}).textContent || ''", 1).startswith("好的"))
    tid = win.task_view.task_id
    win.open_details(tid)  # what 详细 and the ⋯ menu ask for
    ok = pump(qapp, 5, until=lambda: js(qapp, win, "!!document.querySelector('.details .d-head .tag')", 1))
    assert ok, (win.web.bridge.details_json(tid)[:600], js(qapp, win, "(document.querySelector('.details') || {}).outerHTML || 'none'"), win.web.last)
    assert not win.pages.isVisible()  # no Qt page any more
    d = json.loads(win.web.bridge.details_json(tid))
    assert d["status"] == "完成" and "token" in d["info"] and isinstance(d["sections"], list)
    rows = json.loads(win.web.bridge.ws_rows(tid, "timeline"))
    assert rows["rows"], rows
    detail = json.loads(win.web.bridge.ws_detail(tid, "timeline", 0))
    assert detail.get("text")
    for tab in ("changes", "files", "commands", "findings"):
        assert "rows" in json.loads(win.web.bridge.ws_rows(tid, tab))
    assert json.loads(win.web.bridge.remember(tid, "首页用白色"))["ok"]
    notes = [n for n in win.d.s.notes.search("首页用白色")] if hasattr(win.d.s.notes, "search") else None
    assert notes is None or notes



def test_the_model_chosen_is_kept_and_never_switched(qapp, make_config, monkeypatch):
    """A real bug (2026-11-12): Codex GPT-6-Luna chosen and sent, and the chat's box then showed Fable 5.1 - the
    project's own model - ready to send the next message with it. The box shows the model chosen, each chat the model its
    last turn ran with, a new start the model chosen last; with nothing chosen it shows none and sends nothing."""
    from codedoctor.backend import Backend
    from codedoctor.desktop import app as app_mod
    from codedoctor.desktop import prefs as ui_prefs
    from codedoctor.models import scripted

    monkeypatch.setenv("LUMEN_WEB_CHAT", "1")
    ui = ui_prefs.load()
    ui["last_pick"], ui["last_level"] = {}, ""
    ui_prefs.save(ui)
    cheap, dear = unique_model("cheap"), unique_model("dear")
    for m in (cheap, dear):
        scripted.register(m, [{"text": f"answered by {m}"}] * 6)
    cfg = make_config(agents=[{"id": "doctor", "role": "general", "endpoint": "fake", "model": dear}])  # the project's own: dear

    def window():
        win = app_mod.MainWindow(cfg, Backend(cfg, poll_s=0.05))
        win.resize(1280, 820)
        win.show()
        assert pump(qapp, 20, until=lambda: js(qapp, win, "!!document.querySelector('.side .nav')", 1))
        return win

    def close(win):
        win.timer.stop()
        win.closeEvent = lambda e: e.accept()
        win.b.close()
        win.close()

    def answered(win, text):
        return pump(qapp, 20, until=lambda: text in (js(qapp, win, "[...document.querySelectorAll('.md')].map(m => m.textContent).join('|')", 1) or ""))

    win = window()
    try:
        assert win.home.composer.model_choice is None  # nothing chosen yet: none shown, the project's own is not slipped in
        assert json.loads(win.web.bridge.send("home", "hi"))["ok"] is False  # and nothing goes until one is chosen
        win.web.bridge.set_model("home", json.dumps({"endpoint": "fake", "model": cheap}))
        win.web.bridge.send("home", "first chat")
        assert answered(win, f"answered by {cheap}")
        chat_a = win.task_view.task_id
        assert win.task_view.composer.model_choice == {"endpoint": "fake", "model": cheap}  # the chat goes on with it
        win.navigate("home")
        assert win.home.composer.model_choice == {"endpoint": "fake", "model": cheap}
        win.web.bridge.set_model("home", json.dumps({"endpoint": "fake", "model": dear}))
        win.web.bridge.send("home", "second chat")
        assert answered(win, f"answered by {dear}")
        chat_b = win.task_view.task_id
        win.open_task(chat_a)  # each chat: the model its last turn ran with
        assert win.task_view.composer.model_choice == {"endpoint": "fake", "model": cheap}
        win.open_task(chat_b)
        assert win.task_view.composer.model_choice == {"endpoint": "fake", "model": dear}
        win.open_task(chat_a)
        win.web.bridge.send("chat", "go on")  # a follow-up goes with the chat's model
        assert answered(win, f"answered by {cheap}")
        assert win.task_view.composer.model_choice == {"endpoint": "fake", "model": cheap}
    finally:
        close(win)
    win = window()  # a new start: the model chosen last
    try:
        assert win.home.composer.model_choice == {"endpoint": "fake", "model": dear}
    finally:
        close(win)
