"""Anthropic Messages API client (/v1/messages)."""

from __future__ import annotations

import httpx

from codedoctor.models import reasoning as thinking
from codedoctor.models.base import ChatMessage, ChatResult, LazyHTTP, ModelError, ToolCall, ToolSpec
from codedoctor.models.openai_compat import _status_error

API_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 8192


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, base_url: str, api_key: str | None, timeout_s: float, transport: httpx.AsyncBaseTransport | None = None):
        headers = {"anthropic-version": API_VERSION}
        if api_key:
            headers["x-api-key"] = api_key
        self._http = LazyHTTP(base_url=base_url, headers=headers, timeout=timeout_s, transport=transport)  # made on first use

    @staticmethod
    def _encode(messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        system = "\n\n".join(m.content or "" for m in messages if m.role == "system")
        out: list[dict] = []

        def push(role: str, block: dict) -> None:
            # Consecutive same-role turns are merged; tool results travel as user turns.
            if out and out[-1]["role"] == role:
                out[-1]["content"].append(block)
            else:
                out.append({"role": role, "content": [block]})

        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                push("user", {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content or ""})
            elif m.role == "assistant":
                for block in (m.reasoning or {}).get("thinking") or []:  # signed, given back unchanged (tool use)
                    push("assistant", block)
                if m.content:
                    push("assistant", {"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    push("assistant", {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
            else:
                push("user", {"type": "text", "text": m.content or ""})
                for i in m.images:
                    push("user", {"type": "image", "source": {"type": "base64", "media_type": i["mime"], "data": i["data"]}})
        return system, out

    async def chat(self, model, messages, tools, *, temperature=None, max_output_tokens=None, reasoning=None) -> ChatResult:
        system, msgs = self._encode(messages)
        think, max_tokens = thinking.anthropic_thinking(reasoning, max_output_tokens or DEFAULT_MAX_TOKENS)
        body: dict = {"model": model, "messages": msgs, "max_tokens": max_tokens}
        # prompt caching: Claude caches only up to marked blocks. Marked: the tools, the system prompt and the newest
        # message, so each request reads everything before its new part from the cache (about a tenth of the price)
        cache = {"type": "ephemeral"}
        if system:
            body["system"] = [{"type": "text", "text": system, "cache_control": cache}]
        if tools:
            body["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
            body["tools"][-1]["cache_control"] = cache
        if msgs and msgs[-1]["content"]:
            msgs[-1]["content"][-1] = {**msgs[-1]["content"][-1], "cache_control": cache}
        if think:
            body["thinking"] = think  # with thinking Claude takes no temperature
        elif temperature is not None:
            body["temperature"] = temperature
        try:
            resp = await self._http.post("/v1/messages", json=body)
        except httpx.HTTPError as e:
            raise ModelError(f"{type(e).__name__}: {e}", retryable=True) from e
        if resp.status_code != 200:
            raise _status_error(resp)
        try:
            data = resp.json()
            blocks = data["content"]
        except (ValueError, KeyError) as e:
            raise ModelError(f"malformed response: {resp.text[:300]}", retryable=True) from e
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        calls = [
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input") if isinstance(b.get("input"), dict) else {})
            for b in blocks
            if b.get("type") == "tool_use"
        ]
        usage = data.get("usage") or {}
        return ChatResult(
            text="".join(texts) or None,
            tool_calls=calls,
            finish=data.get("stop_reason") or "end_turn",
            # Claude counts cache reads and writes apart from input_tokens; all of it is input the budget counts
            input_tokens=(usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0),
            output_tokens=usage.get("output_tokens", 0),
            raw=data,
            cached_tokens=usage.get("cache_read_input_tokens") or 0,
            reasoning={"thinking": [b for b in blocks if b.get("type") in ("thinking", "redacted_thinking")]}
            if any(b.get("type") in ("thinking", "redacted_thinking") for b in blocks) else None,
        )

    async def list_models(self) -> list[str]:
        try:
            resp = await self._http.get("/v1/models")
        except httpx.HTTPError as e:
            raise ModelError(f"{type(e).__name__}: {e}", retryable=True) from e
        if resp.status_code != 200:
            raise _status_error(resp)
        return [m.get("id", "") for m in resp.json().get("data", [])]

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        raise ModelError("the Anthropic API has no embeddings endpoint; choose an OpenAI-compatible one for memory.embedding",
                         retryable=False)

    async def aclose(self) -> None:
        await self._http.aclose()
