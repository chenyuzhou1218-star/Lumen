"""打开电脑操作: which windows the agents may see and act in.

A real bug (2026-11-10): the switch saved screenshots and input on without a window list, which the configuration
rightly refuses ("computer.windows must list the window titles agents may see and act in"), so it never worked. Now
it asks: the windows open right now, ticked by the person, and a title can be typed for one that is not open yet.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout)

from codedoctor.desktop.theme import C


def open_titles(own: str = "Lumen") -> list[str]:
    """Titles of the windows open now, topmost first, without Lumen's own."""
    try:
        from codedoctor.computer.desktop import default_desktop

        desk = default_desktop()
        wins = desk.windows(minimized=True) if desk is not None else []
    except Exception:
        return []
    seen, out = set(), []
    for w in wins:
        title = (w.title or "").strip()
        if title and title not in seen and own not in title:
            seen.add(title)
            out.append(title)
    return out


class WindowPick(QDialog):
    """Tick the windows; 打开 is enabled once there is at least one."""

    def __init__(self, parent=None, titles: list[str] | None = None, chosen: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("打开电脑操作")
        self.setMinimumSize(460, 420)
        self.setStyleSheet(f"QDialog {{ background: white; }} QListWidget {{ border: 1px solid {C['border']}; border-radius: 10px; padding: 4px; }}"
                           f"QListWidget::item {{ padding: 6px 4px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        head = QLabel("AI 可以看和操作哪些窗口？")
        head.setStyleSheet(f"font-size: 17px; font-weight: 600; color: {C['ink']};")
        note = QLabel("只勾你愿意让它截图、点击和打字的窗口。每一步仍然要你批准（可以在输入框下面改）。")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {C['text2']}; font-size: 13px;")
        lay.addWidget(head)
        lay.addWidget(note)
        self.list = QListWidget()
        chosen = set(chosen or [])
        for title in titles if titles is not None else open_titles():
            self._add(title, title in chosen)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.extra = QLineEdit()
        self.extra.setPlaceholderText("没打开的窗口：输入它的标题（或标题里的一段）")
        add = QPushButton("加上")
        add.setObjectName("Ghost")
        add.clicked.connect(self._add_typed)
        self.extra.returnPressed.connect(self._add_typed)
        row.addWidget(self.extra, 1)
        row.addWidget(add)
        lay.addLayout(row)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("打开电脑操作")
        self.ok.setObjectName("Primary")
        self.ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)
        self.list.itemChanged.connect(lambda _=None: self._update())
        self._update()

    def _add(self, title: str, on: bool) -> None:
        item = QListWidgetItem(title)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.list.addItem(item)

    def _add_typed(self) -> None:
        text = self.extra.text().strip()
        if text and text not in self.titles(all_items=True):
            self._add(text, True)
        self.extra.clear()
        self._update()

    def titles(self, all_items: bool = False) -> list[str]:
        out = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if all_items or item.checkState() == Qt.Checked:
                out.append(item.text())
        return out

    def _update(self) -> None:
        self.ok.setEnabled(bool(self.titles()))
