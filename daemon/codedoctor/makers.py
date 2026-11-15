"""The tools that make things, for agents (2026-11-06): CodeSound, CodePage, CodeGame, CodeDeck, CodeData, CodeCAD, CodeLab.

Each is a folder in Lumen's tools/ (D:/CodeDoctor/code-doctor/tools/<id>) with a JSON-first command line and a project folder, as Code3D is. They
all follow one shape, so that one pair of tools serves them all, and the list of tools sent to a model does not grow with each:

    maker_read   the guide (schema), checks, what is in a project, a picture already made
    maker_run    what makes something: new project, render, build, play

Like Code3D, they exist only in an investigation the user started with @<tool>, and only where the tool is found. Running a project runs
code, so it asks for what running code asks for. CodeLab only reads logs here: its start and stop stay with the user, because the user's
training jobs are not an agent's to start or stop.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess

from codedoctor import video
from codedoctor.agents.tools import TOOLS, Tool, ToolContext, ToolResult, _code_class, _err, _obj, _safe_path

_HERE = Path(__file__).resolve()
TEXT_LIMIT = 12000
GUIDE_LIMIT = 40000
PICTURES_AT_ONCE = 4


@dataclass(frozen=True)
class Maker:
    id: str
    name: str
    main: str                 # the file that marks a project of this tool, for following it in a window
    reads: tuple              # actions of maker_read
    runs: tuple               # actions of maker_run
    window: bool = False      # has an editor.py that can follow a folder


MAKERS = {m.id: m for m in (
    Maker("codesound", "CodeSound", "song.py", ("schema", "check", "score", "look"), ("init", "render", "midi"), True),
    Maker("codepage", "CodePage", "page.json", ("schema", "check", "look"), ("init", "build"), True),
    Maker("codegame", "CodeGame", "game.js", ("schema", "check", "look"), ("init", "build", "play"), True),
    Maker("codedeck", "CodeDeck", "deck.json", ("schema", "look"), ("init", "build"), True),
    Maker("codedata", "CodeData", "analysis.py", ("schema", "profile", "look"), ("init", "run", "recheck"), True),
    Maker("codecad", "CodeCAD", "part.py", ("schema", "check", "look"), ("init", "build"), True),
    Maker("codelab", "CodeLab", "", ("schema", "watch", "compare", "picture", "look"), ()),
    Maker("codetools", "CodeTools", "", ("schema", "look"), ("plugin",)),
    Maker("codefilm", "CodeFilm", "film.json", ("schema", "check", "look"), ("init", "plan", "build"), True),
    Maker("codepdf", "CodePDF", "", ("schema",), ("run",)),  # no project file; its own window (tool_view.NO_FOLDER) is not a folder follower
)}
IDS = tuple(MAKERS)
READ_ACTIONS = ("schema", "check", "score", "profile", "look", "watch", "compare", "picture")
RUN_ACTIONS = ("init", "render", "midi", "build", "play", "run", "recheck", "plugin", "plan")


def home(tool: str) -> Path | None:
    """The tool's folder, or None when it is not installed."""
    for cand in (os.environ.get(f"{tool.upper()}_HOME"), _HERE.parents[3] / "tools" / tool, _HERE.parents[2] / "tools" / tool):
        if cand and (Path(cand) / f"{tool}.py").is_file():
            return Path(cand).resolve()
    return None


def installed() -> list[str]:
    return [t for t in IDS if home(t) is not None]


def allowed(name: str, config) -> bool:
    """Reading is free. Making things runs code, whoever wrote it."""
    if not installed():
        return False
    return name == "maker_read" or (config.permissions.write_files and config.permissions.run_command != "deny")


def needs_running(tools: list[str]) -> bool:
    """Called in a tool that runs code? CodeLab only reads."""
    return any(MAKERS[t].runs for t in tools if t in MAKERS)


_windows: dict[str, subprocess.Popen] = {}


def open_window(tool: str, root) -> bool:
    """The tool's window, following the project being worked on under root. A tool without one just works in the background."""
    where = home(tool)
    if where is None or not MAKERS[tool].window:
        return False
    key = f"{tool}:{Path(root).resolve()}".lower()
    proc = _windows.get(key)
    if proc is not None and proc.poll() is None:
        return True
    exe = Path(video.python())
    if exe.with_name("pythonw.exe").is_file():
        exe = exe.with_name("pythonw.exe")  # no console window
    try:
        _windows[key] = subprocess.Popen([str(exe), str(where / "editor.py"), "--watch", str(Path(root).resolve())], cwd=str(where), close_fds=True)
    except OSError:
        return False
    return True


def open_app(tool: str, extra: str = "") -> bool:
    """The tool's own window, from the 插件 page: a program of its own, not tied to any chat."""
    from codedoctor import model3d

    where = home(tool) if tool in MAKERS else (model3d.home() if tool == "code3d" else video.home())
    if where is None or not (where / "editor.py").is_file():
        return False
    exe = Path(video.python())
    if exe.with_name("pythonw.exe").is_file():
        exe = exe.with_name("pythonw.exe")
    key = f"{tool}:{extra}"
    running = _opened.get(key)
    if running is not None and running.poll() is None:  # already open: a second click starts nothing more (each one was a heavy process)
        return True
    try:
        _opened[key] = subprocess.Popen([str(exe), str(where / "editor.py"), *([extra] if extra else [])], cwd=str(where), close_fds=True)
    except OSError:
        return False
    return True


_opened: dict[str, subprocess.Popen] = {}


def run(tool: str, args: list[str], cwd: Path, timeout: int = 1800) -> dict:
    """One command of the tool; its JSON answer (the last line of stdout that is an answer)."""
    where = home(tool)
    if where is None:
        return {"ok": False, "error": f"{MAKERS[tool].name} is not installed (set {tool.upper()}_HOME)"}
    if not Path(cwd).is_dir():  # Windows would say only "the directory name is invalid"; say which one, and what to do
        if str(os.environ.get("LUMEN_LANG", "")).lower().startswith("zh"):
            return {"ok": False, "error": f"文件夹 {cwd} 不存在。请先建好这个文件夹（init 会在已有的文件夹里建项目），或者换一个已有的文件夹。"}
        return {"ok": False, "error": f"The folder {cwd} does not exist. Create it first (init makes a project inside an existing folder), or use a folder that exists."}
    try:
        out = subprocess.run([video.python(), str(where / f"{tool}.py"), *args], cwd=str(cwd), capture_output=True, timeout=timeout + 30,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}, creationflags=0x08000000 if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{MAKERS[tool].name} did not finish in {timeout} s"}
    except OSError as e:
        return {"ok": False, "error": f"cannot start {MAKERS[tool].name}: {e}"}
    for line in reversed(out.stdout.decode("utf-8", "replace").strip().splitlines()):
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        if isinstance(answer, dict) and "event" not in answer:
            return answer
    err = (out.stderr.decode("utf-8", "replace") or out.stdout.decode("utf-8", "replace")).strip()
    return {"ok": False, "error": err[-1500:] or f"{MAKERS[tool].name} exited with code {out.returncode}"}


def _picture_files(res: dict, folder: Path) -> list[Path]:
    names = list(res.get("pictures") or [])
    if res.get("picture"):
        names.append(res["picture"])
    found = []
    for name in names:
        p = Path(name)
        p = p if p.is_absolute() else folder / p
        if p.suffix.lower() == ".png" and p.is_file():
            found.append(p)
    return found[:PICTURES_AT_ONCE]


def _answer(ctx: ToolContext, shown: str, root: Path, res: dict, folder: Path, limit: int = TEXT_LIMIT) -> ToolResult:
    """The tool's JSON answer, recorded as evidence like a test run; pictures go to the model's own eyes."""
    ok = bool(res.get("ok", True))
    res = {**{k: res[k] for k in ("ok", "warnings", "error") if k in res}, **res}  # what must be read comes first
    many = len(res.get("pictures") or [])
    if many > PICTURES_AT_ONCE:
        res["pictures_note"] = f"{many} pictures; the first {PICTURES_AT_ONCE} are shown. maker_read action=look file=... shows any other."
    text = json.dumps(res, ensure_ascii=False)
    ev_id = ctx.services.evidence.add_test_run(root, shown, 0 if ok else 1, text, agent_id=ctx.agent_id, data_class=_code_class(ctx))
    if len(text) > limit:
        text = text[:limit] + " …(cut)"
    images = []
    for path in _picture_files(res, folder) if ok else []:
        images.append(ctx.services.evidence.add_blob(path.read_bytes(), "image/png", source="tool", collected_by="makers/0", agent_id=ctx.agent_id, data_class=_code_class(ctx)))
    head = f"evidence: {ev_id}\n" if ev_id else ""
    return ToolResult(ok=ok, content=("" if ok else "ERROR: ") + head + text, evidence=([ev_id] if ev_id else []) + images, images=images, data_class=_code_class(ctx))


def _known(args: dict, actions: tuple) -> str | None:
    tool = args["tool"]
    if tool not in MAKERS:
        return f"unknown tool {tool}: {', '.join(IDS)}"
    if home(tool) is None:
        return f"{MAKERS[tool].name} is not installed"
    if args["action"] not in actions:
        return f"{MAKERS[tool].name} has no {args['action']} here; it has: {', '.join(actions) or 'nothing to run'}"
    return None


def maker_read(ctx: ToolContext, args: dict) -> ToolResult:
    wrong = _known(args, MAKERS.get(args["tool"], MAKERS["codelab"]).reads)
    if wrong:
        return _err(wrong)
    tool, action = args["tool"], args["action"]
    root = _safe_path(ctx, ".")[0]
    if action == "schema":
        cmd = ["schema", args["file"]] if tool == "codetools" and args.get("file") else ["schema"]  # one plugin's fields
        return _answer(ctx, f"{tool} schema", root, run(tool, cmd, root), root, GUIDE_LIMIT)
    if action == "look":
        if not args.get("file"):
            return _err("look needs file: a .png in the project")
        picture = _safe_path(ctx, args["file"])[0]
        if picture.suffix.lower() != ".png" or not picture.is_file():
            return _err(f"no picture at {args['file']}")
        ev = ctx.services.evidence.add_blob(picture.read_bytes(), "image/png", source="tool", collected_by="makers/0", agent_id=ctx.agent_id, data_class=_code_class(ctx))
        return ToolResult(ok=True, evidence=[ev], images=[ev], data_class=_code_class(ctx), content=f"picture: {args['file']}")
    if tool == "codelab":
        logs = args.get("logs") or ([args["file"]] if args.get("file") else [])
        if not logs:
            return _err(f"{action} needs file: a log inside the project")
        paths = [str(_safe_path(ctx, f)[0]) for f in logs]
        if action == "watch":
            cmd = ["watch", paths[0]]
        elif action == "compare":
            cmd = ["compare", *paths]
        else:
            cmd = ["picture", paths[0], "-o", str(root / ".lumen-lab.png")]
        return _answer(ctx, f"codelab {action}", root, run(tool, cmd, root, 120), root)
    if not args.get("project"):
        return _err(f"{action} needs project (the project's folder)")
    folder = _safe_path(ctx, args["project"])[0]
    cmd = ["look" if action == "profile" else action, str(folder)]
    return _answer(ctx, f"{tool} {action} {args['project']}", root, run(tool, cmd, folder), folder)


def maker_run(ctx: ToolContext, args: dict) -> ToolResult:
    wrong = _known(args, MAKERS.get(args["tool"], MAKERS["codelab"]).runs)
    if wrong:
        return _err(wrong)
    tool, action = args["tool"], args["action"]
    root = _safe_path(ctx, ".")[0]
    folder = _safe_path(ctx, args["project"])[0]
    timeout = int(args.get("timeout_s", 1800))
    if tool == "codetools":
        return _plugin(ctx, args, root, folder, timeout)
    if tool == "codepdf":
        return _pdf(ctx, args, root, folder, timeout)
    cmd = [action, str(folder)]
    if tool == "codesound" and action == "render":
        cmd += ["--quality", args.get("quality", "check"), "--timeout", str(timeout)]
        if args.get("stems"):
            cmd.append("--stems")
    elif tool == "codepage" and action == "build":
        cmd.append("--pictures")
    elif tool == "codegame" and action == "play":
        if args.get("steps"):
            cmd += ["--steps", str(_safe_path(ctx, args["steps"])[0])]
    elif tool == "codedata" and action == "run":
        cmd += ["--pictures", "--timeout", str(timeout)]
    elif tool == "codedata" and action == "recheck":
        cmd += ["--timeout", str(timeout)]
    elif tool == "codefilm" and action == "plan":
        extra = args.get("args") or {}
        if not extra.get("idea"):
            return _err("plan needs args.idea: the user's sentence")
        cmd += ["--idea", str(extra["idea"]), "--lines", str(extra.get("lines") or "")]
        if extra.get("seconds"):
            cmd += ["--seconds", str(int(extra["seconds"]))]
    elif tool == "codefilm" and action == "build":
        cmd += ["--quality", "final" if args.get("quality") == "final" else "draft"]
    elif tool == "codecad" and action == "build":
        cmd += ["--timeout", str(timeout)]
    elif tool == "codedeck" and action == "init" and args.get("doc"):
        cmd.append("--doc")
    return _answer(ctx, f"{tool} {action} {args['project']}", root, run(tool, cmd, root if action == "init" else folder, timeout), folder)


PDF_PATHS = ("file", "files")  # the fields of CodePDF that name files: inside the project, like every other tool's


def _pdf(ctx: ToolContext, args: dict, root: Path, folder: Path, timeout: int) -> ToolResult:
    """One operation of CodePDF (images, merge, split, compress, size, rotate, pick): `plugin` names it, `args` are its fields; the
    new files go into `project`. The originals are never changed (CodePDF writes new files)."""
    if not args.get("plugin"):
        return _err("codepdf needs plugin (images, merge, split, compress, size, rotate or pick) and args: maker_read tool=codepdf action=schema lists the fields")
    values = dict(args.get("args") or {})
    for key in PDF_PATHS:
        if values.get(key):
            names = values[key] if isinstance(values[key], list) else [values[key]]
            safe = [str(_safe_path(ctx, str(n))[0]) for n in names]
            values[key] = safe if isinstance(values[key], list) else safe[0]
    folder.mkdir(parents=True, exist_ok=True)
    job = folder / ".pdf_args.json"
    job.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    res = run("codepdf", ["run", args["plugin"], "--args-file", str(job), "--out", str(folder)], root, timeout)
    job.unlink(missing_ok=True)
    return _answer(ctx, f"codepdf {args['plugin']}", root, res, folder)


def _plugin(ctx: ToolContext, args: dict, root: Path, folder: Path, timeout: int) -> ToolResult:
    """One action of one small plugin. Paths in its fields stay inside the project, as every other tool's do; results go to `project`."""
    if not args.get("plugin") or not args.get("plugin_action"):
        return _err("plugin needs plugin and plugin_action: maker_read tool=codetools action=schema lists them")
    told = run("codetools", ["schema", args["plugin"]], root, 60)
    if not told.get("ok"):
        return _err(str(told.get("error")))
    actions = (told.get("plugin") or {}).get("actions")
    if not isinstance(actions, list):
        return _err(f"{args['plugin']}: codetools did not list its actions")
    action = next((a for a in actions if a["key"] == args["plugin_action"]), None)
    if action is None:
        return _err(f"{args['plugin']} has no {args['plugin_action']}: " + ", ".join(a["key"] for a in actions))
    if action["changes"] and ctx.role == "guardian":
        return _err("this action changes the user's files")
    values = dict(args.get("args") or {})
    for f in action["fields"]:
        if f["kind"] in ("file", "folder") and values.get(f["key"]):
            values[f["key"]] = str(_safe_path(ctx, str(values[f["key"]]))[0])
    folder.mkdir(parents=True, exist_ok=True)
    job = folder / ".plugin_args.json"
    job.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    res = run("codetools", ["run", args["plugin"], args["plugin_action"], "--args-file", str(job), "--out", str(folder)], root, timeout)
    job.unlink(missing_ok=True)
    return _answer(ctx, f"codetools {args['plugin']} {args['plugin_action']}", root, res, folder)


def change_line(args: dict, res: ToolResult) -> str:
    """One line of the hands' system-written report."""
    name = MAKERS[args["tool"]].name if args.get("tool") in MAKERS else args.get("tool", "")
    what = f"{name} {args.get('action', '')} {args.get('project', '')}".strip()
    if not res.ok:
        return f"{what} 失败：{res.content.removeprefix('ERROR: ').split(chr(10))[-1][:160]}"
    return what


def result_picture(tools: list[str], root, since: float = 0) -> Path | None:
    """The picture to show in the answer: what the team made in this project since a moment."""
    names = {"shots.png", "latest.png", "desktop.png", "page_01.png", "report.png", "play_moved.png", "play_end.png"}
    found: list[tuple[float, Path]] = []
    for base, dirs, files in os.walk(root):
        rel = Path(base).relative_to(root)
        if len(rel.parts) > 3:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", "__pycache__", "frames", "stems", "sfx")]
        if rel.name == "out":
            for name in names & set(files):
                when = (Path(base) / name).stat().st_mtime
                if when >= since:
                    found.append((when, Path(base) / name))
    return max(found)[1] if found else None


PATH = {"type": "string", "minLength": 1, "maxLength": 500}
TOOL_ID = {"enum": list(IDS)}
MAKER_TOOLS = [
    Tool("maker_read", "Lumen's making tools, whether the user called one in with @ or the work needs it (CodeSound music and sound, CodePage web pages, CodeGame 3D games, CodeDeck slides and documents, CodeData data "
                       "reports, CodeCAD parts to print, CodeLab training logs, CodePDF photos to PDF, merge, split, compress, resize). `tool` is which. action=schema gives its guide: read it before you write anything, and follow it. "
                       "check tests a project without running it; score lists a song's notes and problems; profile shows what is in a data folder; look shows a .png (`file`). "
                       "CodeLab: watch, picture (`file` a log) and compare (`logs`). CodeTools: schema lists dozens of small plugins, and with `file` a plugin id gives its fields. `project` is the project's folder.",
         _obj({"tool": TOOL_ID, "action": {"enum": list(READ_ACTIONS)}, "project": PATH, "file": PATH, "logs": {"type": "array", "items": PATH, "maxItems": 6}}, ["tool", "action"]), maker_read),
    Tool("maker_run", "Makes something with one of Lumen's tools, in the background. init: a new project folder (doc=true for a CodeDeck document). CodeSound: render (quality check, then final; "
                      "stems), midi. CodePage, CodeDeck, CodeCAD: build. CodeGame: build, play (a machine player; steps: a JSON file of key presses). CodeData: run, recheck. "
                      "CodeTools: action=plugin with plugin, plugin_action and args (its fields); project is where results go. "
                      "CodePDF: action=run with plugin (images, merge, split, compress, size, rotate, pick) and args (its fields, see schema); the new PDFs go into project. "
                      "CodeFilm: plan (args: idea, lines, seconds), then write film.json yourself, then build (quality check means a draft, final the full film). "
                      "Answers come with measurements and warnings, and pictures you then see: look at them, fix the biggest thing, and run again. "
                      "Errors give the line. Write the project's files with your file tools.",
         _obj({"tool": TOOL_ID, "action": {"enum": list(RUN_ACTIONS)}, "project": PATH, "quality": {"enum": ["check", "final"]}, "stems": {"type": "boolean"}, "doc": {"type": "boolean"}, "steps": PATH,
               "plugin": {"type": "string", "maxLength": 40}, "plugin_action": {"type": "string", "maxLength": 40}, "args": {"type": "object"},
               "timeout_s": {"type": "integer", "minimum": 30, "maximum": 86400}}, ["tool", "action", "project"]),
         maker_run, effect_class="external", retry_safe=False),
]
for _t in MAKER_TOOLS:
    TOOLS[_t.name] = _t
NAMES = tuple(t.name for t in MAKER_TOOLS)
