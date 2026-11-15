"""The Lumen team (agents/team.py): Lumen hands work to named members, they remember their earlier jobs, send one-off
helpers, Beacon re-checks the changers; the web tools stay off this computer's own addresses."""

from __future__ import annotations

import asyncio

from types import SimpleNamespace

import pytest

from codedoctor.agents import team
from codedoctor.agents.daemon import Daemon
from codedoctor.models import scripted

from conftest import unique_model


def team_agents(models: dict[str, list]) -> list[dict]:
    """The team as add_to_raw makes it, each member on its own scripted model (turns in `models`, by member id)."""
    raw = {"agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": unique_model("doc")}]}
    assert team.add_to_raw(raw)
    for a in raw["agents"]:
        name = unique_model(a["id"])
        scripted.register(name, models.get(a["id"], [{"text": "ok"}]))
        a["model"] = name
    return raw["agents"]


ALLOWED = {"write_files": True, "run_command": "allowlist", "command_allowlist": ["python -m pytest"]}
OK = {"text": "RECHECK OK - read the code and ran the tests myself; the report holds."}


def ask(*jobs):
    return {"tool_calls": [{"name": "ask_team", "arguments": {"jobs": [{"member": m, "task": t} for m, t in jobs]}}]}


async def _run(cfg, text, *, chat_of=None, d=None):
    own = d is None
    d = d or Daemon(cfg, poll_s=0.02)
    if own:
        await d.start()
    sub = d.submit_task("lumen", text[:40], text, chat_of=chat_of)
    report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 20)
    return d, sub, report


def test_the_team_joins_any_configuration_beside_the_cluster_modes(make_config):
    agents = team_agents({})
    ids = [a["id"] for a in agents]
    assert ids[1:] == [m.id for m in team.MEMBERS]
    beacon = next(a for a in agents if a["id"] == "beacon")
    assert beacon["supervises"] == "spark" and beacon["supervises_workers"] == ["lantern", "iris"]
    assert all(a["context_budget_tokens"] == team.CONTEXT_TOKENS for a in agents[1:])
    cfg = make_config(agents=agents, permissions=ALLOWED)
    assert cfg.agents["lumen"].team and not cfg.agents["doctor"].team
    assert len({m.name for m in team.MEMBERS}) == 8 and all(m.meaning and m.job for m in team.MEMBERS)
    raw = {"agents": agents}
    assert not team.add_to_raw(raw)  # already there: nothing changes


async def test_lumen_hands_work_to_two_members_at_once_and_answers(make_config):
    seen = {}

    def lumen_answers(msgs):
        seen["reports"] = " ".join(m.content or "" for m in msgs)
        return {"text": "Prism 找到了原因，Torch 跑过测试。"}

    agents = team_agents({
        "lumen": [ask(("prism", "Why is the total wrong?"), ("torch", "Run the tests")), lumen_answers],
        "prism": [{"text": "The total is computed in shop.py and skips the coupon."}, OK],
        "torch": [{"text": "3 tests ran, 1 failed: test_total."}, OK],
    })
    cfg = make_config(agents=agents, permissions=ALLOWED)
    d, sub, report = await _run(cfg, "结账总价不对，帮我看看")
    await d.halt()
    assert report["body"]["outcome"] == "done" and "Prism" in report["body"]["summary"]
    assert "shop.py" in seen["reports"] and "test_total" in seen["reports"] and '"member": "torch"' in seen["reports"]
    kids = d.s.db.query("SELECT agent FROM tasks WHERE parent_task_id = ?", (sub["task_id"],))
    assert sorted(k["agent"] for k in kids) == ["prism", "torch"]
    checks = d.s.db.query("SELECT agent, title FROM tasks WHERE agent LIKE '%-h%'")
    assert sorted(c["title"] for c in checks) == ["复查 Prism 的工作", "复查 Torch 的工作"]


async def test_a_member_remembers_its_earlier_jobs(make_config):
    second = {}

    def prism_second(msgs):
        second["text"] = " ".join(m.content or "" for m in msgs)
        return {"text": "As I found before: shop.py."}

    agents = team_agents({
        "lumen": [ask(("prism", "Where is the total computed?")), {"text": "shop.py"},
                  ask(("prism", "And the coupon?")), {"text": "done"}],
        "prism": [{"text": "In shop.py, function total()."}, OK, prism_second, OK],
    })
    cfg = make_config(agents=agents, permissions=ALLOWED)
    d, first, _ = await _run(cfg, "总价在哪算的")
    try:
        await _run(cfg, "优惠券呢", chat_of=first["task_id"], d=d)
    finally:
        await d.halt()
    assert "Where is the total computed?" in second["text"] and "function total()" in second["text"]


async def test_beacon_rechecks_what_spark_changed(make_config):
    agents = team_agents({
        "lumen": [ask(("spark", "Fix the coupon")), {"text": "Fixed and checked."}],
        "spark": [{"text": "Changed shop.py: the coupon is applied."}, OK],
        "beacon": [{"text": "Re-checked: the change is right."}],
    })
    cfg = make_config(agents=agents, permissions=ALLOWED)
    d, sub, report = await _run(cfg, "修一下优惠券")
    await d.halt()
    reviews = d.s.db.query("SELECT agent, state FROM tasks WHERE agent = 'beacon'")
    assert [dict(r) for r in reviews] == [{"agent": "beacon", "state": "finished"}]
    assert report["body"]["outcome"] == "done"


async def test_a_member_sends_one_off_helpers_that_are_gone_afterwards(make_config):
    agents = team_agents({  # the helpers run on prism's model: their answers come from the same script
        "lumen": [ask(("prism", "Check both modules")), {"text": "done"}],
        "prism": [{"tool_calls": [{"name": "spawn_helpers", "arguments": {"jobs": ["Read cart.py", "Read pay.py"]}}]},
                  {"text": "cart.py is fine."}, {"text": "pay.py is fine."}, {"text": "Both modules checked."}, OK],
    })
    cfg = make_config(agents=agents, permissions=ALLOWED)
    d, sub, report = await _run(cfg, "检查两个模块")
    await d.halt()
    helpers = d.s.db.query("SELECT agent FROM tasks WHERE agent LIKE 'prism-h%'")
    assert sorted(h["agent"] for h in helpers) == ["prism-h1", "prism-h2", "prism-h3"]  # two helpers and the re-check
    assert not any(a.startswith("prism-h") for a in d.agents) and "prism-h1" not in d.s.config.agents


async def test_a_one_off_helper_rechecks_a_members_work_before_lumen_gets_it(make_config):
    """The user's design: a one-off helper re-checks the member's work first; what it finds goes back to the member,
    and Lumen gets the corrected report."""
    seen = {}

    def spark_fixes(msgs):
        seen["told"] = " ".join(m.content or "" for m in msgs if m.role == "user")
        return {"text": "Fixed the second place too: cart.py and checkout.py now apply the coupon."}

    def lumen_answers(msgs):
        seen["lumen"] = " ".join(m.content or "" for m in msgs)
        return {"text": "Fixed in both places."}

    agents = team_agents({
        "lumen": [ask(("spark", "Apply the coupon everywhere")), lumen_answers],
        "spark": [{"text": "Changed cart.py: the coupon is applied."},
                  {"text": "checkout.py line 12 still ignores the coupon; the job said everywhere."},  # the re-check
                  spark_fixes],
        "beacon": [{"text": "Re-checked: both places are right."}],
    })
    cfg = make_config(agents=agents, permissions=ALLOWED)
    d, sub, report = await _run(cfg, "优惠券到处都要生效")
    await d.halt()
    assert "checkout.py line 12" in seen["told"]
    assert "checkout.py now apply" in seen["lumen"] and report["body"]["outcome"] == "done"
    rows = d.s.db.query("SELECT agent, title FROM tasks WHERE agent LIKE 'spark-h%'")
    assert [r["title"] for r in rows] == ["复查 Spark 的工作"]  # once: the corrected report is not checked again
    assert not any(a.startswith("spark-h") for a in d.agents)


def test_the_web_tools_never_reach_this_computer_and_respect_the_data_level():
    ctx = SimpleNamespace(data_class="internal")
    for url in ("http://127.0.0.1:8765/api/tasks", "http://localhost/", "http://192.168.1.5/", "file:///C:/x"):
        res = team.fetch_page(ctx, {"url": url})
        assert not res.ok, url
    res = team.web_search(SimpleNamespace(data_class="local_only"), {"query": "x"})
    assert not res.ok and "local_only" in res.content


def test_page_text_is_readable():
    page = "<html><head><title>t</title><style>.a{}</style></head><body><h1>Wood</h1><p>Hold the&nbsp;left button" \
           "<script>evil()</script></p></body></html>"
    assert team._text(page) == "Wood\nHold the left button"


@pytest.mark.parametrize("agent", ["spark-h3", "spark"])
def test_helpers_are_their_members(agent):
    assert team.member(agent).name == "Spark"


# --- the team across a process boundary: Claude Code as a member (agents/team_link.py, mcp_bridge.py) ------------------

def test_the_lead_on_claude_code_can_only_share_the_work_out(make_config):
    """The lead only shares the work out; the user's rule: no command allowlist, so a member's shell is all of Bash."""
    from codedoctor import claude_code

    cfg = make_config(agents=team_agents({}), permissions={"write_files": True, "run_command": "allowlist",
                                                           "command_allowlist": ["python -m pytest"]})
    allowed, denied, edits = claude_code.team_rights(cfg, cfg.agents["lumen"])
    assert not edits and "Edit" in denied and "Write" in denied and "Bash" in denied and "Read" in allowed
    assert "Task" in denied and "Agent" in denied  # Claude Code's own subagents would not be the team
    allowed, denied, edits = claude_code.team_rights(cfg, cfg.agents["spark"])
    assert edits and "Edit" in allowed and "Bash" in allowed and "Bash" not in denied
    assert not [t for t in allowed if t.startswith("Bash(")]
    allowed, denied, edits = claude_code.team_rights(cfg, cfg.agents["prism"])
    assert not edits and "Edit" in denied and "Bash" in allowed
    allowed, denied, _ = claude_code.team_rights(cfg, cfg.agents["ray"])
    assert "WebSearch" in allowed and "Read" in denied
    text = team.engine_prompt("lumen", "shop", sorted(cfg.agents))
    assert "mcp__codedoctor__ask_team" in text and "spark (Spark)" in text


async def test_an_engine_hands_work_to_the_team_through_the_link(make_config, monkeypatch):
    """Claude Code's MCP server (a separate program) reaches ask_team in the running service, with the token, only as
    the agent of a running task; a member's report comes back as the tool's answer. The user's rule (2026-11-13): only a
    guardian may give its own verdict on a computer action (decide_action) over the link."""
    import io
    import json

    from codedoctor import mcp_bridge
    from codedoctor.agents import team_link

    agents = team_agents({"lumen": [{"wait_s": 3, "text": "done"}], "torch": [{"text": "All 3 tests pass."}, OK]})
    d = Daemon(make_config(agents=agents, permissions=ALLOWED), poll_s=0.02)
    await d.start()
    try:
        sub = d.submit_task("lumen", "t", "Run the tests")
        await asyncio.sleep(0.3)
        link = await team_link.ensure(d.s)
        for key, value in team_link.env(link, sub["task_id"], "lumen").items():
            monkeypatch.setenv(key, value)
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "ask_team", "arguments": {
            "jobs": [{"member": "torch", "task": "Run the tests"}]}}}
        monkeypatch.setenv("LUMEN_TEAM_TOKEN", "wrong")
        ok, text, _ = await asyncio.to_thread(mcp_bridge._forward, "ask_team", call["params"]["arguments"])
        assert not ok and "refused" in text
        monkeypatch.setenv("LUMEN_TEAM_TOKEN", link["token"])
        monkeypatch.setenv("LUMEN_TEAM_AGENT", "torch")  # not the agent of this task
        ok, text, _ = await asyncio.to_thread(mcp_bridge._forward, "ask_team", call["params"]["arguments"])
        assert not ok and "no such running task" in text
        monkeypatch.setenv("LUMEN_TEAM_AGENT", "lumen")
        ok, text, _ = await asyncio.to_thread(mcp_bridge._forward, "decide_action", {})
        assert not ok and "only a guardian" in text  # the user's approval never goes over the link; Lumen is no guardian

        lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n", json.dumps(call) + "\n"]
        out = io.StringIO()
        await asyncio.to_thread(mcp_bridge.serve, d.config.root, ["@ask_team", "@spawn_helpers"], stdin=iter(lines), stdout=out)
        listed, called = [json.loads(x) for x in out.getvalue().splitlines()]
        assert {t["name"] for t in listed["result"]["tools"]} == {"ask_team", "spawn_helpers"}
        assert not called["result"]["isError"] and "All 3 tests pass." in called["result"]["content"][0]["text"]
    finally:
        await d.halt()


async def test_a_long_report_does_not_stop_a_members_next_job(make_config):
    """A real run: Torch's first report was longer than the message format took, so every later job for Torch failed
    before it began, and the other job of the same call was sent twice."""
    long_report = "test_x ... ok\n" * 900
    agents = team_agents({
        "lumen": [ask(("torch", "Run the tests")), ask(("prism", "Look"), ("torch", "Run them again")), {"text": "done"}],
        "torch": [{"text": long_report}, OK, {"text": "All pass now."}, OK],
        "prism": [{"text": "Looked."}, OK],
    })
    d, sub, report = await _run(make_config(agents=agents, permissions=ALLOWED), "跑测试")
    await d.halt()
    rows = d.s.db.query("SELECT agent, outcome FROM tasks WHERE parent_task_id = ? ORDER BY created_at", (sub["task_id"],))
    assert [(r["agent"], r["outcome"]) for r in rows] == [("torch", "done"), ("prism", "done"), ("torch", "done")]
    assert report["body"]["outcome"] == "done"


async def test_one_job_that_cannot_start_does_not_lose_the_others(make_config, monkeypatch):
    agents = team_agents({"lumen": [ask(("prism", "Look"), ("torch", "Run")), {"text": "done"}],
                          "prism": [{"text": "Looked."}, OK]})
    monkeypatch.setattr(team, "history", lambda s, who: [{"user": "x" * 9000, "assistant": "y"}] if who == "torch" else [])
    seen = {}
    real = team.ask_team

    async def spy(ctx, args):
        res = await real(ctx, args)
        seen["out"] = res.content
        return res
    monkeypatch.setattr(team.TOOLS["ask_team"], "handler", spy)
    d, sub, _ = await _run(make_config(agents=agents, permissions=ALLOWED), "看看")
    await d.halt()
    assert '"not started"' in seen["out"] and "Looked." in seen["out"]
    assert [r["agent"] for r in d.s.db.query("SELECT agent FROM tasks WHERE parent_task_id = ?", (sub["task_id"],))] == ["prism"]


def test_a_member_on_claude_code_has_only_its_own_tools(make_config, tmp_path):
    from codedoctor import claude_code

    cfg = make_config(agents=team_agents({}), permissions={"write_files": True, "run_command": "allowlist",
                                                           "command_allowlist": ["python -m unittest"]})
    out = claude_code.argv(cfg, "claude", cfg=cfg.agents["torch"], persona="You are Torch.")
    tools = out[out.index("--tools") + 1].split(",")
    assert "Bash" in tools and "Read" in tools and "Edit" not in tools and "--strict-mcp-config" in out
    assert not {"ListAgents", "SendMessage", "PowerShell", "Task", "Agent"} & set(tools)
    text = team.engine_prompt("torch", "shop", sorted(cfg.agents), ("python -m unittest",))
    assert "python -m unittest" in text and "STATUS: DONE" in text
    shown = claude_code.step("mcp__codedoctor__ask_team", {"jobs": [{"member": "spark", "task": "写\n代码"},
                                                                    {"member": "torch", "task": "跑"}]}, tmp_path)
    assert shown == {"tool": "ask_team", "description": "Spark、Torch：写"}


# --- the whole team on an engine: the choice reaches everyone, memory, the computer, CodeCut, Codex --------------------

async def test_what_the_user_chose_reaches_everyone_working_on_the_task(make_config):
    from codedoctor.agents import orchestration as orch

    d = Daemon(make_config(agents=team_agents({})), poll_s=0.05)
    root = orch.create_subtask(d.s, sender="user", recipient="lumen", title="t", instructions="go", parent_task_id=None,
                               extra={"engine": "codex", "engine_model": "gpt-5.6-luna", "engine_effort": "low", "toolsets": ["codecut"]})
    kid = orch.create_subtask(d.s, sender="lumen", recipient="spark", title="x", instructions="do", parent_task_id=root["task_id"])
    grandkid = orch.create_subtask(d.s, sender="spark", recipient="beacon", title="y", instructions="check", parent_task_id=kid["task_id"])
    body = orch.body_of(orch.task_row(d.s, grandkid["task_id"]))
    assert (body["engine"], body["engine_model"], body["engine_effort"], body["toolsets"]) == ("codex", "gpt-5.6-luna", "low", ["codecut"])
    await d.s.aclose()


async def test_each_member_gets_its_own_tools_on_an_engine(make_config, monkeypatch):
    """Each member gets its job's tools; the user's rule (2026-11-13): a guardian on an engine gives its own verdict on a
    computer action with decide_action (the user's approval stays in the window)."""
    from codedoctor import engines, video

    monkeypatch.setattr(video, "home", lambda: video.Path("."))
    d = Daemon(make_config(agents=team_agents({}), computer={"screenshot": "on", "input": "ask", "windows": ["Game"]},
                           permissions={"write_files": True}), poll_s=0.05, desktop=None)
    await d.start()
    try:
        body = {"task_id": "task_x", "title": "t", "instructions": "cut the video", "toolsets": ["codecut"]}
        lead = await engines.team_setup(d.agents["lumen"], body, "mcp__codedoctor__")
        assert "codecut" not in lead["toolsets"] and "@ask_team" in lead["toolsets"] and "@remember" in lead["toolsets"]
        spark = await engines.team_setup(d.agents["spark"], body, "mcp__codedoctor__")
        assert "codecut" in spark["toolsets"] and "@spawn_helpers" in spark["toolsets"] and "@ask_team" not in spark["toolsets"]
        assert "mcp__codedoctor__video_edit" in spark["persona"]
        ray = await engines.team_setup(d.agents["ray"], body, "")
        assert "@browser_open" in ray["toolsets"]
        assert "video_edit" in d.agents["spark"].tools
        beacon = await engines.team_setup(d.agents["beacon"], body, "")
        assert "@decide_action" in beacon["toolsets"] and "@approve_permission" in beacon["toolsets"]
        assert "@decide_action" not in spark["toolsets"]  # only the guardian decides
    finally:
        await d.halt()


async def test_memory_and_the_computer_work_through_the_link(make_config, monkeypatch):
    """Iris played by an engine sees the screen as a picture and acts under the same gate; a member's memory is its own."""
    from codedoctor import mcp_bridge
    from codedoctor.agents import team_link
    from codedoctor.computer.desktop import FakeDesktop, Window

    game = Window(1, "MyGame", 10, (100, 100, 900, 700))
    agents = team_agents({"iris": [{"wait_s": 4, "text": "done"}]})
    d = Daemon(make_config(agents=agents, computer={"screenshot": "on", "input": "ask", "windows": ["MyGame"]}),
               poll_s=0.02, desktop=FakeDesktop(wins=[game], fg=1))
    await d.start()
    try:
        sub = d.submit_task("iris", "t", "look at the game")
        await asyncio.sleep(0.3)
        link = await team_link.ensure(d.s)
        for key, value in team_link.env(link, sub["task_id"], "iris").items():
            monkeypatch.setenv(key, value)
        ok, text, images = await asyncio.to_thread(mcp_bridge._forward, "screenshot", {})
        assert ok and "screenshot" in text and images and images[0]["mime"] == "image/png" and images[0]["data"]
        ok, text, _ = await asyncio.to_thread(mcp_bridge._forward, "remember", {"text": "The menu is at the top.", "kind": "fact"})
        assert ok, text
        ok, text, _ = await asyncio.to_thread(mcp_bridge._forward, "recall", {"query": "menu"})
        assert ok and "menu" in text.lower()
        ok, text, _ = await asyncio.to_thread(mcp_bridge._forward, "ask_team", {"jobs": []})
        assert not ok and "may not use" in text  # not Iris's tool
    finally:
        await d.halt()


def test_codex_plays_a_member_by_its_job(make_config):
    """The user's rule (2026-11-14): no sandbox of Codex's, whoever the member; its job only decides web search, and a
    member is told no limits ("Change no files." is gone)."""
    from codedoctor import codex

    cfg = make_config(agents=team_agents({}), permissions={"write_files": True, "run_command": "allowlist",
                                                           "command_allowlist": ["python -m unittest"]})
    mcp = {"command": "python", "args": ["-m", "x"], "env": {"A": "1"}}
    lead = codex.argv(cfg, ["codex"], mcp, cfg=cfg.agents["lumen"])
    assert lead[lead.index("--sandbox") + 1] == "danger-full-access" and any("tool_timeout_sec=86460" in x for x in lead)
    spark = codex.argv(cfg, ["codex"], mcp, cfg=cfg.agents["spark"])
    assert spark[spark.index("--sandbox") + 1] == "danger-full-access"
    ray = codex.argv(cfg, ["codex"], cfg=cfg.agents["ray"])
    assert 'web_search="live"' in ray and ray[ray.index("--sandbox") + 1] == "danger-full-access"
    plain = codex.argv(cfg, ["codex"])
    assert 'web_search="disabled"' in plain and plain[plain.index("--sandbox") + 1] == "danger-full-access"
    body = {"title": "t", "instructions": "go", "task_id": "x"}
    setup = {"persona": "You are Lumen.", "notes": "", "toolsets": ["@ask_team", "@remember"]}
    text = codex._member_prompt(cfg, body, setup, cfg.agents["lumen"])
    assert "ask_team, remember" in text and "Change no files." not in text and "STATUS: DONE" in text
    assert codex.bridged("ask_team", {"jobs": [{"member": "spark", "task": "写代码"}]})["description"] == "Spark：写代码"


async def test_lumen_is_told_who_cannot_work_in_this_project(make_config):
    """A real run: Lumen kept sending work to members who could not do it, and ended "blocked" though the video was fine.
    It now knows, and ask_team refuses. The user's rule: commands and file changes can no longer be switched off, so only
    computer use, when the user turned it off, leaves a member (Iris) without work."""
    seen = {}

    def lead(msgs):
        seen["system"] = msgs[0].content
        return ask(("iris", "Click the start button"))

    agents = team_agents({"lumen": [lead, {"text": "done"}]})
    d, sub, report = await _run(make_config(agents=agents, permissions={"write_files": False, "run_command": "deny"},
                                            computer={"screenshot": "off", "input": "off", "terminal": "off"}), "点开始")
    await d.halt()
    assert "Not available in this project" in seen["system"] and "Iris (computer use" in seen["system"]
    assert "Torch (running commands" not in seen["system"] and "Spark (changing files" not in seen["system"]
    assert "- torch (Torch)" in seen["system"] and "- iris (Iris)" not in seen["system"]
    assert not d.s.db.query("SELECT 1 FROM tasks WHERE agent = 'iris'")


def test_a_picture_of_the_export_comes_through_the_tool_server(tmp_path, monkeypatch):
    """A real run: the tool server had no evidence store, so taking a picture ended it ("Connection closed"), and with it
    every video tool of that run. Pictures come back as pictures; a tool that fails does not end the server."""
    import io
    import json

    from codedoctor import mcp_bridge, video

    def frame(ctx, args, root):
        ev = ctx.services.evidence.add_blob(b"png-bytes", "image/png", source="tool")
        if args.get("at") == 9:
            raise ValueError("no such moment")
        return team.ToolResult(ok=True, content="picture", evidence=[ev], images=[ev])

    monkeypatch.setattr(video, "_frame", frame)
    calls = [{"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": "video_project", "arguments": {
        "action": "frame", "media": "out/clip.mp4", "at": at}}} for i, at in ((1, 1), (2, 9), (3, 1))]
    out = io.StringIO()
    mcp_bridge.serve(tmp_path, ["codecut"], stdin=iter(json.dumps(c) + "\n" for c in calls), stdout=out)
    first, failed, again = [json.loads(x)["result"] for x in out.getvalue().splitlines()]
    assert first["content"][1] == {"type": "image", "data": "cG5nLWJ5dGVz", "mimeType": "image/png"}
    assert failed["isError"] and "no such moment" in failed["content"][0]["text"] and not again["isError"]


def test_the_computers_tools_exist_in_the_tool_server(tmp_path):
    """A real run: they were not registered there, the server died on start and Iris's Claude Code waited for ever."""
    import io
    import json

    from codedoctor import mcp_bridge

    out = io.StringIO()
    mcp_bridge.serve(tmp_path, ["@screenshot", "@mouse_click", "@remember"], stdout=out,
                     stdin=iter([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + chr(10)]))
    assert {t["name"] for t in json.loads(out.getvalue())["result"]["tools"]} == {"screenshot", "mouse_click", "remember"}


async def test_a_recheck_is_told_what_is_worth_sending_back(make_config):
    """A real run: a re-check sent Ray back over pixel differences, Ray tested everything again, and the eight minutes ran out
    before anyone reported three bugs both had found."""
    seen = {}

    def checker(msgs):
        seen["job"] = " ".join(m.content or "" for m in msgs)
        return OK

    agents = team_agents({"lumen": [ask(("prism", "Look")), {"text": "done"}], "prism": [{"text": "Found it."}, checker]})
    d, _, report = await _run(make_config(agents=agents, permissions=ALLOWED), "看看")
    await d.halt()
    assert "would mislead the user" in seen["job"] and "a few pixels off" in seen["job"]
    assert report["body"]["outcome"] == "done"


# --- keeping functions as they are called (agents/interfaces.py) ---------------------------------------------------------

SHOP = """def refund(order_id, items):
    for sku, qty in items:
        pass
    return 5


def total(cart, coupon=0):
    return 1


def _private(x):
    return x


class Cart:
    def add(self, sku):
        return sku
"""


def _services(tmp_path):
    return SimpleNamespace(config=SimpleNamespace(root=tmp_path))


@pytest.mark.parametrize("old,new,line", [
    ("def refund(order_id, items):", "def refund(order_id):", "was refund(order_id, items), now refund(order_id)"),
    ("def refund(order_id, items):", "def refund(order, items):", "now refund(order, items)"),
    ("def refund(order_id, items):", "def refund(order_id, items, key):", "now refund(order_id, items, key)"),
    ("def total(cart, coupon=0):", "def total(cart, coupon):", "now total(cart, coupon)"),
    ("def total(cart, coupon=0):", "def sum_up(cart, coupon=0):", "total(cart, coupon=0) is gone"),
    ("    def add(self, sku):", "    def add(self, sku, qty):", "Cart.add"),
])
def test_calls_that_no_longer_fit_are_found(tmp_path, old, new, line):
    from codedoctor.agents import interfaces

    f = tmp_path / "shop.py"
    f.write_text(SHOP, encoding="utf-8")
    s = _services(tmp_path)
    interfaces.remember(s, "root")
    assert interfaces.breaks(s, "root") == []
    f.write_text(SHOP.replace(old, new), encoding="utf-8")
    assert any(line in x for x in interfaces.breaks(s, "root")), interfaces.breaks(s, "root")


@pytest.mark.parametrize("old,new", [
    ("def refund(order_id, items):", "def refund(order_id, items, key=None):"),  # a new optional parameter fits
    ("def _private(x):", "def _private(x, y):"),
    ("    return 1\n", "    return max(1, 0)\n"),
])
def test_what_keeps_calls_working_is_no_break(tmp_path, old, new):
    from codedoctor.agents import interfaces

    f = tmp_path / "shop.py"
    f.write_text(SHOP, encoding="utf-8")
    s = _services(tmp_path)
    interfaces.remember(s, "root")
    f.write_text(SHOP.replace(old, new), encoding="utf-8")
    assert interfaces.breaks(s, "root") == []


def test_what_the_real_run_changed_goes_to_the_recheck(tmp_path):
    """refund() kept its parameters, took them apart differently and returned something else: no program can call that
    wrong, so the re-check gets it in black and white."""
    from codedoctor.agents import interfaces

    f = tmp_path / "shop.py"
    f.write_text(SHOP, encoding="utf-8")
    s = _services(tmp_path)
    interfaces.remember(s, "root")
    f.write_text(SHOP.replace("for sku, qty in items:", "for idx, qty in items:").replace("return 5", "return {'cents': 5}"), encoding="utf-8")
    assert interfaces.breaks(s, "root") == []
    text = " ".join(interfaces.changes(s, "root"))
    assert "(sku, qty) in items" in text.replace("'", "") or "sku, qty in items" in text
    assert "idx" in text and "returned 5" in text and "cents" in text


def test_a_job_that_asks_for_it_may_change_an_interface(make_config):
    from codedoctor.agents import interfaces

    assert interfaces.told_to_change("请把 refund 的接口改成按行号") and not interfaces.told_to_change("修好退款")


async def test_a_member_that_breaks_a_call_is_sent_back_before_the_recheck(make_config, project):
    target = project / "server" / "shop.py"
    source = target.read_text(encoding="utf-8")
    name = next(ln for ln in source.splitlines() if ln.lstrip().startswith("def ") and not ln.lstrip().startswith("def _") and "self, " in ln)
    seen = {}

    def breaks_it(msgs):
        target.write_text(source.replace(name, name.split("(")[0] + "(self):"), encoding="utf-8")
        return {"text": "Changed it."}

    def puts_it_back(msgs):
        seen["told"] = " ".join(m.content or "" for m in msgs if m.role == "user")
        target.write_text(source, encoding="utf-8")
        return {"text": "Put back."}

    agents = team_agents({"lumen": [ask(("spark", "Fix the total")), {"text": "done"}], "spark": [breaks_it, puts_it_back, OK],
                          "beacon": [{"text": "ok"}]})
    d, _, report = await _run(make_config(agents=agents, permissions=ALLOWED), "修总价")
    await d.halt()
    assert "no longer fit" in seen["told"] and report["body"]["outcome"] == "done"
    assert team.KEEP_INTERFACES in d.s.models.client("fake").calls[1]["messages"][0].content
