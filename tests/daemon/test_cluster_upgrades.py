"""Cluster upgrades (ADR 0009): one token budget for the whole investigation, a worker pool, subtasks that carry
the claims and evidence to verify, and a warning when a guardian uses the same model as its worker."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

from codedoctor import cli, claim_rules
from codedoctor import config as config_mod
from codedoctor.agents import orchestration as orch
from codedoctor.agents.daemon import Daemon
from codedoctor.currency import snapshot_version
from codedoctor.models import scripted

from conftest import unique_model

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "shop-coupling"
S = "ent:symbol:shop:"


def cluster(tmp_path: Path, scripts: dict[str, list], *, workers=1, guardians=True, same_model_guardian=False):
    root = tmp_path / "shop-coupling"
    if not root.exists():
        shutil.copytree(SAMPLE, root)
    models = {a: unique_model(a) for a in scripts}
    for a, turns in scripts.items():
        scripted.register(models[a], turns)
    agents = [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": models.get("head-dispatch", "none")},
              {"id": "head-logic", "role": "head_logic", "endpoint": "fake", "model": models.get("head-logic", "none")}]
    for i in range(1, workers + 1):
        w = f"worker-{i}"
        agents.append({"id": w, "role": "worker", "endpoint": "fake", "model": models.get(w, "none")})
        if guardians:
            g = f"guardian-{i}"
            agents.append({"id": g, "role": "guardian", "endpoint": "fake", "supervises": w,
                           "model": models.get(w, "none") if same_model_guardian else models.get(g, "none")})
    return config_mod.parse({
        "cd_schema": "cd.config.project/0",
        "project": {"name": "shop", "root": str(root), "data_dir": str(tmp_path / "data")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": agents, "defaults": {"budget": {"max_steps": 12}, "stall_steps": 4},
    })


async def run(cfg, *, budget=None, setup=None, timeout=20):
    d = Daemon(cfg, poll_s=0.02)
    if setup:
        setup(d)
    await d.start()
    try:
        sub = d.submit_task("head-dispatch", "investigate", "Why are rewards paid twice?", budget=budget)
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), timeout)
        for _ in range(200):  # let subtasks and reviews settle
            if all(orch.task_row(d.s, t)["state"] == "finished" for t in orch.tree(d.s, sub["task_id"])):
                break
            await asyncio.sleep(0.02)
    finally:
        await d.halt()
    return d, sub, report


def tool_results(d, model_of_agent) -> list[str]:
    return [m.content for c in d.s.models.client("fake").calls if c["model"] == model_of_agent
            for m in c["messages"] if m.role == "tool"]


# Every project may change code (the user removed read-only members), so the head names each worker's files; one file, one
# worker, so each subtask gets a file of its own.
FILES = ["server/app.py", "server/db.py", "server/inventory.py", "server/rewards.py", "server/session.py", "server/shop.py"]


def delegate(agent, title, **kw):
    files = [FILES[sum(map(ord, title)) % len(FILES)]]
    return {"tool_calls": [{"name": "delegate", "arguments": {"agent": agent, "title": title, "instructions": f"do {title}",
                                                              "files": files, **kw}}]}


WAIT = {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 10}}]}


async def test_one_budget_for_the_whole_investigation(tmp_path):
    """The user's rule: every project may change code (no read-only members), so the head gives each worker its files."""
    burn = [{"tool_calls": [{"name": "list_dir", "arguments": {"path": p}}], "input_tokens": 3000}
            for p in ["server", "web", ".", "server", "web", "."]]
    # the head's own turns are counted small: this is about the worker using up the shared budget, not the head's prompt
    head = [{**t, "input_tokens": 300} for t in (delegate("worker-1", "burn"), WAIT, delegate("worker-1", "more"),
                                                 {"text": "partial answer"})]
    cfg = cluster(tmp_path, {"head-dispatch": head,
                             "worker-1": burn}, guardians=False)
    d, sub, report = await run(cfg, budget={"max_tokens": 8000})
    [work] = [c for c in orch.children(d.s, sub["task_id"])]
    assert orch.task_row(d.s, work["id"])["outcome"] == "budget_exhausted"
    # its share (a fifth) ran out first: it was asked to answer, called a tool instead and was stopped
    assert "share of the investigation's token budget is spent" in orch.report_of(d.s, work["id"])["summary"]
    worker_calls = [c for c in d.s.models.client("fake").calls if c["model"] == cfg.agents["worker-1"].primary.model]
    assert len(worker_calls) < len(burn)  # stopped by the shared budget, not by running out of script
    dispatch_tools = tool_results(d, cfg.agents["head-dispatch"].primary.model)
    assert any("No new subtasks" in t for t in dispatch_tools), (report, dispatch_tools)  # the second delegate was refused
    assert report["body"]["outcome"] == "done" and len(orch.children(d.s, sub["task_id"])) == 1
    used, limit, _ = orch.cluster_budget(d.s, sub["task_id"])
    assert limit == 8000 and used < 8000 + 3100 + 2000  # at most one call per agent past the limit, plus the answer
    await d.s.aclose()


async def test_any_worker_spreads_subtasks_over_the_pool(tmp_path):
    """The user's rule: every project may change code (no read-only members), so the head gives each worker its files."""
    work = [{"tool_calls": [{"name": "list_dir", "arguments": {"path": "server"}}]}, {"text": "listed"}]
    cfg = cluster(tmp_path, {"head-dispatch": [delegate("any", "A"), delegate("any", "B"), WAIT, {"text": "both done"}],
                             "worker-1": list(work), "worker-2": list(work)}, workers=2, guardians=False)
    d, sub, report = await run(cfg)
    kids = orch.children(d.s, sub["task_id"])
    assert sorted(k["agent"] for k in kids) == ["worker-1", "worker-2"]  # the second went to the idle worker
    assert all(k["outcome"] == "done" for k in kids) and report["body"]["outcome"] == "done"
    status = tool_results(d, cfg.agents["head-dispatch"].primary.model)
    assert any("delegated" in t and "open task(s) there now" in t for t in status)
    await d.s.aclose()


async def test_a_subtask_carries_claims_to_verify_and_the_supervisor_states_the_result(tmp_path):
    """The user's rule: every project may change code (no read-only members): the worker is the hands, gets its files and
    files no claims; its supervisor re-checks and supersedes the claim it was asked to verify."""
    held: dict = {}

    def setup(d):
        root = d.s.config.root
        ev, _ = d.s.evidence.add_code_excerpt(root, "server/session.py", 8, 10, agent_id="head-logic")
        claim = d.s.claims.submit({
            "claim_type": "hypothesis", "evidence_level": "inferred",
            "statement": {"text": "reconnect replays settle, so the reward is paid twice", "subject": S + "server/session.py#reconnect",
                          "relation": "causes", "object": "ent:state:shop:py/gold"},
            "scope": {"code_version": snapshot_version(root)},
            "evidence": [{"id": ev, "role": "supports", "shows": "replay loop"}],
            "falsification": {"method": "test", "description": "settle, drop the response, reconnect, compare gold"}},
            author={"kind": "agent", "id": "head-logic", "role": "head_logic", "model": {"provider": "scripted", "model": "m"},
                    "task_id": "task_01JB8Z2000000000000000TK01"})
        held.update(claim=claim["id"], ev=ev)

    def guardian_verifies(msgs):
        ev = re.findall(r"evidence: (ev:code:\S+)", "\n".join(m.content or "" for m in msgs))[-1]
        return {"tool_calls": [{"name": "submit_claim", "arguments": {"claim": {
            "claim_type": "hypothesis", "evidence_level": "inferred", "supersedes": held["claim"],
            "statement": {"text": "confirmed: the loop calls settle() for every pending settle request",
                          "subject": S + "server/session.py#reconnect", "relation": "causes", "object": "ent:state:shop:py/gold"},
            "scope": {"code_version": ev.split(":")[2]},
            "evidence": [{"id": ev, "role": "supports", "shows": "settle(pending, player) inside the loop",
                          "assert": [{"op": "text_contains", "text": "settle(pending, player)"}]}],
            "falsification": {"method": "test", "description": "settle, drop the response, reconnect, compare gold"}}}}]}

    cfg = cluster(tmp_path, {
        "head-dispatch": [
            delegate("worker-1", "bad", claims=["clm_01JB8Z8000000000000000CM99"]),
            lambda msgs: delegate("worker-1", "verify", claims=[held["claim"]], evidence=[held["ev"]]),
            WAIT, {"text": "verified"}],
        "worker-1": [{"tool_calls": [{"name": "read_file", "arguments": {"path": "server/session.py", "start_line": 5, "end_line": 12}}]},
                     {"text": "confirmed: settle() runs for every pending settle request"}],
        "guardian-1": [{"tool_calls": [{"name": "read_file", "arguments": {"path": "server/session.py", "start_line": 5, "end_line": 12}}]},
                       guardian_verifies, {"text": "re-checked and superseded"}],
    })
    d, sub, report = await run(cfg, setup=setup)
    dispatch_tools = tool_results(d, cfg.agents["head-dispatch"].primary.model)
    assert "unknown claim clm_01JB8Z8000000000000000CM99" in dispatch_tools[0]
    first = [c for c in d.s.models.client("fake").calls if c["model"] == cfg.agents["worker-1"].primary.model][0]["messages"]
    task_text = first[1].content
    assert held["claim"] in task_text and held["ev"] in task_text and '"supersedes"' in task_text
    assert "<<<DATA (untrusted content from claims and evidence" in task_text
    assert first[-1].content.startswith("[Code Doctor working memory") and f"{held['claim']} [UNVERIFIED]" in first[-1].content
    [work] = [c for c in orch.children(d.s, sub["task_id"]) if not orch.body_of(c).get("review_of")]
    assert orch.body_of(work)["context"] == {"claims": [held["claim"]], "evidence": [held["ev"]]}
    assert d.s.claims.get(held["claim"])["status"] == "superseded"
    assert not d.s.claims.by_task(work["id"])  # the hands file no claims
    [review] = [c for c in orch.children(d.s, sub["task_id"]) if orch.body_of(c).get("review_of") == work["id"]]
    [new] = d.s.claims.by_task(review["id"])
    assert new["author"]["id"] == "guardian-1"
    assert d.s.notes.claim_states([held["claim"]]) == {held["claim"]: (new["status"], new["id"])}
    await d.s.aclose()


def test_guardian_with_the_workers_model_is_warned_about(tmp_path, capsys):
    same = cluster(tmp_path, {"worker-1": [], "guardian-1": []}, same_model_guardian=True)
    assert len(config_mod.independence_warnings(same)) == 1 and "guardian-1" in config_mod.independence_warnings(same)[0]
    assert config_mod.independence_warnings(cluster(tmp_path, {"worker-1": [], "guardian-1": []})) == []
    path = tmp_path / "cd.toml"
    raw = config_mod.load_raw(path) if path.exists() else None
    assert raw is None
    config_mod.save_raw({
        "cd_schema": "cd.config.project/0", "project": {"name": "shop", "root": str(same.root), "data_dir": str(tmp_path / "d2")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": [{"id": "worker-1", "role": "worker", "endpoint": "fake", "model": "m"},
                   {"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": "m", "supervises": "worker-1"}]}, path)
    cli.main(["check", "--config", str(path)])
    assert "提醒：监督者 guardian-1" in capsys.readouterr().out
