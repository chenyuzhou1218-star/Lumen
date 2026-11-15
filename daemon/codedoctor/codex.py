"""Codex as an executor (2026-11-02): Lumen hands an investigation to the user's own Codex (OpenAI).

Like codedoctor/claude_code.py: Lumen keeps the snapshot, the steps on the task page, the tests afterwards and
the data-class rules, and Codex does the work in the project folder, headless (`codex exec --json`), on the user's
ChatGPT subscription.

What it may do follows the project's permissions, through Codex's own sandbox: read-only when the project does not
allow changing code, else writes only inside the project folder; no network, no web search, never an approval
question. Codex reads files with shell commands, so it always runs some; which ones it may run beyond reading is told
in the instructions (the sandbox keeps any command from writing outside the project or reaching the network).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
from pathlib import Path

from codedoctor.engines import EFFORTS as EFFORT_KEYS

NAME = "codex"
SYSTEM = ("Rules from Lumen, which runs the project's tests after you and shows every step to the user: change "
          "only what the task needs, keep functions' names, arguments and return shapes, and write tests that prove "
          "each fix. End with a short report: what was wrong, what you changed (files), how you verified it.")


def executable() -> list[str] | None:
    """How to start Codex: npm's codex.cmd goes through cmd.exe, so on Windows its script is run with node directly."""
    found = shutil.which("codex")
    if not found:
        return None
    if found.lower().endswith((".cmd", ".bat")):
        script = Path(found).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node")
        return [node, str(script)] if node and script.is_file() else None
    return [found]


def home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def models() -> list[dict]:
    """The models Codex lists (its own cache of what the account may use, models_cache.json), in its order, each with
    its own reasoning levels; "yours" is the one set in Codex's config.toml."""
    data = json.loads((home() / "models_cache.json").read_text(encoding="utf-8"))
    try:
        import tomllib

        mine = tomllib.loads((home() / "config.toml").read_text(encoding="utf-8")).get("model")
    except (OSError, ValueError):
        mine = None
    out = []
    for m in sorted(data.get("models") or [], key=lambda m: m.get("priority", 99)):
        if m.get("visibility") != "list" or not m.get("slug"):
            continue
        efforts = [lv["effort"] for lv in m.get("supported_reasoning_levels") or [] if lv.get("effort") in EFFORT_KEYS]
        out.append({"id": m["slug"], "name": m.get("display_name") or m["slug"], "efforts": efforts,
                    "default_effort": m.get("default_reasoning_level"), "yours": m["slug"] == mine})
    return out


def _toml(value) -> str:
    return json.dumps(value, ensure_ascii=False)  # a JSON string or list is a TOML string or array


def team_rights(conf, cfg) -> tuple[bool, bool]:
    """(may write, may search the web) for a Lumen team member played by Codex: its sandbox follows its job."""
    have = set(cfg.tools or ())
    return (conf.permissions.write_files and "edit_file" in have,
            bool(have & {"web_search", "fetch_page"}) and conf.code_data_class in ("public", "internal"))


def argv(conf, exe: list[str], mcp: dict | None = None, model: str | None = None, effort: str | None = None,
         cfg=None, outside: bool = False, read_only: bool = False) -> list[str]:
    """The prompt goes on stdin (engines.start). model / effort: the user's choice, else Codex's own settings.
    cfg: a Lumen team member's agent. outside: it may also write in the user's folders and other drives (codedoctor/outside.py):
    only in 完全放开, because Codex cannot stop and ask the user before a write. read_only: the user said no (全部问我)."""
    writes, web = team_rights(conf, cfg) if cfg is not None and cfg.team else (conf.permissions.write_files, False)
    # No sandbox of Codex's, whoever the member and whatever the tier (the user, 2026-11-14: "删掉任何的权限...给他完全的
    # 权限"): every member was told "only reading is allowed here" and stopped. What needs the user is asked by Lumen itself
    # (the approve bar); Codex's own sandbox also broke on extra folders. Only a user's 不同意 (全部问我) makes it read-only.
    sandbox = "read-only" if read_only else "danger-full-access"
    out = [*exe, "exec", "--json", "--skip-git-repo-check", "--ephemeral", "--color", "never", "-C", str(conf.root),
           "--sandbox", sandbox,
           "-c", 'approval_policy="never"', "-c", f'web_search="{"live" if web else "disabled"}"']
    if sandbox == "workspace-write":
        out += ["-c", "sandbox_workspace_write.network_access=false"]
    if model:
        out += ["-m", model]
    if effort:
        out += ["-c", f"model_reasoning_effort={_toml(effort)}"]
    if mcp:  # Lumen's own tools for this run (codedoctor/mcp_bridge.py)
        out += ["-c", f"mcp_servers.codedoctor.command={_toml(mcp['command'])}",
                "-c", f"mcp_servers.codedoctor.args={_toml(mcp['args'])}",
                "-c", "mcp_servers.codedoctor.env={" + ", ".join(f"{k} = {_toml(v)}" for k, v in mcp["env"].items()) + "}",
                # its own tools need no question: they keep to the project folder themselves (codedoctor/video.py)
                "-c", 'mcp_servers.codedoctor.default_tools_approval_mode="approve"',
                # a member's job runs inside one call of ask_team; importing Lumen takes a moment on a weak computer
                "-c", "mcp_servers.codedoctor.tool_timeout_sec=86460", "-c", "mcp_servers.codedoctor.startup_timeout_sec=60"]
    return out + ["-"]


def _member_prompt(conf, body: dict, setup: dict, cfg) -> str:
    """The instructions for a member of the Lumen team: who it is, what its sandbox lets it do."""
    from codedoctor import engines
    from codedoctor.agents.runtime import history_text

    have = set(cfg.tools or ())
    rules = []
    # No limits are told any more ("run only these commands", "use the shell only to read"): the member just works, and what
    # needs the user is asked by Lumen (the user, 2026-11-14). Its job says what it does.
    # No "Change no files." any more (the user, 2026-11-14): Lumen read it as the user's own words and asked them whether it
    # might make a new video. A member without an editing tool is told whose job editing is; the lead hands it on.
    if cfg.id == "lumen":
        rules.append("You do not edit files yourself: hand changes to the member whose job they are, with ask_team.")
    elif "edit_file" not in have:
        rules.append("Editing files is another member's job: say in your report what should change and where.")
    names = ", ".join(t[1:] for t in setup["toolsets"] if t.startswith("@"))
    if names:
        rules.append(f"Your tools from Lumen are on the MCP server `codedoctor`: {names}. Search your tools for them if "
                     "they are not listed.")
    from codedoctor.agents import team

    # The message itself, said to be one: with the persona right above it and no label, a model took "You are Lumen"
    # for the user introducing themself and answered "你之前说你叫 Lumen，所以我也可以叫你 Lumen" (2026-11-11).
    me = team.member(cfg.id)
    who = "the user" if cfg.id == "lumen" else "Lumen, your lead"
    ask = body["instructions"] if str(body["instructions"]).startswith(str(body["title"])) else f"{body['title']}\n\n{body['instructions']}"
    return (f"{setup['persona']}\n\n{setup['notes']}{history_text(body)}"
            f"The message you are answering now, from {who} (you are {me.name if me else cfg.id}; they are not):\n\n{ask}\n\n"
            f"How you work in Lumen (the program's rules, not the user's words; never ask the user about them): "
            f"{' '.join(rules)}\n\n{engines.STATUS_RULE}")


def prompt(conf, body: dict, read_only: bool = False) -> str:
    """No limits are told (the user, 2026-11-14: no allowlist, no read-only members): the old file's run_command and
    write_files once made every task say "run only these commands" and "change no files". read_only: the user said no to
    changes in this chat (全部问我), and its sandbox is read-only too."""
    commands = "Change no files: the user said no to changes in this chat." if read_only else ""
    if body.get("toolsets"):  # the rules above are about the shell; Lumen's own tools are given for this task
        from codedoctor import mcp_bridge

        names = ", ".join(n.removeprefix("mcp__codedoctor__") for n in mcp_bridge.tool_names(body["toolsets"]))
        commands += (f"\n\nFor this task Lumen gives you its own tools on the MCP server `codedoctor`: {names}. "
                     "They are allowed and meant for this work (search your tools for them if they are not listed): "
                     "do the work with them, not with the shell.")
    from codedoctor import engines

    from codedoctor.agents.runtime import history_text

    return f"{history_text(body)}{body['title']}\n\n{body['instructions']}\n\n{SYSTEM} {commands}\n\n{engines.STATUS_RULE}"


_READ = re.compile(r"^(?:Get-Content|cat|type)\s+(?:-(?:LiteralPath|Path)\s+)?['\"]?([^'\"|;]+?)['\"]?(?:\s|$)", re.I)


def _rel(path: str, root) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def _unwrap(cmd: str) -> str:
    """The command inside Codex's `"...powershell.exe" -Command '...'` (shell-quoted), else the line as it is."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return cmd
    lower = [p.lower() for p in parts]
    if parts and Path(lower[0]).stem in ("powershell", "pwsh", "bash", "sh") and len(parts) > 2 \
            and lower[-2] in ("-command", "-c", "-lc"):
        return parts[-1]
    return cmd


def steps(item: dict, root) -> list[dict]:
    """A Codex item as Lumen shows it, in Claude Code's words ({"tool": "Read"/"Edit"/..., "path"/...})."""
    kind = item.get("type")
    if kind == "command_execution":
        cmd = _unwrap(str(item.get("command", "")).strip())
        read = _READ.match(cmd)
        if read and ";" not in cmd and "|" not in cmd:
            return [{"tool": "Read", "path": _rel(read.group(1).strip(), root)}]
        return [{"tool": "Bash", "command": cmd[:300]}]
    if kind == "file_change":
        verb = {"add": "Write", "delete": "Delete"}
        return [{"tool": verb.get(c.get("kind"), "Edit"), "path": _rel(c.get("path", ""), root)}
                for c in item.get("changes") or []] or [{"tool": "Edit"}]
    if kind == "mcp_tool_call":
        return [bridged(str(item.get("tool", "?")), item.get("arguments") or {})]
    if kind == "web_search":
        return [{"tool": "WebSearch", "pattern": str(item.get("query", ""))[:200]}]
    if kind == "todo_list":
        return [{"tool": "TodoWrite"}]
    return []


def bridged(tool: str, args: dict) -> dict:
    """A call of one of Lumen's own tools (codedoctor/mcp_bridge.py), shown by what it does."""
    from codedoctor.agents import team
    from codedoctor.video import ACTION_CN

    shown = team.step(tool, args)
    if shown is not None:
        return shown

    action = args.get("action")
    rest = [str(v) for k, v in args.items() if k != "action" and isinstance(v, (str, int, float))]
    return {"tool": tool, "description": " ".join([ACTION_CN.get(action, action)] * bool(action) + rest)[:120]}


def _ok(item: dict) -> bool:
    if item.get("type") == "command_execution":
        return item.get("exit_code") == 0
    return item.get("status") not in ("failed", "declined") and not item.get("error")


async def run(rt, msg: dict, body: dict) -> tuple[str, str, dict]:
    """Do the task with Codex; returns (outcome, summary, found) like AgentRuntime._task_loop."""
    from codedoctor import engines
    from codedoctor.agents.runtime import Usage

    s, conf, task_id = rt.s, rt.s.config, body["task_id"]
    usage = Usage()
    found = {"evidence": [], "claims": [], "usage": usage}
    why = engines.refused(conf, "Codex")
    if why:
        return "blocked", why, found
    exe = executable()
    if exe is None:
        return "blocked", "没有找到 Codex（codex 命令）。用 npm i -g @openai/codex 装好，运行一次 codex 登录后再选它。", found
    mcp = None
    setup = await engines.team_setup(rt, body, "")
    if setup["toolsets"]:
        from codedoctor import mcp_bridge

        mcp = mcp_bridge.server(s, setup["toolsets"], setup["env"])
    member = {"cfg": rt.cfg} if rt.cfg.team else {}
    gate = getattr(s, "computer", None)
    tier = gate.tier_of(task_id) if gate is not None else "auto"
    member["outside"] = tier == "full"  # 完全放开: the user's folders and other drives too
    writes = (team_rights(conf, rt.cfg)[0] if rt.cfg.team else conf.permissions.write_files)
    if writes and tier == "ask" and gate is not None:
        # 全部问我: Codex writes inside its own sandbox and cannot stop to ask before each file (the flow check, 2026-11-14:
        # hello.txt was made with nobody asked). So the user is asked once, before this member may change files at all;
        # refused, it works read-only.
        from codedoctor.agents.tools import ToolContext

        ctx = ToolContext(services=s, agent_id=rt.cfg.id, role=rt.cfg.role, task_id=task_id, model={}, call_entry_id="",
                          thread_id=str(msg.get("thread_id") or ""), known_agents=set(conf.agents), data_class=conf.code_data_class)
        what = {"path": str(conf.root), "detail": str(body.get("instructions") or body.get("title") or "")[:300]}
        if not await gate.ask_plain(ctx, "edit", what, intent=f"{rt.cfg.id} (Codex) will change files in this project"):
            member["read_only"] = True
    proc = await engines.start(argv(conf, exe, mcp, body.get("engine_model"), body.get("engine_effort"), **member),
                               _member_prompt(conf, body, setup, rt.cfg) if rt.cfg.team else
                               prompt(conf, body, member.get("read_only", False)), conf.root)
    s.journal.append(rt.id, "state_change", {"state": NAME, "reason": "Codex started"}, task_id=task_id)
    texts, called, state = [], set(), {"done": False, "error": ""}

    def on_event(event):
        kind, item = event.get("type"), event.get("item") or {}
        if kind in ("item.started", "item.completed"):
            if item.get("type") == "agent_message":
                if kind == "item.completed" and str(item.get("text", "")).strip():
                    texts.append(item["text"])
                return
            shown = steps(item, conf.root)
            for n, a in enumerate(shown):
                call_id = f"{item.get('id')}:{n}"
                if call_id not in called:
                    called.add(call_id)
                    usage.steps += 1
                    s.journal.append(rt.id, "tool_call", {"tool": NAME, "call_id": call_id, "arguments": a}, task_id=task_id)
                if kind == "item.completed":
                    s.journal.append(rt.id, "tool_result", {"tool": NAME, "call_id": call_id, "ok": _ok(item), "claims": [],
                                                            "evidence": [], "notes": [], "external": True,
                                                            "data_class": conf.code_data_class}, task_id=task_id)
        elif kind == "turn.completed":
            u = event.get("usage") or {}
            usage.model_calls += 1
            usage.input_tokens += int(u.get("input_tokens") or 0)  # cached input is part of it
            usage.output_tokens += int(u.get("output_tokens") or 0)
            usage.cached_tokens += int(u.get("cached_input_tokens") or 0)
            state["done"] = True
            s.journal.append(rt.id, "model_response", {"finish": "completed", "tool_calls": 0, "engine": NAME,
                                                       "input_tokens": int(u.get("input_tokens") or 0),
                                                       "output_tokens": int(u.get("output_tokens") or 0),
                                                       "cached_tokens": int(u.get("cached_input_tokens") or 0)}, task_id=task_id)
        elif kind == "turn.failed":
            state["error"] = str((event.get("error") or {}).get("message", "")) or "turn failed"
        elif kind == "error":
            state["error"] = str(event.get("message", ""))

    outcome = await engines.events(rt, task_id, proc, on_event)
    await proc.wait()
    err = (await proc.stderr.read()).decode("utf-8", "replace").strip()
    report = getattr(proc, "why", "") or (texts[-1] if texts else "")
    if outcome is None:
        if state["done"]:
            outcome = "done"
        else:
            said = state["error"] or err[-800:]
            if re.search(r"log ?in|401|unauthori[sz]ed|auth", said, re.I):
                outcome, report = "blocked", ("Codex 没有登录（或登录过期）。在终端运行一次 codex，按提示登录，再回来重试。\n\n"
                                              f"它说：{said[-400:]}")
            else:
                outcome, report = "failed", f"Codex stopped without finishing. {said}"
    outcome, report = await engines.finish(rt, outcome, report, found)
    return outcome, report or "(Codex returned no text)", found
