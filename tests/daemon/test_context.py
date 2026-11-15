"""Context management (ADR 0008, M5): working memory, elision with a low-water mark, deduplicated
tool results, recall and tool output sized to the context budget, and a journal that still
rebuilds every request exactly."""

from __future__ import annotations

import asyncio
import re

from codedoctor.agents.daemon import Daemon
from codedoctor.agents.runtime import BEFORE_M5, ContextPolicy
from codedoctor.models import scripted

from conftest import unique_model

WM = "[Code Doctor working memory"
def _tools_tokens() -> int:
    """Tokens the general role's tool descriptions in a plain task and its system prompt take: they count against the
    budget (review R5). Measured, not written down: the user turned computer use on for every project (2026-11-13), and
    its tools go with every request too."""
    import tempfile
    from pathlib import Path

    from codedoctor import config as config_mod, makers, model3d, video
    from codedoctor.agents import prompts
    from codedoctor.store.db import dumps

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
        cfg = config_mod.parse({"cd_schema": "cd.config.project/0", "project": {"name": "shop-demo", "root": t, "data_dir": t},
                                "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
                                "agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": "m"}]},
                               base_dir=Path(t))
        d = Daemon(cfg)
        kits = {*video.NAMES, *model3d.NAMES, *makers.NAMES}
        chars = sum(len(dumps({"name": x.name, "description": x.description, "parameters": x.parameters}))
                    for n, x in d.agents["doctor"].tools.items() if n not in kits)
        d.s.db.close()
    return int((chars + len(prompts.system_prompt("general", "doctor", "shop-demo", "", fixes=True))) / 3)


TOOLS = _tools_tokens()


def big_file(project, name="server/big.py", lines=300):
    (project / name).write_text("".join(f"def f{i}(x):  # line {i:04d} padding padding padding\n" for i in range(1, lines + 1)),
                                encoding="utf-8")


async def run(cfg, policy=None, instructions="look", timeout=15):
    d = Daemon(cfg, poll_s=0.02)
    if policy is not None:
        for a in d.agents.values():
            a.policy = policy
    await d.start()
    try:
        sub = d.submit_task("doctor", instructions[:60], instructions)
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), timeout)
    finally:
        await d.halt()
    return d, sub, report


def agent(model, budget=None):
    a = {"id": "doctor", "role": "general", "endpoint": "fake", "model": model}
    if budget:
        a["context_budget_tokens"] = budget
    return [a]


def requests(d, task_id):
    return [d.s.journal.original(e)["payload"] for e in d.s.journal.read(task_id=task_id) if e["type"] == "model_request"]


def last_claim(msgs) -> str:
    """From the tool result that accepted it or, once that was elided, from the working memory - as a model would."""
    from codedoctor.bench.context import _newest_claim

    return _newest_claim(msgs)


def claim_turn(msgs):
    ev = re.findall(r"evidence: (ev:code:\S+)", "\n".join(m.content or "" for m in msgs))[-1]
    return {"tool_calls": [{"name": "submit_claim", "arguments": {"claim": {
        "claim_type": "hypothesis", "evidence_level": "inferred",
        "statement": {"text": "early return skips the orders write", "subject": "ent:symbol:shop-demo:server/shop.py#ShopService.buy",
                      "relation": "causes", "object": "ent:stage:shop.buy/db-write"},
        "scope": {"code_version": ev.split(":")[2]},
        "evidence": [{"id": ev, "role": "supports", "shows": "early return"}],
        "falsification": {"method": "test", "description": "call buy() with equal versions"}}}}]}


async def test_working_memory_carries_current_claim_status_and_evidence(make_config):
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py"}}]},
        claim_turn,
        lambda msgs: {"tool_calls": [{"name": "withdraw_claim", "arguments": {"claim_id": last_claim(msgs), "reason": "wrong"}}]},
        {"text": "done"},
    ]}, agents=agent(model, budget=1200 + TOOLS))
    d, sub, _ = await run(cfg)
    calls = d.s.models.client("fake").calls
    assert not calls[0]["messages"][-1].content.startswith(WM)  # nothing established yet: no working memory
    wm2, wm3, wm4 = (c["messages"][-1].content for c in calls[1:4])
    assert wm2.startswith(WM) and "ev:code:" in wm2 and "server/shop.py" in wm2
    cid = last_claim(calls[2]["messages"])
    assert f"{cid} [UNVERIFIED]" in wm3
    assert f"{cid} [RULED OUT (withdrawn)]" in wm4  # read from the database, not from the conversation
    assert "<<<DATA (untrusted content from working memory" in wm4
    # the journal keeps what was sent, outside the conversation itself
    assert requests(d, sub["task_id"])[3]["working_memory"] == wm4


async def test_elision_goes_to_the_low_water_mark_and_the_journal_rebuilds_every_request(make_config, project):
    big_file(project)
    reads = [{"tool_calls": [{"name": "read_file", "arguments": {"path": "server/big.py", "start_line": 1 + 30 * i,
                                                                "end_line": 30 + 30 * i}}]} for i in range(9)]

    async def rewrites(policy):
        model = unique_model()
        cfg = make_config({model: reads + [{"text": "done"}]}, agents=agent(model, budget=3000 + TOOLS))
        d, sub, _ = await run(cfg, policy)
        sent = d.s.models.client("fake").calls
        budget = (3000 + TOOLS) * 3
        assert all(sum(len(m.content or "") for m in c["messages"]) <= budget + 50 for c in sent)
        # rebuild the conversation from the journal: request deltas plus the rewrites recorded with them
        convo = []
        for p, call in zip(requests(d, sub["task_id"]), sent):
            for i, content in p.get("rewritten", {}).items():
                convo[int(i)]["content"] = content
            convo += p["messages"]
            actual = call["messages"][:-1] if call["messages"][-1].content.startswith(WM) else call["messages"]
            assert [m["content"] for m in convo] == [m.content for m in actual]
        return sum(1 for p in requests(d, sub["task_id"]) if p.get("rewritten"))

    eager, low_water = await rewrites(ContextPolicy(low_water=1.0)), await rewrites(ContextPolicy())
    assert 0 < low_water < eager  # fewer rewrites of the middle of the context: a local model's prefix cache survives


async def test_an_identical_tool_result_is_not_repeated(make_config):
    model = unique_model()
    read = {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py"}}]}
    cfg = make_config({model: [read, read, {"text": "done"}]})
    d, _, _ = await run(cfg)
    tools = [m for m in d.s.models.client("fake").calls[2]["messages"] if m.role == "tool"]
    assert tools[0].content.startswith("<<<DATA") and "class ShopService" in tools[0].content
    assert tools[1].content.startswith("(identical to the earlier read_file result above") and "evidence: ev:code:" in tools[1].content
    model = unique_model()
    cfg = make_config({model: [read, read, {"text": "done"}]})
    d, _, _ = await run(cfg, BEFORE_M5)
    tools = [m for m in d.s.models.client("fake").calls[2]["messages"] if m.role == "tool"]
    assert tools[0].content == tools[1].content


async def test_tool_output_follows_the_budget_and_evidence_matches_what_was_shown(make_config, project):
    big_file(project)
    model = unique_model()
    cfg = make_config({model: [{"tool_calls": [{"name": "read_file", "arguments": {"path": "server/big.py"}}]}, {"text": "done"}]},
                      agents=agent(model, budget=3000 + TOOLS))
    d, _, _ = await run(cfg)
    [tool] = [m for m in d.s.models.client("fake").calls[1]["messages"] if m.role == "tool"]
    shown = re.search(r"file: server/big.py lines 1-(\d+) of 300", tool.content)
    last = int(shown.group(1))
    assert 10 < last < 300 and f"start_line={last + 1}" in tool.content  # cut to the budget, not the whole file
    ev = re.search(r"evidence: (ev:code:\S+)", tool.content).group(1)
    assert ev.endswith(f":L1-L{last}")  # cites exactly the lines the model saw
    assert len(tool.content) < (3000 + TOOLS) * 3 * 0.25 + 400


async def test_recalled_memory_fits_its_share_and_read_note_shows_all(make_config):
    model = unique_model()
    cfg = make_config({model: [
        lambda msgs: {"tool_calls": [{"name": "read_note", "arguments": {"id": re.findall(r"mem_[0-9A-Z]{26}", msgs[1].content)[0]}}]},
        {"text": "done"},
    ]}, agents=agent(model, budget=3000 + TOOLS))
    d = Daemon(cfg)
    src = [d.s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]
    for i in range(8):
        d.s.notes.write(owner="doctor", scope="project", kind="summary", sources=src,
                        text=f"金币结算 reconnect 调查 {i}: " + "细节 " * 1500)
    await d.s.aclose()
    d, _, _ = await run(cfg, instructions="金币结算 reconnect 为什么重复")
    calls = d.s.models.client("fake").calls
    memory = calls[0]["messages"][1].content.split("Relevant long-term memory", 1)[1]
    assert len(memory) < (3000 + TOOLS) * 3 * 0.15 + 600
    assert "read_note mem_" in memory and "more matching notes not shown" in memory
    [tool] = [m for m in calls[1]["messages"] if m.role == "tool"]
    assert tool.content.count("细节") == 1500 and "sources: jrn_" in tool.content


async def test_read_note_respects_private_memory(make_config):
    model = unique_model()
    cfg = make_config({model: [
        lambda msgs: {"tool_calls": [{"name": "read_note", "arguments": {"id": PRIVATE[0]}}]},
        {"text": "done"},
    ]})
    d = Daemon(cfg)
    src = [d.s.journal.append("worker-9", "state_change", {"state": "idle"})["id"]]
    PRIVATE[:] = [d.s.notes.write(owner="worker-9", scope="agent", kind="fact", sources=src, text="private")["id"]]
    await d.s.aclose()
    d, _, _ = await run(cfg)
    [tool] = [m for m in d.s.models.client("fake").calls[1]["messages"] if m.role == "tool"]
    assert "no note" in tool.content and "private" not in tool.content.replace("no note", "")


PRIVATE: list[str] = []


async def test_a_short_task_with_room_to_spare_gets_no_working_memory(make_config):
    model = unique_model()
    cfg = make_config({model: [{"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py"}}]}, claim_turn,
                               {"text": "done"}]})
    d, sub, _ = await run(cfg)
    assert not any(c["messages"][-1].content.startswith(WM) for c in d.s.models.client("fake").calls)
    assert not any("working_memory" in p for p in requests(d, sub["task_id"]))


async def test_two_refusals_with_the_same_words_are_both_shown(make_config):
    """A real team run: two different calls got the same refusal; the second was folded into "identical to the earlier
    result" and the agent reported that both ran and failed. Refusals are never folded. (The run's refusal came from the
    command allowlist, which the user removed; two calls missing the same argument get the same words here.)"""
    model = unique_model()
    a = {"tool_calls": [{"name": "read_file", "arguments": {"start_line": 1}}]}
    b = {"tool_calls": [{"name": "read_file", "arguments": {"start_line": 2}}]}
    cfg = make_config({model: [a, b, {"text": "done"}]})
    d, _, _ = await run(cfg)
    tools = [m for m in d.s.models.client("fake").calls[2]["messages"] if m.role == "tool"]
    assert len(tools) == 2 and all(t.content.startswith("ERROR") for t in tools), [t.content[:80] for t in tools]
