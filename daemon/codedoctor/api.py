"""Local HTTP API (docs/api.md). Binds to 127.0.0.1 by default. With a token (codedoctor serve --token, or
CODEDOCTOR_API_TOKEN) every request needs `Authorization: Bearer <token>`; off this machine a token is required."""

from __future__ import annotations

from contextlib import asynccontextmanager

import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from codedoctor import __version__, claim_rules, interface
from codedoctor.agents.bus import MessageError
from codedoctor.agents.daemon import Daemon
from codedoctor.claims import ClaimRejected
from codedoctor.config import ProjectConfig
from codedoctor.memory import related as related_memory
from codedoctor.telemetry import TelemetryError, TelemetryStore
from codedoctor.cluster.http import mount as mount_cluster


class TaskIn(BaseModel):
    agent: str | None = None  # default: the entry of the way of working the user chose (as the window and `fix`)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=50000)
    scope: dict | None = None
    budget: dict | None = None
    data_class: str | None = None
    reasoning: str | None = Field(default=None, pattern="^(off|low|medium|high|max)$")  # 思考强度 for this investigation
    model: dict | None = None  # {"endpoint", "model"}: every agent of this investigation uses it
    tools: list[str] | None = None  # toolsets called in, as @ in the window: ["codecut"] = video with CodeCut, ["code3d"] = 3D with Code3D
    engine: str | None = Field(default=None, pattern="^(claude_code|codex)$")  # the user's own Claude Code or Codex does the work
    engine_model: str | None = None  # its own model (e.g. gpt-6.1-sol, opus); checked against what it lists
    engine_effort: str | None = Field(default=None, pattern="^(low|medium|high|xhigh|max|ultra)$")  # its own level
    chat_of: str | None = Field(default=None, pattern="^task_[0-9A-HJKMNP-TV-Z]{26}$")  # the conversation it continues


class ReviewIn(BaseModel):
    verdict: str
    notes: str = Field(min_length=1, max_length=20000)
    evidence: list[str] | None = None


class ControlIn(BaseModel):
    agent: str
    command: str
    task_id: str | None = None
    reason: str | None = None


def create_app(config: ProjectConfig, token: str | None = None, **daemon_kw) -> FastAPI:
    daemon = Daemon(config, **daemon_kw)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await daemon.start()
        yield
        await daemon.stop()

    app = FastAPI(title="Code Doctor", version=__version__, lifespan=lifespan)
    app.state.daemon = daemon

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        if token and not hmac.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
            return JSONResponse({"detail": "missing or wrong token (Authorization: Bearer ...)"}, status_code=401)
        return await call_next(request)

    mount_cluster(app, daemon)

    @app.get("/tasks")
    def tasks(limit: int = 50):
        return daemon.recent_tasks(min(limit, 500))

    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__, "project": config.name, "agents": daemon.agent_states()}

    @app.get("/agents")
    def agents():
        return daemon.agent_states()

    @app.post("/tasks")
    def submit(t: TaskIn):
        agent = t.agent or interface.entry_agent(config)
        title = t.title or t.instructions.splitlines()[0][:80] or "调查"
        try:
            return {"agent": agent, **daemon.submit_task(agent, title, t.instructions, scope=t.scope, budget=t.budget,
                                                         data_class=t.data_class, reasoning=t.reasoning, model=t.model,
                                                         tools=t.tools, engine=t.engine,
                                                         engine_model=t.engine_model, engine_effort=t.engine_effort,
                                                         chat_of=t.chat_of)}
        except KeyError as e:
            raise HTTPException(404, str(e))
        except MessageError as e:
            raise HTTPException(422, str(e))

    @app.get("/tasks/{task_id}")
    def task(task_id: str):
        t = daemon.task(task_id)
        if t is None:
            raise HTTPException(404, "unknown task")
        return t

    @app.get("/tasks/{task_id}/progress")
    def task_progress(task_id: str, after_seq: int = 0, limit: int = 500):
        """New readable events since after_seq (pass back the returned last_seq), and whether everything is settled."""
        if daemon.task(task_id) is None:
            raise HTTPException(404, "unknown task")
        events, last = interface.progress(daemon.s, task_id, after_seq, min(limit, 2000))
        return {"events": events, "last_seq": last, "settled": interface.settled(daemon.s, task_id)}

    @app.get("/tasks/{task_id}/result")
    def task_result(task_id: str):
        """Status, answer, team, changed files, the system's tests and the scouts' findings."""
        r = interface.result(daemon.s, task_id)
        if r is None:
            raise HTTPException(404, "unknown task")
        return {**r, "settled": interface.settled(daemon.s, task_id)}

    @app.post("/tasks/{task_id}/cancel")
    def task_cancel(task_id: str):
        try:
            interface.cancel(daemon, task_id)
        except KeyError as e:
            raise HTTPException(404, str(e))
        return {"ok": True}

    @app.post("/tasks/{task_id}/undo")
    def task_undo(task_id: str):
        """Put back the files the investigation changed (files changed afterwards are skipped and listed)."""
        from codedoctor import workspace

        if daemon.task(task_id) is None:
            raise HTTPException(404, "unknown task")
        if not interface.settled(daemon.s, task_id):
            raise HTTPException(409, "the investigation is still running")
        return workspace.revert(daemon.s, task_id)

    @app.post("/control")
    def control(c: ControlIn):
        try:
            return daemon.control(c.agent, c.command, task_id=c.task_id, reason=c.reason)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except MessageError as e:
            raise HTTPException(422, str(e))

    @app.get("/messages")
    def messages(to: str | None = None, thread_id: str | None = None, task_id: str | None = None, after_seq: int = 0, limit: int = 200):
        return daemon.s.bus.list(recipient=to, thread_id=thread_id, task_id=task_id, after_seq=after_seq, limit=min(limit, 1000))

    @app.get("/journal")
    def journal(task_id: str | None = None, agent: str | None = None, after_seq: int = 0, limit: int = 500):
        return daemon.s.journal.read(task_id=task_id, agent=agent, after_seq=after_seq, limit=min(limit, 5000))

    @app.get("/journal/{entry_id}/original")
    def journal_original(entry_id: str):
        e = daemon.s.journal.get(entry_id)
        if e is None:
            raise HTTPException(404, "unknown journal entry")
        return daemon.s.journal.original(e)

    # Anomaly inbox and detail checklist (ADR 0014): read only. Decisions are the logic head's.
    @app.get("/anomalies")
    def anomalies(root_task_id: str | None = None, limit: int = 200):
        an = daemon.s.anomalies
        return an.for_root(root_task_id) if root_task_id else an.recent(min(limit, 1000))

    @app.get("/checklist/{root_task_id}")
    def checklist(root_task_id: str):
        return daemon.s.anomalies.checklist(root_task_id)

    # Computer use (ADR 0012): read and stop only. Approving an action is deliberately NOT possible over HTTP:
    # this API has no login, so any local program could otherwise approve on the user's behalf.
    @app.get("/computer/status")
    def computer_status():
        gate = daemon.s.computer
        p = daemon.config.computer
        return {"available": bool(gate and gate.available), "stopped": gate.stopped() if gate else None,
                "screenshot": p.screenshot, "input": p.input, "apps": p.apps, "terminal": p.terminal,
                "windows": list(p.windows), "launch": [t.id for t in p.launch],
                "pending": len(gate.actions(statuses=("pending_guardian", "pending_user"))) if gate else 0}

    @app.get("/computer/actions")
    def computer_actions(task_id: str | None = None, limit: int = 100):
        gate = daemon.s.computer
        return gate.actions(task_ids=[task_id] if task_id else None, limit=min(limit, 500)) if gate else []

    @app.post("/computer/stop")
    def computer_stop():
        if daemon.s.computer:
            daemon.s.computer.stop("stopped through the HTTP API")
        return {"stopped": True}

    @app.post("/computer/resume")
    def computer_resume():
        if daemon.s.computer:
            daemon.s.computer.resume()
        return {"stopped": False}

    @app.get("/memory/search")
    async def memory_search(q: str, reader: str, k: int = 10, shared: bool = True):
        found = await related_memory.recall_async(daemon.s, q, reader=reader, data_class=daemon.s.config.code_data_class,
                                                  k=min(k, 100), include_shared=shared)
        return [{"score": r.score, "flags": r.flags, "via": r.via, "meaning": r.meaning, **r.note} for r in found]

    @app.get("/claims/{claim_id}")
    def claim(claim_id: str):
        c = daemon.s.claims.get(claim_id)
        if c is None:
            raise HTTPException(404, "unknown claim")
        return {"claim": c, "reviews": daemon.s.claims.reviews(claim_id), "events": daemon.s.claims.events(claim_id),
                "validation": daemon.s.claims.latest_validation(claim_id)}

    @app.post("/claims/{claim_id}/reviews")
    def review(claim_id: str, r: ReviewIn):
        try:
            rev = daemon.s.claims.add_review(claim_id, reviewer="user", verdict=r.verdict, notes=r.notes, evidence=r.evidence)
        except ClaimRejected as e:
            raise HTTPException(422, e.problems)
        return {"review": rev, "result": claim_rules.evaluate(daemon.s, claim_id)}

    @app.post("/claims/{claim_id}/evaluate")
    def evaluate(claim_id: str):
        try:
            return claim_rules.evaluate(daemon.s, claim_id)
        except KeyError:
            raise HTTPException(404, "unknown claim")

    @app.post("/claims/refresh")
    def refresh():
        return claim_rules.refresh_all(daemon.s)

    telemetry = TelemetryStore(daemon.s)

    @app.post("/telemetry/coverage")
    def coverage_in(doc: dict):
        try:
            return {"id": telemetry.add_coverage(doc)}
        except TelemetryError as e:
            raise HTTPException(422, str(e))

    @app.post("/telemetry/health")
    def health_in(doc: dict):
        try:
            return {"id": telemetry.add_health(doc)}
        except TelemetryError as e:
            raise HTTPException(422, str(e))

    @app.post("/templates")
    def template_in(doc: dict):
        try:
            telemetry.add_template(doc)
        except TelemetryError as e:
            raise HTTPException(422, str(e))
        return {"id": doc["id"], "version": doc["version"]}

    @app.get("/coverage")
    def coverage():
        return telemetry.coverage_status()

    @app.get("/evidence")
    def evidence(id: str):
        rec = daemon.s.evidence.get(id)
        if rec is None:
            raise HTTPException(404, "unknown evidence id")
        return {"record": rec, "integrity": daemon.s.evidence.check(id)}

    return app
