"""What a plugin is made of. A plugin is one file in plugins/: it says what it asks for and what it does, and the window, the command line and
Lumen's agents all follow from that, so that adding one touches nothing else.

    PLUGIN = Plugin('qr', '二维码', '创作', '把文字或网址做成二维码', [
        Action('make', '生成', [Field('text', '内容', 'area')], make, sample={'text': 'hello'}),
    ])

    def make(a, out):            # a: what was filled in; out: a folder for results
        ...
        return done('做好了', files=[path], pictures=[path], table=[['甲', 1]])

sample is real input: `codetools check` runs every action of every plugin on it, so that none can ship without having run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


class Stop(Exception):
    """Something the person can fix, in words."""


@dataclass
class Field:
    key: str
    label: str
    kind: str = 'text'    # text, area, number, file, folder, choice, check
    value: object = ''
    choices: tuple = ()
    hint: str = ''


@dataclass
class Action:
    key: str
    label: str
    fields: list
    run: Callable
    sample: dict = field(default_factory=dict)
    changes: bool = False   # touches the person's own files: the window asks first


@dataclass
class Plugin:
    id: str
    name: str
    group: str
    blurb: str
    actions: list


def done(*lines, files=(), pictures=(), table=None, warnings=(), **more) -> dict:
    return {'ok': True, 'lines': [str(x) for x in lines], 'files': [str(f) for f in files], 'pictures': [str(p) for p in pictures], 'table': table or [], 'warnings': list(warnings), **more}


def need(a: dict, key: str, label: str = ''):
    value = a.get(key)
    if value in (None, ''):
        raise Stop(f'要填 {label or key}')
    return value


def number(a: dict, key: str, default: float) -> float:
    value = a.get(key, default)
    if value in (None, ''):
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise Stop(f'{key} 要是数字：{value}') from e


def path_of(a: dict, key: str, must_exist: bool = True) -> Path:
    p = Path(str(need(a, key))).expanduser()
    if must_exist and not p.exists():
        raise Stop(f'没有这个：{p}')
    return p


def font(size: int, bold: bool = False):
    from PIL import ImageFont

    wide = ('C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/msyh.ttc') if bold else ('C:/Windows/Fonts/msyh.ttc',)
    for path in (*wide, '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/Library/Fonts/Arial Unicode.ttf'):  # Windows, then macOS
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def human(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'
