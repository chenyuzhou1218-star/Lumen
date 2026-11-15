"""When may a claim change status? (hard requirements 3 and 6)

Nobody stamps their own conclusion. The rule engine, not the author, moves a claim:

  proposed -> needs_revalidation   cited code changed, or code/config/db version changed (stale)
  proposed -> refuted              a reviewer other than the author gave a counterexample with intact evidence,
                                   or a supporting item's own predicate evaluates false
  proposed -> supported            all of:
                                     - evidence level is not 'speculated'
                                     - the 4-level evidence validation is 'accepted'
                                     - at least one 'reverified' review by someone other than the author
                                     - no 'insufficient_evidence' review after the latest re-check
                                     - every claim it depends on is itself 'supported'
                                     - it is not stale
  supported -> needs_revalidation  as above; a stale conclusion is not a current fact
  author:   -> withdrawn

Raising the evidence level (speculated -> inferred -> reproduced) is done by a NEW
claim that cites the new evidence and `supersedes` the old one; levels of an
existing claim never change. A stale claim is likewise replaced by a new claim
made against the current version.
"""

from __future__ import annotations

from codedoctor.claims import TERMINAL
from codedoctor.currency import claim_staleness, snapshot_version
from codedoctor.evidence.validator import validate_claim


def evaluate(services, claim_id: str, current: dict | None = None) -> dict:
    store = services.claims
    claim = store.get(claim_id)
    if claim is None:
        raise KeyError(claim_id)
    out = {"claim_id": claim_id, "before": claim["status"], "missing": [], "validation": None}

    def done(status: str) -> dict:
        out["status"] = status
        out["changed"] = status != out["before"]
        return out

    if claim["status"] in TERMINAL:
        out["missing"].append(f"claim is {claim['status']}; it can no longer change")
        return done(claim["status"])

    current = current or {"code_version": snapshot_version(services.config.root)}
    stale = claim_staleness(services, claim, current)
    if stale and claim["status"] in ("proposed", "supported"):
        rule, detail = stale
        store.set_status(claim_id, "needs_revalidation", by="system", rule=rule, basis={"detail": detail[:4000]})
        claim["status"] = "needs_revalidation"
    if claim["status"] == "needs_revalidation":
        out["missing"].append("stale: submit a new claim against the current version with 'supersedes' set to this one")
        return done("needs_revalidation")

    author = claim["author"]["id"]
    reviews = store.reviews(claim_id)
    for r in reviews:
        if r["verdict"] == "counterexample" and r["reviewer"] != author and \
                all(services.evidence.check(e) == "ok" for e in r.get("evidence", [])):
            store.set_status(claim_id, "refuted", by="system", rule="refute_counterexample",
                             basis={"reviews": [r["review_id"]], "evidence": r["evidence"]})
            return done("refuted")

    val = validate_claim(services, claim, reviews, current.get("code_version"))
    store.save_validation(val)
    out["validation"] = val["id"]
    if "evidence_contradicts_claim" in val["reasons"]:
        store.set_status(claim_id, "refuted", by="system", rule="refute_contradicted",
                         basis={"validation": val["id"], "detail": "a supporting item's predicate evaluated false"})
        return done("refuted")

    missing = out["missing"]
    if claim["evidence_level"] == "speculated":
        missing.append("speculation is never promoted: test it, then submit a new claim at a higher level that supersedes this one")
    if val["overall"] != "accepted":
        missing.append(f"evidence validation is {val['overall']} ({', '.join(val['reasons'])})")
    independent = [r for r in reviews if r["verdict"] == "reverified" and r["reviewer"] != author]
    if not independent:
        missing.append("needs an independent re-check: a 'reverified' review by an agent or user other than the author")
    else:
        # Order by position, not timestamp: two reviews can share a millisecond. store.reviews() is in creation order.
        last_ok = max(i for i, r in enumerate(reviews) if r in independent)
        if any(r["verdict"] == "insufficient_evidence" for r in reviews[last_ok + 1:]):
            missing.append("a reviewer reported insufficient evidence after the latest re-check")
    for dep in claim.get("depends_on", []):
        dep_claim = store.get(dep)
        if dep_claim is None or dep_claim["status"] != "supported":
            missing.append(f"depends on {dep}, which is {dep_claim['status'] if dep_claim else 'missing'}")

    if claim["status"] == "proposed" and not missing:
        store.set_status(claim_id, "supported", by="system", rule="promote_supported",
                         basis={"validation": val["id"], "reviews": [r["review_id"] for r in independent]})
        return done("supported")
    return done(claim["status"])


def refresh_all(services, current: dict | None = None) -> list[dict]:
    """Re-evaluate every open claim (e.g. after the code changed). Returns those whose status changed."""
    current = current or {"code_version": snapshot_version(services.config.root)}
    return [r for r in (evaluate(services, cid, current) for cid in services.claims.open_ids()) if r["changed"]]
