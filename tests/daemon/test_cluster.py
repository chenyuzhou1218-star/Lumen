"""Multi-agent cluster: dispatch head, logic head, worker, guardian working on the sample project."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

import pytest

from codedoctor import config as config_mod
from codedoctor.agents import orchestration as orch
from codedoctor.agents.daemon import Daemon
from codedoctor.models import scripted

from conftest import unique_model

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "shop-coupling"


def last_evidence(messages) -> str:
    for m in reversed(messages):
        found = re.findall(r"evidence: (ev:code:\S+)", m.content or "")
        if found:
            return found[0]
    raise AssertionError("no evidence in conversation")


def cluster_config(tmp_path: Path, models: dict[str, str], *, guardian: bool = True) -> config_mod.ProjectConfig:
    root = tmp_path / "shop-coupling"
    if not root.exists():
        shutil.copytree(SAMPLE, root)
    agents = [
        {"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": models["dispatch"]},
        {"id": "head-logic", "role": "head_logic", "endpoint": "fake", "model": models["logic"]},
        {"id": "worker-1", "role": "worker", "endpoint": "fake", "model": models["worker"]},
    ]
    if guardian:
        agents.append({"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": models["guardian"], "supervises": "worker-1"})
    return config_mod.parse({
        "cd_schema": "cd.config.project/0",
        "project": {"name": "shop", "root": str(root), "data_dir": str(tmp_path / "data")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": agents,
        "defaults": {"budget": {"max_steps": 12}, "stall_steps": 4},
    })


def reconnect_claim(msgs):
    return {"tool_calls": [{"name": "submit_claim", "arguments": {"claim": {
        "claim_type": "hypothesis", "evidence_level": "inferred",
        "statement": {"text": "reconnect replays pending /api/match/settle requests, so a match reward can be paid twice",
                      "subject": "ent:symbol:shop:server/session.py#reconnect", "relation": "causes",
                      "object": "ent:state:shop:py/gold"},
        "scope": {"code_version": last_evidence(msgs).split(":")[2]},
        "evidence": [{"id": last_evidence(msgs), "role": "supports", "shows": "settle() is called again for pending requests",
                      "assert": [{"op": "text_contains", "text": "settle(pending, player)"}]}],
        "falsification": {"method": "test", "intervention": True,
                          "description": "settle a match, drop the response, reconnect, compare gold with the ledger"}}}}]}


def worker_script():
    # The worker is the hands (every project may change code): it reads and answers; it files no claims.
    return [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/session.py", "start_line": 5, "end_line": 12}}]},
        {"text": "reconnect() replays settle() for pending requests; add_gold has no idempotency key."},
    ]


def guardian_script():
    # The supervisor re-reads the code itself and states what its worker found.
    return [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/session.py", "start_line": 5, "end_line": 12}}]},
        reconnect_claim,
        {"text": "Re-read session.py myself: the loop calls settle() for every pending settle request. Also noticed: "
                 "spend_gold writes players and ledger without a transaction."},
    ]


async def run_cluster(cfg, instructions="Players report match rewards paid twice after reconnecting. Why?", timeout=20):
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("head-dispatch", "Double rewards", instructions)
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), timeout)
        return d, sub, report
    finally:
        await d.halt()


async def test_full_cluster_flow_with_guardian_review(tmp_path):
    """The user's rule: every project may change code (no read-only members), so the head gives each worker its files."""
    m = {k: unique_model(k) for k in ("dispatch", "logic", "worker", "guardian")}
    scripted.register(m["dispatch"], [
        {"tool_calls": [{"name": "consult", "arguments": {"question": "Which modules can pay a match reward twice?"}}]},
        {"tool_calls": [{"name": "delegate", "arguments": {
            "agent": "worker-1", "title": "Check reconnect replay",
            "instructions": "Read server/session.py and server/rewards.py; confirm whether reconnect can settle twice.",
            "files": ["server/session.py", "server/rewards.py"]}}]},
        {"tool_calls": [{"name": "wait_for", "arguments": {}}]},
        {"text": "Verified: reconnect replays settle() (claim supported after guardian re-check). Not covered: concurrency tests."},
    ])
    scripted.register(m["logic"], [
        {"tool_calls": [{"name": "graph_common_cause", "arguments": {"symptoms": ["/api/session/reconnect", "/api/match/settle"]}}]},
        {"tool_calls": [{"name": "graph_risks", "arguments": {"pattern": "retry_path_to_write"}}]},
        {"text": "Common path: reconnect -> settle -> add_gold writes py/gold and ledger with no idempotency key."},
    ])
    scripted.register(m["worker"], worker_script())
    scripted.register(m["guardian"], guardian_script())
    cfg = cluster_config(tmp_path, m)
    d, sub, report = await run_cluster(cfg)

    assert report["body"]["outcome"] == "done", report["body"]["summary"]
    kids = orch.children(d.s, sub["task_id"])
    assert [k["agent"] for k in kids] == ["head-logic", "worker-1", "guardian-1"]
    worker_task, review_task = kids[1], kids[2]
    assert orch.body_of(review_task)["review_of"] == worker_task["id"]
    # the guardian sees the whole request, not just the title (it once reported a task as cut off)
    assert "confirm whether reconnect can settle twice" in orch.body_of(review_task)["instructions"]
    assert all(k["state"] == "finished" for k in kids)

    assert not d.s.claims.by_task(worker_task["id"])  # the hands file no claims
    [claim] = d.s.claims.by_task(review_task["id"])
    assert claim["author"]["id"] == "guardian-1" and "settle" in claim["statement"]["text"]

    logic_calls = d.s.models.client("fake").calls
    last_tool = lambda call: [x for x in call["messages"] if x.role == "tool"][-1].content  # noqa: E731
    logic_results = last_tool([c for c in logic_calls if c["model"] == m["logic"]][1])
    assert "ent:state:shop:py/gold" in logic_results  # the graph found the shared gold state

    dispatch_last = last_tool([c for c in logic_calls if c["model"] == m["dispatch"]][-1])
    assert "guardian-1" in dispatch_last and "Re-read session.py myself" in dispatch_last  # wait_for showed the review
    assert d.s.graph.meta()["files"] == 13


async def test_logic_head_objection_blocks_delivery(tmp_path):
    m = {k: unique_model(k) for k in ("dispatch", "logic", "worker", "guardian")}
    scripted.register(m["dispatch"], [
        {"tool_calls": [{"name": "consult", "arguments": {"question": "Is it safe to ship?"}}]},
        # the unchecked detail checklist sends the head back twice (ADR 0014); it keeps its answer
        *[{"text": "Ship it."}] * 3,
    ])
    scripted.register(m["logic"], [
        {"tool_calls": [{"name": "raise_objection", "arguments": {
            "text": "retryFetch retries /api/shop/buy and nothing on that path is idempotent; untested."}}]},
        {"text": "Not safe: see objection."},
    ])
    cfg = cluster_config(tmp_path, m)
    d, sub, report = await run_cluster(cfg)
    assert report["body"]["outcome"] == "blocked"
    assert "Ship it." in report["body"]["summary"] and "retryFetch" in report["body"]["summary"]
    esc = [x for x in d.s.bus.list(task_id=sub["task_id"]) if x["kind"] == "escalation"]
    assert esc and esc[0]["body"]["reason"] == "head_disagreement" and esc[0]["to"] == "user"


async def test_delegation_rules(tmp_path):
    """The user's rule: every project may change code (no read-only members), so the head gives each worker its files."""
    m = {k: unique_model(k) for k in ("dispatch", "logic", "worker", "guardian")}
    same = {"agent": "worker-1", "title": "Same", "instructions": "Do the same thing", "files": ["server/shop.py"]}
    scripted.register(m["dispatch"], [
        {"tool_calls": [{"name": "delegate", "arguments": {"agent": "guardian-1", "title": "x", "instructions": "y"}}]},
        {"tool_calls": [{"name": "delegate", "arguments": same}, {"name": "delegate", "arguments": same}]},
        {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 10}}]},
        {"text": "done"},
    ])
    scripted.register(m["worker"], [{"text": "nothing found"}])
    scripted.register(m["guardian"], [{"text": "nothing to review"}])
    cfg = cluster_config(tmp_path, m)
    d, sub, report = await run_cluster(cfg)
    results = [e for e in d.s.journal.read(task_id=sub["task_id"]) if e["type"] == "tool_result"]
    texts = [d.s.journal.original(e)["payload"] for e in results]
    assert "is not a worker" in texts[0]
    assert texts[1].startswith("delegated") and "duplicate work" in texts[2]
    assert len([k for k in orch.children(d.s, sub["task_id"]) if k["agent"] == "worker-1"]) == 1


async def test_cancelling_the_root_cancels_subtasks(tmp_path):
    """The user's rule: every project may change code (no read-only members), so the head gives each worker its files."""
    m = {k: unique_model(k) for k in ("dispatch", "logic", "worker", "guardian")}
    scripted.register(m["dispatch"], [
        {"tool_calls": [{"name": "delegate", "arguments": {"agent": "worker-1", "title": "slow", "instructions": "read everything",
                                                         "files": ["server/app.py"]}}]},
        {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 60}}]},
        {"text": "should not get here"},
    ])
    scripted.register(m["worker"], [{"tool_calls": [{"name": "list_dir", "arguments": {"path": f"{p}"}}]} for p in
                                    ["server", "web", ".", "server", "web", "."] * 3])
    cfg = cluster_config(tmp_path, m, guardian=False)
    d = Daemon(cfg, poll_s=0.05)
    real = d.s.models.client("fake").chat

    async def slow(model, *a, **kw):
        if model == m["worker"]:
            await asyncio.sleep(0.15)
        return await real(model, *a, **kw)

    d.s.models.client("fake").chat = slow
    await d.start()
    try:
        sub = d.submit_task("head-dispatch", "t", "go")
        for _ in range(200):
            kids = orch.children(d.s, sub["task_id"])
            if kids and kids[0]["state"] == "running":
                break
            await asyncio.sleep(0.02)
        d.control("head-dispatch", "cancel_task", task_id=sub["task_id"])
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
        for _ in range(200):
            if orch.children(d.s, sub["task_id"])[0]["state"] == "finished":
                break
            await asyncio.sleep(0.02)
    finally:
        await d.halt()
    assert report["body"]["outcome"] == "cancelled"
    assert orch.children(d.s, sub["task_id"])[0]["outcome"] == "cancelled"


def test_guardian_must_supervise_a_worker(tmp_path):
    with pytest.raises(config_mod.ConfigError, match="not a configured worker"):
        config_mod.parse({
            "cd_schema": "cd.config.project/0", "project": {"name": "x", "root": str(tmp_path)},
            "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
            "agents": [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": "m"},
                       {"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": "m", "supervises": "head-dispatch"}]})


def test_subtask_is_committed_before_worker_is_notified(make_config):
    """Task and message commit atomically; even an immediate worker sees its row."""
    from codedoctor.agents.runtime import AgentRuntime
    from codedoctor.services import Services

    cfg = make_config()
    s = Services.open(cfg)
    try:
        worker = AgentRuntime(cfg.agents["doctor"], s, set(cfg.agents))
        real_notify = s.bus.notify

        def notify_and_start_at_once(recipient):
            msg = s.bus.next_for(recipient)
            assert orch.task_row(s, msg["body"]["task_id"])["state"] == "queued"
            worker._begin_task(msg, msg["body"])
            s.bus.mark_delivered(msg["id"])
            real_notify(recipient)

        s.bus.notify = notify_and_start_at_once
        parent = orch.create_subtask(s, sender="user", recipient="doctor", title="root", instructions="go", parent_task_id=None)
        sub = orch.create_subtask(s, sender="doctor", recipient="doctor", title="t", instructions="x", parent_task_id=parent["task_id"])
        row = orch.task_row(s, sub["task_id"])
        assert row["state"] == "running" and row["parent_task_id"] == parent["task_id"]
    finally:
        s.db.close()
