"""submit_claim reshapes unambiguous shorthand and explains entity ids (first real run, DeepSeek, 2026-10-27)."""

from __future__ import annotations

from types import SimpleNamespace

from codedoctor.agents import claim_input
from codedoctor.agents.tools import TOOLS, usable
from codedoctor.config import Permissions

V = "wt-" + "a" * 64


def draft(**over):
    d = {"claim_type": "finding", "evidence_level": "inferred",
         "statement": {"text": "retry charges twice", "subject": "web/api.js#request", "relation": "causes",
                       "object": "duplicate wallet charge"},
         "evidence": [{"id": f"ev:code:{V}:web/api.js@{'b' * 64}:L1-L34", "role": "primary", "shows": "retries POST",
                       "assert": True}],
         "conditions": "slow network"}
    d.update(over)
    return d


def test_shorthand_is_reshaped_and_reported(tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "api.js").write_text("function request() {}\n", encoding="utf-8")
    out, notes = claim_input.normalize(draft(scope={"paths": ["web/api.js"]}), "shop", {}, tmp_path)
    st = out["statement"]
    assert st["subject"] == "ent:symbol:shop:web/api.js#request"
    assert st["object"] == {"value": "duplicate wallet charge"}
    assert out["evidence"][0]["role"] == "supports" and "assert" not in out["evidence"][0]
    assert out["conditions"] == [{"text": "slow network"}]
    assert out["scope"] == {"code_version": V}  # from the cited evidence; the unknown key is dropped
    assert len(notes) == 7  # subject, object, role, assert, conditions, scope key, code version


def test_nothing_semantic_is_guessed(tmp_path):
    out, _ = claim_input.normalize(draft(claim_type="root_cause", evidence_level="code_only",
                                         falsification="if a key were sent"), "shop", {}, tmp_path)
    assert out["claim_type"] == "root_cause" and out["evidence_level"] == "code_only"
    assert out["falsification"] == "if a key were sent"
    assert out["statement"]["subject"] == "web/api.js#request"  # no such file: left for the validator to explain


def test_entity_errors_name_real_ids():
    nodes = {"ent:symbol:shop:web/api.js#request": None, "ent:symbol:shop:server/checkout.py#checkout": None,
             "ent:file:shop:README.md": None}
    [p] = claim_input.explain(["statement/subject: 'api.js request' is not valid under any of the given schemas"],
                              {"statement": {"subject": "api.js request"}}, nodes)
    assert "is not an entity id" in p and "ent:symbol:shop:web/api.js#request" in p


def test_a_json_string_claim_is_accepted():
    assert claim_input.parse('{"claim_type": "finding"}') == {"claim_type": "finding"}


def test_a_missing_or_doubled_wrapper_is_accepted():
    c = {"claim_type": "finding"}
    assert claim_input.unwrap({"claim": c}) == claim_input.unwrap(c) == claim_input.unwrap({"claim": {"claim": c}}) == c


def test_the_tool_shows_the_claim_shape():
    claim = TOOLS["submit_claim"].parameters["properties"]["claim"]
    assert claim["properties"]["claim_type"]["enum"] == claim_input.CLAIM_TYPES
    assert not TOOLS["submit_claim"].check_args


def test_tools_that_cannot_work_are_not_offered():
    class Cfg:
        permissions = Permissions(run_command="deny")
        agents = {"worker-1": SimpleNamespace(role="worker"), "guardian-1": SimpleNamespace(role="guardian")}  # 双人互检

    assert not usable("run_command", Cfg) and not usable("cluster_run", Cfg) and usable("cluster_impact", Cfg)
    Cfg.permissions = Permissions(run_command="allowlist")
    Cfg.agents = {**Cfg.agents, "logic": SimpleNamespace(role="head_logic")}
    assert usable("run_command", Cfg) and usable("cluster_run", Cfg)
    assert not usable("decide_anomaly", Cfg, "worker") and usable("decide_anomaly", Cfg, "head_logic")


async def test_the_answering_agent_keeps_budget_for_its_guardian_and_still_answers(make_config):
    """Real run 2: the dual-mode worker spent everything, its guardian never ran and the user got no answer. The user's
    rule: no read-only members, so the worker is told to stop reading and fix."""
    import asyncio

    from codedoctor.agents.daemon import Daemon
    from conftest import unique_model

    w, g = unique_model(), unique_model()
    read = {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py"}}], "input_tokens": 200}
    cfg = make_config({w: [read, read, read, {"text": "Found: buy() returns early. Not covered: the client."}],
                       g: [{"text": "nothing to review"}]},
                      agents=[{"id": "worker-1", "role": "worker", "endpoint": "fake", "model": w},
                              {"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": g,
                               "supervises_workers": ["worker-1"]}],
                      defaults={"budget": {"max_steps": 12, "max_tokens": 1000}, "stall_steps": 5})
    d = Daemon(cfg, poll_s=0.02)
    await d.start()
    try:
        sub = d.submit_task("worker-1", "t", "why does buy do nothing")
        report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
    finally:
        await d.halt()
    calls = [c for c in d.s.models.client("fake").calls if c["model"] == w]
    said = lambda i: " ".join(m.content or "" for m in calls[i]["messages"] if m.role == "user")  # noqa: E731
    # every worker fixes (the user removed read-only members), so the first warning says to stop reading and fix
    assert "Stop reading" in said(2) and "WITHOUT calling tools" in said(3)  # 250+250 > 60% of 700; 750 > 700
    assert report["body"]["outcome"] == "done" and "buy() returns early" in report["body"]["summary"]


def test_requests_in_flight_count_against_the_investigation_budget(make_config):
    from codedoctor.agents import orchestration as orch
    from codedoctor.agents.daemon import Daemon

    d = Daemon(make_config())
    sub = d.submit_task("doctor", "t", "go")
    before, _, root = orch.cluster_budget(d.s, sub["task_id"])
    orch.inflight(d.s)[root] = 12000  # another agent's request is on its way
    assert orch.cluster_budget(d.s, sub["task_id"])[0] == before + 12000


async def test_an_empty_balance_is_explained_in_chinese_and_no_other_agent_tries_again(make_config):
    """Real run: the DeepSeek balance ran out and every agent hit HTTP 402 on its own; the user saw 'model_unavailable'."""
    import asyncio

    from codedoctor.agents.daemon import Daemon
    from conftest import unique_model

    a, b = unique_model(), unique_model()
    broke = {"error": 'HTTP 402: {"error":{"message":"Insufficient Balance"}}', "status": 402}
    cfg = make_config({a: [broke], b: [{"text": "never asked"}]},
                      agents=[{"id": "w1", "role": "general", "endpoint": "fake", "model": a},
                              {"id": "w2", "role": "general", "endpoint": "fake", "model": b}])
    d = Daemon(cfg, poll_s=0.02)
    await d.start()
    try:
        first = await asyncio.wait_for(d.wait_for_report(d.submit_task("w1", "t", "go")["task_id"]), 10)
        second = await asyncio.wait_for(d.wait_for_report(d.submit_task("w2", "t", "go")["task_id"]), 10)
    finally:
        await d.halt()
    assert first["body"]["outcome"] == "blocked" and "余额不足" in first["body"]["summary"]
    assert "余额不足" in second["body"]["summary"]
    assert not [c for c in d.s.models.client("fake").calls if c["model"] == b]  # w2 never sent a request
