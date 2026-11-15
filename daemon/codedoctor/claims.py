"""Claim store. Agents submit the statement part; the system fills identity,
authorship and status, validates against schemas/claim, and refuses any claim
that cites evidence the registry does not have (or whose bytes changed).

Status is never set by the author (except withdrawing). Reviews, validations
and every status change are stored; claim_rules decides transitions."""

from __future__ import annotations

import json

from codedoctor import ids
from codedoctor.evidence.registry import EvidenceStore
from codedoctor.protocol import semantic
from codedoctor.protocol.registry import validator, validator_for
from codedoctor.store.db import Database, dumps

SCHEMA = "claim/claim.schema.json"
EVENT_SCHEMA = "claim/status-event.schema.json"
REVIEW_REF = "https://code-doctor.local/schemas/v0/agent/message.schema.json#/$defs/review"
AGENT_FIELDS = {"claim_type", "statement", "evidence_level", "scope", "evidence", "depends_on",
                "falsification", "conditions", "supersedes", "data_class"}
TERMINAL = {"refuted", "withdrawn", "superseded"}


class ClaimRejected(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


class ClaimStore:
    def __init__(self, db: Database, evidence: EvidenceStore):
        self.db = db
        self.evidence = evidence

    # --- claims ---------------------------------------------------------------------

    def submit(self, draft: dict, *, author: dict) -> dict:
        extra = set(draft) - AGENT_FIELDS
        if extra:
            raise ClaimRejected([f"fields not allowed in a draft: {sorted(extra)} (id, author, status are set by the system)"])
        claim = {"cd_schema": "cd.claim/0", "id": ids.new_id("clm"), "created_at": ids.now(),
                 "author": author, "status": "proposed", "evidence": [], **draft}
        problems = [
            f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
            for e in validator(SCHEMA).iter_errors(claim)
        ][:8]
        if not problems:
            problems = [f"{v.path}: {v.message}" for v in semantic.check(SCHEMA, claim)]
        problems += self._evidence_problems([r.get("id") for r in claim.get("evidence", []) if isinstance(r, dict)])
        for dep in claim.get("depends_on", []):
            if self.get(dep) is None:
                problems.append(f"depends_on: unknown claim {dep}")
        old = self.get(claim["supersedes"]) if claim.get("supersedes") else None
        if claim.get("supersedes") and old is None:
            problems.append(f"supersedes: unknown claim {claim['supersedes']}")
        if problems:
            raise ClaimRejected(problems)
        with self.db.tx() as c:
            c.execute(
                "INSERT INTO claims (id, author, task_id, status, created_at, doc) VALUES (?,?,?,?,?,?)",
                (claim["id"], author["id"], author.get("task_id"), claim["status"], claim["created_at"], dumps(claim)),
            )
        if old and old["status"] not in TERMINAL:
            self.set_status(old["id"], "superseded", by="system", rule="superseded_by", basis={"superseded_by": claim["id"]})
        return claim

    def _evidence_problems(self, ev_ids: list[str | None]) -> list[str]:
        out = []
        for i, ev_id in enumerate(ev_ids):
            if ev_id and (state := self.evidence.check(ev_id)) != "ok":
                out.append(f"evidence/{i}: {ev_id} is {state} - cite only ids returned by tools")
        return out

    def get(self, claim_id: str) -> dict | None:
        row = self.db.one("SELECT doc FROM claims WHERE id = ?", (claim_id,))
        return json.loads(row["doc"]) if row else None

    def by_task(self, task_id: str) -> list[dict]:
        return [json.loads(r["doc"]) for r in self.db.query("SELECT doc FROM claims WHERE task_id = ? ORDER BY created_at", (task_id,))]

    def open_ids(self) -> list[str]:
        return [r["id"] for r in self.db.query("SELECT id FROM claims WHERE status IN ('proposed', 'supported') ORDER BY created_at")]

    # --- status -----------------------------------------------------------------------

    def set_status(self, claim_id: str, to: str, *, by: str, rule: str, basis: dict) -> dict:
        claim = self.get(claim_id)
        event = {"cd_schema": "cd.claim.status-event/0", "claim_id": claim_id, "from": claim["status"], "to": to,
                 "at": ids.now(), "by": by, "rule": rule, "basis": basis}
        errors = list(validator(EVENT_SCHEMA).iter_errors(event))
        if errors:
            raise ValueError(f"illegal status change: {errors[0].message}")
        claim["status"] = to
        with self.db.tx() as c:
            c.execute("UPDATE claims SET status = ?, doc = ? WHERE id = ?", (to, dumps(claim), claim_id))
            c.execute("INSERT INTO claim_events (claim_id, at, doc) VALUES (?,?,?)", (claim_id, event["at"], dumps(event)))
        return event

    def events(self, claim_id: str) -> list[dict]:
        return [json.loads(r["doc"]) for r in self.db.query("SELECT doc FROM claim_events WHERE claim_id = ? ORDER BY seq", (claim_id,))]

    def withdraw(self, claim_id: str, by: str, reason: str) -> dict:
        claim = self.get(claim_id)
        if claim is None:
            raise ClaimRejected([f"unknown claim {claim_id}"])
        if claim["author"]["id"] != by:
            raise ClaimRejected(["only the author can withdraw a claim"])
        if claim["status"] in TERMINAL:
            raise ClaimRejected([f"claim is already {claim['status']}"])
        return self.set_status(claim_id, "withdrawn", by=by, rule="withdrawn_by_author", basis={"detail": reason[:4000]})

    # --- reviews ----------------------------------------------------------------------

    def add_review(self, claim_id: str, *, reviewer: str, verdict: str, notes: str, evidence: list[str] | None = None) -> dict:
        claim = self.get(claim_id)
        if claim is None:
            raise ClaimRejected([f"unknown claim {claim_id}"])
        if reviewer == claim["author"]["id"]:
            raise ClaimRejected(["a claim cannot be reviewed by its own author"])
        body = {"review_id": ids.new_id("rev"), "claim_id": claim_id, "verdict": verdict, "notes": notes}
        if evidence:
            body["evidence"] = evidence
        problems = [e.message for e in validator_for(REVIEW_REF).iter_errors(body)]
        problems += self._evidence_problems(evidence or [])
        if problems:
            raise ClaimRejected(problems)
        doc = {**body, "reviewer": reviewer, "at": ids.now()}
        with self.db.tx() as c:
            c.execute("INSERT INTO reviews (id, claim_id, reviewer, verdict, at, doc) VALUES (?,?,?,?,?,?)",
                      (doc["review_id"], claim_id, reviewer, verdict, doc["at"], dumps(doc)))
        return doc

    def reviews(self, claim_id: str) -> list[dict]:
        return [json.loads(r["doc"]) for r in self.db.query("SELECT doc FROM reviews WHERE claim_id = ? ORDER BY at, id", (claim_id,))]

    # --- validations ------------------------------------------------------------------

    def save_validation(self, doc: dict) -> None:
        with self.db.tx() as c:
            c.execute("INSERT INTO validations (id, claim_id, overall, validated_at, doc) VALUES (?,?,?,?,?)",
                      (doc["id"], doc["claim_id"], doc["overall"], doc["validated_at"], dumps(doc)))

    def latest_validation(self, claim_id: str) -> dict | None:
        row = self.db.one("SELECT doc FROM validations WHERE claim_id = ? ORDER BY validated_at DESC, id DESC LIMIT 1", (claim_id,))
        return json.loads(row["doc"]) if row else None
