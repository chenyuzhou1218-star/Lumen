"""Build one client per user-configured endpoint, with a concurrency limit per endpoint."""

from __future__ import annotations

import asyncio

import httpx

from codedoctor import secrets
from codedoctor.config import Endpoint, ProjectConfig
from codedoctor.models.anthropic import AnthropicClient
from codedoctor.models.base import ModelClient, ModelError
from codedoctor.models.openai_compat import OpenAICompatClient
from codedoctor.models.scripted import ScriptedClient


class MissingKeyClient:
    """Stand-in when the endpoint's key is not available: every call fails clearly, nothing is sent."""

    def __init__(self, endpoint: Endpoint):
        self.provider = endpoint.kind
        where = []
        if endpoint.api_key_env:
            where.append(f"environment variable {endpoint.api_key_env}")
        if endpoint.api_key_keyring:
            where.append("the Windows Credential Manager (set it in Lumen: 设置 → 服务与密钥)")
        self._msg = f"no API key for endpoint {endpoint.id!r}: not found in {' or '.join(where)}"

    async def chat(self, *a, **kw):
        raise ModelError(self._msg, retryable=False)

    async def list_models(self):
        raise ModelError(self._msg, retryable=False)

    async def embed(self, *a, **kw):
        raise ModelError(self._msg, retryable=False)

    async def aclose(self):
        pass


class EngineClient:
    """An 'engine' endpoint: the user's own Claude Code or Codex. Its agents hand whole investigations to it
    (AgentRuntime._run_task, codedoctor/engines.py); there is no chat API to call, so a direct call says so."""

    def __init__(self, endpoint: Endpoint):
        self.engine = endpoint.base_url.split(":", 1)[1]
        self.provider = "engine"
        self._msg = (f"{endpoint.name or self.engine} does whole investigations on its own; it cannot be asked a single "
                     "question - give this role a model from an API service (设置 → Agent 模型)")

    async def chat(self, *a, **kw):
        raise ModelError(self._msg, retryable=False)

    async def list_models(self):
        from codedoctor import engines

        return [m["id"] for m in engines.models(self.engine)]

    async def embed(self, *a, **kw):
        raise ModelError(self._msg, retryable=False)

    async def aclose(self):
        pass


def build_client(endpoint: Endpoint, transport: httpx.AsyncBaseTransport | None = None) -> ModelClient:
    if endpoint.kind == "scripted":
        return ScriptedClient(endpoint.base_url)
    if endpoint.kind == "engine":
        return EngineClient(endpoint)
    api_key = None
    if endpoint.api_key_env or endpoint.api_key_keyring:
        api_key = secrets.get_key(endpoint)
        if not api_key:
            return MissingKeyClient(endpoint)
    if endpoint.kind == "openai_compatible":
        return OpenAICompatClient(endpoint.base_url, api_key, endpoint.timeout_s, transport,
                                  text_tool_calls=endpoint.text_tool_calls, provider=endpoint.provider)
    if endpoint.kind == "anthropic":
        return AnthropicClient(endpoint.base_url, api_key, endpoint.timeout_s, transport)
    raise ValueError(f"unsupported endpoint kind {endpoint.kind!r}")


class ModelPool:
    """Clients and per-endpoint semaphores. Shared by all agents of a project."""

    def __init__(self, config: ProjectConfig, transport: httpx.AsyncBaseTransport | None = None):
        self.endpoints = config.endpoints
        self._transport = transport
        self._keys = {eid: self._key(ep) for eid, ep in config.endpoints.items()}
        self.clients: dict[str, ModelClient] = {eid: build_client(ep, transport) for eid, ep in config.endpoints.items()}
        self._limits = {eid: asyncio.Semaphore(ep.max_concurrency) for eid, ep in config.endpoints.items()}
        self._stale: list[ModelClient] = []

    @staticmethod
    def _key(ep: Endpoint) -> str | None:
        return secrets.get_key(ep) if ep.kind != "scripted" and (ep.api_key_env or ep.api_key_keyring) else None

    def client(self, endpoint_id: str) -> ModelClient:
        """The endpoint's client. A key saved or changed in the desktop while Code Doctor runs is used from the next
        request on (no restart), so "key saved" on the settings page is also what the agents get."""
        ep = self.endpoints[endpoint_id]
        if ep.kind != "scripted" and (ep.api_key_env or ep.api_key_keyring):
            key = self._key(ep)
            if key != self._keys.get(endpoint_id):
                self._keys[endpoint_id] = key
                self._stale.append(self.clients[endpoint_id])  # closed in aclose(); a request may still be using it
                self.clients[endpoint_id] = build_client(ep, self._transport)
        return self.clients[endpoint_id]

    def limit(self, endpoint_id: str) -> asyncio.Semaphore:
        return self._limits[endpoint_id]

    async def aclose(self) -> None:
        for c in [*self.clients.values(), *self._stale]:
            await c.aclose()
