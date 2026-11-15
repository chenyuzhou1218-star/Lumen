"""Long-term memory, batch 1 (docs/adr/0006): recall reads the live status of the claims a note
cites (M1), and follows the coupling graph to notes about coupled entities (M2). M3 (one note
per claim at task end) is covered end to end in test_agent.py."""

from __future__ import annotations

import pytest

from codedoctor import claim_rules
from codedoctor.agents.tools import format_recalled
from codedoctor.currency import snapshot_version
from codedoctor.graph.model import Edge, Graph, Node
from codedoctor.memory import related
from codedoctor.services import Services

AUTHOR = {"kind": "agent", "id": "doctor", "role": "general",
          "model": {"provider": "scripted", "model": "m", "endpoint_profile": "fake"}, "task_id": "task_01JB8Z2000000000000000TK01"}
BUY = "ent:symbol:shop-api:server/shop.py#ShopService.buy"
CHECKOUT_PY = "from server.wallet import spend_gold\n\n\ndef checkout(player, price):\n    spend_gold(player, price)\n"
WALLET_PY = "def spend_gold(player, amount):\n    player.gold -= amount\n"
SPEND = "ent:symbol:shop-demo:server/wallet.py#spend_gold"
CHECKOUT = "ent:symbol:shop-demo:server/checkout.py#checkout"


@pytest.fixture
def s(make_config, project):
    (project / "server" / "checkout.py").write_text(CHECKOUT_PY, encoding="utf-8")
    (project / "server" / "wallet.py").write_text(WALLET_PY, encoding="utf-8")
    services = Services.open(make_config())
    yield services
    services.db.close()


def _src(s) -> list[str]:
    return [s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]


def _claim(s, project, **extra) -> dict:
    ev_id, _ = s.evidence.add_code_excerpt(project, "server/shop.py", 6, 7, agent_id="doctor")
    d = {
        "claim_type": "hypothesis",
        "statement": {"text": "early return skips the orders write", "subject": BUY, "relation": "causes",
                      "object": "ent:stage:shop.buy/db-write"},
        "evidence_level": "inferred",
        "scope": {"code_version": snapshot_version(project)},
        "evidence": [{"id": ev_id, "role": "supports", "shows": "early return", "assert": [{"op": "text_contains", "text": "return None"}]}],
        "falsification": {"method": "test", "intervention": True, "description": "call buy() with equal versions"},
        **extra,
    }
    return s.claims.submit(d, author=AUTHOR)


def _refute(s, claim_id: str) -> None:
    proof = s.evidence.add_blob(b"replay: orders row written", "text/plain", source="tool", collected_by="test/1", agent_id="guardian-1")
    s.claims.add_review(claim_id, reviewer="guardian-1", verdict="counterexample", notes="replay wrote the order", evidence=[proof])
    assert claim_rules.evaluate(s, claim_id)["status"] == "refuted"


def _note(s, text: str, **kw) -> dict:
    return s.notes.write(owner="doctor", scope="project", kind=kw.pop("kind", "fact"), sources=_src(s), text=text, **kw)


# --- M1: claim status is read live -------------------------------------------------------------

def test_note_shows_its_claims_current_status(s, project):
    c = _claim(s, project)
    note = _note(s, "buy() early return skips the orders write", claims=[c["id"]])
    [hit] = s.notes.recall("orders write", reader="doctor")
    assert hit.flags == [f"UNVERIFIED: {c['id']}"]

    s.claims.add_review(c["id"], reviewer="guardian-1", verdict="reverified", notes="re-read it",
                        evidence=[c["evidence"][0]["id"]])
    assert claim_rules.evaluate(s, c["id"])["status"] == "supported"
    [hit] = s.notes.recall("orders write", reader="doctor")
    assert hit.note["id"] == note["id"] and hit.flags == [f"VERIFIED: {c['id']}"]


def test_refuted_memory_is_flagged_and_ranked_below_unrefuted(s, project):
    c = _claim(s, project)
    wrong = _note(s, "orders write is skipped by the version check", claims=[c["id"]])
    plain = _note(s, "orders write is skipped when the session expired")
    _refute(s, c["id"])
    hits = s.notes.recall("orders write skipped", reader="doctor")
    assert [h.note["id"] for h in hits] == [plain["id"], wrong["id"]]  # still recalled: knowing what was ruled out matters
    assert hits[1].flags == [f"REFUTED (disproven; do not rely on it): {c['id']}"] and hits[0].flags == []
    text = format_recalled(s, hits)
    assert f"[REFUTED (disproven; do not rely on it): {c['id']}]" in text


def test_superseded_claim_is_followed_to_its_replacement(s, project):
    old = _claim(s, project)
    new = _claim(s, project, supersedes=old["id"], evidence_level="inferred")
    assert s.claims.get(old["id"])["status"] == "superseded"
    _note(s, "orders write skipped (first analysis)", claims=[old["id"]])
    _refute(s, new["id"])
    [hit] = s.notes.recall("orders write", reader="doctor")
    assert hit.flags == [f"REFUTED (disproven; do not rely on it): {old['id']} (superseded by {new['id']})"]
    assert s.notes.claim_states([old["id"]]) == {old["id"]: ("refuted", new["id"])}


def test_unknown_claims_are_flagged_not_trusted(s):
    _note(s, "orders write skipped", claims=["clm_01JB8Z8000000000000000CM99"])
    [hit] = s.notes.recall("orders write", reader="doctor")
    assert hit.flags == ["CLAIM NOT FOUND: clm_01JB8Z8000000000000000CM99"]


def test_specific_notes_outrank_a_summary_with_the_same_words(s):
    summary = _note(s, "Task ended done. The orders write is skipped.", kind="summary")
    fact = _note(s, "The orders write is skipped.")
    assert [h.note["id"] for h in s.notes.recall("orders write skipped", reader="doctor")] == [fact["id"], summary["id"]]


# --- M2: recall follows the coupling graph -------------------------------------------------------

def test_recall_reaches_notes_about_coupled_modules(s):
    s.graph.build()
    note = _note(s, "deducts without a lock; two concurrent requests can both pass the balance check", entities=[SPEND])

    assert s.notes.recall("why does checkout sometimes fail", reader="doctor") == []  # no word in common
    [hit] = related.recall(s, "why does checkout sometimes fail", reader="doctor")
    assert hit.note["id"] == note["id"]
    assert hit.via == "affected by 'checkout': checkout -calls-> spend_gold"
    assert "(recalled through coupling: affected by 'checkout': checkout -calls-> spend_gold)" in format_recalled(s, [hit])
    assert related.recall(s, "why does checkout sometimes fail", reader="doctor", follow_coupling=False) == []


def test_coupling_is_followed_upstream_and_closer_entities_rank_higher(s):
    s.graph.build()
    near = _note(s, "checkout is called from the cart page", entities=[CHECKOUT])
    far = _note(s, "buy() compares gold before the version check", entities=["ent:symbol:shop-demo:server/shop.py#ShopService.buy"])
    hits = related.recall(s, "spend_gold", reader="doctor")
    assert [h.note["id"] for h in hits] == [near["id"], far["id"]]  # 1 hop upstream, then 2 hops downstream
    assert hits[0].via == "affects 'spend_gold': checkout -calls-> spend_gold"
    assert hits[1].via == ("affected by 'spend_gold': spend_gold -writes-> py/gold, ShopService.buy -reads-> py/gold")


def test_a_file_path_seeds_the_symbols_it_defines(s):
    s.graph.build()
    note = _note(s, "balance check is not atomic", entities=[SPEND])
    [hit] = related.recall(s, "look at server/wallet.py", reader="doctor")
    assert hit.note["id"] == note["id"] and hit.via is None  # named directly (through its file), not via coupling


def test_no_graph_means_text_recall_only(s):
    _note(s, "balance check is not atomic", entities=[SPEND])
    assert related.coupled(s, "checkout spend_gold") == {}  # never built: recall does not start a build
    assert s.graph.meta() == {}


def test_ambiguous_names_are_not_used_as_seeds():
    g = Graph()
    for i in range(5):
        g.add_node(Node(f"ent:symbol:svc:m{i}.py#Handler.save", "symbol", "Handler.save", f"m{i}.py", 1))
    g.add_node(Node("ent:symbol:svc:wallet.py#spend_gold", "symbol", "spend_gold", "wallet.py", 1))
    found = related.seeds(g, "save fails after spend_gold")
    assert found == {"ent:symbol:svc:wallet.py#spend_gold": "spend_gold"}


def test_expansion_stops_at_the_depth_limit():
    g = Graph(edges=[Edge(f"ent:symbol:svc:a.py#f{i}", "calls", f"ent:symbol:svc:a.py#f{i + 1}") for i in range(5)])
    out = related.expand(g, {"ent:symbol:svc:a.py#f0": "f0"})
    assert sorted(out) == ["ent:symbol:svc:a.py#f0", "ent:symbol:svc:a.py#f1", "ent:symbol:svc:a.py#f2"]
    assert out["ent:symbol:svc:a.py#f2"][0] == 2


def test_entity_index_is_backfilled_when_upgrading_from_version_3(tmp_path):
    import json

    from codedoctor.store import db as dbmod

    path = tmp_path / "v3.sqlite3"
    d = dbmod.Database(path)
    doc = {"id": "mem_01JB8ZA000000000000000NT01", "entities": [BUY]}
    with d.tx() as c:
        c.execute("INSERT INTO notes (id, scope, owner, kind, created_at, doc) VALUES (?,?,?,?,?,?)",
                  (doc["id"], "project", "doctor", "fact", "2026-10-24T00:00:00Z", json.dumps(doc)))
        c.execute("DELETE FROM note_entities")
        c.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
    d.close()
    d = dbmod.Database(path)
    try:
        assert [r["entity"] for r in d.query("SELECT entity FROM note_entities")] == [BUY]
        assert d.one("SELECT value FROM meta WHERE key='schema_version'")["value"] == str(dbmod.SCHEMA_VERSION)
    finally:
        d.close()
