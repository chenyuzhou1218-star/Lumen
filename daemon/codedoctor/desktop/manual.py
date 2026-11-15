"""功能手册: what Lumen can do, in the ten interface languages (desktop/book/<language>.md).

Opened from 设置 → 帮助 → 功能手册, from the project picker (它能做什么？) and from the first-run wizard.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from codedoctor.desktop import i18n
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import label

BOOK = Path(__file__).with_name("book")
CSS = (f"QTextBrowser {{ background: rgba(255,255,255,175); border: 1px solid rgba(255,255,255,210); border-radius: 16px;"
       f" padding: 18px 26px; color: {C['text']}; font-size: 14px; selection-background-color: #bcd3f2; }}")


def text_of(lang: str) -> str:
    if lang == "zh-TW" and (BOOK / "zh.md").exists():  # the Chinese book, converted
        from codedoctor.desktop import zh_hant

        return zh_hant.convert((BOOK / "zh.md").read_text(encoding="utf-8"))
    path = BOOK / f"{lang}.md"
    if not path.exists():
        path = BOOK / "en.md"
    return path.read_text(encoding="utf-8")


class ManualView(QWidget):
    """The book with a language switch above it."""

    def __init__(self, lang: str | None = None, compact: bool = False):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0 if compact else 32, 0 if compact else 24, 0 if compact else 32, 0 if compact else 16)
        lay.setSpacing(12)
        head = QHBoxLayout()
        if not compact:
            head.addWidget(label(tr("n_book"), "PageTitle"))
        head.addStretch(1)
        head.addWidget(label(tr("book_lang"), size=13, color=C["text2"]))
        self.lang = QComboBox()
        for code, name in i18n.LANGS:
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(max(self.lang.findData(lang or i18n.language()), 0))
        head.addWidget(self.lang)
        lay.addLayout(head)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setStyleSheet(CSS)
        lay.addWidget(self.view, 1)
        self.lang.currentIndexChanged.connect(self._load)
        self._load()

    def _load(self, *_):
        self.view.setMarkdown(text_of(self.lang.currentData()))
        self.view.verticalScrollBar().setValue(0)


class ManualDialog(QDialog):
    def __init__(self, parent=None, lang: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("n_book"))
        self.resize(900, 760)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.addWidget(ManualView(lang, compact=True), 1)
        close = QPushButton("OK")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
