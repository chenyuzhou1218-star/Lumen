"""Build builder/components.js: the hand-made components (core.json) and the families in families/, each in its looks.

    python library/make.py          write builder/components.js and say how many components there are

The window and the command line both read components.js; edit core.json or a family and run this again.
"""
from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kit  # noqa: E402
from parts import S  # noqa: E402

# The order of the groups on the left; a group the core already has gets the family's items after its own.
ORDER = [('layout', '布局'), ('nav', '导航栏'), ('hero', '首屏'), ('feature', '特点'), ('stat', '数字'), ('card', '卡片'),
         ('content', '图文'), ('media', '图片和视频'), ('proof', '评价'), ('team', '团队'), ('price', '价格表'), ('faq', '问答'),
         ('step', '步骤和时间线'), ('cta', '号召'), ('contact', '联系'), ('form', '表单'), ('search', '搜索栏'), ('play', '互动'),
         ('logo', '标志墙'), ('notice', '提示条'), ('text', '文字'), ('button', '按钮'), ('slides', '幻灯片'), ('more', '其他'),
         ('footer', '页脚')]


def items_of(s: S) -> list:
    """The structure in each of its looks. The first look carries the css; the others need it (one copy on a page)."""
    out = []
    for i, look in enumerate(s.looks):
        item = {'id': s.id + (f'-{look}' if look else ''), 'name': s.name + (f' · {kit.LOOK_NAMES[look]}' if look else ''),
                'html': s.html.replace('%K', f' g-k-{look}' if look else ''), 'fields': s.fields, 'look': look or 'plain'}
        if i == 0:
            item['css'] = s.css
            item['needs'] = s.needs or ('g-icons' if s.icons else 'g-core')
            if s.js:
                item['js'] = s.js
        else:
            item['needs'] = s.id + (f'-{s.looks[0]}' if s.looks[0] else '')
            if s.js:
                item['js'] = s.js
        if s.tags:
            item['tags'] = s.tags
        item.update(s.extra)
        out.append(item)
    return out


def families() -> tuple:
    """(structures, shared style sheets): a family's KIT is css its structures need once on a page."""
    found, kits = [], []
    pkg = HERE / 'families'
    for mod in sorted(pkgutil.iter_modules([str(pkg)]), key=lambda m: m.name):
        m = importlib.import_module(f'families.{mod.name}')
        found += m.ITEMS
        kits += getattr(m, 'KIT', [])
    return found, kits


def build() -> dict:
    lib = json.loads((HERE / 'core.json').read_text(encoding='utf-8'))
    lib['placeholders'].update(kit.PICTURES)
    lib['base'] = lib['base'] + kit.ANIM_CSS
    lib['anim_js'] = kit.ANIM_JS
    cats = {c['id']: c for c in lib['categories']}
    for cid, name in ORDER:
        cats.setdefault(cid, {'id': cid, 'name': name, 'items': []})
    seen = {i['id'] for c in lib['categories'] for i in c['items']}
    structures, kits = families()
    for s in structures:
        if s.cat not in cats:
            raise SystemExit(f'{s.id}: no group {s.cat}')
        for item in items_of(s):
            if item['id'] in seen:
                raise SystemExit(f'two components called {item["id"]}')
            seen.add(item['id'])
            cats[s.cat]['items'].append(item)
    hidden = {'id': '_kit', 'name': '', 'hidden': True, 'items': [
        {'id': 'g-core', 'name': '', 'html': '', 'css': kit.CORE_CSS, 'fields': []},
        {'id': 'g-icons', 'name': '', 'html': '', 'css': kit.ICON_CSS, 'fields': [], 'needs': 'g-core'}]
        + [{'name': '', 'html': '', 'fields': [], **k} for k in kits]}
    order = [cid for cid, _ in ORDER] + [c for c in cats if c not in dict(ORDER)]
    lib['categories'] = [cats[c] for c in order if cats[c]['items']] + [hidden]
    return lib


def main() -> None:
    lib = build()
    text = 'window.CP_COMPONENTS =\r\n' + json.dumps(lib, ensure_ascii=False, separators=(',', ':')) + ';\r\n'
    (HERE.parent / 'builder' / 'components.js').write_text(text, encoding='utf-8', newline='')
    shown = [i for c in lib['categories'] if not c.get('hidden') for i in c['items']]
    print(json.dumps({'ok': True, 'components': len(shown), 'groups': {c['name']: len(c['items']) for c in lib['categories'] if not c.get('hidden')},
                      'size_kb': round(len(text.encode('utf-8')) / 1024)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
