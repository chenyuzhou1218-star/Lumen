"""Coupling-graph tools (all roles) and cluster orchestration tools (heads)."""

from __future__ import annotations

import asyncio
import json

from codedoctor.agents import orchestration as orch
from codedoctor.agents import prompts
from codedoctor.agents.tools import _EV_ITEMS, TOOLS, Tool, ToolContext, ToolResult, _err, _obj
from codedoctor.graph.model import node_type


def _graph_result(ctx: ToolContext, text: str) -> ToolResult:
    # Names and paths come from the project's source code: untrusted, and as sensitive as the code.
    return ToolResult(ok=True, content=text, external=True, data_class=ctx.services.config.code_data_class)


def _short(entity: str) -> str:
    return entity.split(":", 3)[-1] if entity.startswith("ent:") else entity


def _node_line(g, entity: str) -> str:
    n = g.nodes.get(entity)
    loc = f"  @ {n.path}:{n.line}" if n and n.path else ""
    return f"{entity}{loc}"


# --- coupling graph -----------------------------------------------------------------------------

def graph_overview(ctx: ToolContext, args: dict) -> ToolResult:
    gs = ctx.services.graph
    meta = gs.ensure_built()
    g = gs.graph()
    entries = g.entry_points()
    shared = []
    for ent, n in g.nodes.items():
        if n.type in ("table", "state"):
            writers = {e.src for e in g.inc.get(ent, []) if e.rel == "writes"}
            if len(writers) >= 2:
                shared.append((len(writers), ent))
    shared.sort(reverse=True)
    lines = [
        f"Coupling graph of {ctx.services.config.name} (code version {meta['code_version'][:16]}..., built {meta['built_at']}):",
        f"{meta['files']} files ({meta['languages']}), {meta['stats']['nodes']} nodes, {meta['stats']['edges']} edges "
        f"{meta['stats']['edge_provenance']}, parse errors: {len(meta.get('parse_errors', {}))}",
        f"node types: {meta['stats']['node_types']}",
        f"entry points (route handlers, event/message consumers): {len(entries)}",
        "",
        "Most widely written state/tables (writers):",
        *[f"  {n:>3}  {ent}" for n, ent in shared[:12]],
        "",
        f"Risk findings by pattern/severity: {gs.risk_counts()}",
        "Top risks (use graph_risks for details):",
    ]
    for r in gs.risks(limit=args.get("risks", 10), min_severity="medium"):
        loc = r["locations"][0]
        lines.append(f"  [{r['severity']}] {r['id']} {r['pattern']}: {r['explanation'][:200]}  @ {loc['path']}:{loc['line']}")
    lines.append("\nEdges are static (from code), runtime, inferred (proposed claims) or verified (supported claims). "
                 "Static 'heuristic' and 'name_match' edges can be wrong: confirm with read_file before claiming.")
    return _graph_result(ctx, "\n".join(lines))


def graph_rebuild(ctx: ToolContext, args: dict) -> ToolResult:
    meta = ctx.services.graph.build()
    return _graph_result(ctx, f"rebuilt: {meta['files']} files, {meta['stats']['edges']} edges, {meta['risks']} risk findings, "
                              f"{meta['seconds']}s")


def graph_find(ctx: ToolContext, args: dict) -> ToolResult:
    ctx.services.graph.ensure_built()
    g = ctx.services.graph.graph()
    hits = g.find(args["query"], min(args.get("limit", 25), 100))
    if args.get("type"):
        hits = [n for n in hits if n.type == args["type"]]
    if not hits:
        return _graph_result(ctx, "(no matching entity)")
    return _graph_result(ctx, "\n".join(f"{n.type:<7} {_node_line(g, n.id)}" for n in hits))


def _resolve(ctx, text):
    g = ctx.services.graph.graph()
    n = g.resolve(text)
    return g, n


def graph_neighbors(ctx: ToolContext, args: dict) -> ToolResult:
    ctx.services.graph.ensure_built()
    g, n = _resolve(ctx, args["entity"])
    if n is None:
        return _err(f"no entity matches {args['entity']!r}; use graph_find")
    limit = min(args.get("limit", 40), 200)
    rels = set(args.get("relations", [])) or None
    out = [e for e in g.out.get(n.id, []) if not rels or e.rel in rels][:limit]
    inc = [e for e in g.inc.get(n.id, []) if not rels or e.rel in rels][:limit]
    lines = [f"{_node_line(g, n.id)}", f"outgoing ({len(g.out.get(n.id, []))}):"]
    lines += [f"  -{e.rel}-> {_short(e.dst)}  ({e.provenance}{', ' + e.resolution if e.resolution else ''})"
              f"{' @ ' + str(e.path) + ':' + str(e.line) if e.path else ''}" for e in out]
    lines.append(f"incoming ({len(g.inc.get(n.id, []))}):")
    lines += [f"  <-{e.rel}- {_short(e.src)}  ({e.provenance}{', ' + e.resolution if e.resolution else ''})"
              f"{' @ ' + str(e.path) + ':' + str(e.line) if e.path else ''}" for e in inc]
    return _graph_result(ctx, "\n".join(lines))


def graph_impact(ctx: ToolContext, args: dict) -> ToolResult:
    ctx.services.graph.ensure_built()
    g, n = _resolve(ctx, args["entity"])
    if n is None:
        return _err(f"no entity matches {args['entity']!r}; use graph_find")
    depth = min(args.get("depth", 4), 8)
    imp = g.impact(n.id, depth)
    lines = [f"Impact of {_node_line(g, n.id)} (depth {depth}; ambiguous name matches not followed):"]
    for title, key in (("AFFECTS (changing it can break these)", "affects"), ("AFFECTED BY (these can break it)", "affected_by")):
        items = sorted(((d, ent, p) for ent, (d, p) in imp[key].items() if ent != n.id and node_type(ent) != "file"),
                       key=lambda x: (x[0], node_type(x[1]) not in ("route", "state", "table", "event", "ws_msg"), x[1]))
        lines.append(f"\n{title}: {len(items)}")
        for d, ent, path in items[: args.get("limit", 40)]:
            via = path[-1]
            lines.append(f"  d={d} {_short(ent)}   via {via.rel} ({via.provenance}){' @ ' + str(via.path) + ':' + str(via.line) if via.path else ''}")
    return _graph_result(ctx, "\n".join(lines))


def graph_common_cause(ctx: ToolContext, args: dict) -> ToolResult:
    ctx.services.graph.ensure_built()
    g = ctx.services.graph.graph()
    resolved = []
    for text in args["symptoms"]:
        n = g.resolve(text)
        if n is None:
            return _err(f"no entity matches {text!r}; use graph_find")
        resolved.append(n.id)
    ranked = g.common_cause(resolved)
    if not ranked:
        return _graph_result(ctx, "No shared dependency or upstream cause found within the search depth.")
    lines = [f"Candidates shared by the symptoms {', '.join(_short(s) for s in resolved)} "
             "(ranked by how many symptoms they connect to; a candidate is a hypothesis to test, not a cause):"]
    for r in ranked[: min(args.get("limit", 10), 30)]:
        lines.append(f"\n- {_node_line(g, r['entity'])}  connects {r['explains']}/{r['of']} symptoms, total distance {r['total_distance']}")
        for s, path in r["paths"].items():
            lines.append(f"    from {_short(s)}: " + (" | ".join(p.split("  (")[0].replace("ent:", "") for p in path) or "(itself)"))
    return _graph_result(ctx, "\n".join(lines))


def graph_risks(ctx: ToolContext, args: dict) -> ToolResult:
    ctx.services.graph.ensure_built()
    found = ctx.services.graph.risks(limit=min(args.get("limit", 15), 100), pattern=args.get("pattern"),
                                     min_severity=args.get("min_severity", "medium"))
    if not found:
        return _graph_result(ctx, "(no risk findings at this severity)")
    lines = ["Structural risk leads (NOT confirmed bugs; turn the ones worth testing into risk_prediction claims):"]
    for r in found:
        locs = ", ".join(f"{l['path']}:{l['line']}" for l in r["locations"][:4])
        lines += [f"\n[{r['severity']}] {r['id']} {r['pattern']} ({r['fault_model']})", f"  {r['explanation']}",
                  f"  entities: {', '.join(r['entities'][:6])}", f"  at: {locs}", f"  verify: {r['how_to_verify']}"]
    return _graph_result(ctx, "\n".join(lines))


# --- cluster orchestration -------------------------------------------------------------------

def _over_budget(ctx: ToolContext) -> ToolResult | None:
    from codedoctor.agents.runtime import REVIEW_RESERVE

    used, limit, root = orch.cluster_budget(ctx.services, ctx.task_id)
    if used < limit * (1 - REVIEW_RESERVE):
        return None
    return ToolResult(ok=False, progress=False, content=(
        f"ERROR: the investigation's token budget for work is spent ({used} of {limit} tokens across all agents of {root}; "
        f"the last {int(REVIEW_RESERVE * 100)}% is kept for the guardians' reviews). No new subtasks: finish with the "
        "results you have and say what was not covered."))


def _context_block(ctx: ToolContext, claim_ids: list[str], evidence_ids: list[str]) -> tuple[str | None, str | None]:
    """(text to append to the subtask's instructions, error). Claims are quoted as data: their wording came from agents."""
    s = ctx.services
    lines = []
    for cid in claim_ids:
        c = s.claims.get(cid)
        if c is None:
            return None, f"unknown claim {cid}"
        st = c["statement"]
        obj = st["object"] if isinstance(st["object"], str) else json.dumps(st["object"]["value"], ensure_ascii=False)
        lines.append(f"- {c['id']} [{c['status']}, {c['evidence_level']}] by {c['author']['id']}: {st['text']}\n"
                     f"  {st['subject']} -{st['relation']}-> {obj}\n"
                     f"  evidence: {', '.join(r['id'] for r in c.get('evidence', [])) or 'none'}"
                     + (f"\n  falsify by ({c['falsification']['method']}): {c['falsification']['description']}" if c.get("falsification") else ""))
    for ev in evidence_ids:
        if s.evidence.check(ev) != "ok":
            return None, f"evidence {ev} is {s.evidence.check(ev)}"
    if not lines and not evidence_ids:
        return None, None
    parts = []
    if lines:
        parts.append("Claims to verify:\n" + "\n".join(lines))
    if evidence_ids:
        parts.append("Evidence to start from:\n" + "\n".join(f"- {e}" for e in evidence_ids))
    guide = ("\n\nHow to verify a claim listed above: re-check it yourself with your own tools. If it holds, submit a NEW claim "
             "citing evidence you obtained, with \"supersedes\" set to that claim's id (your guardian will re-check yours). "
             "If it does not hold, do not supersede it: say why in your answer and cite the evidence.") if lines else ""
    return (f"\n\nContext from {ctx.agent_id} (from the claim and evidence stores):\n"
            + prompts.wrap_untrusted("claims and evidence", "\n\n".join(parts)) + guide), None


def delegate(ctx: ToolContext, args: dict) -> ToolResult:
    cfg = ctx.services.config
    target = args["agent"]
    anomaly = None
    if args.get("anomaly"):
        anomaly = ctx.services.anomalies.get(args["anomaly"])
        if anomaly is None or anomaly["root_task_id"] != orch.root_of(ctx.services, ctx.task_id):
            return _err(f"unknown anomaly {args['anomaly']!r} in this investigation; see anomaly_inbox")
    # ADR 0014: an anomaly is verified independently - not by the worker whose work it came from
    origin = {anomaly["origin_worker"]} if anomaly and anomaly.get("origin_worker") else set()
    if target == "any":
        target = orch.pick_worker(ctx.services, exclude=origin) or target
    if target not in cfg.agents or cfg.agents[target].role not in orch.DELEGATE_ROLES:
        options = [a.id for a in cfg.agents.values() if a.role in orch.DELEGATE_ROLES]
        return _err(f"{target!r} is not a worker; you can delegate to: {', '.join(options) or '(none configured)'} or 'any'")
    others = [a.id for a in cfg.agents.values() if a.role in orch.DELEGATE_ROLES and a.id not in origin]
    if target in origin and others:
        return _err(f"{args['anomaly']} came from {target}'s work; give its verification to another worker "
                    f"({', '.join(others)}) or 'any', so it does not rest on the original judgement")
    if (stop := _over_budget(ctx)) is not None:
        return stop
    if not cfg.cluster.parallel_subtasks:
        running = orch.open_work(ctx.services, ctx.task_id)
        if running:
            return ToolResult(ok=False, progress=False, content=(
                f"ERROR: collaboration mode runs one subtask at a time and {running[0]['id']} ({running[0]['agent']}) is not "
                "finished; wait_for it first. (Parallel pairs are the advanced cluster mode, chosen by the user.)"))
    # before the file check: a repeated order would otherwise only hear that its files are taken
    dup = orch.open_duplicate(ctx.services, ctx.task_id, target, args["title"], args["instructions"])
    if dup:
        state = "already finished successfully" if dup["state"] == "finished" else f"still {dup['state']}"
        return ToolResult(ok=False, content=f"ERROR: duplicate work: {dup['id']} with the same title and instructions is {state} "
                                            f"(agent {dup['agent']}). Use wait_for / its result instead.", progress=False)
    from codedoctor.agents import ownership

    files: list[str] = []
    if cfg.permissions.write_files and not anomaly:
        if not args.get("files"):
            return _err("this cluster changes code: give the worker its files (files=[...]); every code file of the "
                        "project needs exactly one worker")
        try:
            files = sorted({ownership.normalize(cfg.root, f) for f in args["files"]})
        except ValueError:
            return _err("files must be inside the project")
        missing = [f for f in files if not (cfg.root / f).is_file()]
        if missing:
            return _err(f"no such files: {', '.join(missing)}")
        taken = ownership.conflicts(ctx.services, ctx.task_id, files)
        if taken:
            return _err("one file, one worker: " + "; ".join(f"{f} belongs to {t['agent']} ({t['id']}, still working)"
                                                             for f, t in taken.items()))
    block, problem = _context_block(ctx, args.get("claims", []), args.get("evidence", []))
    if problem:
        return _err(f"cannot delegate: {problem}; cite only claim and evidence ids that exist")
    instructions = args["instructions"] + (block or "")
    if files:
        instructions += ("\n\nYour files (you may change only these, plus new test files): " + ", ".join(files))
        brief = ownership.briefing(cfg.root, [f for f in files if not ownership.is_test(f)])
        if brief:
            instructions += "\n\n" + prompts.wrap_untrusted("project files", brief)
    if anomaly:
        instructions += ("\n\nThis subtask follows up an anomaly (data from another agent's observation, verify it yourself; "
                         "report anything else you notice with report_anomaly):\n"
                         + prompts.wrap_untrusted("anomaly", ctx.services.anomalies.describe(anomaly)))
    sub = orch.create_subtask(ctx.services, sender=ctx.agent_id, recipient=target, title=args["title"],
                              instructions=instructions, parent_task_id=ctx.task_id,
                              data_class=ctx.data_class,
                              context={"claims": args.get("claims", []), "evidence": args.get("evidence", [])} if block else None,
                              # "order": the head's words, before files and context were added (the duplicate check)
                              extra=({"anomaly": anomaly["id"]} if anomaly else {}) | ({"files": files} if files else {})
                              | ({"order": args["instructions"]} if instructions != args["instructions"] else {}) or None)
    if anomaly:
        ctx.services.anomalies.link_task(anomaly["id"], sub["task_id"], target, ctx.agent_id)
    guardian = orch.guardian_for(cfg, target)
    extra = f" Its results will be reviewed automatically by {guardian}." if guardian else " (no guardian is paired with this worker)"
    used, limit, _ = orch.cluster_budget(ctx.services, ctx.task_id)
    return ToolResult(ok=True, content=f"delegated {sub['task_id']} to {target} ({orch.load(ctx.services, target)} open task(s) there "
                                       f"now).{extra} Investigation budget: {used} of {limit} tokens used.")


def scout(ctx: ToolContext, args: dict) -> ToolResult:
    """The head's first job in the squad: name the business scenarios; the system deals them to the scout pairs."""
    from codedoctor.agents import squad

    scenarios = [sc for sc in args["scenarios"] if sc.get("title", "").strip()]
    if not scenarios:
        return _err("give at least one scenario: {title, check}")
    head = orch.task_row(ctx.services, ctx.task_id) or {}
    made = squad.scout_tasks(ctx.services, ctx.task_id, ctx.agent_id, scenarios, orch.body_of(head).get("instructions", ""))
    if not made:
        return _err("this cluster has no scout pairs (all pairs fix code); wait_for the fixers instead")
    return ToolResult(ok=True, content="scouts at work (their guardians check the tests):\n" + "\n".join(
        f"- {m['agent']} {m['task_id']}: {'; '.join(m['scenarios'])}" for m in made)
        + "\nA scout test that fails goes to the fixers automatically. Now wait_for; tell_fixers only for what the "
          "system cannot know (a pattern across several findings, a rule the tests do not show).")


def tell_fixers(ctx: ToolContext, args: dict) -> ToolResult:
    """The head's second job: pass a finding to the main pair (and the alternates) while they work."""
    from codedoctor.agents import squad

    told = squad.fixers(ctx.services, orch.root_of(ctx.services, ctx.task_id))
    if not told:
        return _err("no fixer is working any more; the result is being settled")
    for f in told:
        squad.post_note(ctx.services, f["id"], f"[from the dispatch head {ctx.agent_id}] {args['text']}")
    return ToolResult(ok=True, content="told " + ", ".join(f"{f['agent']} ({f['id']})" for f in told))


async def wait_for(ctx: ToolContext, args: dict) -> ToolResult:
    s = ctx.services
    ids = args.get("task_ids") or [c["id"] for c in orch.children(s, ctx.task_id) if not orch.body_of(c).get("review_of")]
    if not ids:
        return ToolResult(ok=False, content="ERROR: nothing to wait for; delegate first", progress=False)
    timeout = min(args.get("timeout_s", 900), 3600)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    root = orch.root_of(s, ctx.task_id)
    urgent_before = {a["id"] for a in s.anomalies.for_root(root) if a["urgent"]}
    woke = []
    while loop.time() < deadline and not all(orch.settled(s, t) for t in ids):
        if orch.is_cancelled(s, ctx.task_id):
            break
        if not args.get("task_ids"):  # "everything": subtasks the system starts meanwhile (squad backups) count too
            ids = [c["id"] for c in orch.children(s, ctx.task_id) if not orch.body_of(c).get("review_of")]
        # ADR 0014: a serious anomaly wakes the head at once instead of after the slowest subtask
        woke = [a for a in s.anomalies.for_root(root) if a["urgent"] and a["id"] not in urgent_before]
        if woke:
            break
        await asyncio.sleep(0.5)
    done = [t for t in ids if orch.settled(s, t)]
    pending = [t for t in ids if t not in done]
    report = {"finished": [orch.digest(s, t) for t in done], "still_running": [orch.digest(s, t) for t in pending]}
    if woke:
        report["woken_by_urgent_anomalies"] = [s.anomalies.describe(a) for a in woke]
    if done or woke:
        s.anomalies.ensure_assessment(root)  # small anomalies reach the logic head at the latest now
    items = s.anomalies.for_root(root)
    if items:
        report["anomaly_inbox"] = {st: sum(a["status"] == st for a in items) for st in ("new", "fix_now", "expand", "confirm",
                                                                                        "backlog", "resolved")}
    return ToolResult(ok=True, content=json.dumps(report, ensure_ascii=False, indent=1), external=True,
                      data_class=s.config.code_data_class, progress=bool(done or woke))


async def consult(ctx: ToolContext, args: dict) -> ToolResult:
    heads = orch.agents_with_role(ctx.services.config, "head_logic")
    if not heads:
        return _err("no head_logic agent is configured")
    if (stop := _over_budget(ctx)) is not None:
        return stop
    sub = orch.create_subtask(ctx.services, sender=ctx.agent_id, recipient=heads[0], title=args["question"][:200],
                              instructions=args["question"], parent_task_id=ctx.task_id, data_class=ctx.data_class)
    res = await wait_for(ctx, {"task_ids": [sub["task_id"]], "timeout_s": args.get("timeout_s", 1800)})
    return ToolResult(ok=res.ok, content=f"{heads[0]} answered ({sub['task_id']}):\n{res.content}", external=True,
                      data_class=res.data_class, progress=res.progress)


def task_status(ctx: ToolContext, args: dict) -> ToolResult:
    s = ctx.services
    kids = orch.children(s, ctx.task_id)
    lines = [f"Subtasks of {ctx.task_id}: {len(kids)}"]
    for c in kids:
        b = orch.body_of(c)
        tag = f"review of {b['review_of']}" if b.get("review_of") else "work"
        lines.append(f"- {c['id']} [{tag}] {c['agent']}: {c['state']}{'/' + c['outcome'] if c['outcome'] else ''}  {c['title'][:80]}")
        for cl in s.claims.by_task(c["id"]):
            lines.append(f"    claim {cl['id']} {cl['status']} ({cl['evidence_level']}): {cl['statement']['text'][:160]}")
    used, limit, root = orch.cluster_budget(s, ctx.task_id)
    lines.append(f"\nInvestigation budget ({root}, all agents): {used} of {limit} tokens used.")
    workers = [a.id for a in s.config.agents.values() if a.role in orch.DELEGATE_ROLES]
    lines.append("Workers (open tasks): " + ", ".join(f"{w} ({orch.load(s, w)})" for w in workers))
    root = orch.root_of(s, ctx.task_id)
    if s.anomalies.for_root(root):
        s.anomalies.ensure_assessment(root)
        lines.append("\n" + s.anomalies.inbox_text(root, limit=15))
    lines.append("\n" + s.anomalies.checklist_text(root))
    obj = orch.objections(s, root)
    if obj:
        lines.append("\nOPEN OBJECTIONS (delivery is blocked until they are withdrawn or the user decides):")
        lines += [f"- {o['id']} by {o['raised_by']}: {o['text'][:400]}" for o in obj]
    return ToolResult(ok=True, content="\n".join(lines), external=True, data_class=s.config.code_data_class)


def raise_objection(ctx: ToolContext, args: dict) -> ToolResult:
    doc = orch.raise_objection(ctx.services, task_id=ctx.task_id, by=ctx.agent_id, text=args["text"], claim_ids=args.get("claims", []))
    return ToolResult(ok=True, content=f"objection {doc['id']} recorded on {doc['root_task_id']}: delivery is blocked until you "
                                       "withdraw it or the user decides")


def withdraw_objection(ctx: ToolContext, args: dict) -> ToolResult:
    try:
        orch.set_objection_status(ctx.services, args["objection_id"], "withdrawn", ctx.agent_id, args["reason"])
    except KeyError:
        return _err(f"unknown objection {args['objection_id']}")
    except PermissionError as e:
        return _err(str(e))
    return ToolResult(ok=True, content=f"objection {args['objection_id']} withdrawn")


ENTITY = {"type": "string", "minLength": 1, "description": "entity id (ent:...) or a name / path fragment to look up"}
NEW_TOOLS = [
    Tool("graph_overview", "Summary of the project's coupling graph: size, most widely written state, top structural risks.",
         _obj({"risks": {"type": "integer", "minimum": 0, "maximum": 30}}, []), graph_overview),
    Tool("graph_rebuild", "Re-parse the project into the coupling graph (after code changes).", _obj({}, []), graph_rebuild),
    Tool("graph_find", "Find entities (functions, routes, events, messages, state, tables, files) by name or path.",
         _obj({"query": {"type": "string", "minLength": 1}, "type": {"type": "string"},
               "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, ["query"]), graph_find),
    Tool("graph_neighbors", "Direct relations of one entity (calls, handles, reads, writes, emits, consumes...) with provenance and source location.",
         _obj({"entity": ENTITY, "relations": {"type": "array", "items": {"type": "string"}},
               "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, ["entity"]), graph_neighbors),
    Tool("graph_impact", "What an entity affects and what affects it, across modules, services, events and shared state.",
         _obj({"entity": ENTITY, "depth": {"type": "integer", "minimum": 1, "maximum": 8},
               "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, ["entity"]), graph_impact),
    Tool("graph_common_cause", "Given several symptoms (entities), find shared dependencies / upstream causes that connect them.",
         _obj({"symptoms": {"type": "array", "minItems": 2, "maxItems": 10, "items": ENTITY},
               "limit": {"type": "integer", "minimum": 1, "maximum": 30}}, ["symptoms"]), graph_common_cause),
    Tool("graph_risks", "Structural risk leads found deterministically (shared writers, retries without idempotency, writes "
                        "without transaction, silent no-op paths, dead events, missing routes).",
         _obj({"pattern": {"type": "string"}, "min_severity": {"enum": ["low", "medium", "high"]},
               "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, []), graph_risks),
    Tool("delegate", "Give one subtask to a worker and return immediately. Subtasks must not overlap (different files/questions). "
                     "agent: a worker id, or \"any\" for the least busy worker (several subtasks then run in parallel). "
                     "claims / evidence: ids the worker should verify or start from; they are attached to its instructions. "
                     "anomaly: the anomaly id this subtask follows up (verification goes to a worker other than the one it "
                     "came from; the task is linked to the anomaly).",
         _obj({"agent": {"type": "string"}, "title": {"type": "string", "minLength": 1, "maxLength": 200},
               "instructions": {"type": "string", "minLength": 1, "maxLength": 20000},
               "claims": {"type": "array", "items": {"type": "string", "pattern": "^clm_"}, "maxItems": 20},
               "evidence": {**_EV_ITEMS, "maxItems": 30}, "anomaly": {"type": "string", "pattern": "^anm_"},
               "files": {"type": "array", "items": {"type": "string"}, "maxItems": 200,
                         "description": "when the cluster changes code: the files this worker owns (one worker per file)"}},
              ["agent", "title", "instructions"]),
         delegate, effect_class="internal", retry_safe=False),
    Tool("scout", "Name the business scenarios to test (each: a title and what must hold, from the task's complaints and "
                  "the README's rules). The system deals them to the scout pairs, who write one test each; a failing "
                  "test is handed to the fixers at once. Name more scenarios than complaints: the bugs nobody reported "
                  "are the ones a pair misses.",
         _obj({"scenarios": {"type": "array", "minItems": 1, "maxItems": 40, "items": _obj(
             {"title": {"type": "string", "minLength": 1, "maxLength": 200},
              "check": {"type": "string", "maxLength": 1000, "description": "what must hold, concretely"}}, ["title"])}},
             ["scenarios"]), scout, effect_class="internal", retry_safe=False),
    Tool("tell_fixers", "Pass a finding to the main and alternate fixers while they work (they get it before their next step).",
         _obj({"text": {"type": "string", "minLength": 1, "maxLength": 4000}}, ["text"]), tell_fixers,
         effect_class="internal", retry_safe=False),
    Tool("wait_for", "Wait (without using tokens) until subtasks and their guardian reviews finish. Returns outcomes, claims "
                     "with their current status, and guardian verdicts.",
         _obj({"task_ids": {"type": "array", "items": {"type": "string"}}, "timeout_s": {"type": "integer", "minimum": 5, "maximum": 3600}}, []),
         wait_for),
    Tool("consult", "Ask the logic head a question (coupling, root cause, future risks) and wait for its analysis.",
         _obj({"question": {"type": "string", "minLength": 1, "maxLength": 20000},
               "timeout_s": {"type": "integer", "minimum": 5, "maximum": 3600}}, ["question"]),
         consult, effect_class="internal", retry_safe=False),
    Tool("task_status", "Status of all your subtasks, their claims, and open objections.", _obj({}, []), task_status),
    Tool("raise_objection", "Object to delivering the current result (e.g. an unverified risk or ignored coupling). Blocks delivery "
                            "until withdrawn or the user decides. Cite claim ids when possible.",
         _obj({"text": {"type": "string", "minLength": 1, "maxLength": 8000}, "claims": _EV_ITEMS}, ["text"]),
         raise_objection, effect_class="internal", retry_safe=False),
    Tool("withdraw_objection", "Withdraw an objection you raised, with the reason (e.g. new evidence resolved it).",
         _obj({"objection_id": {"type": "string"}, "reason": {"type": "string", "minLength": 1, "maxLength": 4000}},
              ["objection_id", "reason"]), withdraw_objection, effect_class="internal", retry_safe=True),
]
for _t in NEW_TOOLS:
    TOOLS[_t.name] = _t
