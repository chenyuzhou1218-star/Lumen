"""Ctrl+K: one box that reaches everything. Type a few letters of a chat, a page or an action, Enter goes there.

The window hands in a list of Item; this file only searches and shows it, so an action is added in app.py and nowhere else.
Letters match in order, not only side by side: "szwg" finds 设置 外观 by its keywords too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog, QFrame, QLineEdit, QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle, QVBoxLayout

from codedoctor.desktop.theme import C, FONT_FAMILY
from codedoctor.desktop.widgets import shadow


@dataclass
class Item:
    title: str
    group: str
    run: Callable[[], None]
    keys: str = ""   # more words it answers to
    hint: str = ""   # a shortcut, or where it lives


def score(needle: str, item: Item) -> int:
    """0: not a match. Higher is better: a start beats a middle, a run beats scattered letters."""
    if not needle:
        return 1
    hay = f"{item.title} {item.keys}".lower()
    needle = needle.lower()
    at = hay.find(needle)
    if at == 0:
        return 100
    if at > 0:
        return 80 - min(at, 30)
    place = 0
    for ch in needle:  # letters in order, with gaps
        place = hay.find(ch, place) + 1
        if place == 0:
            return 0
    return 10


def search(items: list[Item], needle: str, most: int = 40) -> list[Item]:
    found = [(score(needle, it), i, it) for i, it in enumerate(items)]
    return [it for s, _, it in sorted((f for f in found if f[0]), key=lambda f: (-f[0], f[1]))][:most]


class _Row(QStyledItemDelegate):
    """A row: the title, its group in grey, the shortcut on the right. Painted, so that a long chat title is cut, not wrapped."""

    def sizeHint(self, option, index):  # noqa: N802 (Qt naming)
        size = super().sizeHint(option, index)
        size.setHeight(40)
        return size

    def paint(self, p, option, index):
        item: Item = index.data(Qt.UserRole)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(6, 2, -6, -2)
        if option.state & QStyle.State_Selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["sidebar_hover"]))
            p.drawRoundedRect(r, 10, 10)
        fm = option.fontMetrics
        right = fm.horizontalAdvance(item.hint) + 14 if item.hint else 0
        group_w = fm.horizontalAdvance(item.group) + 12
        p.setPen(QColor(C["ink"]))
        title = fm.elidedText(item.title, Qt.ElideRight, int(r.width() - right - group_w - 24))
        p.drawText(r.adjusted(14, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, title)
        p.setPen(QColor(C["text3"]))
        p.drawText(r.adjusted(14 + fm.horizontalAdvance(title) + 10, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, item.group)
        if item.hint:
            p.drawText(r.adjusted(0, 0, -14, 0), Qt.AlignVCenter | Qt.AlignRight, item.hint)
        p.restore()


class CommandPalette(QDialog):
    """more(text) adds what takes a moment to find, a little after the typing stops."""

    def __init__(self, parent, items: list[Item], more: Callable[[str], list[Item]] | None = None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.items = items
        self.more = more
        self.deeper = QTimer(self)
        self.deeper.setSingleShot(True)
        self.deeper.setInterval(260)
        self.deeper.timeout.connect(self._go_deeper)
        self.chosen: Item | None = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 26, 26, 26)
        card = QFrame()
        card.setObjectName("Palette")
        card.setStyleSheet(f"#Palette {{ background: white; border: 1px solid {C['border']}; border-radius: 16px; }}")
        shadow(card, 34, 40, 6)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        self.box = QLineEdit()
        self.box.setPlaceholderText("跳到聊天、页面，或做一件事")
        self.box.setStyleSheet(f"QLineEdit {{ border: none; background: transparent; padding: 8px 12px; font-size: 16px; color: {C['ink']}; font-family: {FONT_FAMILY}; }}")
        self.box.textChanged.connect(self.fill)
        self.box.installEventFilter(self)
        lay.addWidget(self.box)
        self.list = QListWidget()
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setItemDelegate(_Row(self.list))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setStyleSheet(f"QListWidget {{ background: transparent; outline: none; font-size: 14px; font-family: {FONT_FAMILY}; }}")
        self.list.itemActivated.connect(self._take)
        self.list.itemClicked.connect(self._take)
        lay.addWidget(self.list)
        outer.addWidget(card)
        self.fill("")

    def fit(self, window) -> None:
        """Under the top of the window, as wide as it has room for."""
        width = min(640, max(320, window.width() - 80))
        height = min(520, max(260, window.height() - 120))
        self.resize(width, height)
        spot = window.mapToGlobal(window.rect().topLeft())
        self.move(spot.x() + (window.width() - width) // 2, spot.y() + 40)

    def fill(self, needle: str) -> None:
        self.list.clear()
        for it in search(self.items, needle.strip()):
            row = QListWidgetItem(it.title)
            row.setData(Qt.UserRole, it)
            self.list.addItem(row)
        if self.list.count():
            self.list.setCurrentRow(0)
        if self.more is not None:
            self.deeper.start()

    def _go_deeper(self) -> None:
        needle = self.box.text().strip()
        if len(needle) < 2:
            return
        for it in self.more(needle):
            row = QListWidgetItem(it.title)
            row.setData(Qt.UserRole, it)
            self.list.addItem(row)
        if self.list.count() and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)

    def _take(self, row: QListWidgetItem) -> None:
        self.chosen = row.data(Qt.UserRole)
        self.accept()

    def eventFilter(self, obj, e):
        if obj is self.box and e.type() == QEvent.KeyPress:
            key = e.key()
            if key in (Qt.Key_Down, Qt.Key_Up) and self.list.count():
                step = 1 if key == Qt.Key_Down else -1
                self.list.setCurrentRow((self.list.currentRow() + step) % self.list.count())
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                row = self.list.currentItem()
                if row is not None:
                    self._take(row)
                return True
        return super().eventFilter(obj, e)


def ask(window, items: list[Item], more=None) -> None:
    """Show it over the window, and do what was chosen once it has gone."""
    dialog = CommandPalette(window, items, more)
    dialog.fit(window)
    dialog.box.setFocus()
    if dialog.exec() and dialog.chosen is not None:
        dialog.chosen.run()
