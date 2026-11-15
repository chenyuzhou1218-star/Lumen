"""What a model sends to submit_claim, reshaped before validation.

First real run (DeepSeek, 2026-10-27): the model found both planted bugs but spent half its token budget on seven
rejected drafts, because the tool showed only {"claim": object} and the errors did not say what an entity id looks
like. The tool now shows the claim's shape (PARAMETERS), unambiguous shorthand is reshaped here, and a bad entity
id gets an error with real ids to choose from. Nothing is guessed: claim type, evidence level, evidence role
beyond plain synonyms and falsification method stay the model's job. Every reshaping is reported back to the model.
"""

from __future__ import annotations

import json
import re

from codedoctor.graph.model import encode_path

CLAIM_TYPES = ["finding", "hypothesis", "risk_prediction", "fix_verification"]
LEVELS = ["observed", "reproduced", "inferred", "speculated"]
RELATIONS = ["calls", "handles", "reads", "writes", "emits", "consumes", "triggers", "renders", "depends_on",
             "shares_state_with", "precedes", "present_in", "absent_in", "fails_with", "violates", "causes", "may_cause",
             "affects", "fixed_by"]
METHODS = ["trace_query", "test", "fault_injection", "replay", "code_inspection", "db_query", "manual"]
_ENTITY = ("Entity id: ent:symbol:<project>:<path>#<name>, ent:file:<project>:<path>, ent:route:<project>:<METHOD>:<path>, "
           "... - use the exact ids graph_find / graph_neighbors return; a plain 'path#name' or project path is accepted")

PARAMETERS = {
    "type": "object",  # some models send a JSON string anyway: parse() accepts it
    "required": ["claim_type", "statement", "evidence_level", "scope", "evidence"],
    "properties": {
        "claim_type": {"enum": CLAIM_TYPES, "description": "finding: true now; hypothesis: an explanation to test; "
                                                           "risk_prediction: could fail under conditions; fix_verification"},
        "statement": {"type": "object", "required": ["text", "subject", "relation", "object"], "properties": {
            "text": {"type": "string"},
            "subject": {"type": "string", "description": _ENTITY},
            "relation": {"enum": RELATIONS},
            "object": {"description": "an entity id like subject, or {\"value\": \"...\"} for anything that is not a thing "
                                      "in the code (a symptom, a number)"}}},
        "evidence_level": {"enum": LEVELS, "description": "observed: runtime logs/db show it; reproduced: re-triggered; "
                                                          "inferred: read from code or other evidence; speculated: judgement"},
        "scope": {"type": "object", "properties": {"code_version": {
            "type": "string", "description": "the version part of your evidence ids: ev:code:<code_version>:<path>@..."}}},
        "evidence": {"type": "array", "items": {"type": "object", "required": ["id", "role", "shows"], "properties": {
            "id": {"type": "string", "description": "an evidence id a tool returned"},
            "role": {"enum": ["supports", "refutes", "context"]},
            "shows": {"type": "string"}}}},
        "falsification": {"type": "object", "required": ["method", "description"], "description": "required for "
                          "hypothesis and risk_prediction", "properties": {
                              "method": {"enum": METHODS}, "description": {"type": "string"}}},
        "conditions": {"type": "array", "items": {"type": "object", "required": ["text"],
                                                  "properties": {"text": {"type": "string"}}}},
        "depends_on": {"type": "array", "items": {"type": "string"}},
        "supersedes": {"type": "string"},
    },
}

_ROLES = {"primary": "supports", "supporting": "supports", "support": "supports", "supported": "supports",
          "refuting": "refutes", "refute": "refutes", "contradicts": "refutes", "background": "context"}
_SCOPE_KEYS = {"code_version", "config_version", "db_schema_version", "action_ids", "trace_ids", "services", "environment"}
_ROUTE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/\S*)$", re.I)
_CODE_EV = re.compile(r"^ev:code:([^:]+):")


def unwrap(args: dict):
    """The claim from submit_claim's arguments. Real run 6: models also sent the claim's fields without the 'claim'
    wrapper, or wrapped it twice; both are unambiguous."""
    if set(args) == {"claim"}:
        inner = args["claim"]
        if isinstance(inner, dict) and set(inner) == {"claim"}:
            return inner["claim"]
        return inner
    if "claim_type" in args or "statement" in args:
        return args
    raise ValueError("submit_claim takes one argument: claim (an object with claim_type, statement, ...)")


def parse(raw) -> dict:
    """The claim as an object; some models send it as a JSON string."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError("claim must be a JSON object")
    return raw


def normalize(draft: dict, svc: str, nodes: dict, root) -> tuple[dict, list[str]]:
    """Return (reshaped copy, what was changed)."""
    d = json.loads(json.dumps(draft))
    notes: list[str] = []
    st = d.get("statement")
    if isinstance(st, dict):
        for field in ("subject", "object"):
            v = st.get(field)
            if isinstance(v, str) and not v.startswith("ent:"):
                ent = _entity(v.strip(), svc, nodes, root)
                if ent:
                    st[field] = ent
                    notes.append(f"statement.{field} {v!r} -> {ent}")
                elif field == "object":
                    st[field] = {"value": v}
                    notes.append(f"statement.object {v!r} kept as a plain value (not a thing in the code)")
    ev = d.get("evidence")
    if isinstance(ev, list):
        for i, item in enumerate(ev):
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            if isinstance(role, str) and role.lower() in _ROLES:
                item["role"] = _ROLES[role.lower()]
                notes.append(f"evidence[{i}].role {role!r} -> {item['role']!r}")
            if isinstance(item.get("assert"), bool):
                item.pop("assert")
                notes.append(f"evidence[{i}].assert dropped (it takes predicates, not true/false)")
    cond = d.get("conditions")
    if isinstance(cond, str):
        d["conditions"] = cond = [cond]
        notes.append("conditions: a single text -> a list")
    if isinstance(cond, list):
        for i, c in enumerate(cond):
            if isinstance(c, str):
                cond[i] = {"text": c}
            elif isinstance(c, dict) and "text" not in c and set(c) <= {"description", "fault_model"} and "description" in c:
                c["text"] = c.pop("description")
    fals = d.get("falsification")
    if isinstance(fals, dict) and "description" not in fals and isinstance(fals.get("text"), str):
        fals["description"] = fals.pop("text")
    scope = d.get("scope")
    if isinstance(scope, dict):
        extra = sorted(set(scope) - _SCOPE_KEYS)
        for k in extra:
            scope.pop(k)
        if extra:
            notes.append(f"scope: dropped {extra} (scope says which code version the claim is about)")
    versions = {m.group(1) for item in (ev if isinstance(ev, list) else []) if isinstance(item, dict)
                for m in [_CODE_EV.match(str(item.get("id", "")))] if m}
    if len(versions) == 1 and (not isinstance(scope, dict) or not scope.get("code_version")):
        d["scope"] = {**(scope if isinstance(scope, dict) else {}), "code_version": next(iter(versions))}
        notes.append(f"scope.code_version taken from the cited evidence ({next(iter(versions))[:14]}...)")
    return d, notes


def _entity(text: str, svc: str, nodes: dict, root) -> str | None:
    m = _ROUTE.match(text)
    if m:
        ent = f"ent:route:{svc}:{m.group(1).upper()}:{m.group(2)}"
        return ent if ent in nodes else None
    if re.search(r"\s", text):
        return None
    path, _, name = text.partition("#")
    path = path.strip("/").replace("\\", "/")
    if not path or not (root / path).is_file():
        return None
    if name:
        return f"ent:symbol:{svc}:{encode_path(path)}#{name}"
    return f"ent:file:{svc}:{encode_path(path)}"


_LEVEL_NEEDS = {
    "reproduced": "evidence_level 'reproduced' needs a supporting ev:test: id - the evidence run_command returns for a "
                  "run of the current code; a fix_verification must cite the test run after the fix. Without one, use "
                  "'inferred' (claim_type 'finding')",
    "observed": "evidence_level 'observed' needs supporting runtime telemetry (logs, traces); reading code is 'inferred'",
}


def explain(problems: list[str], draft: dict, nodes: dict) -> list[str]:
    """Replace the validator's 'not valid under any of the given schemas' for entity fields with something usable."""
    st = draft.get("statement") if isinstance(draft.get("statement"), dict) else {}
    out = []
    for p in problems:
        if p.startswith("evidence:") and "does not contain items matching" in p and draft.get("evidence_level") in _LEVEL_NEEDS:
            out.append("evidence: " + _LEVEL_NEEDS[draft["evidence_level"]])
            continue
        field = next((f for f in ("subject", "object") if p.startswith(f"statement/{f}:")), None)
        if field and "is not valid under any of the given schemas" in p:
            v = st.get(field)
            hint = ", ".join(suggest(str(v), nodes)) or "none found - call graph_find first"
            p = (f"statement/{field}: {v!r} is not an entity id. {_ENTITY}. Closest ids in this project: {hint}"
                 + (". For a symptom or value that is not in the code use {\"value\": \"...\"}." if field == "object" else ""))
        out.append(p)
    return out


def suggest(text: str, nodes: dict, k: int = 3) -> list[str]:
    words = [w for w in re.split(r"[^A-Za-z0-9_]+", text.lower()) if len(w) > 2]
    if not words:
        return []
    scored = []
    for nid in nodes:
        low = nid.lower()
        hits = sum(1 for w in words if w in low)
        if hits:
            scored.append((-hits, len(nid), nid))
    return [nid for *_, nid in sorted(scored)[:k]]
