"""Context bench (bench/scenarios/context/*.json, ADR 0008).

One scripted agent works through a long investigation on a small context budget: it submits
two claims early (and withdraws one), then reads many files, some twice. The same run is done
under the context policy before M5 and the current one. Scored from what was actually sent:

  over_budget           requests (messages plus tool descriptions) larger than the budget (should be 0)
  rewrites              requests for which earlier messages had to be rewritten (each one
                        invalidates a local model's prefix cache; fewer is faster)
  input_chars           characters sent over the whole task (cost)
  evidence_retained     share of the evidence ids collected that the final request still shows in full
  evidence_recoverable  ... in full or as "path Lx-Ly" (reading those lines again gives the same id)
  status_retained       share of claims whose CURRENT status the final request still states
                        (a line naming the claim id and its status)
"""

from __future__ import annotations

import asyncio
import re

from codedoctor.agents.daemon import Daemon
from codedoctor.agents.runtime import BEFORE_M5, CHARS_PER_TOKEN, ContextPolicy, _short_evidence
from codedoctor.bench.common import load, project_copy, scripted_config
from codedoctor.models import scripted

POLICIES = (("before", "M5 之前", BEFORE_M5), ("current", "M5（当前）", ContextPolicy()))
STATUS_WORDS = {"proposed": ("proposed", "unverified"), "supported": ("supported", "verified"),
                "withdrawn": ("withdrawn", "ruled out"), "refuted": ("refuted", "ruled out")}
_CLM = re.compile(r"claim accepted as (clm_[0-9A-Z]{26})")
_n = iter(range(10**9))


def _evidence_for(msgs, path: str) -> str:
    found = re.findall(r"evidence: (ev:code:[^\s:]+:" + re.escape(path) + r"@\S+)", "\n".join(m.content or "" for m in msgs))
    return found[-1]


def _newest_claim(msgs) -> str:
    """The id of the claim submitted last, from wherever the agent can still see it: the tool result that
    accepted it or, once that was elided, the working memory (which lists claims newest first)."""
    accepted = [c for m in msgs if m.role == "tool" for c in _CLM.findall(m.content or "")]
    if accepted:
        return accepted[-1]
    return re.findall(r"- (clm_[0-9A-Z]{26}) \[", msgs[-1].content or "")[0]


def _claim(path: str, subject: str, text: str):
    def turn(msgs):
        ev = _evidence_for(msgs, path)
        return {"tool_calls": [{"name": "submit_claim", "arguments": {"claim": {
            "claim_type": "hypothesis", "evidence_level": "inferred",
            "statement": {"text": text, "subject": subject, "relation": "causes", "object": "ent:state:shop:py/gold"},
            "scope": {"code_version": ev.split(":")[2]}, "evidence": [{"id": ev, "role": "supports", "shows": text}],
            "falsification": {"method": "test", "description": "replay and compare gold with the ledger"}}}}]}
    return turn


def _script(sc: dict) -> list:
    read = lambda p: {"tool_calls": [{"name": "read_file", "arguments": {"path": p}}]}  # noqa: E731
    a, b = sc["early"]
    return [
        read(a), _claim(a, "ent:symbol:shop:server/session.py#reconnect", "reconnect replays settle, so the reward is paid twice"),
        read(b), _claim(b, "ent:symbol:shop:server/wallet.py#spend_gold", "spend_gold races with add_gold"),
        lambda msgs: {"tool_calls": [{"name": "withdraw_claim", "arguments": {
            "claim_id": _newest_claim(msgs), "reason": "no concurrency in this code path"}}]},
        *[read(p) for p in sc["files"]], *[read(p) for p in sc["reread"]],
        {"text": "Read everything. reconnect replays settle; the spend_gold race was ruled out."},
    ]


async def _run(sc: dict, policy: ContextPolicy) -> dict:
    model = f"bench-context-{sc['id']}-{next(_n)}"
    scripted.register(model, _script(sc))
    with project_copy(sc) as (root, data):
        cfg = scripted_config(root, data, sc["name"], [{"id": "doctor", "role": "general", "endpoint": "bench", "model": model,
                                                         "context_budget_tokens": sc["context_budget_tokens"]}],
                              max_steps=len(_script(sc)) + 2,
                              # reading code on a small budget: the computer tools (some 7600 tokens of descriptions) are not
                              # what this measures, and with them on a small budget leaves no room for the reads
                              computer={"disabled": True})
        d = Daemon(cfg, poll_s=0.02)
        for a in d.agents.values():
            a.policy = policy
        await d.start()
        try:
            sub = d.submit_task("doctor", sc["task"]["title"], sc["task"]["instructions"])
            report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 60)
        finally:
            await d.halt()
        try:
            s = d.s
            budget = sc["context_budget_tokens"] * CHARS_PER_TOKEN
            sent = s.models.client("bench").calls
            tools = d.agents["doctor"]._tools_chars  # tool descriptions go with every request and count (review R5)
            sizes = [sum(len(m.content or "") for m in c["messages"]) + tools for c in sent]
            payloads = [s.journal.original(e)["payload"] for e in s.journal.read(task_id=sub["task_id"]) if e["type"] == "model_request"]
            final = "\n".join(m.content or "" for m in sent[-1]["messages"])
            evidence = list(dict.fromkeys(e for r in s.journal.read(task_id=sub["task_id"]) if r["type"] == "tool_result"
                                          for e in s.journal.original(r)["data"].get("evidence", [])))
            claims = s.claims.by_task(sub["task_id"])

            def stated(c: dict) -> bool:
                words = STATUS_WORDS.get(c["status"], (c["status"],))
                return any(c["id"] in ln and any(w in ln.lower() for w in words) for ln in final.splitlines())

            return {
                "outcome": report["body"]["outcome"], "requests": len(sent),
                "over_budget": sum(1 for z in sizes if z > budget), "peak_share": round(max(sizes) / budget, 3),
                "rewrites": sum(1 for p in payloads if isinstance(p, dict) and p.get("rewritten")),
                "input_chars": sum(sizes),
                "evidence_retained": round(sum(1 for e in evidence if e in final) / len(evidence), 3),
                "evidence_recoverable": round(sum(1 for e in evidence if e in final or (_short_evidence(e) or e) in final)
                                              / len(evidence), 3),
                "status_retained": round(sum(1 for c in claims if stated(c)) / len(claims), 3),
                "claims": {c["status"]: sum(1 for x in claims if x["status"] == c["status"]) for c in claims},
            }
        finally:
            await d.s.aclose()


async def arun(scenarios_dir=None) -> dict:
    out = []
    for sc in load("context", scenarios_dir):
        out.append({"id": sc["id"], "budget_tokens": sc["context_budget_tokens"],
                    "policies": {pid: {"label": label, **await _run(sc, policy)} for pid, label, policy in POLICIES}})
    return {"scenarios": out}


def run(scenarios_dir=None) -> dict:
    return asyncio.run(arun(scenarios_dir))
