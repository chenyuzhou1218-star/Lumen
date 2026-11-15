"""Claude Code as an executor (2026-11-02): Lumen hands an investigation to the user's own Claude Code.

Lumen stays the hub - the project, the snapshot before and after (undo), the steps on the task page, the tests
it runs afterwards, the guardian's review, long-term memory - and Claude Code does the work in the project folder,
headless (`claude -p ... --output-format stream-json`). It runs on the user's Claude subscription.

What it may do follows the project's permissions: reading always; editing files only when the project allows changing
code; shell commands only those on the project's allowlist. Code whose level is 仅本机 never goes to it (a cloud
service). It does not ask questions: what is not allowed is refused.
"""

from __future__ import annotations

import asyncio
import secrets
import time
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

NAME = "claude_code"
SYSTEM = ("You are working for Lumen, which runs the project's tests after you and shows every step to the user. "
          "Change only what the task needs, keep functions' names, arguments and return shapes, and write tests that "
          "prove each fix. End with a short report: what was wrong, what you changed (files), how you verified it.")


def executable() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")
    return str(local) if local.is_file() else None


# Claude Code's models are asked from Claude Code itself (2026-11-10, the user's rule: a list written into Lumen goes
# stale the day a model comes out). Its own model menu - what its /model shows, for this account and this version - is
# in its answer to the SDK's `initialize` request: no model runs, nothing is sent, about two seconds. The last answer
# is kept on disk, so the menu opens at once; each run of Lumen asks again in the background and the new list is
# used as soon as it arrives. Models go by their full names (`--model`), so the version shown is the version that
# runs, each with its own levels (`--effort`; Opus 4.6 has no xhigh, Haiku 4.5 none at all).
EFFORTS = ("low", "medium", "high", "xhigh", "max")
_menu: list[dict] | None = None  # what Claude Code said, this run or the last
_asked = False  # asked again this run (or asking now)
_lock = threading.Lock()


def _menu_file() -> Path:
    return Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor") / "engines" / "claude_code_models.json"


def ask_menu(timeout_s: float = 45.0) -> list[dict]:
    """Claude Code's model menu as it gives it (its `models` in the answer to `initialize`). Started with no tools, no
    MCP servers and no session kept, in the temporary folder, and stopped as soon as it has answered."""
    from codedoctor import engines

    exe = executable()
    if not exe:
        raise FileNotFoundError("Claude Code is not installed")
    proc = subprocess.Popen([exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                             "--no-session-persistence", "--tools", "", "--strict-mcp-config"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            cwd=tempfile.gettempdir(), env=engines.env(),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    timer = threading.Timer(timeout_s, proc.kill)
    timer.start()
    try:
        proc.stdin.write((json.dumps({"type": "control_request", "request_id": "lumen-models",
                                      "request": {"subtype": "initialize"}}) + "\n").encode("utf-8"))
        proc.stdin.flush()
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("type") == "control_response":
                answer = event.get("response") or {}
                answer = answer.get("response") or answer
                listed = answer.get("models")
                if not isinstance(listed, list):
                    raise ValueError(answer.get("error") or "Claude Code gave no model list")
                return listed
        raise TimeoutError("Claude Code did not answer")
    finally:
        timer.cancel()
        try:
            proc.kill()
        except OSError:
            pass


def parse_menu(listed: list[dict]) -> list[dict]:
    """Claude Code's menu as Lumen shows it: [{"id", "name", "efforts", "default_effort", "yours"}], in its order.
    Its 默认 row is not a model of its own: it marks the one it runs by default ("yours"); an alias (opus, sonnet ...)
    goes by the full name it stands for, and each model is listed once."""
    from codedoctor.engines import EFFORTS as KNOWN

    fallback = next((m.get("resolvedModel") for m in listed if isinstance(m, dict) and m.get("value") == "default"), None)
    out, seen = [], set()
    for m in listed:
        if not isinstance(m, dict) or m.get("value") == "default":
            continue
        key = str(m.get("resolvedModel") or m.get("value") or "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,79}", key) or key in seen:
            continue
        seen.add(key)
        efforts = [e for e in m.get("supportedEffortLevels") or [] if e in KNOWN] if m.get("supportsEffort") else []
        out.append({"id": key, "name": str(m.get("displayName") or key), "efforts": efforts, "default_effort": None,
                    "yours": key == fallback})
    return out


def refresh() -> list[dict]:
    """Ask Claude Code now (about two seconds: off the UI thread) and keep its answer."""
    global _menu
    found = parse_menu(ask_menu())
    with _lock:
        _menu = found
    try:
        path = _menu_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"asked": time.time(), "models": found}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return found


def _refresh_quietly() -> None:
    try:
        refresh()
    except Exception:  # not installed, not answering: the last list stays
        pass


def refresh_later() -> None:
    """Ask Claude Code again in the background, once a run."""
    global _asked
    with _lock:
        if _asked:
            return
        _asked = True
    threading.Thread(target=_refresh_quietly, daemon=True, name="claude-code-models").start()


def models() -> list[dict]:
    """Claude Code's own models, as its menu lists them now. The list kept from last time answers at once and a fresh
    one is asked for in the background; with none kept (the first time ever), Claude Code is asked and waited for."""
    global _menu, _asked
    with _lock:
        menu = _menu
    if menu is None:
        try:
            menu = json.loads(_menu_file().read_text(encoding="utf-8"))["models"]
            with _lock:
                _menu = menu
        except (OSError, ValueError, KeyError, TypeError):
            with _lock:
                first = not _asked
                _asked = True
            if first:
                try:
                    menu = refresh()
                except Exception:  # not installed or not answering: no list, its own setting runs
                    menu = []
            menu = menu or []
    refresh_later()
    return [dict(m, efforts=list(m.get("efforts") or [])) for m in menu]


def team_rights(conf, cfg) -> tuple[list[str], list[str], bool]:
    """(allowed, disallowed, may edit) for a Lumen team member played by Claude Code: its job's tools and no others.
    The lead gets no edit or shell tool and no subagents of Claude Code's own: what it does not do itself goes
    through ask_team, so the work really is shared out (agents/team.py). argv then lists exactly these with --tools: a
    real run's helper could see other Claude sessions on the computer (ListAgents, SendMessage) and PowerShell."""
    have = set(cfg.tools or ())
    allowed, denied = ["TodoWrite"], ["Task", "Agent"]
    edits = conf.permissions.write_files and "edit_file" in have
    shell = "run_command" in have  # any command, no allowlist: the 批准方式 decides who is asked (team_link._approve)
    web = bool(have & {"web_search", "fetch_page"}) and conf.code_data_class in ("public", "internal")
    allowed += ["Read", "Glob", "Grep", "LS"] if "read_file" in have else []
    denied += [] if "read_file" in have else ["Read", "Glob", "Grep", "LS"]
    allowed += ["Edit", "MultiEdit", "Write", "NotebookEdit"] if edits else []
    denied += [] if edits else ["Edit", "MultiEdit", "Write", "NotebookEdit"]
    allowed += ["Bash"] if shell else []
    denied += [] if shell else ["Bash"]
    allowed += ["WebSearch", "WebFetch"] if web else []
    denied += [] if web else ["WebSearch", "WebFetch"]
    return allowed, denied, edits


def argv(conf, exe: str, mcp_config: str | None = None, model: str | None = None, effort: str | None = None,
         cfg=None, persona: str | None = None) -> list[str]:
    """The prompt goes on stdin (engines.start). model / effort: the user's choice, else Claude Code's own settings.
    cfg / persona: a Lumen team member's agent and who it is."""
    from codedoctor import engines

    builtin = None
    if cfg is not None and cfg.team:
        tools, denied, edits = team_rights(conf, cfg)
        builtin = sorted({t.split("(")[0] for t in tools})
    else:
        tools = ["Read", "Glob", "Grep", "LS", "TodoWrite"]
        if conf.permissions.write_files:
            tools += ["Edit", "MultiEdit", "Write", "NotebookEdit"]
        tools += ["Bash"]  # any command (the user: no permissions to stop it)
        denied, edits = ["WebFetch", "WebSearch"], conf.permissions.write_files
    out = [exe, "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
           "--permission-mode", "acceptEdits" if edits else "default",
           "--allowedTools", ",".join(tools), "--disallowedTools", ",".join(denied),
           # Lumen itself only talks and hands out work: its own short prompt instead of a coder's long one (half the reading)
           "--system-prompt" if persona and getattr(cfg, "id", "") == "lumen" else "--append-system-prompt",
           f"{persona or SYSTEM} {engines.STATUS_RULE}"]
    if builtin is not None:  # only these exist for it; the user's own MCP servers stay out too
        out += ["--tools", ",".join(builtin)]
        if not mcp_config:
            out += ["--strict-mcp-config"]
    if model:
        out += ["--model", model]
    if effort:
        out += ["--effort", effort]
    if mcp_config:  # Lumen's own tools for this run (codedoctor/mcp_bridge.py)
        from codedoctor import mcp_bridge

        toolsets = json.loads(Path(mcp_config).read_text(encoding="utf-8"))["mcpServers"]["codedoctor"]["args"][-1].split(",")
        out[out.index("--allowedTools") + 1] += "," + ",".join(mcp_bridge.tool_names(toolsets))
        if "@approve_permission" in toolsets:
            # Edit, Write and Bash are no longer pre-approved: each asks Lumen (team_link._approve), which checks what the project
            # allows and asks the user as their 批准方式 for the chat says. Without acceptEdits nothing is approved behind its back.
            at = out.index("--allowedTools") + 1
            out[at] = ",".join(x for x in out[at].split(",") if x.split("(")[0] not in ("Edit", "MultiEdit", "Write", "NotebookEdit", "Bash"))
            out[out.index("--permission-mode") + 1] = "default"
            out += ["--permission-prompt-tool", "mcp__codedoctor__approve_permission"]
            if edits:  # every write is asked about above, so the user's folders and other drives can be open too (outside.py)
                from codedoctor import outside

                for d in outside.dirs():
                    out += ["--add-dir", str(d)]
        out += ["--mcp-config", mcp_config, "--strict-mcp-config"]
    return out


def step(tool: str, inp: dict, root: Path) -> dict:
    """A Claude Code tool call as Lumen shows it: {"tool": ..., "path"/"command"/"query": ...}."""
    if tool.startswith("mcp__codedoctor__"):  # one of Lumen's own tools (codedoctor/mcp_bridge.py)
        from codedoctor import codex

        return codex.bridged(tool.removeprefix("mcp__codedoctor__"), inp)
    a = {"tool": tool}
    path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
    if path:
        try:
            a["path"] = Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
        except (ValueError, OSError):
            a["path"] = str(path)
    for key in ("command", "pattern", "description"):
        if inp.get(key):
            a[key] = str(inp[key])[:300]
    if tool in ("Edit", "MultiEdit"):
        edits = inp.get("edits") or [{"old_string": inp.get("old_string", ""), "new_string": inp.get("new_string", "")}]
        a["minus"] = sum(len(str(e.get("old_string", "")).splitlines()) or 1 for e in edits)
        a["plus"] = sum(len(str(e.get("new_string", "")).splitlines()) or 1 for e in edits)
    if tool == "Write":
        a["lines"] = len(str(inp.get("content", "")).splitlines())
    return a


def _ask(body: dict) -> str:
    title, text = body["title"], body["instructions"]
    return text if text.startswith(title) else f"{title}\n\n{text}"


def _listen(rt, task_id: str, usage, texts: list, got: dict, keep: bool, marks: dict | None = None):
    """What the engine says, as steps on the task's page. keep: a result ends the turn, the process stays."""
    s, conf = rt.s, rt.s.config

    def on_event(event):
        kind = event.get("type")
        if kind == "assistant":
            if marks is not None:
                marks.setdefault("first", time.monotonic())
            u = (event.get("message") or {}).get("usage") or {}
            mid = (event.get("message") or {}).get("id")
            seen = s.__dict__.setdefault("_live_seen", set())
            if u and (task_id, mid) not in seen:  # tokens while it runs (its total comes with the result): the window's
                seen.add((task_id, mid))         # spend limit sees them now; one message is counted once, however many parts
                live = s.__dict__.setdefault("_live_tokens", {})
                new = int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0) + int(u.get("output_tokens") or 0)
                live[task_id] = live.get(task_id, 0) + new
            for c in (event.get("message") or {}).get("content", []):
                if c.get("type") == "text" and c.get("text", "").strip():
                    texts.append(c["text"])
                elif c.get("type") == "tool_use":
                    usage.steps += 1
                    s.journal.append(rt.id, "tool_call", {"tool": NAME, "call_id": c.get("id"),
                                                          "arguments": step(c.get("name", "?"), c.get("input") or {}, conf.root)},
                                     task_id=task_id)
        elif kind == "user":
            for c in (event.get("message") or {}).get("content", []):
                if c.get("type") == "tool_result":
                    s.journal.append(rt.id, "tool_result", {"tool": NAME, "call_id": c.get("tool_use_id"),
                                                            "ok": not c.get("is_error"), "claims": [], "evidence": [],
                                                            "notes": [], "external": True, "data_class": conf.code_data_class},
                                     task_id=task_id)
        elif kind == "result":
            got["result"] = event
            return keep
        return None

    return on_event


async def _conclude(rt, task_id: str, proc, outcome, err: str, usage, texts: list, got: dict, found: dict, cost, extra: dict | None = None):
    from codedoctor import engines

    s = rt.s
    result = got.get("result")
    if result:
        u = result.get("usage") or {}
        usage.model_calls = int(result.get("num_turns") or 0)
        usage.input_tokens = int(u.get("input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0) \
            + int(u.get("cache_creation_input_tokens") or 0)
        usage.output_tokens = int(u.get("output_tokens") or 0)
        usage.cached_tokens = int(u.get("cache_read_input_tokens") or 0)
        s.journal.append(rt.id, "model_response", {"finish": result.get("subtype"), "tool_calls": 0,
                                                   "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                                                   "cached_tokens": usage.cached_tokens,
                                                   "engine": NAME, "cost_usd": cost, **(extra or {})}, task_id=task_id)
    report = getattr(proc, "why", "") or (result or {}).get("result") or (texts[-1] if texts else "")
    if outcome is None:
        if result is None:
            outcome, report = "failed", f"Claude Code stopped without a result. {err[-800:]}"
        elif result.get("is_error"):
            outcome = "blocked" if "authenticate" in report.lower() or "login" in report.lower() else "failed"
            if outcome == "blocked":
                report = ("Claude Code 没有登录（或登录过期）。在终端运行一次 claude，按提示登录，再回来重试。"
                          f"它说：{report}")
        else:
            outcome = "done"
    outcome, report = await engines.finish(rt, outcome, report, found)
    return outcome, report or "(Claude Code returned no text)", found


async def open_session(rt, body: dict, sig: tuple, key: str):
    """A Claude Code waiting for its first message: it has spent no tokens yet."""
    from codedoctor import engine_sessions, engines, mcp_bridge
    from codedoctor.agents import team

    s, conf = rt.s, rt.s.config
    link_id = f"sess_{secrets.token_hex(8)}"
    setup = await engines.team_setup(rt, body, "mcp__codedoctor__", link_id)
    mcp = mcp_bridge.config_file(s, link_id, setup["toolsets"], setup["env"]) if setup["toolsets"] else None
    args = argv(conf, executable(), mcp, body.get("engine_model"), body.get("engine_effort"), cfg=rt.cfg, persona=setup["persona"])
    args += ["--input-format", "stream-json"]
    extra = {"MCP_TOOL_TIMEOUT": str(team.JOB_WAIT_S * 1000 + 60000), "ENABLE_TOOL_SEARCH": "false"}
    proc = await engines.start(args, None, conf.root, extra)
    session = engine_sessions.Session(key, sig, proc, link_id, mcp)
    engine_sessions.add(s, session)
    return session


async def warm(rt, body: dict) -> None:
    """One spare process for the next new chat, so that its first message has no cold start either."""
    from codedoctor import engine_sessions, engines

    sig = _signature(rt, body)
    key = f"{engine_sessions.SPARE}:{sig}"
    if key in engine_sessions.pool(rt.s) or engines.refused(rt.s.config, "Claude Code") or executable() is None:
        return
    await open_session(rt, {"task_id": "", "title": "", "instructions": "", **body}, sig, key)


def _signature(rt, body: dict) -> tuple:
    return (rt.id, body.get("engine_model"), body.get("engine_effort"), tuple(sorted(body.get("toolsets") or ())))


async def _talk(rt, msg: dict, body: dict, again: bool = False) -> tuple[str, str, dict]:
    """A message to the Claude Code of this conversation (engine_sessions.py)."""
    from codedoctor import engine_sessions, engines
    from codedoctor.agents import team
    from codedoctor.agents.runtime import Usage, history_text

    s, task_id = rt.s, body["task_id"]
    usage = Usage()
    found = {"evidence": [], "claims": [], "usage": usage}
    began = time.monotonic()
    chat, sig = body.get("chat_of") or task_id, _signature(rt, body)
    session = engine_sessions.take(s, chat, sig)
    if session is None:
        session = await open_session(rt, body, sig, chat if chat not in engine_sessions.pool(s) else task_id)
        session.busy = True
    knows = session.turns > 0  # it remembers the conversation: nothing is sent twice
    engine_sessions.links(s)[session.link_id] = task_id
    from codedoctor.memory import digest

    notes = await team.memory_notes(rt, body, brief=False)
    known = digest.text(s)  # sent again only when another conversation (or this one) changed it
    if known and known != session.known:
        session.known, notes = known, known + notes
    text = f"{notes}{'' if knows else history_text(body)}{_ask(body)}"
    line = json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}, ensure_ascii=False)
    s.journal.append(rt.id, "state_change", {"state": NAME, "reason": "Claude Code started" if not session.turns else "Claude Code continues"},
                     task_id=task_id)
    marks = {"sent": time.monotonic()}
    texts, got = [], {}
    try:
        session.proc.stdin.write((line + "\n").encode("utf-8"))
        await session.proc.stdin.drain()
    except (OSError, ConnectionError):
        pass  # gone: the read below says so
    outcome = await engines.events(rt, task_id, session.proc, _listen(rt, task_id, usage, texts, got, True, marks))
    result = got.get("result")
    session.turns += 1
    if result is None:
        err = "\n".join(session.errors)
        engine_sessions.close(s, session)
        if outcome is None and knows and not texts and not again:  # it had died while waiting: a new one, with the earlier turns
            return await _talk(rt, msg, body, True)
    else:
        err = ""
        engine_sessions.release(s, session)
    if result is not None and outcome is None and s.__dict__.get("warm_engines"):
        asyncio.ensure_future(warm(rt, body))
    total = result.get("total_cost_usd") if result else None
    cost = round(total - session.spent, 6) if total is not None else None  # it counts the whole session
    session.spent = total if total is not None else session.spent
    now = time.monotonic()
    timing = {"reused": knows, "prepare_ms": int((marks["sent"] - began) * 1000), "total_ms": int((now - began) * 1000),
              "first_ms": int((marks.get("first", now) - marks["sent"]) * 1000), "api_ms": (result or {}).get("duration_api_ms")}
    return await _conclude(rt, task_id, session.proc, outcome, err, usage, texts, got, found, cost, timing)


async def run(rt, msg: dict, body: dict) -> tuple[str, str, dict]:
    """Do the task with Claude Code; returns (outcome, summary, found) like AgentRuntime._task_loop."""
    from codedoctor import engines
    from codedoctor.agents.runtime import Usage, history_text

    s, conf, task_id = rt.s, rt.s.config, body["task_id"]
    usage = Usage()
    found = {"evidence": [], "claims": [], "usage": usage}
    why = engines.refused(conf, "Claude Code")
    if why:
        return "blocked", why, found
    exe = executable()
    if exe is None:
        return "blocked", "没有找到 Claude Code（claude 命令）。装好并登录一次后再选它。", found
    if rt.cfg.team and rt.id == "lumen" and not body.get("parent_task_id"):  # the one the user talks to stays running
        return await _talk(rt, msg, body)
    mcp = None
    setup = await engines.team_setup(rt, body, "mcp__codedoctor__")
    link_env = setup["env"]
    member, extra = {}, {}
    if rt.cfg.team:  # a member of the Lumen team: who it is, and the way back to the team (agents/team_link.py)
        from codedoctor.agents import team

        member = {"cfg": rt.cfg, "persona": setup["persona"]}
        extra = {"MCP_TOOL_TIMEOUT": str(team.JOB_WAIT_S * 1000 + 60000),  # a member's job may take this long
                 "ENABLE_TOOL_SEARCH": "false"}  # the team's tools are there from the first turn, not to be looked up
    if setup["toolsets"]:
        from codedoctor import mcp_bridge

        mcp = mcp_bridge.config_file(s, task_id, setup["toolsets"], link_env)
    proc = await engines.start(argv(conf, exe, mcp, body.get("engine_model"), body.get("engine_effort"), **member),
                               f"{setup['notes']}{history_text(body)}{_ask(body)}", conf.root,
                               *([extra] if extra else []))
    s.journal.append(rt.id, "state_change", {"state": NAME, "reason": "Claude Code started"}, task_id=task_id)
    texts, got = [], {}
    outcome = await engines.events(rt, task_id, proc, _listen(rt, task_id, usage, texts, got, False))
    await proc.wait()
    if link_env and mcp:
        Path(mcp).unlink(missing_ok=True)  # it holds the link's token
    err = (await proc.stderr.read()).decode("utf-8", "replace").strip()
    result = got.get("result")
    return await _conclude(rt, task_id, proc, outcome, err, usage, texts, got, found, (result or {}).get("total_cost_usd"))
