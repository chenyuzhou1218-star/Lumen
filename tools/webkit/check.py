"""Looks at a tool's real window without putting anything on the desktop (QT_QPA_PLATFORM=offscreen): the page is
loaded over the real bridge, read with JavaScript at several window sizes, in 浅色 and 深色, and every button and card
is checked to be inside the window and not squeezed.

    python webkit/check.py <tool> [--script probe.js] [--sizes 1280x820,960x640,...]
The tool's editor.py gives the window: window_for_check(argv) if it has one, else app_window.Project with its CONFIG.
Prints one JSON line per size and ends with "ok" or what is wrong."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QPA_FONTDIR', 'C:/Windows/Fonts')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')

TOOLS = Path(__file__).resolve().parents[1]

# Everything that should be inside the window: anything clickable, every card's head, the bar, the bottom line.
# An element inside something that scrolls is fine below or right of the window: it can be scrolled to.
LAYOUT = r"""(() => {
  const W = innerWidth, H = innerHeight, bad = [];
  const scrolls = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p);
    if (/(auto|scroll)/.test(s.overflowY + s.overflowX) && (p.scrollHeight > p.clientHeight + 1 || p.scrollWidth > p.clientWidth + 1)) return true; } return false; };
  const name = (el) => (el.getAttribute('aria-label') || el.title || el.textContent || el.className || el.tagName).trim().slice(0, 30);
  for (const el of document.querySelectorAll('button, .card-head, .bar, .foot, input, textarea, select, [role=separator]')) {
    if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
    if (el.closest('.code')) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if ((r.right > W + 1 || r.bottom > H + 1 || r.left < -1 || r.top < -1) && !scrolls(el)) bad.push(`outside: ${name(el)} ${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)}`);
  }
  // nothing on a bar or a card's head lies over its neighbour
  for (const row of document.querySelectorAll('.bar, .card-head, .foot, .askbox .row, .drawer-head')) {
    if (!row.offsetParent && getComputedStyle(row).position !== 'fixed') continue;
    const parts = [...row.querySelectorAll('button, b, .crumb, .project, .unsaved, .chip, .status, .where, .mark, .pick')]
      .filter((e) => e.offsetParent && !e.closest('.menu') && !(e.tagName === 'B' && e.closest('button')))
      .map((e) => [e, e.getBoundingClientRect()]).filter(([, r]) => r.width > 0);
    for (let i = 0; i < parts.length; i++) for (let j = i + 1; j < parts.length; j++) {
      const [ea, a] = parts[i], [eb, b] = parts[j];
      if (ea.contains(eb) || eb.contains(ea)) continue;
      const x = Math.min(a.right, b.right) - Math.max(a.left, b.left), y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (x > 1 && y > 1) bad.push(`overlap: ${name(ea)} / ${name(eb)}`);
    }
  }
  for (const el of document.querySelectorAll('.bar, .bar .who, .card-head, .foot, .tools, .askbox .row, .modal-foot')) {
    if (el.offsetParent && el.scrollWidth > el.clientWidth + 1) bad.push(`squeezed: ${el.className} ${el.scrollWidth}>${el.clientWidth}`);
  }
  for (const el of document.querySelectorAll('button')) {
    if (!el.offsetParent || el.closest('.menu')) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && el.scrollWidth > el.clientWidth + 1) bad.push(`button cut: ${name(el)}`);
  }
  const app = document.querySelector('.app');
  if (app && (app.scrollHeight > app.clientHeight + 1 || app.scrollWidth > app.clientWidth + 1)) bad.push(`page overflows ${app.scrollWidth}x${app.scrollHeight} > ${app.clientWidth}x${app.clientHeight}`);
  return bad;
})()"""


def pump(app, seconds: float, until=None) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return bool(until and until())


def js(app, win, code: str, wait: float = 8):
    box = {}
    win.view.page().runJavaScript(f'JSON.stringify((() => {{ return {code}; }})())', 0, lambda r: box.setdefault('r', r))
    pump(app, wait, until=lambda: 'r' in box)
    r = box.get('r')
    return json.loads(r) if r not in (None, '') else None


def keep_prefs(editor) -> None:
    """The check opens examples; the user's own remembered project stays what it was (QSettings 'Lumen'/<tool>)."""
    from PySide6.QtCore import QSettings
    import atexit

    name = getattr(getattr(editor, 'CONFIG', None), 'name', None) or getattr(editor, 'PREFS', None)
    if not name:
        return
    prefs = QSettings('Lumen', name)
    saved = {k: prefs.value(k) for k in prefs.allKeys()}

    def put_back():
        prefs.clear()
        for k, v in saved.items():
            prefs.setValue(k, v)
        prefs.sync()

    atexit.register(put_back)


def open_window(tool: str, argv: list, mode: str):
    sys.path.insert(0, str(TOOLS / tool))
    os.chdir(TOOLS / tool)
    import webshell

    app = webshell.make_app()
    editor = importlib.import_module('editor')
    keep_prefs(editor)
    if hasattr(editor, 'window_for_check'):
        win = editor.window_for_check(argv, mode)
    else:
        import app_window

        folder, watch, _ = app_window.args_of(argv)
        project = app_window.Project(editor.CONFIG, folder, watch)
        win = webshell.window(project, editor.CONFIG.name, TOOLS / tool / 'ui_dist', mode=mode, minimum=(380, 300))
    return app, win


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('tool')
    ap.add_argument('--sizes', default='1280x820,1580x430,1580x360,1200x500,1024x700,860x600,720x480,560x420,420x340')
    ap.add_argument('--script', help='a JavaScript file run after the checks; its value is printed')
    ap.add_argument('--ready', default="!!document.querySelector('.app .bar, .app header')")
    ap.add_argument('args', nargs='*')
    a = ap.parse_args()
    problems = []
    for mode in ('light', 'dark'):
        app, win = open_window(a.tool, a.args, mode)
        win.resize(1280, 820)
        win.show()
        if not pump(app, 30, until=lambda: js(app, win, a.ready, 1)):
            print(json.dumps({'mode': mode, 'error': 'the page did not draw'}))
            return 1
        got = js(app, win, "document.documentElement.dataset.mode + '|' + getComputedStyle(document.body).backgroundColor")
        want = 'dark|rgb(28, 28, 31)' if mode == 'dark' else 'light|rgb(255, 255, 255)'
        if got != want:
            problems.append(f'{mode}: page is {got}')
        for size in a.sizes.split(','):
            w, h = (int(v) for v in size.split('x'))
            win.resize(w, h)
            pump(app, 0.6)
            bad = js(app, win, LAYOUT) or []
            print(json.dumps({'mode': mode, 'size': size, 'view': js(app, win, '[innerWidth, innerHeight]'), 'bad': bad}, ensure_ascii=False))
            problems += [f'{mode} {size}: {b}' for b in bad]
        if a.script:
            win.resize(1280, 820)
            pump(app, 0.5)
            code = Path(a.script).read_text(encoding='utf-8')
            js(app, win, f"(window.__probe = undefined, Promise.resolve({code}).then((v) => {{ window.__probe = v === undefined ? null : v; }}, (e) => {{ window.__probe = {{ error: String(e) }}; }}), 0)")
            pump(app, 120, until=lambda: js(app, win, 'window.__probe !== undefined', 1))
            print(json.dumps({'mode': mode, 'script': js(app, win, 'window.__probe')}, ensure_ascii=False))
        win.closing = True
        if hasattr(win.handler, 'closing'):
            win.handler.closing()
        win.close()
        win.deleteLater()
        pump(app, 0.3)
    print('ok' if not problems else 'PROBLEMS:\n' + '\n'.join(problems))
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
