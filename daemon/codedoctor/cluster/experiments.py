"""Explicitly registered experiment adapters; no shell, eval or model-selected imports."""
from __future__ import annotations

import hashlib
import inspect
import time
from dataclasses import dataclass

from codedoctor import ids
from codedoctor.cluster.contracts import BusinessError, canonical, evaluate


@dataclass(frozen=True)
class Scenario:
    id: str
    code_version: str
    worker: object
    guardian: object
    description: str


def harness_id(handler) -> str:
    try:
        source = inspect.getsource(handler).encode("utf-8")
    except (OSError, TypeError):
        raise BusinessError("experiment handler must have inspectable, versioned source") from None
    return hashlib.sha256(source).hexdigest()


class ExperimentRegistry:
    def __init__(self):
        self.scenarios: dict[str, Scenario] = {}

    def register(self, scenario: Scenario):
        if scenario.id in self.scenarios or not callable(scenario.worker) or not callable(scenario.guardian):
            raise BusinessError("distinct trusted scenario registration is required")
        if scenario.worker is scenario.guardian or harness_id(scenario.worker) == harness_id(scenario.guardian):
            raise BusinessError("guardian needs an independently registered harness, not the worker's callable")
        self.scenarios[scenario.id] = scenario


def execute(services, scenario: Scenario, contracts: list[dict], *, role: str, agent_id: str,
            repeats: int, data_class: str, cancelled, seconds: float = 10) -> dict:
    if role not in {"worker", "guardian"} or type(repeats) is not int or not 2 <= repeats <= 8 or not contracts:
        raise BusinessError("experiments require a worker/guardian, contracts, and 2–8 repeats")
    handler = scenario.worker if role == "worker" else scenario.guardian
    harness, trial = harness_id(handler), ids.new_id("trial")
    source = inspect.getsource(handler).encode("utf-8")
    harness_evidence = services.evidence.add_blob(source, "text/x-python", source="tool", collected_by="cluster.harness/0",
                                                   agent_id=agent_id, data_class=data_class,
                                                   binding={"code_version": scenario.code_version})
    records, started = [], time.monotonic()
    for repeat in range(repeats):
        for phase in ("baseline", "fault", "rescue"):
            if cancelled() or time.monotonic() - started >= seconds:
                return {"trial": trial, "status": "incomplete", "records": records, "signature": None, "harness": harness}
            try:
                metrics = handler(phase, repeat)
                canonical(metrics)  # reject NaN, non-JSON objects, or hidden arbitrary objects
                if not isinstance(metrics, dict):
                    raise BusinessError("handler returns metric objects")
                checks = [evaluate(contract, metrics) for contract in contracts]
                outcome = "unknown" if any(c["status"] == "unknown" for c in checks) else (
                    "violated" if any(c["status"] == "violated" for c in checks) else "holds")
                payload = {"metrics": metrics, "checks": checks, "outcome": outcome}
            except Exception as error:
                payload = {"outcome": "execution_error", "error_type": type(error).__name__}
            payload.update(cd_schema="cd.cluster.execution/0", trial=trial, scenario=scenario.id,
                           code_version=scenario.code_version, phase=phase, repeat=repeat, harness=harness,
                           agent_id=agent_id, role=role, project=services.config.name)
            payload["harness_evidence"] = harness_evidence
            eid = services.evidence.add_blob(canonical(payload), "application/json", source="tool",
                                             collected_by="cluster.experiments/0", agent_id=agent_id,
                                             data_class=data_class, binding={"code_version": scenario.code_version})
            records.append({"evidence": eid, **payload})
            if cancelled() or time.monotonic() - started >= seconds:
                return {"trial": trial, "status": "incomplete", "records": records, "signature": None, "harness": harness}
    by_phase = {phase: [r["outcome"] for r in records if r["phase"] == phase] for phase in ("baseline", "fault", "rescue")}
    if any(r["outcome"] in {"execution_error", "unknown"} for r in records):
        status, signature = "inconclusive", None
    elif any(v != "holds" for v in by_phase["baseline"] + by_phase["rescue"]):
        status, signature = "bad_control", None
    elif len(set(by_phase["fault"])) != 1:
        status, signature = "nondeterministic", None
    else:
        status, signature = "completed", by_phase["fault"][0]
    return {"trial": trial, "status": status, "signature": signature, "records": records, "harness": harness}
