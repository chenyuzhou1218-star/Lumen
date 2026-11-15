"""Claude Code kept running between messages (2026-11-05, the user's request).

A new Claude Code for every message cost a cold start, sometimes half a minute, and read its whole set-up again. Now Lumen,
the member the user talks to, has one process per conversation: the next message goes down the same pipe and it answers
at once, remembering the conversation by itself. With the window open one spare process stands ready for the next new
chat. A waiting process spends no tokens, only memory, so there are few of them and idle ones are closed.

The conversation stays with the process. When it is gone (closed for being idle, stopped, or crashed) the next message
starts a new one, which gets the earlier turns the usual way. A different model, level or set of tools is a different
process: Claude Code takes them when it starts.

Team tools reach Lumen through a local link that names the task (agents/team_link.py). A process outlives its task, so it
names a session instead, and this file says which task that session is working on now.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
import time

from codedoctor import engines

IDLE_S = 20 * 60
MOST = 3  # about 200 MB each on a small computer
SPARE = "spare"


@dataclass
class Session:
    key: str
    sig: tuple
    proc: object
    link_id: str
    mcp: str | None = None
    errors: deque = field(default_factory=lambda: deque(maxlen=40))
    spent: float = 0.0
    used: float = field(default_factory=time.monotonic)
    busy: bool = False
    turns: int = 0
    reader: object = None
    known: str | None = None  # the shared memory of the user as this session last got it (memory/digest.py)

    @property
    def alive(self) -> bool:
        return self.proc.returncode is None


def pool(services) -> dict[str, Session]:
    return services.__dict__.setdefault("_engine_sessions", {})


def links(services) -> dict[str, str]:
    """The link's session id -> the task it works on now."""
    return services.__dict__.setdefault("_team_sessions", {})


def add(services, session: Session) -> None:
    pool(services)[session.key] = session
    session.reader = asyncio.ensure_future(_read_errors(session))


async def _read_errors(session: Session) -> None:
    """Its error stream, read all along: a full pipe would stop the process, and the last lines say why it died."""
    try:
        while line := await session.proc.stderr.readline():
            session.errors.append(line.decode("utf-8", "replace").rstrip())
    except (asyncio.CancelledError, OSError, ValueError):
        pass


def close(services, session: Session) -> None:
    if pool(services).get(session.key) is session:
        del pool(services)[session.key]
    links(services).pop(session.link_id, None)
    if session.reader is not None:
        session.reader.cancel()
    engines.kill(session.proc)
    if session.mcp:
        Path(session.mcp).unlink(missing_ok=True)  # it holds the link's token


def take(services, key: str, sig: tuple) -> Session | None:
    """This conversation's process, or the spare one, ready for a message; None when one has to be started. A process
    still answering is left alone: a message sent meanwhile gets its own."""
    held = pool(services).get(key)
    if held is not None and not held.alive:
        close(services, held)
        held = None
    if held is not None and held.sig != sig:  # another model or level was chosen: its memory cannot move across
        if held.busy:
            return None
        close(services, held)
        held = None
    spare = pool(services).get(f"{SPARE}:{sig}")
    if held is None and spare is not None and spare.alive:
        del pool(services)[spare.key]
        spare.key = key
        pool(services)[key] = spare
        held = spare
    if held is None or held.busy:
        return None
    held.busy = True
    return held


def is_spare(session: Session) -> bool:
    return session.key.startswith(f"{SPARE}:")


def prune(services) -> None:
    """Idle ones go; of the rest the most recently used stay. The spare waits: that is what it is for."""
    now = time.monotonic()
    talking = sorted((s for s in pool(services).values() if not is_spare(s)), key=lambda s: s.used, reverse=True)
    for i, session in enumerate(talking):
        if not session.busy and (now - session.used > IDLE_S or i >= MOST):
            close(services, session)


def release(services, session: Session) -> None:
    session.busy = False
    session.used = time.monotonic()
    prune(services)
    asyncio.get_running_loop().call_later(IDLE_S + 1, prune, services)


async def close_all(services) -> None:
    for session in list(pool(services).values()):
        close(services, session)
