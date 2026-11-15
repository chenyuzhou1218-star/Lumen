"""Computer use (ADR 0012) on an in-memory desktop: nothing here moves the real mouse or presses a real key."""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from codedoctor import config as config_mod
from codedoctor.agents import orchestration as orch
from codedoctor.agents.daemon import Daemon
from codedoctor.agents.runtime import AgentRuntime
from codedoctor.agents.tools import tools_for
from codedoctor.computer.desktop import FakeDesktop, Window
from codedoctor.models import scripted
from codedoctor.models.base import ChatMessage
from codedoctor.models.openai_compat import OpenAICompatClient
from codedoctor.services import Services

from conftest import unique_model

GAME = Window(1, "MyGame - level 1", 10, (100, 100, 900, 700))
NOTEPAD = Window(2, "Notes.txt - Notepad", 20, (0, 0, 1920, 1080))
ON = {"screenshot": "on", "input": "guardian", "apps": "guardian", "terminal": "guardian", "windows": ["MyGame"], "background": False,
      "launch": [{"id": "game", "path": "D:/games/mygame.exe", "args": ["--windowed"]}]}
ACT = re.compile(r"act_[0-9A-Z]{26}")


def desktop(**kw) -> FakeDesktop:
    return FakeDesktop(wins=[GAME, NOTEPAD], fg=GAME.handle, **kw)


def pair(worker_turns, guardian_turns, *, computer=None, guardian=True, worker_role="worker"):
    """(raw agents, models) for a worker and its guardian on the scripted endpoint."""
    w, g = unique_model("w"), unique_model("g")
    scripted.register(w, worker_turns)
    scripted.register(g, guardian_turns)
    agents = [{"id": "worker-1", "role": worker_role, "endpoint": "fake", "model": w}]
    if guardian:
        agents.append({"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": g, "supervises": "worker-1"})
    return agents, w, g


SHOOT = {"tool_calls": [{"name": "screenshot", "arguments": {}}]}


def click(x=50, y=50, **kw):
    return {"tool_calls": [{"name": "mouse_click", "arguments": {"x": x, "y": y, "intent": "open the shop menu", **kw}}]}


def decide(verdict):
    return lambda msgs: {"tool_calls": [{"name": "decide_action", "arguments": {
        "action_id": ACT.findall(msgs[1].content)[0], "verdict": verdict, "reason": f"{verdict}: checked the marked point"}}]}


async def run(cfg, fake, agent="worker-1", during=None, timeout=15, approval=None):
    d = Daemon(cfg, poll_s=0.02, desktop=fake)
    await d.start()
    try:
        sub = d.submit_task(agent, "reproduce", "Open the shop in the game and check the price",
                            **({"approval": approval} if approval else {}))
        waiter = asyncio.create_task(d.wait_for_report(sub["task_id"]))
        if during:
            await during(d)
        report = await asyncio.wait_for(waiter, timeout)
    finally:
        await d.halt()
    return d, sub, report


def calls(d, model):
    return [c for c in d.s.models.client("fake").calls if c["model"] == model]


# --- the approval flow ------------------------------------------------------------------------------

async def test_guardian_approves_before_the_click_happens(make_config):
    """The user's rule: 帮我审查 also asks the user about mouse and keyboard; in 完全放开 only the guardian decides."""
    agents, w, g = pair([SHOOT, click(), {"text": "clicked the shop"}], [decide("approve"), {"text": "approved"}])
    fake = desktop()
    d, sub, report = await run(make_config(agents=agents, computer=ON), fake, approval="full")
    assert report["body"]["outcome"] == "done"
    assert ("click", 150, 150, "left", 1) in fake.log  # (50, 50) in the window screenshot = (150, 150) on screen
    [act] = d.s.computer.actions(task_ids=[sub["task_id"]])
    assert act["status"] == "executed" and [e["what"] for e in act["events"]][:2] == ["asked_guardian", "guardian_approve"]
    approval = calls(d, g)[0]["messages"][1]
    assert act["id"] in approval.content and approval.images  # the guardian saw the marked screenshot
    after = calls(d, w)[2]["messages"]
    assert any(m.images and "Screenshot(s) from the tool calls" in m.content for m in after)  # result shown to the worker
    assert "done: left-click" in [m for m in after if m.role == "tool"][-1].content
    assert not d.s.notes.by_task(act["guardian_task"])  # approving a click leaves no long-term memory
    await d.s.aclose()


async def test_guardian_denial_means_nothing_happens(make_config):
    agents, w, g = pair([SHOOT, click(), {"text": "could not"}], [decide("deny"), {"text": "denied"}])
    fake = desktop()
    d, sub, _ = await run(make_config(agents=agents, computer=ON), fake)
    assert not [e for e in fake.log if e[0] == "click"]
    tool = [m for m in calls(d, w)[2]["messages"] if m.role == "tool"][-1].content
    assert tool.startswith("NOT done - DENIED") and "Do not try to get around this" in tool
    await d.s.aclose()


async def test_irreversible_needs_the_user_after_the_guardian(make_config):
    agents, w, g = pair([SHOOT, click(irreversible=True), {"text": "done"}], [decide("approve"), {"text": "ok"}])
    fake = desktop()

    async def user_approves(d):
        for _ in range(300):
            pending = d.s.computer.actions(statuses=("pending_user",))
            if pending:
                assert "agent declares it irreversible" in pending[0]["user_reason"]
                d.s.computer.user_decides(pending[0]["id"], True, "fine")
                return
            await asyncio.sleep(0.02)
        raise AssertionError("the user was never asked")

    d, sub, _ = await run(make_config(agents=agents, computer=ON), fake, during=user_approves)
    [act] = d.s.computer.actions(task_ids=[sub["task_id"]])
    assert act["status"] == "executed" and ("click", 150, 150, "left", 1) in fake.log
    assert [e["what"] for e in act["events"]][:4] == ["asked_guardian", "guardian_approve", "asked_user", "user_approved"]
    assert any(m["kind"] == "escalation" and act["id"] in m["body"]["detail"] for m in d.s.bus.list(task_id=sub["task_id"]))
    await d.s.aclose()


async def test_user_denies_and_nothing_happens(make_config):
    agents, w, g = pair([SHOOT, click(), {"text": "done"}], [decide("needs_user"), {"text": "user decides"}])
    fake = desktop()

    async def user_denies(d):
        for _ in range(300):
            pending = d.s.computer.actions(statuses=("pending_user",))
            if pending:
                d.s.computer.user_decides(pending[0]["id"], False, "no")
                return
            await asyncio.sleep(0.02)

    d, sub, _ = await run(make_config(agents=agents, computer=ON), fake, during=user_denies)
    assert not [e for e in fake.log if e[0] == "click"]
    assert d.s.computer.actions(task_ids=[sub["task_id"]])[0]["status"] == "denied"
    await d.s.aclose()


async def test_without_a_guardian_the_user_decides(make_config):
    agents, w, _ = pair([SHOOT, click(), {"text": "done"}], [], guardian=False, worker_role="general")
    fake = desktop()

    async def user_approves(d):
        for _ in range(300):
            pending = d.s.computer.actions(statuses=("pending_user",))
            if pending:
                d.s.computer.user_decides(pending[0]["id"], True)
                return
            await asyncio.sleep(0.02)

    d, sub, _ = await run(make_config(agents=agents, computer=ON), fake, during=user_approves)
    [act] = d.s.computer.actions(task_ids=[sub["task_id"]])
    assert act["status"] == "executed" and act["events"][0]["what"] == "no_guardian"
    await d.s.aclose()


async def test_worker_review_lists_its_computer_actions(make_config):
    """The user's rule: 帮我审查 asks the user about a click too; in 完全放开 the guardian's approval is enough."""
    agents, w, g = pair([SHOOT, click(), {"text": "clicked"}], [decide("approve"), {"text": "ok"}, {"text": "reviewed"}])
    d, sub, _ = await run(make_config(agents=agents, computer=ON), desktop(), approval="full")
    rows = d.s.db.query("SELECT body FROM tasks WHERE body LIKE '%\"review_of\"%'")  # created before the report is posted
    assert rows and "Computer actions the worker performed" in rows[0]["body"]
    await d.s.aclose()


# --- hard checks, by the program ---------------------------------------------------------------------

@pytest.fixture
def gate(make_config):
    fake = desktop()
    cfg = make_config(computer=ON)
    s = Services.open(cfg, desktop=fake)
    yield s.computer, fake, s
    s.db.close()


def ctx(task="task_01JB8Z2000000000000000TK01"):
    return SimpleNamespace(task_id=task, agent_id="worker-1")


def refused(gate, kind, args, **kw) -> str:
    rec = asyncio.run(gate.request(ctx(), kind, args, intent="test", **kw))
    assert rec["status"] == "refused", rec
    return rec["events"][-1]["note"]


def test_clicks_need_a_screenshot_and_an_allowed_window(gate):
    g, fake, _ = gate
    assert "take a screenshot first" in refused(g, "click", {"x": 1, "y": 1})
    g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    assert "not inside an allowed window" in refused(g, "click", {"x": 900, "y": 10})  # = (1000, 110), outside the game
    assert not [e for e in fake.log if e[0] == "click"]


def approved(g, kind, args, **extra) -> dict:
    """An action the guardian approved, run as the gate runs it (checked again first)."""
    rec = {"id": f"act_01JB8Z2000000000000000{kind[:2].upper()}{len(extra):02d}", "task_id": ctx().task_id,
           "agent": "worker-1", "kind": kind, "args": args, "intent": "t", "status": "approved",
           "created_at": "2026-10-31T00:00:00.000Z", "mode": "guardian", **extra}
    g._save(rec)
    return asyncio.run(g._execute(rec["id"], ctx()))


def test_a_covered_allowed_window_comes_to_the_front_before_the_click(gate):
    """Real Notepad test: a browser covered Notepad and every click was refused."""
    g, fake, _ = gate
    g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    fake.wins.insert(0, Window(3, "Browser", 30, (0, 0, 1920, 1080)))
    out = approved(g, "click", {"x": 50, "y": 50}, screen_point=[150, 150])
    assert out["status"] == "executed"
    assert [e[0] for e in fake.log][-2:] == ["focus", "click"] and fake.log[-2][1] == GAME.handle
    fake.wins.insert(0, Window(4, "Browser 2", 31, (0, 0, 1920, 1080)))
    fake.focus_works = False  # Windows would not change the foreground: refused, nothing clicked behind it
    out = approved(g, "click", {"x": 60, "y": 60}, screen_point=[160, 160], extra=1)
    assert out["status"] == "refused" and "could not be brought to the front" in out["events"][-1]["note"]
    assert len([e for e in fake.log if e[0] == "click"]) == 1


def test_typing_goes_to_the_screenshots_allowed_window_brought_to_the_front(gate):
    g, fake, _ = gate
    g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    fake.fg = NOTEPAD.handle  # not allowed (its title is not in computer.windows)
    out = approved(g, "type", {"text": "hello"})
    assert out["status"] == "executed" and fake.fg == GAME.handle and ("type", "hello") in fake.log


def test_a_covered_window_is_captured_on_its_own_or_not_at_all(gate):
    """Real Notepad test: the 'window' screenshot grabbed the screen, and the browser above Notepad reached the model."""
    g, fake, s = gate
    fake.wins.insert(0, Window(3, "Browser", 30, (0, 0, 1920, 1080)))
    shot = g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(s.evidence.content(shot["evidence"])))
    assert img.getcolors() == [(img.width * img.height, (0x44, 0xaa, 0x77))]  # only the game's own picture
    fake.own_picture = False
    with pytest.raises(PermissionError, match="covered"):
        g.screenshot(task_id=ctx().task_id, agent_id="worker-1")


def test_keyboard_only_into_the_allowed_window_and_no_system_shortcuts(gate):
    g, fake, _ = gate
    fake.wins.remove(GAME)  # no allowed window open: nowhere the keyboard may go
    fake.fg = NOTEPAD.handle
    assert "not allowed" in refused(g, "type", {"text": "hello"})
    fake.wins.insert(0, GAME)
    fake.fg = GAME.handle
    assert "outside the allowed window" in refused(g, "keys", {"keys": ["alt", "tab"]})
    assert "Windows key is never allowed" in refused(g, "keys", {"keys": ["win", "r"]})
    assert not [e for e in fake.log if e[0] in ("type", "press")]


def test_any_program_starts_and_only_our_own_are_closed(gate):
    """The user's rule (2026-11-14): no list of programs - any program starts by its path or a name Windows knows."""
    g, fake, _ = gate
    assert "no program" in refused(g, "launch", {"app": "no-such-program-lumen-xyz"})
    found = g._program({"app": sys.executable, "args": ["-V"]})
    assert found is not None and found.path == sys.executable and found.args == ("-V",)
    assert g._program({"app": "game"}).path == "D:/games/mygame.exe"  # a short name the configuration gave still works
    assert "only programs it launched" in refused(g, "close", {"pid": 4242})
    assert "chaining" in refused(g, "terminal", {"command": "dir & del /q *"})


def test_switched_off_capabilities_and_stop_refuse(make_config):
    s = Services.open(make_config(computer={"screenshot": "on", "windows": ["MyGame"]}), desktop=desktop())
    try:
        assert "switched off" in refused(s.computer, "terminal", {"command": "dir"})
    finally:
        s.db.close()


def test_stop_denies_pending_actions_and_refuses_new_ones(gate):
    g, fake, s = gate
    rec = {"id": "act_01JB8Z2000000000000000AC01", "task_id": ctx().task_id, "agent": "worker-1", "kind": "type",
           "args": {"text": "x"}, "intent": "t", "status": "pending_user", "created_at": "2026-10-25T00:00:00.000Z"}
    g._save(rec)
    g.stop("test")
    assert g.get(rec["id"])["status"] == "denied"
    assert "stopped" in refused(g, "type", {"text": "x"})
    g.resume()
    assert g.stopped() is None


def test_mouse_in_the_corner_stops_everything(gate):
    g, fake, _ = gate
    g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    rec = {"id": "act_01JB8Z2000000000000000AC02", "task_id": ctx().task_id, "agent": "worker-1", "kind": "click",
           "args": {"x": 50, "y": 50}, "screen_point": [150, 150], "intent": "t", "status": "approved",
           "created_at": "2026-10-25T00:00:00.000Z", "mode": "guardian"}
    g._save(rec)
    fake.pos = (0, 0)  # the user pushed the mouse into the top-left corner
    out = asyncio.run(g._execute(rec["id"], ctx()))
    assert out["status"] == "refused" and "top-left corner" in g.stopped()
    assert not [e for e in fake.log if e[0] == "click"]


def test_rules_mark_irreversible_actions(gate):
    g, _, _ = gate
    assert g._irreversible({"kind": "keys", "args": {"keys": ["alt", "F4"]}})
    assert g._irreversible({"kind": "keys", "args": {"keys": ["shift", "delete"]}})
    assert g._irreversible({"kind": "close", "args": {"pid": 1, "force": True}})
    assert g._irreversible({"kind": "terminal", "args": {"command": "git push origin main"}})
    assert g._irreversible({"kind": "terminal", "args": {"command": "Remove-Item build -Recurse"}})
    assert not g._irreversible({"kind": "terminal", "args": {"command": "python -m pytest"}})
    assert not g._irreversible({"kind": "keys", "args": {"keys": ["ctrl", "s"]}})


def test_screenshots_show_only_allowed_windows_and_never_list_others(gate):
    g, fake, s = gate
    shot = g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    assert shot["origin"] == [100, 100] and shot["size"] == [800, 600] and shot["window"] == GAME.title
    from codedoctor.computer.tools import list_windows

    out = list_windows(SimpleNamespace(services=s), {}).content
    assert "MyGame" in out and "Notepad" not in out and "1 other windows exist" in out


# --- tools offered, heads, configuration --------------------------------------------------------------

def test_tools_follow_the_switches_and_heads_never_act(make_config):
    """The user's rule (2026-11-13): computer use is on from the start; only switching it off removes its tools."""
    agents = [{"id": "worker-1", "role": "worker", "endpoint": "fake", "model": "m"},
              {"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": "m", "supervises": "worker-1"}]
    off = Services.open(make_config(agents=agents, computer={"screenshot": "off", "input": "off", "terminal": "off"}))
    start = Services.open(make_config(agents=agents), desktop=desktop())
    on = Services.open(make_config(agents=agents, computer=ON), desktop=desktop())
    try:
        names = lambda s, a: set(AgentRuntime(s.config.agents[a], s, set(s.config.agents)).tools)  # noqa: E731
        assert not names(off, "worker-1") & {"screenshot", "mouse_click", "terminal"}
        assert {"screenshot", "mouse_click", "terminal"} <= names(start, "worker-1")  # nothing configured: on
        assert {"screenshot", "mouse_click", "type_text", "press_keys", "launch_app", "terminal"} <= names(on, "worker-1")
        assert {"screenshot", "decide_action"} <= names(on, "guardian-1") and "mouse_click" not in names(on, "guardian-1")
    finally:
        off.db.close()
        start.db.close()
        on.db.close()
    with pytest.raises(ValueError, match="cannot execute"):
        tools_for("head_dispatch", ("mouse_click",))


def test_configuration_is_explicit(make_config):
    """What is configured must hold together; the user's rules: with nothing configured computer use is on, for every
    window (2026-11-13), and no list of windows or programs is needed (2026-11-14: "把所有的白名单全都删掉"); the supervisor
    and the 批准方式 still decide each action."""
    with pytest.raises(config_mod.ConfigError, match="screenshot"):
        make_config(computer={"input": "guardian", "windows": ["x"]})
    no_list = make_config(computer={"screenshot": "on", "input": "guardian"}).computer
    assert no_list.windows == ("",) and no_list.apps == "guardian" and no_list.launch == ()
    start = make_config().computer
    assert start.enabled and start.windows == ("",) and start.apps == "guardian"


# --- images to models, context, data class --------------------------------------------------------

def test_images_are_sent_as_data_urls_to_openai_compatible_models():
    m = ChatMessage("user", "look", images=[{"evidence": "ev:blob:" + "0" * 64, "mime": "image/png", "data": "AAAA"}])
    [enc] = OpenAICompatClient._encode([m])
    assert enc["content"][0] == {"type": "text", "text": "look"}
    assert enc["content"][1]["image_url"]["url"] == "data:image/png;base64,AAAA"


async def test_only_the_latest_screenshots_stay_in_the_context(make_config):
    agents, w, _ = pair([SHOOT, SHOOT, SHOOT, {"text": "done"}], [], guardian=False)
    d, sub, _ = await run(make_config(agents=agents, computer=ON), desktop())
    last = calls(d, w)[-1]["messages"]
    assert sum(len(m.images) for m in last) == 2
    assert any("older screenshot(s) removed from the context" in (m.content or "") for m in last)
    rebuilt, _ = d.agents["worker-1"]._rebuild_convo(sub["task_id"])
    assert sum(len(m.images) for m in rebuilt) == 0  # the task is over and its screenshots with it; the rest rebuilds
    await d.s.aclose()


async def test_screenshots_never_reach_an_endpoint_below_their_data_class(make_config):
    w = unique_model("w")
    scripted.register(w, [SHOOT, {"text": "should not be called"}])
    cfg = make_config(endpoints=[{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": False, "max_data_class": "internal"}],
                      agents=[{"id": "worker-1", "role": "general", "endpoint": "fake", "model": w}],
                      computer={**ON, "screenshot_data_class": "confidential"})
    d, sub, report = await run(cfg, desktop())
    assert report["body"]["outcome"] == "blocked" and "permission_needed" in report["body"]["summary"]
    assert len(calls(d, w)) == 1  # the screenshot was never sent
    await d.s.aclose()


def test_a_minimized_allowed_window_is_still_open_and_is_restored_to_act(gate):
    """Second real Notepad test: another program kept minimizing Notepad, the list said none was open and the
    approved click was refused. The user's rule (2026-11-14): a screenshot with no window named never brings up a
    minimized program; named, it does."""
    g, fake, s = gate
    g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    shot = g.shot(None, ctx().task_id)
    fake.wins = [replace(GAME, minimized=True), NOTEPAD]
    fake.fg = NOTEPAD.handle
    from codedoctor.computer.tools import list_windows

    assert "minimized" in list_windows(SimpleNamespace(services=s), {}).content
    out = approved(g, "click", {"x": 50, "y": 50}, screen_point=[150, 150], shot=shot["id"])
    assert out["status"] == "executed" and ("restore", GAME.handle) in fake.log and fake.fg == GAME.handle
    fake.wins = [replace(GAME, minimized=True), NOTEPAD]
    with pytest.raises(LookupError, match="open and visible"):
        g.screenshot(task_id=ctx().task_id, agent_id="worker-1")  # nothing named: it stays down
    assert fake.wins[0].minimized
    again = g.screenshot(task_id=ctx().task_id, agent_id="worker-1", window="MyGame")  # named: restored, then captured
    assert again["window"] == GAME.title and not fake.wins[0].minimized


async def test_help_me_review_asks_the_user_about_mouse_and_keyboard(make_config):
    """The user's rule (2026-11-14): 帮我审查 asks the user about mouse and keyboard; what they approve runs, what nobody
    answers is not done."""
    keys = {"tool_calls": [{"name": "press_keys", "arguments": {"keys": ["alt", "F4"], "intent": "close the game"}}]}
    agents, w, _ = pair([SHOOT, click(), keys, {"text": "done"}], [], guardian=False)
    cfg = make_config(agents=agents, computer={**ON, "user_timeout_s": 10})
    fake = desktop()
    d = Daemon(cfg, poll_s=0.02, desktop=fake)
    await d.start()
    try:
        sub = d.submit_task("worker-1", "reproduce", "Open the shop", approval="auto")
        for _ in range(500):  # the user approves the click and leaves the shortcut unanswered
            pending = [a for a in d.s.computer.actions(statuses=("pending_user",)) if a["kind"] == "click"]
            if pending:
                d.s.computer.user_decides(pending[0]["id"], True)
                break
            await asyncio.sleep(0.02)
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 40)
    finally:
        await d.halt()
    acts = d.s.computer.actions(task_ids=[sub["task_id"]])
    by_kind = {a["kind"]: a for a in acts}
    assert by_kind["click"]["status"] == "executed"
    assert any(e["what"] == "asked_user" for e in by_kind["click"]["events"])
    assert not any(e["what"] == "auto_approved" for a in acts for e in a["events"])
    assert by_kind["keys"]["status"] == "denied"
    assert [e for e in fake.log if e[0] == "click"] and not [e for e in fake.log if e[0] == "press"]


async def test_full_access_asks_nothing_but_the_hard_checks_stay(make_config):
    """完全访问权限: even an irreversible shortcut runs without asking; a blocked shortcut is still refused."""
    keys = {"tool_calls": [{"name": "press_keys", "arguments": {"keys": ["alt", "F4"], "intent": "close the game"}}]}
    blocked = {"tool_calls": [{"name": "press_keys", "arguments": {"keys": ["alt", "tab"], "intent": "switch"}}]}
    agents, w, _ = pair([SHOOT, keys, blocked, {"text": "done"}], [], guardian=False)
    fake = desktop()
    d = Daemon(make_config(agents=agents, computer=ON), poll_s=0.02, desktop=fake)
    await d.start()
    try:
        sub = d.submit_task("worker-1", "reproduce", "Close the game", approval="full")
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 15)
    finally:
        await d.halt()
    acts = d.s.computer.actions(task_ids=[sub["task_id"]])
    assert [a["status"] for a in acts if a["kind"] == "keys"] == ["executed", "refused"] or \
        sorted(a["status"] for a in acts if a["kind"] == "keys") == ["executed", "refused"]
    assert ("press", ("alt", "f4")) in fake.log and ("press", ("alt", "tab")) not in fake.log


# --- waiting for something slow -----------------------------------------------------------------------

def _loading(fake: FakeDesktop, moving: bool) -> FakeDesktop:
    """A loading screen: its bar grows on every capture (moving) or stays where it is."""
    from PIL import ImageDraw

    plain, n = fake.capture, [0]

    def capture(rect):
        img = plain(rect)
        n[0] += 1
        ImageDraw.Draw(img).rectangle([0, 0, 40 * (n[0] if moving else 1), 60], fill="#fff")
        return img
    fake.capture = capture
    fake.own_picture = False
    return fake


WAIT = {"tool_calls": [{"name": "wait_and_look", "arguments": {"seconds": 1}}]}


@pytest.mark.parametrize("moving", [True, False])
async def test_waiting_on_a_loading_screen_is_progress_while_it_moves(make_config, monkeypatch, moving):
    """A real run: a game loading its world showed the same kind of screen for a minute and the agent was stopped as
    "no new information" after 8 identical-looking screenshots. Waiting counts as progress while the screen changes;
    a screen that never changes still stops it (stall_steps 3 here)."""
    from codedoctor.computer import tools as ctools

    real_sleep = asyncio.sleep
    monkeypatch.setattr(ctools, "asyncio", SimpleNamespace(sleep=lambda s: real_sleep(0)), raising=False)
    agents, w, _ = pair([SHOOT, WAIT, WAIT, WAIT, WAIT, {"text": "loaded"}], [], guardian=False)
    d, sub, report = await run(make_config(agents=agents, computer=ON), _loading(desktop(), moving))
    body = report["body"]
    assert body["outcome"] == ("done" if moving else "stalled"), body["summary"]
    told = [m.content for m in calls(d, w)[-1]["messages"] if m.role == "tool"]
    assert any(("the screen changed" if moving else "did NOT change") in t for t in told)


def test_a_screenshot_knows_if_the_screen_changed(gate):
    g, fake, _ = gate
    task = ctx().task_id
    assert g.screenshot(task_id=task, agent_id="w")["changed"] is True  # the first one
    assert g.screenshot(task_id=task, agent_id="w")["changed"] is False
    from PIL import Image

    fake.capture_window = lambda handle: Image.new("RGB", (800, 600), "#fff")  # the game drew something else
    assert g.screenshot(task_id=task, agent_id="w")["changed"] is True
    assert g.screenshot(task_id="task_01JB8Z2000000000000000TK02", agent_id="w")["changed"] is True  # per task


async def test_screenshots_are_gone_when_the_whole_task_ends(make_config):
    """The user's rule: a screenshot serves the running task and is not kept. Nothing is written outside the project's
    data; the record of what was done stays."""
    seen = {}

    def look(msgs):
        seen["image_sent"] = any(m.images for m in msgs)
        return {"text": "done"}

    agents, w, _ = pair([SHOOT, look], [], guardian=False)
    d, sub, report = await run(make_config(agents=agents, computer=ON), desktop())
    assert report["body"]["outcome"] == "done" and seen["image_sent"]
    shots = d.s.db.query("SELECT doc FROM computer_shots WHERE task_id = ?", (sub["task_id"],))
    assert len(shots) == 1
    import json

    ev = json.loads(shots[0]["doc"])["evidence"]
    rec = d.s.evidence.get(ev)
    assert d.s.evidence.check(ev) == "forgotten" and not d.s.blobs.path(rec["content"]["sha256"]).exists()


# --- working behind the user's back: their mouse, keyboard and front window stay theirs ---------------------------------

@pytest.fixture
def behind(make_config):
    fake = FakeDesktop(wins=[NOTEPAD, GAME], fg=NOTEPAD.handle)  # the user plays in front; the allowed window is covered
    cfg = make_config(computer={**ON, "background": True, "input": "guardian"})
    s = Services.open(cfg, desktop=fake)
    yield s.computer, fake
    s.db.close()


def test_a_covered_window_is_worked_without_touching_the_user(behind):
    g, fake = behind
    shot = g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    assert shot["window"] == GAME.title
    for kind, args, extra in (("click", {"x": 40, "y": 40, "screenshot": shot["id"]}, {"shot": shot["id"], "screen_point": [140, 140]}),
                              ("type", {"text": "你好"}, {}), ("keys", {"keys": ["enter"]}, {})):
        approved(g, kind, args, **extra)
    names = [e[0] for e in fake.log]
    assert "post_click" in names and "post_text" in names and "post_keys" in names
    assert not {"focus", "click", "move", "type", "press"} & set(names)  # no real mouse, no real keyboard, nothing brought up
    assert fake.fg == NOTEPAD.handle


@pytest.mark.parametrize("kind,args", [("look", {"dx": 100, "dy": 0}), ("hold", {"keys": ["w"], "seconds": 1}), ("mouse_hold", {"button": "left", "seconds": 1})])
def test_what_needs_the_real_mouse_is_refused_in_the_background(behind, kind, args):
    g, fake = behind
    g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    assert "real mouse" in refused(g, kind, args)


def test_a_shortcut_cannot_be_sent_to_a_background_window(behind):
    g, fake = behind
    g.screenshot(task_id=ctx().task_id, agent_id="worker-1")
    assert "shortcut" in refused(g, "keys", {"keys": ["ctrl", "s"]})
