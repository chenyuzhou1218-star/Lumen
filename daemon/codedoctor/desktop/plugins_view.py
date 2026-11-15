"""插件: every tool beside Lumen on one page, big ones first. A click opens it; a word in the box finds it.

The list of small plugins comes from CodeTools itself, so that a new plugin appears here without anything changing in this file.
Each card carries the same line drawing as the tool's own window (a black square for the big tools, a grey one for the small
plugins, drawn by the group they belong to).
"""

from __future__ import annotations

import json
import os
import subprocess
import threading

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from codedoctor import makers, video
from codedoctor.desktop import locale
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.theme import C, FONT_FAMILY
from codedoctor.desktop.widgets import label

BIG = (("codefilm", "CodeFilm"), ("codesound", "CodeSound"), ("codepage", "CodePage"), ("codegame", "CodeGame"), ("code3d", "Code3D"), ("codecut", "CodeCut"), ("codedeck", "CodeDeck"), ("codedata", "CodeData"),
       ("codecad", "CodeCAD"), ("codelab", "CodeLab"), ("codepdf", "CodePDF"))
# CodeTools names its groups in the interface language; the drawing of a group is found by the name in either language
GROUP_KEY = {"创作": "创作", "create": "创作", "creative": "创作", "写作": "写作", "write": "写作", "writing": "写作", "文件": "文件", "files": "文件",
             "file": "文件", "documents": "文件", "开发": "开发", "develop": "开发", "development": "开发", "dev": "开发", "科学": "科学",
             "science": "科学", "游戏": "游戏", "games": "游戏", "game": "游戏"}
GLYPHS = {  # the drawings each tool's window uses (look.py in the tools folder), on a 16 x 16 grid
    "codefilm": '<rect x="2" y="2.6" width="12" height="10.8" rx="1.4"/><path d="M4.8 2.6v10.8M11.2 2.6v10.8M2 5.4h2.8M2 8h2.8M2 10.6h2.8M11.2 5.4H14M11.2 8H14M11.2 10.6H14"/>',
    "codepdf": '<path d="M4 1.8h5.2L12.6 5.2V14.2H4Z"/><path d="M9.2 1.8v3.4h3.4M6 9h4.6M6 11.4h3"/>',
    "codesound": '<path d="M6 12.2V3.4l7-1.4v8.6"/><circle cx="4.4" cy="12.2" r="1.7"/><circle cx="11.4" cy="10.6" r="1.7"/>',
    "codepage": '<rect x="2.2" y="2.2" width="11.6" height="11.6" rx="1.4"/><path d="M2.2 6h11.6M6.4 6v7.8"/>',
    "codegame": '<rect x="1.8" y="4.6" width="12.4" height="7.4" rx="3.6"/><path d="M5 7.4v2M4 8.4h2"/><circle cx="10.6" cy="7.8" r=".6"/><circle cx="11.8" cy="9.2" r=".6"/>',
    "code3d": '<path d="m8 1.8 5.4 3.1v6.2L8 14.2l-5.4-3.1V4.9Z"/><path d="m2.6 4.9 5.4 3.1 5.4-3.1M8 8v6.2"/>',
    "codecut": '<circle cx="4.4" cy="11.6" r="2"/><circle cx="11.6" cy="11.6" r="2"/><path d="M5.7 10 11.8 2.4M10.3 10 4.2 2.4"/>',
    "codedeck": '<rect x="1.8" y="2.6" width="12.4" height="8.6" rx="1.2"/><path d="M8 11.2v2.4M5.6 13.6h4.8M4.6 8.4l2.2-2.2 1.6 1.4 2.6-2.6"/>',
    "codedata": '<path d="M2.4 13.6h11.2"/><rect x="3.4" y="8" width="2.2" height="4.4" rx=".5"/><rect x="6.9" y="4.6" width="2.2" height="7.8" rx=".5"/><rect x="10.4" y="6.6" width="2.2" height="5.8" rx=".5"/>',
    "codecad": '<rect x="1.8" y="5.2" width="12.4" height="5.6" rx="1"/><path d="M4.4 5.2v2.2M7 5.2v3M9.6 5.2v2.2M12.2 5.2v3"/>',
    "codelab": '<path d="M6 1.8h4M6.6 1.8v4.4L2.8 12.4c-.4.7.1 1.6.9 1.6h8.6c.8 0 1.3-.9.9-1.6L9.4 6.2V1.8"/><path d="M4.4 10h7.2"/>',
    "创作": '<path d="M8 1.8 9.4 6.6 14.2 8 9.4 9.4 8 14.2 6.6 9.4 1.8 8 6.6 6.6Z"/>',
    "写作": '<path d="M10.6 2.6 13.4 5.4 6 12.8l-3.4.6.6-3.4Z"/><path d="M9.2 4 12 6.8"/>',
    "文件": '<path d="M1.8 4.4c0-.6.4-1 1-1h3.1l1.5 1.5h5.8c.6 0 1 .4 1 1v6.2c0 .6-.4 1-1 1H2.8c-.6 0-1-.4-1-1Z"/>',
    "开发": '<path d="m5.4 4.6-3.4 3.4 3.4 3.4"/><path d="m10.6 4.6 3.4 3.4-3.4 3.4"/><path d="m9 2.8-2 10.4"/>',
    "科学": '<path d="M6 1.8h4M6.6 1.8v4.4L2.8 12.4c-.4.7.1 1.6.9 1.6h8.6c.8 0 1.3-.9.9-1.6L9.4 6.2V1.8"/><path d="M4.4 10h7.2"/>',
    "游戏": '<rect x="1.8" y="4.6" width="12.4" height="7.4" rx="3.6"/><path d="M5 7.4v2M4 8.4h2"/><circle cx="10.6" cy="7.8" r=".6"/><circle cx="11.8" cy="9.2" r=".6"/>',
    "search": '<circle cx="7" cy="7" r="4.4"/><path d="m10.3 10.3 3.3 3.3"/>',
}
INK, INK2, INK3, RULE, EDGE2 = "#111113", "#5f5f66", "#9a9aa2", "#ededee", "#d6d6db"
CARD_WIDTH = 200
TINT = {}  # kept for anything that still reads it; the cards are no longer coloured by tool


def _svg(name: str, color: str, stroke: float = 1.4) -> QByteArray:
    body = GLYPHS.get(name, GLYPHS["创作"])
    return QByteArray(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" stroke="{color}" stroke-width="{stroke}" '
                      f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'.encode())


def glyph_icon(name: str, color: str = INK3, size: int = 16) -> QIcon:
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    QSvgRenderer(_svg(name, color)).render(p)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


class Card(QFrame):
    clicked = Signal()

    def __init__(self, name: str, about: str, glyph: str, big: bool):
        super().__init__()
        self.setObjectName("PluginCard")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(104 if big else 96)
        self.setMinimumWidth(180)
        self.name, self.about, self.glyph, self.big = name, about, glyph, big
        self.setToolTip(about)

    def mouseReleaseEvent(self, e):
        if self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hover = self.underMouse()
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        if hover:  # a soft lift: two faint rings under the card
            for i, a in ((3, 10), (1.5, 16)):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(17, 17, 19, a))
                p.drawRoundedRect(r.adjusted(-i + 1, -i + 2.5, i - 1, i + 1.5), 13 + i, 13 + i)
        p.setPen(QColor(EDGE2 if hover else RULE))
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(r, 12, 12)
        box = QRectF(16, 16, 30, 30)
        p.setPen(Qt.NoPen if self.big else QColor(RULE))
        p.setBrush(QColor(INK if self.big else "#f6f6f7"))
        p.drawRoundedRect(box, 8, 8)
        f = QFont(FONT_FAMILY)
        if self.big:
            QSvgRenderer(_svg(self.glyph, "#ffffff", 1.5)).render(p, box.adjusted(7, 7, -7, -7))
        else:  # a small plugin: its first character, so that a row of them tells apart at a glance
            f.setPixelSize(13)
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.setPen(QColor(INK))
            p.drawText(box, Qt.AlignCenter, self.name[:1].upper())
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(INK))
        p.drawText(QRectF(56, 16, self.width() - 72, 30), Qt.AlignVCenter | Qt.AlignLeft, p.fontMetrics().elidedText(self.name, Qt.ElideRight, self.width() - 80))
        if hover:
            p.setPen(QColor(INK3))
            f.setPixelSize(15)
            f.setWeight(QFont.Normal)
            p.setFont(f)
            p.drawText(QRectF(self.width() - 34, 16, 18, 30), Qt.AlignVCenter | Qt.AlignRight, "›")
        f.setPixelSize(12)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        p.setPen(QColor(INK2))
        text = QRectF(16, 56, self.width() - 32, self.height() - 64)
        lines = self._lines(p, self.about, text.width(), 2)
        p.drawText(text, Qt.AlignTop | Qt.AlignLeft, "\n".join(lines))
        p.end()

    @staticmethod
    def _lines(p: QPainter, words: str, width: float, most: int) -> list:
        """At most `most` lines, the last one ending in … when the words do not fit."""
        fm, out, line = p.fontMetrics(), [], ""
        for ch in words:
            if fm.horizontalAdvance(line + ch) > width:
                out.append(line)
                line = ch
                if len(out) == most:
                    out[-1] = fm.elidedText(out[-1] + words[len("".join(out)):], Qt.ElideRight, int(width))
                    return out
            else:
                line += ch
        if line:
            out.append(line)
        return out[:most]


class PluginsPage(QWidget):
    ready = Signal(list)

    def __init__(self):
        super().__init__()
        self.plugins: list | None = None
        self.cards: list = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 12)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(label(tr("plugins"), "PageTitle"))
        self.count = QLabel("")
        self.count.setStyleSheet(f"color:{INK2};background:#f4f4f5;border-radius:5px;padding:1px 7px;font-size:11.5px;")
        self.count.setFixedHeight(20)
        head.addWidget(self.count, 0, Qt.AlignVCenter)
        head.addStretch(1)
        outer.addLayout(head)
        self.box = QLineEdit()
        self.box.setPlaceholderText(locale.t("找一个插件"))
        self.box.addAction(QAction(glyph_icon("search"), "", self.box), QLineEdit.LeadingPosition)
        self.box.setStyleSheet(f"QLineEdit{{background:#fafafa;border:1px solid transparent;border-radius:9px;padding:7px 10px 7px 4px;}}"
                               f"QLineEdit:hover{{border-color:#e3e3e6;}}QLineEdit:focus{{background:#ffffff;border-color:{INK};}}")
        self.box.textChanged.connect(lambda _: self.fill())
        outer.addWidget(self.box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        self.inner = QWidget()
        self.col = QVBoxLayout(self.inner)
        self.col.setContentsMargins(0, 4, 8, 16)
        self.col.setSpacing(10)
        scroll.setWidget(self.inner)
        outer.addWidget(scroll, 1)
        self.ready.connect(self._loaded)
        self.columns = 0
        self.message = ""

    def load(self) -> None:
        """Python has to start to list them: not on the window's own thread. A list read in another language is read again."""
        from codedoctor.desktop import i18n

        if self.plugins is not None and getattr(self, "lang", None) != i18n.language() and not getattr(self, "_reading", False):
            self.plugins = None
        if self.plugins is None:
            self.lang = i18n.language()
            self._reading = True
            self.plugins = []
            threading.Thread(target=self._read, daemon=True).start()
        self.fill()

    def _read(self) -> None:
        from codedoctor.desktop import i18n

        where = makers.home("codetools")
        found = []
        if where is not None:
            try:  # the plugins say their names and notes in the language of the window (LUMEN_LANG, read by the tool's own i18n.py)
                out = subprocess.run([video.python(), str(where / "codetools.py"), "list"], capture_output=True, timeout=60, creationflags=0x08000000 if os.name == "nt" else 0,
                                     env={**os.environ, "LUMEN_LANG": i18n.language(), "PYTHONIOENCODING": "utf-8"})
                found = json.loads(out.stdout.decode("utf-8", "replace").strip().splitlines()[-1]).get("plugins", [])
            except (OSError, ValueError, IndexError, subprocess.SubprocessError):
                found = []
        self.ready.emit(found)

    def _loaded(self, found: list) -> None:
        self._reading = False
        self.plugins = found
        from codedoctor.desktop import i18n

        if getattr(self, "lang", None) != i18n.language():  # the language changed while it was being read: read again
            self.plugins = None
            self.load()
            return
        self.fill()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        columns = max(1, (self.width() - 52) // (CARD_WIDTH + 12))  # 2 columns from about 470 px, so a narrow window is not one long list
        if columns != self.columns:
            self.columns = columns
            QTimer.singleShot(0, self.fill)

    def fill(self) -> None:
        while self.col.count():
            item = self.col.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        needle = self.box.text().strip().lower()
        columns = max(1, self.columns or 3)
        shown = 0

        def section(title: str, glyph: str, entries: list, big: bool) -> None:
            nonlocal shown
            if not entries:
                return
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(2, 14 if shown else 4, 0, 2)
            h.setSpacing(8)
            mark = QLabel()
            mark.setPixmap(glyph_icon(glyph, INK3, 14).pixmap(14, 14))
            h.addWidget(mark)
            head = QLabel(title)
            head.setStyleSheet(f"color:{INK};font-weight:600;font-size:12.5px;")
            h.addWidget(head)
            n = QLabel(str(len(entries)))
            n.setStyleSheet(f"color:{INK3};font-size:12px;")
            h.addWidget(n)
            h.addStretch(1)
            self.col.addWidget(row)
            grid_box = QWidget()
            grid = QGridLayout(grid_box)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(12)
            for i, (name, about, mark_name, act) in enumerate(entries):
                card = Card(name, about, mark_name, big)
                card.clicked.connect(act)
                grid.addWidget(card, i // columns, i % columns)
            for c in range(columns):
                grid.setColumnStretch(c, 1)
            self.col.addWidget(grid_box)
            shown += len(entries)

        big = []
        for key, name in BIG:
            about = tr(f"{key}_sub")
            if not needle or needle in f"{key} {name} {about}".lower():
                big.append((name, about, key, lambda k=key: makers.open_app(k)))
        section(locale.t("大工具"), "codepage", big, True)
        groups: dict = {}
        for p in self.plugins or []:
            if not needle or needle in f"{p['id']} {p['name']} {p['blurb']}".lower():
                groups.setdefault(p["group"], []).append((p["name"], p["blurb"], p["group"], lambda i=p["id"]: makers.open_app("codetools", i)))
        for group, entries in groups.items():
            section(locale.t(group), group, entries, False)
        if not shown:
            empty = QLabel(locale.t("没有找到。换个词试试。") if needle else "")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{INK3};padding:40px;")
            self.col.addWidget(empty)
        total = len(BIG) + len(self.plugins or [])
        self.count.setText(f"{shown} / {total}" if needle else str(total))
        self.col.addStretch(1)
