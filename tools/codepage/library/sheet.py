"""Look at components the way people will: every one rendered by codepage.py, at computer and phone width, in pictures.

    python library/sheet.py <out folder> <id prefix or group id> [...] [--theme N] [--phone]

Writes sheet-*.png (cut into pieces a person can look at) and sheet.html. For checking the library while making it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codepage  # noqa: E402


def pick(words: list) -> list:
    out = []
    for cat in codepage.LIB['categories']:
        if cat.get('hidden'):
            continue
        for item in cat['items']:
            if any(item['id'] == w or item['id'].startswith(w + '-') or cat['id'] == w for w in words):
                out.append(item)
    return out


def page_of(items: list, theme: int) -> str:
    page = codepage.blank('sheet')
    page['theme'] = {**codepage.LIB['themes'][theme], 'radius': 10, 'font': codepage.LIB['fonts'][0]['css']}
    page['blocks'] = []
    for i, item in enumerate(items):
        node = {'id': f'n{i}', 'type': item['id'], 'values': {}, 'style': {}}
        if item.get('slides') or item.get('kids'):
            node['children'] = [[{'id': f'n{i}k{j}{k}', 'type': t, 'values': {}, 'style': {}} for k, t in enumerate(kid)] for j, kid in enumerate(item.get('kids') or [[]])]
        elif item.get('slots'):
            node['children'] = [[] for _ in range(item['slots'])]
        page['blocks'].append(node)
    html = codepage.document(page)
    start = html[:html.index('<body>') + 6]
    tail = html[html.rindex('\n<script>\n'):] if '\n<script>\n' in html else '\n</body>\n</html>\n'
    label = 'font:600 13px Segoe UI,sans-serif;background:#fffbe6;color:#5a4a00;padding:6px 12px;border-top:2px solid #f0d000'
    body = ''.join(f'<div style="{label}">{item["id"]} · {item["name"]}</div>{codepage.node_html(n)}' for item, n in zip(items, page['blocks']))
    return start + '\n' + body + tail


def main() -> None:
    args = sys.argv[1:]
    out = Path(args.pop(0))
    theme = 0
    if '--theme' in args:
        k = args.index('--theme')
        theme = int(args[k + 1])
        del args[k:k + 2]
    looks = None
    if '--look' in args:  # only these looks: --look plain,ink
        k = args.index('--look')
        looks = set(args[k + 1].split(','))
        del args[k:k + 2]
    phone = '--phone' in args
    args = [a for a in args if a != '--phone']
    items = [i for i in pick(args) if looks is None or i.get('look', 'plain') in looks]
    out.mkdir(parents=True, exist_ok=True)
    (out / 'sheet.html').write_text(page_of(items, theme), encoding='utf-8')
    from playwright.sync_api import sync_playwright
    from PIL import Image

    width = 390 if phone else 1280
    with sync_playwright() as p:
        b = p.chromium.launch(channel='msedge')
        pg = b.new_page(viewport={'width': width, 'height': 900})
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto((out / 'sheet.html').as_uri())
        pg.wait_for_timeout(400)
        over = pg.evaluate('document.documentElement.scrollWidth - innerWidth')
        height = pg.evaluate('document.documentElement.scrollHeight')
        step = 2600 if not phone else 2400
        names = []
        # in pieces: one picture of a very tall page repeats itself past about 16,000 pixels
        for k, y in enumerate(range(0, height, step)):
            name = out / f'sheet-{k + 1}.png'
            pg.screenshot(path=str(name), full_page=True, clip={'x': 0, 'y': y, 'width': width, 'height': min(step, height - y)})
            if not phone:
                im = Image.open(name)
                im.resize((im.width * 6 // 10, im.height * 6 // 10)).save(name)
            names.append(name.name)
        b.close()
    print(json.dumps({'items': len(items), 'pictures': names, 'overflow_px': over, 'errors': errors}, ensure_ascii=False))


if __name__ == '__main__':
    main()
