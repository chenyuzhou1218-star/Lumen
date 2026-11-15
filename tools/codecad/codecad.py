"""CodeCAD's command line: real parts with real dimensions, written as code, cut by the user's own Blender, ready to 3D print.

    codecad init <folder>       a new part
    codecad schema              the guide and the kit
    codecad check <folder>      is part.py written correctly (does not run it)
    codecad build <folder>      makes each part, measures it, writes its STL and a picture

A project is a folder: project.json, part.py, out/. Every command prints one JSON object as its last line.
"""
from __future__ import annotations

import right_python

right_python.use('PIL')

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
KIT = ROOT / 'kit'
SETTINGS = {'name': '', 'script': 'part.py', 'printer': [220, 220, 250], 'max_seconds': 600}
STARTER = '''"""Lengths are millimetres, Z is up. Build on z = 0 when it is to be printed."""
import cad

plate = cad.rounded_plate(60, 40, 5, 4).at(0, 0, 2.5)
for x in (-22, 22):
    plate = plate - cad.screw_hole('M3').at(x, 0, 5)

cad.part('plate', plate, x=60, y=40, z=5)
'''
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
LOW_PRIORITY = 0x00004000 if os.name == 'nt' else 0


class Stop(Exception):
    """An answer with ok:false."""


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def folder_of(text: str) -> Path:
    folder = Path(text).resolve()
    if not (folder / 'project.json').is_file():
        raise Stop(f'{folder} 不是 CodeCAD 项目：先运行 init')
    return folder


def load(folder: Path) -> dict:
    try:
        return {**SETTINGS, **json.loads((folder / 'project.json').read_text(encoding='utf-8-sig'))}
    except (OSError, ValueError) as e:
        raise Stop(f'读不了 project.json：{e}') from e


def find_blender() -> Path | None:
    """The Blender Code3D already found: it knows where the user's copy is. CodeCAD downloads nothing."""
    code3d = ROOT.parent / 'code3d'
    if (code3d / 'code3d.py').is_file():
        sys.path.insert(0, str(code3d))
        try:
            import code3d as other

            return other.find_blender()
        finally:
            sys.path.remove(str(code3d))
    env = os.environ.get('CODE3D_BLENDER')
    return Path(env) if env and Path(env).is_file() else None


def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'project.json').exists():
        raise Stop(f'{folder} 已经是项目了')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'project.json').write_text(json.dumps({**SETTINGS, 'name': folder.name}, ensure_ascii=False, indent=2), encoding='utf-8')
    if not (folder / 'part.py').exists():
        (folder / 'part.py').write_text(STARTER, encoding='utf-8')
    return {'ok': True, 'project': str(folder), 'script': 'part.py'}


def _kit_calls() -> list:
    tree = ast.parse((KIT / 'cad.py').read_text(encoding='utf-8'))
    out = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            out.append({'call': f'cad.{node.name}({ast.unparse(node.args)})', 'doc': ast.get_docstring(node) or ''})
        if isinstance(node, ast.ClassDef) and node.name == 'Shape':
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                    out.append({'call': f'shape.{item.name}({ast.unparse(item.args).removeprefix("self, ").removeprefix("self")})', 'doc': ast.get_docstring(item) or ''})
    return out


def cmd_schema(_a) -> dict:
    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8'), 'cad': _kit_calls()}


def cmd_check(a) -> dict:
    folder = folder_of(a.folder)
    path = folder / load(folder)['script']
    if not path.is_file():
        raise Stop(f'没有 {path.name}')
    source = path.read_text(encoding='utf-8-sig')
    try:
        tree = compile(source, str(path), 'exec', ast.PyCF_ONLY_AST)
    except SyntaxError as e:
        return {'ok': False, 'error': f'第 {e.lineno} 行语法错误：{e.msg}', 'line': e.lineno}
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == 'cad'}
    known = {c['call'].split('(')[0][4:] for c in _kit_calls() if c['call'].startswith('cad.')}
    unknown = sorted(called - known)
    if unknown:
        return {'ok': False, 'error': f'cad 里没有这些：{", ".join(unknown)}'}
    return {'ok': True, 'lines': len(source.splitlines()), 'blender': bool(find_blender())}


def cmd_build(a) -> dict:
    folder = folder_of(a.folder)
    settings = load(folder)
    exe = find_blender()
    if exe is None:
        raise Stop('没有找到 Blender：CodeCAD 用它来切割和测量。')
    with tempfile.TemporaryDirectory(prefix='codecad-') as tmp:
        result = Path(tmp) / 'result.json'
        job = Path(tmp) / 'job.json'
        job.write_text(json.dumps({'kit': str(KIT), 'project': str(folder), 'script': settings['script'], 'result': str(result), 'printer': settings['printer'], 'picture': not a.no_picture}, ensure_ascii=False), encoding='utf-8')
        cmd = [str(exe), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '9', '--python', str(KIT / 'runner.py'), '--', str(job)]
        try:
            res = subprocess.run(cmd, cwd=str(folder), capture_output=True, timeout=a.timeout or settings['max_seconds'], creationflags=NO_WINDOW | LOW_PRIORITY)
        except subprocess.TimeoutExpired as e:
            raise Stop('Blender 没有在时间内做完：减少布尔运算次数，或者 cad.segments(48)') from e
        if result.is_file():
            return json.loads(result.read_text(encoding='utf-8'))
        raise Stop('Blender 没有给出结果：' + res.stdout.decode('utf-8', 'replace')[-900:])


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codecad')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('schema').set_defaults(fn=cmd_schema)
    for name, fn in (('init', cmd_init), ('check', cmd_check)):
        q = sub.add_parser(name)
        q.add_argument('folder')
        q.set_defaults(fn=fn)
    q = sub.add_parser('build')
    q.add_argument('folder')
    q.add_argument('--no-picture', action='store_true')
    q.add_argument('--timeout', type=float, default=0)
    q.set_defaults(fn=cmd_build)
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
