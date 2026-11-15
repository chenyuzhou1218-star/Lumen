"""Coupling graph: extraction from Python and JavaScript, queries, and the risk detectors,
checked against samples/shop-coupling whose defects are known (see its README)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codedoctor.graph.build import build
from codedoctor.graph.risks import detect
from codedoctor.graph.service import edge_doc
from codedoctor.protocol.registry import validator

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "shop-coupling"
V = "wt-" + "0" * 64


@pytest.fixture(scope="module")
def graph():
    g, info = build(SAMPLE, "shop")
    assert info["parse_errors"] == {}
    return g


def has(g, src, rel, dst, **kw):
    for e in g.edges:
        if e.src == src and e.rel == rel and e.dst == dst and all(getattr(e, k) == v for k, v in kw.items()):
            return e
    return None


S = "ent:symbol:shop:"


def test_python_routes_calls_state_and_tables(graph):
    g = graph
    assert has(g, "ent:route:shop:POST:/api/shop/buy", "handles", S + "server/shop.py#buy", resolution="exact")
    assert has(g, S + "server/shop.py#buy", "calls", S + "server/wallet.py#spend_gold", resolution="exact")
    assert has(g, S + "server/session.py#reconnect", "calls", S + "server/rewards.py#settle", resolution="exact")
    assert has(g, S + "server/wallet.py#add_gold", "calls", S + "server/db.py#execute", resolution="exact")  # module alias
    e = has(g, S + "server/wallet.py#add_gold", "writes", "ent:state:shop:py/gold", resolution="heuristic")
    assert (e.path, e.line) == ("server/wallet.py", 6)
    assert has(g, S + "server/wallet.py#spend_gold", "writes", "ent:table:main:players")
    assert has(g, S + "server/wallet.py#spend_gold", "writes", "ent:table:main:ledger")
    assert has(g, "ent:file:shop:server/shop.py", "imports", "ent:file:shop:server/wallet.py")


def test_javascript_http_events_and_state(graph):
    g = graph
    assert has(g, S + "web/shop.js#ShopUI.onBuyClick", "calls", "ent:route:shop:POST:/api/shop/buy")  # through retryFetch wrapper
    assert has(g, S + "web/shop.js#ShopUI.onBuyClick", "calls", S + "web/net.js#retryFetch", resolution="exact")  # ES import
    assert has(g, S + "web/shop.js#ShopUI.onBuyClick", "emits", "ent:event:shop:purchase_success")
    assert has(g, "ent:event:shop:purchase_success", "consumes", S + "web/hud.js#on_purchase_success")
    assert has(g, S + "web/hud.js#on_purchase_success", "writes", "ent:state:shop:js/gold")
    assert has(g, S + "web/match.js#finishMatch", "calls", "ent:route:shop:POST:/api/match/report")
    # client and server `gold` are different memory: never the same node
    assert "ent:state:shop:js/gold" in g.nodes and "ent:state:shop:py/gold" in g.nodes


def test_every_edge_is_schema_valid(graph):
    v = validator("graph/edge.schema.json")
    for e in graph.edges:
        errors = list(v.iter_errors(edge_doc(e, V)))
        assert not errors, (e.describe(), errors[0].message)


def test_all_planted_defects_are_detected(graph):
    risks = detect(graph, V)
    v = validator("graph/risk.schema.json")
    for r in risks:
        assert not list(v.iter_errors(r))
    by = {}
    for r in risks:
        by.setdefault(r["pattern"], []).append(r)

    gold = next(r for r in by["shared_state_multi_writer"] if r["entities"][0] == "ent:state:shop:py/gold")
    assert gold["severity"] == "high" and "3 entry points" in gold["explanation"]                       # defect 1
    retry_sources = {r["entities"][0] for r in by["retry_path_to_write"]}
    assert S + "server/session.py#reconnect" in retry_sources                                          # defect 2
    assert S + "web/net.js#retryFetch" in retry_sources                                                # defect 3
    assert any(r["entities"][0] == S + "server/wallet.py#spend_gold" for r in by["multi_write_without_transaction"])  # defect 4
    noop = by["silent_noop_path"][0]
    assert noop["entities"][0] == S + "server/wallet.py#spend_gold" and noop["locations"][0] == {"path": "server/wallet.py", "line": 12}  # 5
    assert by["listener_without_event"][0]["entities"][0] == "ent:event:shop:gold_changed"            # defect 6
    assert by["client_route_without_handler"][0]["entities"][0] == "ent:route:shop:POST:/api/match/report"  # defect 7


def test_common_cause_of_two_symptoms_is_the_shared_gold_state(graph):
    ranked = graph.common_cause(["ent:route:shop:POST:/api/shop/buy", "ent:route:shop:POST:/api/session/reconnect"])
    assert ranked[0]["entity"] == "ent:state:shop:py/gold" and ranked[0]["explains"] == 2
    top = {r["entity"] for r in ranked[:6]}
    assert "ent:table:main:ledger" in top


def test_impact_crosses_client_server_boundary(graph):
    imp = graph.impact(S + "server/wallet.py#spend_gold", 6)
    upstream = imp["affected_by"]
    assert "ent:route:shop:POST:/api/shop/buy" in upstream
    assert S + "web/shop.js#ShopUI.onBuyClick" in upstream  # the client button handler reaches the server function
    assert "ent:table:main:ledger" in imp["affects"]


def test_ambiguous_names_are_marked_and_not_followed(tmp_path):
    (tmp_path / "a.py").write_text("def persist(x):\n    x.total = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def persist(x):\n    x.balance = 2\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("def handler(o):\n    o.store.persist(o)\n", encoding="utf-8")
    g, _ = build(tmp_path, "amb")
    calls = [e for e in g.edges if e.rel == "calls" and e.src.endswith("c.py#handler")]
    assert {e.resolution for e in calls} == {"ambiguous"} and len(calls) == 2
    assert "ent:state:amb:py/balance" not in g.reach("ent:symbol:amb:c.py#handler", "down")


def test_service_persists_and_merges_claim_edges(make_config, project):
    from codedoctor.services import Services

    s = Services.open(make_config())
    try:
        meta = s.graph.build()
        assert meta["files"] == 1 and meta["stats"]["edges"] > 0
        ev, _ = s.evidence.add_code_excerpt(project, "server/shop.py", 6, 7, agent_id="doctor")
        from codedoctor.currency import snapshot_version
        s.claims.submit({
            "claim_type": "hypothesis", "evidence_level": "inferred",
            "statement": {"text": "buy affects orders", "subject": "ent:symbol:shop-demo:server/shop.py#ShopService.buy",
                          "relation": "affects", "object": "ent:table:main:orders"},
            "scope": {"code_version": snapshot_version(project)},
            "evidence": [{"id": ev, "role": "supports", "shows": "x"}],
            "falsification": {"method": "test", "description": "d"}},
            author={"kind": "agent", "id": "doctor", "role": "general", "model": {"provider": "scripted", "model": "m"},
                    "task_id": "task_01JB8Z2000000000000000TK01"})
        g = s.graph.graph()
        inferred = [e for e in g.edges if e.provenance == "inferred"]
        assert len(inferred) == 1 and inferred[0].claim.startswith("clm_")
        s2 = Services.open(make_config())  # reload from the database
        assert s2.graph.graph().stats()["edges"] == g.stats()["edges"]
        s2.db.close()
    finally:
        s.db.close()
