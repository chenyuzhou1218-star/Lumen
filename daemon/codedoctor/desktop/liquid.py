"""Native glass materials.

One living backdrop is rendered per size; every translucent surface samples a
blurred copy of it. That is what makes a panel read as glass over the room
instead of a white slab — the previous opaque-white gradients were the reason
the workspace felt heavy. Nothing here blurs the widget tree per frame: the
backdrop is rasterised at a third of the window size and blurred by repeated
smooth downscales, all inside Qt's C++ raster engine.
"""
# Ported 2026-10-27 from ChatGPT's studio build (Codex work dir business-cluster-backend, 2026-10-26),
# unchanged except for this note; the user asked for its look and opening animation in this app.
from __future__ import annotations

import math
import os
import random
from pathlib import Path

from PySide6.QtCore import Property, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import QSlider, QStyle, QVBoxLayout, QWidget, QLabel

# --- design tokens ---------------------------------------------------------------------

INK = "#101b2a"          # headline ink
TEXT = "#28323f"         # body
MUTED = "#4e5b71"
FAINT = "#78849a"
ACCENT = "#3a6ba8"
ACCENT_DEEP = "#2d5b93"
ACCENT_SOFT = "rgba(58,107,168,28)"

#: One family list for Windows, macOS and Linux, in preference order. Every
#: entry before the Latin-only fallbacks carries both Latin and CJK, so the
#: primary family always renders Chinese — Qt then falls back per glyph.
UI_FAMILIES = ("Microsoft YaHei UI", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC",
               "Source Han Sans SC", "Noto Sans SC", "Segoe UI Variable Text", "Segoe UI",
               "Helvetica Neue", "Noto Sans", "DejaVu Sans")
MONO_FAMILIES = ("JetBrains Mono", "Cascadia Mono", "SF Mono", "Menlo", "Consolas",
                 "DejaVu Sans Mono", "Noto Sans Mono")
FONT_LIST = ", ".join(f'"{name}"' for name in UI_FAMILIES)
MONO_LIST = ", ".join(f'"{name}"' for name in MONO_FAMILIES)


def font_stack() -> tuple[str, ...]:
    """The curated families this machine actually has, in preference order.

    Keeping the unavailable ones out matters: a Qt font list resolves per glyph,
    but the *primary* family still decides what a raw font reports, and some
    platforms (offscreen, minimal containers) enumerate no families at all.
    """
    try:
        available = set(QFontDatabase.families())
    except Exception:  # no GUI font database yet
        available = set()
    chosen = tuple(name for name in UI_FAMILIES if name in available)
    return chosen or UI_FAMILIES

BASE_TOP = QColor("#edf3fb")
BASE_BOTTOM = QColor("#dde6f4")

#: x, y, radius (fraction of the long edge), colour, drift x/y, speed
BLOBS = (
    (0.10, -0.04, 0.86, "#93b6e8", 0.05, 0.04, 0.62),
    (1.00, 0.06, 0.66, "#c2abe6", 0.04, 0.05, 0.44),
    (0.82, 1.08, 0.78, "#8fd4c8", 0.05, 0.04, 0.52),
    (0.24, 1.00, 0.58, "#f0d3b4", 0.06, 0.03, 0.38),
    (0.56, 0.40, 0.66, "#cfdcf5", 0.04, 0.05, 0.30),
)


def _assets() -> dict:
    """Tiny generated PNGs for combo chevrons.

    Qt style sheets cannot draw a chevron, and shipping binary assets into the
    repository is unnecessary: one 20 px glyph is written to the user's cache on
    first run and referenced by path. Failures are non-fatal.
    """
    root = Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor") / "ui"
    try:
        root.mkdir(parents=True, exist_ok=True)
        chevron = root / "chevron.png"
        if not chevron.exists():
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor("#71809a"), 1.6)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline([QPointF(6.5, 8.5), QPointF(10, 12), QPointF(13.5, 8.5)])
            painter.end()
            pixmap.save(str(chevron))
        return {"chevron": chevron.as_posix()}
    except OSError:
        return {}


# --- style sheet -----------------------------------------------------------------------

def STYLE() -> str:  # noqa: N802 - kept as a callable name for existing imports
    assets = _assets()
    chevron = f'image: url("{assets["chevron"]}"); width: 10px; height: 10px;' if assets else ""
    families = ", ".join(f'"{name}"' for name in font_stack())
    return f"""
QWidget {{ color: {TEXT}; font-family: {families}; font-size: 14px; font-weight: 500; }}
QLabel {{ background: transparent; border: none; }}
QLabel[kind="eyebrow"] {{ color: {FAINT}; font-size: 10px; font-weight: 600; }}
QLabel[kind="title"] {{ color: {INK}; font-size: 30px; font-weight: 600; }}
QLabel[kind="section"] {{ color: {INK}; font-size: 21px; font-weight: 600; }}
QLabel[kind="muted"] {{ color: {MUTED}; font-size: 13px; }}
QLabel[kind="faint"] {{ color: {FAINT}; font-size: 12px; }}

QPushButton {{ background: rgba(255,255,255,140); border: 1px solid rgba(255,255,255,190);
               border-radius: 12px; padding: 9px 16px; color: {TEXT}; }}
QPushButton:hover {{ background: rgba(255,255,255,205); border-color: rgba(255,255,255,235); }}
QPushButton:pressed {{ background: rgba(255,255,255,160); }}
QPushButton:disabled {{ color: #a9b3c2; background: rgba(255,255,255,80); border-color: rgba(255,255,255,120); }}
QPushButton:checked {{ background: rgba(58,107,168,26); border-color: rgba(58,107,168,90); color: {ACCENT_DEEP}; }}
QPushButton[kind="nav"] {{ background: transparent; border: 1px solid transparent; border-radius: 10px;
                           padding: 8px 11px; text-align: left; color: {MUTED}; }}
QPushButton[kind="nav"]:hover {{ background: rgba(255,255,255,120); color: {TEXT}; }}
QPushButton[kind="nav"]:checked {{ background: rgba(255,255,255,150); color: {INK}; font-weight: 600;
                                   border-color: rgba(255,255,255,190); }}
QPushButton[kind="quiet"] {{ background: transparent; border: 1px solid transparent; padding: 7px 10px;
                             color: {MUTED}; border-radius: 10px; }}
QPushButton[kind="quiet"]:hover {{ background: rgba(255,255,255,120); color: {TEXT}; }}
QPushButton[kind="quiet"]:disabled {{ color: #b3bcc9; background: transparent; }}
QPushButton[kind="chip"] {{ background: rgba(255,255,255,92); border: 1px solid rgba(255,255,255,168);
                           border-radius: 15px; padding: 7px 14px; color: {MUTED}; font-size: 12px; }}
QPushButton[kind="chip"]:hover {{ background: rgba(255,255,255,200); color: {TEXT};
                                  border-color: rgba(255,255,255,235); }}
QPushButton[kind="send"] {{ background: qlineargradient(x1:0,y1:0,x2:0.6,y2:1, stop:0 #4d7db8, stop:1 {ACCENT_DEEP});
                            border: 1px solid rgba(255,255,255,110); border-radius: 17px; color: white;
                            min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px;
                            padding: 0px; font-size: 15px; font-weight: 600; }}
QPushButton[kind="send"]:hover {{ background: qlineargradient(x1:0,y1:0,x2:0.6,y2:1, stop:0 #5889c4, stop:1 #35659f); }}
QPushButton[kind="send"]:disabled {{ background: rgba(150,164,186,90); border-color: rgba(255,255,255,60); color: rgba(255,255,255,170); }}
QPushButton[primary="true"] {{ background: qlineargradient(x1:0,y1:0,x2:0.7,y2:1, stop:0 #4d7db8, stop:1 {ACCENT_DEEP});
                               border: 1px solid rgba(255,255,255,120); color: white; font-weight: 600; }}
QPushButton[primary="true"]:hover {{ background: qlineargradient(x1:0,y1:0,x2:0.7,y2:1, stop:0 #5a8bc6, stop:1 #35659f); }}
QPushButton[primary="true"]:disabled {{ background: rgba(150,164,186,110); border-color: rgba(255,255,255,80); }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: rgba(255,255,255,150);
    border: 1px solid rgba(255,255,255,200); border-radius: 11px; padding: 9px 12px;
    min-height: 20px; selection-background-color: #bcd3f2; selection-color: {INK}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ background: rgba(255,255,255,185); }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: rgba(58,107,168,140); background: rgba(255,255,255,225); }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ {chevron} }}
QComboBox QAbstractItemView {{ background: #f8fafd; color: {TEXT}; border: 1px solid rgba(150,170,200,90);
    border-radius: 10px; padding: 6px; selection-background-color: rgba(58,107,168,28);
    selection-color: {INK}; outline: none; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 16px; border: none; background: transparent; }}

QPlainTextEdit, QTextBrowser {{ background: transparent; border: none; color: {TEXT};
    selection-background-color: #bcd3f2; selection-color: {INK}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 2px 1px; }}
QScrollBar::handle:vertical {{ background: rgba(96,112,138,34); border-radius: 3px; min-height: 44px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(96,112,138,78); }}
QScrollBar::handle:vertical:pressed {{ background: rgba(112,128,152,90); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 8px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: rgba(120,140,170,70); border-radius: 3px; }}

QCheckBox {{ spacing: 9px; background: transparent; color: {MUTED}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px;
    background: rgba(255,255,255,190); border: 1px solid rgba(140,160,190,120); }}
QCheckBox::indicator:hover {{ border-color: rgba(58,107,168,140); }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QTabWidget::pane {{ background: transparent; border: none; }}
QTabBar::tab {{ background: transparent; border: none; padding: 10px 16px; color: {MUTED}; }}
QTabBar::tab:selected {{ color: {ACCENT_DEEP}; }}

QTableWidget {{ background: transparent; border: none; gridline-color: transparent;
    alternate-background-color: transparent; selection-background-color: transparent;
    selection-color: {INK}; }}
QTableWidget::item {{ padding: 6px; border-bottom: 1px solid rgba(130,150,180,26); }}
QTableWidget::item:selected {{ background: rgba(58,107,168,22); color: {INK}; }}
QTableWidget QComboBox {{ background: rgba(255,255,255,120); border: 1px solid rgba(255,255,255,170);
    border-radius: 8px; padding: 1px 6px; min-height: 0px; margin: 2px; }}
QTableWidget QComboBox::drop-down {{ width: 18px; }}
QTableWidget QLineEdit {{ background: transparent; border: none; padding: 2px; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; border: none; padding: 7px 6px;
    border-bottom: 1px solid rgba(130,150,180,50); color: {FAINT}; font-size: 11px; font-weight: 600; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QToolTip {{ background: #1c2736; color: #eef3fa; border: none; padding: 7px 9px; border-radius: 7px; }}
QMessageBox {{ background: #f7f9fd; }}
QMessageBox QLabel {{ color: {INK}; }}
QDialog {{ background: #f7f9fd; }}
QMenu {{ background: #f8fafd; border: 1px solid rgba(150,170,200,80); border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 18px 7px 12px; border-radius: 7px; }}
QMenu::item:selected {{ background: rgba(58,107,168,26); }}
"""


def text(value: str = "", kind: str | None = None, wrap: bool = False, *, tracking: float = 0.0,
         color: str | None = None, size: int | None = None, weight: int | None = None) -> QLabel:
    """A label with the shared type scale. Tracking is set on the font, not the sheet."""
    label = QLabel(value)
    if kind:
        label.setProperty("kind", kind)
    label.setWordWrap(wrap)
    if tracking or size or weight or color:
        font = QFont(label.font())
        if tracking:
            font.setLetterSpacing(QFont.AbsoluteSpacing, tracking)
        if size:
            font.setPixelSize(size)
        if weight:
            font.setWeight(QFont.Weight(weight))
        label.setFont(font)
    if color:
        label.setStyleSheet(f"color: {color};")
    return label


# --- backdrop --------------------------------------------------------------------------

_RENDERED: dict = {}  # (wallpaper, width, height, dpr) -> (sharp pixmap, frosted image), shared by every window


class Atmosphere(QWidget):
    """The wallpaper: silk filaments fanning over a pastel field.

    Rendered once per size at device resolution and cached, then blurred into
    the copy every glass surface samples. A static image, not a per-frame
    animation: detail is what makes glass look like glass, and detail is
    expensive to redraw.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self._sharp: QPixmap | None = None
        self._frost: QImage | None = None
        self._size = QSize(0, 0)
        self._dpr = 1.0
        self.wallpaper = "plain"
        self._rebuild = QTimer(self)
        self._rebuild.setSingleShot(True)
        self._rebuild.setInterval(90)
        self._rebuild.timeout.connect(self._refresh)

    def set_living(self, living: bool) -> None:
        """Kept for callers; the wallpaper is a still image."""
        self.update()

    def set_wallpaper(self, wallpaper: str) -> None:
        if wallpaper not in {"plain","silk","aurora"}:
            wallpaper="plain"
        if wallpaper==self.wallpaper and self._sharp is not None:
            return
        self.wallpaper=wallpaper
        self._sharp=None
        self._frost=None
        if self.isVisible():  # else it is rendered once, at its real size, when shown
            self._render()
        self.update()
        for glass in self.findChildren(Glass):
            glass.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild.start()  # dragging a window must not re-render per pixel

    def showEvent(self,event):
        self._rebuild.stop()
        self._render()
        super().showEvent(event)

    def _refresh(self):
        self._render()
        self.update()

    # -- painting ---------------------------------------------------------------

    def _silk(self, t: float, width: int, height: int, jitter: float) -> QPainterPath:
        """One strand of the fan: from the lower left, sweeping up to the right."""
        x0, y0 = -0.10 * width, height * (0.52 + 0.66 * t) + jitter * height
        c1x, c1y = width * (0.18 + 0.12 * math.sin(t * 3.4)), height * (0.60 + 0.42 * t) + jitter * height
        c2x, c2y = width * (0.58 + 0.14 * math.cos(t * 2.1)), height * (0.06 + 0.48 * t) + jitter * height
        x1, y1 = width * 1.10, height * (-0.28 + 0.68 * t) + jitter * height * 0.6
        path = QPainterPath(QPointF(x0, y0))
        path.cubicTo(QPointF(c1x, c1y), QPointF(c2x, c2y), QPointF(x1, y1))
        return path

    def _paint_wallpaper(self, painter: QPainter, width: int, height: int):
        if self.wallpaper == "plain":  # the white theme: a white page
            painter.fillRect(0, 0, width, height, QColor("#ffffff"))
            return
        if self.wallpaper=="aurora":
            painter.fillRect(0,0,width,height,QColor("#e8eff7"))
            for x,y,radius,color in ((.12,.15,.82,"#8db9ec"),(.88,.08,.75,"#c2ace9"),(.72,1.05,.9,"#8fd8cf"),(.22,.92,.65,"#f1cfbc")):
                glow=QRadialGradient(QPointF(width*x,height*y),max(width,height)*radius)
                glow.setColorAt(0,QColor(color))
                glow.setColorAt(1,QColor(240,246,252,0))
                painter.fillRect(0,0,width,height,glow)
            return
        painter.setRenderHint(QPainter.Antialiasing, True)
        span = max(width, height)

        field = QLinearGradient(QPointF(0, height * 1.05), QPointF(width, -height * 0.05))
        field.setColorAt(0.00, QColor("#8ba3c8"))
        field.setColorAt(0.24, QColor("#a6aecd"))
        field.setColorAt(0.48, QColor("#c4b4ce"))
        field.setColorAt(0.70, QColor("#d9c0cb"))
        field.setColorAt(0.88, QColor("#d3dcee"))
        field.setColorAt(1.00, QColor("#e4eaf6"))
        painter.fillRect(0, 0, width, height, field)

        glow = QRadialGradient(QPointF(width * 0.80, height * -0.02), span * 0.72)
        glow.setColorAt(0.0, QColor(255, 255, 255, 168))
        glow.setColorAt(0.45, QColor(255, 255, 255, 62))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(0, 0, width, height, glow)


        painter.setBrush(Qt.NoBrush)
        rng = random.Random(20261026)

        # broad bands first: they carry the colour
        for index in range(18):
            t = index / 17
            path = self._silk(t, width, height, rng.uniform(-0.04, 0.04))
            colour = QColor(rng.choice(("#ffffff", "#ffffff", "#efe6ff", "#ffe7ec", "#e4edff")))
            colour.setAlpha(6 + int(10 * rng.random()))
            painter.setPen(QPen(colour, 30 + 70 * rng.random(), Qt.SolidLine, Qt.RoundCap))
            painter.drawPath(path)

        # fine filaments: they carry the feather, clustered where the fan turns
        for index in range(96):
            t = rng.triangular(0.18, 0.86, 0.52)
            path = self._silk(t, width, height, rng.uniform(-0.05, 0.05))
            colour = QColor("#ffffff" if rng.random() < 0.8 else "#f4e9ff")
            colour.setAlpha(14 + int(48 * rng.random()))
            painter.setPen(QPen(colour, 0.8 + 2.2 * rng.random(), Qt.SolidLine, Qt.RoundCap))
            painter.drawPath(path)

        # a few bright threads catch the light
        for index in range(9):
            t = 0.12 + 0.66 * rng.random()
            path = self._silk(t, width, height, rng.uniform(-0.02, 0.02))
            colour = QColor(255, 255, 255, 120 + int(60 * rng.random()))
            painter.setPen(QPen(colour, 1.2 + 0.8 * rng.random(), Qt.SolidLine, Qt.RoundCap))
            painter.drawPath(path)

        # Depth and calm are graded last, over the strands: the rail sits on the
        # left and the status line in the corner, and both need quiet colour.
        shade = QRadialGradient(QPointF(width * 0.02, height * 1.06), span * 0.70)
        shade.setColorAt(0.0, QColor(64, 80, 120, 96))
        shade.setColorAt(1.0, QColor(64, 80, 120, 0))
        painter.fillRect(0, 0, width, height, shade)

        haze = QLinearGradient(QPointF(0, 0), QPointF(width * 0.30, 0))
        haze.setColorAt(0.0, QColor(255, 255, 255, 88))
        haze.setColorAt(0.60, QColor(255, 255, 255, 40))
        haze.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(0, 0, int(width * 0.30), height, haze)

    def _render(self):
        width, height = max(1, self.width()), max(1, self.height())
        dpr = self.devicePixelRatioF() or 1.0
        if (width, height, dpr) == (self._size.width(), self._size.height(), self._dpr) and self._frost is not None:
            return
        self._size = QSize(width, height)
        self._dpr = dpr
        key = (self.wallpaper, width, height, dpr)
        if key in _RENDERED:  # the same picture another window (the launcher) already rendered at this size
            self._sharp, self._frost = _RENDERED[key]
            return
        image = QImage(int(width * dpr), int(height * dpr), QImage.Format_RGB32)
        image.setDevicePixelRatio(dpr)
        image.fill(QColor("#cdd3e6"))
        painter = QPainter(image)
        self._paint_wallpaper(painter, width, height)
        painter.end()
        self._sharp = QPixmap.fromImage(image)

        # The frosted copy: down, then back up, twice — a real blur in C++.
        low_w, low_h = max(8, int(width * dpr) // 4), max(8, int(height * dpr) // 4)
        soft = image.scaled(low_w, low_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        soft = soft.scaled(max(4, low_w // 2), max(4, low_h // 2), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self._frost = soft.scaled(low_w, low_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        if len(_RENDERED) >= 4:  # a few sizes at most (the launcher and the window share one)
            _RENDERED.pop(next(iter(_RENDERED)))
        _RENDERED[key] = (self._sharp, self._frost)

    def frosted(self) -> tuple[QImage | None, float]:
        if self._frost is None:
            self._render()
        if self._frost is None:
            return None, 1.0
        return self._frost, self._frost.width() / max(1, self.width())

    def paintEvent(self, event):
        if self._sharp is None:
            self._render()
        painter = QPainter(self)
        if self._sharp is not None:
            # A cached image may still have the old size during the resize
            # debounce. Always cover the entire window; otherwise its first
            # frame or newly exposed edges can show stale backing-store pixels.
            painter.drawPixmap(self.rect(),self._sharp,self._sharp.rect())
        if self.wallpaper != "plain":
            self._paint_edge(painter)

    def _paint_edge(self, painter: QPainter) -> None:
        """A very light frame, so the pane reads as glass laid over the desktop."""
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = QRectF(self.rect())
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1.0))
        painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))
        for offset, alpha in ((1.5, 18), (2.5, 12), (3.5, 7)):
            painter.setPen(QPen(QColor(40, 62, 96, alpha), 1.0))
            painter.drawRect(rect.adjusted(offset, offset, -offset, -offset))


# --- glass -----------------------------------------------------------------------------

class Glass(QWidget):
    """A frosted panel that samples the window backdrop.

    ``tint`` is the white wash laid over the blur (0-255): the lower it is, the
    more of the room shows through. ``glow`` is animatable, used for focus.
    """

    def __init__(self, parent=None, *, radius: int = 26, padding: int = 24, tint: int = 62,
                 rim: int = 210, sheen: bool = True, refract: float = 9.0, shadow: int = 0,
                 vibrancy: float = 0.42):
        super().__init__(parent)
        self.radius = radius
        self.tint = tint
        self.rim = rim
        self.sheen = sheen
        self.refract = refract
        self.shadow = shadow
        self.vibrancy = vibrancy
        self._glow = 0.0
        self._jelly = 0.0
        self._jelly_animation = None
        self._light = QPointF(0.3, 0.0)
        self._atmosphere: Atmosphere | None = None
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setMouseTracking(True)
        self._cache: QPixmap | None = None  # the glass without the moving highlight, rendered once per look
        self._cache_key = None
        self._sheen_timer = QTimer(self)
        self._sheen_timer.setSingleShot(True)
        self._sheen_timer.setInterval(33)
        self._sheen_timer.timeout.connect(self.update)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding + shadow, padding + shadow, padding + shadow, padding + shadow)
        self.body.setSpacing(14)

    # -- animatable focus glow
    def _get_glow(self) -> float:
        return self._glow

    def _set_glow(self, value: float) -> None:
        self._glow = float(value)
        self.update()

    glow = Property(float, _get_glow, _set_glow)

    def _get_jelly(self):
        return self._jelly

    def _set_jelly(self,value):
        self._jelly=float(value)
        self.update()

    jelly = Property(float,_get_jelly,_set_jelly)

    def _settle(self,target):
        from codedoctor.desktop import motion
        from PySide6.QtCore import QPropertyAnimation,QEasingCurve
        if self._jelly_animation is not None:
            self._jelly_animation.stop()
            self._jelly_animation.deleteLater()
        if motion.reduced():
            self._set_jelly(target)
            return
        animation=QPropertyAnimation(self,b"jelly",self)
        animation.setDuration(320)
        animation.setStartValue(self._jelly)
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutBack)
        self._jelly_animation=animation
        animation.start()

    def enterEvent(self,event):
        self._settle(1.0)
        super().enterEvent(event)

    def leaveEvent(self,event):
        self._settle(0.0)
        super().leaveEvent(event)

    def atmosphere(self) -> Atmosphere | None:
        if self._atmosphere is None:
            window = self.window()
            if window is not None:
                self._atmosphere = window.findChild(Atmosphere)
        return self._atmosphere

    def mouseMoveEvent(self, event):
        # Only this surface repaints, from its cached glass, and at most ~30 times a second: a repaint also repaints
        # every widget on the panel, and pointer events come far faster than that on a slow machine.
        width = max(1, self.width())
        height = max(1, self.height())
        self._light = QPointF(event.position().x() / width, event.position().y() / height)
        if self.sheen and not self._sheen_timer.isActive():
            self._sheen_timer.start()
        super().mouseMoveEvent(event)

    def _paint_shadow(self, painter: QPainter, rect: QRectF) -> None:
        """A soft drop shadow painted inside our own bounds (no QGraphicsEffect,
        which would fight the entrance animation)."""
        if not self.shadow:
            return
        layers = 12
        painter.setPen(Qt.NoPen)
        for index in range(layers, 0, -1):
            k = index / layers
            spread = self.shadow * k
            alpha = int(2 + 10 * (1 - k) ** 2)
            shape = QPainterPath()
            shape.addRoundedRect(rect.adjusted(-spread, -spread + 6, spread, spread + 6),
                                 self.radius + spread, self.radius + spread)
            painter.setBrush(QColor(22, 36, 64, alpha))
            painter.drawPath(shape)

    def paintEvent(self, event):
        """The cached glass (see _render_glass), then the highlight that follows the pointer on top."""
        pad = self.shadow
        inset = 0.75 + max(-.2, min(1.6, self._jelly * 1.2))
        rect = QRectF(self.rect()).adjusted(pad + inset, pad + inset, -pad - inset, -pad - inset)
        atmosphere = self.atmosphere()
        if atmosphere is not None and not atmosphere.isAncestorOf(self):
            atmosphere = None
        image, scale = atmosphere.frosted() if atmosphere is not None else (None, 1.0)
        origin = self.mapTo(atmosphere, QPoint(int(pad), int(pad))) if atmosphere is not None else QPoint()
        dpr = self.devicePixelRatioF() or 1.0
        jelly = round(self._jelly, 2)
        light = (round(self._light.x(), 1), round(self._light.y(), 1)) if jelly else (0, 0)  # only the jelly uses it
        key = (self.width(), self.height(), dpr, origin.x(), origin.y(), jelly, light, round(self._glow, 2),
               image.cacheKey() if image is not None else 0, self.tint, self.rim, self.refract, self.vibrancy,
               self.radius, self.shadow)
        if key != self._cache_key or self._cache is None:
            self._cache_key = key
            self._cache = QPixmap(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
            self._cache.setDevicePixelRatio(dpr)
            self._cache.fill(Qt.transparent)
            layer = QPainter(self._cache)
            layer.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            self._render_glass(layer, rect, image, scale, origin)
            layer.end()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cache)
        # the highlight that follows the cursor, like a specular highlight on glass
        if self.sheen and self.underMouse():
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(rect, self.radius, self.radius)
            sheen = QRadialGradient(
                QPointF(rect.left() + rect.width() * self._light.x(),
                        rect.top() + rect.height() * self._light.y()),
                max(rect.width(), rect.height()) * 0.62)
            sheen.setColorAt(0.0, QColor(255, 255, 255, 62))
            sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setClipPath(path)
            painter.fillRect(rect, sheen)

    def _render_glass(self, painter: QPainter, rect: QRectF, image, scale: float, origin: QPoint) -> None:
        """Everything but the moving highlight: drawn once per size, place, wallpaper and state, then reused - the
        overlay blend, the refraction and the 12-layer shadow are far too slow to redraw on every repaint."""
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        self._paint_shadow(painter, rect)

        # 1. what is actually behind this panel, blurred
        if image is not None and scale:
            source = QRectF(origin.x() * scale, origin.y() * scale,
                            max(1.0, rect.width() * scale), max(1.0, rect.height() * scale))
            source.translate((self._light.x()-.5)*self._jelly*6*scale,
                             (self._light.y()-.5)*self._jelly*6*scale)
            painter.save()
            painter.setClipPath(path)
            painter.drawImage(rect, image, source)
            # Vibrancy: the same blurred pixels composited over themselves pull
            # the colour back up, so the glass reads as coloured glass rather
            # than grey milk.
            painter.setCompositionMode(QPainter.CompositionMode_Overlay)
            painter.setOpacity(self.vibrancy)
            painter.drawImage(rect, image, source)
            painter.restore()
        else:
            painter.fillPath(path, BASE_BOTTOM)

        # 2. the glass wash
        wash = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        wash.setColorAt(0.0, QColor(255, 255, 255, min(255, self.tint + 22)))
        wash.setColorAt(0.55, QColor(255, 255, 255, self.tint))
        wash.setColorAt(1.0, QColor(255, 255, 255, max(0, self.tint - 8)))
        painter.fillPath(path, wash)

        # 3. edge refraction: the border band magnifies what is behind it, the
        #    way a thick glass edge bends light. This is what separates a frosted
        #    panel from a lensed one.
        if image is not None and self.refract > 0:
            band = QPainterPath()
            band.setFillRule(Qt.OddEvenFill)
            band.addRoundedRect(rect, self.radius, self.radius)
            inset = max(2.0, self.radius - self.refract * 0.6)
            band.addRoundedRect(rect.adjusted(self.refract, self.refract, -self.refract, -self.refract),
                                inset, inset)
            painter.save()
            painter.setClipPath(band)
            grow = self.refract * 1.9
            painter.drawImage(rect.adjusted(-grow, -grow, grow, grow), image,
                              source.adjusted(-grow * scale, -grow * scale, grow * scale, grow * scale))
            painter.fillPath(band, QColor(255, 255, 255, 26))
            painter.restore()

        # 4. rim: bright top-left, fading bottom-right, plus a hairline for edges
        if self._glow > 0.01:
            painter.setPen(QPen(QColor(58, 107, 168, int(120 * self._glow)), 1.4))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
        if self.rim <= 0:
            return  # an edge-less sheet: pure blur, used for the rail
        rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
        rim.setColorAt(0.0, QColor(255, 255, 255, self.rim))
        rim.setColorAt(0.42, QColor(255, 255, 255, int(self.rim * 0.42)))
        rim.setColorAt(1.0, QColor(255, 255, 255, int(self.rim * 0.78)))
        atmosphere = self.atmosphere()
        plain = atmosphere is not None and atmosphere.wallpaper == "plain"
        painter.setPen(QPen(QColor("#e5e5e5"), 1.0) if plain else QPen(rim, 1.0))  # white on white: a grey hairline
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        if not getattr(self, "inner_rim", True):
            return
        hairline = QPainterPath()
        hairline.addRoundedRect(rect.adjusted(1.4, 1.4, -1.4, -1.4), max(0.0, self.radius - 1.2), max(0.0, self.radius - 1.2))
        painter.setPen(QPen(QColor(26, 44, 74, 26), 1.0))
        painter.drawPath(hairline)


# --- small painted marks ---------------------------------------------------------------

class MedicalMark(QWidget):
    """The mark of the app: Lumen itself (the name stays for the pages that use it)."""

    def __init__(self, size=42, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        from codedoctor.desktop.team_ui import art

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        image = art("lumen")
        if image is not None:
            painter.drawImage(QRectF(self.rect()), image)
        painter.end()


class LiquidSlider(QSlider):
    """Click anywhere or drag directly; callers map indices to valid rosters."""

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)

    def _at(self, x):
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), round(x - 17),
                                              max(1, self.width() - 34), self.invertedAppearance())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setSliderDown(True)
            self.setValue(self._at(event.position().x()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self.setValue(self._at(event.position().x()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isSliderDown():
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        y = self.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(126, 148, 180, 70))
        painter.drawRoundedRect(QRectF(14, y - 3, self.width() - 28, 6), 3, 3)
        ratio = (self.value() - self.minimum()) / max(1, self.maximum() - self.minimum())
        x = 17 + ratio * (self.width() - 34)
        painter.setBrush(QColor(58, 107, 168, 120))
        painter.drawRoundedRect(QRectF(14, y - 3, max(1, x - 14), 6), 3, 3)
        for radius, alpha in ((15, 10), (12, 16)):
            painter.setBrush(QColor(46, 88, 142, alpha))
            painter.drawEllipse(QPointF(x, y + 1), radius, radius)
        handle = QLinearGradient(x - 10, y - 12, x + 10, y + 12)
        handle.setColorAt(0, QColor(255, 255, 255, 250))
        handle.setColorAt(1, QColor(226, 236, 249, 220))
        painter.setPen(QPen(QColor(255, 255, 255, 240), 1.4))
        painter.setBrush(handle)
        painter.drawEllipse(QPointF(x, y), 11, 11)
