"""Video editing for agents through CodeCut (2026-11-01).

CodeCut (D:/CodeDoctor/code-doctor/tools/codecut) is the user's video editor: a desktop window and a JSON-first command line that
share one project file and one renderer. Agents edit with the command line, never by clicking the window: every
command answers with one JSON object ({"ok": true, ...} or {"ok": false, "error": ...}), so a result is a fact, not a
guess from a screenshot. Three tools:

    video_project  read: list a project's clips, check it, the JSON contract, a media file's length and streams
    video_edit     change: init, add, split, text, update, duplicate, remove, move, set
    video_render   render the MP4 (or a quick preview)

Project files, sources and outputs must be inside the project folder (URLs are allowed for code scenes); CodeCut never
runs repository scripts. The tools exist only in an investigation the user started with @CodeCut in the message box
(body["toolsets"], agents/runtime._task_tools) and where CodeCut is found: $CODECUT_HOME, or tools/codecut next to
this repository. CodeCut needs Playwright and PySide6, so it runs in its own Python ($CODECUT_PYTHON, else the one its
launcher uses).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from codedoctor.agents.tools import TOOLS, Tool, ToolContext, ToolResult, _code_class, _err, _obj, _safe_path

_HERE = Path(__file__).resolve()
# what the user can call in with @ (desktop/composer.py); code3d: codedoctor/model3d.py; the others: codedoctor/makers.py
TOOLSETS = ("codecut", "code3d", "codesound", "codepage", "codegame", "codedeck", "codedata", "codecad", "codelab", "codetools", "codefilm", "codepdf")
EDIT_ACTIONS = ("init", "add", "split", "text", "update", "duplicate", "remove", "move", "set")
READ_ACTIONS = ("list", "check", "schema", "info", "frame")
TEXT_LIMIT = 12000


def home() -> Path | None:
    """CodeCut's folder, or None when it is not installed."""
    for cand in (os.environ.get("CODECUT_HOME"), _HERE.parents[3] / "tools" / "codecut", _HERE.parents[2] / "tools" / "codecut"):
        if cand and (Path(cand) / "codecut.py").is_file():
            return Path(cand).resolve()
    return None


def hands(config, agent_id: str) -> str:
    """Who edits when the user called in @CodeCut: heads only decide and schedule (no editing tools), so a task sent to
    a head goes to the first worker with a guardian (the guardian still reviews), else the first worker."""
    role = config.agents[agent_id].role
    if role not in ("head_dispatch", "head_logic"):
        return agent_id
    from codedoctor.agents import orchestration as orch

    workers = orch.agents_with_role(config, "worker")
    return next((w for w in workers if orch.guardian_for(config, w)), workers[0] if workers else agent_id)


_windows: dict[str, subprocess.Popen] = {}


def open_window(folder) -> bool:
    """CodeCut's window following `folder` (editor.py --follow): it shows the project the agents edit there, live.
    One window per folder; opened again only after it was closed."""
    where = home()
    if where is None:
        return False
    key = str(Path(folder).resolve()).lower()
    proc = _windows.get(key)
    if proc is not None and proc.poll() is None:
        return True
    exe = Path(python())
    if exe.with_name("pythonw.exe").is_file():
        exe = exe.with_name("pythonw.exe")  # no console window
    try:
        _windows[key] = subprocess.Popen([str(exe), str(where / "editor.py"), "--follow", str(Path(folder).resolve()), "--compact"],
                                         cwd=str(where), close_fds=True)
    except OSError:
        return False
    return True


def python() -> str:
    """The tools' interpreter: $CODECUT_PYTHON; else Lumen's own (its .venv), when setup.ps1 put the tools' libraries there
    - a fresh install keeps everything in Lumen's folder; else the Python CodeCut's launcher uses (older installs, where the
    tools' libraries went into the user's Python 3.12); else this one.

    A clean install from GitHub (2026-11-15) showed why: pip refused to write into the user's Python and setup went on, so
    on a new computer CodeCut would have had nothing to run with."""
    env = os.environ.get("CODECUT_PYTHON")
    if env:
        return env
    import importlib.util

    own = Path(sys.executable).with_name("python.exe")  # Lumen runs as pythonw.exe; its console twin sits beside it
    if own.is_file() and importlib.util.find_spec("playwright") is not None:  # the one tools library Lumen itself lacks
        return str(own)
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"
    if local.is_file():
        return str(local)
    return shutil.which("python") or sys.executable


def run(args: list[str], cwd: Path, timeout: int = 120) -> dict:
    """One CodeCut command; its JSON answer (the last JSON line of stdout)."""
    where = home()
    if where is None:
        return {"ok": False, "error": "CodeCut is not installed (set CODECUT_HOME)"}
    try:
        out = subprocess.run([python(), str(where / "codecut.py"), *args], cwd=str(cwd), capture_output=True, timeout=timeout,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                             creationflags=0x08000000 if os.name == "nt" else 0)  # no console window
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"CodeCut did not finish in {timeout} s"}
    except OSError as e:
        return {"ok": False, "error": f"cannot start CodeCut: {e}"}
    for line in reversed(out.stdout.decode("utf-8", "replace").strip().splitlines()):
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        if isinstance(answer, dict):
            return answer
    err = (out.stderr.decode("utf-8", "replace") or out.stdout.decode("utf-8", "replace")).strip()
    return {"ok": False, "error": err[-1500:] or f"CodeCut exited with code {out.returncode}"}


def _inside(ctx: ToolContext, rel: str) -> str:
    return str(_safe_path(ctx, rel)[0])


def _source(ctx: ToolContext, src: str) -> str:
    if src.startswith(("http://", "https://")):
        return src
    return _inside(ctx, src)


def _shown(cmd: list[str], root: Path) -> str:
    """The command as a person would type it in the project folder."""
    base = str(root) + os.sep
    return "codecut " + " ".join(a.replace(base, "").replace("\\", "/") if isinstance(a, str) else str(a) for a in cmd)


def _answer(ctx: ToolContext, cmd: list[str], root: Path, res: dict) -> ToolResult:
    """CodeCut's JSON answer, recorded as evidence (ev:test: - a run of CodeCut on the project as it is now): a
    finding about the cut ("the export is 5.5 s with audio") can cite it, like a test run for code."""
    ok = bool(res.get("ok", True))
    text = json.dumps(res, ensure_ascii=False)
    ev_id = None
    if cmd[0] != "schema":
        ev_id = ctx.services.evidence.add_test_run(root, _shown(cmd, root), 0 if ok else 1, text, agent_id=ctx.agent_id,
                                                   data_class=_code_class(ctx))
    if len(text) > TEXT_LIMIT:
        text = text[:TEXT_LIMIT] + " …(cut)"
    head = f"evidence: {ev_id}\n" if ev_id else ""
    return ToolResult(ok=ok, content=("" if ok else "ERROR: ") + head + text, evidence=[ev_id] if ev_id else [])


ACTION_CN = {"init": "新建剪辑项目", "add": "加入素材", "split": "分割片段", "text": "加字幕", "update": "修改片段",
             "duplicate": "复制片段", "remove": "删除片段", "move": "移动片段", "set": "修改片段"}


def change_line(name: str, args: dict, res: ToolResult) -> str:
    """One line of the hands' system-written report for a video edit or export."""
    project = args.get("project", "")
    if not res.ok:
        return f"{name} 失败：{res.content.removeprefix('ERROR: ').split(chr(10))[-1][:160]}"
    try:
        answer = json.loads(res.content.split("\n", 1)[-1] if res.content.startswith("evidence:") else res.content)
    except ValueError:
        answer = {}
    if name == "video_render":
        dur = answer.get("duration")
        return f"导出 {args.get('output') or Path(str(answer.get('output', 'result.mp4'))).name}" + (f"（{dur:g} 秒）" if dur else "")
    action = args.get("action", "")
    what = {"add": args.get("source", ""), "split": f"{args.get('clip')} 于 {args.get('time')} 秒",
            "text": f"“{args.get('text', '')}”", "update": f"{args.get('clip')}：" + json.dumps(args.get("fields", {}), ensure_ascii=False),
            "set": f"{args.get('clip')}：{args.get('field')}={args.get('value')}", "duplicate": args.get("clip", ""),
            "remove": args.get("clip", ""), "move": f"{args.get('clip')} 到第 {args.get('position')} 位"}.get(action, "")
    return f"{project}：{ACTION_CN.get(action, action)} {what}".strip()


def _frame(ctx: ToolContext, args: dict, root: Path) -> ToolResult:
    """One picture of a video: agents check titles and picture by looking, not by asking someone with a screen."""
    if not args.get("media"):
        return _err("frame needs media (the video file in the project)")
    where = home()
    if where is None:
        return _err("CodeCut is not installed (set CODECUT_HOME)")
    source = _inside(ctx, args["media"])
    target = root / "out" / f"frame-{Path(source).stem}-{float(args.get('at', 0)):g}s.png"
    target.parent.mkdir(exist_ok=True)
    code = ("import sys, subprocess; sys.path.insert(0, sys.argv[1]); import codecut; "
            "sys.exit(subprocess.run([codecut.tool('ffmpeg'), '-y', '-ss', sys.argv[2], '-i', sys.argv[3], '-frames:v', '1', "
            "sys.argv[4]], capture_output=True).returncode)")
    try:
        done = subprocess.run([python(), "-c", code, str(where), str(float(args.get("at", 0))), source, str(target)],
                              capture_output=True, timeout=60, creationflags=0x08000000 if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired) as e:
        return _err(f"could not take the picture: {e}")
    if done.returncode or not target.is_file():
        return _err(f"could not take the picture (exit {done.returncode})")
    ev = ctx.services.evidence.add_blob(target.read_bytes(), "image/png", source="tool", collected_by="video.frame/0",
                                        agent_id=ctx.agent_id, data_class=_code_class(ctx))
    return ToolResult(ok=True, evidence=[ev], images=[ev], data_class=_code_class(ctx),
                      content=f"picture of {args['media']} at {float(args.get('at', 0)):g} s: {target.relative_to(root).as_posix()}")


def video_project(ctx: ToolContext, args: dict) -> ToolResult:
    root = _safe_path(ctx, ".")[0]
    action = args["action"]
    if action == "frame":
        return _frame(ctx, args, root)
    if action == "schema":
        return _answer(ctx, ["schema"], root, run(["schema"], root))
    if action == "info":
        if not args.get("media"):
            return _err("info needs media (a file in the project)")
        cmd = ["info", _inside(ctx, args["media"])]
        return _answer(ctx, cmd, root, run(cmd, root))
    if not args.get("project"):
        return _err(f"{action} needs project (the project's .json file)")
    cmd = [action, _inside(ctx, args["project"])]
    return _answer(ctx, cmd, root, run(cmd, root))


def _num(v) -> str:
    return repr(float(v)) if not isinstance(v, bool) else str(v)


def video_edit(ctx: ToolContext, args: dict) -> ToolResult:
    root = _safe_path(ctx, ".")[0]
    action, project = args["action"], _inside(ctx, args["project"])
    clip = args.get("clip")
    if action in ("split", "update", "duplicate", "remove", "move", "set") and not clip:
        return _err(f"{action} needs clip (its id; see video_project list)")
    if action == "init":
        cmd = ["init", project]
        for k in ("width", "height", "fps"):
            if k in args:
                cmd += [f"--{k}", str(int(args[k]))]
    elif action == "add":
        if not args.get("kind") or not args.get("source"):
            return _err("add needs kind (code, video, audio, image) and source")
        cmd = ["add", project, args["kind"], _source(ctx, args["source"])]
        if clip:
            cmd += ["--id", clip]
        for k in ("duration", "trim", "volume", "start", "wait"):
            if k in args:
                cmd += [f"--{k}", _num(args[k])]
        for k in ("x", "y", "width", "height"):
            if k in args:
                cmd += [f"--{k}", str(int(args[k]))]
        if args.get("entry"):
            cmd += ["--entry", args["entry"]]
        if args.get("over"):
            cmd += ["--over", args["over"]]
    elif action == "split":
        if "time" not in args:
            return _err("split needs time (seconds on the whole timeline)")
        cmd = ["split", project, clip, _num(args["time"])]
    elif action == "text":
        if not args.get("text"):
            return _err("text needs text")
        cmd = ["text", project, args["text"]]
        if clip:
            cmd += ["--id", clip]
        for k, flag in (("start", "--start"), ("duration", "--duration"), ("x", "--x"), ("y", "--y")):
            if k in args:
                cmd += [flag, _num(args[k])]
        if "font_size" in args:
            cmd += ["--size", str(int(args["font_size"]))]
        if args.get("color"):
            cmd += ["--color", args["color"]]
        if args.get("box") is False:
            cmd += ["--no-box"]
    elif action == "update":
        if not args.get("fields"):
            return _err("update needs fields, e.g. {\"speed\": 2, \"fade_in\": 0.5}")
        cmd = ["update", project, clip, json.dumps(args["fields"], ensure_ascii=False)]
    elif action == "move":
        if "position" not in args:
            return _err("move needs position (1-based, within its track)")
        cmd = ["move", project, clip, str(int(args["position"]))]
    elif action == "set":
        if not args.get("field") or "value" not in args:
            return _err("set needs field and value")
        cmd = ["set", project, clip, args["field"], _num(args["value"])]
    else:  # duplicate, remove
        cmd = [action, project, clip]
    return _answer(ctx, cmd, root, run(cmd, root))


def video_render(ctx: ToolContext, args: dict) -> ToolResult:
    root = _safe_path(ctx, ".")[0]
    cmd = ["preview" if args.get("preview") else "render", _inside(ctx, args["project"])]
    if args.get("output"):
        out = _inside(ctx, args["output"])
        if not out.lower().endswith(".mp4"):
            return _err("output must be an .mp4 file")
        cmd += ["-o", out]
    if args.get("scene"):
        if not args.get("preview"):
            return _err("scene works with preview only")
        cmd += ["--scene", args["scene"]]
    if args.get("overwrite"):
        cmd += ["--force"]
    return _answer(ctx, cmd, root, run(cmd, root, timeout=int(args.get("timeout_s", 900))))


PATH = {"type": "string", "minLength": 1, "maxLength": 500}
NUM = {"type": "number"}
VIDEO_TOOLS = [
    Tool("video_project", "Video editing (CodeCut): read a video project. action=list shows every clip with its id, kind, "
                          "duration and the whole length; check validates it and its sources; schema gives the project JSON "
                          "contract (all fields: speed, fades, crop, colour, titles); info gives a media file's length and "
                          "streams; frame shows a picture of a video (media) at a moment (at, seconds), to check titles and "
                          "picture with your own eyes. Paths are relative to the project folder.",
         _obj({"action": {"enum": list(READ_ACTIONS)}, "project": PATH, "media": PATH,
               "at": {"type": "number", "minimum": 0}}, ["action"]), video_project),
    Tool("video_edit", "Video editing (CodeCut): change a video project (.json). init: new project (width, height, fps). "
                       "add: a clip - kind code (an HTML page or http URL, rendered as it runs) / video / image as the next "
                       "scene, audio at start; over=<scene id> makes a picture-in-picture (x, y, width, height). "
                       "split: cut clip at time (seconds on the whole timeline). text: a burned-in title (start, duration, "
                       "font_size, color, x/y centre). update: any fields of clip, e.g. {\"speed\": 2, \"fade_in\": 0.5, "
                       "\"volume\": 0.3, \"crop\": [0,0,0,0.1], \"saturation\": 1.2, \"rotate\": 90}. duplicate / remove / "
                       "move (position, 1-based) / set (field, value). Every answer is CodeCut's JSON; ok:false says why.",
         _obj({"action": {"enum": list(EDIT_ACTIONS)}, "project": PATH, "clip": {"type": "string", "maxLength": 80},
               "kind": {"enum": ["code", "video", "audio", "image"]}, "source": PATH, "entry": PATH, "over": {"type": "string"},
               "duration": NUM, "trim": NUM, "volume": NUM, "start": NUM, "wait": NUM, "time": NUM, "x": NUM, "y": NUM,
               "width": NUM, "height": NUM, "fps": NUM, "text": {"type": "string", "minLength": 1, "maxLength": 500},
               "font_size": NUM, "color": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}, "box": {"type": "boolean"},
               "fields": {"type": "object"}, "position": {"type": "integer", "minimum": 1},
               "field": {"enum": ["duration", "trim", "volume", "start", "x", "y", "width", "height", "wait"]}, "value": NUM},
              ["action", "project"]),
         video_edit, effect_class="external", retry_safe=False),
    Tool("video_render", "Video editing (CodeCut): render the project to an MP4 inside the project folder (default "
                         "result.mp4 next to it). preview=true makes a quick preview (scene=<id> for one scene). An existing "
                         "file is kept unless overwrite=true. Report the output path only when the answer says ok:true.",
         _obj({"project": PATH, "output": PATH, "preview": {"type": "boolean"}, "scene": {"type": "string"},
               "overwrite": {"type": "boolean"}, "timeout_s": {"type": "integer", "minimum": 30, "maximum": 3600}}, ["project"]),
         video_render, effect_class="external", retry_safe=False),
]
for _t in VIDEO_TOOLS:
    TOOLS[_t.name] = _t
NAMES = tuple(t.name for t in VIDEO_TOOLS)
