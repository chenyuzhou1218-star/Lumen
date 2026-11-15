"""Reasoning bench (bench/scenarios/reasoning/*.json).

static scenarios - no model: the coupling graph's own reasoning. Are the planted defects
  found (and how high do they rank), does common-cause analysis put the shared root first,
  does impact analysis reach across the client/server boundary.

agent scenarios - a task run end to end by scripted agents (bench/policies.py), scored from
  what the run left in the database, never from the wording of the answer:
  outcome     root_cause (1 = a supported causal claim names a true root cause, 0.5 = only an
              unverified one, 0 = none), false_facts (supported claims about a false lead),
              coverage (share of must-cover entities named in claims or in the answer), cost
  defects     reasoning mistakes present when the answer was delivered (DEFECTS below)
  guards      which of them the system itself pointed out. A check counts as flagged when the
              report lists it under body.reasoning_checks ([{"check": <name>, ...}]) - the
              interface the reasoning batch (R1/R2) is to fill. A flag with no such defect is
              a false alarm.
"""

from __future__ import annotations

import asyncio
import json
from itertools import count

from codedoctor.agents import orchestration as orch
from codedoctor.agents.daemon import Daemon
from codedoctor.bench.common import REPO, load, project_copy, scripted_config, short
from codedoctor.bench.policies import POLICIES
from codedoctor.graph.build import build
from codedoctor.graph.risks import detect
from codedoctor.models import scripted

CAUSAL = {"causes", "may_cause", "affects", "violates"}
LIVE = {"proposed", "supported", "needs_revalidation"}
DEFECTS = {  # shown in the Chinese report
    "unclaimed_conclusion": "交付了答案，但背后没有任何有效的因果主张",
    "unsupported_conclusion": "交付了答案，但它依赖的因果主张没有一条经过验证",
    "false_lead_asserted": "有效的因果主张指向已知的错误线索",
    "competing_open": "两个以上互相竞争的因果假设仍未排除，且彼此不构成推理链",
    "chain_gap": "某条有效的因果主张没有通过主张链连接到报告的症状",
}
TIMEOUT_S = 30
_run_no = count()

# --- static ------------------------------------------------------------------------------------


def run_static(sc: dict) -> dict:
    g, info = build(REPO / sc["project"], sc["name"])
    risks = detect(g, "wt-" + "0" * 64)
    matched: set[int] = set()
    defects = []
    for d in sc["defects"]:
        hits = [i for i, r in enumerate(risks) if r["pattern"] == d["pattern"] and r["entities"][0] == d["entity"]]
        matched.update(hits)
        defects.append({"id": d["id"], "what": d["what"], "detected": bool(hits), "rank": hits[0] + 1 if hits else None})
    common = []
    for cc in sc["common_cause"]:
        ranked = [r["entity"] for r in g.common_cause(cc["symptoms"])]
        rank = ranked.index(cc["expect"]) + 1 if cc["expect"] in ranked else None
        common.append({"id": cc["id"], "expect": cc["expect"], "rank": rank, "top3": ranked[:3]})
    impact = []
    for im in sc["impact"]:
        imp = g.impact(im["entity"], im.get("depth", 4))
        want = [("affected_by", e) for e in im["affected_by"]] + [("affects", e) for e in im["affects"]]
        missing = [e for side, e in want if e not in imp[side]]
        impact.append({"id": im["id"], "recall": round(1 - len(missing) / len(want), 3), "missing": missing})
    found = [d for d in defects if d["detected"]]
    return {
        "id": sc["id"], "kind": "static", "parse_errors": info["parse_errors"],
        "summary": {
            "defects_detected": f"{len(found)}/{len(defects)}",
            "defect_recall": round(len(found) / len(defects), 3),
            "mean_defect_rank": round(sum(d["rank"] for d in found) / len(found), 2) if found else None,
            "risks_reported": len(risks),
            "risks_matching_a_known_defect": len(matched),
            "common_cause_hit_at_1": sum(1 for c in common if c["rank"] == 1),
            "common_cause_hit_at_3": sum(1 for c in common if c["rank"] and c["rank"] <= 3),
            "common_cause_probes": len(common),
            "impact_recall": round(sum(i["recall"] for i in impact) / len(impact), 3),
        },
        "defects": defects, "common_cause": common, "impact": impact,
    }

# --- agent runs --------------------------------------------------------------------------------


def _agents(mode: str, models: dict[str, str]) -> list[dict]:
    if mode == "basic":
        return [{"id": "doctor", "role": "general", "endpoint": "bench", "model": models["doctor"]}]
    return [
        {"id": "head-dispatch", "role": "head_dispatch", "endpoint": "bench", "model": models["head-dispatch"]},
        {"id": "head-logic", "role": "head_logic", "endpoint": "bench", "model": models["head-logic"]},
        {"id": "worker-1", "role": "worker", "endpoint": "bench", "model": models["worker-1"]},
        {"id": "guardian-1", "role": "guardian", "endpoint": "bench", "model": models["guardian-1"], "supervises": "worker-1"},
    ]


def _tree(s, root_id: str) -> list[str]:
    out, todo = [], [root_id]
    while todo:
        tid = todo.pop(0)
        out.append(tid)
        todo += [c["id"] for c in orch.children(s, tid)]
    return out


def _components(claims: list[dict]) -> dict[str, int]:
    """Entity -> component id, joining subject and object of every claim."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in claims:
        st = c["statement"]
        if isinstance(st["object"], str):
            parent[find(st["subject"])] = find(st["object"])
        else:
            find(st["subject"])
    roots = {}
    return {e: roots.setdefault(find(e), len(roots)) for e in list(parent)}


def _depends(claims_by_id: dict[str, dict], a: str, b: str) -> bool:
    """Does claim a build on claim b (depends_on, transitively)?"""
    todo, seen = [a], set()
    while todo:
        cur = todo.pop()
        if cur == b:
            return True
        if cur in seen or cur not in claims_by_id:
            continue
        seen.add(cur)
        todo += claims_by_id[cur].get("depends_on", [])
    return False


def score_run(truth: dict, outcome: str, answer: str, claims: list[dict], flagged: set[str]) -> dict:
    live = [c for c in claims if c["status"] in LIVE and c["statement"]["relation"] in CAUSAL]
    subj = lambda c: c["statement"]["subject"]  # noqa: E731
    obj = lambda c: c["statement"]["object"] if isinstance(c["statement"]["object"], str) else None  # noqa: E731
    roots = [c for c in live if subj(c) in truth["root_causes"]]
    by_id = {c["id"]: c for c in claims}
    open_h = [c for c in live if c["claim_type"] == "hypothesis" and c["status"] != "supported"]
    competing = any(subj(a) != subj(b) and obj(a) != subj(b) and obj(b) != subj(a)
                    and not _depends(by_id, a["id"], b["id"]) and not _depends(by_id, b["id"], a["id"])
                    for i, a in enumerate(open_h) for b in open_h[i + 1:])
    comp = _components(live)
    symptom_comps = {comp[e] for e in truth["symptom"] if e in comp}
    delivered = outcome == "done"
    present = {
        "unclaimed_conclusion": delivered and not live,
        "unsupported_conclusion": delivered and bool(live) and not any(c["status"] == "supported" for c in live),
        "false_lead_asserted": delivered and any(subj(c) in truth["false_leads"] for c in live),
        "competing_open": delivered and competing,
        "chain_gap": delivered and any(comp[subj(c)] not in symptom_comps for c in live),
    }
    defects = sorted(k for k, v in present.items() if v)
    named = {e for c in claims if c["status"] in LIVE for e in (subj(c), obj(c)) if e}
    covered = [e for e in truth["must_cover"] if e in named or short(e) in answer]
    return {
        "outcome": outcome,
        "root_cause": 1.0 if any(c["status"] == "supported" for c in roots) else 0.5 if roots else 0.0,
        "false_facts": sum(1 for c in claims if c["status"] == "supported" and subj(c) in truth["false_leads"]),
        "coverage": round(len(covered) / len(truth["must_cover"]), 3) if truth["must_cover"] else 1.0,
        "defects": defects,
        "flagged": sorted(flagged),
        "caught": sorted(set(defects) & flagged),
        "false_alarms": sorted(flagged - set(defects)),
    }


async def _run_agent(sc: dict, policy_name: str) -> dict:
    policy = POLICIES[(sc["id"], policy_name)]()
    n = next(_run_no)
    models = {agent: f"bench-{sc['id']}-{policy_name}-{agent}-{n}" for agent in policy.scripts}
    for agent, turns in policy.scripts.items():
        scripted.register(models[agent], turns)
    with project_copy(sc) as (root, data):
        cfg = scripted_config(root, data, sc["name"], _agents(policy.mode, models))
        d = Daemon(cfg, poll_s=0.05)
        await d.start()
        try:
            entry = "doctor" if policy.mode == "basic" else "head-dispatch"
            sub = d.submit_task(entry, sc["task"]["title"], sc["task"]["instructions"])
            report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), TIMEOUT_S)
        finally:
            await d.halt()
        try:
            s = d.s
            tree = _tree(s, sub["task_id"])
            claims = [c for t in tree for c in s.claims.by_task(t)]
            usage = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "steps": 0}
            for t in tree:
                row = s.db.one("SELECT usage FROM tasks WHERE id = ?", (t,))
                for key, v in (json.loads(row["usage"]) if row and row["usage"] else {}).items():
                    if key in usage:
                        usage[key] += v
            body = report["body"]
            flagged = {c.get("check") for c in body.get("reasoning_checks", []) if isinstance(c, dict)}
            scored = score_run(sc["truth"], body["outcome"], body.get("summary", ""), claims, flagged)
            return {"policy": policy_name, "mode": policy.mode, **scored, "tasks": len(tree), "cost": usage,
                    "claims": [{"type": c["claim_type"], "status": c["status"], "subject": short(c["statement"]["subject"]),
                                "relation": c["statement"]["relation"],
                                "object": short(c["statement"]["object"]) if isinstance(c["statement"]["object"], str) else "(value)"}
                               for c in claims]}
        finally:
            await d.s.aclose()


def summarize_agent(runs: list[dict]) -> dict:
    present = sum(len(r["defects"]) for r in runs)
    caught = sum(len(r["caught"]) for r in runs)
    return {
        "runs": len(runs),
        "root_cause": round(sum(r["root_cause"] for r in runs) / len(runs), 3),
        "false_facts": sum(r["false_facts"] for r in runs),
        "coverage": round(sum(r["coverage"] for r in runs) / len(runs), 3),
        "defects_present": present,
        "defects_caught": caught,
        "catch_rate": round(caught / present, 3) if present else None,
        "false_alarms": sum(len(r["false_alarms"]) for r in runs),
        "model_calls": sum(r["cost"]["model_calls"] for r in runs),
        "tokens": sum(r["cost"]["input_tokens"] + r["cost"]["output_tokens"] for r in runs),
    }


async def run_agent_scenario(sc: dict) -> dict:
    runs = [await _run_agent(sc, p) for p in sc["policies"]]
    return {"id": sc["id"], "kind": "agent", "summary": summarize_agent(runs), "runs": runs}


async def arun(scenarios_dir=None) -> dict:
    scenarios = load("reasoning", scenarios_dir)
    static = [run_static(sc) for sc in scenarios if sc["kind"] == "static"]
    agent = [await run_agent_scenario(sc) for sc in scenarios if sc["kind"] == "agent"]
    return {
        "defect_checks": DEFECTS,
        "static": static,
        "agent": agent,
        "summary": {"agent": summarize_agent([r for sc in agent for r in sc["runs"]]) if agent else None},
    }


def run(scenarios_dir=None) -> dict:
    return asyncio.run(arun(scenarios_dir))
