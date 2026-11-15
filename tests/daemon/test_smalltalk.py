"""Small talk is answered by the model, not investigated (agents/smalltalk.py): no snapshot, no subtask, no review, and no
canned reply; anything that asks about code is investigated as before."""

from __future__ import annotations

import asyncio

import pytest

from codedoctor.agents import smalltalk
from codedoctor.agents.daemon import Daemon


@pytest.mark.parametrize("text", ["你好", "你好！", "您好呀", "你好你好", "hi", "Hello!", "hey there", "谢谢", "好的，谢谢",
                                  "在吗？", "你是谁", "你能做什么？", "thanks!", "ok", "こんにちは", "안녕하세요", "Bonjour"])
def test_these_are_small_talk(text):
    assert smalltalk.is_smalltalk(text)


@pytest.mark.parametrize("text", ["你好，帮我看一下登录为什么失败", "hi, the cart total is wrong", "早期版本有个 bug",
                                  "好的，把优惠券改成减 8 块", "test the checkout", "为什么结账慢", "修一下",
                                  "你好\n结账的时候报错了", "hello world 这个函数报错"])
def test_these_are_work(text):
    assert not smalltalk.is_smalltalk(text)


def test_there_are_no_canned_replies():
    """The user could tell them by their speed: 你好 came back at once, 1+1 took a moment."""
    assert not hasattr(smalltalk, "FIXED") and not hasattr(smalltalk, "fixed")


async def _ask(cfg, text, **kw):
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", text[:60], text, **kw)
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 20)
        rows = d.s.db.query("SELECT id FROM tasks")
        calls = [e for e in d.s.journal.read(task_id=sub["task_id"]) if e["type"] in ("tool_call", "model_request")]
        snaps = d.s.db.query("SELECT 1 FROM sqlite_master WHERE name = 'workspace_snapshots'")
        return report["body"], len(rows), calls, sub, d, snaps
    finally:
        await d.halt()


async def test_hello_gets_a_line_back_and_nothing_else(make_config):
    cfg = make_config({"chat-model": [{"text": "你好！有什么要我查的？"}]})
    body, tasks, calls, sub, d, _ = await _ask(cfg, "你好")
    assert body["outcome"] == "done" and body["summary"] == "你好！有什么要我查的？"
    assert tasks == 1 and calls == []  # no subtask, no tool, no investigation request
    assert body["usage"]["model_calls"] == 1


async def test_with_codex_doing_the_work_codex_answers(make_config, monkeypatch):
    from codedoctor import codex
    from codedoctor.agents.runtime import AgentRuntime, Usage

    asked = []

    async def answers(rt, msg, body):
        asked.append(body["instructions"])
        return "done", "你好呀，今天过得怎么样？", {"evidence": [], "claims": [], "usage": Usage()}

    async def no_review(*a, **k):
        raise AssertionError("a greeting is not reviewed")

    monkeypatch.setattr(codex, "run", answers)
    monkeypatch.setattr(AgentRuntime, "_engine_recheck", no_review)
    cfg = make_config(endpoints=[{"id": "codex", "kind": "engine", "base_url": "engine:codex", "local": False,
                                  "max_data_class": "internal", "models": ["gpt-9-sol"]}],
                      agents=[{"id": "doctor", "role": "general", "endpoint": "codex", "model": "gpt-9-sol"}])
    body, *_ = await _ask(cfg, "你好")
    assert asked == ["你好"] and body["outcome"] == "done" and body["summary"] == "你好呀，今天过得怎么样？"


async def test_when_the_model_cannot_answer_the_user_is_told(make_config, monkeypatch):
    from codedoctor.models.base import ModelError
    from codedoctor.models.factory import ModelPool

    class Down:
        provider = "fake"

        async def chat(self, *a, **k):
            raise ModelError("HTTP 500: down", retryable=False, status=500)

        async def aclose(self):
            pass

    monkeypatch.setattr(ModelPool, "client", lambda self, eid: Down())
    body, *_ = await _ask(make_config({"down-model": [{"text": "unused"}]}), "你好")
    assert body["outcome"] == "failed" and "down" in body["summary"]


async def test_a_question_about_code_is_still_investigated(make_config):
    cfg = make_config({"work-model": [{"tool_calls": [{"name": "list_dir", "arguments": {"path": "."}}]},
                                      {"text": "Looked: the total is computed in shop.py."}]})
    body, tasks, calls, *_ = await _ask(cfg, "你好，结账总价不对，帮我查一下")
    assert "shop.py" in body["summary"] and any(c["type"] == "tool_call" for c in calls)


async def test_a_conversation_carries_its_earlier_turns(make_config):
    """新聊天: the second message of a conversation gets the first turn with it, like any chat; "好的" there is a
    go-ahead (work), not small talk."""
    cfg = make_config({"conv-model": [{"text": "The total is computed in shop.py; shall I fix it?"},
                                      {"text": "Fixed it as agreed."}]})
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        first = d.submit_task("doctor", "total", "Why is the total wrong?")
        await asyncio.wait_for(d.wait_for_report(first["task_id"]), 20)
        second = d.submit_task("doctor", "好的", "好的", chat_of=first["task_id"])
        await asyncio.wait_for(d.wait_for_report(second["task_id"]), 20)
        body = d.s.db.one("SELECT body FROM tasks WHERE id = ?", (second["task_id"],))["body"]
        request = [e for e in d.s.journal.read(task_id=second["task_id"]) if e["type"] == "model_request"][0]
        turns = d.chat_turns(first["task_id"])
    finally:
        await d.halt()
    import json

    body = json.loads(body)
    assert not body.get("chat") and body["chat_of"] == first["task_id"]
    assert body["history"] == [{"user": "Why is the total wrong?",
                                "assistant": "The total is computed in shop.py; shall I fix it?"}]
    sent = json.dumps(d.s.journal.original(request), ensure_ascii=False)
    assert "shall I fix it?" in sent  # the model saw the earlier turn
    assert [t["id"] for t in turns] == [first["task_id"], second["task_id"]]


async def test_a_busy_model_service_is_asked_again(make_config, monkeypatch):
    """A real run stopped on the first "429 concurrency limit" of a shared service: a busy service is asked again,
    with growing waits, before the task gives up."""
    from codedoctor.agents.runtime import AgentRuntime
    from codedoctor.models.base import ChatResult, ModelError
    from codedoctor.models.factory import ModelPool

    calls = []

    class Busy:
        provider = "fake"

        async def chat(self, *a, **k):
            calls.append(1)
            if len(calls) <= 3:
                raise ModelError("HTTP 429: model is at its concurrency limit", retryable=True, status=429)
            return ChatResult("answered after the rush", [], "stop", 10, 5)

        async def aclose(self):
            pass

    monkeypatch.setattr(ModelPool, "client", lambda self, eid: Busy())
    monkeypatch.setattr(AgentRuntime, "retry_delay_s", 0.01)
    cfg = make_config({"busy-model": [{"text": "unused"}]})
    body, *_ = await _ask(cfg, "Why is the total wrong?")
    assert body["outcome"] == "done" and "answered after the rush" in body["summary"] and len(calls) == 4
