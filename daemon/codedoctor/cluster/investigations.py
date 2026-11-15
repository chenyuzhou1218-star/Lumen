"""Durable competing-hypothesis investigations executed by real Worker/Guardian tasks."""
from __future__ import annotations

import json

from codedoctor import ids
from codedoctor.agents import orchestration as orch
from codedoctor.cluster.contracts import BusinessError, canonical, evaluate, validate_contract
import hashlib
from codedoctor.cluster.coupling import candidates
from codedoctor.cluster.experiments import ExperimentRegistry, execute, harness_id
from codedoctor.currency import snapshot_version
from codedoctor.evidence.registry import stricter
from codedoctor.store.db import dumps

DDL = (
    "CREATE TABLE IF NOT EXISTS cluster_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS cluster_contracts (id TEXT PRIMARY KEY, version TEXT NOT NULL, doc TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS cluster_investigations (id TEXT PRIMARY KEY, root_id TEXT NOT NULL UNIQUE, version TEXT NOT NULL, doc TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS cluster_checks (investigation TEXT NOT NULL, id TEXT NOT NULL, worker TEXT, guardian TEXT, worker_task TEXT, state TEXT NOT NULL, PRIMARY KEY(investigation,id))",
    "CREATE TABLE IF NOT EXISTS cluster_trials (investigation TEXT NOT NULL, check_id TEXT NOT NULL, role TEXT NOT NULL, agent TEXT NOT NULL, task TEXT NOT NULL, state TEXT NOT NULL, doc TEXT, PRIMARY KEY(investigation,check_id,role))",
)


class InvestigationService:
    def __init__(self, services):
        self.s = services
        self.registry = ExperimentRegistry()  # empty unless trusted application code explicitly registers adapters
        with services.db.tx() as connection:
            for statement in DDL:
                connection.execute(statement)
            row = connection.execute("SELECT value FROM cluster_meta WHERE key='schema_version'").fetchone()
            if row and row["value"] != "1":
                raise BusinessError("unsupported business cluster store version")
            connection.execute("INSERT OR IGNORE INTO cluster_meta VALUES ('schema_version','1')")

    def _role(self, actor: str, allowed: set[str]):
        cfg = self.s.config.agents.get(actor)
        if cfg is None or cfg.role not in allowed:
            raise PermissionError(f"{actor!r} is not allowed to perform this cluster operation")
        return cfg.role

    def approve_contract(self, contract: dict, source_evidence: str, *, approved_by: str):
        """User/application boundary, deliberately NOT exposed as a model tool."""
        if approved_by != "user":
            raise PermissionError("business rules must be explicitly approved by the user")
        validate_contract(contract)
        version = snapshot_version(self.s.config.root)
        record = self.s.evidence.get(source_evidence)
        if self.s.evidence.check(source_evidence) != "ok" or record["binding"].get("code_version") != version:
            raise BusinessError("contract source evidence must be intact and bound to the current snapshot")
        doc = {"contract": contract, "source_evidence": source_evidence, "approved_by": approved_by,
               "code_version": version, "data_class": record["data_class"]}
        with self.s.db.tx() as connection:
            old = connection.execute("SELECT doc FROM cluster_contracts WHERE id=?", (contract["id"],)).fetchone()
            if old and json.loads(old["doc"]) != doc:
                raise BusinessError("approved contracts are immutable; use a new contract id")
            connection.execute("INSERT OR IGNORE INTO cluster_contracts VALUES (?,?,?)", (contract["id"], version, dumps(doc)))
        return doc

    def _contract(self, contract_id, version):
        row = self.s.db.one("SELECT doc FROM cluster_contracts WHERE id=? AND version=?", (contract_id, version))
        if row is None:
            raise BusinessError(f"contract {contract_id!r} is not approved for this code snapshot")
        doc = json.loads(row["doc"])
        if self.s.evidence.check(doc["source_evidence"]) != "ok":
            raise BusinessError("approved contract source has become unavailable or tampered")
        return doc

    def get(self, investigation):
        row = self.s.db.one("SELECT doc FROM cluster_investigations WHERE id=?", (investigation,))
        if row is None:
            raise BusinessError("unknown business investigation")
        return json.loads(row["doc"])

    def for_root(self, root):
        row = self.s.db.one("SELECT id FROM cluster_investigations WHERE root_id=?", (root,))
        return row["id"] if row else None

    def open(self, root: str, actor: str, plan: dict, data_class: str = "internal"):
        self._role(actor, {"head_logic", "head_dispatch"})
        from codedoctor.protocol.registry import validator
        errors = list(validator("cluster/plan.schema.json").iter_errors(plan))
        if errors:
            raise BusinessError("invalid investigation plan: " + errors[0].message[:400])
        root_row = orch.task_row(self.s, root)
        if not root_row or self.s.config.agents[root_row["agent"]].role != "head_dispatch" or orch.is_cancelled(self.s, root):
            raise BusinessError("a live dispatch-head root task is required")
        if root_row["state"] == "finished":
            raise BusinessError("cannot attach a plan to an already delivered task")
        version = self.s.graph.ensure_built()["code_version"]
        graph = self.s.graph.graph()
        leads = candidates(graph, plan["symptoms"])
        admissible = set(plan["symptoms"]) | {r["entity"] for r in leads["candidates"]}
        hypothesis_ids = {h["id"] for h in plan["hypotheses"]}
        if len(hypothesis_ids) != len(plan["hypotheses"]) or any(h["candidate"] not in graph.nodes for h in plan["hypotheses"]):
            raise BusinessError("hypothesis ids must be distinct and candidates must be exact graph entities")
        if any(h["candidate"] not in admissible for h in plan["hypotheses"]):
            raise BusinessError("a hypothesis candidate must be connected to the declared symptoms, not an unrelated node")
        if {c["purpose"] for c in plan["checks"]} != {"discriminate", "regression"}:
            raise BusinessError("a business investigation needs both distinguishing tests and impact regressions")
        if len({c["id"] for c in plan["checks"]}) != len(plan["checks"]):
            raise BusinessError("check ids must be distinct")
        if plan["max_executions"] < len(plan["checks"]) * plan["repeats"] * 6:
            raise BusinessError("budget must cover independent worker/guardian baseline/fault/rescue repeats")
        data_class = stricter(self.s.config.code_data_class, data_class)
        harnesses = {}
        for check in plan["checks"]:
            scenario = self.registry.scenarios.get(check["scenario"])
            if scenario is None or scenario.code_version != version:
                raise BusinessError("all scenarios must be explicitly registered for the same code snapshot")
            harnesses[scenario.id] = {"worker": harness_id(scenario.worker), "guardian": harness_id(scenario.guardian)}
            if check["purpose"] == "discriminate" and set(check["predictions"]) != hypothesis_ids:
                raise BusinessError("a distinguishing test needs a prediction for every competing hypothesis")
            if check["purpose"] == "regression" and check["predictions"]:
                raise BusinessError("regression checks do not eliminate hypotheses")
            for cid in check["contracts"]:
                data_class = stricter(data_class, self._contract(cid, version)["data_class"])
        investigation = ids.new_id("inv")
        doc = {"cd_schema": "cd.cluster.investigation/0", "id": investigation, "root_task_id": root,
               "code_version": version, "project": self.s.config.name, "proposed_by": actor, "plan": plan,
               "structural_leads": leads, "data_class": data_class, "harnesses": harnesses}
        with self.s.db.tx() as connection:
            existing = connection.execute("SELECT doc FROM cluster_investigations WHERE root_id=?", (root,)).fetchone()
            if existing:
                previous = json.loads(existing["doc"])
                if previous["plan"] == plan:
                    return previous
                raise BusinessError("root already has an immutable plan; preserve it and start a new investigation")
            connection.execute("INSERT INTO cluster_investigations VALUES (?,?,?,?)", (investigation, root, version, dumps(doc)))
            connection.executemany("INSERT INTO cluster_checks (investigation,id,state) VALUES (?,?,'planned')", [(investigation, c["id"]) for c in plan["checks"]])
        self.s.journal.append(actor, "state_change", {"state": "business_investigation_opened", "investigation": investigation}, task_id=root, payload=doc)
        return doc

    def _active(self, doc):
        if orch.is_cancelled(self.s, doc["root_task_id"]):
            raise BusinessError("business investigation was cancelled")
        if snapshot_version(self.s.config.root) != doc["code_version"]:
            raise BusinessError("code changed; old experiments cannot validate the new snapshot")

    def dispatch(self, investigation: str, actor: str, *, check_id: str | None = None, worker: str = "any"):
        self._role(actor, {"head_dispatch"})
        doc = self.get(investigation)
        if orch.task_row(self.s, doc["root_task_id"])["agent"] != actor:
            raise PermissionError("only this investigation's dispatch head can schedule it")
        self._active(doc)
        used, limit, _ = orch.cluster_budget(self.s, doc["root_task_id"])
        if used >= limit:
            raise BusinessError("the investigation's user-configured model budget is exhausted")
        chosen = check_id or self.status(investigation)["next_check"]
        check = next((c for c in doc["plan"]["checks"] if c["id"] == chosen), None)
        if not check:
            raise BusinessError("no pending test to dispatch")
        if worker == "any":
            worker = orch.pick_worker(self.s)
        self._role(worker, {"worker", "investigator"})
        guardian = orch.guardian_for(self.s.config, worker)
        if not guardian or guardian == worker:
            raise BusinessError("a distinct user-configured guardian is required; no models are auto-created")
        self._role(guardian, {"guardian"})
        with self.s.db.tx() as connection:
            row = connection.execute("SELECT * FROM cluster_checks WHERE investigation=? AND id=?", (investigation, chosen)).fetchone()
            if row["state"] != "planned":
                raise BusinessError("test already dispatched; duplicate work is not permitted")
            connection.execute("UPDATE cluster_checks SET state='reserved',worker=?,guardian=? WHERE investigation=? AND id=?", (worker, guardian, investigation, chosen))
        try:
            def bind(connection, task_id):
                connection.execute("UPDATE cluster_checks SET worker_task=?,state='queued' WHERE investigation=? AND id=?", (task_id, investigation, chosen))
            sub = orch.create_subtask(self.s, sender=actor, recipient=worker, title=f"Business test: {chosen}",
                                      instructions=f"Execute cluster_run with investigation={investigation!r}, check={chosen!r}. "
                                                   "Do not invent metrics or claim success from code reading. This runs only the registered isolated adapter. "
                                                   "Report the actual receipt ids; your guardian must execute its independent harness.",
                                      parent_task_id=doc["root_task_id"], data_class=doc["data_class"], on_created=bind)
        except BaseException:
            with self.s.db.tx() as connection:
                connection.execute("UPDATE cluster_checks SET state='planned',worker=NULL,guardian=NULL WHERE investigation=? AND id=? AND state='reserved'", (investigation, chosen))
            raise
        return sub | {"investigation": investigation, "check": chosen, "worker": worker, "guardian": guardian}

    def run(self, investigation: str, check_id: str, actor: str, task_id: str, data_class: str):
        role = self._role(actor, {"worker", "investigator", "guardian"})
        role = "worker" if role == "investigator" else role
        doc = self.get(investigation)
        self._active(doc)
        job = self.s.db.one("SELECT * FROM cluster_checks WHERE investigation=? AND id=?", (investigation, check_id))
        if not job or job[role] != actor:
            raise PermissionError("this actor is not assigned to this business test")
        if role == "worker" and job["worker_task"] != task_id:
            raise PermissionError("worker receipt must come from its assigned task")
        if role == "guardian":
            row = orch.task_row(self.s, task_id)
            if not row or orch.body_of(row).get("review_of") != job["worker_task"]:
                raise PermissionError("guardian must run from its independent review task")
            prior = self.s.db.one("SELECT state FROM cluster_trials WHERE investigation=? AND check_id=? AND role='worker'", (investigation, check_id))
            if not prior or prior["state"] != "finished":
                raise BusinessError("worker execution has not finished")
        check = next(c for c in doc["plan"]["checks"] if c["id"] == check_id)
        contracts = [self._contract(cid, doc["code_version"])["contract"] for cid in check["contracts"]]
        scenario = self.registry.scenarios.get(check["scenario"])
        if scenario is None or scenario.code_version != doc["code_version"]:
            raise BusinessError("trusted adapter must be re-registered after restart; nothing is auto-imported")
        handler = scenario.worker if role == "worker" else scenario.guardian
        if harness_id(handler) != doc["harnesses"][scenario.id][role]:
            raise BusinessError("registered harness changed after planning; old evidence cannot be mixed with it")
        with self.s.db.tx() as connection:
            old = connection.execute("SELECT doc FROM cluster_trials WHERE investigation=? AND check_id=? AND role=?", (investigation, check_id, role)).fetchone()
            if old:
                if old["doc"]:
                    return json.loads(old["doc"])
                raise BusinessError("execution already running or interrupted; do not blindly repeat side effects")
            connection.execute("INSERT INTO cluster_trials VALUES (?,?,?,?,?,'running',NULL)", (investigation, check_id, role, actor, task_id))
        result = execute(self.s, scenario, contracts, role=role, agent_id=actor, repeats=doc["plan"]["repeats"],
                         data_class=stricter(data_class, doc["data_class"]), cancelled=lambda: orch.is_cancelled(self.s, task_id))
        with self.s.db.tx() as connection:
            connection.execute("UPDATE cluster_trials SET state='finished',doc=? WHERE investigation=? AND check_id=? AND role=?", (dumps(result), investigation, check_id, role))
        return result

    def review_instructions(self, worker_task_id):
        rows = self.s.db.query("SELECT investigation,id FROM cluster_checks WHERE worker_task=?", (worker_task_id,))
        return "\n".join(f"Independently execute cluster_run with investigation={r['investigation']!r}, check={r['id']!r}. "
                         "Reading the worker's metrics or agreeing with its text is NOT an independent execution." for r in rows)

    def _verified_pair(self, doc, check):
        rows = self.s.db.query("SELECT * FROM cluster_trials WHERE investigation=? AND check_id=?", (doc["id"], check["id"]))
        trials, evidence = {}, []
        contracts = [self._contract(cid, doc["code_version"])["contract"] for cid in check["contracts"]]
        assignment = self.s.db.one("SELECT worker,guardian FROM cluster_checks WHERE investigation=? AND id=?", (doc["id"], check["id"]))
        for row in rows:
            if not row["doc"]:
                return None, "running_or_interrupted", evidence
            trial = json.loads(row["doc"])
            if trial["status"] != "completed":
                return None, trial["status"], evidence
            if trial["harness"] != doc["harnesses"][check["scenario"]][row["role"]]:
                return None, "wrong_harness", evidence
            if len(trial["records"]) != doc["plan"]["repeats"] * 3:
                return None, "incomplete_evidence", evidence
            phases = {(r["phase"], r["repeat"]) for r in trial["records"]}
            if phases != {(phase, i) for phase in ("baseline", "fault", "rescue") for i in range(doc["plan"]["repeats"])}:
                return None, "incomplete_evidence", evidence
            if row["agent"] != assignment[row["role"]]:
                return None, "wrong_actor", evidence
            for record in trial["records"]:
                eid = record["evidence"]
                payload = {k: v for k, v in record.items() if k != "evidence"}
                if (self.s.evidence.check(eid) != "ok" or self.s.evidence.content(eid) != canonical(payload)
                        or payload["agent_id"] != row["agent"] or payload["role"] != row["role"]
                        or payload["code_version"] != doc["code_version"] or payload["project"] != doc["project"]
                        or payload["trial"] != trial["trial"] or payload["harness"] != trial["harness"]
                        or payload["scenario"] != check["scenario"]):
                    return None, "invalid_evidence", evidence
                metadata = self.s.evidence.get(eid)
                if (metadata["binding"].get("code_version") != doc["code_version"]
                        or metadata["provenance"].get("agent_id") != row["agent"]
                        or metadata["provenance"].get("collected_by") != "cluster.experiments/0"):
                    return None, "wrong_collector", evidence
                source_id = payload["harness_evidence"]
                if (self.s.evidence.check(source_id) != "ok"
                        or hashlib.sha256(self.s.evidence.content(source_id)).hexdigest() != trial["harness"]):
                    return None, "invalid_harness_evidence", evidence
                checks = [evaluate(c, payload["metrics"]) for c in contracts]
                outcome = "unknown" if any(c["status"] == "unknown" for c in checks) else ("violated" if any(c["status"] == "violated" for c in checks) else "holds")
                if checks != payload["checks"] or outcome != payload["outcome"]:
                    return None, "oracle_disagreement", evidence
                if payload["phase"] in {"baseline", "rescue"} and outcome != "holds":
                    return None, "bad_control", evidence
                if payload["phase"] == "fault" and outcome != trial["signature"]:
                    return None, "unstable_signature", evidence
                evidence.append(eid)
            trials[row["role"]] = trial
        if set(trials) != {"worker", "guardian"}:
            return None, "awaiting_independent_execution", evidence
        w, g = trials["worker"], trials["guardian"]
        if w["trial"] == g["trial"] or w["harness"] == g["harness"] or len(evidence) != len(set(evidence)):
            return None, "not_independent", evidence
        if w["signature"] != g["signature"]:
            return None, "disputed", evidence
        return w["signature"], "independently_reproduced_in_scope", evidence

    def status(self, investigation: str):
        doc = self.get(investigation)
        problems, checked, evidence = [], [], []
        support = {h["id"]: [] for h in doc["plan"]["hypotheses"]}
        refutations = {h["id"]: [] for h in doc["plan"]["hypotheses"]}
        compatible = {h["id"] for h in doc["plan"]["hypotheses"]}
        for task_id in orch.tree(self.s, doc["root_task_id"])[1:]:
            task = orch.task_row(self.s, task_id)
            if task["state"] != "finished" or task["outcome"] != "done":
                problems.append(f"{task_id}: agent task not successfully settled")
        for objection in orch.objections(self.s, doc["root_task_id"]):
            problems.append(f"{objection['id']}: unresolved head objection")
        try:
            self._active(doc)
            for check in doc["plan"]["checks"]:
                for cid in check["contracts"]:
                    self._contract(cid, doc["code_version"])
        except BusinessError as error:
            problems.append(str(error))
        for check in doc["plan"]["checks"]:
            try:
                signature, state, receipts = self._verified_pair(doc, check)
            except (BusinessError, KeyError, TypeError, ValueError):
                signature, state, receipts = None, "invalid_or_unavailable_evidence", []
            evidence.extend(receipts)
            checked.append({"id": check["id"], "purpose": check["purpose"], "state": state, "observed": signature})
            if signature and check["purpose"] == "discriminate":
                compatible &= {hid for hid, expected in check["predictions"].items() if expected == signature}
                for hid, expected in check["predictions"].items():
                    target = support if expected == signature else refutations
                    target[hid].append({"check": check["id"], "predicted": expected, "observed": signature, "evidence": receipts})
            if not signature:
                problems.append(f"{check['id']}: {state}")
            elif check["purpose"] == "regression" and signature != "holds":
                problems.append(f"{check['id']}: affected business regression failed")
        if len(compatible) != 1:
            problems.append("competing hypotheses remain" if compatible else "observations contradict all hypotheses")
        pending = []
        for check in doc["plan"]["checks"]:
            row = self.s.db.one("SELECT state FROM cluster_checks WHERE investigation=? AND id=?", (investigation, check["id"]))
            if row["state"] != "planned":
                continue
            values = [check["predictions"].get(h) for h in sorted(compatible)]
            score = sum(a != b for i, a in enumerate(values) for b in values[i + 1:])
            pending.append((-score, check["id"]))
        pending.sort()
        ledger = [{**hypothesis,
                   "state": "refuted_in_declared_scope" if refutations[hypothesis["id"]] else (
                       "compatible_not_proven" if support[hypothesis["id"]] else "untested"),
                   "support": support[hypothesis["id"]], "refutations": refutations[hypothesis["id"]]}
                  for hypothesis in doc["plan"]["hypotheses"]]
        return {"cd_schema": "cd.cluster.status/0", "id": investigation, "root_task_id": doc["root_task_id"],
                "code_version": doc["code_version"], "compatible_hypotheses": sorted(compatible),
                "hypothesis_ledger": ledger,
                "checks": checked, "next_check": pending[0][1] if pending else None,
                "next_check_distinguishes_pairs": -pending[0][0] if pending else 0,
                "delivery_allowed": not problems, "blocking_reasons": problems, "evidence": evidence,
                "structural_analysis_truncated": doc["structural_leads"]["truncated"],
                "interpretation": "controlled_scenarios_only_not_universal_causality", "runtime_trace_coverage": "not_asserted"}

    def delivery_gate(self, root):
        investigation = self.for_root(root)
        return self.status(investigation) if investigation else None
