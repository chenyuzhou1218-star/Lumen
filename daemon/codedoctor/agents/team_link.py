"""The Lumen team across a process boundary: an engine (the user's Claude Code) that plays a member runs as its own
program, and its tools come from a small MCP server (codedoctor/mcp_bridge.py), yet handing work to the team has to
happen here, in the running service. This is the way back: a socket on 127.0.0.1 with a random token, one request per
connection. It takes only Lumen's own tools a member needs (the team, memory, the browser, the computer), only for a
task that is running, and only as the agent that runs it, under the project's rules - never approvals, which stay
in the window.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import secrets

from codedoctor.agents import orchestration as orch
from codedoctor.agents import team
from codedoctor.agents.tools import TOOLS, ToolContext, execute_async

# decide_action is the supervisor's own verdict on one computer action (not the user's approval, which stays in the window): only a
# guardian may use it (checked below). Without it a guardian played by Claude Code could never answer, and every action was denied.
ALLOWED = ("ask_team", "spawn_helpers", "ask_user", "decide_action", *team.BROWSER, *team.MEMORY, *team.COMPUTER)
MAX_LINE = 16 * 1024 * 1024


async def _answer(services, token: str, line: bytes) -> dict:
    try:
        req = json.loads(line.decode("utf-8"))
    except ValueError:
        return {"ok": False, "content": "ERROR: not a request"}
    if not hmac.compare_digest(str(req.get("token", "")), token):
        return {"ok": False, "content": "ERROR: refused"}
    task_id, agent, name = req.get("task_id"), req.get("agent"), req.get("tool")
    task_id = services.__dict__.get("_team_sessions", {}).get(task_id, task_id)  # a kept process: its current task
    row = orch.task_row(services, task_id or "")
    cfg = services.config.agents.get(agent or "")
    runtime = getattr(getattr(services, "daemon", None), "agents", {}).get(agent or "")
    if row is None or cfg is None or runtime is None or row["agent"] != agent or row["state"] != "running":
        return {"ok": False, "content": "ERROR: no such running task for this agent"}
    if name == "approve_permission":
        return await _approve(services, task_id, cfg, row, req.get("arguments") or {})
    if name == "decide_action" and cfg.role != "guardian":
        return {"ok": False, "content": "ERROR: only a guardian decides on an action"}
    if name not in ALLOWED or name not in runtime.tools:  # its tools as this project allows them (computer, files ...)
        return {"ok": False, "content": f"ERROR: {agent} may not use {name!r}"}
    entry = services.journal.append(agent, "state_change", {"state": "team_tool", "tool": name}, task_id=task_id)
    ctx = ToolContext(services=services, agent_id=agent, role=cfg.role, task_id=task_id, model={}, call_entry_id=entry["id"],
                      thread_id=row["thread_id"], known_agents=set(services.config.agents),
                      data_class=services.config.code_data_class)
    res = await execute_async(TOOLS[name], ctx, req.get("arguments") or {})
    out = {"ok": res.ok, "content": res.content}
    if res.images:  # a screenshot goes to the engine as a picture
        import base64

        out["images"] = [{"mime": services.evidence.get(ev)["content"]["media_type"],
                          "data": base64.b64encode(services.evidence.content(ev)).decode("ascii")} for ev in res.images[-2:]]
    return out


def _permission(allow: bool, text: str, updated: dict | None = None) -> dict:
    out = {"behavior": "allow", "updatedInput": updated or {}} if allow else {"behavior": "deny", "message": text}
    return {"ok": True, "content": json.dumps(out, ensure_ascii=False)}


async def _approve(services, task_id: str, cfg, row: dict, args: dict) -> dict:
    """Claude Code asks whether it may use Edit, Write or Bash (--permission-prompt-tool). What the project allows at all is
    checked first (write_files, the command allowlist); then the user's 批准方式 for this chat decides whether they are asked."""
    from pathlib import Path

    from codedoctor.computer import gate as gate_mod

    tool, inp = str(args.get("tool_name", "")), dict(args.get("input") or {})
    conf = services.config
    perm = conf.permissions
    root = Path(conf.root)
    if tool in ("Edit", "MultiEdit", "NotebookEdit", "Write"):  # no project switch stops it (the user: "删掉任何的权限")
        path = str(inp.get("file_path") or inp.get("notebook_path") or "")
        try:
            shown = Path(path).resolve().relative_to(root.resolve()).as_posix()
            kind = "create" if tool == "Write" and not (root / shown).exists() else "edit"
        except (ValueError, OSError):  # outside the project: the user's folders and other drives, never the system's (outside.py)
            from codedoctor import outside

            if not outside.allowed(Path(path)):
                return _permission(False, "this place is not open to agents (system folders and other users' folders never are)")
            shown, kind = str(Path(path).resolve()), "outside"
        what = {"path": shown}
    elif tool == "Bash":
        command = str(inp.get("command", "")).strip()  # any command: only the 批准方式 decides whether the user is asked
        kind, what = ("delete" if gate_mod.is_delete_command(command) else "command"), {"command": command[:500]}
    elif tool == "maker_run":  # a tool of the team's that runs code: no file or command rules of Claude Code's apply
        kind, what = "command", {"command": f"{inp.get('tool', '')} {inp.get('action', '')} {inp.get('project', '')}".strip()[:500]}
    else:
        return _permission(False, f"{tool} is not available in this project")
    gate = services.computer
    if gate is not None and gate_mod.asks_user(gate.tier_of(task_id), kind, what):
        ctx = ToolContext(services=services, agent_id=cfg.id, role=cfg.role, task_id=task_id, model={}, call_entry_id="",
                          thread_id=row["thread_id"], known_agents=set(services.config.agents), data_class=services.config.code_data_class)
        if not await gate.ask_plain(ctx, kind, what, intent=f"{cfg.id} wants to use {tool}"):
            return _permission(False, "the user did not approve this action (or did not answer in time): do not do it")
    return _permission(True, "", inp)


async def ensure(services) -> dict:
    """The running link of this service: {"port", "token", "server"}; started the first time it is needed."""
    link = services.__dict__.get("_team_link")
    if link is not None:
        return link
    token = secrets.token_urlsafe(32)

    async def handle(reader, writer):
        try:
            out = await _answer(services, token, await reader.readline())
            writer.write(json.dumps(out, ensure_ascii=False).encode("utf-8") + b"\n")
            await writer.drain()
        except (ConnectionError, ValueError, asyncio.LimitOverrunError) as e:
            services.journal.append("system", "state_change", {"state": "team_link_error", "reason": f"{type(e).__name__}: {e}"})
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, limit=MAX_LINE)
    link = {"port": server.sockets[0].getsockname()[1], "token": token, "server": server}
    services.__dict__["_team_link"] = link
    return link


def close(services) -> None:
    link = services.__dict__.pop("_team_link", None)
    if link is not None:
        link["server"].close()


def env(link: dict, task_id: str, agent_id: str) -> dict:
    """What the MCP server needs to reach the link for one engine run."""
    return {"LUMEN_TEAM_PORT": str(link["port"]), "LUMEN_TEAM_TOKEN": link["token"], "LUMEN_TEAM_TASK": task_id,
            "LUMEN_TEAM_AGENT": agent_id}
