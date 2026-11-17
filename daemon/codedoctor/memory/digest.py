"""Lumen's long-term memory of the user, shared by every conversation (the user, 2026-11-14/15: each conversation is its own,
but what one learns the others know; every new conversation starts with an AI's summary of the earlier ones - a few K to some
ten K - that tells it who I am, how I talk and what we did, so it "很懂我").

Two texts, written by the model:
  about the user  ~/.codedoctor/memory/about_user.md   every project: who they are, how they talk, taste, standing rules
  this project    <project data>/digest.md              what each conversation did and decided, where things stand now

When they are written:
  - after turns end: the turns that ended close together are folded in, a little after the last of them (note_turn);
  - when a new conversation starts (before_new_chat): turns not folded in yet are folded in first, and the new conversation
    waits for that (at most NEW_CHAT_WAIT_S). With no memory yet, or every REVIEW_EVERY new conversations, the model reads
    the earlier conversations themselves from the database and writes the memory again from them - the increments cannot
    drift for long.
Every turn of the lead starts with both (team.memory_notes; a kept Claude Code session gets them again only when they
changed). The model is the one the user chose for that turn - never another one.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from pathlib import Path

# characters each (the user, 2026-11-15: "从零 k 到八十 k 左右"): nothing while there is no history, growing with it, together
# some 80K at most; the model writes only as much as the history is worth
USER_MAX, PROJECT_MAX = 10000, 70000  # the hard limit: 80K together, for very long work only
NORMAL_MAX = 50000  # what the memory normally stays within (the user: "正常情况下极限也就是个五十 K")
QUIET_S = 20.0  # turns ending within this of each other are folded into one rewrite
TURN_CHARS = 2500  # of each message and each answer, for a rewrite
HISTORY_CHARS = 150000  # of the earlier conversations, newest first, for a review from the database
NEW_CHAT_WAIT_S = 90.0  # a new conversation waits at most this long for the memory to be brought up to date
REVIEW_EVERY = 15  # new conversations between two reviews from the database
HIDDEN = "\n\n<<lumen:context>>\n"  # what the window adds to a message (desktop/web_chat.py): not the user's words

SYSTEM = ("You keep the long-term memory that Lumen, an AI assistant, has of one user. You only write the memory; you do "
          "not answer the user and you use no tools.")

ASK = """Below are the current memory (two parts) and {what}. Several conversations may run at the same time; they all share
this memory. Write both parts again so that they hold what is new as well. Keep what helps the next conversation
understand this person and carry on the work, drop chatter and what was replaced. The length follows the history: a few
lines when there is little, long and detailed when there is much (decisions, file names, what was tried and why it failed,
the user's exact rules). Both parts together normally stay within {normal} characters; only a very long history of big,
long-running work may take more, and never more than the limits below (together {hard}).

PART 1, ABOUT THE USER (all their projects; at most {user_max} characters): who they are and what they do; how they talk
(voice input, loose grammar, the words they use); their taste and the quality they expect; the standing rules they gave
(what to always do, what never to do), close to their own words; what annoys them; their languages. Only what lasts beyond
one task.

PART 2, THIS PROJECT ({project}; at most {project_max} characters): what the project is; what was done and decided, and in
which conversation when it matters; where things stand now; open problems and what the user asked for that is not done yet.
The newest matters most: merge repeats.

Never invent anything. Never keep secrets (API keys, passwords, tokens, card numbers). Write in the language the user writes
in. Answer with exactly the line <<about_user>>, then part 1, then the line <<project>>, then part 2, and nothing else.

CURRENT MEMORY
<<about_user>>
{about_user}
<<project>>
{project_text}

{heading}
{turns}"""

_SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|sk-ant-[A-Za-z0-9_\-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|"
                     r"xox[abp]-[A-Za-z0-9\-]{10,}|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})")

_pending: dict[str, list[dict]] = {}  # project data folder -> turns waiting for the next rewrite
_jobs: dict[str, asyncio.Task] = {}
_locks: dict[str, asyncio.Lock] = {}


def home() -> Path:
    return Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor")


def user_file() -> Path:
    return home() / "memory" / "about_user.md"


def project_file(services) -> Path:
    return Path(services.config.data_dir) / "digest.md"


def _state_file(services) -> Path:
    return Path(services.config.data_dir) / "digest_state.json"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".digest-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    os.replace(tmp, path)  # whole or not at all: another window may be reading it


def _state(services) -> dict:
    try:
        return json.loads(_state_file(services).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_text(path: Path, text: str) -> None:
    """The user's own wording of a part (设置 → 长期记忆): written as it is, secrets left out."""
    _write(path, _clean(text))


def forget_pending(services) -> None:
    """The user cleared the memory (设置 → 长期记忆): nothing waiting is folded in, and a review reads only what is said from now
    on - the memory is not rebuilt from the conversations before."""
    key = str(services.config.data_dir)
    _pending.pop(key, None)
    job = _jobs.pop(key, None)
    if job is not None and not job.done():
        job.cancel()
    state = _state(services)
    state["since"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    state["reviewed_at_chat"] = int(state.get("chats", 0))
    try:
        _write(_state_file(services), json.dumps(state))
    except OSError:
        pass


def text(services) -> str:
    """The memory as the lead's turn starts with it; "" while there is none yet."""
    about, project = _read(user_file()), _read(project_file(services))
    if not (about or project):
        return ""
    parts = ["WHAT YOU KNOW FROM EARLIER CONVERSATIONS (Lumen's long-term memory, an AI's summary of the earlier conversations, "
             "shared by all conversations with this user; others may be running at the same time and add to it). Use it the "
             "way a colleague uses what they know about someone: keep to their rules and style without being told again, and "
             "do not recite it back to them."]
    if about:
        parts.append("About the user:\n" + about)
    if project:
        parts.append(f"This project ({services.config.name}):\n" + project)
    return "\n\n".join(parts) + "\n\n---\n\n"


def _clean(words: str) -> str:
    return _SECRET.sub("[secret left out]", (words or "").split(HIDDEN)[0]).strip()


def _cut(words: str, n: int = TURN_CHARS) -> str:
    return words if len(words) <= n else words[:n] + " [...]"


def _off() -> bool:
    return bool(os.environ.get("LUMEN_NO_DIGEST"))


def choice_of(rt, body: dict) -> dict | None:
    """The model the user chose for this turn, to write the memory with as well."""
    b = rt._engine_body(body)
    if b.get("engine"):
        return {"engine": b["engine"], "model": b.get("engine_model")}
    chosen = body.get("model") or {}
    endpoint, model = (chosen["endpoint"], chosen["model"]) if chosen.get("endpoint") else (rt.cfg.primary.endpoint, rt.cfg.primary.model)
    return {"endpoint": endpoint, "model": model} if endpoint in rt.s.config.endpoints else None


def note_turn(rt, body: dict, outcome: str, summary: str) -> None:
    """A turn of the user's conversation ended: it goes into the memory with the next rewrite."""
    if outcome in ("cancelled", "interrupted") or _off():
        return
    choice = choice_of(rt, body)
    if choice is None:
        return
    key = str(rt.s.config.data_dir)
    _pending.setdefault(key, []).append({"chat": body.get("chat_of") or body["task_id"], "at": time.strftime("%Y-%m-%d %H:%M"),
                                         "user": _cut(_clean(body.get("instructions", ""))),
                                         "answer": _cut(_clean(summary)), "outcome": outcome, "choice": choice})
    job = _jobs.get(key)
    if job is None or job.done():
        try:
            _jobs[key] = asyncio.ensure_future(_later(rt.s, key))
        except RuntimeError:  # no event loop (a direct call in a test): it waits for the next turn
            pass


async def _later(services, key: str) -> None:
    while True:
        seen = len(_pending.get(key, []))
        await asyncio.sleep(QUIET_S)
        if len(_pending.get(key, [])) == seen:  # nothing new for a while: one rewrite for all of them
            break
    await _fold(services, key)
    if _pending.get(key):  # more ended while it was being written
        _jobs[key] = asyncio.ensure_future(_later(services, key))


async def _fold(services, key: str) -> bool:
    async with _locks.setdefault(key, asyncio.Lock()):
        turns = _pending.pop(key, [])
        if not turns:
            return False
        try:
            return await rewrite(services, turns)
        except Exception as e:  # the memory stays as it was; the reason is in the journal
            _journal(services, "memory_error", f"{type(e).__name__}: {str(e)[:300]}")
            return False


async def before_new_chat(rt, body: dict) -> None:
    """A new conversation starts: the memory is brought up to date first - the turns not folded in yet, or a review of the
    earlier conversations from the database when there is no memory yet or REVIEW_EVERY new conversations went by. The new
    conversation waits for it, at most NEW_CHAT_WAIT_S; the rewrite goes on behind it after that."""
    if _off():
        return
    s, key = rt.s, str(rt.s.config.data_dir)
    choice = choice_of(rt, body)
    if choice is None:
        return
    state = _state(s)
    state["chats"] = int(state.get("chats", 0)) + 1
    review = (not _read(project_file(s)) or state["chats"] - int(state.get("reviewed_at_chat", 0)) >= REVIEW_EVERY)
    try:
        _write(_state_file(s), json.dumps(state))
    except OSError:
        pass
    work = None
    if review:
        past = conversations(s, exclude=body["task_id"])
        if past:
            work = asyncio.ensure_future(_review(s, key, past, choice, state["chats"]))
    elif _pending.get(key):
        job = _jobs.pop(key, None)
        if job is not None and not job.done():
            job.cancel()  # no need to wait for the quiet: it is folded in now
        work = asyncio.ensure_future(_fold(s, key))
    if work is None:
        return
    # the chat shows it while it waits (desktop/web_chat._steps): a wait with nothing on the screen looked like a hang
    task_id = body["task_id"]
    s.journal.append("lumen", "state_change", {"state": "remembering", "review": review}, task_id=task_id)
    started = time.monotonic()
    try:
        await asyncio.wait_for(asyncio.shield(work), NEW_CHAT_WAIT_S)
        s.journal.append("lumen", "state_change", {"state": "remembered", "seconds": round(time.monotonic() - started)}, task_id=task_id)
    except (TimeoutError, asyncio.TimeoutError):
        _journal(s, "memory_slow", f"the memory took over {NEW_CHAT_WAIT_S:.0f} s; the conversation started with the one there was")
        s.journal.append("lumen", "state_change", {"state": "remembered", "late": True}, task_id=task_id)


async def _review(services, key: str, past: str, choice: dict, chats: int) -> bool:
    async with _locks.setdefault(key, asyncio.Lock()):
        _pending.pop(key, None)  # the review reads them from the database anyway
        try:
            ok = await rewrite(services, [], choice=choice, history=past)
        except Exception as e:
            _journal(services, "memory_error", f"{type(e).__name__}: {str(e)[:300]}")
            return False
        if ok:
            state = _state(services)
            state["reviewed_at_chat"] = chats
            try:
                _write(_state_file(services), json.dumps(state))
            except OSError:
                pass
        return ok


def conversations(services, exclude: str | None = None, limit_chars: int = HISTORY_CHARS) -> str:
    """The user's earlier conversations in this project, read from the database: newest first until limit_chars, then
    written oldest first, each turn as the user's words and Lumen's answer."""
    from codedoctor.agents import orchestration as orch

    since = _state(services).get("since") or ""  # the user cleared the memory then: nothing older comes back
    rows = services.db.query("SELECT id, title, created_at, body FROM tasks WHERE requester = 'user' AND parent_task_id IS NULL "
                             "AND state = 'finished' AND created_at > ? ORDER BY created_at DESC LIMIT 400", (since,))
    chats: dict[str, list[str]] = {}
    order: list[str] = []
    size = 0
    for row in rows:
        if row["id"] == exclude:
            continue
        try:
            body = json.loads(row["body"]) if row["body"] else {}
        except ValueError:
            body = {}
        if body.get("approval_of"):
            continue
        report = orch.report_of(services, row["id"]) or {}
        turn = (f"[{str(row['created_at'])[:16].replace('T', ' ')}]\nUser: {_cut(_clean(body.get('instructions') or row['title']), 1500)}\n"
                f"Lumen: {_cut(_clean(report.get('summary', '')), 1500)}")
        if size + len(turn) > limit_chars:
            break
        chat = body.get("chat_of") or row["id"]
        if chat not in chats:
            chats[chat] = []
            order.append(chat)
        chats[chat].insert(0, turn)
        size += len(turn)
    out = [f"--- conversation {i + 1} ---\n" + "\n\n".join(chats[c]) for i, c in enumerate(reversed(order))]
    return "\n\n".join(out)


def _turns_text(turns: list[dict]) -> str:
    chats: dict[str, str] = {}
    out = []
    for t in turns:
        name = chats.setdefault(t["chat"], f"conversation {len(chats) + 1}")
        out.append(f"[{t['at']} · {name}{'' if t['outcome'] == 'done' else ' · ' + t['outcome']}]\n"
                   f"User: {t['user']}\nLumen: {t['answer']}")
    return "\n\n".join(out)


def parse(answer: str) -> tuple[str, str] | None:
    """The two parts as the model wrote them, whole: one too long is compressed again (_fit), never cut here."""
    m = re.search(r"<<about_user>>\s*(.*?)\s*<<project>>\s*(.*)\Z", answer or "", re.S)
    if not m:
        return None
    about, project = _clean(m.group(1)), _clean(m.group(2))
    return (about, project) if (about or project) else None


def _asked() -> dict:
    """The limits as the model is told them: a little under the real ones, so that a slight overshoot still fits."""
    return {"user_max": int(USER_MAX * 0.9), "project_max": int(PROJECT_MAX * 0.93), "hard": int((USER_MAX + PROJECT_MAX) * 0.92)}


SHRINK = """This long-term memory of a user is too long: {size} characters, where the limit is {user_max} for part 1 and
{project_max} for part 2 ({hard} together). Write it again shorter. Nothing may disappear: keep every topic, every rule
of the user, every decision, every open problem and every unfinished request - only say each with less detail (fewer
examples, shorter wording, older details merged). Same language, same format: the line <<about_user>>, part 1, the line
<<project>>, part 2, and nothing else.

<<about_user>>
{about_user}
<<project>>
{project_text}"""


async def _fit(services, choice: dict, about: str, project: str, tries: int = 3) -> tuple[str, str]:
    """A memory over the limits is compressed again by the model - less detail, nothing left out (the user, 2026-11-15:
    "一定要压缩到八万字以内...不能落...也不能没有记忆") - up to `tries` times; only if it is still too long then is the
    end of a part cut, so that a turn can always be sent."""
    for _ in range(tries):
        if len(about) <= USER_MAX and len(project) <= PROJECT_MAX:
            return about, project
        answer = await ask_model(services, choice, SHRINK.format(
            size=len(about) + len(project), **_asked(),
            about_user=about, project_text=project))
        got = parse(answer)
        if got is None:
            break
        about, project = got[0] or about, got[1] or project
        _journal(services, "memory_compressed", f"compressed again: {len(about)} + {len(project)} characters")
    if len(about) > USER_MAX or len(project) > PROJECT_MAX:
        _journal(services, "memory_cut", f"still {len(about)} + {len(project)} characters after compressing: the ends were cut")
    return about[:USER_MAX], project[:PROJECT_MAX]


def _journal(services, state: str, reason: str) -> None:
    try:
        services.journal.append("lumen", "state_change", {"state": state, "reason": reason})
    except Exception:
        pass


async def rewrite(services, turns: list[dict], choice: dict | None = None, history: str | None = None) -> bool:
    """turns: what just ended (folded into the memory); history: the earlier conversations themselves (a review)."""
    if history is not None:
        what, heading, body = ("the user's earlier conversations in this project, read again from the start (newest kept "
                               "when there were too many)"), "EARLIER CONVERSATIONS", history
    else:
        what, heading, body = "the conversation turns that just ended", "TURNS THAT JUST ENDED", _turns_text(turns)
    prompt = ASK.format(what=what, heading=heading, **_asked(),
                        normal=min(NORMAL_MAX, int((USER_MAX + PROJECT_MAX) * 0.62)),
                        project=services.config.name, about_user=_read(user_file()) or "(nothing yet)",
                        project_text=_read(project_file(services)) or "(nothing yet)", turns=body)
    choice = choice or turns[-1]["choice"]
    answer = await ask_model(services, choice, prompt)
    got = parse(answer)
    if got is None:
        _journal(services, "memory_error", "the memory came back in another shape: kept the old one")
        return False
    about, project = await _fit(services, choice, *got)
    if about:
        _write(user_file(), about)
    if project:
        _write(project_file(services), project)
    _journal(services, "memory_updated", f"{'review of the earlier conversations' if history is not None else f'{len(turns)} turn(s)'}; "
                                         f"{len(about)} + {len(project)} characters")
    return True


async def ask_model(services, choice: dict, prompt: str, timeout_s: float = 420) -> str:  # writing 80K takes a while
    """One question, one answer, no tools: with Claude Code, Codex or a chat API, whichever the user chose."""
    from codedoctor import engines

    data = Path(services.config.data_dir)  # Lumen's own files for this project: the scratch answer file of Codex
    data.mkdir(parents=True, exist_ok=True)
    # it runs in the project folder: run in the data folder, a memory wrote that folder down as the project's
    # "working folder" (C:\Users\...\lumen-...\projects\..., seen in the introduction film's capture, 2026-11-16)
    cwd = Path(services.config.root) if Path(services.config.root).is_dir() else data
    if choice.get("engine") == "claude_code":
        from codedoctor import claude_code

        exe = claude_code.executable()
        if exe is None:
            return ""
        argv = [exe, "-p", "--output-format", "text", "--no-session-persistence", "--tools", "", "--strict-mcp-config",
                "--system-prompt", SYSTEM, *(["--model", choice["model"]] if choice.get("model") else [])]
        return await _run(engines, argv, prompt, cwd, timeout_s)
    if choice.get("engine") == "codex":
        from codedoctor import codex

        exe = codex.executable()
        if exe is None:
            return ""
        out = data / f".digest-{os.getpid()}-{time.monotonic_ns()}.txt"  # never into the user's project
        argv = [*exe, "exec", "--skip-git-repo-check", "--ephemeral", "--color", "never", "-C", str(cwd), "--sandbox", "read-only",
                "-c", 'approval_policy="never"', "-c", 'web_search="disabled"', "-o", str(out),
                *(["-m", choice["model"]] if choice.get("model") else []), "-"]
        await _run(engines, argv, f"{SYSTEM}\n\n{prompt}", cwd, timeout_s)
        try:
            return out.read_text(encoding="utf-8")
        except OSError:
            return ""
        finally:
            out.unlink(missing_ok=True)
    if choice.get("endpoint"):
        from codedoctor.models.base import ChatMessage

        async with services.models.limit(choice["endpoint"]):
            result = await asyncio.wait_for(services.models.client(choice["endpoint"]).chat(
                choice["model"], [ChatMessage("system", SYSTEM), ChatMessage("user", prompt)], [], max_output_tokens=32000), timeout_s)
        return result.text or ""
    return ""


async def _run(engines, argv: list[str], prompt: str, cwd: Path, timeout_s: float) -> str:
    proc = await engines.start(argv, prompt, cwd)  # its stdin is closed once the prompt is in
    try:
        out, _ = await asyncio.wait_for(asyncio.gather(proc.stdout.read(), proc.stderr.read()), timeout_s)
        await proc.wait()
    except TimeoutError:
        engines.kill(proc)
        return ""
    finally:
        engines._live.discard(proc)
    return out.decode("utf-8", "replace")
