from __future__ import annotations

import asyncio
import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from codedoctor.agents import orchestration as orch
from codedoctor.agents.daemon import Daemon
from codedoctor.agents.tools import tools_for
from codedoctor.cluster.contracts import BusinessError, evaluate, validate_contract
from codedoctor.cluster.coupling import candidates
from codedoctor.cluster.experiments import Scenario, execute
from codedoctor.graph.model import Edge, Graph, Node
from codedoctor.store.db import dumps
from tools.business_cluster_cases import plan, prepare
from tools.business_cluster_demo import configuration, execute_case


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["duplicate", "concurrent", "pricing"])
async def test_actual_business_cluster_closes_experiments_and_regressions(tmp_path, case):
    result = await execute_case(tmp_path / case, case)
    assert result["outcome"] == "done", result
    assert result["status"]["delivery_allowed"]
    assert result["status"]["compatible_hypotheses"] == ["mechanism"]
    assert result["experimental_receipts"] == 24  # 2 checks x 2 actors x 2 repeats x 3 phases
    assert len(result["tasks"]) == 6  # dispatch, logic, two workers, two independent guardians


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [{"guardian_runs": False}, {"early_delivery": True}])
async def test_text_agreement_and_early_head_delivery_cannot_bypass_evidence(tmp_path, options):
    result = await execute_case(tmp_path, "duplicate", **options)
    assert result["outcome"] == "blocked"
    assert not result["status"]["delivery_allowed"]
    assert any("awaiting_independent_execution" in reason for reason in result["status"]["blocking_reasons"])


@pytest.fixture
def engine(tmp_path):
    daemon = Daemon(configuration(tmp_path, "duplicate"))
    prepare(daemon.s)
    root = daemon.submit_task("dispatch", "business", "investigate")
    document = daemon.s.investigations.open(root["task_id"], "logic", plan("cluster-shop"))
    yield daemon, document
    daemon.s.db.close()


def run_both(daemon, doc, check="distinguish", worker="worker-1", guardian="guardian-1"):
    engine = daemon.s.investigations
    sub = engine.dispatch(doc["id"], "dispatch", check_id=check, worker=worker)
    worker_result = engine.run(doc["id"], check, worker, sub["task_id"], "internal")
    review = orch.create_subtask(daemon.s, sender="system", recipient=guardian, title="review", instructions="independent",
                                parent_task_id=doc["root_task_id"], review_of=sub["task_id"])
    guardian_result = engine.run(doc["id"], check, guardian, review["task_id"], "internal")
    # Unit harness simulates the surrounding task completion; end-to-end tests
    # above exercise the actual runtime/report lifecycle instead.
    with daemon.s.db.tx() as connection:
        connection.execute("UPDATE tasks SET state='finished',outcome='done' WHERE id IN (?,?)", (sub["task_id"], review["task_id"]))
    return worker_result, guardian_result


def test_ui_reads_actual_investigation_without_write_authority(engine):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from codedoctor.cluster.http import mount

    daemon, doc = engine
    app = FastAPI()
    mount(app, daemon)
    with TestClient(app) as client:
        capability = client.get("/cluster/capabilities").json()
        assert capability["business_contracts_require_user_approval"]
        assert not capability["heads_execute_terminal_or_experiments"]
        detail = client.get("/cluster/investigations/" + doc["id"])
        assert detail.status_code == 200
        assert not detail.json()["status"]["delivery_allowed"]
        assert client.get("/cluster/investigations/missing").status_code == 404
        assert client.get("/cluster/investigations", params={"root_task_id": "missing"}).json() == []
        assert client.get("/cluster/contracts").json()
        assert client.post("/cluster/contracts", json={"approve": True}).status_code == 405


def test_missing_adapter_after_restart_never_auto_imports_or_executes(engine):
    daemon, doc = engine
    sub = daemon.s.investigations.dispatch(doc["id"], "dispatch", check_id="distinguish", worker="worker-1")
    daemon.s.investigations.registry.scenarios.clear()
    with pytest.raises(BusinessError, match="re-registered"):
        daemon.s.investigations.run(doc["id"], "distinguish", "worker-1", sub["task_id"], "internal")
    assert not daemon.s.db.query("SELECT * FROM cluster_trials")
    assert not daemon.s.investigations.status(doc["id"])["delivery_allowed"]


def test_raw_execution_receipts_have_independent_harnesses_and_runs(engine):
    daemon, doc = engine
    first, second = run_both(daemon, doc)
    assert first["trial"] != second["trial"] and first["harness"] != second["harness"]
    assert first["signature"] == second["signature"] == "violated"
    assert first["records"][1]["metrics"]["actual"] == 60
    assert second["records"][1]["metrics"]["actual"] == 80
    assert daemon.s.investigations.status(doc["id"])["compatible_hypotheses"] == ["mechanism"]
    assert not daemon.s.investigations.status(doc["id"])["delivery_allowed"]  # impact regression still missing


def test_tampered_evidence_blocks_previously_valid_result(engine):
    daemon, doc = engine
    first, _ = run_both(daemon, doc)
    run_both(daemon, doc, "impact_regression", "worker-2", "guardian-2")
    assert daemon.s.investigations.status(doc["id"])["delivery_allowed"]
    record = daemon.s.evidence.get(first["records"][0]["evidence"])
    daemon.s.blobs.path(record["content"]["sha256"]).write_bytes(b"tampered")
    status = daemon.s.investigations.status(doc["id"])
    assert not status["delivery_allowed"] and any("invalid_evidence" in reason for reason in status["blocking_reasons"])


def test_changed_code_invalidates_old_trials(engine):
    daemon, doc = engine
    run_both(daemon, doc)
    (daemon.s.config.root / "system.py").write_bytes((daemon.s.config.root / "system.py").read_bytes() + b"\n# changed\n")
    assert not daemon.s.investigations.status(doc["id"])["delivery_allowed"]
    with pytest.raises(BusinessError, match="code changed"):
        daemon.s.investigations.dispatch(doc["id"], "dispatch", check_id="impact_regression")


def test_guardian_cannot_reuse_worker_task_or_another_workers_job(engine):
    daemon, doc = engine
    sub = daemon.s.investigations.dispatch(doc["id"], "dispatch", check_id="distinguish", worker="worker-1")
    daemon.s.investigations.run(doc["id"], "distinguish", "worker-1", sub["task_id"], "internal")
    with pytest.raises(PermissionError):
        daemon.s.investigations.run(doc["id"], "distinguish", "guardian-1", sub["task_id"], "internal")
    with pytest.raises(PermissionError):
        daemon.s.investigations.run(doc["id"], "distinguish", "guardian-2", sub["task_id"], "internal")


def test_duplicate_execution_returns_the_same_cached_receipt_not_new_trials(engine):
    daemon, doc = engine
    sub = daemon.s.investigations.dispatch(doc["id"], "dispatch", check_id="distinguish", worker="worker-1")
    first = daemon.s.investigations.run(doc["id"], "distinguish", "worker-1", sub["task_id"], "internal")
    second = daemon.s.investigations.run(doc["id"], "distinguish", "worker-1", sub["task_id"], "internal")
    assert first == second


def test_atomic_task_message_and_business_assignment_rollback_together(engine):
    daemon, doc = engine
    count = len(daemon.s.bus.list(limit=1000))
    def fail(connection, task_id):
        raise RuntimeError("deliberate transaction failure")
    with pytest.raises(RuntimeError):
        orch.create_subtask(daemon.s, sender="dispatch", recipient="worker-1", title="rollback", instructions="do not run",
                            parent_task_id=doc["root_task_id"], on_created=fail)
    assert len(daemon.s.bus.list(limit=1000)) == count
    assert not orch.children(daemon.s, doc["root_task_id"])


def test_heads_cannot_override_tool_configuration_to_execute_commands_or_experiments():
    for role in ("head_dispatch", "head_logic"):
        for name in ("run_command", "cluster_run"):
            with pytest.raises(ValueError, match="cannot execute"):
                tools_for(role, (name,))


def test_unapproved_contract_and_unregistered_scenario_are_not_accepted(engine):
    daemon, doc = engine
    with pytest.raises(PermissionError):
        daemon.s.investigations.approve_contract({"id": "fake"}, "made-up", approved_by="logic")
    altered = copy.deepcopy(doc["plan"])
    altered["checks"][0]["scenario"] = "arbitrary_import"
    # A separate root avoids the existing-plan immutability gate.
    root = daemon.submit_task("dispatch", "other", "other")
    with pytest.raises(BusinessError, match="explicitly registered"):
        daemon.s.investigations.open(root["task_id"], "logic", altered)


def test_missing_business_observation_is_unknown_not_a_bug():
    contract = {"id": "money", "description": "account agrees with ledger", "rule": {"op": "equal", "left": "balance", "right": "ledger"}}
    assert evaluate(contract, {"balance": 30})["status"] == "unknown"
    assert evaluate(contract, {"balance": True, "ledger": 1})["status"] == "unknown"
    assert evaluate(contract, {"balance": 30, "ledger": 60})["status"] == "violated"


def test_typed_influence_finds_shared_callee_and_not_shared_downstream_noise():
    graph = Graph({name: Node(name, "symbol", name) for name in ("cart", "invoice", "pricing", "gold", "unrelated")})
    graph.add_edge(Edge("cart", "calls", "pricing", path="pricing.py", line=7))
    graph.add_edge(Edge("invoice", "calls", "pricing", path="invoice.py", line=9))
    graph.add_edge(Edge("pricing", "writes", "gold"))
    graph.add_edge(Edge("unrelated", "reads", "gold"))
    result = candidates(graph, ["cart", "invoice"])
    assert result["candidates"][0]["entity"] == "pricing"
    assert not result["causality_proven"]
    assert all(hop["from"] == "pricing" for path in result["candidates"][0]["paths"].values() for hop in path)
    assert "unrelated" not in {row["entity"] for row in result["candidates"]}


def test_cycles_budgets_and_uncertain_edges_are_explicit():
    graph = Graph({name: Node(name, "symbol", name) for name in ("a", "b", "c", "invented")})
    graph.add_edge(Edge("a", "calls", "b"))
    graph.add_edge(Edge("b", "calls", "a"))
    graph.add_edge(Edge("b", "calls", "c"))
    graph.add_edge(Edge("a", "may_cause", "invented", provenance="inferred"))
    result = candidates(graph, ["a"], depth=1)
    assert result["truncated"] and result["excluded_uncertain_edges"]
    assert "invented" not in {r["entity"] for r in result["candidates"]}


def test_concurrent_dispatch_cannot_duplicate_one_check(engine):
    daemon, doc = engine
    barrier = threading.Barrier(2)
    def dispatch():
        barrier.wait()
        try:
            return daemon.s.investigations.dispatch(doc["id"], "dispatch", check_id="distinguish", worker="worker-1")
        except BusinessError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: dispatch(), range(2)))
    assert sum(result is not None for result in results) == 1
    children = orch.children(daemon.s, doc["root_task_id"])
    assert len(children) == 1
    assignment = daemon.s.db.one("SELECT * FROM cluster_checks WHERE investigation=? AND id='distinguish'", (doc["id"],))
    assert assignment["worker_task"] == children[0]["id"]


def test_competing_hypotheses_with_the_same_predictions_remain_unresolved(engine):
    daemon, doc = engine
    altered = copy.deepcopy(doc["plan"])
    altered["checks"][0]["predictions"]["display_only"] = "violated"
    root = daemon.submit_task("dispatch", "indistinguishable", "test alternatives")
    second = daemon.s.investigations.open(root["task_id"], "logic", altered)
    run_both(daemon, second)
    run_both(daemon, second, "impact_regression", "worker-2", "guardian-2")
    status = daemon.s.investigations.status(second["id"])
    assert len(status["compatible_hypotheses"]) == 2 and not status["delivery_allowed"]


def test_hypothesis_ledger_explains_refutation_with_real_receipts(engine):
    daemon, doc = engine
    run_both(daemon, doc)
    ledger = {h["id"]: h for h in daemon.s.investigations.status(doc["id"])["hypothesis_ledger"]}
    assert ledger["mechanism"]["state"] == "compatible_not_proven"
    assert ledger["display_only"]["state"] == "refuted_in_declared_scope"
    rejection = ledger["display_only"]["refutations"][0]
    assert rejection["predicted"] == "holds" and rejection["observed"] == "violated"
    assert len(rejection["evidence"]) == 12


def test_cancelled_investigation_cannot_launch_more_work(engine):
    daemon, doc = engine
    daemon.control("dispatch", "cancel_task", task_id=doc["root_task_id"])
    with pytest.raises(BusinessError, match="cancelled"):
        daemon.s.investigations.dispatch(doc["id"], "dispatch")
    assert not daemon.s.investigations.status(doc["id"])["delivery_allowed"]


def test_pending_or_failed_agent_and_open_objection_block_delivery(engine):
    daemon, doc = engine
    run_both(daemon, doc)
    run_both(daemon, doc, "impact_regression", "worker-2", "guardian-2")
    assert daemon.s.investigations.status(doc["id"])["delivery_allowed"]
    child = orch.create_subtask(daemon.s, sender="dispatch", recipient="worker-1", title="unfinished", instructions="extra coverage", parent_task_id=doc["root_task_id"])
    assert not daemon.s.investigations.status(doc["id"])["delivery_allowed"]
    with daemon.s.db.tx() as connection:
        connection.execute("UPDATE tasks SET state='finished',outcome='done' WHERE id=?", (child["task_id"],))
    obj = orch.raise_objection(daemon.s, task_id=doc["root_task_id"], by="logic", text="missing business scope", claim_ids=[])
    assert not daemon.s.investigations.status(doc["id"])["delivery_allowed"]
    orch.set_objection_status(daemon.s, obj["id"], "withdrawn", "logic", "now covered")
    assert daemon.s.investigations.status(doc["id"])["delivery_allowed"]


def test_business_budget_must_cover_both_actors_and_controls(engine):
    daemon, doc = engine
    altered = copy.deepcopy(doc["plan"])
    altered["max_executions"] = 12
    root = daemon.submit_task("dispatch", "budget", "scope")
    with pytest.raises(BusinessError, match="independent"):
        daemon.s.investigations.open(root["task_id"], "logic", altered)


def test_oracle_rejects_executable_rules_and_boolean_money_values():
    with pytest.raises(BusinessError):
        validate_contract({"id": "bad", "description": "bad", "rule": {"op": "eval", "code": "delete_all()"}})
    with pytest.raises(BusinessError):
        validate_contract({"id": "bad", "description": "bad", "rule": {"op": "sum_equal", "parts": [{}], "total": "money"}})
    contract = {"id": "sum", "description": "conservation", "rule": {"op": "sum_equal", "parts": ["cash", "credit"], "total": "price"}}
    assert evaluate(contract, {"cash": 10, "credit": 20, "price": 30})["status"] == "holds"
    assert evaluate(contract, {"cash": 10, "credit": False, "price": 10})["status"] == "unknown"


def disagreeing_guardian(phase, repeat):
    return {"actual": 30, "expected": 30, "keys": ["guardian"]}


def test_disagreement_is_not_resolved_by_majority_or_model_confidence(engine):
    daemon, doc = engine
    old = daemon.s.investigations.registry.scenarios["duplicate"]
    daemon.s.investigations.registry.scenarios["duplicate"] = Scenario(old.id, old.code_version, old.worker, disagreeing_guardian, old.description)
    root = daemon.submit_task("dispatch", "disputed", "scope")
    second = daemon.s.investigations.open(root["task_id"], "logic", doc["plan"])
    run_both(daemon, second)
    status = daemon.s.investigations.status(second["id"])
    assert status["checks"][0]["state"] == "disputed" and not status["delivery_allowed"]


def test_registered_adapter_cannot_be_swapped_after_plan(engine):
    daemon, doc = engine
    old = daemon.s.investigations.registry.scenarios["duplicate"]
    daemon.s.investigations.registry.scenarios["duplicate"] = Scenario(old.id, old.code_version, old.worker, disagreeing_guardian, old.description)
    sub = daemon.s.investigations.dispatch(doc["id"], "dispatch", check_id="distinguish", worker="worker-1")
    daemon.s.investigations.run(doc["id"], "distinguish", "worker-1", sub["task_id"], "internal")
    guardian = orch.create_subtask(daemon.s, sender="system", recipient="guardian-1", title="review", instructions="independent", parent_task_id=doc["root_task_id"], review_of=sub["task_id"])
    with pytest.raises(BusinessError, match="harness changed"):
        daemon.s.investigations.run(doc["id"], "distinguish", "guardian-1", guardian["task_id"], "internal")


def test_typed_event_production_consumption_path_is_not_reversed():
    graph = Graph({name: Node(name, "symbol", name) for name in ("producer", "event", "consumer", "reader")})
    graph.add_edge(Edge("producer", "emits", "event"))
    graph.add_edge(Edge("event", "consumes", "consumer"))
    graph.add_edge(Edge("event", "consumes", "reader"))
    result = candidates(graph, ["consumer", "reader"])
    shared = {row["entity"] for row in result["candidates"]}
    assert shared == {"event", "producer"}


def test_delivery_memory_uses_gated_outcome_not_unaccepted_head_draft(tmp_path):
    async def check():
        cfg = configuration(tmp_path, "duplicate", early_delivery=True)
        daemon = Daemon(cfg, poll_s=0.02)
        prepare(daemon.s)
        await daemon.start()
        try:
            sub = daemon.submit_task("dispatch", "early", "investigate")
            report = await asyncio.wait_for(daemon.wait_for_report(sub["task_id"]), 15)
            assert report["body"]["outcome"] == "blocked"
            summaries = [n for n in daemon.s.notes.by_task(sub["task_id"]) if n["kind"] == "summary"]
            assert summaries and "blocked" in summaries[-1]["text"]
        finally:
            await daemon.stop()
    asyncio.run(check())
