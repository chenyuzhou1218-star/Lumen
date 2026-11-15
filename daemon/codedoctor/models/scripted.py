"""Deterministic fake model for tests and offline demos.

A script is a list of turns per model name. Each turn is one of:
  {"text": "..."}                                         final answer
  {"tool_calls": [{"name": "read_file", "arguments": {...}}]}
  {"error": "...", "retryable": true}                     simulate a failure
  callable(messages) -> one of the above                 (in-process scripts only)
When the script runs out, the model answers "(script exhausted)".

base_url "scripted:" uses scripts registered in-process (tests);
"scripted:<path>" loads {"<model>": [turns...]} from a JSON file.

Embeddings: register_embedder(model, fn) with fn(text) -> vector, or fn raising ModelError to
simulate an outage. An unregistered embedding model is an error, like an unregistered chat model.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Callable

from codedoctor.models.base import ChatResult, ModelError, ToolCall

_REGISTERED: dict[str, list[dict]] = {}
_EMBEDDERS: dict[str, Callable[[str], list[float]]] = {}


def register(model: str, turns: list[dict]) -> None:
    _REGISTERED[model] = list(turns)


def register_embedder(model: str, fn: Callable[[str], list[float]]) -> None:
    _EMBEDDERS[model] = fn


class ScriptedClient:
    provider = "scripted"

    def __init__(self, base_url: str):
        path = base_url.removeprefix("scripted:")
        self._scripts = json.loads(Path(path).read_text(encoding="utf-8")) if path else _REGISTERED
        self._pos: dict[str, int] = {}
        self.calls: list[dict] = []  # what the agent sent, for inspection in tests
        self.embed_calls: list[dict] = []

    async def chat(self, model, messages, tools, *, temperature=None, max_output_tokens=None, reasoning=None) -> ChatResult:
        # copies: the runtime later elides old messages in place, and a record must show what was sent at the time
        self.calls.append({"model": model, "messages": [copy.copy(m) for m in messages], "tools": [t.name for t in tools],
                           "reasoning": reasoning})
        turns = self._scripts.get(model)
        if turns is None:
            raise ModelError(f"no script for model {model!r}", retryable=False, status=404)
        i = self._pos.get(model, 0)
        self._pos[model] = i + 1
        if i >= len(turns):
            return ChatResult(text="(script exhausted)", tool_calls=[], finish="stop")
        turn = turns[i]
        if callable(turn):  # in-process scripts may compute a turn from the conversation (e.g. cite an evidence id)
            turn = turn(messages)
        if turn.get("wait_s"):  # a slow service: the answer takes this long (the loop keeps running meanwhile)
            import asyncio

            await asyncio.sleep(turn["wait_s"])
        if "error" in turn:
            raise ModelError(turn["error"], retryable=turn.get("retryable", False), status=turn.get("status"))
        calls = [
            ToolCall(id=f"call_{i}_{j}", name=c["name"], arguments=c.get("arguments", {}))
            for j, c in enumerate(turn.get("tool_calls", []))
        ]
        approx_in = sum(len(m.content or "") for m in messages) // 4
        return ChatResult(
            text=turn.get("text"),
            tool_calls=calls,
            finish="tool_calls" if calls else "stop",
            input_tokens=turn.get("input_tokens", approx_in),
            output_tokens=turn.get("output_tokens", 50),
        )

    async def list_models(self) -> list[str]:
        return sorted(self._scripts)

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        fn = _EMBEDDERS.get(model)
        if fn is None:
            raise ModelError(f"no embedder for model {model!r}", retryable=False, status=404)
        self.embed_calls.append({"model": model, "texts": list(texts)})
        return [list(fn(t)) for t in texts]

    async def aclose(self) -> None:
        pass
