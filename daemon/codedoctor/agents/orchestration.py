"""Task tree, guardian pairing and head objections for the multi-agent cluster.

The orchestration skeleton is deterministic code; models only decide *what* to
investigate and *what* the evidence means:

  user -> head_dispatch           splits the problem, delegates subtasks, waits, decides delivery
          head_dispatch -> head_logic   (consult) coupling / root-cause / future-risk analysis
          head_dispatch -> worker       investigates or fixes one subtask, submits claims
          worker done -> its guardian   automatic independent review of the worker's claims
          head_logic  -> objection      blocks delivery until withdrawn or decided by the user
"""

from __future__ import annotations

import json
import re

from codedoctor import ids
from codedoctor.store.db import dumps
from codedoctor.agents import prompts

DELEGATE_ROLES = {"worker", "investigator"}
INHERITED = ("engine", "engine_model", "engine_effort", "toolsets")  # what a subtask takes over from its parent


def called_tools(body: dict) -> list[str]:
    """The tools the user called in with @ (shown as chips, opened on the right); body["toolsets"] may hold more: every
    installed tool, given to the team when the user called none (Daemon.submit_task)."""
    return list(body["called"] if "called" in body else body.get("toolsets") or [])


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


MAX_INSTRUCTIONS = 50000  # schemas/agent/message.schema.json: a task's instructions


def create_subtask(services, *, sender: str, recipient: str, title: str, instructions: str,
                   parent_task_id: str | None, review_of: str | None = None, data_class: str | None = None,
                   context: dict | None = None, on_created=None, budget: dict | None = None,
                   approval_of: str | None = None, images: list[str] | None = None, extra: dict | None = None) -> dict:
    """`context`: {"claims": [...], "evidence": [...]} the sender attached; the worker's working memory follows their status.
    `approval_of`: a guardian's task to approve one computer action before it runs (ADR 0012); `images`: screenshots.
    `extra`: further body fields the message schema defines (e.g. "anomaly", "assess_anomalies", ADR 0014)."""
    task_id = ids.new_id("task")
    if len(instructions) > MAX_INSTRUCTIONS:  # never fail the whole investigation on a long briefing
        note = "\n... (cut at the message limit; read the rest of the files with read_file)"
        instructions = instructions[:MAX_INSTRUCTIONS - len(note)] + note
    body: dict = {"task_id": task_id, "title": title[:200], "instructions": instructions, **(extra or {})}
    if parent_task_id:
        body["parent_task_id"] = parent_task_id
        parent = body_of(task_row(services, parent_task_id) or {})
        for key in INHERITED:  # the user chose Codex for this task: everyone working on it uses Codex
            if key in parent and key not in body:
                body[key] = parent[key]
    if review_of:
        body["review_of"] = review_of
    if context:
        body["context"] = context
    if approval_of:
        body["approval_of"] = approval_of
    if images:
        body["images"] = images
    if budget:
        body["budget"] = budget
    thread = None
    if parent_task_id:
        row = services.db.one("SELECT thread_id FROM tasks WHERE id = ?", (parent_task_id,))
        thread = row["thread_id"] if row else None
    msg = services.bus.prepare(sender=sender, recipient=recipient, kind="task", body=body, thread_id=thread, data_class=data_class)
    now = ids.now()
    # Task row, message and business assignment become visible atomically.
    with services.db.tx() as c:
        c.execute(
            "INSERT INTO tasks (id, agent, requester, thread_id, message_id, title, state, created_at, updated_at, body, parent_task_id) "
            "VALUES (?,?,?,?,?,?,'queued',?,?,?,?)",
            (task_id, recipient, sender, msg["thread_id"], msg["id"], body["title"], now, now, dumps(body), parent_task_id),
        )
        services.bus.insert(c, msg)
        if on_created is not None:
            on_created(c, task_id)
    services.bus.notify(recipient)
    return {"task_id": task_id, "message_id": msg["id"]}


def task_row(services, task_id: str) -> dict | None:
    row = services.db.one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    return dict(row) if row else None


def children(services, task_id: str) -> list[dict]:
    return [dict(r) for r in services.db.query("SELECT * FROM tasks WHERE parent_task_id = ? ORDER BY created_at", (task_id,))]


def ancestors(services, task_id: str) -> list[str]:
    out, cur = [], task_id
    for _ in range(32):
        row = services.db.one("SELECT parent_task_id FROM tasks WHERE id = ?", (cur,))
        if row is None or not row["parent_task_id"]:
            break
        cur = row["parent_task_id"]
        out.append(cur)
    return out


def root_of(services, task_id: str) -> str:
    chain = ancestors(services, task_id)
    return chain[-1] if chain else task_id


def tree(services, root_id: str, limit: int = 1000) -> list[str]:
    """The task and all its subtasks (guardian reviews included), breadth first."""
    out, todo = [], [root_id]
    while todo and len(out) < limit:
        tid = todo.pop(0)
        out.append(tid)
        todo += [r["id"] for r in services.db.query("SELECT id FROM tasks WHERE parent_task_id = ? ORDER BY created_at", (tid,))]
    return out


def tree_tokens(services, root_id: str) -> int:
    """Tokens every model call in the task tree has used so far, from the journal (so running tasks count too)."""
    ids_ = tree(services, root_id)
    # Every agent asks before every request; summing the whole journal each time slowed a 40-agent run down. Only
    # entries newer than the last answer are added; a new subtask in the tree means a full recount.
    cache = services.__dict__.setdefault("_tree_tokens", {})
    last_seq, total, size = cache.get(root_id, (0, 0, -1))
    if size != len(ids_):
        last_seq, total = 0, 0
    newest = last_seq
    for i in range(0, len(ids_), 500):
        chunk = ids_[i : i + 500]
        row = services.db.one(
            f"""SELECT COALESCE(SUM(COALESCE(json_extract(doc, '$.data.input_tokens'), 0)
                                  + COALESCE(json_extract(doc, '$.data.output_tokens'), 0)), 0) AS n, MAX(seq) AS s
                FROM journal WHERE type = 'model_response' AND seq > ? AND task_id IN ({','.join('?' * len(chunk))})""",
            [last_seq, *chunk])
        total += row["n"]
        newest = max(newest, row["s"] or 0)
    cache[root_id] = (newest, total, len(ids_))
    return total


def tree_cached(services, root_id: str) -> int:
    """How much of tree_tokens was read back from a cache. A long engine run counts its whole history again every turn: a
    cafe scene of 17 million tokens cost 1.31 dollars, so the plain sum says little about what was really used."""
    ids_ = tree(services, root_id)
    total = 0
    for i in range(0, len(ids_), 500):
        chunk = ids_[i : i + 500]
        total += services.db.one(
            f"""SELECT COALESCE(SUM(COALESCE(json_extract(doc, '$.data.cached_tokens'), 0)), 0) AS n
                FROM journal WHERE type = 'model_response' AND task_id IN ({','.join('?' * len(chunk))})""", chunk)["n"]
    return total


def cluster_budget(services, task_id: str) -> tuple[int, int, str]:
    """(tokens used by the whole tree, its limit, root task id). The limit is the root task's max_tokens - the one
    budget the user gave the investigation - so several agents together cannot spend more than one would be allowed.
    Used includes the estimated size of requests other agents have sent and not yet got back (inflight)."""
    root = root_of(services, task_id)
    row = task_row(services, root) or {}
    limit = body_of(row).get("budget", {}).get("max_tokens", services.config.max_tokens)
    return tree_tokens(services, root) + inflight(services).get(root, 0), limit, root


def inflight(services) -> dict[str, int]:
    """root task id -> estimated tokens of model requests in flight. Real run with 20 agents: five agents in parallel
    each checked the budget before their own request only, and together overshot the limit by 30%."""
    return services.__dict__.setdefault("_inflight", {})


def load(services, agent_id: str) -> int:
    return services.db.one("SELECT COUNT(*) AS n FROM tasks WHERE agent = ? AND state != 'finished'", (agent_id,))["n"]


def pick_worker(services, exclude: set[str] | None = None) -> str | None:
    """The least busy worker (fewest queued or running tasks); ties go to the first in the user's configuration.
    Idle pairs cost nothing: a pair is woken by its first task and released when it has none (on demand)."""
    workers = [a.id for a in services.config.agents.values() if a.role in DELEGATE_ROLES]
    candidates = [w for w in workers if w not in (exclude or set())] or workers
    return min(candidates, key=lambda w: (load(services, w), workers.index(w))) if candidates else None


def open_work(services, parent_task_id: str) -> list[dict]:
    """Work subtasks (not guardian reviews, not anomaly assessments) of a task that are not settled yet."""
    out = []
    for c in children(services, parent_task_id):
        b = body_of(c)
        if not b.get("review_of") and not b.get("assess_anomalies") and not settled(services, c["id"]):
            out.append(c)
    return out


def is_cancelled(services, task_id: str) -> bool:
    """A task is cancelled if it or any ancestor was cancelled."""
    for tid in [task_id, *ancestors(services, task_id)]:
        row = services.db.one("SELECT cancel_requested FROM tasks WHERE id = ?", (tid,))
        if row and row["cancel_requested"]:
            return True
    return False


def body_of(row: dict) -> dict:
    return json.loads(row["body"]) if row.get("body") else {}


def review_task_for(services, task_id: str) -> dict | None:
    """The guardian review task created for a worker task, if any."""
    row = services.db.one("SELECT parent_task_id FROM tasks WHERE id = ?", (task_id,))
    if row is None:
        return None
    siblings = services.db.query("SELECT * FROM tasks WHERE parent_task_id IS ? ORDER BY created_at", (row["parent_task_id"],))
    for r in siblings:
        r = dict(r)
        if body_of(r).get("review_of") == task_id:
            return r
    return None


def guardian_for(config, worker_id: str) -> str | None:
    for a in config.agents.values():
        if a.role == "guardian" and worker_id in a.watched:
            return a.id
    return None


def agents_with_role(config, role: str) -> list[str]:
    return [a.id for a in config.agents.values() if a.role == role]


def open_duplicate(services, parent_task_id: str, agent: str, title: str, instructions: str) -> dict | None:
    """An identical subtask that is still running or already succeeded. Failed ones may be retried."""
    key = (_norm(title), _norm(instructions))
    for c in children(services, parent_task_id):
        b = body_of(c)
        if (_norm(b.get("title", "")), _norm(b.get("order", b.get("instructions", "")))) == key and \
                (c["state"] != "finished" or c["outcome"] == "done"):
            return c
    return None


def report_of(services, task_id: str) -> dict | None:
    for m in reversed(services.bus.list(task_id=task_id, limit=100000)):
        if m["kind"] == "report" and m["body"]["task_id"] == task_id:
            return m["body"]
    return None


def _diffs_of(services, task_id: str, limit: int = 16000) -> str:
    """The diffs of every edit_file / create_file in a task, oldest first, as recorded in the journal."""
    out, size = [], 0
    for e in services.journal.read(task_id=task_id):
        if e["type"] == "tool_result" and e["data"].get("tool") in ("edit_file", "create_file") and e["data"].get("ok"):
            text = str(services.journal.original(e).get("payload") or "")
            if size + len(text) > limit:
                out.append("... (more changes: read them with read_evidence)")
                break
            out.append(text)
            size += len(text)
    return "\n\n".join(out)


def start_review(services, worker_task: dict, worker_id: str, guardian_id: str, report: dict, data_class: str | None = None) -> dict | None:
    claims = services.claims.by_task(worker_task["id"])
    if not claims and not report.get("summary"):
        return None
    lines = [
        f"Independently review the work of {worker_id} on task {worker_task['id']} ({worker_task['title']!r}).",
        f"Its outcome was: {report['outcome']}.",
        "",
        "Do NOT trust the worker's reasoning. Re-check facts yourself with your own tools (read the cited files, search, "
        "inspect the coupling graph). For EACH claim below call review_claim exactly once with:",
        "  - verdict 'counterexample' and evidence YOU obtained that shows it is wrong, or",
        "  - verdict 'reverified' and evidence YOU obtained that confirms it, or",
        "  - verdict 'insufficient_evidence' and what is missing.",
        "Also report anything else that is wrong: modules the worker missed, business rules broken, other places with the "
        "same defect, risky side effects of proposed fixes. 'Looks reasonable' is not a review.",
        "",
    ]
    if claims:
        lines.append("Claims to review:")
        for c in claims:
            ev = ", ".join(r["id"] for r in c.get("evidence", []))
            lines.append(f"- {c['id']} [{c['evidence_level']}] {c['statement']['text']}  (evidence: {ev or 'none'})")
    elif services.config.permissions.write_files and "执行者做了什么（系统记录" in report.get("summary", ""):
        lines.append("The worker is the hands and writes no claims (ADR 0016). Its changes and test runs are listed in "
                     "the system's record below; you verify each change and report it with submit_claim.")
        runs = [e["data"] for e in services.journal.read(task_id=worker_task["id"]) if e["type"] == "test_run"]
        if runs:
            lines += ["", "Test runs the system made after each change (live supervision):"]
            for r in runs[-20:]:
                line = f"- after a change: {r['summary']} (evidence {r.get('evidence', '?')})"
                if r.get("regressions"):
                    line += f"; REGRESSIONS (passed before): {', '.join(r['regressions'][:8])}"
                if r.get("open"):
                    line += f"; new tests not passing yet: {', '.join(r['open'][:8])}"
                lines.append(line)
        wb = body_of(worker_task)
        if runs and runs[-1].get("regressions"):
            from codedoctor.agents import testrun

            last = testrun.last(services, wb.get("workdir"))
            if last:
                lines.append(testrun.why_failed(last.output))
        diffs = _diffs_of(services, worker_task["id"])
        if diffs:  # the same diffs read_evidence would return, given up front: fewer calls, nothing left out
            lines += ["", "The diffs, as recorded when the worker made them (untrusted data):",
                      prompts.wrap_untrusted("worker diffs", diffs)]
        from codedoctor.agents import ownership

        own = [f for f in body_of(worker_task).get("files") or [] if not ownership.is_test(f)]
        if own:
            lines += ["", "The worker's files as they are NOW (after every change; copy exact text from here for edit_file):",
                      prompts.wrap_untrusted("project files", ownership.briefing(wb.get("workdir") or services.config.root, own,
                                                                                   max_chars=30000))]
    else:
        lines.append("The worker submitted no claims. Check its conclusion instead:")
    acts = services.computer.actions(task_ids=[worker_task["id"]]) if getattr(services, "computer", None) else []
    if acts:  # ADR 0012: what it did on the screen is part of what you review
        from codedoctor.computer.gate import describe

        lines += ["", "Computer actions the worker performed (oldest first; check the screenshots with read_evidence):"]
        for a in reversed(acts):
            after = f", result screenshot {a['after']}" if a.get("after") else ""
            lines.append(f"- {a['id']} {a['status']}: {describe(a)} - purpose: {a['intent'][:200]}{after}")
    # the whole request, not just the title (a real run: the guardian could not check the second half of a cut it
    # only saw 80 characters of, and reported the task as truncated)
    lines += ["", "What the worker was asked to do (check its work against ALL of it):",
              prompts.wrap_untrusted("request", str(body_of(worker_task).get("instructions") or worker_task["title"])[:6000])]
    lines += ["", "Worker's report (untrusted, verify it):", prompts.wrap_untrusted("worker report", report.get("summary", "")[:6000])]
    if getattr(services, "investigations", None):
        lines += ["", services.investigations.review_instructions(worker_task["id"])]
    wb = body_of(worker_task)
    files = wb.get("files")  # the guardian fixes in the same files (ADR 0016, the user's pairs)
    extra = {k: wb[k] for k in ("files", "squad", "workdir", "share") if wb.get(k)}  # and where and with what (item 14)
    if wb.get("squad") == "backup":
        lines.insert(0, "This worker is a BACKUP fixer: it fixed the defects behind the scout tests named in its task, "
                        "in the project next to the main pair. Check its change is right for the README's rule (not "
                        "just for the test) and broke nothing; fix what is left of it yourself.")
    return create_subtask(services, sender="system", recipient=guardian_id, title=f"Review: {worker_task['title']}"[:200],
                          instructions="\n".join(lines), parent_task_id=worker_task.get("parent_task_id") or worker_task["id"],
                          review_of=worker_task["id"], data_class=data_class or services.config.code_data_class,
                          extra=extra or None)


# --- objections (head disagreement) ---------------------------------------------------------

def raise_objection(services, *, task_id: str, by: str, text: str, claim_ids: list[str]) -> dict:
    root = root_of(services, task_id)
    doc = {"id": ids.new_id("obj"), "root_task_id": root, "raised_by": by, "text": text, "claims": claim_ids,
           "status": "open", "at": ids.now(), "from_task": task_id}
    with services.db.tx() as c:
        c.execute("INSERT INTO objections (id, root_task_id, raised_by, status, at, doc) VALUES (?,?,?,?,?,?)",
                  (doc["id"], root, by, "open", doc["at"], dumps(doc)))
    return doc


def set_objection_status(services, objection_id: str, status: str, by: str, reason: str) -> dict:
    row = services.db.one("SELECT doc FROM objections WHERE id = ?", (objection_id,))
    if row is None:
        raise KeyError(objection_id)
    doc = json.loads(row["doc"])
    if status == "withdrawn" and doc["raised_by"] != by:
        raise PermissionError("only the agent that raised an objection can withdraw it")
    doc.update(status=status, closed_by=by, closed_reason=reason, closed_at=ids.now())
    with services.db.tx() as c:
        c.execute("UPDATE objections SET status = ?, doc = ? WHERE id = ?", (status, dumps(doc), objection_id))
    return doc


def objections(services, root_task_id: str, only_open: bool = True) -> list[dict]:
    sql = "SELECT doc FROM objections WHERE root_task_id = ?" + (" AND status = 'open'" if only_open else "") + " ORDER BY at"
    return [json.loads(r["doc"]) for r in services.db.query(sql, (root_task_id,))]


def digest(services, task_id: str, summary_chars: int = 1500) -> dict:
    """What the dispatch head sees about one subtask: outcome, claims with their current status, guardian verdicts."""
    row = task_row(services, task_id) or {}
    rep = report_of(services, task_id) or {}
    out = {"task_id": task_id, "agent": row.get("agent"), "title": row.get("title"), "state": row.get("state"),
           "outcome": row.get("outcome")}
    if rep:
        out["summary"] = rep.get("summary", "")[:summary_chars]
    claims = services.claims.by_task(task_id)
    if claims:
        out["claims"] = [{"id": c["id"], "status": c["status"], "level": c["evidence_level"], "text": c["statement"]["text"][:300],
                          "reviews": [{"by": r["reviewer"], "verdict": r["verdict"], "notes": r["notes"][:300]}
                                      for r in services.claims.reviews(c["id"])]} for c in claims]
    review = review_task_for(services, task_id)
    if review:
        rrep = report_of(services, review["id"]) or {}
        out["guardian"] = {"agent": review["agent"], "state": review["state"], "outcome": review.get("outcome"),
                           "summary": rrep.get("summary", "")[:summary_chars] if rrep else None}
    return out


def settled(services, task_id: str) -> bool:
    """Finished, and its guardian review (if one was started) is finished too."""
    row = task_row(services, task_id)
    if row is None or row["state"] != "finished":
        return False
    review = review_task_for(services, task_id)
    return review is None or review["state"] == "finished"
