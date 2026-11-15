"""3D for agents through Code3D (2026-11-05).

Code3D (D:/CodeDoctor/code-doctor/tools/code3d) is the user's tool for making 3D with code: a window and a JSON-first command line that
share one project folder (project.json, scene.py, out/), with the user's own Blender doing the modelling and rendering in
the background. Two tools:

    code3d_project  read: the c3d kit (schema), check a scene without running it, look at a picture already rendered
    code3d_run      runs the scene in Blender: new project, list what is in it, render, views, export

scene.py is code, so running it asks for what running code asks for: changing files allowed and shell commands not denied.
Inside Blender a guard keeps a scene off programs, the network and files outside its folder (Code3D's kit/guard.py). That
stops mistakes and careless scripts; it is not a wall against a determined attacker, Blender's own C code does not pass it.
The tools exist only in an investigation the user started with @Code3D, and where Code3D and Blender are found. Code3D
runs in the same Python as CodeCut.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from codedoctor import video
from codedoctor.agents.tools import TOOLS, Tool, ToolContext, ToolResult, _code_class, _err, _obj, _safe_path

_HERE = Path(__file__).resolve()
TEXT_LIMIT = 12000
FORMATS = ("glb", "fbx", "obj", "stl", "usd", "blend")
VIEWS = ("camera", "front", "back", "left", "right", "top", "iso")
RUN_ACTIONS = ("init", "objects", "render", "views", "export")
PICTURES_AT_ONCE = 4


def home() -> Path | None:
    """Code3D's folder, or None when it is not installed."""
    for cand in (os.environ.get("CODE3D_HOME"), _HERE.parents[3] / "tools" / "code3d", _HERE.parents[2] / "tools" / "code3d"):
        if cand and (Path(cand) / "code3d.py").is_file():
            return Path(cand).resolve()
    return None


def allowed(name: str, config) -> bool:
    """Reading is free. Running a scene runs code, whoever wrote it."""
    if home() is None:
        return False
    return name == "code3d_project" or (config.permissions.write_files and config.permissions.run_command != "deny")


_windows: dict[str, subprocess.Popen] = {}


def open_window(root) -> bool:
    """Code3D's window, watching a folder: the project being worked on in it comes up by itself, the one the team just
    made included (editor.py --watch)."""
    where = home()
    if where is None:
        return False
    key = str(Path(root).resolve()).lower()
    proc = _windows.get(key)
    if proc is not None and proc.poll() is None:
        return True
    exe = Path(video.python())
    if exe.with_name("pythonw.exe").is_file():
        exe = exe.with_name("pythonw.exe")  # no console window
    try:
        _windows[key] = subprocess.Popen([str(exe), str(where / "editor.py"), "--watch", str(Path(root).resolve())],
                                         cwd=str(where), close_fds=True)
    except OSError:
        return False
    return True


def run(args: list[str], cwd: Path, timeout: int = 900) -> dict:
    """One Code3D command; its JSON answer (the last line of stdout that is an answer, not progress)."""
    where = home()
    if where is None:
        return {"ok": False, "error": "Code3D is not installed (set CODE3D_HOME)"}
    try:
        out = subprocess.run([video.python(), str(where / "code3d.py"), *args], cwd=str(cwd), capture_output=True, timeout=timeout + 30,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}, creationflags=0x08000000 if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Code3D did not finish in {timeout} s"}
    except OSError as e:
        return {"ok": False, "error": f"cannot start Code3D: {e}"}
    for line in reversed(out.stdout.decode("utf-8", "replace").strip().splitlines()):
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        if isinstance(answer, dict) and "event" not in answer:
            return answer
    err = (out.stderr.decode("utf-8", "replace") or out.stdout.decode("utf-8", "replace")).strip()
    return {"ok": False, "error": err[-1500:] or f"Code3D exited with code {out.returncode}"}


def _inside(ctx: ToolContext, rel: str) -> Path:
    return _safe_path(ctx, rel)[0]


def _shown(cmd: list[str], root: Path) -> str:
    base = str(root) + os.sep
    return "code3d " + " ".join(str(a).replace(base, "").replace("\\", "/") for a in cmd)


def _short(res: dict, root: Path) -> dict:
    """Paths as the project knows them. What the agent must read comes first and the scene as a list of things, not of every
    part: a street has 900 parts, and that list once pushed the measured notes past the cut, so a team never read them."""
    res = dict(res)
    for inner in (res, res.get("scene") if isinstance(res.get("scene"), dict) else {}):
        if inner.get("things"):
            inner.pop("objects", None)
    out = {k: res[k] for k in ("ok", "warnings") if k in res}
    for k, v in res.items():
        if k in ("output", "project", "frames") and isinstance(v, str) and v.startswith(str(root)):
            v = Path(v).relative_to(root).as_posix() or "."
        elif k == "pictures":
            v = [Path(p).relative_to(root).as_posix() if p.startswith(str(root)) else p for p in v]
        out[k] = v
    return out


def _version(folder: Path) -> str:
    try:
        return hashlib.sha256((folder / "scene.py").read_bytes() + (folder / "project.json").read_bytes()).hexdigest()
    except OSError:
        return ""


def _seen(folder: Path) -> bool:
    try:
        return (folder / "out" / ".looked").read_text(encoding="utf-8") == _version(folder)
    except OSError:
        return False


def _saw(folder: Path) -> None:
    (folder / "out").mkdir(exist_ok=True)
    (folder / "out" / ".looked").write_text(_version(folder), encoding="utf-8")


NOT_SEEN = ("Refused: nobody has looked at this version of the scene. Render it with quality=check or draft, look at the picture, "
            "fix what is wrong, and then come back. (A real run exported a black window nobody had seen.)")


def _picture(ctx: ToolContext, path: Path) -> str:
    return ctx.services.evidence.add_blob(path.read_bytes(), "image/png", source="tool", collected_by="code3d.render/0", agent_id=ctx.agent_id,
                                          data_class=_code_class(ctx))


def _answer(ctx: ToolContext, cmd: list[str], root: Path, res: dict, pictures: list[Path] | None = None) -> ToolResult:
    """Code3D's JSON answer, recorded as evidence like a test run; pictures go to the model's own eyes."""
    ok = bool(res.get("ok", True))
    text = json.dumps(_short(res, root), ensure_ascii=False)
    ev_id = ctx.services.evidence.add_test_run(root, _shown(cmd, root), 0 if ok else 1, text, agent_id=ctx.agent_id, data_class=_code_class(ctx))
    if len(text) > TEXT_LIMIT:
        text = text[:TEXT_LIMIT] + " …(cut)"
    evidence = [ev_id] if ev_id else []
    images = [_picture(ctx, p) for p in (pictures or []) if p.is_file()] if ok else []
    head = f"evidence: {ev_id}\n" if ev_id else ""
    return ToolResult(ok=ok, content=("" if ok else "ERROR: ") + head + text, evidence=evidence + images, images=images, data_class=_code_class(ctx))


def change_line(args: dict, res: ToolResult) -> str:
    """One line of the hands' system-written report."""
    what = {"init": "新建 3D 项目", "objects": "运行场景", "render": "渲染", "views": "渲染各个角度", "export": "导出模型"}.get(args.get("action", ""), "运行场景")
    if not res.ok:
        return f"{what}失败：{res.content.removeprefix('ERROR: ').split(chr(10))[-1][:160]}"
    return f"{args.get('project', '')}：{what}" + (f" {args['format']}" if args.get("action") == "export" else "")


def code3d_project(ctx: ToolContext, args: dict) -> ToolResult:
    root = _safe_path(ctx, ".")[0]
    action = args["action"]
    if action == "schema":
        return _answer(ctx, ["schema"], root, run(["schema"], root))
    if not args.get("project"):
        return _err(f"{action} needs project (the project's folder)")
    folder = _inside(ctx, args["project"])
    if action == "check":
        return _answer(ctx, ["check", str(folder)], root, run(["check", str(folder)], folder))
    picture = _inside(ctx, args.get("picture") or f"{args['project']}/out/latest.png")  # look
    if picture.suffix.lower() != ".png" or not picture.is_file():
        return _err(f"no picture at {args.get('picture') or 'out/latest.png'}: render first")
    ev = _picture(ctx, picture)
    return ToolResult(ok=True, evidence=[ev], images=[ev], data_class=_code_class(ctx), content=f"picture: {picture.relative_to(root).as_posix()}")


def code3d_run(ctx: ToolContext, args: dict) -> ToolResult:
    root = _safe_path(ctx, ".")[0]
    action, folder = args["action"], _inside(ctx, args["project"])
    timeout = int(args.get("timeout_s", 900))
    limit = ["--timeout", str(timeout)]
    if action == "init":
        cmd = ["init", str(folder)]
        for key in ("width", "height", "fps", "samples"):
            if key in args:
                cmd += [f"--{key}", str(int(args[key]))]
        return _answer(ctx, cmd, root, run(cmd, root))
    if not (folder / "project.json").is_file():
        return _err(f"{args['project']} is not a Code3D project: action=init makes one")
    if action == "objects":
        cmd = ["objects", str(folder), *limit]
        return _answer(ctx, cmd, root, run(cmd, folder, timeout))
    if action == "render":
        quality = args.get("quality", "check")
        if quality == "final" and not _seen(folder):
            return _err(NOT_SEEN)
        cmd = ["render", str(folder), "--view", args.get("view", "camera"), "--quality", quality, *limit]
        if "frame" in args:
            cmd += ["--frame", str(int(args["frame"]))]
        res = run(cmd, folder, timeout)
        if res.get("ok"):
            _saw(folder)
        return _answer(ctx, cmd, root, res, [Path(res["output"])] if res.get("output") else [])
    if action == "views":
        views = args.get("views") or ["front", "right", "top", "iso"]
        if len(views) > PICTURES_AT_ONCE:
            return _err(f"at most {PICTURES_AT_ONCE} views at once")
        cmd = ["views", str(folder), "--views", ",".join(views), *limit]
        res = run(cmd, folder, timeout)
        if res.get("ok"):
            _saw(folder)
        return _answer(ctx, cmd, root, res, [Path(p) for p in res.get("pictures", [])])
    fmt = args.get("format")  # export
    if fmt not in FORMATS:
        return _err(f"export needs format: {', '.join(FORMATS)}")
    if not _seen(folder):
        return _err(NOT_SEEN)
    cmd = ["export", str(folder), "--format", fmt, "--force", *limit]
    return _answer(ctx, cmd, root, run(cmd, folder, timeout))


def result_picture(root, since: float = 0) -> Path | None:
    """The picture the team made in this project: the newest final, else the newest render, since a moment."""
    found: list[tuple[float, Path]] = []
    for base, dirs, files in os.walk(root):
        rel = Path(base).relative_to(root)
        if len(rel.parts) > 3:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", "__pycache__", "frames", "turn")]
        if rel.name == "out":
            for name, rank in (("final.png", 1), ("latest.png", 0)):
                if name in files:
                    path = Path(base) / name
                    when = path.stat().st_mtime
                    if when >= since:
                        found.append((rank, when, path))
    return max(found)[2] if found else None


PATH = {"type": "string", "minLength": 1, "maxLength": 500}
MODEL3D_TOOLS = [
    Tool("code3d_project", "3D (Code3D): read a project. action=schema gives the c3d kit and the project's fields: read it before you "
                           "write a scene. check tests scene.py's syntax and kit names without running it. look shows the last "
                           "render, or `picture` (a .png in the project). `project` is the project's folder.",
         _obj({"action": {"enum": ["schema", "check", "look"]}, "project": PATH, "picture": PATH}, ["action"]), code3d_project),
    Tool("code3d_run", "3D (Code3D): run the project's scene.py in Blender, in the background. init: new project folder (width, height, "
                       "fps, samples). objects: what is in the scene, sizes in metres, polygons. render: one picture you then see, with "
                       "measured notes on it (view; quality=check takes seconds and is what you work with, draft is a better look, "
                       "final is the full size and samples, once, at the end; frame for animation). views: up to 4 sides at once. "
                       "export: a model file (format). final and export are refused until this version of the scene has been "
                       "rendered and looked at. Errors give the line of scene.py. Write scene.py with your file tools.",
         _obj({"action": {"enum": list(RUN_ACTIONS)}, "project": PATH, "view": {"enum": list(VIEWS)}, "quality": {"enum": ["check", "draft", "final"]},
               "views": {"type": "array", "items": {"enum": list(VIEWS)}, "maxItems": PICTURES_AT_ONCE}, "format": {"enum": list(FORMATS)},
               "frame": {"type": "integer", "minimum": 0}, "width": {"type": "integer", "minimum": 16, "maximum": 7680},
               "height": {"type": "integer", "minimum": 16, "maximum": 4320}, "fps": {"type": "integer", "minimum": 1, "maximum": 120},
               "samples": {"type": "integer", "minimum": 1, "maximum": 4096},
               "timeout_s": {"type": "integer", "minimum": 30, "maximum": 86400}}, ["action", "project"]),
         code3d_run, effect_class="external", retry_safe=False),
]
for _t in MODEL3D_TOOLS:
    TOOLS[_t.name] = _t
NAMES = tuple(t.name for t in MODEL3D_TOOLS)
