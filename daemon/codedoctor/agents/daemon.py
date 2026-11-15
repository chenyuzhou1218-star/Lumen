"""The background service: owns the project's services and runs every agent's loop.

Runs independently of any UI. The desktop window (codedoctor.gui) and the CLI
use this class in-process; scripts can use the HTTP API (codedoctor.api).
Only one service may run per project data directory (InstanceLock).
"""

from __future__ import annotations

import asyncio
import json

import httpx

from codedoctor import claim_rules, ids
from codedoctor.agents import orchestration as orch
from codedoctor.agents.anomalies import head_phase
from codedoctor.agents.runtime import AgentRuntime
from codedoctor.config import ProjectConfig, validate_cluster
from codedoctor.cluster.foresight import Foresight
from codedoctor.services import Services
from codedoctor.store.db import dumps
from codedoctor.store.lock import InstanceLock


def conversation_turns(services, chat_id: str) -> list[dict]:
    """The task rows of one conversation, oldest first: the first message's task, then every one continuing it."""
    out = []
    for r in services.db.query("SELECT * FROM tasks WHERE parent_task_id IS NULL AND (id = ? OR body LIKE ?) "
                               "ORDER BY created_at", (chat_id, f'%{chat_id}%')):
        r = dict(r)
        if r["id"] == chat_id or orch.body_of(r).get("chat_of") == chat_id:
            out.append(r)
    return out


def conversation_history(services, chat_id: str, exclude: str | None = None) -> list[dict]:
    """[{"user", "assistant"}] of a conversation's last turns, within a size the models take easily. `exclude`: the task
    asking (its own row is not history). An answer not written yet is said so - but a message is run only after the
    ones before it (Haiku check item 10), so by then their answers are there."""
    if not services.db.one("SELECT 1 FROM tasks WHERE id = ? AND parent_task_id IS NULL", (chat_id,)):
        raise KeyError(f"unknown conversation {chat_id!r}")
    turns = []
    first = services.db.one("SELECT agent FROM tasks WHERE id = ?", (chat_id,))
    lead = services.config.agents.get(first["agent"]) if first else None
    turns_n, chars = (Daemon.TEAM_TURNS, Daemon.TEAM_CHARS) if lead is not None and lead.team else (Daemon.HISTORY_TURNS,
                                                                                                    Daemon.HISTORY_CHARS)
    rows = [r for r in conversation_turns(services, chat_id) if r["id"] != exclude]
    for r in rows[-turns_n:]:
        body = orch.body_of(r)
        reports = [m for m in services.bus.list(thread_id=r["thread_id"])
                   if m["kind"] == "report" and m["body"].get("task_id") == r["id"]]
        answer = reports[-1]["body"].get("summary", "") if reports else "(no answer yet)"
        turns.append({"user": body.get("instructions", r["title"])[:3000], "assistant": answer[:4000]})
    while turns and sum(len(t["user"]) + len(t["assistant"]) for t in turns) > chars:
        turns.pop(0)
    return turns


HIDDEN = "\n\n<<lumen:context>>\n"  # the same marker as desktop/web_chat.HIDDEN: what follows it is not shown as the user's

# what each of Lumen's tools is for, for the lead when the user named none (Daemon.submit_task)
TOOL_KINDS = {
    "codecut": "CodeCut - video editing: cut, join, titles, music, export",
    "code3d": "Code3D - 3D models and scenes in the user's Blender, exported as GLB and pictures",
    "codesound": "CodeSound - music and sound effects",
    "codepage": "CodePage - web pages and sites",
    "codegame": "CodeGame - games",
    "codedeck": "CodeDeck - slides and documents",
    "codedata": "CodeData - analysis of Excel or CSV data, a report whose every number has its source",
    "codecad": "CodeCAD - printable parts in millimetres",
    "codelab": "CodeLab - watching a model's training: logs, progress, problems",
    "codetools": "CodeTools - dozens of small tools: logos and posters, flowcharts, QR codes, e-books, subtitles, voice-over, "
                 "batch photo editing, files, backups, search, API tests, databases, logs, calculation, circuits, maps",
    "codefilm": "CodeFilm - a short film from one sentence",
    "codepdf": "CodePDF - PDFs: pictures to PDF, merge, split, compress, rotate, pick pages",
}


def with_context(instructions: str, note: str) -> str:
    """The message with a note for the AI after the marker (desktop/web_chat.shown() shows only what is before it)."""
    return f"{instructions}\n{note}" if HIDDEN in instructions else f"{instructions}{HIDDEN}{note}"


def tools_guide(found: list[str], config) -> str:
    hands = next((a for a in ("spark",) if a in config.agents), None)
    lines = "\n".join(f"- {TOOL_KINDS.get(t, t)}" for t in found)
    return ("Lumen's own tools on this computer (the user named none; pick yourself whether the work needs one):\n" + lines +
            "\nWhen the work fits one of them, hand it to " + (hands.capitalize() if hands else "the member who has these tools") +
            " and name the tool in the job (\"use CodePDF to ...\"). A member uses the tool for that work rather than writing a "
            "script of its own for the same thing; the tool opens on the right for the user to watch. When none fits, work as "
            "usual.")


class Daemon:
    def __init__(self, config: ProjectConfig, *, transport: httpx.AsyncBaseTransport | None = None, poll_s: float = 2.0,
                 desktop=None):
        self.config = config
        validate_cluster(config.agents, config.cluster)
        self.s = Services.open(config, transport, desktop)
        self.s.daemon = self  # one-off helpers (agents/team.py, subagents.py) are added and retired while it runs
        names = set(config.agents)
        self.agents = {aid: AgentRuntime(cfg, self.s, names) for aid, cfg in config.agents.items()}
        self.poll_s = poll_s
        self._loops: list[asyncio.Task] = []
        self._lock = InstanceLock(config.data_dir)
        self.foresight = Foresight(self.s)

    async def start(self) -> None:
        self.s.bus.bind_loop(asyncio.get_running_loop())
        # tools run in threads; a worker waiting for the test lock holds one. The default pool (cpu + 4) let 19
        # waiting workers starve the dispatch head's delegate calls in a 40-agent run.
        from concurrent.futures import ThreadPoolExecutor

        asyncio.get_running_loop().set_default_executor(
            ThreadPoolExecutor(max_workers=max(32, 2 * len(self.agents) + 8), thread_name_prefix="codedoctor-tool"))
        self._lock.acquire()  # raises AlreadyRunning if another service owns this project
        # Tasks left running by a stop or crash are reported as interrupted before anything else runs.
        self.recovered = {a.id: a.recover_interrupted() for a in self.agents.values()}
        # Conclusions about code that changed while the service was down are no longer current facts.
        self.refreshed = await asyncio.to_thread(claim_rules.refresh_all, self.s)
        self._loops = [asyncio.create_task(self._loop(a), name=f"agent:{a.id}") for a in self.agents.values()]
        if self.config.cluster.enabled and self.config.cluster.foresight:
            self._loops.append(asyncio.create_task(self._foresight_loop(), name="cluster:foresight"))
        if self.s.vectors.enabled:
            self._loops.append(asyncio.create_task(self._index_loop(), name="memory:vectors"))

    async def _foresight_loop(self) -> None:
        while True:
            try:
                self.foresight.tick()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.s.journal.append("system", "state_change", {"state": "foresight_error", "reason": f"{type(error).__name__}: {error}"})
            await asyncio.sleep(min(self.config.cluster.interval_s, max(0.1, self.poll_s)))

    async def _index_loop(self) -> None:
        """Semantic memory (ADR 0007): embed new notes in the background, newest first. An endpoint
        that fails is retried after a minute; meanwhile recall works on text and coupling."""
        while True:
            try:
                handled = await self.s.vectors.index_pending()
            except asyncio.CancelledError:
                raise
            except Exception:  # the reason is kept in s.vectors.last_error
                await asyncio.sleep(60)
                continue
            await asyncio.sleep(0.01 if handled else max(self.poll_s, 5.0))

    async def _loop(self, agent: AgentRuntime) -> None:
        while True:
            try:
                busy = await agent.step(parallel=True)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep the loop alive; the error is in the journal
                self.s.journal.append(agent.id, "state_change", {"state": "error", "reason": f"{type(e).__name__}: {e}"})
                busy = False
            if not busy:
                await self.s.bus.wait(agent.id, self.poll_s)

    def add_agent(self, cfg) -> None:
        """A one-off helper joins for one job: its own loop, beside the configured agents."""
        self.s.config.agents[cfg.id] = cfg
        self.agents[cfg.id] = AgentRuntime(cfg, self.s, set(self.s.config.agents))
        self._loops.append(asyncio.create_task(self._loop(self.agents[cfg.id]), name=f"agent:{cfg.id}"))

    def retire_agent(self, agent_id: str) -> None:
        """The helper's job is done: its loop ends; its tasks and journal stay as the record."""
        for t in [t for t in self._loops if t.get_name() == f"agent:{agent_id}"]:
            t.cancel()
            self._loops.remove(t)
        self.agents.pop(agent_id, None)
        self.s.config.agents.pop(agent_id, None)

    async def halt(self) -> None:
        """Stop the agent loops but keep the database open (for inspection)."""
        from codedoctor import engine_sessions
        from codedoctor.agents import team_link

        await engine_sessions.close_all(self.s)
        team_link.close(self.s)
        for t in self._loops:
            t.cancel()
        side = [job for a in self.agents.values() for job in a.cancel_side()]  # conversations running beside each other
        await asyncio.gather(*self._loops, *side, return_exceptions=True)
        self._loops = []
        self._lock.release()

    async def stop(self) -> None:
        await self.halt()
        await self.s.aclose()

    # --- commands -------------------------------------------------------------------

    def submit_task(self, agent_id: str, title: str, instructions: str, *, scope: dict | None = None,
                    budget: dict | None = None, data_class: str | None = None, reasoning: str | None = None,
                    model: dict | None = None, approval: str | None = None, tools: list[str] | None = None,
                    engine: str | None = None, engine_model: str | None = None,
                    engine_effort: str | None = None, chat_of: str | None = None) -> dict:
        """reasoning / model: the user's choice for this whole investigation (every agent of it). approval: "auto"
        (帮我批准) or "full" (完全访问权限) - only from the window (computer/gate.py; never over HTTP). tools: toolsets
        the user called in with @ (["codecut"]: video, codedoctor/video.py; ["code3d"]: 3D, model3d.py); their tools exist only in this
        investigation. chat_of: the conversation this message continues (its first task): the earlier turns go with
        it, like any chat."""
        if agent_id not in self.agents:
            raise KeyError(f"unknown agent {agent_id!r}")
        if tools and {"codecut", "code3d", "codesound", "codepage", "codegame", "codedeck", "codedata", "codecad", "codetools", "codefilm", "codepdf"} & set(tools):  # all are hands-on work
            from codedoctor import video

            agent_id = video.hands(self.s.config, agent_id)
        task_id = ids.new_id("task")
        body: dict = {"task_id": task_id, "title": title, "instructions": instructions}
        history = self.chat_history(chat_of) if chat_of else []
        if chat_of:
            body["chat_of"] = chat_of
            if history:
                body["history"] = history
        from codedoctor.agents import smalltalk

        if not tools and not scope and smalltalk.is_smalltalk(instructions, in_conversation=bool(history)):
            body["chat"] = True  # 你好 / 谢谢 / 你是谁: answered in a line, not investigated (agents/smalltalk.py)
        if scope:
            body["scope"] = scope
        if budget:
            body["budget"] = budget
        if reasoning:
            body["reasoning"] = reasoning
        if approval in ("ask", "auto", "full"):
            body["approval"] = approval
        if tools:
            from codedoctor import video

            unknown = [t for t in tools if t not in video.TOOLSETS]
            if unknown:
                raise KeyError(f"unknown toolset {unknown[0]!r}; known: {', '.join(video.TOOLSETS)}")
            if "code3d" in tools:  # a scene is code: engines get the tools from the bridge, so the check is here for everyone
                from codedoctor import model3d

                if not model3d.allowed("code3d_run", self.s.config):
                    raise PermissionError("Code3D 不能在这个项目里运行：它要运行代码，需要项目允许改文件和运行命令（并且装好了 Code3D）。")
            from codedoctor import makers

            called = [t for t in tools if t in makers.MAKERS]
            for t in called:
                if makers.home(t) is None:
                    raise PermissionError(f"没有找到 {makers.MAKERS[t].name}（放在 Lumen 旁边的 tools/{t}）。")
            if makers.needs_running(called) and not makers.allowed("maker_run", self.s.config):
                raise PermissionError(f"{makers.MAKERS[called[0]].name} 不能在这个项目里运行：它要运行代码，需要项目允许改文件和运行命令。")
            body["toolsets"] = list(dict.fromkeys(tools))
        elif self.agents[agent_id].cfg.team and not body.get("chat"):
            # Nothing called in with @: the team still has every tool installed here and picks the one the work needs (the
            # user, 2026-11-15: "不用调用任何的插件...它会帮你调用插件"). The message stays with Lumen, who decides; no chip
            # is shown and no window opens until a tool is really used (desktop/app.py _watch_commands).
            found = self.installed_tools()
            if found:
                body["toolsets"], body["called"] = found, []
                # said to Lumen behind the message (the window shows the text before the marker only): a real run made a PDF
                # with a 200-line script of its own, CodePDF unused, because nobody named the tool to the member
                if not chat_of:  # once, with a conversation's first message: the later ones have it in the conversation
                    body["instructions"] = with_context(instructions, tools_guide(found, self.s.config))
        if engine:
            from codedoctor import engines

            engines.get(engine)  # KeyError for an unknown one
            engines.check_choice(engine, engine_model, engine_effort)  # its own models and levels, by its own names
            body["engine"] = engine  # the user's Claude Code or Codex does the work (codedoctor/engines.py)
            if engine_model:
                body["engine_model"] = engine_model
            if engine_effort:
                body["engine_effort"] = engine_effort
        if model:
            if model.get("endpoint") not in self.s.config.endpoints:
                raise KeyError(f"unknown endpoint {model.get('endpoint')!r}")
            body["model"] = {"endpoint": model["endpoint"], "model": model["model"]}
        msg = self.s.bus.prepare(sender="user", recipient=agent_id, kind="task", body=body, data_class=data_class)
        now = ids.now()
        with self.s.db.tx() as c:
            c.execute(
                "INSERT INTO tasks (id, agent, requester, thread_id, message_id, title, state, created_at, updated_at, body) "
                "VALUES (?,?,?,?,?,?,'queued',?,?,?)",
                (task_id, agent_id, "user", msg["thread_id"], msg["id"], title, now, now, dumps(body)),
            )
            self.s.bus.insert(c, msg)
        self.s.bus.notify(agent_id)
        return {"task_id": task_id, "message_id": msg["id"], "thread_id": msg["thread_id"], "agent": agent_id}

    def installed_tools(self) -> list[str]:
        """Every Lumen tool this computer has and this project may run, in the order of video.TOOLSETS."""
        from codedoctor import makers, model3d, video

        out = []
        for t in video.TOOLSETS:
            if t == "codecut":
                ok = video.home() is not None
            elif t == "code3d":
                ok = model3d.allowed("code3d_run", self.s.config)
            else:
                ok = t in makers.MAKERS and makers.home(t) is not None and (
                    not makers.needs_running([t]) or makers.allowed("maker_run", self.s.config))
            if ok:
                out.append(t)
        return out

    HISTORY_TURNS, HISTORY_CHARS = 8, 14000
    TEAM_TURNS, TEAM_CHARS = 40, 80000  # Lumen keeps much more of the conversation (the user: the longest context)

    def chat_turns(self, chat_id: str) -> list[dict]:
        """The task rows of one conversation, oldest first: the first message's task, then every one continuing it."""
        return conversation_turns(self.s, chat_id)

    def chat_history(self, chat_id: str) -> list[dict]:
        """[{"user", "assistant"}] of a conversation's last turns, within a size the models take easily."""
        return conversation_history(self.s, chat_id)

    def control(self, agent_id: str, command: str, *, task_id: str | None = None, reason: str | None = None) -> dict:
        if agent_id not in self.agents:
            raise KeyError(f"unknown agent {agent_id!r}")
        body: dict = {"command": command}
        if task_id:
            body["task_id"] = task_id
        if reason:
            body["reason"] = reason
        msg = self.s.bus.post(sender="user", recipient=agent_id, kind="control", body=body)
        # Cancellation must reach a task that is already running, so it is applied immediately.
        with self.s.db.tx() as c:
            if command == "cancel_task":
                c.execute("UPDATE tasks SET cancel_requested = 1 WHERE id = ?", (task_id,))
            elif command == "stop":
                c.execute("UPDATE tasks SET cancel_requested = 1 WHERE agent = ? AND state != 'finished'", (agent_id,))
        return msg

    def task(self, task_id: str) -> dict | None:
        row = self.s.db.one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if row is None:
            return None
        out = dict(row)
        out["usage"] = json.loads(out["usage"]) if out["usage"] else None
        out["messages"] = self.s.bus.list(thread_id=row["thread_id"])
        out["claims"] = self.s.claims.by_task(task_id)
        out["side_effects"] = self.s.effects.for_task(task_id)
        return out

    def recent_tasks(self, limit: int = 50) -> list[dict]:
        rows = self.s.db.query(  # chat_of: the conversation a message continues (the window lists each one once)
            "SELECT id, agent, title, state, outcome, created_at, updated_at, parent_task_id, "
            "json_extract(body, '$.chat_of') AS chat_of FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def agent_states(self) -> list[dict]:
        rows = {r["id"]: dict(r) for r in self.s.db.query("SELECT * FROM agents")}
        return [
            {"id": a.id, "role": a.cfg.role, "model": f"{a.cfg.primary.endpoint}/{a.cfg.primary.model}",
             "fallbacks": [f"{f.endpoint}/{f.model}" for f in a.cfg.fallbacks],
             "state": rows.get(a.id, {}).get("state", "idle"), "reason": rows.get(a.id, {}).get("reason"),
             # the five head states (ADR 0014): listening / reviewing / reflecting / commanding / delivery
             "phase": head_phase(self.s, a.id) if a.cfg.role in ("head_dispatch", "head_logic") else None}
            for a in self.agents.values()
        ]

    async def wait_for_report(self, task_id: str, timeout_s: float = 600) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while True:
            for m in self.s.bus.list(task_id=task_id):
                if m["kind"] == "report":
                    return m
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError(f"no report for {task_id} within {timeout_s}s")
            await asyncio.sleep(0.05)
