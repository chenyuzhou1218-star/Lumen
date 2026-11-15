from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from codedoctor.config import ClusterPolicy, ConfigError, parse
from codedoctor.agents.daemon import Daemon
from codedoctor.cluster.coupling import blast_radius
from codedoctor.graph.model import Graph, Node, Edge
from codedoctor.models import scripted
from tools.business_cluster_demo import configuration


def raw_config(tmp_path, pairs=1):
    agents = [{"id": "dispatch", "role": "head_dispatch", "endpoint": "scripted", "model": "user-head-a"},
              {"id": "logic", "role": "head_logic", "endpoint": "scripted", "model": "user-head-b"}]
    for i in range(pairs):
        agents += [{"id": f"w{i}", "role": "worker", "endpoint": "scripted", "model": "user-worker"},
                   {"id": f"g{i}", "role": "guardian", "endpoint": "scripted", "model": "user-guardian", "supervises": f"w{i}"}]
    return {"cd_schema": "cd.config.project/0", "project": {"name": "topology", "root": str(tmp_path)},
            "endpoints": [{"id": "scripted", "kind": "scripted", "base_url": "scripted:", "local": True}],
            "agents": agents, "cluster": {"enabled": True, "max_agents": 40}}


def test_user_sets_limit_with_two_heads_and_nineteen_pairs(tmp_path):
    raw = raw_config(tmp_path, 19)
    assert len(parse(raw).agents) == 40
    raw["cluster"]["max_agents"] = 39
    with pytest.raises(ConfigError, match="count"):
        parse(raw)


def test_hard_limit_applies_even_when_cluster_disabled(tmp_path):
    raw = raw_config(tmp_path, 20)
    raw.pop("cluster")
    with pytest.raises(ConfigError):
        parse(raw)


@pytest.mark.parametrize("mutation", ["missing_guardian", "duplicate_pair", "extra_head", "no_heads"])
def test_invalid_supervision_or_head_counts_fail_closed(tmp_path, mutation):
    raw = raw_config(tmp_path, 2)
    if mutation == "missing_guardian":
        raw["agents"].pop()
    elif mutation == "duplicate_pair":
        raw["agents"][-1]["supervises"] = "w0"
    elif mutation == "extra_head":
        raw["agents"].append({**raw["agents"][0], "id": "third-head"})
    else:
        raw["agents"] = raw["agents"][2:]
    with pytest.raises(ConfigError):
        parse(raw)


def test_large_context_is_a_user_budget_not_a_claim_of_model_capacity(tmp_path):
    raw = raw_config(tmp_path)
    raw["agents"][0]["context_budget_tokens"] = 500_000_000
    cfg = parse(raw)
    assert cfg.agents["dispatch"].context_budget_tokens == 500_000_000
    assert cfg.agents["dispatch"].primary.model == "user-head-a"
    assert not cfg.agents["dispatch"].fallbacks


def setup_daemon(tmp_path, **policy):
    cfg = configuration(tmp_path, "duplicate")
    return Daemon(replace(cfg, cluster=ClusterPolicy(enabled=True, foresight=True, interval_s=0.1, **policy)))


def finish_cycles(daemon):
    with daemon.s.db.tx() as connection:
        connection.execute("UPDATE tasks SET state='finished',outcome='done'")
        connection.execute("UPDATE messages SET delivered_at='unit-test'")


def test_idle_heads_continue_while_worker_is_busy_and_never_duplicate(tmp_path):
    daemon = setup_daemon(tmp_path)
    try:
        daemon.submit_task("worker-1", "long-running", "worker stays busy")
        assert len(daemon.foresight.tick(now=10000)) == 2
        assert not daemon.foresight.tick(now=10001)  # heads already own queued cycles
        with daemon.s.db.tx() as connection:
            connection.execute("UPDATE tasks SET state='finished',outcome='done' WHERE agent IN ('dispatch','logic')")
            connection.execute("UPDATE messages SET delivered_at='unit-test' WHERE recipient IN ('dispatch','logic')")
        assert len(daemon.foresight.tick(now=10002)) == 2
        assert daemon.s.db.one("SELECT state FROM tasks WHERE agent='worker-1'")["state"] == "queued"
    finally:
        daemon.s.db.close()


def test_pause_pending_controls_and_hourly_reservations_are_respected(tmp_path):
    daemon = setup_daemon(tmp_path, reserved_tokens_per_hour=40000)
    try:
        assert len(daemon.foresight.tick(now=10000)) == 2
        finish_cycles(daemon)
        assert not daemon.foresight.tick(now=10002)  # reservation persists even with zero reported tokens
        assert len(daemon.foresight.tick(now=13601)) == 2
        finish_cycles(daemon)
        daemon.control("dispatch", "pause")
        daemon.agents["logic"]._set_state("paused", "user pause")
        assert not daemon.foresight.tick(now=17202)
    finally:
        daemon.s.db.close()


def test_two_scheduler_callers_reserve_only_two_head_cycles(tmp_path):
    daemon = setup_daemon(tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: daemon.foresight.tick(now=10000), range(2)))
        assert sum(len(result) for result in results) == 2
        assert len(daemon.s.db.query("SELECT * FROM cluster_foresight_cycles")) == 2
    finally:
        daemon.s.db.close()


def test_restart_keeps_cycle_limit_and_no_default_background_calls(tmp_path):
    daemon = setup_daemon(tmp_path, reserved_tokens_per_hour=40000)
    cfg = daemon.config
    daemon.foresight.tick(now=10000)
    finish_cycles(daemon)
    daemon.s.db.close()
    restarted = Daemon(cfg)
    try:
        assert not restarted.foresight.tick(now=10001)
        assert len(restarted.foresight.status()["recent_cycles"]) == 2
    finally:
        restarted.s.db.close()
    disabled = Daemon(replace(cfg, cluster=ClusterPolicy()))
    try:
        assert not disabled.foresight.tick()
        assert not disabled.foresight.status()["enabled"]
    finally:
        disabled.s.db.close()


def test_foresight_never_downgrades_sensitive_previous_task_context(tmp_path):
    daemon = setup_daemon(tmp_path)
    try:
        daemon.submit_task("worker-1", "sensitive", "private evidence", data_class="local_only")
        cycles = daemon.foresight.tick(now=10000)
        assert len(cycles) == 2
        for cycle in cycles:
            messages = daemon.s.bus.list(task_id=cycle["task_id"])
            assert messages[0]["data_class"] == "local_only"
    finally:
        daemon.s.db.close()


@pytest.mark.asyncio
async def test_actual_daemon_calls_both_user_models_in_successive_cycles(tmp_path):
    daemon = setup_daemon(tmp_path)
    for head in ("dispatch", "logic"):
        model = daemon.config.agents[head].primary.model
        scripted.register(model, [{"text": "Unverified risk hypothesis; obtain evidence and falsify alternatives."}] * 8)
    try:
        await daemon.start()
        deadline = asyncio.get_running_loop().time() + 8
        while asyncio.get_running_loop().time() < deadline:
            rows = daemon.s.db.query("SELECT agent,COUNT(*) AS n FROM tasks WHERE state='finished' GROUP BY agent")
            if {row["agent"]: row["n"] for row in rows}.get("dispatch", 0) >= 2 and {row["agent"]: row["n"] for row in rows}.get("logic", 0) >= 2:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("heads did not complete two actual reasoning cycles")
        assert len(daemon.s.models.client("scripted").calls) >= 4
        assert all(row["reserved"] == 20000 for row in daemon.s.db.query("SELECT * FROM cluster_foresight_cycles"))
    finally:
        await daemon.stop()


def test_thousands_of_influence_nodes_are_traversed_without_recursion():
    graph = Graph()
    for i in range(3001):
        graph.add_node(Node(f"n{i}", "symbol", f"f{i}", "system.py", i + 1))
        if i:
            graph.add_edge(Edge(f"n{i}", "calls", f"n{i-1}", path="system.py", line=i + 1))
    graph.add_edge(Edge("n0", "calls", "n3000"))  # cycle
    result = blast_radius(graph, "n0")
    assert result["affected_count"] == 3000
    assert not result["truncated"] and not result["causality_proven"]
    assert result["affected"][-1]["via"] == "n2999"
    assert blast_radius(graph, "n0", max_nodes=100)["truncated"]
    assert blast_radius(graph, "n0", depth=10)["affected_count"] == 10
