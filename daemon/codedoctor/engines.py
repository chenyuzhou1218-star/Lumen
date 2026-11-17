"""Other AIs that can do an investigation's work (2026-11-02): the user's own Claude Code or Codex, headless.

Lumen stays the hub - the project, the snapshot before and after (undo), the steps on the task page, the tests
it runs afterwards, the rules on what may leave the machine - and the engine does the work in the project folder on
the user's own subscription. Each engine is a module with executable() and async run(rt, msg, body) -> (outcome,
summary, found), like AgentRuntime._task_loop; this module holds what they share.
"""

from __future__ import annotations

import asyncio
import atexit
import importlib
import json
import os
import re
import signal
import subprocess

NAMES = ("claude_code", "codex")
TIMEOUT_S = 24 * 3600  # the user's limit for one run
SILENT_S = 20 * 60  # the user's rule: an AI that shows nothing at all for this long, not even thinking, is closed


TITLES = {"claude_code": "Claude Code", "codex": "Codex"}
# Each engine's own reasoning levels, by the names it shows them under (Codex: Low ... Ultra; Claude Code: low ... max).
# None of them has a "no thinking" level, so Lumen's 不思考/低/中/高/最高 is never offered for an engine.
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
EFFORT_NAMES = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "Extra High", "max": "Max", "ultra": "Ultra"}
CLAUDE_EFFORT_NAMES = {"low": "低", "medium": "中等", "high": "高", "xhigh": "超高", "max": "最高"}  # as Claude's own menu says


def effort_name(engine: str | None, key: str | None) -> str:
    """A level by the name that engine gives it."""
    names = CLAUDE_EFFORT_NAMES if engine == "claude_code" else EFFORT_NAMES
    return names.get(key, "")


def get(name: str):
    if name not in NAMES:
        raise KeyError(f"unknown engine {name!r}; known: {', '.join(NAMES)}")
    return importlib.import_module(f"codedoctor.{name}")


def status(name: str) -> str:
    """"ready" (installed and signed in), "login" (installed, not signed in) or "missing". Asks the program itself,
    which takes a second or two: call it off the UI thread."""
    mod = get(name)
    exe = mod.executable()
    if not exe:
        return "missing"
    argv = ([exe, "auth", "status"] if name == "claude_code" else [*exe, "login", "status"])
    try:
        out = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                             env=env(), stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return "login"
    text = out.stdout + out.stderr
    if name == "claude_code":
        try:
            return "ready" if json.loads(out.stdout).get("loggedIn") else "login"
        except ValueError:
            return "login"
    return "ready" if out.returncode == 0 and "logged in" in text.lower() and "not logged in" not in text.lower() else "login"


LOGIN_COMMAND = {"claude_code": "claude", "codex": "codex login"}


def endpoint(name: str) -> dict:
    """The configuration entry that sets an engine up as a service: its agents hand their investigations to it."""
    return {"id": name.replace("_", "-"), "name": TITLES[name], "provider": name, "kind": "engine",
            "base_url": f"engine:{name}", "local": False, "max_data_class": "internal",
            "models": [m["id"] for m in models(name)] or [name]}


def models(name: str) -> list[dict]:
    """The engine's own models, as it lists them: [{"id", "name", "efforts": [...], "default_effort", "yours"}]
    ("yours": the one set as default in the engine's own settings)."""
    try:
        return get(name).models()
    except Exception:  # an unreadable list: the engine's own default still works
        return []


def check_choice(name: str, model: str | None, effort: str | None) -> None:
    """A model and level the engine has (ValueError otherwise); unknown lists let anything well-formed through."""
    if effort is not None and effort not in EFFORTS:
        raise ValueError(f"{TITLES[name]} 没有 {effort!r} 这一档（它的档位：{', '.join(EFFORT_NAMES.values())}）")
    if model is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}", model):
        raise ValueError(f"不是模型名：{model!r}")
    listed = {m["id"]: m for m in models(name)}
    if model and listed and model not in listed:
        raise ValueError(f"{TITLES[name]} 没有模型 {model!r}（它有：{', '.join(listed)}）")
    if effort and listed:  # the chosen model's levels; without a model, any of the engine's
        has = listed[model]["efforts"] if model else sorted({e for m in listed.values() for e in m["efforts"]},
                                                              key=EFFORTS.index)
        if effort not in has:
            who = listed[model]["name"] if model else TITLES[name]
            raise ValueError(f"{who} 没有 {EFFORT_NAMES[effort]} 这一档"
                             f"（它的档位：{', '.join(EFFORT_NAMES[e] for e in has) or '无'}）")


def label(body: dict) -> str:
    """"Codex · GPT-6.1-Sol · Ultra": who does the work, as the engine names it."""
    name = body["engine"]
    model = body.get("engine_model")
    if model:
        model = next((m["name"] for m in models(name) if m["id"] == model), model)
    effort = effort_name(name, body.get("engine_effort"))
    return " · ".join(x for x in (TITLES[name], model, effort) if x)


def refused(conf, title: str) -> str | None:
    """Why this project's code may not go to the engine (a cloud service), or None."""
    if conf.code_data_class == "local_only":
        return (f"这个项目的代码级别是“仅本机”，不能交给 {title}（它是云端服务）。"
                "要用它，先在首页把代码级别改成“内部代码”。")
    return None


def env(**extra) -> dict:
    """The environment for the engine: the user's, minus a Claude Code session's own variables (when Lumen
    itself was started from one, the child must not take that session's sign-in for its own)."""
    out = {k: v for k, v in os.environ.items()
           if k != "CLAUDECODE" and not k.startswith(("CLAUDE_CODE_", "CLAUDE_AGENT_SDK_"))}
    out.update(extra)
    return out


_live: set = set()  # engines running now: stopped with Lumen (atexit) and with their task


def kill(proc) -> None:
    """The engine and everything it started: on Windows, killing Codex's node launcher leaves its codex.exe working
    on (and editing the project), so the whole process tree goes."""
    _live.discard(proc)
    if proc.returncode is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # its own session (start_new_session in start)
        except OSError:
            pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass


@atexit.register
def _stop_all() -> None:
    for proc in list(_live):
        kill(proc)


async def team_setup(rt, body: dict, tools_at: str, link_id: str | None = None) -> dict:
    """What an engine run needs for a member of the Lumen team: {"toolsets", "env", "persona", "notes", "extra"}; for
    anyone else only the toolsets the user called in."""
    toolsets = list(body.get("toolsets") or [])
    if not rt.cfg.team:
        return {"toolsets": toolsets, "env": None, "persona": None, "notes": "", "extra": None}
    from codedoctor.agents import team, team_link

    s, conf = rt.s, rt.s.config
    # the one who edits gets the editor
    toolsets = [t for t in toolsets if (t != "codecut" or "video_edit" in rt.tools) and (t != "code3d" or "code3d_run" in rt.tools)
                and (t in ("codecut", "code3d") or t.startswith("@") or "maker_read" in rt.tools)]
    names = [n for n in rt.tools if n in team_link.ALLOWED]
    names.append("approve_permission")  # Claude Code asks it before Edit, Write and Bash (the user's 批准方式; claude_code.argv)
    toolsets += [f"@{n}" for n in names]
    return {"toolsets": toolsets, "env": team_link.env(await team_link.ensure(s), link_id or body["task_id"], rt.id) if names else None,
            "persona": team.engine_prompt(rt.id, conf.name, sorted(conf.agents), tuple(conf.permissions.command_allowlist), tools_at,
                                          tuple(rt.tools), team.out_of_action(s)),
            "notes": await team.memory_notes(rt, body), "extra": None}


async def start(argv: list[str], prompt: str | None, cwd, extra_env: dict | None = None) -> asyncio.subprocess.Process:
    """prompt None: stdin stays open, messages follow (engine_sessions.py)."""
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=str(cwd), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=16 * 1024 * 1024, env=env(**(extra_env or {})),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
    _live.add(proc)
    if os.name == "nt":  # ends with Lumen, even when Lumen cannot close it (killed, crashed): desktop/job.py
        from codedoctor.desktop import job

        job.adopt_pid(proc.pid)
    if prompt is not None:
        proc.stdin.write(prompt.encode("utf-8"))  # on stdin: the instructions may be longer than a command line may be
        await proc.stdin.drain()
        proc.stdin.close()
    return proc


def _waiting_on_others(rt, task_id: str) -> bool:
    from codedoctor.agents import orchestration as orch

    return any(c["state"] != "finished" for c in orch.children(rt.s, task_id))


async def events(rt, task_id: str, proc, on_event) -> str | None:
    """Feed each JSON line the engine prints to on_event; "cancelled"/"failed" if it was stopped, else None.
    on_event returning True ends the turn with the engine still running (a process kept between messages).
    However else this ends - the task cancelled, Lumen stopping - the engine does not run on alone."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + TIMEOUT_S
    silent_until = loop.time() + SILENT_S
    try:
        while True:
            if rt._cancel_requested(task_id):
                kill(proc)
                return "cancelled"
            if loop.time() > deadline:
                kill(proc)
                proc.why = f"运行满 {TIMEOUT_S // 3600} 小时，已强制关闭。"
                return "failed"
            if loop.time() > silent_until:
                if _waiting_on_others(rt, task_id):  # Lumen waits for a member, who has a watch of its own
                    silent_until = loop.time() + SILENT_S
                    continue
                kill(proc)
                proc.why = f"这个 AI 连续 {SILENT_S / 60:g} 分钟没有任何动静，连思考都没有，已强制关闭。"
                return "failed"
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), 1.0)
            except asyncio.TimeoutError:
                continue
            if not line:
                _live.discard(proc)
                return None
            silent_until = loop.time() + SILENT_S
            try:
                event = json.loads(line.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(event, dict) and on_event(event) is True:
                return None
    except BaseException:
        kill(proc)
        raise


STATUS_RULE = ("Your very last line must be exactly one of: `STATUS: DONE` (the task is fully done), `STATUS: BLOCKED` "
               "(you could not do it without something from the user - a permission, a file, an answer; say what in "
               "the report), `STATUS: FAILED` (you tried and could not do it).")
# on its own line, or at the end of the last sentence ("…叫你 Lumen。STATUS: DONE": a real Codex answer, 2026-11-11)
_STATUS = re.compile(r"[ \t]*[>*`_~-]*[ \t]*STATUS:\s*(DONE|BLOCKED|FAILED)\b[^\w\n]*$", re.I | re.M)


def verdict(report: str) -> tuple[str, str]:
    """The engine's own word on whether it did the task (its last STATUS line), and the report without that line.
    Finishing its turn is not finishing the task: an engine that could not do it says so here."""
    hits = list(_STATUS.finditer(report))
    if not hits:
        return "done", report
    last = hits[-1]
    report = (report[:last.start()] + report[last.end():]).strip()
    word = last.group(1).upper()
    if word == "BLOCKED":
        return "blocked", f"没做完：它需要你给一样东西（权限、文件或回答），见下。\n\n{report}"
    if word == "FAILED":
        return "failed", f"没做成，见下。\n\n{report}"
    return "done", report


async def finish(rt, outcome: str, report: str, found: dict) -> tuple[str, str]:
    """The engine's verdict; when it says it is done, Lumen runs the project's tests itself and says what they show."""
    from codedoctor.agents import testrun

    if outcome == "done":
        outcome, report = verdict(report)
    if outcome == "done" and testrun.command(rt.s):
        res = await asyncio.to_thread(testrun.run, rt.s, rt.id)
        found["evidence"].append(res.evidence)
        report += f"\n\n系统跑了测试（这一步结束后 Lumen 自动运行，不是模型自己说的）：{res.summary}"
    return outcome, report
