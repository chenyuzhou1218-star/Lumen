"""/v1/chat/completions client: OpenAI, DeepSeek, Ollama, LM Studio, llama.cpp server, vLLM, ..."""

from __future__ import annotations

import json

import httpx

from codedoctor.models import reasoning as thinking, text_tools
from codedoctor.models.base import ChatMessage, ChatResult, LazyHTTP, ModelError, ToolCall, ToolSpec


def _status_error(resp: httpx.Response) -> ModelError:
    body = resp.text[:500]
    retryable = resp.status_code == 429 or resp.status_code >= 500
    return ModelError(f"HTTP {resp.status_code}: {body}", retryable=retryable, status=resp.status_code)


class OpenAICompatClient:
    provider = "openai_compatible"

    def __init__(self, base_url: str, api_key: str | None, timeout_s: float, transport: httpx.AsyncBaseTransport | None = None,
                 *, text_tool_calls: bool = True, provider: str = ""):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.text_tool_calls = text_tool_calls
        self.thinking_style = thinking.style(provider, base_url)
        self._no_thinking_fields: set[str] = set()  # models that rejected the thinking fields (asked again without)
        self._http = LazyHTTP(base_url=base_url, headers=headers, timeout=timeout_s, transport=transport)  # made on first use

    @staticmethod
    def _encode(messages: list[ChatMessage]) -> list[dict]:
        out = []
        for m in messages:
            if m.role == "tool":
                out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or ""})
            elif m.role == "assistant" and m.tool_calls:
                msg = {
                    "role": "assistant",
                    "content": m.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
                        for tc in m.tool_calls
                    ],
                }
                if m.reasoning and m.reasoning.get("reasoning_content"):
                    msg["reasoning_content"] = m.reasoning["reasoning_content"]  # DeepSeek: required back with tools
                out.append(msg)
            else:
                if m.images:  # vision models: text plus data-URL images
                    out.append({"role": m.role, "content": [{"type": "text", "text": m.content or ""}] + [
                        {"type": "image_url", "image_url": {"url": f"data:{i['mime']};base64,{i['data']}"}} for i in m.images]})
                else:
                    out.append({"role": m.role, "content": m.content or ""})
        return out

    async def chat(self, model, messages, tools, *, temperature=None, max_output_tokens=None, reasoning=None) -> ChatResult:
        body: dict = {"model": model, "messages": self._encode(messages), "stream": False}
        fields = {} if model in self._no_thinking_fields else thinking.openai_fields(self.thinking_style, reasoning)
        if tools:
            body["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]
        if temperature is not None:
            body["temperature"] = temperature
        if max_output_tokens is not None:
            body["max_tokens"] = max_output_tokens
        try:
            resp = await self._http.post("/chat/completions", json={**body, **fields})
            if resp.status_code != 200 and thinking.rejected(resp.status_code, resp.text, fields):
                self._no_thinking_fields.add(model)  # this model takes no thinking level here: never fail for it
                resp = await self._http.post("/chat/completions", json=body)
        except httpx.HTTPError as e:
            raise ModelError(f"{type(e).__name__}: {e}", retryable=True) from e
        if resp.status_code != 200:
            raise _status_error(resp)
        try:
            data = resp.json()
            choice = data["choices"][0]
            msg = choice["message"]
        except (ValueError, KeyError, IndexError) as e:
            raise ModelError(f"malformed response: {resp.text[:300]}", retryable=True) from e

        calls = []
        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function", {})
            raw_args = fn.get("arguments") or "{}"
            parse_error = None
            if isinstance(raw_args, dict):
                args = raw_args
            else:
                try:
                    args = json.loads(raw_args)
                    if not isinstance(args, dict):
                        args, parse_error = {}, "arguments must be a JSON object"
                except json.JSONDecodeError as e:
                    args, parse_error = {}, f"arguments are not valid JSON: {e}"
            calls.append(ToolCall(id=tc.get("id") or f"call_{i}", name=fn.get("name", ""), arguments=args, parse_error=parse_error))
        text = msg.get("content") or None
        if not calls and tools and self.text_tool_calls:
            calls, text = text_tools.extract(text, [t.name for t in tools])
        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            tool_calls=calls,
            finish=choice.get("finish_reason") or ("tool_calls" if calls else "stop"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            raw=data,
            # DeepSeek: prompt_cache_hit_tokens; OpenAI and most others: prompt_tokens_details.cached_tokens
            cached_tokens=usage.get("prompt_cache_hit_tokens") or (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0,
            reasoning={"reasoning_content": msg["reasoning_content"]} if msg.get("reasoning_content") else None,
        )

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """/v1/embeddings: one vector per text, in order."""
        try:
            resp = await self._http.post("/embeddings", json={"model": model, "input": texts})
        except httpx.HTTPError as e:
            raise ModelError(f"{type(e).__name__}: {e}", retryable=True) from e
        if resp.status_code != 200:
            raise _status_error(resp)
        try:
            rows = sorted(resp.json()["data"], key=lambda d: d.get("index", 0))
            vectors = [[float(x) for x in d["embedding"]] for d in rows]
        except (ValueError, KeyError, TypeError) as e:
            raise ModelError(f"malformed embeddings response: {resp.text[:300]}", retryable=False) from e
        if len(vectors) != len(texts):
            raise ModelError(f"asked for {len(texts)} embeddings, got {len(vectors)}", retryable=False)
        return vectors

    async def list_models(self) -> list[str]:
        try:
            resp = await self._http.get("/models")
        except httpx.HTTPError as e:
            raise ModelError(f"{type(e).__name__}: {e}", retryable=True) from e
        if resp.status_code != 200:
            raise _status_error(resp)
        return [m.get("id", "") for m in resp.json().get("data", [])]

    async def aclose(self) -> None:
        await self._http.aclose()
