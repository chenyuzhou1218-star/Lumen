"""The question panel: an agent asks the user a question with options, and goes on with the answer (like Claude Code's
AskUserQuestion). The window lifts a panel above the message box (web/src/Composer.jsx AskPanel); the user's choices come back here.

    questions: 1 to 4, each {question, options: 2 to 6 texts, multi: bool}. The panel adds one more option at the end that the
    user writes in themselves, so an agent never lists "other".

Pending questions live in the running service (nothing is written to disk); they end when answered, when the task is cancelled or
after half an hour.
"""

from __future__ import annotations

import asyncio
import secrets
import time

from codedoctor.agents import orchestration as orch
from codedoctor.agents.tools import TOOLS, Tool, ToolContext, ToolResult, _err, _obj

WAIT_S = 1800


def _store(services) -> dict:
    return services.__dict__.setdefault("_questions", {})


def _poke(services) -> None:
    cb = getattr(services, "asks_changed", None)
    if cb is not None:
        try:
            cb()
        except Exception:
            pass


def pending(services) -> list[dict]:
    """What the window shows now: [{"id", "agent", "items": [{"question", "options", "multi"}]}], oldest first."""
    return [{"id": q["id"], "agent": q["agent"], "items": q["items"]} for q in sorted(_store(services).values(), key=lambda q: q["at"])
            if q["answer"] is None]


def answer(services, qid: str, answers: list[dict]) -> bool:
    """The user's choices: [{"choices": [text, ...], "other": text}], one per question. False when it is no longer waiting."""
    q = _store(services).get(qid)
    if q is None or q["answer"] is not None:
        return False
    lines = []
    for item, a in zip(q["items"], answers):
        picked = [str(c) for c in (a.get("choices") or [])]
        other = str(a.get("other") or "").strip()
        if other:
            picked.append(f"(the user wrote) {other}")
        none = "(skipped by the user: decide this yourself)" if a.get("skipped") else "(no answer)"
        lines.append(f"Q: {item['question']}\nA: {'; '.join(picked) if picked else none}")
    q["answer"] = "\n\n".join(lines)
    _poke(services)
    return True


def follow_up(services, task_id: str, agent: str, question: str, options: list[str]) -> str:
    """A turn ended 被拦下 saying what it needs, without asking (the user, 2026-11-14): the window asks for it in the panel.
    No agent waits for this one: the window sends the answer as the user's next message in that chat (web_chat.answer_ask)."""
    for q in _store(services).values():
        if q.get("followup") and q["task_id"] == task_id:
            return q["id"]
    qid = f"q_{secrets.token_hex(6)}"
    _store(services)[qid] = {"id": qid, "task_id": task_id, "agent": agent, "followup": True, "answer": None, "at": time.time(),
                             "items": [{"question": question[:500], "options": options, "multi": False}]}
    _poke(services)
    return qid


def take_follow_up(services, qid: str) -> dict | None:
    """The follow-up question just answered (taken out of the panel), or None when qid is a question an agent waits for."""
    q = _store(services).get(qid)
    if q is None or not q.get("followup") or q["answer"] is None:
        return None
    _store(services).pop(qid, None)
    _poke(services)
    return q


async def ask_user(ctx: ToolContext, args: dict) -> ToolResult:
    services = ctx.services
    qid = f"q_{secrets.token_hex(6)}"
    items = [{"question": str(i["question"])[:500], "options": [str(o)[:200] for o in i["options"]], "multi": bool(i.get("multi"))}
             for i in args["questions"]]
    entry = {"id": qid, "task_id": ctx.task_id, "agent": ctx.agent_id, "items": items, "answer": None, "at": time.time()}
    _store(services)[qid] = entry
    _poke(services)
    deadline = time.monotonic() + WAIT_S
    try:
        while entry["answer"] is None and time.monotonic() < deadline:
            if orch.is_cancelled(services, ctx.task_id):
                break
            await asyncio.sleep(0.3)
    finally:
        _store(services).pop(qid, None)
        _poke(services)
    if entry["answer"] is None:
        return _err("The user did not answer (or the task was cancelled). Do not guess: say what you still need to know.")
    return ToolResult(ok=True, content="The user answered:\n\n" + entry["answer"], progress=True)


TOOLS["ask_user"] = Tool(
    "ask_user",
    "Ask the user questions in a panel above their message box and wait for the answers. Use it when you are not sure enough what "
    "they want: ask specific questions and give 2 to 6 concrete options for each (set multi for several answers). The panel adds a "
    "last option the user writes in themselves. Up to 4 questions at once. Never ask about permissions, approvals or whether "
    "you may change files: the program handles those by the user's own setting - ask only about what they want.",
    _obj({"questions": {"type": "array", "minItems": 1, "maxItems": 4,
                        "items": _obj({"question": {"type": "string", "minLength": 1},
                                       "options": {"type": "array", "minItems": 2, "maxItems": 6, "items": {"type": "string", "minLength": 1}},
                                       "multi": {"type": "boolean"}}, ["question", "options"])}}, ["questions"]),
    ask_user)
