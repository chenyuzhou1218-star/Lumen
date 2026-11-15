"""What a finished task leaves in long-term memory (ADR 0003, ADR 0006 M3).

One summary note for the task, plus one 'claim' note per claim the agent submitted in it,
so a later task recalls the specific finding rather than a long summary. A claim note does
not say whether the claim is true: it cites the claim, and recall reads the claim's status
at that time (verified, unverified, stale, refuted).
"""

from __future__ import annotations

import json

from codedoctor.evidence.registry import stricter
from codedoctor.memory.notes import MemoryError_


def claim_note_fields(claim: dict) -> dict:
    """The note fields for one claim, generated from its structure (never from model prose about it)."""
    st = claim["statement"]
    obj = st["object"] if isinstance(st["object"], str) else json.dumps(st["object"]["value"], ensure_ascii=False)
    lines = [f"{claim['claim_type']} ({claim['evidence_level']}): {st['text']}", f"{st['subject']} -{st['relation']}-> {obj}"]
    lines += [f"Condition: {c['text']}" + (f" [{c['fault_model']}]" if c.get("fault_model") else "")
              for c in claim.get("conditions", [])]
    if claim.get("falsification"):
        lines.append(f"Falsify by ({claim['falsification']['method']}): {claim['falsification']['description']}")
    return {
        "kind": "claim", "text": "\n".join(lines)[:20000],
        "entities": [st["subject"]] + ([st["object"]] if isinstance(st["object"], str) else []),
        "evidence": [r["id"] for r in claim.get("evidence", [])][:64], "claims": [claim["id"]],
        "code_version": claim["scope"]["code_version"], "data_class": claim.get("data_class"),
    }


def write(services, *, owner: str, task_id: str, title: str, outcome: str, summary: str, evidence: list[str],
          claims: list[str], source: str, claim_sources: dict[str, str] | None = None, data_class: str | None = None) -> dict:
    """Write the task's memory. `source` is the task's last journal entry; `claim_sources` maps a claim id to the
    tool_result entry that accepted it (falls back to the summary note). `data_class` is the strictest data the task
    saw: its notes are at least that sensitive, which decides where they may be sent (e.g. for embedding).
    Returns the summary note."""
    summary_note = services.notes.write(
        owner=owner, scope="project", kind="summary",
        text=f"Task '{title}' ({task_id}) ended {outcome}.\n{summary[:6000]}",
        evidence=evidence[:64], claims=claims[:64], sources=[source], task_id=task_id, data_class=data_class,
    )
    for cid in claims:
        claim = services.claims.get(cid)
        if claim is None or claim["author"]["id"] != owner or claim["author"].get("task_id") != task_id:
            continue  # only what this agent claimed in this task
        fields = claim_note_fields(claim)
        if data_class:
            fields["data_class"] = stricter(fields["data_class"] or "public", data_class)
        try:
            services.notes.write(owner=owner, scope="project", task_id=task_id,
                                 sources=[(claim_sources or {}).get(cid, summary_note["id"])], **fields)
        except MemoryError_:
            continue  # the claim itself and the summary are stored; a missing extra note must not block the report
    return summary_note
