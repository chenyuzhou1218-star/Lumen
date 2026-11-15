"""Side-effect ledger (schemas/agent/side-effect).

Intent is written before a tool that can change something runs; the result is
written after. If the service dies in between, recovery turns the intent into
'unknown' instead of guessing, and nothing unknown or non-retryable is repeated
automatically.
"""

from __future__ import annotations

import json

from codedoctor import ids
from codedoctor.protocol.registry import validator
from codedoctor.store.db import Database, dumps

SCHEMA = "agent/side-effect.schema.json"


class EffectLedger:
    def __init__(self, db: Database):
        self.db = db

    def _save(self, doc: dict, insert: bool = False) -> dict:
        errors = list(validator(SCHEMA).iter_errors(doc))
        if errors:
            raise ValueError(f"invalid side-effect entry: {errors[0].message}")
        with self.db.tx() as c:
            if insert:
                c.execute("INSERT INTO effects (id, task_id, agent, tool, state, intent_at, doc) VALUES (?,?,?,?,?,?,?)",
                          (doc["id"], doc["task_id"], doc["agent"], doc["tool"], doc["state"], doc["intent_at"], dumps(doc)))
            else:
                c.execute("UPDATE effects SET state = ?, doc = ? WHERE id = ?", (doc["state"], dumps(doc), doc["id"]))
        return doc

    def intent(self, *, task_id: str, agent: str, tool: str, effect_class: str, retry_safe: bool,
               arguments: dict, journal_call: str) -> dict:
        return self._save({
            "cd_schema": "cd.agent.side-effect/0", "id": ids.new_id("eff"), "task_id": task_id, "agent": agent,
            "tool": tool, "effect_class": effect_class, "retry_safe": retry_safe, "arguments": arguments,
            "state": "intent", "intent_at": ids.now(), "journal_call": journal_call,
        }, insert=True)

    def finish(self, effect: dict, *, ok: bool, journal_result: str, summary: str) -> dict:
        effect = {**effect, "state": "done" if ok else "failed", "finished_at": ids.now(),
                  "journal_result": journal_result, "result_summary": summary[:2000]}
        return self._save(effect)

    def mark_unknown(self, task_id: str) -> list[dict]:
        """Recovery: every effect of the task still in 'intent' becomes 'unknown'."""
        changed = []
        for doc in self.for_task(task_id):
            if doc["state"] == "intent":
                changed.append(self._save({**doc, "state": "unknown"}))
        return changed

    def for_task(self, task_id: str) -> list[dict]:
        rows = self.db.query("SELECT doc FROM effects WHERE task_id = ? ORDER BY intent_at, id", (task_id,))
        return [json.loads(r["doc"]) for r in rows]


def describe(effects: list[dict]) -> str:
    """Human/model-readable ledger summary used in interruption reports and resume prompts."""
    if not effects:
        return "No side effects were recorded."
    lines = []
    for e in effects:
        args = json.dumps(e["arguments"], ensure_ascii=False)[:300]
        flag = {"unknown": "UNKNOWN (may or may not have happened)", "done": "done", "failed": "failed", "intent": "in progress"}[e["state"]]
        retry = "safe to retry" if e["retry_safe"] else "NOT safe to retry"
        lines.append(f"- {e['id']} {e['tool']}({args}) [{e['effect_class']}, {retry}]: {flag}")
    return "\n".join(lines)
