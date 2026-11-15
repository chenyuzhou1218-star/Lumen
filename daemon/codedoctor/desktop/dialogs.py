"""One notice window for everything that can get long (save results, errors, reminders).

The summary is one or two sentences; details go into a fixed-height list the mouse wheel scrolls, so a notice
never grows taller than the screen however many items it has.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout

from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import hbox, label

KIND = {"ok": ("✓", C["green"], C["green_soft"]), "info": ("i", C["blue"], C["blue_soft"]),
        "warning": ("!", C["amber"], C["amber_soft"]), "error": ("✕", C["red"], C["red_soft"])}


class Notice(QDialog):
    def __init__(self, parent, title: str, text: str, *, kind: str = "info", details: list[str] | None = None,
                 details_title: str = "", buttons: tuple[str, ...] = ("好",)):
        super().__init__(parent)
        self.choice: str | None = None
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self.setMaximumWidth(720)
        glyph, fg, bg = KIND.get(kind, KIND["info"])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(12)
        icon = label(glyph, size=16, bold=True, color=fg)
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 15px; font-size: 16px; font-weight: 700;")
        lay.addWidget(hbox(icon, label(title, size=16, bold=True), None, spacing=10))
        body = label(text, wrap=True, size=14, selectable=True)
        lay.addWidget(body)
        if details:
            if details_title:
                lay.addWidget(label(details_title, size=13, bold=True, color=C["text2"]))
            box = QTextBrowser()
            box.setOpenLinks(False)
            box.setStyleSheet(f"QTextBrowser {{ background: #ffffff; border: 1px solid {C['border']}; border-radius: 10px; "
                              f"padding: 8px; font-size: 13px; }}")
            box.setHtml("".join(f"<p style='margin:0 0 8px 0'>• {_esc(d)}</p>" for d in details))
            screen = QApplication.primaryScreen()
            cap = int(screen.availableGeometry().height() * 0.45) if screen else 360
            box.document().setTextWidth(500)  # the list is as tall as its text, up to the cap; beyond that it scrolls
            box.setFixedHeight(max(60, min(cap, int(box.document().size().height()) + 26)))
            lay.addWidget(box)
        row = QHBoxLayout()
        row.addStretch(1)
        for i, text_ in enumerate(buttons):
            b = QPushButton(text_)
            if i == 0:
                b.setObjectName("Primary")
                b.setDefault(True)
            b.clicked.connect(lambda _=False, t=text_: self._choose(t))
            row.addWidget(b)
        lay.addLayout(row)

    def _choose(self, text: str) -> None:
        self.choice = text
        self.accept()


def ask_text(parent, title: str, text: str, value: str = "") -> str | None:
    """One line from the user; None if they closed it."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(420)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(22, 20, 22, 16)
    lay.setSpacing(12)
    lay.addWidget(label(title, size=16, bold=True))
    if text:
        lay.addWidget(label(text, wrap=True, size=13, color=C["text2"]))
    box = QLineEdit(value)
    box.selectAll()
    box.returnPressed.connect(dlg.accept)
    lay.addWidget(box)
    row = QHBoxLayout()
    row.addStretch(1)
    ok = QPushButton("好")
    ok.setObjectName("Primary")
    ok.setDefault(True)
    ok.clicked.connect(dlg.accept)
    later = QPushButton("算了")
    later.clicked.connect(dlg.reject)
    row.addWidget(ok)
    row.addWidget(later)
    lay.addLayout(row)
    return box.text() if dlg.exec() else None


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


def notice(parent, title: str, text: str, **kw) -> str | None:
    """Show a notice; returns the text of the button clicked (None when closed)."""
    dlg = Notice(parent, title, text, **kw)
    dlg.exec()
    return dlg.choice
