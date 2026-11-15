"""Words of the tool windows in the language Lumen is set to (2026-11-13). Every tool carries this same file and its own en.json
({"中文": "English"}; a {0} in a line stands for a number or name that changes). 中文 is what the code says, so it is
what shows when Lumen is in 中文; for any other language the window is translated from en.json while it runs:

    Qt windows       embed.show(win) calls apply(win): a sweep over every widget's text, tool tip and placeholder, and the
                     dialogs' titles and texts, each time something new appears
    web windows      webshell.py calls web_script() once the page is loaded: the same, over the page's text and attributes

A line that is not in en.json stays as it is. No file is read, and nothing is patched, when the language is 中文.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
HAN = re.compile(r'[一-鿿]')


LANGS = ('zh', 'en', 'fr', 'es', 'de', 'it', 'pt')  # Lumen's languages (desktop/i18n.LANGS); a window shows English for any other


def _norm(code) -> str:
    c = str(code or 'zh').lower()
    if c.startswith('zh'):
        return 'zh'
    return c[:2] if c[:2] in LANGS else 'en'


def language() -> str:
    import sys
    given = os.environ.get('LUMEN_LANG')
    for k, a in enumerate(sys.argv):
        if a == '--lang' and k + 1 < len(sys.argv):
            given = sys.argv[k + 1]
        elif a.startswith('--lang='):
            given = a.split('=', 1)[1]
    if given:
        return _norm(given)
    home = Path(os.environ.get('CODEDOCTOR_HOME') or Path.home() / '.codedoctor')
    try:
        lang = json.loads((home / 'ui.json').read_text(encoding='utf-8')).get('language')
    except (OSError, ValueError, AttributeError):
        lang = None
    return _norm(lang)


def table(*folders: Path) -> dict:
    """The words of the interface: each folder's en.json, and in another language its <code>.json over it (fr.json, es.json ...;
    a folder earlier in the list wins; a line missing from <code>.json shows in English)."""
    out: dict = {}
    for folder in (*folders, HERE):
        layer: dict = {}
        for name in ('en.json',) if language() in ('en', 'zh') else ('en.json', f'{language()}.json'):
            try:
                layer.update(json.loads((Path(folder) / name).read_text(encoding='utf-8')))
            except (OSError, ValueError, AttributeError):
                continue
        for k, v in layer.items():
            out.setdefault(k, v)
    return out


class Words:
    def __init__(self, entries: dict):
        self.exact = {k: v for k, v in entries.items() if '{' not in k}
        self.shapes = []
        for k, v in entries.items():
            if '{' in k and HAN.search(re.sub(r'\{\d+\}', '', k)):  # a line with no words of its own around its {0} would swallow any name
                pattern = ''.join('(.+?)' if re.fullmatch(r'\{\d+\}', p) else re.escape(p) for p in re.split(r'(\{\d+\})', k))
                self.shapes.append((re.compile('^' + pattern + '$', re.S), v))

    def __call__(self, text: str) -> str:
        if not text or not HAN.search(text):
            return text
        done = self.__dict__.setdefault('_seen', {})  # painted text asks again on every paint
        if text in done:
            return done[text]
        out = self._say(text)
        if len(done) < 4000:
            done[text] = out
        return out

    def _say(self, text: str) -> str:
        key = text.strip()
        got = self.exact.get(key)
        if got is None:
            for rx, v in self.shapes:
                m = rx.match(key)
                if m:
                    got = re.sub(r'\{(\d+)\}', lambda g: self(m.group(int(g.group(1)) + 1)) if int(g.group(1)) < len(m.groups()) else '', v)
                    break
        return text if got is None else text.replace(key, got, 1)


# --- what a command line says to Lumen ---------------------------------------------------------------------------------------

_cli = None


def localize(obj):
    """An answer a tool prints for Lumen to show (names, blurbs, notes, errors) in Lumen's language. Whole lines only: a string is
    translated when it is exactly a line of en.json (or one of its {0} templates), never piece by piece, so a name or a file path
    that happens to contain a known word is left alone. 中文 returns the answer as it is."""
    global _cli
    if language() == 'zh':
        return obj
    if _cli is None:
        _cli = Words(table(HERE))
    if isinstance(obj, str):
        return _cli(obj)
    if isinstance(obj, list):
        return [localize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: localize(v) for k, v in obj.items()}
    return obj


# --- Qt windows ---------------------------------------------------------------------------------------------------------
# No timer: a widget is translated once, when Qt polishes it (just before it is first shown), and every later setText / setToolTip /
# setPlaceholderText / setTitle / setItemText / addItem goes through the same table on its way in, so a window that is resized never
# shows a Chinese word for a moment. A widget that shows the person's own words (a file name, a note) carries the property
# `no_i18n` = True and is left alone.

def apply(win) -> None:
    if language() == 'zh':
        return
    words = Words(table(HERE))
    if not words.exact and not words.shapes:
        return
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QFileDialog, QGroupBox, QInputDialog, QLabel, QLineEdit, QListWidget,
                                   QMenu, QMessageBox, QPlainTextEdit, QStatusBar, QTabBar, QTextEdit, QWidget)

    def mine(w) -> bool:
        return not w.property('no_i18n')

    def say(w, text):
        return words(text) if isinstance(text, str) and HAN.search(text) and mine(w) else text

    # what a widget is born with: once, at polish
    def polish(w) -> None:
        try:
            if not mine(w):
                return
            tip = w.toolTip()
            if tip and HAN.search(tip):
                w.setToolTip(tip)
            if isinstance(w, (QLabel, QAbstractButton)):
                t = w.text()
                if HAN.search(t):
                    w.setText(t)
            elif isinstance(w, QGroupBox):
                w.setTitle(w.title())
            elif isinstance(w, QComboBox):
                for i in range(w.count()):
                    if HAN.search(w.itemText(i)):
                        w.setItemText(i, w.itemText(i))
            elif isinstance(w, QTabBar):
                for i in range(w.count()):
                    if HAN.search(w.tabText(i)):
                        w.setTabText(i, w.tabText(i))
            elif isinstance(w, (QLineEdit, QPlainTextEdit, QTextEdit)):
                if HAN.search(w.placeholderText()):
                    w.setPlaceholderText(w.placeholderText())
            elif isinstance(w, QListWidget):
                for i in range(w.count()):
                    item = w.item(i)
                    if HAN.search(item.text()) and not item.data(0x0100):  # an item that carries data is the person's own (a file name)
                        item.setText(words(item.text()))
            if w.isWindow() and HAN.search(w.windowTitle()):
                w.setWindowTitle(w.windowTitle())
            if isinstance(w, QMenu):
                for a in w.actions():
                    if HAN.search(a.text()):
                        a.setText(a.text())
        except RuntimeError:
            pass  # a widget that was just deleted

    class Watch(QObject):
        def eventFilter(self, obj, e):
            if e.type() == QEvent.Polish and isinstance(obj, QWidget):
                polish(obj)
            return False

    # later changes pass through the table too
    def wrap(cls, name: str, at: int = 0, skip=None) -> None:
        orig = getattr(cls, name, None)
        if orig is None:
            return

        def call(self, *args, **kw):
            args = list(args)
            if at < len(args) and isinstance(args[at], str) and HAN.search(args[at]):
                owner = self if isinstance(self, QWidget) else None
                if owner is None or mine(owner):
                    args[at] = words(args[at])
            return orig(self, *args, **kw)
        try:
            setattr(cls, name, call)
        except (TypeError, AttributeError):
            pass

    wrap(QLabel, 'setText')
    wrap(QAbstractButton, 'setText')
    wrap(QGroupBox, 'setTitle')
    wrap(QWidget, 'setToolTip')
    wrap(QWidget, 'setWindowTitle')
    wrap(QLineEdit, 'setPlaceholderText')
    wrap(QPlainTextEdit, 'setPlaceholderText')
    wrap(QTextEdit, 'setPlaceholderText')
    wrap(QComboBox, 'setItemText', 1)
    wrap(QComboBox, 'addItem', 0)
    wrap(QTabBar, 'setTabText', 1)
    wrap(QAction, 'setText')
    wrap(QStatusBar, 'showMessage')
    try:  # text painted by hand (a timeline's track names): every string argument of drawText
        from PySide6.QtGui import QPainter
        orig_draw = QPainter.drawText

        def draw(self, *args):
            return orig_draw(self, *[words(a) if isinstance(a, str) else a for a in args])
        QPainter.drawText = draw
    except (TypeError, AttributeError):
        pass
    wrap(QAction, 'setToolTip')

    # the dialogs the windows ask with: static calls carry their words as arguments
    def wrap_static(cls, name: str, positions: tuple) -> None:
        orig = getattr(cls, name, None)
        if orig is None:
            return

        def call(*args, **kw):
            args = list(args)
            for p in positions:
                if p < len(args) and isinstance(args[p], str):
                    args[p] = words(args[p])
            for k in ('title', 'text', 'label', 'caption', 'filter'):
                if isinstance(kw.get(k), str):
                    kw[k] = words(kw[k])
            return orig(*args, **kw)
        setattr(cls, name, staticmethod(call))

    for name in ('question', 'information', 'warning', 'critical'):
        wrap_static(QMessageBox, name, (1, 2))
    for name in ('getText', 'getItem', 'getInt', 'getDouble'):
        wrap_static(QInputDialog, name, (1, 2))
    for name in ('getOpenFileName', 'getOpenFileNames', 'getSaveFileName', 'getExistingDirectory'):
        wrap_static(QFileDialog, name, (1, 3) if name != 'getExistingDirectory' else (1,))

    app = QApplication.instance()
    watch = Watch(app)  # owned by the application, not the window: the filter must outlive every window and go before the application does
    app.installEventFilter(watch)
    app.aboutToQuit.connect(lambda: app.removeEventFilter(watch))
    win._i18n_watch = watch
    for w in QApplication.allWidgets():  # what already exists
        polish(w)


# --- web windows --------------------------------------------------------------------------------------------------------

WEB = r"""
(function (T, R) {
  if (window.__i18n) return;
  window.__i18n = true;
  const HAN = /[一-鿿]/;
  const shapes = R.map(([src, v]) => [new RegExp(src, 's'), v]);
  function tr(s) {
    if (!s || !HAN.test(s)) return s;
    const k = s.trim();
    let v = T[k];
    if (v === undefined) {
      for (const [rx, tpl] of shapes) {
        const m = rx.exec(k);
        if (m) { v = tpl.replace(/\{(\d+)\}/g, (_, i) => (m[+i + 1] !== undefined ? tr(m[+i + 1]) : '')); break; }
      }
    }
    return v === undefined ? s : s.replace(k, () => v);
  }
  const SKIP = 'pre,code,textarea,script,style,[contenteditable="true"],.cm-content,.code-edit,.no-i18n';
  const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  function node(n) {
    if (n.nodeType === 3) {
      if (HAN.test(n.nodeValue) && !(n.parentElement && n.parentElement.closest(SKIP))) {
        const v = tr(n.nodeValue);
        if (v !== n.nodeValue) n.nodeValue = v;
      }
    } else if (n.nodeType === 1) {
      if (n.matches && n.matches(SKIP)) return;
      for (const a of ATTRS) { const v = n.getAttribute(a); if (v && HAN.test(v)) { const w = tr(v); if (w !== v) n.setAttribute(a, w); } }
      for (const c of n.childNodes) node(c);
    }
  }
  let queued = false;
  const dirty = new Set();
  function flush() { queued = false; const list = [...dirty]; dirty.clear(); for (const n of list) node(n); }
  function mark(n) { dirty.add(n); if (!queued) { queued = true; requestAnimationFrame(flush); } }
  new MutationObserver((records) => {
    for (const r of records) {
      if (r.type === 'childList') r.addedNodes.forEach(mark);
      else if (r.type === 'characterData') mark(r.target);
      else if (r.type === 'attributes') mark(r.target);
    }
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  window.__tr = tr;
  document.title = tr(document.title);
  node(document.body || document.documentElement);
  window.dispatchEvent(new Event('i18n'));  // a page that draws words of its own (CodePage's canvas) draws them again
})
"""


def web_script(*folders: Path) -> str:
    """The script that translates a page, or '' when the language is 中文 or there is nothing to translate with."""
    if language() == 'zh':
        return ''
    words = Words(table(*folders))
    if not words.exact and not words.shapes:
        return ''
    shapes = [[rx.pattern, v] for rx, v in words.shapes]
    return f'({WEB})({json.dumps(words.exact, ensure_ascii=False)}, {json.dumps(shapes, ensure_ascii=False)});'
