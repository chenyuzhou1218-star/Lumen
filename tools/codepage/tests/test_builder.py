"""The builder driven with a real mouse in Edge (playwright): the long list of components, the filters, the three resize
grips, motion, and a deck of slides from the left to the exported page. Pictures go to CODEPAGE_SHOTS when it is set."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

SHOTS = os.environ.get('CODEPAGE_SHOTS')


@unittest.skipIf(sync_playwright is None, 'playwright is not installed')
class Builder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='msedge')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.ctx = self.browser.new_context(viewport={'width': 1440, 'height': 900})
        self.p = self.ctx.new_page()
        self.errors = []
        self.p.on('pageerror', lambda e: self.errors.append(str(e)))
        self.p.goto((ROOT / 'builder' / 'index.html').as_uri())
        self.p.wait_for_function('document.querySelectorAll(".part").length > 0')
        self.p.wait_for_timeout(300)

    def tearDown(self):
        self.ctx.close()
        self.assertEqual(self.errors, [])

    def shot(self, name):
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            self.p.screenshot(path=str(Path(SHOTS, name)))

    def page(self) -> dict:
        return self.p.evaluate('JSON.parse(JSON.stringify(page))')

    def canvas_box(self, selector):
        return self.p.frame_locator('#canvas').locator(selector).first.bounding_box()

    def add(self, kind):
        """Double-click a component's tile: it goes to the end of the page."""
        self.p.fill('#find', '')
        self.p.evaluate(f"catFilter=''; lookFilter=''; fillFilters(); fillParts('')")
        self.p.fill('#find', kind)
        tile = self.p.locator(f'.part:has(.thumb[data-part="{kind}"])').first
        tile.scroll_into_view_if_needed()
        tile.dblclick()
        self.p.wait_for_timeout(150)

    def test_hundreds_of_components_drawn_only_when_seen_and_filtered(self):
        note = self.p.inner_text('#paneNote')
        self.assertGreaterEqual(int(note.split()[0]), 600)
        drawn = self.p.evaluate('document.querySelectorAll(".thumb[data-drawn]").length')
        tiles = self.p.evaluate('document.querySelectorAll(".thumb").length')
        self.assertGreater(drawn, 4)
        self.assertLess(drawn, tiles)  # the rest wait until they are scrolled to
        self.p.evaluate('document.getElementById("parts").scrollTop = 6000')
        self.p.wait_for_timeout(300)
        self.assertGreater(self.p.evaluate('document.querySelectorAll(".thumb[data-drawn]").length'), drawn)
        self.p.click('.chip:has-text("反色")')
        ink = self.p.evaluate('[...document.querySelectorAll(".thumb")].map((t) => CP.byId[t.dataset.part].look)')
        self.assertTrue(ink and all(k == 'ink' for k in ink))
        self.p.select_option('#partsFilter select', 'slides')
        self.p.click('.chip:has-text("全部")')
        names = self.p.evaluate('[...document.querySelectorAll(".cat span:nth-child(2)")].map((e) => e.textContent)')
        self.assertEqual(names, ['幻灯片'])
        self.shot('panel.png')

    def test_three_grips_width_height_and_both(self):
        self.add('feat-icons3')
        self.p.wait_for_timeout(200)
        node = self.page()['blocks'][-1]
        self.assertEqual(self.p.evaluate('selected'), node['id'])
        b = self.canvas_box('#cp-grip-b')
        el = self.canvas_box(f'[data-node="{node["id"]}"]')
        self.p.mouse.move(b['x'] + b['width'] / 2, b['y'] + b['height'] / 2)
        self.p.mouse.down()
        self.p.mouse.move(b['x'] + b['width'] / 2, b['y'] + 160, steps=8)
        size = self.p.frame_locator('#canvas').locator('#cp-size').inner_text()
        self.assertIn('高', size)
        self.p.mouse.up()
        s = self.page()['blocks'][-1]['style']
        self.assertGreater(s['minHeight'], el['height'] + 100)
        self.assertEqual(s['valign'], 'center')
        el2 = self.canvas_box(f'[data-node="{node["id"]}"]')
        self.assertAlmostEqual(el2['height'], s['minHeight'], delta=2)
        self.shot('taller.png')
        # pulled shorter than its content: back to the height it needs (scrolled so that its bottom edge is in view)
        self.p.frame_locator('#canvas').locator('body').evaluate(
            f'() => {{ const e = document.querySelector(\'[data-node="{node["id"]}"]\'); document.documentElement.scrollTop = e.offsetTop + e.offsetHeight - 700; }}')
        self.p.wait_for_timeout(150)
        b = self.canvas_box('#cp-grip-b')
        frame_box = self.p.locator('#canvas').bounding_box()
        self.assertLess(b['y'], frame_box['y'] + frame_box['height'])  # the grip is where the hand can reach it
        self.p.mouse.move(b['x'] + 15, b['y'] + 4)
        self.p.mouse.down()
        self.p.mouse.move(b['x'] + 15, b['y'] - 600, steps=8)
        self.p.mouse.up()
        self.assertNotIn('minHeight', self.page()['blocks'][-1]['style'])
        # the corner: both
        c = self.canvas_box('#cp-grip-c')
        self.p.mouse.move(c['x'] + 6, c['y'] + 6)
        self.p.mouse.down()
        self.p.mouse.move(c['x'] - 300, c['y'] + 220, steps=10)
        self.p.mouse.up()
        s = self.page()['blocks'][-1]['style']
        self.assertLess(s['width'], 85)
        self.assertGreater(s['minHeight'], 0)
        self.p.keyboard.press('Control+z')
        self.assertNotIn('width', self.page()['blocks'][-1]['style'])  # one undo for one drag
        # the right grip still works on its own
        g = self.canvas_box('#cp-grip')
        self.p.mouse.move(g['x'] + 4, g['y'] + 10)
        self.p.mouse.down()
        self.p.mouse.move(g['x'] - 400, g['y'] + 10, steps=8)
        self.p.mouse.up()
        s = self.page()['blocks'][-1]['style']
        self.assertLess(s['width'], 75)
        self.assertNotIn('minHeight', s)

    def test_vertical_place_and_motion_from_the_inspector(self):
        self.add('cta-banner')
        self.p.click('#right .field:has(label:text-is("竖直")) button[title="内容在下面"]')
        self.p.click('#right .field:has(label:text-is("出现")) button:has-text("上浮")')
        s = self.page()['blocks'][-1]['style']
        self.assertEqual((s['valign'], s['anim']), ('bottom', 'up'))
        html = self.p.evaluate('cpDocument(page)')
        self.assertIn('cp-anim cp-anim-up', html)
        self.assertIn('IntersectionObserver', html)
        self.shot('inspector.png')

    def test_a_deck_from_the_left_to_full_screen(self):
        self.add('deck')
        deck = self.page()['blocks'][-1]
        self.assertEqual(len(deck['children']), 5)
        frame = self.p.frame_locator('#canvas')
        self.assertEqual(frame.locator(f'[data-node="{deck["id"]}"] .cp-slide').count(), 5)
        self.assertIn('5 页', self.p.inner_text('#right'))
        self.p.select_option('#right .addPage select', 'sl-quote')
        self.p.click('#right .addPage button')
        deck = self.page()['blocks'][-1]
        self.assertEqual(len(deck['children']), 6)
        self.assertEqual(deck['children'][5][0]['type'], 'sl-quote')
        self.p.click('#right .pageRow:nth-child(6) [data-p="up"]')
        self.assertEqual(self.page()['blocks'][-1]['children'][4][0]['type'], 'sl-quote')
        # drag a slide from the left into the second page
        self.p.fill('#find', '大数字页')
        tile = self.p.locator('.part:has(.thumb[data-part="sl-big-num"])').first
        t = tile.bounding_box()
        target = self.canvas_box(f'[data-node="{deck["id"]}"] .cp-slide:nth-child(2) [data-slot]')
        frame.locator(f'[data-node="{deck["id"]}"] .cp-slide:nth-child(2)').scroll_into_view_if_needed()
        target = self.canvas_box(f'[data-node="{deck["id"]}"] .cp-slide:nth-child(2) [data-slot]')
        self.p.mouse.move(t['x'] + 30, t['y'] + 30)
        self.p.mouse.down()
        self.p.mouse.move(t['x'] + 80, t['y'] + 60, steps=4)
        self.p.mouse.move(target['x'] + target['width'] / 2, target['y'] + target['height'] - 20, steps=12)
        self.p.mouse.up()
        second = self.page()['blocks'][-1]['children'][1]
        self.assertEqual([k['type'] for k in second], ['sl-agenda', 'sl-big-num'])
        self.shot('deck-builder.png')
        # the page people get: one slide at a time
        html = self.p.evaluate('cpDocument(page)')
        out = Path(tempfile.mkdtemp(), 'index.html')
        out.write_text(html, encoding='utf-8')
        view = self.ctx.new_page()
        view.goto(out.as_uri())
        view.wait_for_timeout(300)
        deck_el = view.locator('.cp-deck').last
        deck_el.scroll_into_view_if_needed()
        self.assertEqual(view.locator('.cp-deck.on .cp-slide.cur').count(), 1)
        self.assertEqual(view.inner_text('.cp-deck-n'), '1 / 6')
        deck_el.locator('[data-deck=next]').click()
        deck_el.locator('[data-deck=next]').click()
        self.assertEqual(view.inner_text('.cp-deck-n'), '3 / 6')
        deck_el.focus()
        view.keyboard.press('ArrowLeft')
        self.assertEqual(view.inner_text('.cp-deck-n'), '2 / 6')
        view.keyboard.press('End')
        self.assertEqual(view.inner_text('.cp-deck-n'), '6 / 6')
        self.assertTrue(view.locator('[data-deck=next]').is_disabled())
        view.wait_for_timeout(600)
        if SHOTS:
            view.screenshot(path=str(Path(SHOTS, 'deck-page.png')))
        view.close()

    def test_a_template_at_phone_width_fits(self):
        self.p.click('[data-tab="starts"]')
        self.p.locator('.start:has-text("产品发布")').click()
        self.p.wait_for_timeout(400)
        self.assertGreaterEqual(len(self.page()['blocks']), 8)
        self.p.click('[data-width="390px"]')
        self.p.wait_for_timeout(500)
        over = self.p.frame_locator('#canvas').locator('body').evaluate('() => document.documentElement.scrollWidth - document.documentElement.clientWidth')
        self.assertLessEqual(over, 0)
        self.shot('phone.png')


if __name__ == '__main__':
    unittest.main()
