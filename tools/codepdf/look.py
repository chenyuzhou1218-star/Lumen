"""How the tools' windows look: white, hairline rules, one black for what matters most. Every tool carries this same file.

    THEME            the style sheet (call apply(app) once)
    icon(name)       a line icon, the same drawings as CodePage's builder
    button(...)      a button of one of the kinds: '' (outlined), 'primary' (black), 'ghost' (no border), 'icon' (square)
    Mark(glyph)      the tool's small black square at the top left
    CodeEdit         a code box with line numbers and the current line marked
    Card(title)      a white panel with a hairline border and a header row
    Notes            what came out, one line each, warnings first
"""
from __future__ import annotations

from pathlib import Path
import tempfile

from PySide6.QtCore import QByteArray, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap, QTextFormat
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout,
                               QWidget)

INK, INK2, INK3 = '#111113', '#5f5f66', '#9a9aa2'
RULE, EDGE, EDGE2 = '#ededee', '#e3e3e6', '#cfcfd4'
TINT, TINT2 = '#fafafa', '#f4f4f5'
AMBER, GREEN, RED = '#c98a12', '#1f9d55', '#c8322b'

PATHS = {
    'plus': '<path d="M8 3.2v9.6M3.2 8h9.6"/>',
    'folder': '<path d="M1.8 4.4c0-.6.4-1 1-1h3.1l1.5 1.5h5.8c.6 0 1 .4 1 1v6.2c0 .6-.4 1-1 1H2.8c-.6 0-1-.4-1-1Z"/>',
    'save': '<path d="M2.6 3.6c0-.6.4-1 1-1h7l2.8 2.8v7c0 .6-.4 1-1 1H3.6c-.6 0-1-.4-1-1Z"/><path d="M5.2 2.7v2.8h4.6V2.7"/><path d="M5 13.3V9.6h6v3.7"/>',
    'spark': '<path d="M8 1.8 9.4 6.6 14.2 8 9.4 9.4 8 14.2 6.6 9.4 1.8 8 6.6 6.6Z"/>',
    'play': '<path d="M5 3.4v9.2L12.6 8Z"/>',
    'stop': '<rect x="4" y="4" width="8" height="8" rx="1.4"/>',
    'export': '<path d="M8 10V2.6"/><path d="M5.2 5.3 8 2.5l2.8 2.8"/><path d="M2.6 9.6v2.8c0 .6.4 1 1 1h8.8c.6 0 1-.4 1-1V9.6"/>',
    'open': '<path d="M9.4 2.6h4v4M13.2 2.8 7.6 8.4"/><path d="M12 9.4v3c0 .6-.4 1-1 1H3.6c-.6 0-1-.4-1-1V5c0-.6.4-1 1-1h3"/>',
    'file': '<path d="M3.6 1.6h5.8l3 3v9.8H3.6Z"/><path d="M9.4 1.6v3h3"/>',
    'image': '<rect x="2" y="2.6" width="12" height="10.8" rx="1.4"/><circle cx="5.8" cy="6.2" r="1.1"/><path d="m2.4 12 3.6-3.3 2.4 2.1 2-1.7 3.2 2.8"/>',
    'chev': '<path d="m4.6 6.2 3.4 3.4 3.4-3.4"/>',
    'check': '<path d="m3.6 8.3 2.8 2.8 6-6.3"/>',
    'close': '<path d="m4.2 4.2 7.6 7.6M11.8 4.2l-7.6 7.6"/>',
    'search': '<circle cx="7" cy="7" r="4.4"/><path d="m10.3 10.3 3.3 3.3"/>',
    'refresh': '<path d="M13 4.6V2.4M13 4.6h-2.2"/><path d="M12.8 4.4A5.4 5.4 0 1 0 13.4 9"/>',
    'list': '<path d="M5.6 4h7.8M5.6 8h7.8M5.6 12h7.8"/><circle cx="2.8" cy="4" r=".6"/><circle cx="2.8" cy="8" r=".6"/><circle cx="2.8" cy="12" r=".6"/>',
    'wave': '<path d="M1.8 8h1.4M4.6 5v6M7.4 2.8v10.4M10.2 5.6v4.8M13 7v2"/>',
    'music': '<path d="M6 12.2V3.4l7-1.4v8.6"/><circle cx="4.4" cy="12.2" r="1.7"/><circle cx="11.4" cy="10.6" r="1.7"/>',
    'game': '<rect x="1.8" y="4.6" width="12.4" height="7.4" rx="3.6"/><path d="M5 7.4v2M4 8.4h2"/><circle cx="10.6" cy="7.8" r=".6"/><circle cx="11.8" cy="9.2" r=".6"/>',
    'slides': '<rect x="1.8" y="2.6" width="12.4" height="8.6" rx="1.2"/><path d="M8 11.2v2.4M5.6 13.6h4.8M4.6 8.4l2.2-2.2 1.6 1.4 2.6-2.6"/>',
    'chart': '<path d="M2.4 13.6h11.2"/><rect x="3.4" y="8" width="2.2" height="4.4" rx=".5"/><rect x="6.9" y="4.6" width="2.2" height="7.8" rx=".5"/><rect x="10.4" y="6.6" width="2.2" height="5.8" rx=".5"/>',
    'cube': '<path d="m8 1.8 5.4 3.1v6.2L8 14.2l-5.4-3.1V4.9Z"/><path d="m2.6 4.9 5.4 3.1 5.4-3.1M8 8v6.2"/>',
    'flask': '<path d="M6 1.8h4M6.6 1.8v4.4L2.8 12.4c-.4.7.1 1.6.9 1.6h8.6c.8 0 1.3-.9.9-1.6L9.4 6.2V1.8"/><path d="M4.4 10h7.2"/>',
    'film': '<rect x="2" y="2.6" width="12" height="10.8" rx="1.4"/><path d="M4.8 2.6v10.8M11.2 2.6v10.8M2 5.4h2.8M2 8h2.8M2 10.6h2.8M11.2 5.4H14M11.2 8H14M11.2 10.6H14"/>',
    'tools': '<path d="M9.6 2.4a3 3 0 0 0-3.4 4L2.4 10.2a1.3 1.3 0 0 0 1.8 1.8L8 8.2a3 3 0 0 0 4-3.4l-1.8 1.8-1.7-.4-.4-1.7Z"/>',
    'page': '<rect x="2.2" y="2.2" width="11.6" height="11.6" rx="1.4"/><path d="M2.2 6h11.6M6.4 6v7.8"/>',
    'cut': '<circle cx="4.4" cy="11.6" r="2"/><circle cx="11.6" cy="11.6" r="2"/><path d="M5.7 10 11.8 2.4M10.3 10 4.2 2.4"/>',
    'dot': '<circle cx="8" cy="8" r="2.4"/>',
    'more': '<circle cx="3.6" cy="8" r=".9"/><circle cx="8" cy="8" r=".9"/><circle cx="12.4" cy="8" r=".9"/>',
    'code': '<path d="m5.4 4.6-3.4 3.4 3.4 3.4"/><path d="m10.6 4.6 3.4 3.4-3.4 3.4"/><path d="m9 2.8-2 10.4"/>',
    'clock': '<circle cx="8" cy="8" r="5.8"/><path d="M8 4.8V8l2.2 1.4"/>',
    'mic': '<rect x="5.8" y="1.8" width="4.4" height="7.6" rx="2.2"/><path d="M3.6 7.6a4.4 4.4 0 0 0 8.8 0M8 12v2.2"/>',
}
FILLED = {'play', 'dot'}


def _svg(name: str, color: str, stroke: float = 1.35) -> bytes:
    body = PATHS.get(name, PATHS['dot'])
    paint = f'fill="{color}" stroke="none"' if name in FILLED else f'fill="none" stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" {paint}>{body}</svg>'.encode()


def pixmap(name: str, color: str = INK2, size: int = 16, stroke: float = 1.35) -> QPixmap:
    ratio = 2.0
    pix = QPixmap(int(size * ratio), int(size * ratio))
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    QSvgRenderer(QByteArray(_svg(name, color, stroke))).render(p)
    p.end()
    pix.setDevicePixelRatio(ratio)
    return pix


def icon(name: str, color: str = INK2, active: str = INK) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color), QIcon.Normal)
    ic.addPixmap(pixmap(name, active), QIcon.Active)
    ic.addPixmap(pixmap(name, '#c3c3c9'), QIcon.Disabled)
    return ic


def _asset(name: str, svg: bytes) -> str:
    """A small picture the style sheet points at (QSS takes files, not data)."""
    folder = Path(tempfile.gettempdir()) / 'lumen-look'
    folder.mkdir(exist_ok=True)
    path = folder / name
    if not path.is_file() or path.read_bytes() != svg:
        path.write_bytes(svg)
    return path.as_posix()


CHEV = _asset('chev.svg', _svg('chev', INK2, 1.5))
CHECK = _asset('check.svg', _svg('check', '#ffffff', 2.0))

UI_FONT = '"Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Helvetica Neue"'
MONO_FONT = '"Cascadia Mono", Consolas, Menlo, "Microsoft YaHei UI", "PingFang SC"'

THEME = f"""
QWidget {{ background: #ffffff; color: {INK}; font-family: {UI_FONT}; font-size: 13px; }}
QMainWindow, QDialog {{ background: #ffffff; }}
QToolTip {{ background: {INK}; color: #ffffff; border: none; border-radius: 6px; padding: 5px 8px; font-size: 12px; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 14px; font-weight: 600; }}
QLabel#big {{ font-size: 17px; font-weight: 600; }}
QLabel#muted {{ color: {INK2}; }}
QLabel#faint {{ color: {INK3}; font-size: 12px; }}
QLabel#crumb {{ color: {INK3}; font-size: 14px; }}
QLabel#project {{ color: {INK2}; font-size: 13.5px; font-weight: 500; }}
QLabel#chip {{ color: {INK2}; background: {TINT2}; border-radius: 5px; padding: 1px 7px; font-size: 11.5px; }}
QLabel#cardTitle {{ font-size: 12.5px; font-weight: 600; }}
QWidget#bar {{ border-bottom: 1px solid {RULE}; }}
QWidget#foot {{ border-top: 1px solid {RULE}; }}
QFrame#vrule {{ background: {RULE}; border: none; }}
QFrame#card {{ background: #ffffff; border: 1px solid {RULE}; border-radius: 12px; }}
QWidget#cardHead {{ background: transparent; border-bottom: 1px solid {RULE}; }}
QWidget#well {{ background: {TINT}; }}

QPushButton {{ background: #ffffff; color: {INK}; border: 1px solid {EDGE}; border-radius: 8px; padding: 0 12px; min-height: 30px; max-height: 30px; }}
QPushButton:hover {{ border-color: {EDGE2}; }}
QPushButton:pressed {{ background: {TINT2}; }}
QPushButton:disabled {{ color: #b6b6bc; border-color: {RULE}; }}
QPushButton:focus {{ outline: none; }}
QPushButton#primary {{ background: {INK}; color: #ffffff; border: 1px solid {INK}; font-weight: 600; padding: 0 14px; }}
QPushButton#primary:hover {{ background: #2a2a2e; border-color: #2a2a2e; }}
QPushButton#primary:disabled {{ background: #d5d5d9; border-color: #d5d5d9; color: #ffffff; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; color: {INK2}; padding: 0 10px; }}
QPushButton#ghost:hover {{ background: {TINT2}; color: {INK}; }}
QPushButton#ghost:disabled {{ color: #c3c3c9; background: transparent; }}
QPushButton#icon {{ background: transparent; border: 1px solid transparent; padding: 0; min-width: 30px; max-width: 30px; }}
QPushButton#icon:hover {{ background: {TINT2}; }}
QPushButton#danger {{ background: #ffffff; color: {RED}; border: 1px solid #f1c9c6; }}
QPushButton#danger:hover {{ background: #fdf1f0; }}
QPushButton#rail {{ background: transparent; border: none; border-radius: 8px; color: {INK2}; text-align: left; padding: 0 10px; min-height: 30px; max-height: 30px; }}
QPushButton#rail:hover {{ background: {TINT}; color: {INK}; }}
QPushButton#rail:checked {{ background: {TINT2}; color: {INK}; font-weight: 600; }}
QPushButton#tab {{ background: transparent; border: none; border-radius: 7px; color: {INK2}; padding: 0 12px; min-height: 26px; max-height: 26px; }}
QPushButton#tab:hover {{ color: {INK}; }}
QPushButton#tab:checked {{ background: #ffffff; color: {INK}; font-weight: 600; border: 1px solid {RULE}; }}
QWidget#segs {{ background: {TINT2}; border-radius: 9px; }}

QLineEdit, QSpinBox, QDoubleSpinBox {{ background: #ffffff; border: 1px solid {EDGE}; border-radius: 8px; padding: 0 10px; min-height: 30px; selection-background-color: #dfe5ff; selection-color: {INK}; }}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {EDGE2}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {INK}; }}
QLineEdit#search {{ background: {TINT}; border-color: transparent; padding-left: 30px; }}
QLineEdit#search:hover {{ border-color: {EDGE}; }}
QLineEdit#search:focus {{ background: #ffffff; border-color: {INK}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QPlainTextEdit, QTextEdit {{ background: #ffffff; border: 1px solid {EDGE}; border-radius: 8px; padding: 6px 4px; selection-background-color: #dfe5ff; selection-color: {INK}; }}
QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {INK}; }}
QPlainTextEdit#code {{ border: none; border-radius: 0; padding: 4px 2px; font-family: {MONO_FONT}; font-size: 12.5px; background: #ffffff; }}
QPlainTextEdit#console {{ background: {TINT}; border: 1px solid {RULE}; font-family: {MONO_FONT}; font-size: 12px; color: #2b2b30; }}
QPlainTextEdit#console:focus {{ border-color: {RULE}; }}
QPlainTextEdit#ask {{ font-size: 13px; }}

QComboBox {{ background: #ffffff; border: 1px solid {EDGE}; border-radius: 8px; padding: 0 28px 0 10px; min-height: 30px; max-height: 30px; }}
QComboBox:hover {{ border-color: {EDGE2}; }}
QComboBox:focus {{ border-color: {INK}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url({CHEV}); width: 13px; height: 13px; }}
QComboBox#ghost {{ border-color: transparent; background: transparent; color: {INK2}; }}
QComboBox#ghost:hover {{ background: {TINT2}; color: {INK}; }}
QComboBox QAbstractItemView {{ background: #ffffff; border: 1px solid {EDGE}; border-radius: 8px; padding: 4px; outline: none; selection-background-color: {TINT2}; selection-color: {INK}; }}
QMenu {{ background: #ffffff; border: 1px solid {EDGE}; border-radius: 10px; padding: 5px; }}
QMenu::item {{ padding: 6px 26px 6px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {TINT2}; color: {INK}; }}
QMenu::separator {{ height: 1px; background: {RULE}; margin: 4px 6px; }}

QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {EDGE2}; border-radius: 4px; background: #ffffff; }}
QCheckBox::indicator:hover {{ border-color: {INK2}; }}
QCheckBox::indicator:checked {{ background: {INK}; border-color: {INK}; image: url({CHECK}); }}
QSlider {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 3px; background: #e6e6e9; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {INK}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #ffffff; border: 1px solid #c9c9ce; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }}
QSlider::handle:horizontal:hover {{ border-color: {INK2}; }}
QProgressBar {{ background: {TINT2}; border: none; border-radius: 3px; max-height: 6px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {INK}; border-radius: 3px; }}

QListWidget {{ background: #ffffff; border: none; outline: none; padding: 4px; }}
QListWidget::item {{ border-radius: 7px; padding: 6px 8px; color: {INK2}; }}
QListWidget::item:hover {{ background: {TINT}; color: {INK}; }}
QListWidget::item:selected {{ background: {TINT2}; color: {INK}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {INK2}; padding: 7px 2px; margin-right: 18px; border-bottom: 2px solid transparent; }}
QTabBar::tab:hover {{ color: {INK}; }}
QTabBar::tab:selected {{ color: {INK}; border-bottom: 2px solid {INK}; font-weight: 600; }}
QScrollArea {{ border: none; background: transparent; }}
QAbstractScrollArea::corner {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #dedee2; border-radius: 3px; min-height: 28px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: #c6c6cc; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #dedee2; border-radius: 3px; min-width: 28px; margin: 2px 0; }}
QScrollBar::handle:horizontal:hover {{ background: #c6c6cc; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 12px; }}
QSplitter::handle:vertical {{ height: 12px; }}
"""


def apply(app: QApplication) -> None:
    app.setStyleSheet(THEME)
    try:  # a dark Windows made unstyled text white on white (内容看不见); these windows are light, whatever the system is
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except (AttributeError, RuntimeError):
        pass
    families = set(QFontDatabase.families())
    for name in ('Segoe UI Variable Text', 'Segoe UI', 'Microsoft YaHei UI', 'PingFang SC', 'Helvetica Neue'):
        if name in families:
            f = QFont(name, 10)
            f.setHintingPreference(QFont.PreferNoHinting)
            app.setFont(f)
            break


def mono(size: float = 9.6) -> QFont:
    families = set(QFontDatabase.families())
    for name in ('Cascadia Mono', 'Consolas'):
        if name in families:
            f = QFont(name)
            f.setPointSizeF(size)
            f.setStyleHint(QFont.Monospace)
            return f
    return QFont('Courier New', int(size))


def button(text: str, fn=None, kind: str = '', glyph: str = '', tip: str = '') -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    if glyph:
        light = kind == 'primary'
        b.setIcon(icon(glyph, '#ffffff' if light else INK2, '#ffffff' if light else INK))
        b.setIconSize(QSize(15, 15))
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    if fn:
        b.clicked.connect(lambda _=False: fn())
    return b


def vrule(height: int = 18) -> QFrame:
    r = QFrame()
    r.setObjectName('vrule')
    r.setFixedSize(1, height)
    return r


class Mark(QLabel):
    """The tool's small black square with its drawing in white."""

    def __init__(self, glyph: str, size: int = 24):
        super().__init__()
        ratio = 2.0
        pix = QPixmap(int(size * ratio), int(size * ratio))
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(INK))
        p.drawRoundedRect(QRect(0, 0, pix.width(), pix.height()), 7 * ratio, 7 * ratio)
        inner = int(size * ratio * .62)
        off = (pix.width() - inner) // 2
        QSvgRenderer(QByteArray(_svg(glyph, '#ffffff', 1.6))).render(p, QRect(off, off, inner, inner))
        p.end()
        pix.setDevicePixelRatio(ratio)
        self.setPixmap(pix)
        self.setFixedSize(size, size)


class _Gutter(QWidget):
    def __init__(self, edit):
        super().__init__(edit)
        self.edit = edit

    def sizeHint(self):
        return QSize(self.edit.gutter_width(), 0)

    def paintEvent(self, e):
        self.edit.paint_gutter(e)


class CodeEdit(QPlainTextEdit):
    """A code box: line numbers in a quiet gutter, the current line faintly marked, tabs four spaces wide."""

    def __init__(self):
        super().__init__()
        self.setObjectName('code')
        self.setFont(mono())
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.gutter = _Gutter(self)
        self.blockCountChanged.connect(lambda _n: self._margins())
        self.updateRequest.connect(self._scroll_gutter)
        self.cursorPositionChanged.connect(self._mark_line)
        self._margins()
        self._mark_line()

    def gutter_width(self) -> int:
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 18 + self.fontMetrics().horizontalAdvance('9') * digits

    def _margins(self) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _scroll_gutter(self, rect, dy) -> None:
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, e) -> None:
        p = QPainter(self.gutter)
        p.fillRect(e.rect(), QColor('#ffffff'))
        p.setFont(self.font())
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        h = self.fontMetrics().height()
        while block.isValid() and top <= e.rect().bottom():
            if block.isVisible() and bottom >= e.rect().top():
                p.setPen(QColor(INK2 if n == current else '#c2c2c8'))
                p.drawText(0, top, self.gutter.width() - 10, h, Qt.AlignRight | Qt.AlignVCenter, str(n + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            n += 1
        p.end()

    def _mark_line(self) -> None:
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor('#f7f7f8'))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel] if not self.isReadOnly() else [])
        self.gutter.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Tab and not e.modifiers():
            self.insertPlainText('    ')
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers():
            line = self.textCursor().block().text()
            indent = line[:len(line) - len(line.lstrip(' '))]
            if line.rstrip().endswith((':', '{', '[', '(')):
                indent += '    '
            super().keyPressEvent(e)
            self.insertPlainText(indent)
            return
        super().keyPressEvent(e)


class Card(QFrame):
    """A white panel: a header row (title, a chip, things on the right) and a body."""

    def __init__(self, title: str = '', glyph: str = ''):
        super().__init__()
        self.setObjectName('card')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.head = QWidget()
        self.head.setObjectName('cardHead')
        self.head.setFixedHeight(42)
        row = QHBoxLayout(self.head)
        row.setContentsMargins(14, 0, 8, 0)
        row.setSpacing(8)
        if glyph:
            g = QLabel()
            g.setPixmap(pixmap(glyph, INK3, 15))
            row.addWidget(g)
        self.title = QLabel(title)
        self.title.setObjectName('cardTitle')
        row.addWidget(self.title)
        self.chip = QLabel('')
        self.chip.setObjectName('chip')
        self.chip.setFixedHeight(20)
        self.chip.hide()
        row.addWidget(self.chip)
        row.addStretch(1)
        self.tools = row
        outer.addWidget(self.head)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        outer.addLayout(self.body, 1)

    def set_chip(self, text: str) -> None:
        self.chip.setText(text)
        self.chip.setVisible(bool(text))

    def add_tool(self, w: QWidget) -> None:
        self.tools.addWidget(w)


class Notes(QScrollArea):
    """What came out of a run, one line each: warnings in amber, errors in red, the rest quiet."""

    def __init__(self, empty: str = '运行一次，结果写在这里。'):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        self.lay = QVBoxLayout(holder)
        self.lay.setContentsMargins(14, 10, 14, 12)
        self.lay.setSpacing(2)
        self.lay.addStretch(1)
        self.setWidget(holder)
        self.empty_text = empty
        self.rows = 0
        self.clear()

    def clear(self) -> None:
        while self.lay.count() > 1:
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rows = 0
        self._placeholder = QLabel(self.empty_text)
        self._placeholder.setWordWrap(True)
        self._placeholder.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # it wraps at the card's edge; it never widens the card
        self._placeholder.setObjectName('faint')
        self.lay.insertWidget(0, self._placeholder)

    def count(self) -> int:
        return self.rows

    def addItem(self, text: str, kind: str = '') -> None:  # noqa: N802 (the QListWidget name, which this replaces)
        if self.rows == 0 and self._placeholder is not None:
            self._placeholder.deleteLater()
            self._placeholder = None
        color = {'warn': AMBER, 'error': RED, 'ok': GREEN}.get(kind, '#c2c2c8')
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 5, 0, 5)
        h.setSpacing(10)
        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f'background:{color};border-radius:3px;')
        holder = QVBoxLayout()
        holder.setContentsMargins(0, 6, 0, 0)
        holder.addWidget(dot)
        holder.addStretch(1)
        h.addLayout(holder)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        label.setStyleSheet(f'color:{INK if kind in ("error", "warn") else INK2};')
        h.addWidget(label, 1)
        self.lay.insertWidget(self.lay.count() - 1, row)
        self.rows += 1

    def addItems(self, texts, kind: str = '') -> None:  # noqa: N802
        for t in texts:
            self.addItem(str(t), kind)


class Empty(QWidget):
    """An empty state: a quiet drawing, a line in black, a line in grey."""

    def __init__(self, glyph: str, title: str, hint: str = ''):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(6)
        box = QLabel()
        box.setPixmap(pixmap(glyph, INK3, 22, 1.25))
        box.setFixedSize(48, 48)
        box.setAlignment(Qt.AlignCenter)
        box.setStyleSheet(f'border:1px dashed {EDGE2};border-radius:13px;background:#ffffff;')
        lay.addWidget(box, 0, Qt.AlignHCenter)
        lay.addSpacing(10)
        self.title = QLabel(title)
        self.title.setStyleSheet('font-weight:600;font-size:13.5px;')
        self.title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title)
        self.hint = QLabel(hint)
        self.hint.setObjectName('faint')
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.hint.setMinimumWidth(min(340, 13 * len(hint)))
        self.hint.setVisible(bool(hint))
        lay.addWidget(self.hint)
