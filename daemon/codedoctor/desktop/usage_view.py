"""用量: how much this project used, from the journal: today, seven days, everything; each day as a bar; each AI on a line.

New tokens and tokens read back from a cache are kept apart: an engine reads its history again every turn, so one sum
would say 17 million for a run that cost 1.31 dollars. Dollars are shown only as the engines report them.
"""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from codedoctor.desktop import chat_tools
from codedoctor.desktop import prefs as ui_prefs
from codedoctor.desktop.theme import C, FONT_FAMILY
from codedoctor.desktop.widgets import Card, CardGrid, label

DAYS = 14


def short(n: float) -> str:
    """12,345 as 1.2 万, in the unit a person reads."""
    if ui_prefs.load()["language"] not in ("zh", "zh-TW"):
        return f"{n / 1_000_000:.1f}M" if n >= 1_000_000 else f"{n / 1000:.1f}k" if n >= 1000 else f"{int(n):,}"
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f} 亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f} 万"
    return f"{int(n):,}"


class Bars(QWidget):
    """New tokens per day, painted: the last bar is today, a day without work keeps its place."""

    def __init__(self):
        super().__init__()
        self.values: list[tuple[str, int]] = []
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_values(self, values: list[tuple[str, int]]) -> None:
        self.values = values
        self.update()

    def paintEvent(self, _e):
        if not self.values:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(FONT_FAMILY)
        font.setPixelSize(11)
        p.setFont(font)
        top = max(v for _, v in self.values) or 1
        n = len(self.values)
        slot = self.width() / n
        wide = min(26.0, slot * .62)
        floor = self.height() - 22
        for i, (day, value) in enumerate(self.values):
            x = i * slot + (slot - wide) / 2
            h = max(3.0, (floor - 18) * value / top) if value else 3.0
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["accent"] if value else C["border"]))
            p.drawRoundedRect(QRectF(x, floor - h, wide, h), 5, 5)
            if value and (value == top or n <= 7):
                p.setPen(QColor(C["text2"]))
                p.drawText(QRectF(i * slot - 20, floor - h - 16, slot + 40, 14), Qt.AlignCenter, short(value))
            if i % max(1, n // 7) == 0 or i == n - 1:
                p.setPen(QColor(C["text3"]))
                p.drawText(QRectF(i * slot - 12, floor + 4, slot + 24, 14), Qt.AlignCenter, day[5:].replace("-", "/"))
        p.end()


class UsagePage(QWidget):
    def __init__(self, daemon):
        super().__init__()
        self.d = daemon
        self.seen: tuple | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(28, 24, 28, 24)
        self.lay.setSpacing(14)
        self.lay.addWidget(label("用量", "PageTitle"))
        self.lay.addWidget(label("这个项目里所有 AI 的回答加起来。新用量是真正新产生的；缓存重读是 AI 每一步把前文再读一遍，价格约十分之一。", wrap=True, size=13, color=C["text2"]))
        self.tiles: dict[str, tuple] = {}
        cards = []
        for key, title in (("today", "今天"), ("week", "最近 7 天"), ("all", "全部")):
            tile = Card(padding=16, spacing=4)
            big, small = label("0", size=24, bold=True), label("", wrap=True, size=12, color=C["text3"])
            tile.lay.addWidget(label(title, size=13, color=C["text2"]))
            tile.lay.addWidget(big)
            tile.lay.addWidget(small)
            self.tiles[key] = (big, small)
            cards.append(tile)
        self.lay.addWidget(CardGrid(cards, 200))
        chart = Card(padding=18, spacing=10)
        chart.lay.addWidget(label(f"最近 {DAYS} 天的新用量", size=15, bold=True))
        self.bars = Bars()
        chart.lay.addWidget(self.bars)
        self.lay.addWidget(chart)
        people = Card(padding=18, spacing=8)
        people.lay.addWidget(label("谁用得最多", size=15, bold=True))
        self.table = QVBoxLayout()
        self.table.setSpacing(6)
        people.lay.addLayout(self.table)
        self.lay.addWidget(people)
        self.lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def refresh(self, force: bool = False) -> None:
        rows = chat_tools.usage_rows(self.d)
        mark = (len(rows), date.today())
        if mark == self.seen and not force:
            return
        self.seen = mark
        today = date.today()
        days = [(today - timedelta(days=i)).isoformat() for i in range(DAYS - 1, -1, -1)]
        s = chat_tools.usage_summary(rows, today.isoformat(), days)
        for key, (big, small) in self.tiles.items():
            part = s[key]
            big.setText(short(part["fresh"]))
            small.setText(f"缓存重读 {short(part['cached'])} · {part['answers']} 次回答" + (f" · ${part['cost']:.2f}" if part["cost"] else ""))
        self.bars.set_values(s["by_day"])
        while self.table.count():
            item = self.table.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for who, fresh, cost, answers in s["by_who"][:12]:
            self.table.addWidget(label(f"{who}　{short(fresh)}　{answers} 次" + (f"　${cost:.2f}" if cost else ""), wrap=True, size=13, selectable=True))
        if not s["by_who"]:
            self.table.addWidget(label("还没有用量。问一个问题之后这里就有了。", size=13, color=C["text3"]))
