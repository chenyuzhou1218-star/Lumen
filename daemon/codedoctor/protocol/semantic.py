"""Cross-field rules that JSON Schema cannot express (numeric order of decimal
strings, equality between two fields, self-references).

This is the reference implementation the daemon's ingest and evidence validator
must match. Rules that need other documents (does the cited span exist, is the
reviewer different from the author) belong to the evidence validator, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterator


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    message: str


RuleFn = Callable[[dict], Iterator[Violation]]
_RULES: dict[str, list[RuleFn]] = {}


def rule(*schema_names: str) -> Callable[[RuleFn], RuleFn]:
    def register(fn: RuleFn) -> RuleFn:
        for name in schema_names:
            _RULES.setdefault(name, []).append(fn)
        return fn

    return register


def check(schema_name: str, instance: dict) -> list[Violation]:
    """Run semantic rules. Call only on instances that already pass the schema."""
    return [v for fn in _RULES.get(schema_name, []) for v in fn(instance)]


def _ordered(start: str, end: str) -> bool:
    return int(start) <= int(end)


_LINE_RANGE = re.compile(r":L(\d+)-L(\d+)$")


def _line_range_ok(evidence_id: str) -> bool:
    m = _LINE_RANGE.search(evidence_id)
    return m is None or int(m.group(1)) <= int(m.group(2))


def _evidence_ids(obj) -> Iterator[tuple[str, str]]:
    """Every string in obj that looks like an evidence id, with its JSON path."""
    stack = [("", obj)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            stack.extend((f"{path}/{k}", v) for k, v in node.items())
        elif isinstance(node, list):
            stack.extend((f"{path}/{i}", v) for i, v in enumerate(node))
        elif isinstance(node, str) and node.startswith("ev:"):
            yield path, node


# --- event/span ------------------------------------------------------------

@rule("event/span.schema.json")
def span_time_order(span: dict) -> Iterator[Violation]:
    if not _ordered(span["start_time_unix_nano"], span["end_time_unix_nano"]):
        yield Violation("SPAN_TIME_ORDER", "/end_time_unix_nano", "span ends before it starts")


@rule("event/span.schema.json")
def span_self_parent(span: dict) -> Iterator[Violation]:
    if span.get("parent_span_id") == span["span_id"]:
        yield Violation("SPAN_SELF_PARENT", "/parent_span_id", "span is its own parent")
    for i, link in enumerate(span.get("links", [])):
        if link["trace_id"] == span["trace_id"] and link["span_id"] == span["span_id"]:
            yield Violation("SPAN_SELF_LINK", f"/links/{i}", "span links to itself")


@rule("event/span.schema.json")
def span_event_times(span: dict) -> Iterator[Violation]:
    for i, ev in enumerate(span.get("events", [])):
        t = int(ev["time_unix_nano"])
        if not int(span["start_time_unix_nano"]) <= t <= int(span["end_time_unix_nano"]):
            yield Violation("SPAN_EVENT_OUTSIDE", f"/events/{i}", "span event outside the span's time range")


# --- windows / ranges shared by several records ------------------------------

@rule("event/gap-assessment.schema.json", "event/telemetry-health.schema.json")
def window_order(doc: dict) -> Iterator[Violation]:
    w = doc["window"]
    if not _ordered(w["start_unix_nano"], w["end_unix_nano"]):
        yield Violation("WINDOW_ORDER", "/window", "window ends before it starts")


@rule("event/gap-assessment.schema.json")
def absent_only_after_window(doc: dict) -> Iterator[Violation]:
    """confirmed_absent means late spans are no longer expected: it cannot be decided before the window has ended
    (ChatGPT review R2). Clock skew between hosts is a separate check (clock_skew_bounded)."""
    if doc["verdict"] != "confirmed_absent":
        return
    at = datetime.fromisoformat(doc["assessed_at"].replace("Z", "+00:00"))
    at_ns = int(at.timestamp()) * 1_000_000_000 + at.microsecond * 1000
    if at_ns < int(doc["window"]["end_unix_nano"]):
        yield Violation("ABSENT_BEFORE_WINDOW_END", "/assessed_at", "confirmed_absent assessed before the window ended")


@rule("evidence/evidence-record.schema.json")
def record_time_range(rec: dict) -> Iterator[Violation]:
    tr = rec["binding"].get("time_range")
    if tr and not _ordered(tr["start_unix_nano"], tr["end_unix_nano"]):
        yield Violation("WINDOW_ORDER", "/binding/time_range", "time range ends before it starts")


@rule(
    "evidence/evidence-record.schema.json",
    "evidence/evidence-ref.schema.json",
    "claim/claim.schema.json",
    "event/gap-assessment.schema.json",
    "event/action.schema.json",
)
def evidence_line_ranges(doc: dict) -> Iterator[Violation]:
    for path, ev_id in _evidence_ids(doc):
        if not _line_range_ok(ev_id):
            yield Violation("LINE_RANGE_ORDER", path, f"line range in {ev_id!r} is reversed")


@rule("evidence/evidence-ref.schema.json")
def ref_locator_order(ref: dict) -> Iterator[Violation]:
    loc = ref.get("locator", {})
    if "line_end" in loc and loc["line_end"] < loc["line_start"]:
        yield Violation("LINE_RANGE_ORDER", "/locator", "locator line_end < line_start")


# --- event/action --------------------------------------------------------------

@rule("event/action.schema.json")
def action_id_matches(action: dict) -> Iterator[Violation]:
    if action["id"] != f"ev:action:{action['action_id']}":
        yield Violation("ACTION_ID_MISMATCH", "/id", "id must be 'ev:action:' + action_id")


@rule("event/action.schema.json")
def action_root_trace(action: dict) -> Iterator[Violation]:
    root_trace = action["root"].split(":", 2)[2].split("/")[0]
    roots = [t["trace_id"] for t in action["traces"] if t["joined_by"] == "root"]
    if roots and roots[0] != root_trace:
        yield Violation("ACTION_ROOT_TRACE", "/traces", "trace joined as 'root' is not the root span's trace")
    ids = [t["trace_id"] for t in action["traces"]]
    if len(ids) != len(set(ids)):
        yield Violation("ACTION_DUPLICATE_TRACE", "/traces", "a trace is listed twice")


@rule("event/action.schema.json")
def action_time_order(action: dict) -> Iterator[Violation]:
    end = action.get("end_time_unix_nano")
    if end is not None and not _ordered(action["start_time_unix_nano"], end):
        yield Violation("ACTION_TIME_ORDER", "/end_time_unix_nano", "action ends before it starts")


# --- event/ws-correlation -----------------------------------------------------

@rule("event/ws-correlation.schema.json")
def corr_distinct(corr: dict) -> Iterator[Violation]:
    if corr["send"] == corr["recv"]:
        yield Violation("CORR_SAME_SPAN", "/recv", "send and recv are the same span")


# --- event/chain-template -------------------------------------------------------

@rule("event/chain-template.schema.json")
def template_stage_refs(tpl: dict) -> Iterator[Violation]:
    ids = [s["id"] for s in tpl["stages"]]
    if len(ids) != len(set(ids)):
        yield Violation("TEMPLATE_DUPLICATE_STAGE", "/stages", "duplicate stage id")
    seen: set[str] = set()
    for i, stage in enumerate(tpl["stages"]):
        for dep in stage.get("after", []):
            if dep not in seen:
                yield Violation(
                    "TEMPLATE_STAGE_ORDER",
                    f"/stages/{i}/after",
                    f"stage {stage['id']!r} depends on {dep!r}, which is not an earlier stage",
                )
        seen.add(stage["id"])


# --- claim ---------------------------------------------------------------------

@rule("claim/claim.schema.json")
def claim_self_reference(claim: dict) -> Iterator[Violation]:
    if claim["id"] in claim.get("depends_on", []):
        yield Violation("CLAIM_SELF_DEPENDENCY", "/depends_on", "claim depends on itself")
    if claim.get("supersedes") == claim["id"]:
        yield Violation("CLAIM_SELF_SUPERSEDE", "/supersedes", "claim supersedes itself")


@rule("claim/claim.schema.json")
def claim_subject_object(claim: dict) -> Iterator[Violation]:
    st = claim["statement"]
    if isinstance(st["object"], str) and st["object"] == st["subject"]:
        yield Violation("CLAIM_REFLEXIVE", "/statement/object", "subject and object are the same entity")


# --- evidence/validation-result -------------------------------------------------

@rule("evidence/validation-result.schema.json")
def validation_reasons(result: dict) -> Iterator[Violation]:
    if result["overall"] != "accepted" and not result.get("reasons"):
        yield Violation("VALIDATION_REASON_MISSING", "/reasons", "non-accepted result must list reasons")
