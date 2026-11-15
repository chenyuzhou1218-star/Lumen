"""Safety regression tests for Claude commit 4a74a7d (no production edits). Written by ChatGPT; R4 updated by Claude.

Run with the repository's daemon/ on PYTHONPATH. Every HTTP request is captured
by httpx.MockTransport: no actual model, network, API key, or real secret.
Failures describe required safety properties, not successful fixes.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from codedoctor import ids
from codedoctor.agents.daemon import Daemon
from codedoctor.config import parse
from codedoctor.memory.notes import MemoryError_

SENTINEL = "review-sentinel-NOT-A-REAL-SECRET"


class Wire:
    def __init__(self, turns=None):
        self.turns = list(turns or [{"content": "finished"}])
        self.requests = []

    def __call__(self, request):
        import json
        body = json.loads(request.content)
        self.requests.append(body)
        turn = self.turns[min(len(self.requests) - 1, len(self.turns) - 1)]
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", **turn},
                         "finish_reason": "tool_calls" if turn.get("tool_calls") else "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        })


def call(name, args):
    import json
    return {"id": "call_review", "type": "function", "function": {
        "name": name, "arguments": json.dumps(args),
    }}


def configuration(tmp_path, *, recall_k=8, local=False, code_class="internal", agents=None):
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    return parse({
        "cd_schema": "cd.config.project/0",
        "project": {"name": "runtime-review", "root": str(root),
                    "data_dir": str(tmp_path / "state"), "code_data_class": code_class},
        "endpoints": [{"id": "chosen", "kind": "openai_compatible",
                       "base_url": "https://review.invalid/v1", "local": local}],
        "agents": agents or [{"id": "doctor", "role": "general", "endpoint": "chosen",
                              "model": "user-chosen", "memory": {"recall_k": recall_k}}],
    }, base_dir=tmp_path)


def seed_note(d):
    src = d.s.journal.append("doctor", "tool_result", {"ok": True}, payload=SENTINEL)
    return d.s.notes.write(owner="doctor", scope="agent", kind="fact",
                           text="settlement diagnostic " + SENTINEL,
                           sources=[src["id"]], data_class="local_only")


def has_secret(wire):
    return any(SENTINEL in str(r["messages"]) for r in wire.requests)


@pytest.mark.asyncio
async def test_control_direct_classification_blocks_remote_request(tmp_path):
    """Positive control: direct task taint is already enforced."""
    wire = Wire()
    d = Daemon(configuration(tmp_path), transport=httpx.MockTransport(wire))
    try:
        sub = d.submit_task("doctor", "settlement", SENTINEL, data_class="local_only")
        await d.agents["doctor"].step()
        assert not wire.requests
        assert d.task(sub["task_id"])["outcome"] == "blocked"
    finally:
        await d.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_recall", [True, False], ids=["startup-recall", "recall-tool"])
async def test_R1_memory_classification_survives_recall(tmp_path, initial_recall):
    wire = Wire() if initial_recall else Wire([
        {"content": None, "tool_calls": [call("recall", {"query": "settlement"})]},
        {"content": "finished"},
    ])
    d = Daemon(configuration(tmp_path, recall_k=8 if initial_recall else 0),
               transport=httpx.MockTransport(wire))
    try:
        seed_note(d)
        sub = d.submit_task("doctor", "settlement", "Explain settlement.")
        await d.agents["doctor"].step()
        assert not has_secret(wire), (
            f"local_only note sent to remote internal-only endpoint; "
            f"calls={len(wire.requests)}, outcome={d.task(sub['task_id'])['outcome']}"
        )
    finally:
        await d.stop()


@pytest.mark.asyncio
async def test_R1_summary_retains_task_classification(tmp_path):
    wire = Wire([{"content": SENTINEL}])
    cfg = configuration(tmp_path, local=True)
    d = Daemon(cfg, transport=httpx.MockTransport(wire))
    try:
        sub = d.submit_task("doctor", "settlement", "Summarize settlement", data_class="local_only")
        await d.agents["doctor"].step()
        notes = d.s.notes.by_task(sub["task_id"])
        assert notes and notes[0].get("data_class") == "local_only", notes
    finally:
        await d.stop()


@pytest.mark.asyncio
async def test_R1_message_retains_task_classification(tmp_path):
    wire = Wire([
        {"content": None, "tool_calls": [call("send_message", {"to": "other", "text": SENTINEL})]},
        {"content": "finished"},
    ])
    agents = [{"id": name, "role": "general", "endpoint": "chosen", "model": "user-chosen"}
              for name in ("doctor", "other")]
    d = Daemon(configuration(tmp_path, local=True, agents=agents), transport=httpx.MockTransport(wire))
    try:
        d.submit_task("doctor", "settlement", "Ask other agent", data_class="local_only")
        await d.agents["doctor"].step()
        question = next(m for m in d.s.bus.list(recipient="other") if m["kind"] == "question")
        assert question.get("data_class") == "local_only", question
    finally:
        await d.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("with_tool", [False, True], ids=["final-answer", "late-tool"])
async def test_R2_cancel_while_model_pending_is_respected(tmp_path, with_tool):
    turns = [{"content": None, "tool_calls": [call("read_file", {"path": "probe.txt"})]}] if with_tool else [{"content": "finished"}]
    wire = Wire(turns)
    cfg = configuration(tmp_path)
    (cfg.root / "probe.txt").write_text("harmless test data\n", encoding="utf-8")
    d = Daemon(cfg, transport=httpx.MockTransport(wire))
    pending = None
    entered, release = asyncio.Event(), asyncio.Event()
    original = d.s.models.client("chosen").chat

    async def gated(*args, **kw):
        entered.set()
        await release.wait()
        return await original(*args, **kw)

    d.s.models.client("chosen").chat = gated
    try:
        sub = d.submit_task("doctor", "cancel test", "inspect probe")
        pending = asyncio.create_task(d.agents["doctor"].step())
        await asyncio.wait_for(entered.wait(), 2)
        d.control("doctor", "cancel_task", task_id=sub["task_id"])
        release.set()
        await asyncio.wait_for(pending, 2)
        task = d.task(sub["task_id"])
        tools = [e for e in d.s.journal.read(task_id=sub["task_id"]) if e["type"] == "tool_call"]
        assert task["outcome"] == "cancelled" and not tools, (
            f"outcome={task['outcome']}, tool_calls_after_cancellation={len(tools)}"
        )
    finally:
        if pending and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await d.stop()


@pytest.mark.asyncio
async def test_R3_restart_does_not_orphan_running_task(tmp_path):
    wire = Wire()
    cfg = configuration(tmp_path)
    d = Daemon(cfg, transport=httpx.MockTransport(wire))
    entered = asyncio.Event()

    async def blocked(*args, **kw):
        entered.set()
        await asyncio.Event().wait()

    d.s.models.client("chosen").chat = blocked
    await d.start()
    sub = d.submit_task("doctor", "restart test", "inspect settlement")
    try:
        await asyncio.wait_for(entered.wait(), 2)
    finally:
        await d.stop()  # same shutdown method used by FastAPI lifespan
    reopened = Daemon(cfg, transport=httpx.MockTransport(wire), poll_s=0.01)
    await reopened.start()
    try:
        # A new task completes, proving the restarted consumer is live, not just slow.
        heartbeat = reopened.submit_task("doctor", "heartbeat", "respond once")
        await reopened.wait_for_report(heartbeat["task_id"], timeout_s=2)
        abandoned = reopened.task(sub["task_id"])
        undelivered = reopened.s.bus.next_for("doctor")
        assert abandoned["state"] != "running" or undelivered is not None, (
            f"old task stays {abandoned['state']} with outcome={abandoned['outcome']}; "
            f"no retry message, new task={reopened.task(heartbeat['task_id'])['outcome']}"
        )
    finally:
        await reopened.stop()


@pytest.mark.asyncio
async def test_R4_compacted_request_is_reconstructible_from_journal(tmp_path):
    """Updated by Claude for ADR 0008: the journal now records each request as its new messages plus the earlier
    messages elision rewrote ("rewritten"), and the working memory separately. Elision is forced with a small
    budget (tool output is sized to the budget, so large reads no longer need elision by themselves). Every
    request, not only the last, must be rebuilt exactly."""
    import re
    from dataclasses import replace

    wire = Wire([
        {"content": None, "tool_calls": [call("read_file", {"path": "first.txt"})]},
        {"content": None, "tool_calls": [call("read_file", {"path": "second.txt"})]},
        {"content": None, "tool_calls": [call("read_file", {"path": "third.txt"})]},
        {"content": "finished"},
    ])
    cfg = configuration(tmp_path)
    from test_context import TOOLS  # the tool descriptions and system prompt, measured (computer use is on for every project)

    cfg = replace(cfg, agents={"doctor": replace(cfg.agents["doctor"], context_budget_tokens=TOOLS + 3300)})
    for name, ch in (("first.txt", "a"), ("second.txt", "b"), ("third.txt", "c")):
        (cfg.root / name).write_text((ch * 200 + "\n") * 350, encoding="utf-8")
    d = Daemon(cfg, transport=httpx.MockTransport(wire))
    try:
        sub = d.submit_task("doctor", "journal replay", "Inspect the three files")
        await d.agents["doctor"].step()
        assert d.task(sub["task_id"])["outcome"] == "done"
        assert any(m.get("content", "").startswith("(elided") for r in wire.requests for m in r["messages"])
        convo = []
        requests = [d.s.journal.original(e)["payload"] for e in d.s.journal.read(task_id=sub["task_id"]) if e["type"] == "model_request"]
        assert len(requests) == len(wire.requests) == 4
        for payload, actual in zip(requests, wire.requests):
            for i, content in payload.get("rewritten", {}).items():
                convo[int(i)]["content"] = content
            convo += payload["messages"]
            sent = actual["messages"][:-1] if "working_memory" in payload else actual["messages"]
            assert [(m["role"], m.get("content") or "") for m in convo] == [(m["role"], m.get("content") or "") for m in sent]
            if "working_memory" in payload:
                assert actual["messages"][-1]["content"] == payload["working_memory"]
    finally:
        await d.stop()


@pytest.mark.asyncio
async def test_R5_context_budget_applies_to_unelidable_input(tmp_path):
    wire = Wire()
    cfg = configuration(tmp_path)
    # Use valid configuration to select the smallest allowed context budget.
    from dataclasses import replace
    a = replace(cfg.agents["doctor"], context_budget_tokens=1024)
    cfg = replace(cfg, agents={"doctor": a})
    d = Daemon(cfg, transport=httpx.MockTransport(wire))
    try:
        d.submit_task("doctor", "budget test", "X" * 40000)
        await d.agents["doctor"].step()
        # Even using implementation's own 3 chars/token estimate, it is far over.
        sizes = [sum(len(m.get("content") or "") for m in r["messages"]) for r in wire.requests]
        assert all(n <= 1024 * 3 for n in sizes), f"budget=3072 estimated chars, sent={sizes}"
    finally:
        await d.stop()


@pytest.mark.asyncio
async def test_R6_note_sources_must_resolve_to_originals(tmp_path):
    d = Daemon(configuration(tmp_path), transport=httpx.MockTransport(Wire()))
    ghost = ids.new_id("jrn")
    try:
        assert d.s.journal.get(ghost) is None
        with pytest.raises(MemoryError_, match="."):
            d.s.notes.write(owner="doctor", scope="agent", kind="summary",
                             text="A summary with a nonexistent source.", sources=[ghost])
    finally:
        await d.stop()
