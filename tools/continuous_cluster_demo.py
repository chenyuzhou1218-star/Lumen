"""Run two actual daemon reasoning cycles per head with explicit scripted models."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path

from codedoctor.agents.daemon import Daemon
from codedoctor.config import ClusterPolicy
from codedoctor.models import scripted
from tools.business_cluster_demo import configuration


async def run(state_dir):
    folder = Path(state_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    cfg = configuration(folder, "duplicate")
    cfg = replace(cfg, cluster=ClusterPolicy(enabled=True, foresight=True, interval_s=0.1,
        max_tokens_per_cycle=20000, reserved_tokens_per_hour=80000))
    for head in ("dispatch", "logic"):
        scripted.register(cfg.agents[head].primary.model, [
            {"text": "Hypothesis only: duplicate events may propagate into billing. Independently test idempotency and downstream ledger conservation."},
            {"text": "Hypothesis only: partial failure after commit may invalidate the earlier plan. Need baseline/fault/rescue receipts before any causal conclusion."}])
    daemon = Daemon(cfg, poll_s=0.02)
    try:
        await daemon.start()
        deadline = asyncio.get_running_loop().time() + 15
        while asyncio.get_running_loop().time() < deadline:
            tasks = daemon.s.db.query("SELECT agent,state,outcome,id FROM tasks")
            counts = {head: sum(t["agent"] == head and t["state"] == "finished" for t in tasks) for head in ("dispatch", "logic")}
            if all(n >= 2 for n in counts.values()):
                break
            await asyncio.sleep(0.05)
        else:
            raise TimeoutError("heads did not complete two cycles")
        return {"scope": "actual_daemon_loops_with_scripted_model_responses_not_real_model_quality",
            "cycles": daemon.foresight.status(), "completed_per_head": counts,
            "configured_models": {h: cfg.agents[h].primary.model for h in counts},
            "model_calls": len(daemon.s.models.client("scripted").calls),
            "journal": [daemon.s.journal.original(e) for e in daemon.s.journal.read(limit=500)],
            "pause_reason": "hourly_admission_reserve_reached", "real_model_verified": False}
    finally:
        await daemon.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.state_dir))
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: result[key] for key in ("completed_per_head", "model_calls", "real_model_verified")}, indent=2))
