"""Anomaly inbox and detail-checklist tools (ADR 0014)."""

from __future__ import annotations

from codedoctor.agents import orchestration as orch
from codedoctor.agents.anomalies import DECISIONS, KINDS, REASONING, AnomalyError
from codedoctor.agents.tools import _EV_ITEMS, DEFAULT_TOOLS, TOOLS, Tool, ToolContext, ToolResult, _err, _obj

_TEXT = {"type": "string", "minLength": 1}


def report_anomaly(ctx: ToolContext, args: dict) -> ToolResult:
    s = ctx.services
    try:
        doc, merged = s.anomalies.report(
            task_id=ctx.task_id, by=ctx.agent_id, role=ctx.role, kind=args["kind"], title=args["title"],
            observed=args["observed"], surface=args["surface"], where=args.get("where"), entities=args.get("entities"),
            evidence=args.get("evidence"), hypothesis=args.get("hypothesis", False))
    except AnomalyError as e:
        return _err(str(e))
    root = doc["root_task_id"]
    woke = s.anomalies.ensure_assessment(root) if doc["urgent"] else None
    if merged:
        text = (f"{doc['id']} already in the inbox: recorded as occurrence {len(doc['occurrences'])} with your evidence "
                "(nothing is dropped).")
    else:
        text = f"recorded {doc['id']} in the anomaly inbox of {root}."
    if woke:
        text += f" It is urgent: the logic head was woken to assess it ({woke['task_id']})."
    elif doc["urgent"]:
        text += " It is urgent: the heads see it immediately."
    else:
        text += " The logic head will assess it in its next review; delivery waits until it has decided."
    if doc.get("related") and not merged:
        text += (f" Similar deferred anomalies exist ({', '.join(doc['related'])}): they will be reassessed for a "
                 "common root cause.")
    return ToolResult(ok=True, content=text)


def anomaly_inbox(ctx: ToolContext, args: dict) -> ToolResult:
    s = ctx.services
    if args.get("anomaly_id"):
        a = s.anomalies.get(args["anomaly_id"])
        if a is None:
            return _err(f"unknown anomaly {args['anomaly_id']}")
        lines = [s.anomalies.describe(a), "", "occurrences:"]
        lines += [f"- {o['at']} {o['by']} in {o['task_id']}: {o['observed'][:500]} (evidence: {', '.join(o['evidence']) or 'none'})"
                  for o in a["occurrences"][-20:]]
        if a.get("decision"):
            d = a["decision"]
            lines += ["", "decision reasoning:"] + [f"- {k}: {v}" for k, v in d["reasoning"].items()]
        text = "\n".join(lines)
    else:
        root = orch.root_of(s, ctx.task_id)
        text = s.anomalies.inbox_text(root) + "\n\n" + s.anomalies.checklist_text(root)
    # anomaly text was written by agents from what they saw in the project: data, and as sensitive as the code
    return ToolResult(ok=True, content=text, external=True, data_class=s.config.code_data_class)


def decide_anomaly(ctx: ToolContext, args: dict) -> ToolResult:
    s = ctx.services
    a = s.anomalies.get(args["anomaly_id"])
    if a is None:
        return _err(f"unknown anomaly {args['anomaly_id']}")
    if ctx.role != "head_logic":
        # a single agent, or the worker of 双人互检, decides the anomalies of the investigation it runs for the user
        root = orch.root_of(s, ctx.task_id)
        if a["root_task_id"] != root or (orch.task_row(s, root) or {}).get("agent") != ctx.agent_id:
            return _err("only the logic head decides anomalies; you can decide only those of an investigation you run "
                        "for the user yourself")
    try:
        doc = s.anomalies.decide(args["anomaly_id"], by=ctx.agent_id, decision=args["decision"],
                                 coupling_impact=args["coupling_impact"], reasoning=args["reasoning"],
                                 rationale=args["rationale"], basis_evidence=args.get("basis_evidence"),
                                 basis_hypothesis=args.get("basis_hypothesis", ""), falsification=args.get("falsification", ""))
    except AnomalyError as e:
        return _err(str(e))
    d = doc["decision"]
    nxt = {"fix_now": "The dispatch head delegates the fix and an independent verification (delegate with anomaly=...).",
           "expand": "The dispatch head delegates a wider investigation (delegate with anomaly=...).",
           "backlog": "It stays on record and is reassessed when a similar symptom appears.",
           "confirm": "It stays on record until it is shown to be intended or a defect."}[doc["status"]]
    return ToolResult(ok=True, content=f"{doc['id']}: {DECISIONS[doc['status']]}; surface {doc['surface']} x coupling impact "
                                       f"{d['coupling_impact']} -> {d['handling']} (priority P{d['priority']}). {nxt}")


def resolve_anomaly(ctx: ToolContext, args: dict) -> ToolResult:
    a = ctx.services.anomalies.get(args["anomaly_id"])
    if a is None:
        return _err(f"unknown anomaly {args['anomaly_id']}")
    if ctx.role != "head_logic" and a["root_task_id"] != orch.root_of(ctx.services, ctx.task_id):
        return _err("you can resolve only the anomalies of your own investigation")
    try:
        doc = ctx.services.anomalies.resolve(args["anomaly_id"], by=ctx.agent_id, note=args["note"], claims=args.get("claims"),
                                             evidence=args.get("evidence"), by_design=args.get("by_design", False))
    except AnomalyError as e:
        return _err(str(e))
    return ToolResult(ok=True, content=f"{doc['id']} resolved" + (" (intended behaviour)" if doc["resolution"]["by_design"] else "")
                                       + ". The record and all its occurrences stay.")


def checklist_update(ctx: ToolContext, args: dict) -> ToolResult:
    s = ctx.services
    root = orch.root_of(s, ctx.task_id)
    if args.get("item") or args.get("add"):
        try:
            s.anomalies.update_check(root, by=ctx.agent_id, item=args.get("item"), add_title=args.get("add"),
                                     claims=args.get("claims"), evidence=args.get("evidence"),
                                     not_applicable=args.get("not_applicable"))
        except AnomalyError as e:
            return _err(str(e))
    return ToolResult(ok=True, content=s.anomalies.checklist_text(root))


_REASONING = {"type": "object", "properties": {k: {"type": "string", "minLength": 2, "maxLength": 2000, "description": q}
                                               for k, q in REASONING.items()},
              "required": list(REASONING), "additionalProperties": False}

NEW_TOOLS = [
    Tool("report_anomaly",
         "Report ANY anomaly you notice to the investigation's anomaly inbox, however small: crash, database error, a business "
         "flow that sometimes fails, a button that cannot be clicked, a missing pixel or icon, wrong or misplaced text, an "
         "animation missing a frame, an unusual log warning, or a coupling you suspect (hypothesis=true if not observed). "
         "Small is not a reason to skip it, and do not inflate it either. surface: how big it looks ('small' / 'large'). "
         "Cite the evidence you saw it in. Repeats are merged, never dropped. Kinds: " + ", ".join(KINDS) + ".",
         _obj({"kind": {"enum": list(KINDS)}, "title": {"type": "string", "minLength": 1, "maxLength": 300},
               "observed": {"type": "string", "minLength": 1, "maxLength": 4000}, "surface": {"enum": ["small", "large"]},
               "where": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 20,
                         "description": "files with lines, screens, routes ('server/shop.py:42', 'shop page, buy button')"},
               "entities": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 20},
               "evidence": _EV_ITEMS, "hypothesis": {"type": "boolean"}},
              ["kind", "title", "observed", "surface"]),
         report_anomaly, effect_class="internal", retry_safe=False),
    Tool("anomaly_inbox", "The investigation's anomaly inbox (status, decisions, occurrences) and detail checklist; with "
                          "anomaly_id, one anomaly in full.",
         _obj({"anomaly_id": {"type": "string", "pattern": "^anm_"}}, []), anomaly_inbox),
    Tool("decide_anomaly",
         "Decide one anomaly after answering the micro-anomaly questions (reasoning). decision: fix_now (evidence is clear and "
         "it can be handled safely), expand (a deeper coupled failure is possible), backlog (real but low impact now), "
         "confirm (cannot tell yet whether it is intended). coupling_impact: 'small' / 'large' - large needs basis_evidence, or "
         "basis_hypothesis plus falsification. The program sets the priority from surface x coupling impact.",
         _obj({"anomaly_id": {"type": "string", "pattern": "^anm_"}, "decision": {"enum": list(DECISIONS)},
               "coupling_impact": {"enum": ["small", "large"]}, "reasoning": _REASONING,
               "rationale": {"type": "string", "minLength": 1, "maxLength": 4000}, "basis_evidence": _EV_ITEMS,
               "basis_hypothesis": {"type": "string", "maxLength": 2000}, "falsification": {"type": "string", "maxLength": 2000}},
              ["anomaly_id", "decision", "coupling_impact", "reasoning", "rationale"]),
         decide_anomaly, effect_class="internal", retry_safe=False),
    Tool("resolve_anomaly", "Mark an anomaly resolved: cite a claim whose status is 'supported' (re-checked by a guardian), or "
                            "by_design=true with evidence that it is intended. The record stays.",
         _obj({"anomaly_id": {"type": "string", "pattern": "^anm_"}, "note": {"type": "string", "minLength": 1, "maxLength": 4000},
               "claims": {"type": "array", "items": {"type": "string", "pattern": "^clm_"}, "maxItems": 20},
               "evidence": _EV_ITEMS, "by_design": {"type": "boolean"}}, ["anomaly_id", "note"]),
         resolve_anomaly, effect_class="internal", retry_safe=False),
    Tool("checklist_update", "Show the detail checklist, or attach claims / evidence to an item, add an item (add), or mark it not "
                             "applicable with a reason. An item counts as confirmed only when an attached claim is 'supported'.",
         _obj({"item": {"type": "string", "maxLength": 40}, "add": {"type": "string", "minLength": 1, "maxLength": 200},
               "claims": {"type": "array", "items": {"type": "string", "pattern": "^clm_"}, "maxItems": 20},
               "evidence": _EV_ITEMS, "not_applicable": {"type": "string", "maxLength": 2000}}, []),
         checklist_update, effect_class="internal", retry_safe=False),
]
for _t in NEW_TOOLS:
    TOOLS[_t.name] = _t

for _role, _names in {
    "general": ["report_anomaly", "anomaly_inbox", "decide_anomaly", "resolve_anomaly", "checklist_update"],
    "head_logic": ["report_anomaly", "anomaly_inbox", "decide_anomaly", "resolve_anomaly", "checklist_update"],
    "head_dispatch": ["anomaly_inbox", "resolve_anomaly", "checklist_update"],
    "worker": ["report_anomaly", "anomaly_inbox", "checklist_update", "decide_anomaly"],
    "investigator": ["report_anomaly", "anomaly_inbox", "checklist_update", "decide_anomaly"],
    "guardian": ["report_anomaly", "anomaly_inbox"],
}.items():
    DEFAULT_TOOLS[_role].extend(_names)
