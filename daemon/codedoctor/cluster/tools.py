"""Business investigation tools in the actual Agent tool registry, not a parallel mock runtime."""
from __future__ import annotations

import json
import copy

from codedoctor.agents import orchestration as orch
from codedoctor.agents.tools import DEFAULT_TOOLS, TOOLS, Tool, ToolResult, _obj
from codedoctor.cluster.contracts import BusinessError
from codedoctor.cluster.coupling import candidates, blast_radius
from codedoctor.cluster.contracts import canonical
from codedoctor.evidence.registry import stricter
from codedoctor.protocol.registry import load_all


def _result(ctx, document, evidence=()):
    return ToolResult(ok=True, content=json.dumps(document, ensure_ascii=False), external=True,
                      data_class=stricter(ctx.services.config.code_data_class, ctx.data_class), evidence=list(evidence))


def _bound(ctx, investigation):
    doc = ctx.services.investigations.get(investigation)
    if doc["root_task_id"] != orch.root_of(ctx.services, ctx.task_id):
        raise PermissionError("cannot read or change another investigation's business records")
    return doc


def leads(ctx, args):
    ctx.services.graph.ensure_built()
    return _result(ctx, candidates(ctx.services.graph.graph(), args["symptoms"]))


def impact(ctx, args):
    version = ctx.services.graph.ensure_built()["code_version"]
    result = blast_radius(ctx.services.graph.graph(), args["origin"], max_nodes=args.get("max_nodes", 10000))
    result["code_version"] = version
    evidence = ctx.services.evidence.add_blob(canonical(result), "application/json", source="tool",
        collected_by="cluster.impact/0", agent_id=ctx.agent_id,
        data_class=stricter(ctx.services.config.code_data_class, ctx.data_class), binding={"code_version": version})
    # Full tree stays in evidence; avoid spending the context on thousands of
    # repeated node records. The existing evidence tool can retrieve the blob.
    return _result(ctx, {**result, "affected": result["affected"][:64], "returned_nodes": min(64, result["affected_count"]),
                         "full_tree_evidence": evidence}, [evidence])


def inventory(ctx, args):
    version = ctx.services.graph.ensure_built()["code_version"]
    contracts = [json.loads(row["doc"]) for row in ctx.services.db.query("SELECT doc FROM cluster_contracts WHERE version=?", (version,))]
    scenarios = [{"id": s.id, "description": s.description} for s in ctx.services.investigations.registry.scenarios.values() if s.code_version == version]
    result = _result(ctx, {"code_version": version, "approved_contracts": contracts, "registered_experiments": scenarios,
                           "missing_adapter_is_not_evidence_of_a_bug": True})
    for contract in contracts:
        result.data_class = stricter(result.data_class, contract["data_class"])
    return result


def open_plan(ctx, args):
    doc = ctx.services.investigations.open(orch.root_of(ctx.services, ctx.task_id), ctx.agent_id, args["plan"], ctx.data_class)
    return _result(ctx, {"investigation": doc["id"], "code_version": doc["code_version"],
                         "checks": [c["id"] for c in doc["plan"]["checks"]], "status": "proposed_tests_not_verified"})


def dispatch(ctx, args):
    _bound(ctx, args["investigation"])
    result = ctx.services.investigations.dispatch(args["investigation"], ctx.agent_id,
                                                  check_id=args.get("check"), worker=args.get("worker", "any"))
    return _result(ctx, result)


def run(ctx, args):
    doc = _bound(ctx, args["investigation"])
    result = ctx.services.investigations.run(args["investigation"], args["check"], ctx.agent_id, ctx.task_id, ctx.data_class)
    evidence = [r["evidence"] for r in result["records"]]
    output = {k: v for k, v in result.items() if k != "records"}
    output["records"] = [{k: r[k] for k in ("phase", "repeat", "outcome", "evidence")} for r in result["records"]]
    tool_result = _result(ctx, output, evidence)
    tool_result.data_class = stricter(doc["data_class"], ctx.data_class)
    return tool_result


def status(ctx, args):
    doc = _bound(ctx, args["investigation"])
    report = ctx.services.investigations.status(args["investigation"])
    result = _result(ctx, report, report["evidence"])
    result.data_class = stricter(result.data_class, doc["data_class"])
    return result


def guarded(handler):
    def call(ctx, args):
        try:
            return handler(ctx, args)
        except (BusinessError, PermissionError) as error:
            return ToolResult(ok=False, content=f"ERROR: {error}", progress=False)
    return call


_ID = {"type": "string", "minLength": 1}
_plan = copy.deepcopy(load_all()["cluster/plan.schema.json"])
_definitions = _plan.pop("$defs")
_plan.pop("$schema")
_plan.pop("$id")
_open_parameters = _obj({"plan": _plan}, ["plan"])
_open_parameters["$defs"] = _definitions
for tool in [
    Tool("cluster_impact", "Trace business effect propagation through typed dependencies; preserves the complete tree in evidence. Structural risk, not confirmed bugs.",
         _obj({"origin": _ID, "max_nodes": {"type": "integer", "minimum": 1, "maximum": 50000}}, ["origin"]), guarded(impact)),
    Tool("cluster_inventory", "List user-approved business invariants and explicitly registered experiment adapters for this snapshot. Empty adapters mean execution coverage is missing, not that the software is correct.", _obj({}, []), guarded(inventory)),
    Tool("cluster_candidates", "Find structurally shared upstream dependencies with typed, source-located paths. Not causal proof.",
         _obj({"symptoms": {"type": "array", "minItems": 1, "maxItems": 32, "items": _ID}}, ["symptoms"]), guarded(leads)),
    Tool("cluster_open", "Open an immutable business-coupled investigation: competing hypotheses, explicit predictions, approved contracts, registered experiments and impact regressions.",
         _open_parameters, guarded(open_plan), effect_class="internal", retry_safe=False),
    Tool("cluster_dispatch", "Dispatch the next most discriminating business experiment to a configured worker and its independent guardian. Never picks models.",
         _obj({"investigation": _ID, "check": _ID, "worker": _ID}, ["investigation"]), guarded(dispatch), effect_class="internal", retry_safe=False),
    Tool("cluster_run", "Execute your assigned registered business harness in baseline/fault/rescue repeats. Guardian runs a distinct harness. Never trusts text-only claims.",
         _obj({"investigation": _ID, "check": _ID}, ["investigation", "check"]), guarded(run), effect_class="internal", retry_safe=False),
    Tool("cluster_status", "Show compatible/refuted-in-scope hypotheses, independent receipts, pending regressions, and delivery blockers.",
         _obj({"investigation": _ID}, ["investigation"]), guarded(status)),
]:
    TOOLS[tool.name] = tool

for role, names in {
    "head_logic": ["cluster_inventory", "cluster_candidates", "cluster_open", "cluster_status"],
    "head_dispatch": ["cluster_inventory", "cluster_candidates", "cluster_open", "cluster_dispatch", "cluster_status"],
    "worker": ["cluster_candidates", "cluster_run", "cluster_status"],
    "investigator": ["cluster_candidates", "cluster_run", "cluster_status"],
    "guardian": ["cluster_candidates", "cluster_run", "cluster_status"],
}.items():
    DEFAULT_TOOLS[role].extend(["cluster_impact", *names])
