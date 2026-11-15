"""Code3D's window: the scene's code on the left, what Blender makes of it in the middle, what is in the scene on the right.

It drives the same command line agents use (code3d.py), and follows the project's files: when an agent changes scene.py or
renders, the window shows it. The middle picture is a real render, never a stand-in. "转一圈" renders small pictures all
the way round and a drag runs through them; "在 Blender 打开" gives the live 3D view.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time

from PySide6.QtCore import QEvent, QObject, QPoint, QProcess, QRect, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QCursor, QFont, QFontMetrics, QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextFormat)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QSplitter,
                               QStackedWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget)

import code3d as core
import look

BG, PANEL, LINE, INK, DIM, FAINT, ACCENT, RED = '#ffffff', '#ffffff', '#ededee', '#111113', '#5f5f66', '#9a9aa2', '#111113', '#c8322b'

THEME = look.THEME + f'''
QWidget {{ color:{INK}; }}
QMainWindow,QWidget#workspace {{ background:{BG}; }}
QFrame#topbar {{ background:{BG}; border-bottom:1px solid {LINE}; }}
QFrame#panel {{ background:{PANEL}; border:1px solid {LINE}; border-radius:12px; }}
QFrame#float {{ background:rgba(255,255,255,236); border:1px solid {LINE}; border-radius:12px; }}
QPushButton#chip {{ background:#ffffff; border:1px solid #e3e3e6; border-radius:13px; padding:0 11px; min-height:26px; max-height:26px; font-size:12px; color:{DIM}; }}
QPushButton#chip:hover {{ background:#f4f4f5; border-color:#cfcfd4; color:{INK}; }}
QLabel#stat {{ color:{INK}; font-size:18px; font-weight:600; }}
QLabel#brand {{ font-size:14px; font-weight:600; color:{INK}; }}
QLabel#project {{ color:{DIM}; font-size:13.5px; font-weight:500; }}
QLabel#title {{ font-size:12.5px; font-weight:600; color:{INK}; }}
QLabel#muted {{ color:{DIM}; font-size:12px; }}
QLabel#faint {{ color:{FAINT}; font-size:12px; }}
QLabel#status {{ color:{FAINT}; font-size:12px; }}
QLabel#hello {{ color:{INK}; font-size:22px; font-weight:650; }}
QPushButton#pill {{ background:transparent; border:0; border-radius:7px; padding:0 12px; min-height:26px; max-height:26px; color:{DIM}; font-size:12px; }}
QPushButton#pill:hover {{ color:{INK}; }}
QPushButton#pill:checked {{ background:#ffffff; color:{INK}; font-weight:600; border:1px solid {LINE}; }}
QPushButton#small {{ padding:0 12px; font-size:12px; border-radius:8px; }}
QToolButton {{ background:transparent; border:0; border-radius:8px; padding:6px; }}
QToolButton:hover {{ background:#f4f4f5; }}
QPlainTextEdit {{ background:transparent; border:0; selection-background-color:#dfe5ff; selection-color:{INK}; }}
QPlainTextEdit#console {{ background:#fafafa; border:1px solid {LINE}; border-radius:9px; padding:6px; font-family:"Cascadia Mono",Consolas,"Microsoft YaHei UI"; font-size:12px; color:{DIM}; }}
QListWidget {{ font-size:12px; }}
QSpinBox,QComboBox {{ min-height:28px; max-height:28px; }}
QMenu::item:disabled {{ color:#c3c3c9; }}
QSplitter::handle {{ background:{BG}; }}
QProgressBar {{ border:0; background:#ededee; border-radius:1px; max-height:2px; }}
QProgressBar::chunk {{ background:{INK}; border-radius:1px; }}
QMessageBox {{ background:#ffffff; }}
QPlainTextEdit#code {{ font-family:"Cascadia Code","Cascadia Mono",Consolas,"Microsoft YaHei UI"; font-size:12.5px; border:0; padding:0; }}
'''

ICONS = {
    'code': '<path d="m8 8-5 4 5 4M16 8l5 4-5 4M14 5l-4 14"/>',
    'panel': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
    'cube': '<path d="M12 2.5 20.5 7v10L12 21.5 3.5 17V7z"/><path d="M3.5 7 12 11.8 20.5 7M12 11.8v9.7"/>',
    'open': '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/><path d="M3 9h18"/>',
    'save': '<path d="M4 3h13l4 4v14H3V3zM7 3v6h10V3M7 21v-8h10v8"/>',
    'plus': '<path d="M12 4v16M4 12h16"/>',
    'export': '<rect x="3" y="10" width="18" height="11" rx="2"/><path d="M12 14V2m-4 4 4-4 4 4"/>',
    'spark': '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
    'play': '<path d="m8 4 12 8-12 8z"/>',
    'turn': '<path d="M3 12c0-2.5 4-4.500 9-4.500s9 2 9 4.500-4 4.500-9 4.500c-1 0-2-.1-3-.2"/><path d="m11 13.500-3 3 3 3"/>',
    'blender': '<circle cx="14" cy="13" r="6.500"/><circle cx="14" cy="13" r="2.300"/><path d="M8 13H2.500M9.500 8.500 4 8"/>',
    'stop': '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    'film': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18m10-18v18M3 8h4m-4 8h4M17 8h4m-4 8h4"/>',
}


def icon(name: str, colour: str = '#5f5f66', size: int = 18) -> QIcon:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{colour}" '
           f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g></svg>')
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    QSvgRenderer(svg.encode()).render(p)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def button(text: str, fn=None, kind: str = '', glyph: str = '') -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    if glyph:
        b.setIcon(icon(glyph, '#ffffff' if kind == 'primary' else '#5f5f66', 15))
        b.setIconSize(QSize(16, 16))
    b.setCursor(Qt.PointingHandCursor)
    if fn:
        b.clicked.connect(lambda _=False: fn())
    return b


def tool(name: str, tip: str, fn) -> QToolButton:
    b = QToolButton()
    b.setIcon(icon(name))
    b.setIconSize(QSize(18, 18))
    b.setToolTip(tip)
    b.setAccessibleName(tip)
    b.setCursor(Qt.PointingHandCursor)
    b.clicked.connect(lambda _=False: fn())
    return b


def text(words: str, name: str = '') -> QLabel:
    w = QLabel(words)
    if name:
        w.setObjectName(name)
    return w


def panel() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName('panel')
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(8)
    return f, lay


class Highlighter(QSyntaxHighlighter):
    """Python, with the kit's calls standing out: they are the words a scene is made of."""
    RULES = [(r'\b(?:import|from|as|def|class|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|with|try|except|lambda|pass|break|continue)\b', '#a626a4'),
             (r'\bc3d\.\w+', '#2f6bff'), (r'\bbpy\.\w+', '#2f6bff'), (r'\b-?\d+\.?\d*\b|\.\d+\b', '#b06a00'), (r"'[^'\n]*'|\"[^\"\n]*\"", '#2e8b57'),
             (r'#.*$', '#a0a0a8')]

    def __init__(self, doc):
        super().__init__(doc)
        self.rules = []
        for pattern, colour in self.RULES:
            f = QTextCharFormat()
            f.setForeground(QColor(colour))
            self.rules.append((re.compile(pattern), f))

    def highlightBlock(self, line: str) -> None:
        for rule, f in self.rules:
            for m in rule.finditer(line):
                self.setFormat(m.start(), m.end() - m.start(), f)


class Gutter(QWidget):
    def __init__(self, edit):
        super().__init__(edit)
        self.edit = edit

    def sizeHint(self):
        return QSize(self.edit.gutter_width(), 0)

    def paintEvent(self, e):
        self.edit.paint_gutter(e)


class CodeEdit(QPlainTextEdit):
    """scene.py: line numbers, Python colours, four-space tabs, and the line Blender stopped at marked in red."""

    def __init__(self):
        super().__init__()
        f = QFont('Cascadia Code')
        f.setStyleHint(QFont.Monospace)
        f.setFamilies(['Cascadia Code', 'Consolas', 'Microsoft YaHei UI'])
        f.setPixelSize(14)
        self.setFont(f)
        self.setObjectName('code')
        self.setTabStopDistance(QFontMetrics(f).horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setPlaceholderText('# 这里写场景的代码')
        self.gutter = Gutter(self)
        self.error_line = None
        self.highlighter = Highlighter(self.document())
        self.blockCountChanged.connect(lambda _: self.setViewportMargins(self.gutter_width(), 0, 0, 0))
        self.updateRequest.connect(self._scrolled)
        self.cursorPositionChanged.connect(self.mark)
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)
        self.mark()

    def gutter_width(self) -> int:
        return 22 + self.fontMetrics().horizontalAdvance('9') * max(3, len(str(self.blockCount())))

    def _scrolled(self, rect, dy) -> None:
        self.gutter.scroll(0, dy) if dy else self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        r = self.contentsRect()
        self.gutter.setGeometry(QRect(r.left(), r.top(), self.gutter_width(), r.height()))

    def paint_gutter(self, e) -> None:
        p = QPainter(self.gutter)
        p.setFont(self.font())
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        now = self.textCursor().blockNumber()
        while block.isValid() and top <= e.rect().bottom():
            n = block.blockNumber()
            if block.isVisible():
                p.setPen(QColor(RED if n + 1 == self.error_line else '#5f5f66' if n == now else '#c2c2c8'))
                p.drawText(0, top, self.gutter.width() - 12, self.fontMetrics().height(), Qt.AlignRight, str(n + 1))
            block = block.next()
            top += int(self.blockBoundingRect(block).height()) if block.isValid() else 0
        p.end()

    def mark(self) -> None:
        marks = []
        now = QTextEdit.ExtraSelection()
        now.format.setBackground(QColor('#f7f7f8'))
        now.format.setProperty(QTextFormat.FullWidthSelection, True)
        now.cursor = self.textCursor()
        now.cursor.clearSelection()
        marks.append(now)
        if self.error_line:
            block = self.document().findBlockByNumber(self.error_line - 1)
            if block.isValid():
                bad = QTextEdit.ExtraSelection()
                bad.format.setBackground(QColor(200, 50, 43, 22))
                bad.format.setProperty(QTextFormat.FullWidthSelection, True)
                bad.cursor = QTextCursor(block)
                marks.append(bad)
        self.setExtraSelections(marks)
        self.gutter.update()

    def show_error(self, line) -> None:
        self.error_line = line
        self.mark()
        if line:
            self.setTextCursor(QTextCursor(self.document().findBlockByNumber(line - 1)))
            self.centerCursor()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Tab:
            self.insertPlainText('    ')
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            line = self.textCursor().block().text()
            pad = line[:len(line) - len(line.lstrip())] + ('    ' if line.rstrip().endswith(':') else '')
            super().keyPressEvent(e)
            self.insertPlainText(pad)
            return
        super().keyPressEvent(e)


class Viewport(QWidget):
    """The render, fitted and rounded. With a turn in hand, dragging runs through the angles."""
    MARGIN = 0

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 200)
        self.picture: QPixmap | None = None
        self.turn: list[QPixmap] = []
        self.index = 0
        self.grabbed = None
        self.note = ''
        self.setMouseTracking(True)

    def show_picture(self, path) -> bool:
        pix = QPixmap(str(path))
        if pix.isNull():
            return False
        self.picture, self.turn = pix, []
        self.setCursor(Qt.ArrowCursor)
        self.update()
        return True

    def show_turn(self, paths) -> None:
        self.turn = [p for p in (QPixmap(str(x)) for x in paths) if not p.isNull()]
        self.index = 0
        self.setCursor(Qt.OpenHandCursor if self.turn else Qt.ArrowCursor)
        self.update()

    def clear(self) -> None:
        self.picture, self.turn = None, []
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(area, 10, 10)
        p.fillPath(clip, QColor('#fafafa'))
        pix = self.turn[self.index % len(self.turn)] if self.turn else self.picture
        if pix is not None:
            shown = pix.size().scaled(self.size() - QSize(28, 28), Qt.KeepAspectRatio)  # a quiet margin round the picture
            r = QRectF((self.width() - shown.width()) / 2, (self.height() - shown.height()) / 2, shown.width(), shown.height())
            inner = QPainterPath()
            inner.addRoundedRect(r, 8, 8)
            p.setClipPath(inner)
            p.drawPixmap(r, pix, QRectF(pix.rect()))
            p.setClipping(False)
        if self.note:
            p.setFont(QFont('Microsoft YaHei UI', 9))
            w = p.fontMetrics().horizontalAdvance(self.note) + 22
            r = QRectF((self.width() - w) / 2, 58, w, 26)  # under the view switch, clear of the buttons at the bottom
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(17, 17, 19, 214))
            p.drawRoundedRect(r, 13, 13)
            p.setPen(QColor('#ffffff'))
            p.drawText(r, Qt.AlignCenter, self.note)
        p.setPen(QPen(QColor(LINE), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(clip)
        p.end()

    def mousePressEvent(self, e):
        if self.turn:
            self.grabbed = (e.position().x(), self.index)
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self.grabbed and self.turn:
            step = max(14, self.width() / (2 * len(self.turn)))
            self.index = (self.grabbed[1] - int((e.position().x() - self.grabbed[0]) / step)) % len(self.turn)
            self.update()

    def mouseReleaseEvent(self, _e):
        self.grabbed = None
        if self.turn:
            self.setCursor(Qt.OpenHandCursor)


class FlowRow(QWidget):
    """Small buttons that wrap to the width they get."""

    def __init__(self):
        super().__init__()
        self.items = []

    def add(self, w) -> None:
        w.setParent(self)
        self.items.append(w)

    def place(self, width: int) -> int:
        x = y = 0
        line = 0
        for w in self.items:
            hint = w.sizeHint()
            if x and x + hint.width() > width:
                x, y = 0, y + line + 5
                line = 0
            w.setGeometry(x, y, hint.width(), hint.height())
            x += hint.width() + 5
            line = max(line, hint.height())
        return y + line

    def resizeEvent(self, e):
        self.setFixedHeight(self.place(e.size().width()))

    def showEvent(self, e):
        self.setFixedHeight(self.place(self.width()))


BLOCKS = (('天空', "c3d.sky(sun_height=30, sun_turn=150, clouds=.4)"), ('黄昏', "c3d.dusk(strength=1.3)"), ('摄影棚', "c3d.studio()"), ('地面', "c3d.ground(mat='concrete')"),
          ('草地', "c3d.ground(size=1500, mat='grass')\nc3d.meadow(near=(0, -3))"), ('房间', "c3d.room(size=(5, 3.6, 2.8))"), ('街道', "c3d.street_outside(y=2.2, z=-.3)"),
          ('桌子', "c3d.table(at=(0, 0, 0), size=(1.2, .7, .75))"), ('椅子', "c3d.chair(at=(0, -.8, 0))"), ('沙发', "c3d.sofa(at=(0, 1, 0))"), ('地毯', "c3d.rug(at=(0, 0, 0))"), ('书架', "c3d.bookshelf(at=(1.5, 1.5, 0))"), ('落地灯', "c3d.floor_lamp(at=(-1.5, 1, 0))"), ('杯子', "c3d.mug(at=(0, 0, .75), turn=30)"), ('咖啡', "c3d.cup_and_saucer(at=(0, 0, .75))"),
          ('书', "c3d.book(at=(.2, 0, .75), turn=12)"), ('绿植', "c3d.potted_plant(at=(-.3, .1, .75))"), ('台灯', "c3d.desk_lamp(at=(.4, .2, .75), turn=200)"), ('吊灯', "c3d.pendant_lamp(at=(0, 0, 2.8))"),
          ('电脑', "c3d.laptop(at=(0, 0, .75))"), ('酒杯', "c3d.wine_glass(at=(0, 0, .75))"), ('酒瓶', "c3d.bottle(at=(.1, 0, .75))"), ('花瓶', "c3d.vase(at=(0, 0, .75))"), ('苹果', "c3d.apple(at=(0, 0, .75))"),
          ('树', "c3d.tree(at=(-3, 12, 0), height=9)"), ('远山', "c3d.hills(y=400, height=70)"), ('湖', "c3d.lake(at=(10, 90, 0), size=(220, 90))"), ('晨雾', "c3d.mist(y=190)"), ('雪山', "c3d.mountains(y=800, height=320)"), ('松树', "c3d.pine(at=(-4, 12, 0), height=14)"), ('海', "c3d.beach(shore_y=10)\nc3d.sea(shore_y=10)"), ('街道景', "c3d.city_street(length=120)"), ('楼', "c3d.building(at=(0, 14, 0))"), ('汽车', "c3d.car(at=(0, 6, 0), turn=30)"), ('星空', "c3d.night()"), ('篝火', "c3d.campfire(at=(0, 3, 0))"), ('帐篷', "c3d.tent(at=(-2, 5, 0))"), ('椰树', "c3d.palm(at=(-3, 6, 0))"), ('小屋', "c3d.cottage(at=(0, 14, 0))"), ('小船', "c3d.boat(at=(0, 3, 0))"), ('石头', "c3d.rock(at=(1, 3, 0), size=.8)"),
          ('方块', "c3d.box((.5, .5, .5), at=(0, 0, .25), mat='wood')"), ('球', "c3d.sphere(.3, at=(0, 0, .3), mat='gold')"),
          ('旋转体', "c3d.lathe([(0, 0), (.2, 0), (.2, 0), (.28, .3), (.12, .6), (.16, .75)], mat='marble')"),
          ('管子', "c3d.tube([(0, 0, 0), (.3, 0, .4), (.6, 0, .4)], .02, mat='copper')"), ('文字', "c3d.text('Hello', at=(0, 0, .3), mat='gold')"),
          ('灯泡', "c3d.point(at=(0, 0, 2), power=40, colour=c3d.kelvin(3000))"), ('相机', "c3d.camera(at=(3, -4, 1.6), look=(0, 0, .5), lens=50)"),
          ('动起来', "# 第 1 帧到第 48 帧：把 obj 换成你的物体\n# c3d.key(obj, 1, at=(0, 0, 0))\n# c3d.key(obj, 48, at=(1, 0, 0))"))


class EditorWindow(QMainWindow):
    VIEWS = (('camera', '相机'), ('front', '正面'), ('right', '侧面'), ('top', '顶部'), ('iso', '斜视'))
    STAGES = {'build': '正在搭建场景…', 'render': '正在渲染…', 'views': '正在渲染各个角度…', 'turntable': '正在转一圈…', 'objects': '正在读取场景…',
              'animate': '正在渲染动画…', 'export': '正在导出…'}

    def __init__(self, folder=None, watch=None):
        super().__init__()
        self.folder: Path | None = None
        self.watch = Path(watch).resolve() if watch else None  # a folder an agent may start a project in
        self.watch_since = time.time()
        self.ticks = 0
        self.proc: QProcess | None = None
        self.buffer = b''
        self.after = None
        self.saved_text = ''
        self.script_time = 0.0
        self.latest_time = 0.0
        self.settings_file_time = 0.0
        self.loading = False
        self.ai = None
        self.prefs = QSettings('Code3D', 'Code3D')
        self.setWindowTitle('Code3D')
        self.setWindowIcon(icon('cube', ACCENT, 32))
        self.resize(1320, 820)
        self.setMinimumSize(420, 420)
        self.drawer = ''
        self.setStyleSheet(THEME)
        self.build()
        self.shortcuts()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.follow_tick)
        self.timer.start(900)
        target = folder or self.prefs.value('last', '')
        if target and (Path(target) / 'project.json').is_file():
            self.open_project(Path(target))
        else:
            self.show_welcome()

    # --- layout ------------------------------------------------------------------------------------------------------

    def build(self) -> None:
        root = QWidget()
        root.setObjectName('workspace')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.build_top())
        body = QWidget()
        lay = QHBoxLayout(body)
        lay.setContentsMargins(12, 12, 12, 12)
        self.split = QSplitter(Qt.Horizontal)
        self.split.setHandleWidth(10)
        self.split.setChildrenCollapsible(False)
        self.code_panel, self.view_panel, self.side_panel = self.build_code(), self.build_view(), self.build_side()
        self.split.addWidget(self.code_panel)
        self.split.addWidget(self.view_panel)
        self.split.addWidget(self.side_panel)
        self.split.setStretchFactor(0, 4)
        self.split.setStretchFactor(1, 6)
        self.split.setStretchFactor(2, 0)
        self.split.setSizes([470, 610, 240])
        lay.addWidget(self.split)
        outer.addWidget(body, 1)

    WIDE, MID = 1100, 760

    def toggle_drawer(self, name: str) -> None:
        self.drawer = '' if self.drawer == name else name
        self.relayout()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if hasattr(self, 'split'):
            self.relayout()

    def relayout(self) -> None:
        """Only when the layout really changes, and never inside itself."""
        if getattr(self, '_relaying', False):
            return
        width = self.width()
        state = (width >= self.WIDE, width < self.MID, self.drawer)
        if getattr(self, '_layout_state', None) == state:
            return
        self._relaying = True
        try:
            self._relayout()
            self._layout_state = state
        finally:
            self._relaying = False

    def _relayout(self) -> None:
        """Wide: code | picture | settings. Narrower: the picture, and the code or the settings over it when asked for (below MID they take
        the whole width). The words of the top bar go before its buttons do."""
        width = self.width()
        wide, narrow = width >= self.WIDE, width < self.MID
        if wide:
            self.drawer = ''
        self.code_panel.setVisible(wide or self.drawer == 'code')
        self.side_panel.setVisible(wide or self.drawer == 'side')
        self.view_panel.setVisible(wide or not (narrow and self.drawer) )
        self.code_toggle.setVisible(not wide)
        self.side_toggle.setVisible(not wide)
        for w in (self.brand, self.crumb, self.project_label):
            w.setVisible(not narrow)
        squeeze = 'QPushButton{min-width:0;padding:0;}'
        for b in (self.ai_button, self.export_button):
            b.setText('' if narrow else b.property('words'))
            b.setFixedWidth(34) if narrow else (b.setMinimumWidth(0), b.setMaximumWidth(16777215))
            b.setStyleSheet(squeeze if narrow else '')
        self.blender_button.setText('' if narrow else 'blender')
        if not narrow:
            self.blender_button.setText('在 Blender 打开')
        self.turn_button.setText('' if narrow else '转一圈')
        for b in self.welcome_buttons:
            b.setStyleSheet('QPushButton{min-width:0;padding:0 8px;}' if narrow else '')
        self.code_panel.setMinimumWidth(0 if not wide else 0)
        self.side_panel.setMinimumWidth(0 if not wide else 240)
        self.side_panel.setMaximumWidth(16777215 if not wide else 340)
        self.split.setSizes([470, 610, 240] if wide else [1, 1, 1])
        hero = getattr(self, 'hero', None)
        if hero is not None:
            self.hero_label.setPixmap(hero.scaledToWidth(max(120, min(420, width - 90)), Qt.SmoothTransformation))
        self.place_floats()

    def build_top(self) -> QFrame:
        top = QFrame()
        top.setObjectName('topbar')
        top.setFixedHeight(56)
        h = QHBoxLayout(top)
        h.setContentsMargins(18, 0, 16, 0)
        h.setSpacing(6)
        h.addWidget(look.Mark('cube'))
        h.addSpacing(4)
        self.brand = text('Code3D', 'brand')
        self.crumb = text('/', 'crumb')
        h.addWidget(self.brand)
        h.addWidget(self.crumb)
        self.project_label = text('', 'project')
        h.addWidget(self.project_label)
        h.addStretch(1)
        h.addWidget(tool('plus', '新建项目', self.new_project))
        h.addWidget(tool('open', '打开项目', self.choose_project))
        self.save_button = tool('save', '保存 (Ctrl+S)', self.save)
        h.addWidget(self.save_button)
        h.addSpacing(8)
        # where the room is short, the code and the side panel come in over the picture, one at a time
        self.code_toggle = tool('code', '代码', lambda: self.toggle_drawer('code'))
        self.side_toggle = tool('panel', '场景与设置', lambda: self.toggle_drawer('side'))
        h.addWidget(self.code_toggle)
        h.addWidget(self.side_toggle)
        self.ai_button = button('AI 建模', self.open_ai, '', 'spark')
        self.ai_button.setProperty('words', 'AI 建模')
        h.addWidget(self.ai_button)
        self.export_button = button('导出', self.show_export, 'primary', 'export')
        self.export_button.setProperty('words', '导出')
        h.addWidget(self.export_button)
        return top

    def build_code(self) -> QWidget:
        f, lay = panel()
        head = QHBoxLayout()
        self.file_label = text('scene.py', 'title')
        head.addWidget(self.file_label)
        self.dirty_label = text('', 'faint')
        head.addWidget(self.dirty_label)
        head.addStretch(1)
        self.reload_button = button('载入新版本', self.reload_script, 'small')
        self.reload_button.setFixedHeight(26)
        self.reload_button.setToolTip('文件被别处改过了（比如 AI）。载入后你没保存的修改会被替换。')
        self.reload_button.hide()
        head.addWidget(self.reload_button)
        lay.addLayout(head)
        self.code = CodeEdit()
        self.code.textChanged.connect(self.code_changed)
        lay.addWidget(self.code, 1)
        self.console = QPlainTextEdit()
        self.console.setObjectName('console')
        self.console.setReadOnly(True)
        self.console.setFixedHeight(92)
        self.console.setPlaceholderText('渲染结果和错误显示在这里')
        lay.addWidget(self.console)
        return f

    def build_view(self) -> QWidget:
        f, lay = panel()
        lay.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        head.setContentsMargins(6, 4, 6, 4)
        head.setSpacing(2)
        self.views = QButtonGroup(self)
        self.views.setExclusive(True)
        for key, name in self.VIEWS:
            b = button(name, None, 'pill')
            b.setCheckable(True)
            b.setProperty('view', key)
            b.clicked.connect(lambda _=False, k=key: self.pick_view(k))
            self.views.addButton(b)
            head.addWidget(b)
        self.views.buttons()[0].setChecked(True)
        self.size_label = text('', 'faint')
        top_float = QFrame()
        top_float.setObjectName('float')
        top_float.setLayout(head)
        self.stage = QStackedWidget()
        self.stage.addWidget(self.build_welcome())
        self.view = Viewport()
        self.stage.addWidget(self.view)
        lay.addWidget(self.stage, 1)
        row = QHBoxLayout()
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(6)
        self.preview_button = button('预览', lambda: self.render('draft'), 'primary', 'play')
        self.preview_button.setToolTip('F5：保存并快速渲染')
        self.final_button = button('成片', lambda: self.render('final'), '')
        self.final_button.setToolTip('F6：按项目分辨率和采样渲染，看相机角度')
        self.turn_button = button('转一圈', self.turntable, '', 'turn')
        self.turn_button.setToolTip('渲染一圈小图，拖动画面转着看')
        self.blender_button = button('在 Blender 打开', self.open_in_blender, '', 'blender')
        self.blender_button.setToolTip('用 Blender 自己的窗口打开这个场景：实时 3D 视图和全部工具')
        for b in (self.preview_button, self.final_button, self.turn_button):
            row.addWidget(b)
        row.addWidget(self.blender_button)
        bottom_float = QFrame()
        bottom_float.setObjectName('float')
        bottom_float.setLayout(row)
        self.floats = (top_float, bottom_float)
        for w in self.floats:
            w.setParent(self.stage)
        self.stage.installEventFilter(self)
        self.stage.currentChanged.connect(lambda _=0: self.place_floats())
        state = QHBoxLayout()
        state.setContentsMargins(16, 0, 12, 0)
        self.status = text('', 'status')
        state.addWidget(self.status, 1)
        self.stop_button = button('停止', self.stop, 'small')
        self.stop_button.setFixedHeight(24)
        self.stop_button.hide()
        state.addWidget(self.stop_button)
        state.addWidget(self.size_label)
        box = QWidget()
        box.setFixedHeight(34)
        box.setLayout(state)
        lay.addWidget(box)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(2)
        keep = self.progress.sizePolicy()
        keep.setRetainSizeWhenHidden(True)
        self.progress.setSizePolicy(keep)
        self.progress.hide()
        lay.addWidget(self.progress)
        return f

    def eventFilter(self, obj, e):
        if obj is getattr(self, 'stage', None) and e.type() == QEvent.Resize:
            self.place_floats()
        return super().eventFilter(obj, e)

    def place_floats(self) -> None:
        top, bottom = self.floats
        working = self.stage.currentIndex() == 1
        for w in self.floats:
            w.setVisible(working)
            w.adjustSize()
            w.raise_()
        width = self.stage.width()
        top.move(max(10, (width - top.width()) // 2), 12)
        bottom.move(max(10, (width - bottom.width()) // 2), self.stage.height() - bottom.height() - 14)

    def build_welcome(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(10)
        art = QLabel()
        hero = core.ROOT / 'assets' / 'hero.png'
        if hero.is_file():
            self.hero = QPixmap(str(hero))
            self.hero_label = art
            art.setPixmap(self.hero.scaledToWidth(420, Qt.SmoothTransformation))
        else:
            art.setPixmap(icon('cube', ACCENT, 54).pixmap(54, 54))
        art.setAlignment(Qt.AlignCenter)
        lay.addWidget(art)
        hello = text('用代码做 3D', 'hello')
        hello.setAlignment(Qt.AlignCenter)
        lay.addWidget(hello)
        self.welcome_note = text('写几行代码，Blender 在后台把它变成真实的画面。', 'muted')
        self.welcome_note.setAlignment(Qt.AlignCenter)
        self.welcome_note.setWordWrap(True)
        lay.addWidget(self.welcome_note)
        lay.addSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        self.welcome_buttons = [button('新建项目', self.new_project, 'primary', 'plus'), button('打开项目', self.choose_project), button('看示例', self.open_example)]
        for b in self.welcome_buttons:
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.choose_blender_button = button('选择 blender.exe', self.choose_blender)
        self.choose_blender_button.hide()
        lay.addWidget(self.choose_blender_button, 0, Qt.AlignCenter)
        return w

    def build_side(self) -> QWidget:
        f, lay = panel()
        f.setMinimumWidth(236)
        f.setMaximumWidth(320)
        lay.addWidget(text('场景', 'title'))
        stats = QHBoxLayout()
        self.stats = {}
        for key, name in (('count', '物体'), ('faces', '面'), ('size', '米')):
            col = QVBoxLayout()
            col.setSpacing(0)
            self.stats[key] = text('–', 'stat')
            col.addWidget(self.stats[key])
            col.addWidget(text(name, 'faint'))
            stats.addLayout(col)
        lay.addLayout(stats)
        self.summary = text('', 'faint')
        self.summary.hide()
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.objects = QListWidget()
        self.objects.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        lay.addWidget(self.objects, 1)
        lay.addSpacing(4)
        lay.addWidget(text('积木', 'title'))
        lay.addWidget(text('点一下，把代码写到光标处', 'faint'))
        blocks = FlowRow()
        for name, code in BLOCKS:
            b = button(name, None, 'chip')
            b.setToolTip(code.strip())
            b.clicked.connect(lambda _=False, c=code: self.insert_code(c))
            blocks.add(b)
        lay.addWidget(blocks)
        lay.addSpacing(4)
        lay.addWidget(text('项目设置', 'title'))
        grid = QGridLayout()  # two columns: the list above keeps the room
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.fields = {}
        for i, (key, name, low, high) in enumerate((('width', '宽', 16, 7680), ('height', '高', 16, 4320), ('samples', '采样', 1, 4096), ('fps', '帧率', 1, 120),
                                                    ('frame_start', '起始', 0, 100000), ('frame_end', '结束', 0, 100000))):
            box = QSpinBox()
            box.setRange(low, high)
            box.setValue(core.SETTINGS[key])
            box.setKeyboardTracking(False)
            box.setMinimumWidth(56)
            box.valueChanged.connect(self.settings_changed)
            self.fields[key] = box
            grid.addWidget(text(name, 'muted'), i // 2, (i % 2) * 2)
            grid.addWidget(box, i // 2, (i % 2) * 2 + 1)
        self.engine = QComboBox()
        self.engine.addItem('Cycles（真实）', 'cycles')
        self.engine.addItem('EEVEE（快）', 'eevee')
        self.engine.setToolTip('Cycles 用处理器，慢但真实，不占显卡。EEVEE 用显卡，快，但玩游戏时别用。')
        self.engine.currentIndexChanged.connect(self.settings_changed)
        grid.addWidget(text('引擎', 'muted'), 3, 0)
        grid.addWidget(self.engine, 3, 1, 1, 3)
        lay.addLayout(grid)
        self.animate_button = button('渲染动画', self.animate, '')
        self.animate_button.setToolTip('把起始帧到结束帧全部渲染出来，合成 MP4')
        lay.addWidget(self.animate_button)
        return f

    def shortcuts(self) -> None:
        for keys, fn in ((QKeySequence.Save, self.save), ('F5', lambda: self.render('draft')), ('F6', lambda: self.render('final')),
                         (QKeySequence.Open, self.choose_project), (QKeySequence.New, self.new_project)):
            a = QAction(self)
            a.setShortcut(QKeySequence(keys))
            a.triggered.connect(lambda _=False, f=fn: f())
            self.addAction(a)

    # --- project -----------------------------------------------------------------------------------------------------

    def show_welcome(self) -> None:
        self.stage.setCurrentIndex(0)
        found = core.find_blender() is not None
        self.choose_blender_button.setVisible(not found)
        if not found:
            self.welcome_note.setText('没有找到 Blender。选择你电脑上的 blender.exe，Code3D 用它来建模和渲染。')
        self.enable()

    def enable(self) -> None:
        ready = self.folder is not None
        busy = self.proc is not None
        for b in (self.preview_button, self.final_button, self.turn_button, self.blender_button, self.export_button, self.animate_button, self.ai_button):
            b.setEnabled(ready and not busy)
        self.save_button.setEnabled(ready)
        self.code.setReadOnly(not ready)
        self.engine.setEnabled(ready)
        for box in self.fields.values():
            box.setEnabled(ready)
        for b in self.views.buttons():
            b.setEnabled(ready and not busy)
        self.stop_button.setVisible(busy)
        self.progress.setVisible(busy)

    def new_project(self) -> None:
        name = QFileDialog.getExistingDirectory(self, '选一个空文件夹放新项目')
        if name:
            self.create_project(Path(name))

    def create_project(self, folder: Path) -> None:
        if (folder / 'project.json').exists():
            self.open_project(folder)
            return
        core.main(['init', str(folder)])
        self.open_project(folder)

    def choose_project(self) -> None:
        name = QFileDialog.getExistingDirectory(self, '打开 Code3D 项目文件夹')
        if not name:
            return
        if (Path(name) / 'project.json').is_file():
            self.open_project(Path(name))
        else:
            QMessageBox.information(self, 'Code3D', '这个文件夹里没有 project.json，不是 Code3D 项目。')

    def open_example(self) -> None:
        menu = QMenu(self)
        for folder, title in (('cafe-window', '雨后咖啡馆'), ('still-life', '静物'), ('desk', '书桌'), ('meadow', '山湖'), ('city', '城市夜景'), ('living-room', '客厅'), ('seaside', '海边'), ('winter', '雪夜小屋'), ('autumn', '秋林'), ('camp', '星空露营'), ('tropic', '热带海滩')):
            menu.addAction(title, lambda f=folder: self.open_project(core.ROOT / 'examples' / f))
        menu.exec(QCursor.pos())

    def choose_blender(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, '选择 blender.exe', '', 'Blender (blender.exe)')
        if name:
            core.remember_blender(name)
            self.welcome_note.setText('写几行代码，Blender 在后台把它变成真实的画面。')
            self.choose_blender_button.hide()

    def open_project(self, folder: Path) -> None:
        if self.folder and not self.confirm_leave():
            return
        folder = Path(folder).resolve()
        try:
            settings = core.load(folder)
        except core.Stop as e:
            QMessageBox.warning(self, 'Code3D', str(e))
            return
        self.folder, self.project = folder, settings
        self.prefs.setValue('last', str(folder))
        self.setWindowTitle(f'Code3D — {settings["name"]}')
        self.project_label.setText(settings['name'])
        self.file_label.setText(settings['script'])
        self.load_script()
        self.show_settings()
        self.console.clear()
        self.objects.clear()
        for v in self.stats.values():
            v.setText('–')
        self.stage.setCurrentIndex(1)
        self.view.clear()
        self.latest_time = 0.0
        if not self.show_latest():
            self.view.note = '按 F5 看看这段代码做出了什么'
            self.view.update()
        self.enable()

    @property
    def script_path(self) -> Path:
        return self.folder / self.project['script']

    def load_script(self) -> None:
        self.loading = True
        source = self.script_path.read_text(encoding='utf-8-sig') if self.script_path.is_file() else ''
        self.code.setPlainText(source)
        self.saved_text = source
        self.loading = False
        self.script_time = self.script_path.stat().st_mtime if self.script_path.is_file() else 0.0
        self.code.show_error(None)
        self.reload_button.hide()
        self.code_changed()

    def reload_script(self) -> None:
        cursor = self.code.textCursor().position()
        self.load_script()
        c = self.code.textCursor()
        c.setPosition(min(cursor, self.code.document().characterCount() - 1))
        self.code.setTextCursor(c)

    def code_changed(self) -> None:
        if self.loading:
            return
        self.dirty_label.setText('未保存' if self.dirty else '')
        if self.code.error_line:
            self.code.show_error(None)

    @property
    def dirty(self) -> bool:
        return self.folder is not None and self.code.toPlainText() != self.saved_text

    def save(self) -> bool:
        if self.folder is None:
            return False
        source = self.code.toPlainText()
        self.script_path.write_text(source, encoding='utf-8', newline='\n')
        self.saved_text = source
        self.script_time = self.script_path.stat().st_mtime
        self.dirty_label.setText('')
        self.reload_button.hide()
        return True

    def confirm_leave(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, 'Code3D', '代码有没保存的修改，要保存吗？', QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        return self.save() if answer == QMessageBox.Save else answer == QMessageBox.Discard

    def show_settings(self) -> None:
        self.loading = True
        for key, box in self.fields.items():
            box.setValue(self.project[key])
        self.engine.setCurrentIndex(max(0, self.engine.findData(self.project['engine'])))
        self.loading = False
        self.size_label.setText(f'{self.project["width"]} × {self.project["height"]}')
        self.settings_file_time = (self.folder / 'project.json').stat().st_mtime

    def settings_changed(self) -> None:
        if self.loading or self.folder is None:
            return
        for key, box in self.fields.items():
            self.project[key] = box.value()
        self.project['frame_end'] = max(self.project['frame_end'], self.project['frame_start'])
        self.project['engine'] = self.engine.currentData()
        file = self.folder / 'project.json'
        file.write_text(json.dumps(self.project, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.settings_file_time = file.stat().st_mtime
        self.size_label.setText(f'{self.project["width"]} × {self.project["height"]}')

    # --- following what others do ------------------------------------------------------------------------------------

    def newest_project(self) -> Path | None:
        """The project in the watched folder whose code changed last, if that happened since this window opened."""
        best, when = None, self.watch_since
        for base, dirs, files in os.walk(self.watch):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'out', '__pycache__', 'venv')]
            if len(Path(base).relative_to(self.watch).parts) >= 3:
                dirs[:] = []
            if 'project.json' in files and 'scene.py' in files:
                t = (Path(base) / 'scene.py').stat().st_mtime
                if t > when:
                    best, when = Path(base), t
        return best

    def follow_tick(self) -> None:
        self.ticks += 1
        if self.watch is not None and self.ticks % 3 == 0 and self.proc is None and not self.dirty:
            found = self.newest_project()
            if found is not None and found != self.folder:
                self.open_project(found)
        if self.folder is None or not self.folder.is_dir():
            return
        try:
            now = self.script_path.stat().st_mtime
        except OSError:
            now = self.script_time
        if now != self.script_time:
            if self.dirty:
                self.reload_button.show()
                self.script_time = now
            else:
                self.reload_script()
        file = self.folder / 'project.json'
        if file.is_file() and file.stat().st_mtime != self.settings_file_time:
            try:
                self.project = core.load(self.folder)
                self.show_settings()
            except core.Stop:
                self.settings_file_time = file.stat().st_mtime
        if self.proc is None:
            self.show_latest()

    def show_latest(self) -> bool:
        info = self.folder / 'out' / 'latest.json'
        picture = self.folder / 'out' / 'latest.png'
        if not info.is_file() or not picture.is_file() or info.stat().st_mtime == self.latest_time:
            return self.latest_time != 0.0
        self.latest_time = info.stat().st_mtime
        try:
            data = json.loads(info.read_text(encoding='utf-8'))
        except ValueError:
            data = {}
        if self.view.show_picture(picture):
            self.view.note = ''
            self.mark_view(data.get('view', 'camera'))
            self.show_scene(data.get('scene'))
            return True
        return False

    def mark_view(self, key: str) -> None:
        for b in self.views.buttons():
            b.setChecked(b.property('view') == key)

    def show_scene(self, scene) -> None:
        if not scene:
            return
        self.objects.clear()
        for row in scene.get('objects', []):
            item = QListWidgetItem(f'{row["name"]}')
            item.setToolTip(f'{row["faces"]:,} 个面 · 尺寸 {" × ".join(f"{v:g}" for v in row["size"])} 米\n材质：{"、".join(row["materials"]) or "无"}')
            self.objects.addItem(item)
        faces = scene.get('faces', 0)
        self.stats['count'].setText(str(scene.get('count', 0)))
        self.stats['faces'].setText(f'{faces / 1000:.1f}k' if faces >= 1000 else str(faces))
        self.stats['size'].setText(f'{scene.get("size", 0):.1f}')

    def insert_code(self, code: str) -> None:
        if self.folder is None:
            return
        cursor = self.code.textCursor()
        cursor.movePosition(QTextCursor.EndOfBlock)
        self.code.setTextCursor(cursor)
        self.code.insertPlainText(('\n' if cursor.block().text().strip() else '') + code.strip() + '\n')
        self.code.setFocus()

    # --- jobs --------------------------------------------------------------------------------------------------------

    def pick_view(self, key: str) -> None:
        picture = self.folder / 'out' / f'{key}.png' if self.folder else None
        if picture and picture.is_file() and self.script_path.is_file() and picture.stat().st_mtime > self.script_path.stat().st_mtime and not self.dirty:
            self.view.show_picture(picture)
            return
        self.render('draft', key)

    def current_view(self) -> str:
        checked = self.views.checkedButton()
        return checked.property('view') if checked else 'camera'

    def render(self, quality: str, view: str | None = None) -> None:
        if quality == 'final':
            view = 'camera'
            self.mark_view('camera')
        self.start(['render', str(self.folder or ''), '--view', view or self.current_view(), '--quality', quality], self.rendered)

    def turntable(self) -> None:
        self.start(['turntable', str(self.folder or ''), '--count', '16'], self.turned)

    def animate(self) -> None:
        self.start(['animate', str(self.folder or ''), '--force'], self.exported)

    def show_export(self) -> None:
        menu = QMenu(self)
        for key, name in (('glb', 'GLB（网页、游戏）'), ('fbx', 'FBX（Unity、Unreal）'), ('obj', 'OBJ（通用模型）'), ('stl', 'STL（3D 打印）'), ('usd', 'USD（影视流程）'),
                          ('blend', 'Blend（Blender 工程）')):
            menu.addAction(name, lambda k=key: self.export(k))
        menu.exec(self.export_button.mapToGlobal(QPoint(0, self.export_button.height() + 4)))

    def export(self, key: str) -> None:
        self.start(['export', str(self.folder or ''), '--format', key, '--force'], self.exported)

    def open_in_blender(self) -> None:
        self.start(['open', str(self.folder or '')], self.opened)

    def start(self, args: list[str], after) -> None:
        if self.proc is not None or self.folder is None:
            return
        if self.dirty and not self.save():
            return
        self.console.clear()
        self.code.show_error(None)
        self.buffer = b''
        self.after = after
        self.proc = QProcess(self)
        self.proc.setProgram(sys.executable.replace('pythonw.exe', 'python.exe'))
        self.proc.setArguments([str(core.ROOT / 'code3d.py'), *args])
        self.proc.setWorkingDirectory(str(self.folder))
        self.proc.setProcessChannelMode(QProcess.SeparateChannels)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.done)
        self.proc.errorOccurred.connect(self.failed_to_start)
        self.progress.setRange(0, 0)
        self.status.setText('正在启动 Blender…')
        self.view.note = ''
        self.enable()
        self.proc.start()

    def failed_to_start(self, error) -> None:
        if error == QProcess.FailedToStart and self.proc is not None:
            self.proc = None
            self.status.setText('启动失败')
            self.enable()

    def read(self) -> None:
        self.buffer += bytes(self.proc.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                event = json.loads(line.decode('utf-8', 'replace'))
            except ValueError:
                continue
            if 'event' in event:
                self.on_event(event)
            else:
                self.answer = event

    def on_event(self, event: dict) -> None:
        if event['event'] == 'stage':
            self.status.setText(self.STAGES.get(event['what'], '正在处理…'))
        elif event['event'] == 'progress':
            self.progress.setRange(0, int(event['total']))
            self.progress.setValue(int(event['done']))
            self.status.setText(f'{self.STAGES.get(self.after_name(), "正在处理…")} {event["done"] + 1} / {event["total"]}')

    def after_name(self) -> str:
        return 'animate' if self.after == self.exported else 'turntable' if self.after == self.turned else 'render'

    def done(self, code=0, _status=None) -> None:
        self.read()
        proc, self.proc = self.proc, None
        if proc is None:
            return
        answer = getattr(self, 'answer', None)
        self.answer = None
        proc.deleteLater()
        self.enable()
        if self.stopped:
            self.stopped = False
            self.status.setText('已停止')
            return
        if not answer:
            self.status.setText('没有完成')
            self.log(bytes(proc.readAllStandardError()).decode('utf-8', 'replace')[-1500:] or '程序没有给出结果。')
            return
        for w in answer.get('warnings') or []:
            self.log('注意：' + w)
        if answer.get('ok'):
            self.after(answer)
            return
        self.status.setText('出错了，看左下角')
        line = answer.get('line')
        self.log((f'第 {line} 行：' if line else '') + str(answer.get('error', '未知错误')))
        if line:
            self.code.show_error(line)

    stopped = False
    answer = None

    def stop(self) -> None:
        if self.proc is not None:
            self.stopped = True
            self.proc.kill()

    def log(self, words: str) -> None:
        self.console.appendPlainText(words)

    def rendered(self, a: dict) -> None:
        self.status.setText(f'渲染用了 {a["seconds"]:g} 秒 · {a["width"]} × {a["height"]}')
        self.mark_view(a['view'])
        self.show_scene(a.get('scene'))
        self.latest_time = (self.folder / 'out' / 'latest.json').stat().st_mtime
        self.view.show_picture(a['output'])

    def turned(self, a: dict) -> None:
        self.status.setText('拖动画面可以转着看')
        self.view.show_turn(a['pictures'])
        self.view.note = '左右拖动旋转'

    def exported(self, a: dict) -> None:
        out = a.get('output') or a.get('frames') or ''
        try:
            shown = Path(out).resolve().relative_to(Path(self.folder).resolve()).as_posix() if out else ''
        except (ValueError, OSError):  # an output outside the folder (or a path that cannot be resolved): show it whole
            shown = str(out)
        self.status.setText(f'已导出 {shown}')
        self.log(f'文件在：{out}')

    def opened(self, _a: dict) -> None:
        self.status.setText('已在 Blender 里打开（那是一份副本，改动不会写回代码）')

    def open_ai(self) -> None:
        from ai_panel import AIPanel

        if self.ai is None:
            self.ai = AIPanel(self)
        self.ai.show()
        self.ai.raise_()

    def closeEvent(self, e):
        if not self.confirm_leave():
            e.ignore()
            return
        self.stop()
        if self.ai is not None:
            self.ai.close()
        super().closeEvent(e)


def apply_window_chrome(window) -> None:
    if os.name != 'nt':
        return
    try:
        import ctypes
        from ctypes import wintypes

        setter = ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
        setter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        setter.restype = ctypes.c_long
        dark = ctypes.c_int(1)
        setter(int(window.winId()), 20, ctypes.byref(dark), ctypes.sizeof(dark))
        caption = ctypes.c_uint(0x00120F0E)
        setter(int(window.winId()), 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except (OSError, AttributeError):
        pass


def main() -> int:
    args = sys.argv[1:]
    folder = watch = None
    if '--watch' in args:
        watch = args[args.index('--watch') + 1]
    elif args and not args[0].startswith('-'):
        folder = args[0]
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Code3D')
    win = EditorWindow(folder, watch)
    apply_window_chrome(win)
    import embed
    embed.show(win)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
