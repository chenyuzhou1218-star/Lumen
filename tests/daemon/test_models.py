from __future__ import annotations

import json

import httpx
import pytest

from codedoctor.config import Endpoint
from codedoctor.models.anthropic import AnthropicClient
from codedoctor.models.base import ChatMessage, ModelError, ToolCall, ToolSpec
from codedoctor.models.factory import build_client
from codedoctor.models.openai_compat import OpenAICompatClient

TOOLS = [ToolSpec("read_file", "Read a file", {"type": "object", "properties": {"path": {"type": "string"}}})]
CONVO = [
    ChatMessage("system", "be careful"),
    ChatMessage("user", "why?"),
    ChatMessage("assistant", None, [ToolCall("c1", "read_file", {"path": "a.py"})]),
    ChatMessage("tool", "file contents", tool_call_id="c1", name="read_file"),
]


def _transport(handler):
    seen = []

    def h(request: httpx.Request):
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(h), seen


async def test_openai_compatible_request_and_tool_call_parsing():
    def handler(req):
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
                {"id": "x9", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": \"b.py\"}"}},
                {"id": "x10", "type": "function", "function": {"name": "read_file", "arguments": "not json"}},
            ]}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "prompt_cache_hit_tokens": 96},  # DeepSeek's field
        })

    transport, seen = _transport(handler)
    client = OpenAICompatClient("http://127.0.0.1:11434/v1", "k-123", 10, transport)
    res = await client.chat("qwen3:8b", CONVO, TOOLS, temperature=0.1, max_output_tokens=100)
    await client.aclose()

    req = seen[0]
    assert req.url.path == "/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer k-123"
    body = json.loads(req.content)
    assert body["model"] == "qwen3:8b" and body["max_tokens"] == 100 and body["temperature"] == 0.1
    assert body["tools"][0]["function"]["name"] == "read_file"
    assert body["messages"][2]["tool_calls"][0]["function"]["arguments"] == "{\"path\": \"a.py\"}"
    assert body["messages"][3] == {"role": "tool", "tool_call_id": "c1", "content": "file contents"}

    assert res.tool_calls[0].arguments == {"path": "b.py"}
    assert res.tool_calls[1].parse_error and res.tool_calls[1].arguments == {}
    assert (res.input_tokens, res.output_tokens, res.cached_tokens) == (120, 30, 96)


@pytest.mark.parametrize("status,retryable", [(500, True), (503, True), (429, True), (401, False), (404, False)])
async def test_openai_compatible_error_classes(status, retryable):
    transport, _ = _transport(lambda req: httpx.Response(status, text="nope"))
    client = OpenAICompatClient("http://x/v1", None, 10, transport)
    with pytest.raises(ModelError) as ei:
        await client.chat("m", CONVO, TOOLS)
    assert ei.value.retryable is retryable and ei.value.status == status


async def test_connection_failure_is_retryable():
    def handler(req):
        raise httpx.ConnectError("refused")

    transport, _ = _transport(handler)
    client = OpenAICompatClient("http://x/v1", None, 10, transport)
    with pytest.raises(ModelError) as ei:
        await client.chat("m", CONVO, TOOLS)
    assert ei.value.retryable


async def test_anthropic_request_and_response_conversion():
    def handler(req):
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "checking"},
                        {"type": "tool_use", "id": "tu1", "name": "read_file", "input": {"path": "c.py"}}],
            "stop_reason": "tool_use", "usage": {"input_tokens": 50, "output_tokens": 9},
        })

    transport, seen = _transport(handler)
    client = AnthropicClient("https://api.anthropic.com", "sk-ant", 10, transport)
    res = await client.chat("claude-sonnet-5-5", CONVO, TOOLS)
    await client.aclose()

    req = seen[0]
    assert req.url.path == "/v1/messages"
    assert req.headers["x-api-key"] == "sk-ant" and req.headers["anthropic-version"]
    body = json.loads(req.content)
    # prompt caching (Claude caches up to marked blocks): the system prompt, the last tool and the newest message
    assert body["system"] == [{"type": "text", "text": "be careful", "cache_control": {"type": "ephemeral"}}]
    assert body["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    assert body["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert body["tools"][0]["input_schema"]["properties"]["path"]["type"] == "string"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert body["messages"][1]["content"][0] == {"type": "tool_use", "id": "c1", "name": "read_file", "input": {"path": "a.py"}}
    assert body["messages"][2]["content"][0]["type"] == "tool_result"
    assert res.text == "checking" and res.tool_calls[0].arguments == {"path": "c.py"}
    assert (res.input_tokens, res.output_tokens) == (50, 9)


async def test_missing_key_never_sends_anything(monkeypatch):
    monkeypatch.delenv("CD_TEST_KEY", raising=False)
    transport, seen = _transport(lambda req: httpx.Response(200, json={}))
    ep = Endpoint(id="remote", kind="openai_compatible", base_url="https://api.example.com/v1", local=False, api_key_env="CD_TEST_KEY")
    client = build_client(ep, transport)
    with pytest.raises(ModelError) as ei:
        await client.chat("m", CONVO, TOOLS)
    assert "CD_TEST_KEY" in str(ei.value) and not ei.value.retryable
    assert seen == []


async def test_thinking_level_reaches_each_provider_in_its_own_words():
    from codedoctor.models import reasoning

    assert reasoning.openai_fields("deepseek", "high") == {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
    assert reasoning.openai_fields("deepseek", "off") == {"thinking": {"type": "disabled"}}
    assert reasoning.openai_fields("gemini", "off") == {"reasoning_effort": "none"}
    assert reasoning.openai_fields("qwen", "medium") == {"enable_thinking": True, "thinking_budget": 8192}
    assert reasoning.openai_fields("openrouter", "low") == {"reasoning": {"effort": "low"}}
    assert reasoning.openai_fields("openai", None) == {}  # not set: the provider's default, nothing sent
    assert reasoning.style("", "https://api.deepseek.com/v1") == "deepseek"
    assert reasoning.style("dashscope", "https://x") == "qwen"


async def test_a_thinking_turn_is_given_back_and_a_rejected_level_is_dropped_not_failed():
    sent = []

    def handler(req):
        body = json.loads(req.content)
        sent.append(body)
        if "reasoning_effort" in body:
            return httpx.Response(400, json={"error": {"message": "Unrecognized request argument: reasoning_effort"}})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": "ok", "reasoning_content": "let me think"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}})

    transport, _ = _transport(handler)
    client = OpenAICompatClient("http://127.0.0.1:1234/v1", None, 10, transport)  # a local server: the common way
    res = await client.chat("m", CONVO, TOOLS, reasoning="high")
    assert res.text == "ok" and res.reasoning == {"reasoning_content": "let me think"}
    assert "reasoning_effort" in sent[0] and "reasoning_effort" not in sent[1]  # asked again without it
    await client.chat("m", CONVO, TOOLS, reasoning="high")
    assert "reasoning_effort" not in sent[2]  # remembered: not sent to this model again
    # DeepSeek: with tools, every earlier turn's reasoning_content must go back
    turn = ChatMessage("assistant", "", [ToolCall("t1", "read_file", {"path": "a"})], reasoning=res.reasoning)
    assert OpenAICompatClient._encode([turn])[0]["reasoning_content"] == "let me think"
    await client.aclose()


async def test_claude_thinking_gets_a_budget_and_its_signed_blocks_go_back():
    def handler(req):
        return httpx.Response(200, json={"content": [
            {"type": "thinking", "thinking": "hmm", "signature": "sig1"},
            {"type": "tool_use", "id": "tu1", "name": "read_file", "input": {"path": "c.py"}}],
            "stop_reason": "tool_use", "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 9}})

    transport, seen = _transport(handler)
    client = AnthropicClient("https://api.anthropic.com", "k", 10, transport)
    res = await client.chat("claude", CONVO, TOOLS, temperature=0.2, max_output_tokens=1000, reasoning="medium")
    body = json.loads(seen[0].content)
    assert body["thinking"] == {"type": "enabled", "budget_tokens": 8192} and body["max_tokens"] == 9192
    assert "temperature" not in body  # not allowed with thinking
    assert (res.input_tokens, res.cached_tokens) == (100, 90)  # cache reads count as input; 90 of them cheap
    turn = ChatMessage("assistant", None, res.tool_calls, reasoning=res.reasoning)
    _, msgs = AnthropicClient._encode([ChatMessage("user", "x"), turn])
    assert msgs[1]["content"][0] == {"type": "thinking", "thinking": "hmm", "signature": "sig1"}
    await client.aclose()
