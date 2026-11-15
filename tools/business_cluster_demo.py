"""Headless end-to-end cluster demo using scripted policies and real business execution."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import shutil
import tempfile

from codedoctor import config
from codedoctor.agents.daemon import Daemon
from codedoctor.models import scripted
from tools.business_cluster_cases import TEMPLATE, plan, prepare


def invocation(name, arguments):
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


def investigation_id(messages):
    for message in reversed(messages):
        found = re.findall(r"inv_[0-9A-HJKMNP-TV-Z]{26}", message.content or "")
        if found:
            return found[0]
    raise ValueError("no actual investigation id received")


def run_arguments(messages):
    text = messages[1].content
    match = re.search(r"investigation='(inv_[0-9A-HJKMNP-TV-Z]{26})', check='([a-z0-9_-]+)'", text)
    if not match:
        raise ValueError("no assigned business check")
    return {"investigation": match[1], "check": match[2]}


def configuration(folder: Path, case: str, *, guardian_runs=True, early_delivery=False):
    root = folder / "shop"
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE, root / "system.py")
    investigation_plan = plan("cluster-shop", case)
    prefix = folder.name + "-" + case
    names = ["dispatch", "logic", "worker-1", "guardian-1", "worker-2", "guardian-2"]
    models = {name: prefix + "-" + name for name in names}
    scripted.register(models["logic"], [invocation("cluster_candidates", {"symptoms": investigation_plan["symptoms"]}),
                                        invocation("cluster_open", {"plan": investigation_plan}),
                                        lambda messages: {"text": "Business investigation " + investigation_id(messages)}])
    turns = [invocation("consult", {"question": "Build a falsifiable, business-coupled investigation with independent experiments.", "timeout_s": 5})]
    if not early_delivery:
        turns += [lambda messages: invocation("cluster_dispatch", {"investigation": investigation_id(messages), "check": "distinguish", "worker": "worker-1"}),
                  lambda messages: invocation("cluster_dispatch", {"investigation": investigation_id(messages), "check": "impact_regression", "worker": "worker-2"}),
                  invocation("wait_for", {"timeout_s": 10}),
                  lambda messages: invocation("cluster_status", {"investigation": investigation_id(messages)})]
    turns += [{"text": "Controlled experiments complete; deliver only if the server's evidence gate allows it."}]
    scripted.register(models["dispatch"], turns)
    for name in names[2:]:
        if name.startswith("guardian") and not guardian_runs:
            turns = [{"text": "I agree with the worker, but did not execute anything."}]
        else:
            turns = [lambda messages: invocation("cluster_run", run_arguments(messages)), {"text": "Report only the recorded execution receipts; no universal causal claim."}]
        scripted.register(models[name], turns)
    agents = [{"id": "dispatch", "role": "head_dispatch", "endpoint": "scripted", "model": models["dispatch"]},
              {"id": "logic", "role": "head_logic", "endpoint": "scripted", "model": models["logic"]}]
    for i in (1, 2):
        agents += [{"id": f"worker-{i}", "role": "worker", "endpoint": "scripted", "model": models[f"worker-{i}"]},
                   {"id": f"guardian-{i}", "role": "guardian", "endpoint": "scripted", "model": models[f"guardian-{i}"], "supervises": f"worker-{i}"}]
    return config.parse({"cd_schema": "cd.config.project/0",
                         "project": {"name": "cluster-shop", "root": str(root), "data_dir": str(folder / "data")},
                         "endpoints": [{"id": "scripted", "kind": "scripted", "base_url": "scripted:", "local": True}],
                         "agents": agents, "defaults": {"budget": {"max_steps": 15, "max_tokens": 300000}, "stall_steps": 5}})


async def execute_case(folder: Path, case: str, **options):
    daemon = Daemon(configuration(folder, case, **options), poll_s=0.02)
    prepare(daemon.s)
    await daemon.start()
    try:
        root = daemon.submit_task("dispatch", f"Business coupling: {case}", "Investigate, falsify alternatives, independently reproduce and check affected business invariants.")
        report = await asyncio.wait_for(daemon.wait_for_report(root["task_id"]), 30)
        investigation = daemon.s.investigations.for_root(root["task_id"])
        status = daemon.s.investigations.status(investigation) if investigation else None
        trials = [json.loads(row["doc"]) for row in daemon.s.db.query("SELECT doc FROM cluster_trials WHERE investigation=? AND doc IS NOT NULL", (investigation,))]
        evidence_ids = set(status["evidence"] if status else [])
        evidence_ids |= {record["harness_evidence"] for trial in trials for record in trial["records"]}
        evidence_ids |= {json.loads(row["doc"])["source_evidence"] for row in daemon.s.db.query("SELECT doc FROM cluster_contracts")}
        manifest = [{"record": daemon.s.evidence.get(eid), "content_utf8": daemon.s.evidence.content(eid).decode("utf-8")} for eid in sorted(evidence_ids)]
        return {"case": case, "root": root, "outcome": report["body"]["outcome"], "status": status,
                "agents": daemon.agent_states(), "tasks": daemon.recent_tasks(),
                "model_calls": len(daemon.s.models.client("scripted").calls),
                "experimental_receipts": len(status["evidence"]) if status else 0,
                "trials": trials, "evidence_manifest": manifest,
                "scope": "scripted_agent_decisions_with_actual_sqlite_asyncio_business_execution",
                "real_model_quality_verified": False}
    finally:
        await daemon.stop()


async def main_async(output, state_dir=None):
    if state_dir:
        root = Path(state_dir).resolve()
        root.mkdir(parents=True, exist_ok=False)
        results = [await execute_case(root / case, case) for case in ("duplicate", "concurrent", "pricing")]
    else:
        with tempfile.TemporaryDirectory(prefix="code-doctor-business-cluster-") as temp:
            results = [await execute_case(Path(temp) / case, case) for case in ("duplicate", "concurrent", "pricing")]
    document = {"cd_schema": "cd.cluster.demo/0", "cases": results,
                "all_delivery_gates_passed": all(r["outcome"] == "done" and r["status"]["delivery_allowed"] for r in results)}
    if output:
        with Path(output).open("x", encoding="utf-8") as file:
            json.dump(document, file, ensure_ascii=False, indent=2)
    print(json.dumps({"cases": [{"case": r["case"], "outcome": r["outcome"], "executions": r["experimental_receipts"],
                                  "compatible": r["status"]["compatible_hypotheses"] if r["status"] else []} for r in results],
                      "all_delivery_gates_passed": document["all_delivery_gates_passed"]}, ensure_ascii=False, indent=2))
    return 0 if document["all_delivery_gates_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--state-dir")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args.output, args.state_dir)))
