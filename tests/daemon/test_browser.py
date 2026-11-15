"""The built-in browser (desktop/browser.py) and Ray's hands on it (agents/tools_browser.py). The rules are checked here
with a stand-in for the window's browser; opening real pages is checked in the window itself."""

from __future__ import annotations

import concurrent.futures
from types import SimpleNamespace

import pytest

from codedoctor.agents import team, tools_browser
from codedoctor.agents.tools import TOOLS
from codedoctor.desktop.browser import local_host, typed_url


class Stand:
    """The window's browser, for the tools: records what reached it."""

    def __init__(self, element):
        self.element, self.log = element, []

    def call(self, op, *args):
        self.log.append((op, *args))
        out = self.element if op == "describe" else {"title": "t", "url": "https://x.org/", "text": "hello", "elements": [
            {"ref": 1, "tag": "a", "type": "", "label": "Docs", "href": "https://x.org/docs"}]}
        done = concurrent.futures.Future()
        done.set_result(out)
        return done


def ctx(element=None, data_class="internal", browser=True):
    services = SimpleNamespace(browser=Stand(element) if browser else None)
    return SimpleNamespace(services=services, data_class=data_class, task_id="task_x", agent_id="ray")


@pytest.mark.parametrize("text,url", [("openai.com", "https://openai.com"), ("https://a.b/c", "https://a.b/c"),
                                      ("如何 砍树", "https://www.google.com/search?q=%E5%A6%82%E4%BD%95+%E7%A0%8D%E6%A0%91"),
                                      ("localhost:8000", "http://localhost:8000"), ("minecraft", "https://www.google.com/search?q=minecraft")])
def test_the_address_bar(text, url):
    """The user's rule (2026-11-13): the browser searches with Google unless they chose Bing in the settings."""
    assert typed_url(text) == url
    if "/search?q=" in url:
        assert typed_url(text, "bing") == url.replace("www.google.com", "www.bing.com")


@pytest.mark.parametrize("url,local", [("http://127.0.0.1:8765/api", True), ("http://localhost/", True), ("http://192.168.1.5/", True),
                                       ("http://printer.local/", True), ("https://example.com/", False), ("https://8.8.8.8/", False)])
def test_what_counts_as_this_computer(url, local):
    assert local_host(url) is local


async def test_ray_reads_and_clicks_a_page():
    c = ctx({"tag": "a", "type": "", "label": "Docs"})
    res = await tools_browser.browser_read(c, {})
    assert res.ok and res.external and "[1] a 'Docs' -> https://x.org/docs" in res.content  # page text is untrusted data
    assert (await tools_browser.browser_click(c, {"ref": 1})).ok
    assert ("click", 1) in c.services.browser.log


@pytest.mark.parametrize("label", ["登录", "立即支付", "提交订单", "Sign in", "Buy now", "删除账号", "发送", "同意并继续"])
async def test_what_is_the_users_to_click_is_refused(label):
    c = ctx({"tag": "button", "type": "button", "label": label})
    res = await tools_browser.browser_click(c, {"ref": 3})
    assert not res.ok and "user" in res.content and not any(x[0] == "click" for x in c.services.browser.log)


@pytest.mark.parametrize("element", [{"tag": "input", "type": "password"}, {"tag": "input", "type": "text", "name": "card_number"},
                                     {"tag": "input", "type": "text", "autocomplete": "cc-number"}, {"tag": "input", "type": "text", "placeholder": "短信验证码"},
                                     {"tag": "input", "type": "tel", "id": "cvv"}])
async def test_secrets_are_never_typed(element):
    c = ctx(element)
    res = await tools_browser.browser_type(c, {"ref": 2, "text": "hunter2"})
    assert not res.ok and not any(x[0] == "type" for x in c.services.browser.log)


async def test_an_ordinary_search_box_takes_text():
    c = ctx({"tag": "input", "type": "search", "name": "q", "placeholder": "搜索"})
    assert (await tools_browser.browser_type(c, {"ref": 2, "text": "wood", "submit": True})).ok
    assert ("type", 2, "wood", True) in c.services.browser.log


async def test_the_browser_keeps_this_computer_and_secret_data_out(monkeypatch):
    monkeypatch.setattr(tools_browser, "_user_named", lambda c, url: None)
    res = await tools_browser.browser_open(ctx(), {"url": "http://127.0.0.1:8765/api"})
    assert not res.ok
    res = await tools_browser.browser_open(ctx(data_class="local_only"), {"url": "https://example.com/"})
    assert not res.ok and "local_only" in res.content
    res = await tools_browser.browser_read(ctx(browser=False), {})
    assert not res.ok and "window" in res.content


def test_ray_has_the_browser_and_the_recheck_only_looks():
    ray = team.BY_ID["ray"]
    assert all(n in ray.tools and n in TOOLS for n in team.BROWSER)


def test_a_project_that_has_the_team_gets_new_tools():
    raw = {"agents": [{"id": "doctor", "role": "general", "endpoint": "e", "model": "m"}]}
    team.add_to_raw(raw)
    ray = next(a for a in raw["agents"] if a["id"] == "ray")
    ray["tools"] = ["web_search"]
    assert team.add_to_raw(raw) and "browser_open" in ray["tools"]
    assert not team.add_to_raw(raw)


async def test_an_address_on_this_computer_opens_when_the_user_wrote_it(monkeypatch):
    """The user's own game or site under test; a page or a model naming such an address opens nothing."""
    monkeypatch.setattr(tools_browser, "_user_named", lambda c, url: "localhost:5173")
    c = ctx()
    res = await tools_browser.browser_open(c, {"url": "http://localhost:5173/"})
    assert res.ok and ("allow", "localhost:5173") in c.services.browser.log and ("open", "http://localhost:5173/") in c.services.browser.log


async def test_the_user_named_address_comes_from_the_users_words(make_config):
    from codedoctor.agents.daemon import Daemon

    d = Daemon(make_config({"m": [{"wait_s": 2, "text": "done"}]}), poll_s=0.05)
    sub = d.submit_task("doctor", "t", "试一下 http://localhost:5173/ 这个游戏")
    c = SimpleNamespace(services=d.s, task_id=sub["task_id"])
    assert tools_browser._user_named(c, "http://localhost:5173/x") == "localhost:5173"
    assert tools_browser._user_named(c, "http://127.0.0.1:8765/api") is None
    await d.s.aclose()


class Mouse(Stand):
    """The window's browser with a page to look at."""

    def call(self, op, *args):
        self.log.append((op, *args))
        out = {"look": {"png": b"png", "width": 800, "height": 600, "url": "http://x/", "title": "Game"},
               "point": self.element, "active": self.element, "mouse": {"ok": True}, "keys": {"ok": True}}[op]
        done = concurrent.futures.Future()
        done.set_result(out)
        return done


def page_ctx(element):
    forgotten = []
    evidence = SimpleNamespace(add_blob=lambda *a, **k: "ev:png", forget=forgotten.append)
    services = SimpleNamespace(browser=Mouse(element), evidence=evidence)
    return SimpleNamespace(services=services, data_class="internal", task_id="task_x", agent_id="ray")


async def test_ray_uses_a_real_mouse_and_keys_in_a_game_and_sees_the_result(monkeypatch):
    from codedoctor.agents import orchestration as orch

    monkeypatch.setattr(orch, "root_of", lambda s, t: "root")
    c = page_ctx({"tag": "canvas", "label": ""})
    res = await tools_browser.browser_mouse(c, {"action": "drag", "x": 100, "y": 100, "to_x": 300, "to_y": 200, "seconds": 1})
    assert res.ok and res.images == ["ev:png"] and any(x[0] == "mouse" and x[1] == "drag" for x in c.services.browser.log)
    res = await tools_browser.browser_keys(c, {"keys": ["w"], "seconds": 1.5})
    assert res.ok and ("keys", ["w"], "", 1.5) in c.services.browser.log
    assert c.services._web_shots["root"] == ["ev:png", "ev:png"]  # pictures go when the task ends


@pytest.mark.parametrize("label", ["立即支付", "Sign in", "发送"])
async def test_the_mouse_does_not_get_round_the_rules(label):
    c = page_ctx({"tag": "button", "label": label})
    res = await tools_browser.browser_mouse(c, {"action": "click", "x": 10, "y": 10})
    assert not res.ok and "user" in res.content and not any(x[0] == "mouse" for x in c.services.browser.log)


async def test_a_plain_button_is_not_taken_for_a_submit():
    """A real run: <button> is type "submit" in the page, and the rule on sending refused "开始游戏"."""
    c = ctx({"tag": "button", "type": "submit", "name": "", "id": "start", "label": "开始游戏"})
    assert (await tools_browser.browser_click(c, {"ref": 1})).ok
    c = ctx({"tag": "button", "type": "submit", "name": "submit-order", "id": "", "label": ""})
    assert not (await tools_browser.browser_click(c, {"ref": 1})).ok


def test_a_recheck_can_try_the_page_too():
    assert "browser_mouse" not in team.NO_CHECK_TOOLS and "browser_keys" not in team.NO_CHECK_TOOLS


async def test_keys_do_not_get_round_the_rules():
    c = page_ctx({"tag": "input", "type": "password"})
    res = await tools_browser.browser_keys(c, {"text": "hunter2"})
    assert not res.ok and not any(x[0] == "keys" for x in c.services.browser.log)


def test_a_question_or_an_address_from_the_start_page(qapp_browser=None):
    from codedoctor.desktop.app import make_app
    from codedoctor.desktop.browser import StartPage, looks_like_address

    make_app()
    page = StartPage()
    went = []
    page.go.connect(went.append)
    page.edit.setText("Minecraft 怎么砍树")
    page._enter()
    page.edit.setText("python.org/downloads")
    page._enter()
    assert went == ["Minecraft 怎么砍树", "python.org/downloads"] and page.edit.text() == ""  # both right here, no agent
    assert looks_like_address("http://localhost:5173") and not looks_like_address("3.5 is what")
