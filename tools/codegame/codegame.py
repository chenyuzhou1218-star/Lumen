"""CodeGame's command line: 3D games written as one JavaScript file, built into one web page that runs anywhere.

    codegame init <folder>      a new game
    codegame schema             the guide and the engine's calls
    codegame check <folder>     is game.js written correctly
    codegame build <folder>     out/index.html, with the engine and every asset inside it: double-click to play
    codegame play <folder>      a machine player: starts the game in Edge or Chrome, presses keys, takes pictures, reports what happened

A project is a folder: project.json, game.js, assets/ (GLB models from Code3D, WAV sounds from CodeSound, pictures).
Every command prints one JSON object as its last line.
"""
from __future__ import annotations

import right_python

right_python.use('playwright', 'PIL')

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
KIT = ROOT / 'kit'
SETTINGS = {'name': '', 'script': 'game.js', 'title': ''}
STARTER = (ROOT / 'examples' / 'crystal_valley' / 'game.js')
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
DEFAULT_PLAY = [{'keys': [], 'seconds': 1, 'look': 'start'}, {'keys': ['KeyW'], 'seconds': 2}, {'keys': ['KeyD'], 'seconds': 1}, {'keys': ['Space'], 'seconds': .4},
                {'keys': ['KeyW', 'KeyA'], 'seconds': 2, 'look': 'moved'}]
KEY_NAMES = {'KeyW': 'w', 'KeyA': 'a', 'KeyS': 's', 'KeyD': 'd', 'KeyR': 'r', 'KeyE': 'e', 'KeyF': 'f', 'KeyQ': 'q', 'Space': 'Space', 'ArrowUp': 'ArrowUp', 'ArrowDown': 'ArrowDown',
             'ArrowLeft': 'ArrowLeft', 'ArrowRight': 'ArrowRight', 'Enter': 'Enter', 'ShiftLeft': 'Shift'}
MOST_ASSETS_MB = 60


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
        raise Stop(f'{folder} 不是 CodeGame 项目：先运行 init')
    return folder


def load(folder: Path) -> dict:
    try:
        return {**SETTINGS, **json.loads((folder / 'project.json').read_text(encoding='utf-8-sig'))}
    except (OSError, ValueError) as e:
        raise Stop(f'读不了 project.json：{e}') from e


def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'project.json').exists():
        raise Stop(f'{folder} 已经是项目了')
    (folder / 'assets').mkdir(parents=True, exist_ok=True)
    (folder / 'project.json').write_text(json.dumps({**SETTINGS, 'name': folder.name, 'title': folder.name}, ensure_ascii=False, indent=2), encoding='utf-8')
    if not (folder / 'game.js').exists():
        shutil.copyfile(STARTER, folder / 'game.js')
    return {'ok': True, 'project': str(folder), 'script': 'game.js'}


def cmd_schema(_a) -> dict:
    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8')}


def cmd_check(a) -> dict:
    folder = folder_of(a.folder)
    path = folder / load(folder)['script']
    if not path.is_file():
        raise Stop(f'没有 {path.name}')
    node = shutil.which('node')
    if node is None:
        return {'ok': True, 'lines': len(path.read_text(encoding='utf-8').splitlines()), 'warnings': ['没有 Node，只看了文件在不在；语法错误要到 play 才知道']}
    wrapped = folder / 'out' / '.check.mjs'  # await is allowed at the top of a game, as it runs inside an async function
    wrapped.parent.mkdir(exist_ok=True)
    wrapped.write_text('(async function () {\n' + path.read_text(encoding='utf-8-sig') + '\n}());\n', encoding='utf-8')
    res = subprocess.run([node, '--check', str(wrapped)], capture_output=True, creationflags=NO_WINDOW)
    wrapped.unlink(missing_ok=True)
    if res.returncode:
        text = res.stderr.decode('utf-8', 'replace')
        m = re.search(r':(\d+)\n', text)
        line = int(m.group(1)) - 1 if m else None
        return {'ok': False, 'error': next((x for x in text.splitlines() if 'Error' in x), text[:300]), **({'line': line} if line else {})}
    calls = sorted(set(re.findall(r'\bG\.(\w+)', path.read_text(encoding='utf-8'))))
    known = _engine_names()
    unknown = [c for c in calls if c not in known]
    if unknown:
        return {'ok': False, 'error': f'G 里没有这些：{", ".join(unknown)}'}
    return {'ok': True, 'lines': len(path.read_text(encoding='utf-8').splitlines())}


def _engine_names() -> set:
    text = (KIT / 'engine.js').read_text(encoding='utf-8')
    body = text[text.index('const G = {'):text.index("let seed = 12345")]
    return set(re.findall(r'^    (?:async )?(\w+)(?::|\(|,)', body, re.M))


def cmd_build(a) -> dict:
    folder = folder_of(a.folder)
    settings = load(folder)
    path = folder / settings['script']
    if not path.is_file():
        raise Stop(f'没有 {path.name}')
    assets = {}
    total = 0
    for f in sorted((folder / 'assets').rglob('*')) if (folder / 'assets').is_dir() else []:
        if f.is_file():
            total += f.stat().st_size
            if total > MOST_ASSETS_MB * 1024 * 1024:
                raise Stop(f'素材超过 {MOST_ASSETS_MB} MB，网页会太大')
            kind = 'model/gltf-binary' if f.suffix.lower() == '.glb' else mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
            assets[f.relative_to(folder / 'assets').as_posix()] = f'data:{kind};base64,{base64.b64encode(f.read_bytes()).decode("ascii")}'
    template = (KIT / 'page.html').read_text(encoding='utf-8')
    title = (settings.get('title') or settings.get('name') or folder.name).replace('<', '&lt;')
    # every anchor is filled in one pass: a title or a game that happens to contain {{engine}} must not be filled in again
    parts = {'title': title, 'assets': json.dumps(assets).replace('</', '<\\/'), 'engine': (KIT / 'engine.js').read_text(encoding='utf-8'),
             'game': path.read_text(encoding='utf-8-sig')}
    missing = [k for k in parts if '{{' + k + '}}' not in template]
    if missing:
        raise Stop('page.html 里找不到 ' + '、'.join('{{' + k + '}}' for k in missing))
    page = re.sub(r'\{\{(title|assets|engine|game)\}\}', lambda m: parts[m.group(1)], template)
    out = folder / 'out'
    out.mkdir(exist_ok=True)
    target = out / 'index.html'
    target.write_text(page, encoding='utf-8')
    return {'ok': True, 'output': 'out/index.html', 'size_mb': round(target.stat().st_size / 1048576, 2), 'assets': sorted(assets)}


def _browser(pw):
    for channel in ('msedge', 'chrome', None):
        try:
            # the software GL flag: WebGL also has to work where no graphics chip is offered to a headless browser
            return pw.chromium.launch(channel=channel, headless=True, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']) if channel else pw.chromium.launch(headless=True)
        except Exception:  # noqa: BLE001 (not installed: the next one)
            continue
    raise Stop('没有找到 Edge 或 Chrome，机器玩家开不了')


def cmd_play(a) -> dict:
    """Plays the built game by the steps [{'keys': ['KeyW'], 'seconds': 2, 'look': 'name'}]. Pictures are out/play_<name>.png."""
    folder = folder_of(a.folder)
    built = cmd_build(a)
    steps = json.loads(Path(a.steps).read_text(encoding='utf-8')) if a.steps else DEFAULT_PLAY
    if not isinstance(steps, list) or not steps:
        raise Stop('steps 要是一个列表')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise Stop('这个 Python 里没有 playwright') from e
    errors: list = []
    pictures: list = []
    log: list = []
    with sync_playwright() as pw:
        browser = _browser(pw)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 720})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
            page.goto((folder / 'out' / 'index.html').as_uri())
            page.wait_for_timeout(1200)
            for index, s in enumerate(steps):
                keys = [KEY_NAMES.get(k, k) for k in s.get('keys', [])]
                for k in keys:
                    page.keyboard.down(k)
                page.wait_for_timeout(int(float(s.get('seconds', 1)) * 1000))
                for k in keys:
                    page.keyboard.up(k)
                try:
                    report = page.evaluate('window.__report && window.__report()')
                except Exception as e:  # noqa: BLE001 (the page itself broke)
                    errors.append(str(e))
                    break
                if report:
                    log.append({'step': index + 1, 'keys': s.get('keys', []), 'player': report.get('player'), 'watched': report.get('watched'), 'ended': report.get('ended'), 'fps': report.get('fps')})
                if s.get('look'):
                    name = re.sub(r'[^\w-]', '_', str(s['look']))
                    path = folder / 'out' / f'play_{name}.png'
                    page.screenshot(path=str(path))
                    pictures.append(f'out/play_{name}.png')
            if not pictures:
                path = folder / 'out' / 'play_end.png'
                page.screenshot(path=str(path))
                pictures.append('out/play_end.png')
        finally:
            browser.close()
    return {'ok': not errors, 'built': built['output'], 'played': log, 'pictures': pictures, 'warnings': _notes(log, folder / pictures[-1]), **({'error': '；'.join(dict.fromkeys(errors))[:900]} if errors else {})}


def _notes(log: list, picture: Path) -> list:
    """Measured faults."""
    out = []
    if not log:
        return ['游戏没有开始：读不到它的状态。']
    bad = [r for r in log if r.get('player') and any(v != v for v in r['player']['pos'])]
    if bad:
        out.append('玩家的位置变成了 NaN：运动计算里除了零。')
    players = [r['player'] for r in log if r.get('player')]
    if players:
        if players[-1]['moved'] < .5:
            out.append('按了方向键，玩家几乎没动。')
        if players[-1]['pos'][1] < -30:
            out.append('玩家掉到世界下面去了。')
    else:
        out.append('没有 G.walker：机器玩家看不到玩家的位置。')
    fps = [r['fps'] for r in log if r.get('fps')]
    if fps and min(fps) < 12:
        out.append(f'最低 {min(fps)} 帧（这里是软件绘制，实际电脑会快一些）：东西太多就减少 cells 或物体数量。')
    try:
        from PIL import Image

        small = Image.open(picture).convert('L').resize((32, 18))
        data = list(small.tobytes())
        mean = sum(data) / len(data)
        spread = max(data) - min(data)
        if mean < 12:
            out.append('画面几乎全黑。')
        elif spread < 8:
            out.append('画面几乎是一个颜色：相机可能没对着东西。')
    except (ImportError, OSError):
        pass
    return out


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codegame')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('schema').set_defaults(fn=cmd_schema)
    for name, fn in (('init', cmd_init), ('check', cmd_check), ('build', cmd_build)):
        q = sub.add_parser(name)
        q.add_argument('folder')
        q.set_defaults(fn=fn)
    q = sub.add_parser('play')
    q.add_argument('folder')
    q.add_argument('--steps', help='a JSON file of steps')
    q.set_defaults(fn=cmd_play)
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
