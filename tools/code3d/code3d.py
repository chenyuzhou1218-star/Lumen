"""Code3D's command line: 3D scenes written as code, built and rendered by the user's own Blender.

Every command prints one JSON object as its last line ({"ok": true, ...} or {"ok": false, "error": ...}), so a result is
a fact, not a guess from a picture. A project is a folder: project.json (settings), scene.py (the scene), out/ (results).
Blender never opens a window for this, and it runs at low priority with one core left free, so it can work behind a game.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent
KIT = ROOT / 'kit'
STATE = Path(os.environ.get('CODE3D_STATE') or ROOT / 'state')
SETTINGS = {'name': '', 'script': 'scene.py', 'width': 1280, 'height': 720, 'fps': 24, 'frame_start': 1, 'frame_end': 1,
            'samples': 96, 'engine': 'cycles', 'max_seconds': 300}
VIEWS = ('camera', 'front', 'back', 'left', 'right', 'top', 'iso')
FORMATS = {'glb': '.glb', 'fbx': '.fbx', 'obj': '.obj', 'stl': '.stl', 'usd': '.usdc', 'blend': '.blend'}
STARTER = '''"""Everything in this file runs in Blender. Lengths are metres; c3d is the kit, bpy is all of Blender."""
import c3d

c3d.sky(sun_height=32, sun_turn=150)
c3d.ground(mat='concrete')

c3d.sphere(.5, at=(0, 0, .5), mat='gold')
c3d.box((.6, .6, .1), at=(1.1, -.2, .05), rot=(0, 0, 25), mat='wood')

c3d.camera(at=(3.2, -3.6, 1.5), look=(.3, 0, .4), lens=50)
'''
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
LOW_PRIORITY = 0x00004000 if os.name == 'nt' else 0  # BELOW_NORMAL: the game and the training jobs come first


class Stop(Exception):
    """An answer with ok:false."""


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _shortcut_targets() -> list[Path]:
    """Where the Start menu's Blender shortcuts point: the install follows the user, the registry may not."""
    if os.name != 'nt':
        return []
    script = ("$s=New-Object -ComObject WScript.Shell;"
              "foreach($p in @($env:APPDATA,$env:ProgramData)){"
              "Get-ChildItem -Path (Join-Path $p 'Microsoft\\Windows\\Start Menu\\Programs') -Recurse -Filter '*Blender*.lnk' "
              "-ErrorAction SilentlyContinue|ForEach-Object{$s.CreateShortcut($_.FullName).TargetPath}}")
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, timeout=20,
                             creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [Path(line.strip()) for line in out.stdout.decode('utf-8', 'replace').splitlines() + out.stdout.decode('mbcs' if os.name == 'nt' else 'utf-8', 'replace').splitlines() if line.strip()]


def _registry_places() -> list[Path]:
    if os.name != 'nt':
        return []
    import winreg

    found = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            base = winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(base)[0]):
            try:
                with winreg.OpenKey(base, winreg.EnumKey(base, i)) as k:
                    if 'blender' in str(winreg.QueryValueEx(k, 'DisplayName')[0]).lower():
                        found.append(Path(winreg.QueryValueEx(k, 'InstallLocation')[0]))
            except OSError:
                continue
    return found


def _usable(path) -> Path | None:
    if not path:
        return None
    p = Path(path)
    if p.suffix == '.app':  # macOS: Blender.app
        p = p / 'Contents' / 'MacOS' / 'Blender'
    elif p.is_dir():
        p = p / ('blender.exe' if os.name == 'nt' else 'blender')
    elif p.name.lower() == 'blender-launcher.exe':
        p = p.with_name('blender.exe')
    return p if p.is_file() and p.name.lower().startswith('blender') else None


def find_blender(refresh: bool = False) -> Path | None:
    """The user's Blender. $CODE3D_BLENDER, the one chosen before, then what the machine says. Never downloads anything."""
    if _usable(os.environ.get('CODE3D_BLENDER')):
        return _usable(os.environ['CODE3D_BLENDER'])
    saved = STATE / 'blender.txt'
    if not refresh and saved.is_file():
        p = _usable(saved.read_text(encoding='utf-8').strip())
        if p:
            return p
    candidates = [*_shortcut_targets(), *_registry_places()]
    for base in (os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')):
        if base:
            candidates += sorted(Path(base).glob('Blender Foundation/*'), reverse=True)
    candidates += [Path('/Applications/Blender.app'), Path.home() / 'Applications' / 'Blender.app', shutil.which('blender')]  # macOS, Linux
    for c in candidates:
        p = _usable(c)
        if p:
            remember_blender(p)
            return p
    return None


def remember_blender(path) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / 'blender.txt').write_text(str(path), encoding='utf-8')


def blender_or_stop() -> Path:
    b = find_blender()
    if b is None:
        raise Stop('没有找到 Blender。装好后重试，或把 Blender 的路径（Windows 是 blender.exe，Mac 是 Blender.app）写进环境变量 CODE3D_BLENDER。')
    return b


def tie_to_this_process(proc: subprocess.Popen) -> None:
    """If this process is killed (Stop in the window, a cancelled task), Blender goes with it."""
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [('a', ctypes.c_int64), ('b', ctypes.c_int64), ('LimitFlags', wintypes.DWORD), ('c', ctypes.c_size_t),
                    ('d', ctypes.c_size_t), ('e', wintypes.DWORD), ('f', ctypes.c_size_t), ('g', wintypes.DWORD), ('h', wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [('Basic', Basic), ('Io', ctypes.c_uint64 * 6), ('i', ctypes.c_size_t), ('j', ctypes.c_size_t),
                    ('k', ctypes.c_size_t), ('l', ctypes.c_size_t)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    info = Extended()
    info.Basic.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle)))
    tie_to_this_process.keep = job  # closed by Windows when this process ends


class Crashed(Stop):
    """Blender ended without an answer: not the scene's fault, a scene's errors come back as an answer."""


def blender(job: dict, folder: Path, timeout: float) -> dict:
    """One job for the runner inside Blender. It sometimes dies at once when the machine is short of memory: one more try."""
    try:
        return run_blender(job, folder, timeout)
    except Crashed:
        return run_blender(job, folder, timeout)


def run_blender(job: dict, folder: Path, timeout: float) -> dict:
    """One job for the runner inside Blender. Progress lines pass through; the answer comes back."""
    exe = blender_or_stop()
    with tempfile.TemporaryDirectory(prefix='code3d-') as tmp:
        jobfile, result = Path(tmp) / 'job.json', Path(tmp) / 'result.json'
        settings = load(folder)
        jobfile.write_text(json.dumps({'kit': str(KIT), 'project': str(folder), 'script': settings['script'], 'settings': settings,
                                       'result': str(result), **job}, ensure_ascii=False), encoding='utf-8')
        cmd = [str(exe), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '9',
               '--python', str(KIT / 'runner.py'), '--', str(jobfile)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(folder), creationflags=NO_WINDOW | LOW_PRIORITY)
        tie_to_this_process(proc)
        late = threading.Timer(timeout, proc.kill)
        late.start()
        tail: list[str] = []
        try:
            for raw in proc.stdout:
                line = raw.decode('utf-8', 'replace').rstrip()
                if line.startswith('C3D '):
                    print(line[4:], flush=True)
                elif line:
                    tail = (tail + [line])[-25:]
            proc.wait()
        finally:
            timed_out = not late.is_alive() and proc.returncode not in (0, None)
            late.cancel()
        if timed_out:
            raise Stop(f'Blender 在 {timeout:g} 秒内没有做完，已停止。可以加大时间，或降低采样、分辨率。')
        if result.is_file():
            return json.loads(result.read_text(encoding='utf-8'))
        raise Crashed('Blender 没有给出结果（退出码 %s）：%s' % (proc.returncode, '\n'.join(tail)[-1200:]))


def folder_of(path: str) -> Path:
    p = Path(path).resolve()
    return p.parent if p.is_file() else p


def load(folder: Path) -> dict:
    file = folder / 'project.json'
    if not file.is_file():
        raise Stop(f'{folder} 不是 Code3D 项目（没有 project.json）。先运行 init。')
    try:
        data = json.loads(file.read_text(encoding='utf-8-sig'))
    except ValueError as e:
        raise Stop(f'project.json 写错了：{e}') from None
    settings = {**SETTINGS, **data}
    settings['name'] = settings['name'] or folder.name
    for key, low, high in (('width', 16, 7680), ('height', 16, 4320), ('fps', 1, 120), ('samples', 1, 4096), ('max_seconds', 5, 86400), ('frame_start', 0, 100000),
                           ('frame_end', 0, 100000)):
        if not isinstance(settings[key], int) or not low <= settings[key] <= high:
            raise Stop(f'project.json：{key} 要在 {low} 到 {high} 之间')
    if settings['frame_end'] < settings['frame_start']:
        raise Stop('project.json：frame_end 不能小于 frame_start')
    if settings['engine'] not in ('cycles', 'eevee'):
        raise Stop('project.json：engine 只能是 cycles 或 eevee')
    script = (folder / settings['script']).resolve()
    if folder not in script.parents:
        raise Stop('project.json：script 要在项目文件夹里')
    return settings


def inside(folder: Path, path: str) -> Path:
    p = (folder / path).resolve()
    if p != folder and folder not in p.parents:
        raise Stop(f'{path} 不在项目文件夹里')
    return p


def latest(folder: Path, picture: Path, info: dict) -> None:
    """What the window shows next: it follows this file, whoever rendered."""
    if picture.is_file():
        shutil.copyfile(picture, folder / 'out' / 'latest.png')
        (folder / 'out' / 'latest.json').write_text(json.dumps({**info, 'at': time.time()}, ensure_ascii=False), encoding='utf-8')


def cmd_where(_a) -> dict:
    exe = blender_or_stop()
    out = subprocess.run([str(exe), '--version'], capture_output=True, timeout=60, creationflags=NO_WINDOW)
    first = out.stdout.decode('utf-8', 'replace').strip().splitlines()
    return {'ok': True, 'blender': str(exe), 'version': first[0] if first else ''}


def cmd_schema(_a) -> dict:
    """The kit's whole interface, read from its source, so it cannot go out of date."""
    tree = ast.parse((KIT / 'c3d.py').read_text(encoding='utf-8'))
    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            line = (KIT / 'c3d.py').read_text(encoding='utf-8').splitlines()[node.lineno - 1]
            args = ast.unparse(node.args)
            functions.append({'call': f'c3d.{node.name}({args})', 'does': ast.get_docstring(node)})
    guide = (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8') if (ROOT / 'AI_GUIDE.md').is_file() else ''
    return {'ok': True, 'guide': guide, 'project': {'project.json': {k: v for k, v in SETTINGS.items() if k != 'name'}, 'scene.py': 'Python run inside Blender; import c3d, import bpy'},
            'views': list(VIEWS), 'formats': list(FORMATS), 'rules': 'Lengths are metres, Z is up, colours are #rrggbb, angles are degrees. '
            'scene.py builds the scene and nothing else: no programs, no network, no files outside the project.',
            'c3d': functions}


def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'project.json').exists() and not a.force:
        raise Stop(f'{folder} 已经是项目了（要覆盖加 --force）')
    folder.mkdir(parents=True, exist_ok=True)
    settings = dict(SETTINGS, name=a.name or folder.name)
    for key in ('width', 'height', 'fps', 'samples'):
        if getattr(a, key):
            settings[key] = getattr(a, key)
    (folder / 'project.json').write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not (folder / 'scene.py').exists():
        (folder / 'scene.py').write_text(STARTER, encoding='utf-8')
    (folder / 'out').mkdir(exist_ok=True)
    return {'ok': True, 'project': str(folder), 'files': ['project.json', 'scene.py']}


def cmd_check(a) -> dict:
    """Is it written correctly? It does not run the scene, and needs no Blender."""
    folder = folder_of(a.folder)
    settings = load(folder)
    path = folder / settings['script']
    if not path.is_file():
        raise Stop(f'没有 {settings["script"]}')
    source = path.read_text(encoding='utf-8-sig')
    try:
        tree = compile(source, str(path), 'exec', ast.PyCF_ONLY_AST)
    except SyntaxError as e:
        return {'ok': False, 'error': f'第 {e.lineno} 行语法错误：{e.msg}', 'line': e.lineno}
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name) and n.func.value.id == 'c3d'}
    known = {f['call'].split('(')[0][4:] for f in cmd_schema(None)['c3d']}
    unknown = sorted(called - known)
    if unknown:
        return {'ok': False, 'error': f'c3d 里没有这些：{", ".join(unknown)}（schema 里有全部）'}
    return {'ok': True, 'project': settings, 'lines': len(source.splitlines()), 'blender': bool(find_blender())}


def cmd_objects(a) -> dict:
    return blender({'action': 'objects'}, folder_of(a.folder), a.timeout)


def cmd_render(a) -> dict:
    folder = folder_of(a.folder)
    default = 'final.png' if a.quality == 'final' and a.view == 'camera' else f'{a.view}.png'
    out = inside(folder, a.output or f'out/{default}')
    if a.output and out.exists() and not a.force:
        raise Stop(f'{a.output} 已经存在（要覆盖加 --force）')
    res = blender({'action': 'render', 'view': a.view, 'quality': a.quality, 'frame': a.frame, 'output': str(out)}, folder, a.timeout)
    if res.get('ok'):
        latest(folder, out, {'view': a.view, 'quality': a.quality, 'scene': res.get('scene')})
        res['warnings'] = [*res.get('warnings', []), *res.pop('notes', [])]
    return res


def cmd_views(a) -> dict:
    folder = folder_of(a.folder)
    views = a.views.split(',')
    if any(v not in VIEWS for v in views):
        raise Stop(f'视角只能是 {", ".join(VIEWS)}')
    res = blender({'action': 'views', 'views': views}, folder, a.timeout)
    if res.get('ok') and res['pictures']:
        latest(folder, Path(res['pictures'][-1]), {'view': views[-1], 'quality': 'draft'})
    return res


def cmd_turntable(a) -> dict:
    return blender({'action': 'turntable', 'count': a.count}, folder_of(a.folder), a.timeout)


def cmd_animate(a) -> dict:
    """Every frame as a picture, then one MP4 with CodeCut's ffmpeg when it is there."""
    folder = folder_of(a.folder)
    out = inside(folder, a.output or 'out/animation.mp4')
    if out.exists() and not a.force:
        raise Stop(f'{out.name} 已经存在（要覆盖加 --force）')
    res = blender({'action': 'animate', 'quality': a.quality}, folder, a.timeout)
    if not res.get('ok'):
        return res
    ffmpeg = next((p for p in (ROOT.parent / 'codecut' / 'tools' / 'ffmpeg.exe', shutil.which('ffmpeg')) if p and Path(p).is_file()), None)
    if ffmpeg is None:
        return {**res, 'warnings': [*res.get('warnings', []), '没有 ffmpeg：画面在 frames 文件夹里，没有合成 MP4。']}
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        done = subprocess.run([str(ffmpeg), '-y', '-framerate', str(res['fps']), '-i', str(Path(res['frames']) / '%05d.png'), '-vf',
                               'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', str(out)],
                              capture_output=True, creationflags=NO_WINDOW, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Stop(f'合成 MP4 失败：{type(e).__name__}: {e}') from e
    if done.returncode:
        raise Stop('合成 MP4 失败：' + done.stderr.decode('utf-8', 'replace')[-500:])
    return {**res, 'output': str(out), 'duration': round(res['count'] / res['fps'], 2)}


def cmd_export(a) -> dict:
    folder = folder_of(a.folder)
    if a.format not in FORMATS:
        raise Stop(f'格式只能是 {", ".join(FORMATS)}')
    out = inside(folder, a.output or f'out/{load(folder)["name"]}{FORMATS[a.format]}')
    if out.exists() and not a.force:
        raise Stop(f'{out.name} 已经存在（要覆盖加 --force）')
    return blender({'action': 'export', 'format': a.format, 'output': str(out)}, folder, a.timeout)


def cmd_open(a) -> dict:
    """The real scene in Blender's own window: full 3D view, every tool. Saved next to the project's other results."""
    folder = folder_of(a.folder)
    out = folder / 'out' / 'scene.blend'
    res = blender({'action': 'export', 'format': 'blend', 'output': str(out)}, folder, a.timeout)
    if res.get('ok'):
        subprocess.Popen([str(blender_or_stop()), '--disable-autoexec', str(out)], close_fds=True)
    return res


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='code3d', description='3D scenes written as code, built by Blender.')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('where', help='which Blender is used').set_defaults(fn=cmd_where)
    sub.add_parser('schema', help="the project's fields and the whole c3d kit").set_defaults(fn=cmd_schema)
    q = sub.add_parser('init', help='a new project folder')
    q.add_argument('folder')
    q.add_argument('--name')
    for key in ('width', 'height', 'fps', 'samples'):
        q.add_argument(f'--{key}', type=int)
    q.add_argument('--force', action='store_true')
    q.set_defaults(fn=cmd_init)
    q = sub.add_parser('check', help='syntax and kit names, without running the scene')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_check)

    def common(name, fn, helptext, minutes=30):
        q = sub.add_parser(name, help=helptext)
        q.add_argument('folder')
        q.add_argument('--timeout', type=float, default=minutes * 60)
        q.set_defaults(fn=fn)
        return q

    common('objects', cmd_objects, 'run the scene and list what is in it', 10)
    q = common('render', cmd_render, 'one picture')
    q.add_argument('--view', choices=VIEWS, default='camera')
    q.add_argument('--quality', choices=('check', 'draft', 'final'), default='draft')
    q.add_argument('--frame', type=int)
    q.add_argument('-o', '--output')
    q.add_argument('--force', action='store_true')
    q = common('views', cmd_views, 'several sides of the model, as drafts')
    q.add_argument('--views', default='front,right,top,iso')
    q = common('turntable', cmd_turntable, 'small pictures all the way round, for the window')
    q.add_argument('--count', type=int, default=12)
    q = common('animate', cmd_animate, 'every frame, then an MP4', 24 * 60)
    q.add_argument('--quality', choices=('draft', 'final'), default='draft')
    q.add_argument('-o', '--output')
    q.add_argument('--force', action='store_true')
    q = common('export', cmd_export, 'a model file')
    q.add_argument('--format', default='glb')
    q.add_argument('-o', '--output')
    q.add_argument('--force', action='store_true')
    common('open', cmd_open, "open the scene in Blender's own window", 10)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parser().parse_args(argv)
    try:
        answer = args.fn(args)
    except Stop as e:
        answer = {'ok': False, 'error': str(e)}
    except Exception as e:  # noqa: BLE001 (whatever else goes wrong still answers in JSON, so the window can say it)
        answer = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    say(answer)
    return 0 if answer.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
