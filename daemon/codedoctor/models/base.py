"""Provider-neutral chat interface used by the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema object


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    parse_error: str | None = None  # the model sent arguments that are not a JSON object


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # tool name, for role == tool
    # an assistant turn's thinking as the provider must get it back with tool calls (models/reasoning.py):
    # {"reasoning_content": str} (DeepSeek and others) or {"thinking": [signed blocks]} (Anthropic)
    reasoning: dict | None = None
    # user messages only: [{"evidence": id, "mime": "image/png", "data": base64}] (screenshots, ADR 0012)
    images: list[dict] = field(default_factory=list)


@dataclass
class ChatResult:
    text: str | None
    tool_calls: list[ToolCall]
    finish: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: Any = None
    cached_tokens: int = 0
    reasoning: dict | None = None  # the turn's thinking, to be given back (see ChatMessage.reasoning)  # of input_tokens, served from the provider's prompt cache (billed far lower)


class ModelError(Exception):
    """A model call failed. `retryable` errors may be retried on the same model;
    switching to another model is only ever done through the user's fallback list."""

    def __init__(self, message: str, *, retryable: bool, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


class LazyHTTP:
    """An httpx.AsyncClient made on its first request: making one loads the system's certificates (0.7 s on a slow
    machine, per service), which must not hold up opening a project before any model has been asked anything."""

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._client = None

    def _get(self):
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(**self._kwargs)
        return self._client

    async def post(self, *args, **kwargs):
        return await self._get().post(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return await self._get().get(*args, **kwargs)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()


class ModelClient(Protocol):
    provider: str

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        reasoning: str | None = None,  # 思考强度: off / low / medium / high / max (models/reasoning.py); None: default
    ) -> ChatResult: ...

    async def list_models(self) -> list[str]: ...

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """One vector per text (semantic memory, ADR 0007). Raises ModelError if the provider has none."""
        ...

    async def aclose(self) -> None: ...
