"""Hard requirement 5: interrupted tasks, the side-effect ledger, and resuming without repeating effects."""

from __future__ import annotations

import asyncio

from codedoctor.agents.daemon import Daemon
from codedoctor.agents.tools import TOOLS
from codedoctor.models import scripted

from conftest import unique_model


def _crash(ctx, args):
    # Simulates the process dying in the middle of a command: the exception is not an
    # Exception, so nothing in the runtime gets to record a result.
    raise asyncio.CancelledError()


async def _crash_during_command(make_config, monkeypatch):
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py", "start_line": 1, "end_line": 3}}]},
        {"tool_calls": [{"name": "run_command", "arguments": {"command": "python migrate.py --apply"}}]},
    ]}, permissions={"run_command": "allowlist", "command_allowlist": ["python migrate.py"]})  # a denied tool is not offered
    monkeypatch.setattr(TOOLS["run_command"], "handler", _crash)
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    sub = d.submit_task("doctor", "migrate", "apply the migration")
    for _ in range(200):
        effects = d.s.effects.for_task(sub["task_id"])
        if effects and d._loops[0].done():
            break
        await asyncio.sleep(0.02)
    await d.halt()
    monkeypatch.undo()
    return cfg, model, sub, d


async def test_crash_leaves_effect_in_intent_and_task_running(make_config, monkeypatch):
    cfg, model, sub, d = await _crash_during_command(make_config, monkeypatch)
    assert d.task(sub["task_id"])["state"] == "running"
    [eff] = d.s.effects.for_task(sub["task_id"])
    assert (eff["tool"], eff["state"], eff["effect_class"], eff["retry_safe"]) == ("run_command", "intent", "external", False)
    await d.s.aclose()


async def test_restart_reports_interrupted_with_unknown_effects(make_config, monkeypatch):
    cfg, model, sub, old = await _crash_during_command(make_config, monkeypatch)
    await old.s.aclose()

    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        assert d.recovered["doctor"] == [sub["task_id"]]
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 5)
    finally:
        await d.halt()
    body = report["body"]
    assert body["outcome"] == "interrupted"
    assert "UNKNOWN" in body["summary"] and "NOT safe to retry" in body["summary"] and "resume_task" in body["summary"]
    assert body["evidence"] and body["evidence"][0].startswith("ev:code:")  # work done before the crash is kept
    [eff] = d.s.effects.for_task(sub["task_id"])
    assert eff["state"] == "unknown"
    task = d.task(sub["task_id"])
    assert (task["state"], task["outcome"]) == ("finished", "interrupted")
    assert d.s.models.client("fake").calls == []  # recovery itself never calls a model


async def test_resume_continues_from_the_journal_without_repeating(make_config, monkeypatch):
    cfg, model, sub, old = await _crash_during_command(make_config, monkeypatch)
    await old.s.aclose()
    scripted.register(model, [
        {"tool_calls": [{"name": "list_dir", "arguments": {"path": "."}}]},
        {"text": "Migration state checked; not re-running it until the user confirms."},
    ])
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 5)  # the interrupted report
        d.control("doctor", "resume_task", task_id=sub["task_id"])
        for _ in range(250):
            reports = [m for m in d.s.bus.list(task_id=sub["task_id"]) if m["kind"] == "report"]
            if len(reports) == 2:
                break
            await asyncio.sleep(0.02)
    finally:
        await d.halt()
    assert [r["body"]["outcome"] for r in reports] == ["interrupted", "done"]
    final = reports[1]["body"]
    assert final["usage"]["steps"] == 4 and final["usage"]["model_calls"] == 4  # 2 before the crash + 2 after

    sent = d.s.models.client("fake").calls[0]["messages"]
    roles = [m.role for m in sent]
    assert roles[:2] == ["system", "user"]
    # the original conversation is rebuilt: read_file call + result, run_command call + UNKNOWN result
    calls = [tc.name for m in sent if m.role == "assistant" for tc in m.tool_calls]
    assert calls == ["read_file", "run_command"]
    unknown = [m for m in sent if m.role == "tool" and m.name == "run_command"]
    assert unknown and "UNKNOWN" in unknown[0].content
    convo = [m for m in sent if not (m.content or "").startswith("[Code Doctor working memory")]  # ADR 0008: not part of it
    assert "NOT safe to retry" in convo[-1].content and convo[-1].role == "user"
    assert [e["tool"] for e in d.s.effects.for_task(sub["task_id"])] == ["run_command"]  # nothing re-ran


async def test_cannot_resume_a_finished_task(make_config):
    model = unique_model()
    cfg = make_config({model: [{"text": "done"}]})
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", "t", "go")
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 5)
        d.control("doctor", "resume_task", task_id=sub["task_id"])
        for _ in range(200):
            esc = [m for m in d.s.bus.list(thread_id=None, task_id=sub["task_id"]) if m["kind"] == "escalation"]
            if esc:
                break
            await asyncio.sleep(0.02)
    finally:
        await d.halt()
    assert esc and "cannot resume" in esc[0]["body"]["detail"]


async def test_completed_effects_are_recorded_with_results(make_config):
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "remember", "arguments": {"text": "a fact about shop.py"}}]},
        {"text": "ok"},
    ]})
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", "t", "go")
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 5)
    finally:
        await d.halt()
    [eff] = d.task(sub["task_id"])["side_effects"]
    assert (eff["tool"], eff["state"], eff["effect_class"]) == ("remember", "done", "internal")
    assert eff["result_summary"].startswith("remembered as mem_")
