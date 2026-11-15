"""Claude Code kept running between messages (codedoctor/engine_sessions.py). A stand-in `claude` speaks the same stream."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import textwrap

import pytest

from codedoctor import claude_code, engine_sessions, engines
from codedoctor.agents import team_link
from codedoctor.agents.daemon import Daemon
from test_team import team_agents

FAKE = textwrap.dedent('''
    import json, os, pathlib, sys
    args = sys.argv[1:]
    log = pathlib.Path(os.environ["FAKE_LOG"])
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"start": os.getpid(), "args": args}) + "\\n")
    spent, turn = 0.0, 0
    for raw in sys.stdin.buffer:
        text = json.loads(raw.decode("utf-8"))["message"]["content"][0]["text"]
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"got": text, "pid": os.getpid()}) + "\\n")
        turn += 1
        if "DIE" in text:
            os._exit(1)
        print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "thinking"}]}}), flush=True)
        # the message itself, not the earlier turns sent with a later one; a first message carries a note after it
        if "HANG please" in text and "Earlier in this conversation" not in text:
            import time
            time.sleep(60)
        spent += .01
        print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": f"answer {turn}", "num_turns": 1,
                          "total_cost_usd": spent, "duration_api_ms": 900,
                          "usage": {"input_tokens": 2, "cache_read_input_tokens": 3000, "output_tokens": 12}}), flush=True)
''')


@pytest.fixture
def stand_in(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE, encoding="utf-8")
    log = tmp_path / "fake.log"
    log.write_text("", encoding="utf-8")
    monkeypatch.setenv("FAKE_LOG", str(log))
    real = claude_code.argv

    def argv(*a, **k):
        return [sys.executable, str(script), *real(*a, **k)[1:]]

    monkeypatch.setattr(claude_code, "argv", argv)
    monkeypatch.setattr(claude_code, "executable", lambda: "claude")

    def seen(key):
        return [e[key] for e in map(json.loads, log.read_text(encoding="utf-8").splitlines()) if key in e]

    return seen


def config(make_config):
    return make_config(agents=team_agents({}))


async def say(d, text, chat_of=None, **kw):
    sub = d.submit_task("lumen", text[:40], text, engine="claude_code", chat_of=chat_of, **kw)
    report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 20)
    return sub["task_id"], report["body"]


@pytest.fixture
async def daemon(make_config, stand_in):
    d = Daemon(config(make_config), poll_s=0.02)
    await d.start()
    yield d
    await d.halt()


async def test_a_conversation_is_one_process(daemon, stand_in):
    first, a = await say(daemon, "1+1")
    second, b = await say(daemon, "再加 2", chat_of=first)
    assert a["summary"] == "answer 1" and b["summary"] == "answer 2"
    assert len(stand_in("start")) == 1  # no cold start for the second message
    got = stand_in("got")
    assert got[1].endswith("再加 2") and "1+1" not in got[1].split("---")[-1] and "Earlier in this conversation" not in got[1]  # it remembers


async def test_the_second_message_is_counted_on_its_own(daemon):
    first, _ = await say(daemon, "1+1")
    second, _ = await say(daemon, "2+2", chat_of=first)
    rows = [e["data"] for e in daemon.s.journal.read(task_id=second) if e["type"] == "model_response"]
    assert rows[0]["cost_usd"] == pytest.approx(.01) and rows[0]["reused"] is True and rows[0]["total_ms"] >= rows[0]["first_ms"]
    assert rows[0]["input_tokens"] == 3002 and rows[0]["output_tokens"] == 12


async def test_another_conversation_has_its_own(daemon, stand_in):
    await say(daemon, "one")
    await say(daemon, "two")
    assert len(stand_in("start")) == 2


async def test_another_level_is_another_process_and_gets_the_earlier_turns(daemon, stand_in):
    first, _ = await say(daemon, "记住 42", engine_effort="low")
    _, b = await say(daemon, "我说的是几？", chat_of=first, engine_effort="high")
    assert b["summary"] == "answer 1" and len(stand_in("start")) == 2
    assert "记住 42" in stand_in("got")[1] and "answer 1" in stand_in("got")[1]
    assert "high" in stand_in("args")[1]


async def test_a_process_that_died_while_waiting_is_replaced_without_the_user_noticing(daemon, stand_in):
    first, _ = await say(daemon, "记住 42")
    session = engine_sessions.pool(daemon.s)[first]
    engines.kill(session.proc)
    await session.proc.wait()
    _, b = await say(daemon, "几？", chat_of=first)
    assert b["outcome"] == "done" and b["summary"] == "answer 1" and "记住 42" in stand_in("got")[-1]


async def test_a_crash_during_the_answer_is_said(daemon):
    _, b = await say(daemon, "DIE now")
    assert b["outcome"] == "failed" and "without a result" in b["summary"]
    assert not engine_sessions.pool(daemon.s)


async def test_cancelling_stops_it_and_the_next_message_starts_clean(daemon, stand_in):
    from codedoctor import interface

    sub = daemon.submit_task("lumen", "HANG", "HANG please", engine="claude_code")
    await asyncio.sleep(1.5)
    interface.cancel(daemon, sub["task_id"])
    for _ in range(600):
        if daemon.task(sub["task_id"])["state"] == "finished" and not engine_sessions.pool(daemon.s):
            break
        await asyncio.sleep(.02)
    assert daemon.task(sub["task_id"])["outcome"] != "done" and not engine_sessions.pool(daemon.s)
    _, b = await say(daemon, "你好", chat_of=sub["task_id"])
    assert b["summary"] == "answer 1"


async def test_it_closes_with_lumen(make_config, stand_in):
    d = Daemon(config(make_config), poll_s=0.02)
    await d.start()
    first, _ = await say(d, "1+1")
    proc = engine_sessions.pool(d.s)[first].proc
    await d.halt()
    await asyncio.wait_for(proc.wait(), 10)
    assert not engine_sessions.pool(d.s)


async def test_idle_ones_close_and_few_stay(daemon, monkeypatch):
    ids = [(await say(daemon, f"chat {i}"))[0] for i in range(engine_sessions.MOST + 1)]
    pool = engine_sessions.pool(daemon.s)
    assert len(pool) == engine_sessions.MOST and ids[0] not in pool
    monkeypatch.setattr(engine_sessions, "IDLE_S", 0)
    await asyncio.sleep(.01)
    engine_sessions.prune(daemon.s)
    assert not pool


async def test_a_spare_process_waits_for_the_next_new_chat(daemon, stand_in):
    rt = daemon.agents["lumen"]
    await claude_code.warm(rt, {"engine": "claude_code", "engine_model": None, "engine_effort": None})
    await asyncio.sleep(.8)  # it has started and sits waiting
    assert stand_in("got") == []  # waiting spends nothing
    _, a = await say(daemon, "你好")
    assert a["summary"] == "answer 1"
    await asyncio.sleep(.3)
    assert len(stand_in("start")) == 1  # the spare took it
    engine_sessions.prune(daemon.s)


async def test_the_team_link_finds_the_current_task(daemon):
    daemon.s.__dict__["_team_sessions"] = {"sess_x": "task_now"}
    seen = {}

    def row(services, task_id):
        seen["task"] = task_id
        return None

    team_link.orch.task_row, keep = row, team_link.orch.task_row
    try:
        out = await team_link._answer(daemon.s, "t", json.dumps({"token": "t", "task_id": "sess_x", "agent": "lumen", "tool": "ask_team"}).encode())
    finally:
        team_link.orch.task_row = keep
    assert seen["task"] == "task_now" and not out["ok"]


def test_lumen_gets_a_short_system_prompt_and_members_keep_the_coders(make_config):
    d = Daemon(config(make_config), poll_s=0.02)
    conf = d.s.config
    lead = claude_code.argv(conf, "claude", cfg=conf.agents["lumen"], persona="You are Lumen.")
    assert "--system-prompt" in lead and "--append-system-prompt" not in lead
    spark = claude_code.argv(conf, "claude", cfg=conf.agents["spark"], persona="You are Spark.")
    assert "--append-system-prompt" in spark

