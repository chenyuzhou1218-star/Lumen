"""Code Doctor's tools for Claude Code (2026-11-02): a small MCP server over stdio.

When the user calls in a toolset with @ (@CodeCut) and hands the task to their Claude Code or Codex, Code Doctor
starts this server for that run (Claude Code: `--mcp-config`; Codex: `-c mcp_servers.codedoctor...`): Claude Code then edits and renders video with the same tools Code Doctor's own
agents use (codedoctor/video.py), with the same rules - files only inside the project folder.

    python -m codedoctor.mcp_bridge --root <project> --toolsets codecut
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

PROTOCOL = "2025-06-18"
MAKER_IDS = {"codesound", "codepage", "codegame", "codedeck", "codedata", "codecad", "codelab", "codetools", "codefilm", "codepdf"}  # codedoctor/makers.py


def server(services, toolsets: list[str], env: dict | None = None) -> dict:
    """How an engine starts this server: {"command", "args", "env"}."""
    return {"command": sys.executable, "args": ["-m", "codedoctor.mcp_bridge", "--root", str(services.config.root),
                                                "--toolsets", ",".join(toolsets)],
            "env": {"PYTHONPATH": str(Path(__file__).resolve().parents[1]), **(env or {})}}


def config_file(services, task_id: str, toolsets: list[str], env: dict | None = None) -> str:
    """The --mcp-config file for one Claude Code run."""
    folder = Path(services.config.data_dir) / "mcp"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{task_id}.json"
    path.write_text(json.dumps({"mcpServers": {"codedoctor": server(services, toolsets, env)}}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return str(path)


def tool_names(toolsets: list[str]) -> list[str]:
    """Claude Code's names for the bridged tools (for --allowedTools)."""
    names = []
    if "codecut" in toolsets:
        from codedoctor import video

        names += [f"mcp__codedoctor__{n}" for n in video.NAMES]
    if "code3d" in toolsets:
        from codedoctor import model3d

        names += [f"mcp__codedoctor__{n}" for n in model3d.NAMES]
    if set(toolsets) & MAKER_IDS:
        from codedoctor import makers

        names += [f"mcp__codedoctor__{n}" for n in makers.NAMES]
    names += [f"mcp__codedoctor__{n}" for n in _team_tools(toolsets)]
    return names


def _team_tools(toolsets: list[str]) -> tuple[str, ...]:
    """A team member's tools from the running service (agents/team_link.py), each given as "@name"."""
    return tuple(t[1:] for t in toolsets if t.startswith("@"))


def _forward(name: str, arguments: dict) -> tuple[bool, str, list]:
    """A team tool runs in the service, not here (agents/team_link.py): it may take as long as the job does."""
    req = {"token": os.environ.get("LUMEN_TEAM_TOKEN", ""), "task_id": os.environ.get("LUMEN_TEAM_TASK", ""),
           "agent": os.environ.get("LUMEN_TEAM_AGENT", ""), "tool": name, "arguments": arguments}
    try:
        with socket.create_connection(("127.0.0.1", int(os.environ.get("LUMEN_TEAM_PORT", "0")))) as sock:
            sock.sendall(json.dumps(req, ensure_ascii=False).encode("utf-8") + b"\n")
            with sock.makefile("r", encoding="utf-8") as reader:
                out = json.loads(reader.readline() or "{}")
    except (OSError, ValueError) as e:
        return False, f"ERROR: Lumen could not be reached: {e}", []
    return bool(out.get("ok")), str(out.get("content", "ERROR: no answer")), list(out.get("images") or [])


def _context(root: Path):
    """What Code Doctor's tool handlers need, outside a running investigation."""
    from codedoctor.agents.tools import ToolContext

    pictures: dict[str, tuple[str, bytes]] = {}

    def add_blob(data: bytes, media_type: str, **_kw) -> str:
        pictures[f"ev:mcp:{len(pictures)}"] = (media_type, data)
        return f"ev:mcp:{len(pictures) - 1}"

    services = SimpleNamespace(config=SimpleNamespace(root=root, code_data_class="internal"), pictures=pictures,
                               evidence=SimpleNamespace(add_test_run=lambda *a, **k: None, add_blob=add_blob))
    return ToolContext(services=services, agent_id="claude_code", role="worker", task_id=os.environ.get("LUMEN_TEAM_TASK") or "claude_code", model={},
                       call_entry_id="", thread_id="", known_agents=set(), root=str(root))


def serve(root: Path, toolsets: list[str], stdin=None, stdout=None) -> None:
    import asyncio

    from codedoctor.agents.tools import TOOLS, execute_async
    from codedoctor.computer import tools as _computer  # noqa: F401 (registers the computer's tools)

    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    tools = {}
    if "codecut" in toolsets:
        from codedoctor import video

        tools.update({n: TOOLS[n] for n in video.NAMES})
    if "code3d" in toolsets:
        from codedoctor import model3d

        tools.update({n: TOOLS[n] for n in model3d.NAMES})
    if set(toolsets) & MAKER_IDS:
        from codedoctor import makers

        tools.update({n: TOOLS[n] for n in makers.NAMES})
    remote = _team_tools(toolsets)
    tools.update({n: TOOLS[n] for n in remote})
    ctx = _context(root)

    def reply(msg_id, result=None, error=None):
        out = {"jsonrpc": "2.0", "id": msg_id}
        out.update({"error": error} if error else {"result": result})
        stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        stdout.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if msg_id is None:
            continue  # a notification (initialized, cancelled): nothing to answer
        if method == "initialize":
            reply(msg_id, {"protocolVersion": params.get("protocolVersion", PROTOCOL), "capabilities": {"tools": {}},
                           "serverInfo": {"name": "codedoctor", "version": "0.1"}})
        elif method == "ping":
            reply(msg_id, {})
        elif method == "tools/list":
            reply(msg_id, {"tools": [{"name": t.name, "description": t.description, "inputSchema": t.parameters}
                                     for t in tools.values()]})
        elif method == "tools/call":
            tool = tools.get(params.get("name"))
            if tool is None:
                reply(msg_id, error={"code": -32602, "message": f"unknown tool {params.get('name')!r}"})
                continue
            images = []
            if tool.name in remote:
                ok, text, images = _forward(tool.name, params.get("arguments") or {})  # pictures come with the answer
            else:
                try:
                    if tool.name == "maker_run" and os.environ.get("LUMEN_TEAM_PORT"):  # running code: the user's approval choice first
                        ok, text, _ = _forward("approve_permission", {"tool_name": "maker_run", "input": params.get("arguments") or {}})
                        verdict = json.loads(text) if ok else {"behavior": "deny", "message": text}
                        if verdict.get("behavior") != "allow":
                            reply(msg_id, {"content": [{"type": "text", "text": "ERROR: " + str(verdict.get("message", "not approved"))}], "isError": True})
                            continue
                    res = asyncio.run(execute_async(tool, ctx, params.get("arguments") or {}))
                    ok, text = res.ok, res.content
                    images = [{"mime": ctx.services.pictures[ev][0], "data": base64.b64encode(ctx.services.pictures[ev][1]).decode("ascii")}
                              for ev in res.images if ev in ctx.services.pictures]
                except Exception as e:  # one tool's failure must not end the server (the engine then loses all of them)
                    ok, text = False, f"ERROR: {type(e).__name__}: {e}"
            content = [{"type": "text", "text": text}]
            content += [{"type": "image", "data": i["data"], "mimeType": i["mime"]} for i in images]
            reply(msg_id, {"content": content, "isError": not ok})
        else:
            reply(msg_id, error={"code": -32601, "message": f"unknown method {method!r}"})


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--toolsets", default="")
    a = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    serve(Path(a.root).resolve(), [t for t in a.toolsets.split(",") if t])
    return 0


if __name__ == "__main__":
    sys.exit(main())
