"""Display-layer translation of the desktop (2026-11-01).

The window's code writes its Chinese texts directly, and some code compares them (a status chip's colour comes from
its text, a test verdict is read back from its words). Translating in the source would break those comparisons. So
the code keeps its Chinese, and every text is translated where it reaches the screen: Qt's text setters (labels,
buttons, tool tips, placeholders, menus, actions, tabs, combo boxes, list items, message boxes) are wrapped once at
start-up and look the text up in desktop/locale/<lang>.json:

    {"exact": {"中文": "English"}, "templates": {"{0} 步 · {1}": "{0} steps · {1}"}}

A template's {n} are the values an f-string put in; they are translated too when they are themselves known texts.
Multi-line texts go line by line and HTML text segment by segment. Unknown text is shown as it is (an agent's answer
is never touched). A language without its own catalog falls back to English. tools/extract_ui_strings.py lists the
texts; tests/daemon/test_locale.py checks every one has an English entry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HAN = re.compile(r"[一-鿿]")
_DIR = Path(__file__).resolve().parent / "locale"
_exact: dict[str, str] = {}
_templates: list[tuple[re.Pattern, str]] = []
_active = False


def _compile(tpl: str) -> re.Pattern:
    parts = re.split(r"(\{\d+\})", tpl)
    rx = "".join("(.+?)" if re.fullmatch(r"\{\d+\}", p) else re.escape(p.replace("{{", "{").replace("}}", "}")) for p in parts)
    return re.compile(rx, re.S)


def load(lang: str) -> None:
    """Use `lang`'s catalog (English for what it lacks); Chinese: nothing to do."""
    global _active, _hant
    _exact.clear()
    _templates.clear()
    _active = lang != "zh"
    _hant = lang == "zh-TW"  # 繁體中文: the Chinese texts converted (zh_hant.py), no catalog of its own
    _cache.clear()
    if not _active or _hant:
        return
    merged = {"exact": {}, "templates": {}}
    for code in ("en", lang) if lang != "en" else ("en",):
        try:
            cat = json.loads((_DIR / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        merged["exact"].update(cat.get("exact", {}))
        merged["templates"].update(cat.get("templates", {}))
    _exact.update({k: v for k, v in merged["exact"].items() if v})
    order = sorted(merged["templates"].items(), key=lambda kv: -len(re.sub(r"\{\d+\}", "", kv[0])))  # most specific first
    for zh, out in order:
        if out:
            _templates.append((_compile(zh), out))


def catalog(lang: str) -> dict:
    """The catalog the page gets: English, with `lang`'s texts over it (the same merge as load())."""
    merged = {"exact": {}, "templates": {}}
    for code in ("en", lang) if lang != "en" else ("en",):
        try:
            cat = json.loads((_DIR / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        merged["exact"].update({k: v for k, v in cat.get("exact", {}).items() if v})
        merged["templates"].update({k: v for k, v in cat.get("templates", {}).items() if v})
    return merged


_cache: dict[str, str] = {}
_hant = False
_LEAD = re.compile(r"^[\s●•○◆▶▸▾⇅✓✔×·\-–—()（）\[\]【】📌]+")
_SENT = re.compile(r"(?<=[。！？])")


def t(text):
    """The text in the interface language (unchanged when unknown, not Chinese, or the language is Chinese)."""
    if not _active or not isinstance(text, str) or not HAN.search(text):
        return text
    hit = _cache.get(text)
    if hit is None:
        if _hant:
            from codedoctor.desktop import zh_hant

            hit = zh_hant.convert(text)
        else:
            hit = _translate(text)
        if len(_cache) > 20000:
            _cache.clear()
        _cache[text] = hit
    return hit


def _known(text: str) -> str | None:
    """Exactly a catalog text, or a template filled with values."""
    hit = _exact.get(text)
    if hit is not None:
        return hit
    for rx, out in _templates:
        m = rx.fullmatch(text)
        if m:
            try:
                done = out.format(*[t(g) for g in m.groups()])
            except (IndexError, KeyError, ValueError):
                return None
            # two values side by side ("{1}{2}") may be split in the wrong place: the pieces get another look
            return _pieces(done) if HAN.search(done) else done
    return None


def _pieces(text: str) -> str:
    for sep in ("　·　", " · ", "：", "，", "、"):
        if sep in text:
            parts = text.split(sep)
            done = [t(p) for p in parts]
            if done != parts:
                return {"：": ": ", "，": ", ", "　·　": " · ", "、": ", "}.get(sep, sep).join(done)
    return text


def _translate(text: str) -> str:
    hit = _known(text)
    if hit is not None:
        return hit
    core = text.strip()
    if core != text and core:
        return text.replace(core, t(core), 1)
    lead = _LEAD.match(text)  # "● 事件", "📌 标题": a symbol in front of a known text
    if lead and lead.end() < len(text):
        rest = t(text[lead.end():])
        if rest != text[lead.end():]:
            return text[:lead.end()] + rest
    if "\n" in text:
        return "\n".join(t(line) for line in text.split("\n"))
    if "<" in text and ">" in text:  # rich text: each text segment between tags
        return re.sub(r">([^<]+)<", lambda m: ">" + t(m.group(1)) + "<", text)
    for rx, out in _templates:  # a template followed by more sentences (texts joined in code)
        if rx.pattern.endswith("(.+?)"):
            continue
        m = rx.match(text)
        if m and 0 < m.end() < len(text) and text[m.end() - 1] in "。！？.":
            try:
                return out.format(*[t(g) for g in m.groups()]) + " " + t(text[m.end():])
            except (IndexError, KeyError, ValueError):
                break
    parts = [p for p in _SENT.split(text) if p]
    if len(parts) > 1:  # sentence by sentence
        done = [t(p) for p in parts]
        if done != parts:
            return " ".join(done)
    return _pieces(text)  # pieces joined in code, each a known text


def _wrap_args(fn, positions):
    """A method wrapper translating the str arguments at these positions (after self)."""
    def wrapper(self, *args, **kw):
        args = list(args)
        for i in positions:
            if i < len(args) and isinstance(args[i], str):
                args[i] = t(args[i])
        return fn(self, *args, **kw)
    wrapper.__wrapped__ = fn
    return wrapper


def _wrap_first_str(fn, buttons: bool = False):
    """For overloads like (text) / (icon, text) / (text, parent): the first two str arguments."""
    def wrapper(self, *args, **kw):
        args = [t(a) if isinstance(a, str) and i < 2 else a for i, a in enumerate(args)]
        if buttons:
            args = [a.replace("&", "&&") if isinstance(a, str) and "&" in a and "&&" not in a else a for a in args]
        return fn(self, *args, **kw)
    wrapper.__wrapped__ = fn
    return wrapper


def _wrap_static(fn, positions):
    def wrapper(*args, **kw):
        args = list(args)
        for i in positions:
            if i < len(args) and isinstance(args[i], str):
                args[i] = t(args[i])
        return fn(*args, **kw)
    wrapper.__wrapped__ = fn
    return staticmethod(wrapper)


_installed = False


def install(lang: str) -> None:
    """Load the catalog and wrap Qt's text setters (once per process)."""
    global _installed
    load(lang)
    if _installed or not _active:
        return
    _installed = True
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QComboBox, QFileDialog, QGroupBox, QInputDialog, QLabel,
                                   QLineEdit, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                                   QRadioButton, QTableWidgetItem, QTabWidget, QTextEdit, QToolButton, QTreeWidgetItem,
                                   QWidget)

    for cls in (QLabel, QPushButton, QCheckBox, QRadioButton, QToolButton, QGroupBox, QAction, QMenu, QListWidgetItem):
        cls.__init__ = _wrap_first_str(cls.__init__, buttons=cls in (QPushButton, QCheckBox, QRadioButton, QToolButton))
    QLabel.setText = _wrap_args(QLabel.setText, [0])
    QAbstractButton.setText = _wrap_args(QAbstractButton.setText, [0])
    for cls in (QAbstractButton,):  # on a button "&" marks a shortcut key: "Findings & memory" lost its "&"
        for name in ("setText",):
            inner = getattr(cls, name)

            def amp(self, text, *rest, _inner=inner):
                if isinstance(text, str) and "&" in text and "&&" not in text:
                    text = text.replace("&", "&&")
                return _inner(self, text, *rest)
            setattr(cls, name, amp)
    QWidget.setToolTip = _wrap_args(QWidget.setToolTip, [0])
    QWidget.setWindowTitle = _wrap_args(QWidget.setWindowTitle, [0])
    for cls in (QLineEdit, QPlainTextEdit, QTextEdit):
        cls.setPlaceholderText = _wrap_args(cls.setPlaceholderText, [0])
    QGroupBox.setTitle = _wrap_args(QGroupBox.setTitle, [0])
    QTabWidget.addTab = _wrap_args(QTabWidget.addTab, [1, 2])
    QTabWidget.insertTab = _wrap_args(QTabWidget.insertTab, [2, 3])
    QTabWidget.setTabText = _wrap_args(QTabWidget.setTabText, [1])
    QComboBox.addItem = _wrap_first_str(QComboBox.addItem)
    QComboBox.insertItem = _wrap_args(QComboBox.insertItem, [1, 2])
    QComboBox.setItemText = _wrap_args(QComboBox.setItemText, [1])
    _add_items = QComboBox.addItems
    QComboBox.addItems = lambda self, items: _add_items(self, [t(i) for i in items])
    QAction.setText = _wrap_args(QAction.setText, [0])
    QAction.setToolTip = _wrap_args(QAction.setToolTip, [0])
    QMenu.setTitle = _wrap_args(QMenu.setTitle, [0])
    QMenu.addAction = _wrap_first_str(QMenu.addAction)
    QMenu.addSection = _wrap_first_str(QMenu.addSection)
    QMenu.addMenu = _wrap_first_str(QMenu.addMenu)
    QListWidgetItem.setText = _wrap_args(QListWidgetItem.setText, [0])
    QListWidgetItem.setToolTip = _wrap_args(QListWidgetItem.setToolTip, [0])
    QTreeWidgetItem.setText = _wrap_args(QTreeWidgetItem.setText, [1])
    QTableWidgetItem.setText = _wrap_args(QTableWidgetItem.setText, [0])
    for name in ("question", "information", "warning", "critical"):
        setattr(QMessageBox, name, _wrap_static(getattr(QMessageBox, name), [1, 2]))
    QMessageBox.setText = _wrap_args(QMessageBox.setText, [0])
    QMessageBox.setInformativeText = _wrap_args(QMessageBox.setInformativeText, [0])
    from PySide6.QtGui import QPainter

    _draw = QPainter.drawText  # painted words too (the avatars' role letters, the steps' icons)

    def draw_text(self, *args):
        return _draw(self, *[t(a) if isinstance(a, str) else a for a in args])
    QPainter.drawText = draw_text
    from PySide6.QtWidgets import QFormLayout, QListWidget, QStatusBar, QTableWidget, QToolTip, QTreeWidget

    # texts Qt turns into labels or items itself (no Python constructor runs for them)
    QFormLayout.addRow = _wrap_first_str(QFormLayout.addRow)
    QFormLayout.insertRow = _wrap_args(QFormLayout.insertRow, [1])
    QListWidget.addItem = _wrap_first_str(QListWidget.addItem)
    QListWidget.insertItem = _wrap_args(QListWidget.insertItem, [1])
    _list_items = QListWidget.addItems
    QListWidget.addItems = lambda self, items: _list_items(self, [t(i) for i in items])
    _tree_headers = QTreeWidget.setHeaderLabels
    QTreeWidget.setHeaderLabels = lambda self, items: _tree_headers(self, [t(i) for i in items])
    QTreeWidget.setHeaderLabel = _wrap_args(QTreeWidget.setHeaderLabel, [0])
    for name in ("setHorizontalHeaderLabels", "setVerticalHeaderLabels"):
        inner = getattr(QTableWidget, name)
        setattr(QTableWidget, name, lambda self, items, _inner=inner: _inner(self, [t(i) for i in items]))
    QStatusBar.showMessage = _wrap_args(QStatusBar.showMessage, [0])
    QToolTip.showText = _wrap_static(QToolTip.showText, [1])
    QInputDialog.getText = _wrap_static(QInputDialog.getText, [1, 2])
    QInputDialog.getItem = _wrap_static(QInputDialog.getItem, [1, 2])
    for name in ("getOpenFileName", "getOpenFileNames", "getSaveFileName", "getExistingDirectory"):
        setattr(QFileDialog, name, _wrap_static(getattr(QFileDialog, name), [1]))
