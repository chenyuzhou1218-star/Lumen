"""The page as the window draws it (builder/render.js, run by node) and as the command line writes it (codepage.py) must
be the same, character for character, for every component, every template and a deck of slides."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codepage  # noqa: E402

NODE = r"""
const fs = require('fs'), vm = require('vm');
const ctx = { window: {}, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2] + '/builder/components.js', 'utf8'), ctx);
vm.runInContext(fs.readFileSync(process.argv[2] + '/builder/render.js', 'utf8'), ctx);
ctx.cpLoad(ctx.window.CP_COMPONENTS);
const pages = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
fs.writeFileSync(process.argv[4], JSON.stringify(pages.map((p) => ctx.cpDocument(p))));
"""

counter = iter(range(10 ** 9))


def node_of(kind: str, style: dict | None = None) -> dict:
    """A block as the builder makes it: every field filled in, a deck with its slides."""
    item = codepage.BY_ID[kind]
    n = {'id': f'n{next(counter)}', 'type': kind, 'values': {f['key']: f.get('value', '') for f in item.get('fields', [])}, 'style': style or {}}
    if item.get('slides'):
        n['children'] = [[node_of(t) for t in kids] for kids in item.get('kids', [[]])]
    elif item.get('slots'):
        n['children'] = [[] for _ in range(item['slots'])]
    return n


def visible() -> list:
    return [i for c in codepage.LIB['categories'] if not c.get('hidden') for i in c['items']]


def page_of(blocks: list, theme: int = 0) -> dict:
    p = codepage.blank('test')
    p['theme'] = {**codepage.LIB['themes'][theme], 'radius': 10, 'font': codepage.LIB['fonts'][0]['css']}
    p['blocks'] = blocks
    return p


def templates() -> list:
    """The builder's templates (STARTS in builder.js): lists of component ids."""
    text = (ROOT / 'builder' / 'builder.js').read_text(encoding='utf-8')
    block = text[text.index('const STARTS = ['):text.index('];', text.index('const STARTS = ['))]
    return [(m.group(1), re.findall(r"'([\w-]+)'", m.group(2))) for m in re.finditer(r"name: '([^']+)'.*?blocks: \[([^\]]*)\]", block)]


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class Render(unittest.TestCase):
    def js(self, pages: list) -> list:
        with tempfile.TemporaryDirectory() as tmp:
            src, out, script = Path(tmp, 'in.json'), Path(tmp, 'out.json'), Path(tmp, 'r.js')
            src.write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
            script.write_text(NODE, encoding='utf-8')
            subprocess.run(['node', str(script), str(ROOT), str(src), str(out)], check=True)
            return json.loads(out.read_text(encoding='utf-8'))

    def test_there_are_hundreds_and_each_has_a_name_and_its_fields(self):
        items = visible()
        self.assertGreaterEqual(len(items), 600)
        self.assertEqual(len({i['id'] for i in items}), len(items))
        for item in items:
            self.assertTrue(item['name'], item['id'])
            used = set(re.findall(r'\{\{[#/]?([\w]+)', item['html'])) | {k for alt in re.findall(r'\{\{([\w:/]+/[\w:]+)\}\}', item['html']) for k in re.split(r'[/:]', alt)}
            for f in item.get('fields', []):
                self.assertIn(f['key'], used, f"{item['id']}: field {f['key']} is not in its html")
            if item.get('needs'):
                self.assertIn(item['needs'], codepage.BY_ID, item['id'])

    def test_every_component_comes_out_the_same_both_ways(self):
        pages = [page_of([node_of(i['id'])], theme=k % len(codepage.LIB['themes'])) for k, i in enumerate(visible())]
        made = self.js(pages)
        for i, (p, html) in enumerate(zip(pages, made)):
            want = codepage.document(p)
            self.assertEqual(html, want, p['blocks'][0]['type'])
            body = want[want.index('<body>'):]
            self.assertNotRegex(body, r'\{\{[^}]*\}\}', p['blocks'][0]['type'])  # nothing left unfilled

    def test_templates_motion_height_and_a_deck_in_a_column(self):
        names = templates()
        self.assertGreaterEqual(len(names), 15)
        pages = []
        for name, ids in names:
            for t in ids:
                self.assertIn(t, codepage.BY_ID, f'template {name}: no component {t}')
            pages.append(page_of([node_of(t) for t in ids]))
        row = node_of('row2')
        row['children'][0] = [node_of('deck', {'anim': 'up', 'minHeight': 400, 'valign': 'center'})]
        row['children'][1] = [node_of('feat-bento-ink', {'anim': 'zoom', 'width': 80, 'align': 'right'})]
        pages.append(page_of([row, node_of('hero-badge-glow', {'valign': 'bottom', 'minHeight': 900})]))
        made = self.js(pages)
        for p, html in zip(pages, made):
            self.assertEqual(html, codepage.document(p))
        last = made[-1]
        self.assertIn('class="cp-block cp-anim cp-anim-up"', last)
        self.assertIn("IntersectionObserver", last)  # the motion script came along
        self.assertIn('justify-content:flex-end', last)
        self.assertEqual(last.count('<section class="cp-slide">'), 5)

    def test_the_command_line_checks_slides_and_hides_the_shared_sheets(self):
        p = page_of([node_of('deck')])
        self.assertEqual(codepage.problems(p), [])
        p['blocks'][0]['children'] = []
        self.assertTrue(codepage.problems(p))
        self.assertTrue(codepage.problems(page_of([{'id': 'x', 'type': 'g-core', 'values': {}, 'style': {}}])))
        schema = codepage.cmd_schema(None)
        kinds = {c['type'] for c in schema['components']}
        self.assertNotIn('g-core', kinds)
        self.assertIn('deck', kinds)
        self.assertGreaterEqual(len(kinds), 600)


if __name__ == '__main__':
    unittest.main()
