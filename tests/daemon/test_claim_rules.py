"""Hard requirements 3 (promotion rules) and 6 (versions and staleness)."""

from __future__ import annotations

import json

import pytest

from codedoctor import claim_rules, ids
from codedoctor.claims import ClaimRejected
from codedoctor.currency import snapshot_version, stale_notes
from codedoctor.agents.tools import format_recalled
from codedoctor.memory.notes import Recalled
from codedoctor.evidence.validator import evaluate
from codedoctor.protocol.registry import validator
from codedoctor.services import Services

AUTHOR = {"kind": "agent", "id": "doctor", "role": "general",
          "model": {"provider": "scripted", "model": "m", "endpoint_profile": "fake"}, "task_id": "task_01JB8Z2000000000000000TK01"}


@pytest.fixture
def s(make_config):
    services = Services.open(make_config())
    yield services
    services.db.close()


@pytest.fixture
def excerpt(s, project):
    ev_id, _ = s.evidence.add_code_excerpt(project, "server/shop.py", 6, 7, agent_id="doctor")
    return ev_id


def draft(ev_id, project, *, level="inferred", contains="return None", **extra):
    d = {
        "claim_type": "hypothesis",
        "statement": {"text": "early return skips the orders write", "subject": "ent:symbol:shop-api:server/shop.py#ShopService.buy",
                      "relation": "causes", "object": "ent:stage:shop.buy/db-write"},
        "evidence_level": level,
        "scope": {"code_version": snapshot_version(project)},
        "evidence": [{"id": ev_id, "role": "supports", "shows": "early return", "assert": [{"op": "text_contains", "text": contains}]}],
        "falsification": {"method": "test", "intervention": True, "description": "call buy() with equal versions"},
    }
    d.update(extra)
    return d


def test_author_cannot_review_or_promote_own_claim(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    with pytest.raises(ClaimRejected, match="own author"):
        s.claims.add_review(c["id"], reviewer="doctor", verdict="reverified", notes="looks right", evidence=[excerpt])
    r = claim_rules.evaluate(s, c["id"])
    assert r["status"] == "proposed"
    assert any("independent re-check" in m for m in r["missing"])
    assert s.claims.latest_validation(c["id"])["overall"] == "accepted"  # machine-verified, yet not promoted


def test_an_agent_reviewing_its_own_claim_is_told_there_is_nothing_to_do(s, excerpt, project):
    """A real guardian re-reviewed its own finding, got an error, and filed the refusal as an anomaly (twice)."""
    from codedoctor.agents.tools import TOOLS, ToolContext, execute

    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    ctx = ToolContext(services=s, agent_id="doctor", role="guardian", task_id="task_x", model={}, call_entry_id="jrn_x",
                      thread_id="thr_x", known_agents=set())
    res = execute(TOOLS["review_claim"], ctx, {"claim_id": c["id"], "verdict": "reverified", "notes": "mine"})
    assert res.ok and "your own claim" in res.content and "Nothing to do" in res.content
    assert s.claims.reviews(c["id"]) == [] and claim_rules.evaluate(s, c["id"])["status"] == "proposed"


def test_promotion_needs_validation_and_independent_recheck(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    s.claims.add_review(c["id"], reviewer="guardian-1", verdict="reverified", notes="re-read lines 6-7 myself", evidence=[excerpt])
    r = claim_rules.evaluate(s, c["id"])
    assert (r["before"], r["status"], r["changed"]) == ("proposed", "supported", True)
    [event] = s.claims.events(c["id"])
    assert event["rule"] == "promote_supported" and event["by"] == "system"
    assert event["basis"]["validation"] == r["validation"] and len(event["basis"]["reviews"]) == 1
    assert not list(validator("claim/status-event.schema.json").iter_errors(event))


def test_user_can_be_the_independent_reviewer(s, excerpt, project):
    d = draft(excerpt, project)
    d["evidence"][0].pop("assert")  # no machine-checkable predicate: only an independent check can verify support
    c = s.claims.submit(d, author=AUTHOR)
    assert claim_rules.evaluate(s, c["id"])["status"] == "proposed"
    assert s.claims.latest_validation(c["id"])["overall"] == "accepted_support_unverified"
    s.claims.add_review(c["id"], reviewer="user", verdict="reverified", notes="I checked it", evidence=[excerpt])
    assert claim_rules.evaluate(s, c["id"])["status"] == "supported"
    ref = s.claims.latest_validation(c["id"])["refs"][0]
    assert ref["support"] == "independently_verified" and ref["verified_by"]["agent_id"] == "user"


def test_speculation_is_never_promoted(s, excerpt, project):
    d = draft(excerpt, project, level="speculated")
    d["claim_type"], d["statement"]["relation"] = "risk_prediction", "may_cause"
    d["conditions"] = [{"text": "client retries", "fault_model": "fm:duplicate_request"}]
    c = s.claims.submit(d, author=AUTHOR)
    s.claims.add_review(c["id"], reviewer="guardian-1", verdict="reverified", notes="plausible", evidence=[excerpt])
    r = claim_rules.evaluate(s, c["id"])
    assert r["status"] == "proposed" and any("speculation is never promoted" in m for m in r["missing"])


def test_own_predicate_false_refutes(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project, contains="orders.insert"), author=AUTHOR)  # not in lines 6-7
    r = claim_rules.evaluate(s, c["id"])
    assert r["status"] == "refuted" and s.claims.events(c["id"])[0]["rule"] == "refute_contradicted"


def test_counterexample_refutes_but_needs_real_evidence(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    with pytest.raises(ClaimRejected, match="missing"):
        s.claims.add_review(c["id"], reviewer="guardian-1", verdict="counterexample", notes="trust me",
                            evidence=["ev:blob:" + "a" * 64])
    with pytest.raises(ClaimRejected):
        s.claims.add_review(c["id"], reviewer="guardian-1", verdict="counterexample", notes="no evidence at all")
    proof = s.evidence.add_blob(b"replay: orders row written", "text/plain", source="tool", collected_by="test/1", agent_id="guardian-1")
    s.claims.add_review(c["id"], reviewer="guardian-1", verdict="counterexample", notes="replay wrote the order", evidence=[proof])
    assert claim_rules.evaluate(s, c["id"])["status"] == "refuted"
    with pytest.raises(ClaimRejected, match="already refuted"):
        s.claims.withdraw(c["id"], "doctor", "too late")


def test_unsupported_dependency_and_later_doubts_block_promotion(s, excerpt, project):
    base = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    child = s.claims.submit(draft(excerpt, project, depends_on=[base["id"]]), author=AUTHOR)
    s.claims.add_review(child["id"], reviewer="guardian-1", verdict="reverified", notes="ok", evidence=[excerpt])
    r = claim_rules.evaluate(s, child["id"])
    assert r["status"] == "proposed" and any(base["id"] in m for m in r["missing"])

    s.claims.add_review(base["id"], reviewer="guardian-1", verdict="reverified", notes="ok", evidence=[excerpt])
    s.claims.add_review(base["id"], reviewer="guardian-2", verdict="insufficient_evidence", notes="no runtime trace yet")
    r = claim_rules.evaluate(s, base["id"])
    assert r["status"] == "proposed" and any("insufficient evidence" in m for m in r["missing"])


def test_evidence_from_another_version_is_rejected(s, excerpt, project):
    d = draft(excerpt, project)
    d["evidence"][0]["expect_binding"] = {"code_version": "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"}
    c = s.claims.submit(d, author=AUTHOR)
    claim_rules.evaluate(s, c["id"])
    v = s.claims.latest_validation(c["id"])
    assert v["overall"] == "rejected" and "binding_mismatch" in v["reasons"]
    assert v["refs"][0]["binding_mismatches"][0]["field"] == "code_version"
    assert s.claims.get(c["id"])["status"] == "proposed"


def test_tampered_evidence_rejects_validation(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    s.blobs.path(s.evidence.get(excerpt)["content"]["sha256"]).write_text("changed")
    claim_rules.evaluate(s, c["id"])
    assert "evidence_tampered" in s.claims.latest_validation(c["id"])["reasons"]


def test_changing_the_cited_lines_makes_a_supported_claim_stale(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    s.claims.add_review(c["id"], reviewer="guardian-1", verdict="reverified", notes="ok", evidence=[excerpt])
    assert claim_rules.evaluate(s, c["id"])["status"] == "supported"

    shop = project / "server" / "shop.py"
    shop.write_text("# a new header line\n" + shop.read_text(encoding="utf-8") + "\n# trailing\n", encoding="utf-8")
    assert claim_rules.refresh_all(s) == []  # edits elsewhere (and the excerpt moving) do not invalidate it
    assert s.claims.get(c["id"])["status"] == "supported"

    shop.write_text(shop.read_text(encoding="utf-8").replace("return None", "raise StaleInventory()"), encoding="utf-8")
    [changed] = claim_rules.refresh_all(s)
    assert changed["status"] == "needs_revalidation"
    event = s.claims.events(c["id"])[-1]
    assert event["rule"] == "stale_code" and "server/shop.py" in event["basis"]["detail"]

    # a stale claim is replaced by a new claim against the current code
    new_ev, _ = s.evidence.add_code_excerpt(project, "server/shop.py", 7, 8, agent_id="doctor")
    new = s.claims.submit(draft(new_ev, project, contains="raise StaleInventory()", supersedes=c["id"]), author=AUTHOR)
    assert s.claims.get(c["id"])["status"] == "superseded" and new["status"] == "proposed"


def test_claim_without_code_evidence_goes_stale_on_any_version_change(s, project):
    blob = s.evidence.add_blob(b"server log: 500 on /api/shop/buy", "text/plain", source="tool", collected_by="t/1", agent_id="doctor")
    d = {"claim_type": "finding",
         "statement": {"text": "buy fails with 500", "subject": "ent:route:shop-api:POST:/api/shop/buy", "relation": "fails_with", "object": {"value": 500}},
         "evidence_level": "observed", "scope": {"code_version": snapshot_version(project), "config_version": "sha256:aaa"},
         "evidence": [{"id": blob, "role": "supports", "shows": "500 in log", "assert": [{"op": "text_contains", "text": "500"}]}]}
    c = s.claims.submit(d, author=AUTHOR)
    assert claim_rules.evaluate(s, c["id"])["status"] == "proposed"
    r = claim_rules.evaluate(s, c["id"], current={"code_version": snapshot_version(project), "config_version": "sha256:bbb"})
    assert r["status"] == "needs_revalidation" and "config_version" in s.claims.events(c["id"])[-1]["basis"]["detail"]

    c2 = s.claims.submit(d, author=AUTHOR)
    (project / "README.md").write_text("changed\n", encoding="utf-8")
    assert claim_rules.evaluate(s, c2["id"])["status"] == "needs_revalidation"
    assert s.claims.events(c2["id"])[-1]["rule"] == "stale_version"


def test_outdated_memory_is_flagged_on_recall(s, excerpt, project):
    src = [s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]
    note = s.notes.write(owner="doctor", scope="agent", kind="fact", sources=src, evidence=[excerpt],
                         text="buy() returns None on version mismatch (server/shop.py:6-7)")
    assert stale_notes(s, [note]) == {}
    shop = project / "server" / "shop.py"
    shop.write_text(shop.read_text(encoding="utf-8").replace("return None", "raise StaleInventory()"), encoding="utf-8")
    stale = stale_notes(s, [note])
    assert "server/shop.py changed" in stale[note["id"]]
    assert "[POSSIBLY OUTDATED" in format_recalled(s, [Recalled(note, 1.0)])


def test_only_the_author_can_withdraw(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    with pytest.raises(ClaimRejected, match="only the author"):
        s.claims.withdraw(c["id"], "guardian-1", "not mine")
    s.claims.withdraw(c["id"], "doctor", "wrong file")
    assert s.claims.get(c["id"])["status"] == "withdrawn"


def test_status_cannot_be_set_by_an_agent_through_the_rules(s, excerpt, project):
    c = s.claims.submit(draft(excerpt, project), author=AUTHOR)
    with pytest.raises(ValueError, match="illegal status change"):
        s.claims.set_status(c["id"], "supported", by="doctor", rule="promote_supported",
                            basis={"validation": ids.new_id("val"), "reviews": [ids.new_id("rev")]})


@pytest.mark.parametrize("pred,kind,raw,expected", [
    ({"op": "attr_equals", "attr": "cd.ui.settle.result", "value": "no_change"}, "span",
     json.dumps({"attributes": {"cd.ui.settle.result": "no_change"}}).encode(), "true"),
    ({"op": "status_is", "code": "error"}, "span", json.dumps({"status": {"code": "ok"}}).encode(), "false"),
    ({"op": "duration_ms", "cmp": "gt", "ms": 500}, "span",
     json.dumps({"start_time_unix_nano": "0", "end_time_unix_nano": "1000000000"}).encode(), "true"),
    ({"op": "gap_verdict", "verdict": "confirmed_absent"}, "gap", json.dumps({"verdict": "unknown"}).encode(), "false"),
    ({"op": "field_equals", "pointer": "/checks/sampled/status", "value": "pass"}, "gap",
     json.dumps({"checks": {"sampled": {"status": "pass"}}}).encode(), "true"),
    ({"op": "text_matches", "regex": r"ECONN(RESET|REFUSED)"}, "log", b"error ECONNRESET at 12:00", "true"),
    ({"op": "text_matches", "regex": r"(a)\1"}, "log", b"aa", "error"),
    ({"op": "attr_equals", "attr": "x", "value": 1}, "log", b"x=1", "inapplicable"),
    ({"op": "test_outcome", "outcome": "failed"}, "test", json.dumps({"outcome": "failed"}).encode(), "true"),
])
def test_predicates(pred, kind, raw, expected):
    assert evaluate(pred, kind, raw)[0] == expected
