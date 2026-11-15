"""Four-level evidence validation (schemas/evidence/validation-result).

  1 exists     the id is registered
  2 integrity  the stored bytes still hash to the recorded sha256
  3 binding    the evidence belongs to the code/config/db version, trace and action the claim is about
  4 support    the evidence really shows what the claim says: every predicate evaluates true
               (machine_verified), or a reviewer other than the author re-checked it
               (independently_verified)

An id merely existing never counts as support.
"""

from __future__ import annotations

import json
import re
from typing import Any

from codedoctor import ids
from codedoctor.protocol import semantic
from codedoctor.protocol.registry import validator as schema_validator

SCHEMA = "evidence/validation-result.schema.json"
VALIDATOR_ID = "evidence.validate/0.1.0"
# Linear-time subset only: no backreferences or lookaround (see docs/protocol/evidence-protocol-v0.md).
_UNSAFE_REGEX = re.compile(r"\\[1-9]|\(\?[=!<]|\(\?P=")
_JSON_KINDS = {"span", "trace", "action", "gap", "corr", "health", "coverage", "db", "test"}
_TEXT_KINDS = {"code", "log", "blob"}


def _pointer(doc: Any, pointer: str) -> Any:
    for part in pointer.split("/")[1:] if pointer else []:
        part = part.replace("~1", "/").replace("~0", "~")
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def evaluate(pred: dict, kind: str, raw: bytes) -> tuple[str, str]:
    """('true' | 'false' | 'inapplicable' | 'error', detail)"""
    op = pred["op"]
    if op == "exists":
        return "true", ""
    try:
        if op in ("text_contains", "text_matches"):
            if kind not in _TEXT_KINDS:
                return "inapplicable", f"{op} applies to code, log and text blobs, not {kind}"
            text = raw.decode("utf-8", errors="replace")
            if op == "text_contains":
                return ("true" if pred["text"] in text else "false"), ""
            if _UNSAFE_REGEX.search(pred["regex"]):
                return "error", "regex uses backreferences or lookaround"
            return ("true" if re.search(pred["regex"], text) else "false"), ""
        if kind not in _JSON_KINDS:
            return "inapplicable", f"{op} needs structured evidence, not {kind}"
        doc = json.loads(raw)
        if op == "field_equals":
            return ("true" if _pointer(doc, pred["pointer"]) == pred["value"] else "false"), ""
        if op == "test_outcome":
            if kind != "test":
                return "inapplicable", "test_outcome applies to test evidence"
            return ("true" if doc.get("outcome") == pred["outcome"] else "false"), ""
        if op == "gap_verdict":
            if kind != "gap":
                return "inapplicable", "gap_verdict applies to gap assessments"
            return ("true" if doc.get("verdict") == pred["verdict"] else "false"), ""
        if kind != "span":
            return "inapplicable", f"{op} applies to spans"
        attrs = doc.get("attributes", {})
        if op == "attr_equals":
            return ("true" if attrs.get(pred["attr"]) == pred["value"] else "false"), ""
        if op == "attr_in":
            return ("true" if attrs.get(pred["attr"]) in pred["values"] else "false"), ""
        if op == "attr_absent":
            return ("true" if pred["attr"] not in attrs else "false"), ""
        if op == "status_is":
            return ("true" if doc.get("status", {}).get("code") == pred["code"] else "false"), ""
        if op == "duration_ms":
            ms = (int(doc["end_time_unix_nano"]) - int(doc["start_time_unix_nano"])) / 1e6
            ok = {"gt": ms > pred["ms"], "gte": ms >= pred["ms"], "lt": ms < pred["ms"], "lte": ms <= pred["ms"]}[pred["cmp"]]
            return ("true" if ok else "false"), f"{ms:.1f} ms"
    except (ValueError, KeyError, IndexError, TypeError, re.error) as e:
        return "error", f"{type(e).__name__}: {e}"
    return "error", f"unknown op {op}"


def _binding(claim: dict, ref: dict, record: dict) -> tuple[str, list[dict]]:
    scope, actual = claim["scope"], record.get("binding", {})
    expect = ref.get("expect_binding") or {}
    checks: list[tuple[str, Any]] = []
    for key in ("code_version", "config_version", "db_schema_version"):
        want = expect.get(key, scope.get(key))
        if want is not None and key in actual:
            checks.append((key, want))
    mismatches = [{"field": k, "expected": w, "actual": actual[k]} for k, w in checks if actual[k] != w]
    for key, scope_key in (("trace_id", "trace_ids"), ("action_id", "action_ids")):
        if key not in actual:
            continue
        if key in expect:
            checks.append((key, expect[key]))
            if actual[key] != expect[key]:
                mismatches.append({"field": key, "expected": expect[key], "actual": actual[key]})
        elif scope.get(scope_key):
            checks.append((key, scope[scope_key]))
            if actual[key] not in scope[scope_key]:
                mismatches.append({"field": key, "expected": " | ".join(scope[scope_key]), "actual": actual[key]})
    if mismatches:
        return "fail", mismatches
    return ("pass" if checks else "not_checked"), []


def validate_claim(services, claim: dict, reviews: list[dict], current_code_version: str | None = None) -> dict:
    """Run all four levels for every cited item. `reviews` are this claim's stored reviews."""
    reverified = [r for r in reviews if r["verdict"] == "reverified" and r["reviewer"] != claim["author"]["id"]]
    results, reasons = [], set()
    for ref in claim.get("evidence", []):
        r: dict = {"id": ref["id"], "role": ref["role"]}
        record = services.evidence.get(ref["id"])
        if record is None:
            r.update(exists="fail", integrity="skipped", binding="skipped", support="skipped")
            reasons.add("evidence_missing")
            results.append(r)
            continue
        r["exists"] = "pass"
        if not services.blobs.intact(record["content"]["sha256"]):
            r.update(integrity="fail", binding="skipped", support="skipped")
            reasons.add("evidence_tampered")
            results.append(r)
            continue
        r["integrity"] = "pass"
        binding, mismatches = _binding(claim, ref, record)
        r["binding"] = binding
        if binding == "fail":
            r.update(binding_mismatches=mismatches, support="skipped")
            reasons.add("binding_mismatch")
            results.append(r)
            continue
        preds = ref.get("assert", [])
        if preds:
            raw = services.blobs.get(record["content"]["sha256"])
            outcomes = [evaluate(p, record["kind"], raw) for p in preds]
            r["predicate_results"] = [{"index": i, "result": res, **({"detail": d} if d else {})} for i, (res, d) in enumerate(outcomes)]
            kinds = {res for res, _ in outcomes}
            if "false" in kinds:
                r["support"] = "contradicted"
                if ref["role"] == "supports":
                    reasons.add("evidence_contradicts_claim")
            elif kinds == {"true"}:
                r["support"] = "machine_verified"
            else:
                r["support"] = "inapplicable" if "inapplicable" in kinds else "unverified"
        else:
            r["support"] = "unverified"
        if r["support"] in ("unverified", "inapplicable") and reverified:
            rev = reverified[0]
            r.update(support="independently_verified", verified_by={"agent_id": rev["reviewer"], "review_id": rev["review_id"]})
        if ref["role"] == "supports" and r["support"] not in ("machine_verified", "independently_verified"):
            reasons.add("support_unverified")
        results.append(r)

    supports = [r for r in results if r["role"] == "supports"]
    if reasons & {"evidence_missing", "evidence_tampered", "binding_mismatch", "evidence_contradicts_claim"}:
        overall = "rejected"
    elif not supports:
        overall = "accepted_support_unverified"
        reasons.add("no_supporting_evidence")
    elif "support_unverified" in reasons:
        overall = "accepted_support_unverified"
    else:
        overall = "accepted"
    doc = {"cd_schema": "cd.evidence.validation/0", "id": ids.new_id("val"), "claim_id": claim["id"], "validated_at": ids.now(),
           "validator": VALIDATOR_ID, "refs": results, "overall": overall, "reasons": sorted(reasons)}
    if current_code_version:
        doc["code_version"] = current_code_version
    errors = list(schema_validator(SCHEMA).iter_errors(doc))
    if errors:
        raise ValueError(f"validator produced an invalid result: {errors[0].message}")
    if semantic.check(SCHEMA, doc):
        raise ValueError(f"validator produced an inconsistent result: {semantic.check(SCHEMA, doc)}")
    return doc
