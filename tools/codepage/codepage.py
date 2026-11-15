"""CodePage's command line: a web page as data. The window is for dragging; this is for the AI, and both use page.json.

    codepage init <folder>                 a new page
    codepage schema                        the guide, every component and its fields, the themes
    codepage check <folder>                is page.json right (names, fields)
    codepage build <folder> [--pictures]   out/index.html, and pictures at computer and phone width

Every command prints one JSON object as its last line.
"""
from __future__ import annotations

import right_python

right_python.use('playwright')

import argparse
import html as htmllib
import json
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parent
# one file for the page and for Python: a browser opening the builder from disk may not fetch a .json next to it
LIB = json.loads((ROOT / 'builder' / 'components.js').read_text(encoding='utf-8').removeprefix('window.CP_COMPONENTS =').rstrip().rstrip(';'))
BY_ID = {item['id']: item for cat in LIB['categories'] for item in cat['items']}
KIT = {item['id'] for cat in LIB['categories'] if cat.get('hidden') for item in cat['items']}  # shared css, not components


class Stop(Exception):
    """An answer with ok:false."""


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def blank(name: str) -> dict:
    return {'title': name, 'lang': 'zh-CN', 'description': '', 'theme': {**LIB['themes'][0], 'radius': 10, 'font': LIB['fonts'][0]['css']}, 'blocks': []}


def load(folder: Path) -> dict:
    try:
        data = json.loads((folder / 'page.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        raise Stop(f'读不了 {folder / "page.json"}：{e}') from e
    if not isinstance(data.get('blocks'), list):
        raise Stop('page.json 里要有 blocks 列表')
    base = blank(folder.name)
    return {**base, **data, 'theme': {**base['theme'], **(data.get('theme') or {})}}


def walk(nodes: list):
    for n in nodes:
        yield n
        for inner in n.get('children') or []:
            yield from walk(inner)


def problems(page: dict) -> list:
    out = []
    seen = set()
    for n in walk(page['blocks']):
        kind = n.get('type')
        if kind not in BY_ID or kind in KIT:
            out.append(f'没有 {kind} 这个组件')
            continue
        item = BY_ID[kind]
        if n.get('id') in seen:
            out.append(f'id 重复：{n.get("id")}')
        seen.add(n.get('id'))
        keys = {f['key'] for f in item.get('fields', [])}
        for key in n.get('values') or {}:
            if key not in keys:
                out.append(f'{kind} 没有 {key} 这一项（有：{", ".join(sorted(keys)) or "没有"}）')
        if item.get('slides'):
            if not n.get('children'):
                out.append(f'{kind} 至少要有一页（children 里放一个列表）')
        elif item.get('slots') and len(n.get('children') or []) > item['slots']:
            out.append(f'{kind} 只有 {item["slots"]} 栏')
        if not item.get('slots') and not item.get('slides') and n.get('children'):
            out.append(f'{kind} 里面不能放别的组件')
    return out


# --- the same steps as builder/render.js ------------------------------------------------------------------------------

def esc(text) -> str:
    return htmllib.escape('' if text is None else str(text), quote=True).replace('&#x27;', '&#39;')


def value_of(text) -> str:
    value = '' if text is None else str(text)
    return LIB['placeholders'].get(value, value) if value.startswith('@') else value


def fill(template: str, values: dict, raw: bool) -> str:
    def repeat(m):
        out = []
        for line in str(values.get(m.group(1)) or '').split('\n'):
            if line.strip():
                parts = [p.strip() for p in line.split('|')]
                out.append(re.sub(r'\{\{(\d)\}\}', lambda k: esc(value_of(parts[int(k.group(1)) - 1] if int(k.group(1)) <= len(parts) else '')), m.group(2)))
        return ''.join(out)

    text = re.sub(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', repeat, template, flags=re.S)

    def either(m):  # {{url/mailto:email}}: the first that has a value, with what stands before its ':' put in front
        for alt in m.group(1).split('/'):
            prefix, _, key = alt.rpartition(':')
            if str(values.get(key) or '').strip():
                return esc(prefix + (':' if prefix else '') + str(value_of(values.get(key))))
        return ''

    text = re.sub(r'\{\{([\w:]+(?:/[\w:]+)+)\}\}', either, text)
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(values.get(m.group(1)) or '') if raw else esc(value_of(values.get(m.group(1)))), text)


def _num(value) -> float:
    """A number from the page file; a word where a number belongs counts as 0 instead of stopping the export."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def style_of(s: dict) -> str:
    s = s or {}
    out = []
    for name, key in (('padding-top', 'padTop'), ('padding-bottom', 'padBottom'), ('margin-top', 'marginTop'), ('margin-bottom', 'marginBottom'), ('min-height', 'minHeight'), ('border-radius', 'radius')):
        if s.get(key) not in (None, ''):
            out.append(f'{name}:{_num(s[key]):g}px')
    if s.get('bg'):
        out.append(f"background:{s['bg']}")
    if s.get('color'):
        out.append(f"color:{s['color']}")
    if s.get('align'):
        out.append(f"text-align:{s['align']}")
    if s.get('width') and _num(s['width']) < 100:
        out.append(f"width:{_num(s['width']):g}%")
        out.append('margin-left:auto' if s.get('align') == 'right' else 'margin-right:auto' if s.get('align') == 'left' else 'margin-left:auto;margin-right:auto')
    if s.get('shadow'):
        out.append('box-shadow:0 10px 28px rgba(0,0,0,.14)')
    if VALIGN.get(s.get('valign')):  # a block made taller than what is in it: where its content sits
        out.append(f"display:flex;flex-direction:column;justify-content:{VALIGN[s['valign']]}")
    return esc(';'.join(out))


VALIGN = {'center': 'center', 'bottom': 'flex-end'}
ANIMS = ('up', 'fade', 'zoom', 'left', 'right')


def anim_of(n: dict) -> str:
    a = (n.get('style') or {}).get('anim')
    return f' cp-anim cp-anim-{a}' if a in ANIMS else ''


def node_html(n: dict) -> str:
    item = BY_ID[n['type']]
    values = {**{f['key']: f.get('value', '') for f in item.get('fields', [])}, **(n.get('values') or {})}
    text = fill(item['html'], values, bool(item.get('raw')))
    children = n.get('children') or []

    def slot(index: int) -> str:
        kids = ''.join(node_html(k) for k in (children[index] if index < len(children) else []))
        return f'<div class="cp-slot">{kids}</div>'

    text = re.sub(r'\{\{slot:(\d)\}\}', lambda m: slot(int(m.group(1))), text)
    # a deck of slides: one slide for each list of children, as many as there are
    text = text.replace('{{slot:*}}',''.join(f'<section class="cp-slide">{slot(i)}</section>' for i in range(len(children))))
    style = style_of(n.get('style'))
    return f'<div class="cp-block{anim_of(n)}"{f" style={chr(34)}{style}{chr(34)}" if style else ""}>{text}</div>'


def _on(color) -> str:
    """White or near-black text, whichever reads on this colour (the same as on() in builder/render.js)."""
    m = re.fullmatch(r'#?([0-9a-fA-F]{6})', str(color or '').strip())
    if not m:
        return '#fff'
    r, g, b = [int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in (r, g, b)]
    return '#111' if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 else '#fff'


def css_of(page: dict) -> tuple:
    seen, css, scripts = set(), [], []

    def add(key):
        if key in seen or key not in BY_ID:
            return
        seen.add(key)
        if BY_ID[key].get('needs'):
            add(BY_ID[key]['needs'])
        if BY_ID[key].get('css'):
            css.append(BY_ID[key]['css'])

    moving = False
    for n in walk(page['blocks']):
        add(n['type'])
        js = BY_ID[n['type']].get('js')
        if js and js not in scripts:
            scripts.append(js)
        moving = moving or bool(anim_of(n))
    if moving and LIB.get('anim_js'):
        scripts.append(LIB['anim_js'])
    t = page['theme']
    root = (f":root{{--cp-on-primary:{_on(t['primary'])};--cp-primary:{t['primary']};--cp-bg:{t['bg']};--cp-ink:{t['ink']};--cp-soft:{t['soft']};--cp-line:{t['line']};"
            f"--cp-radius:{float(t.get('radius', 10)):g}px;--cp-font:{t['font']}}}")
    return '\n'.join([root, LIB['base'], *css]), scripts


def document(page: dict) -> str:
    css, scripts = css_of(page)
    body = '\n'.join(node_html(n) for n in page['blocks'])
    js = ('\n<script>\n' + '\n'.join(scripts) + '\n</script>') if scripts else ''
    note = f'\n<meta name="description" content="{esc(page["description"])}">' if page.get('description') else ''
    return f'''<!doctype html>
<html lang="{esc(page.get('lang') or 'zh-CN')}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page.get('title'))}</title>{note}
<style>
{css}
</style>
</head>
<body>
{body}{js}
</body>
</html>
'''


# --- commands -----------------------------------------------------------------------------------------------------------

def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'page.json').exists():
        raise Stop(f'{folder} 已经有 page.json 了')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'page.json').write_text(json.dumps(blank(folder.name), ensure_ascii=False, indent=1), encoding='utf-8')
    return {'ok': True, 'project': str(folder)}


def cmd_schema(_a) -> dict:
    parts = []
    for cat in LIB['categories']:
        if cat.get('hidden'):  # shared style sheets, not something to put on a page
            continue
        for item in cat['items']:
            part = {'type': item['id'], 'group': cat['name'], 'name': item['name'], 'columns': item.get('slots', 0),
                    'fields': {f['key']: f['label'] for f in item.get('fields', [])}}
            if item.get('slides'):
                part['slides'] = '每一页是 children 里的一个列表，页数不限；页里放“幻灯片”组里的 sl-* 组件最合适'
            parts.append(part)
    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8'), 'components': parts, 'themes': LIB['themes'], 'fonts': LIB['fonts'],
            'new_id_example': 'n' + secrets.token_hex(3)}


def cmd_check(a) -> dict:
    page = load(Path(a.folder).resolve())
    found = problems(page)
    return {'ok': not found, 'blocks': len(list(walk(page['blocks']))), **({'error': '；'.join(found[:12])} if found else {})}


def cmd_build(a) -> dict:
    folder = Path(a.folder).resolve()
    page = load(folder)
    found = problems(page)
    if found:
        raise Stop('；'.join(found[:12]))
    out = folder / 'out'
    out.mkdir(exist_ok=True)
    target = out / 'index.html'
    target.write_text(document(page), encoding='utf-8')
    answer = {'ok': True, 'output': 'out/index.html', 'blocks': len(list(walk(page['blocks']))), 'size_kb': round(target.stat().st_size / 1024, 1), 'pictures': []}
    if a.pictures:
        from kit_shot import shots

        try:
            res = shots(target, [(out / 'desktop.png', 1280, 800), (out / 'phone.png', 390, 800)])
        except Exception as e:  # noqa: BLE001 (the browser can fail in many ways; the page is made, only the pictures are missing)
            answer['warnings'] = [f'{type(e).__name__}: {e}']
            return answer
        answer['pictures'] = ['out/desktop.png', 'out/phone.png']
        if res['errors']:
            answer['warnings'] = res['errors']
    return answer


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codepage')
    sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('init')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_init)
    sub.add_parser('schema').set_defaults(fn=cmd_schema)
    q = sub.add_parser('check')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_check)
    q = sub.add_parser('build')
    q.add_argument('folder')
    q.add_argument('--pictures', action='store_true')
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
