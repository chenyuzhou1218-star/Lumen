"""The composer's model and thinking controls, drawn by hand: a rounded pill (⚡ model · level ⌄), a thinking popover
(level title, model chip, fast mode, reset, a thick slider whose filled part sparkles and turns violet at the top
level), and a model list popover. Plain QPushButtons and QMenus looked rough next to what the user showed; these
are painted so corners, shadows and colours are exact."""

from __future__ import annotations

import math
import random
from typing import Callable

from PySide6.QtCore import (QEasingCurve, QElapsedTimer, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from codedoctor.desktop.i18n import tr


def _t(key: str, zh: str, en: str) -> str:
    """A line from the translation table when it is there (i18n.py); until then 中文 or English by the window's language."""
    from codedoctor.desktop import i18n

    if key in i18n.S:
        return tr(key)
    return zh if i18n.language().startswith("zh") else en
from codedoctor.desktop.theme import C
from codedoctor.models.reasoning import LEVELS


def level_name(key: str) -> str:
    return tr(f"lvl_{key}")

BLUE = QColor("#3b7cf4")
BLUE_DEEP = QColor("#2f63e8")
VIOLET_A = QColor("#4f46e5")
VIOLET_B = QColor("#a855f7")
INK = QColor("#1f2329")
GREY = QColor("#8a8f98")
TRACK = QColor("#ece8e1")
PILL = QColor("#f2f2f2")
PILL_HOVER = QColor("#e9e9e9")
ROW_HOVER = QColor("#f4f1eb")
ORANGE = QColor("#e8590c")
SHADOW = 16  # px of soft shadow around a popover card


def _font(px: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def draw_icon(p: QPainter, kind: str, rect: QRectF, color: QColor, width: float = 1.7) -> None:
    """Small stroke icons used here: bolt, reset, chevron, check, shield, plus."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    if kind == "bolt":
        path = QPainterPath(QPointF(x + w * 0.58, y + h * 0.06))
        for px, py in ((0.22, 0.56), (0.48, 0.56), (0.40, 0.94), (0.80, 0.42), (0.54, 0.42), (0.58, 0.06)):
            path.lineTo(x + w * px, y + h * py)
        p.setBrush(color)
        p.drawPath(path)
    elif kind == "reset":
        p.drawArc(QRectF(x + w * 0.14, y + h * 0.14, w * 0.72, h * 0.72), 100 * 16, 290 * 16)
        p.drawLine(QPointF(x + w * 0.40, y + h * 0.10), QPointF(x + w * 0.52, y + h * 0.16))
        p.drawLine(QPointF(x + w * 0.40, y + h * 0.10), QPointF(x + w * 0.44, y + h * 0.26))
    elif kind == "chevron":
        p.drawLine(QPointF(x + w * 0.28, y + h * 0.40), QPointF(x + w * 0.50, y + h * 0.62))
        p.drawLine(QPointF(x + w * 0.50, y + h * 0.62), QPointF(x + w * 0.72, y + h * 0.40))
    elif kind == "right":
        p.drawLine(QPointF(x + w * 0.40, y + h * 0.26), QPointF(x + w * 0.62, y + h * 0.50))
        p.drawLine(QPointF(x + w * 0.62, y + h * 0.50), QPointF(x + w * 0.40, y + h * 0.74))
    elif kind == "check":
        p.drawLine(QPointF(x + w * 0.20, y + h * 0.52), QPointF(x + w * 0.42, y + h * 0.74))
        p.drawLine(QPointF(x + w * 0.42, y + h * 0.74), QPointF(x + w * 0.82, y + h * 0.28))
    elif kind == "shield":
        path = QPainterPath(QPointF(x + w / 2, y + h * 0.08))
        path.lineTo(x + w * 0.86, y + h * 0.24)
        path.cubicTo(x + w * 0.86, y + h * 0.62, x + w * 0.70, y + h * 0.82, x + w / 2, y + h * 0.94)
        path.cubicTo(x + w * 0.30, y + h * 0.82, x + w * 0.14, y + h * 0.62, x + w * 0.14, y + h * 0.24)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(x + w * 0.36, y + h * 0.50), QPointF(x + w * 0.47, y + h * 0.62))
        p.drawLine(QPointF(x + w * 0.47, y + h * 0.62), QPointF(x + w * 0.66, y + h * 0.40))
    elif kind == "hand":
        for i, (dx, top) in enumerate(((0.30, 0.30), (0.44, 0.16), (0.58, 0.20), (0.72, 0.34))):
            p.drawLine(QPointF(x + w * dx, y + h * top), QPointF(x + w * dx, y + h * 0.58))
        path = QPainterPath(QPointF(x + w * 0.30, y + h * 0.56))
        path.cubicTo(x + w * 0.22, y + h * 0.50, x + w * 0.12, y + h * 0.58, x + w * 0.20, y + h * 0.68)
        path.cubicTo(x + w * 0.30, y + h * 0.82, x + w * 0.40, y + h * 0.94, x + w * 0.56, y + h * 0.94)
        path.cubicTo(x + w * 0.70, y + h * 0.94, x + w * 0.74, y + h * 0.80, x + w * 0.72, y + h * 0.58)
        p.drawPath(path)
    elif kind == "team":  # two people: the way of working (协作方式)
        p.drawEllipse(QRectF(x + w * 0.16, y + h * 0.14, w * 0.30, h * 0.30))
        p.drawArc(QRectF(x + w * 0.02, y + h * 0.52, w * 0.58, h * 0.56), 0, 180 * 16)
        p.drawEllipse(QRectF(x + w * 0.58, y + h * 0.22, w * 0.24, h * 0.24))
        p.drawArc(QRectF(x + w * 0.50, y + h * 0.56, w * 0.46, h * 0.44), 0, 180 * 16)
    elif kind == "warn":
        p.drawEllipse(QRectF(x + w * 0.08, y + h * 0.08, w * 0.84, h * 0.84))
        p.drawLine(QPointF(x + w / 2, y + h * 0.28), QPointF(x + w / 2, y + h * 0.56))
        p.setBrush(color)
        p.drawEllipse(QPointF(x + w / 2, y + h * 0.71), w * 0.05, w * 0.05)
    elif kind == "plus":
        p.drawLine(QPointF(x + w / 2, y + h * 0.18), QPointF(x + w / 2, y + h * 0.82))
        p.drawLine(QPointF(x + w * 0.18, y + h / 2), QPointF(x + w * 0.82, y + h / 2))
    elif kind == "up":
        p.drawLine(QPointF(x + w / 2, y + h * 0.22), QPointF(x + w / 2, y + h * 0.80))
        p.drawLine(QPointF(x + w * 0.26, y + h * 0.46), QPointF(x + w / 2, y + h * 0.22))
        p.drawLine(QPointF(x + w * 0.74, y + h * 0.46), QPointF(x + w / 2, y + h * 0.22))
    p.restore()


class IconButton(QPushButton):
    """A flat round icon button (＋, ⚡, ↺): no frame, a soft grey circle on hover; 'on' tints it."""

    def __init__(self, kind: str, tip: str, size: int = 32, icon: int = 18, color: QColor = INK):
        super().__init__()
        self.kind, self.icon_px, self.color = kind, icon, color
        self.on = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.setFlat(True)
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(ROW_HOVER)
            p.drawEllipse(QRectF(self.rect()))
        r = (self.width() - self.icon_px) / 2
        draw_icon(p, self.kind, QRectF(r, r, self.icon_px, self.icon_px), self.color)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class TextButton(QPushButton):
    """A flat text button with an optional leading icon; checkable ones turn blue on a light blue pill when on."""

    def __init__(self, text: str, icon: str | None = None, tip: str = ""):
        super().__init__(text)
        self.icon_kind = icon
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.setFont(_font(14))
        self.setFixedHeight(32)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(text) + (44 if icon else 24))
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isCheckable() and self.isChecked()
        if on or self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(59, 124, 244, 26) if on else ROW_HOVER)
            p.drawRoundedRect(QRectF(self.rect()), self.height() / 2, self.height() / 2)
        color = BLUE_DEEP if on else (INK if self.underMouse() else GREY)
        x = 12
        if self.icon_kind:
            draw_icon(p, self.icon_kind, QRectF(x, (self.height() - 16) / 2, 16, 16), color, 1.5)
            x += 22
        p.setPen(color)
        p.setFont(self.font())
        p.drawText(QRectF(x, 0, self.width() - x - 8, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class ModelPill(QPushButton):
    """⚡ model · level ⌄ on a light grey capsule; opens the thinking popover."""

    def __init__(self):
        super().__init__()
        self.model_text, self.level_text, self.fast = "", "", False
        self.limit = 10000  # the message box narrows this in a narrow window
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.setFont(_font(14))
        self.setStyleSheet("border: none; background: transparent;")
        self.setToolTip(tr("model_tip"))
        self._fit()

    def set_state(self, model: str, level: str, fast: bool) -> None:
        self.model_text, self.level_text, self.fast = model, level, fast
        self._fit()
        self.update()

    def _fit(self) -> None:
        fm = self.fontMetrics()
        w = 14 + fm.horizontalAdvance(self.model_text)
        w += (8 + fm.horizontalAdvance(self.level_text)) if self.level_text else 0
        self.setFixedWidth(min(w + 34, self.limit))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(PILL_HOVER if self.underMouse() or self.isDown() else PILL)
        p.drawRoundedRect(QRectF(self.rect()), self.height() / 2, self.height() / 2)
        fm = self.fontMetrics()
        x = 14
        p.setFont(self.font())
        p.setPen(INK)
        room = self.width() - 40 - (fm.horizontalAdvance(self.level_text) + 8 if self.level_text else 0)
        model = fm.elidedText(self.model_text, Qt.ElideRight, room)
        p.drawText(QRectF(x, 0, 400, self.height()), Qt.AlignVCenter | Qt.AlignLeft, model)
        x += fm.horizontalAdvance(model)
        if self.level_text:
            p.setPen(GREY)
            p.drawText(QRectF(x + 8, 0, 200, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.level_text)
        draw_icon(p, "chevron", QRectF(self.width() - 26, 9, 16, 16), GREY, 1.6)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class SendButton(QPushButton):
    """A filled round send button; grey when there is nothing to send."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("send_tip"))
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2f2f2f" if self.underMouse() else "#0d0d0d") if self.isEnabled() else QColor("#d5d8de"))
        p.drawEllipse(QRectF(self.rect()))
        draw_icon(p, "up", QRectF(9, 9, 18, 18), QColor("white"), 2.0)
        p.end()


# --- popover cards --------------------------------------------------------------------------------------------------

class Popover(QWidget):
    """A floating rounded card with a soft shadow; closes when you click elsewhere."""

    def __init__(self, parent=None, radius: int = 18):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.radius = radius
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(SHADOW + 14, SHADOW + 12, SHADOW + 14, SHADOW + 12)
        self.body.setSpacing(6)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        card = QRectF(self.rect()).adjusted(SHADOW, SHADOW, -SHADOW, -SHADOW)
        for i in range(SHADOW, 0, -2):  # soft shadow, slightly lower than the card
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(15, 23, 42, int(9 * (1 - i / SHADOW) ** 2) + 1))
            p.drawRoundedRect(card.adjusted(-i, -i + 4, i, i + 4), self.radius + i, self.radius + i)
        p.setBrush(QColor("white"))
        p.setPen(QPen(QColor(15, 23, 42, 18), 1))
        p.drawRoundedRect(card, self.radius, self.radius)
        p.end()

    def open_above(self, anchor: QWidget, align_right: bool = True) -> None:
        """Show above the anchor (the composer's buttons sit at the bottom of the window): it fades in and rises 8 px."""
        self.adjustSize()
        top_left = anchor.mapToGlobal(QPoint(0, 0))
        x = top_left.x() + anchor.width() - self.width() + SHADOW if align_right else top_left.x() - SHADOW
        end = QPoint(x, top_left.y() - self.height() + SHADOW - 6)
        self.move(end + QPoint(0, 8))
        self.setWindowOpacity(0.0)
        self.show()
        self._anims = []
        for prop, a, b in ((b"windowOpacity", 0.0, 1.0), (b"pos", end + QPoint(0, 8), end)):
            anim = QPropertyAnimation(self, prop, self)
            anim.setDuration(180)
            anim.setStartValue(a)
            anim.setEndValue(b)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._anims.append(anim)


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


class ThinkSlider(QWidget):
    """A thick rounded track. The knob follows the pointer while dragging and springs onto the nearest stop when let
    go; the filled part ends at the knob and its colour follows it (blue, deeper blue, violet at the top stop); light
    particles stream from the left toward the knob and gather to its centre line; reaching the top stop bursts.
    Everything moves on a 60 fps clock while the slider is shown."""
    changed = Signal(int)     # a stop, chosen (on release, or a click)
    hovering = Signal(int)    # the nearest stop while dragging (the title follows it)

    PAD_X, PAD_Y, TRACK_H = 18, 16, 40  # room around the track: the top level's halo and burst are drawn there, not cut

    def __init__(self, stops: int, value: int = 2):
        super().__init__()
        self.stops = stops
        self.value = value
        self.pos = float(value)  # the knob, in stops (fractional while moving)
        self.dragging = False
        self.setFixedHeight(self.TRACK_H + 2 * self.PAD_Y)
        self.setMinimumWidth(300 + 2 * self.PAD_X)
        self.setCursor(Qt.PointingHandCursor)
        self.rnd = random.Random(11)
        self.particles = [self._particle(fresh=True) for _ in range(34)]
        self.burst: list[list[float]] = []
        self.anim = QVariantAnimation(self)
        self.anim.valueChanged.connect(self._moved)
        self.clock = QElapsedTimer()
        self.tick = QTimer(self)
        self.tick.setInterval(16)
        self.tick.timeout.connect(self._step)

    # --- geometry ---
    def _x(self, pos: float) -> float:
        r = self.TRACK_H / 2
        return self.PAD_X + r + pos * (self.width() - 2 * self.PAD_X - 2 * r) / (self.stops - 1)

    def _pos_at(self, x: float) -> float:
        r = self.TRACK_H / 2
        span = max(self.width() - 2 * self.PAD_X - 2 * r, 1)
        return max(0.0, min(self.stops - 1.0, (x - self.PAD_X - r) * (self.stops - 1) / span))

    # --- particles ---
    def _particle(self, fresh: bool = False) -> list[float]:
        """[x along the fill 0..1, y offset -1..1, speed, size, life]"""
        return [self.rnd.random() * (1.0 if fresh else 0.25), self.rnd.uniform(-1, 1), self.rnd.uniform(0.10, 0.28),
                self.rnd.choice((1.0, 1.3, 1.7, 2.2)), self.rnd.random()]

    def showEvent(self, e):
        self.clock.start()
        self.tick.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.tick.stop()
        super().hideEvent(e)

    def _step(self) -> None:
        dt = min(self.clock.restart() / 1000.0, 0.05)
        speed = 0.6 + 0.35 * self.pos  # the higher the level, the livelier
        for pt in self.particles:
            pt[0] += pt[2] * dt * speed
            pt[1] *= (1 - 1.6 * dt * pt[0])  # drawn to the centre line as they near the knob
            pt[4] += dt * 0.7
            if pt[0] >= 1.0:
                pt[:] = self._particle()
        for b in self.burst:
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            b[3] += 60 * dt
            b[4] -= dt * 1.6
        self.burst = [b for b in self.burst if b[4] > 0]
        self.update()

    def _celebrate(self) -> None:
        kx, cy = self._x(self.stops - 1), self.height() / 2  # where the knob lands, not where it set off
        for _ in range(34):  # all round the knob: the room around the track keeps it in view
            a = self.rnd.uniform(0, math.tau)
            v = self.rnd.uniform(30, 90)
            self.burst.append([kx, cy, math.cos(a) * v, math.sin(a) * v, 1.0])

    # --- moving the knob ---
    def _moved(self, v) -> None:
        self.pos = float(v)
        self.update()

    def set_value(self, v: int, animate: bool = True) -> None:
        v = max(0, min(self.stops - 1, v))
        reached_top = v == self.stops - 1 and self.value != v
        self.value = v
        if animate and self.isVisible():
            self.anim.stop()
            self.anim.setStartValue(self.pos)
            self.anim.setEndValue(float(v))
            self.anim.setDuration(340)
            self.anim.setEasingCurve(QEasingCurve.OutBack)  # a small overshoot: it springs into place
            self.anim.start()
        else:
            self.pos = float(v)
            self.update()
        if reached_top:
            self._celebrate()

    def mousePressEvent(self, e):
        self.anim.stop()
        self.dragging = True
        self.pos = self._pos_at(e.position().x())
        self.hovering.emit(round(self.pos))
        self.update()

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.pos = self._pos_at(e.position().x())
            self.hovering.emit(round(self.pos))
            self.update()

    def mouseReleaseEvent(self, e):
        self.dragging = False
        v = round(self.pos)
        self.set_value(v)
        self.changed.emit(v)

    # --- drawing ---
    def colour(self) -> tuple[QColor, QColor]:
        """(start, end) of the fill for the knob's position: blue, then deeper, violet in the last step."""
        t = self.pos / (self.stops - 1)
        top = max(0.0, (self.pos - (self.stops - 2)))  # 0..1 over the last step
        a = _mix(_mix(QColor("#5b9bff"), BLUE, t * 1.4), QColor("#3b2fd6"), top)
        b = _mix(_mix(BLUE, BLUE_DEEP, t), QColor("#8b2be2"), top)  # a deep violet, not a pale one
        return a, b

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h, px, py = self.TRACK_H, self.PAD_X, self.PAD_Y
        track = QRectF(px, py + 4, self.width() - 2 * px, h - 8)
        rad = track.height() / 2
        top = max(0.0, (self.pos - (self.stops - 2)))
        p.setPen(Qt.NoPen)
        for grow, alpha in ((14, 18), (9, 30), (5, 46)):  # the top level glows violet all round the track
            if top > 0:
                c = QColor(139, 43, 226, int(alpha * top))
                p.setBrush(c)
                p.drawRoundedRect(track.adjusted(-grow, -grow, grow, grow), rad + grow, rad + grow)
        p.setBrush(TRACK)
        p.drawRoundedRect(track, rad, rad)
        kx = self._x(self.pos)
        fill = QRectF(px, py + 4, kx - px + h / 2 - 3, h - 8)
        a, b = self.colour()
        grad = QLinearGradient(px, 0, px + max(fill.width(), 1), 0)
        grad.setColorAt(0, a)
        grad.setColorAt(1, b)
        clip = QPainterPath()
        clip.addRoundedRect(fill, rad, rad)
        p.setBrush(grad)
        p.drawPath(clip)
        cy = py + h / 2
        p.save()
        p.setClipPath(clip)  # light only inside the filled part, left of the knob
        for x01, yo, _sp, size, life in self.particles:
            x = px + 4 + x01 * (kx - px - 8)
            y = cy + yo * (track.height() / 2 - 4)
            twinkle = 0.55 + 0.45 * math.sin(life * 6.0)
            p.setBrush(QColor(255, 255, 255, int(70 + 150 * twinkle * min(1.0, x01 * 3))))
            p.drawEllipse(QPointF(x, y), size * 0.6, size * 0.6)
        glow = QLinearGradient(kx - 60, 0, kx, 0)  # a soft glow just behind the knob; fainter at the top, which is deep
        glow.setColorAt(0, QColor(255, 255, 255, 0))
        glow.setColorAt(1, QColor(255, 255, 255, int(60 * (1 - 0.6 * top))))
        p.setBrush(glow)
        p.drawRect(QRectF(kx - 60, py, 60, h))
        p.restore()
        p.setBrush(QColor(15, 23, 42, 60))
        for i in range(self.stops):  # the stops not reached yet
            if self._x(i) > kx + h / 2:
                p.drawEllipse(QPointF(self._x(i), cy), 2.6, 2.6)
        for bx, by, _vx, _vy, life in self.burst:  # the top level's burst
            c = _mix(QColor("#8b2be2"), QColor("#ffc43d"), self.rnd.random() * 0.5)
            c.setAlpha(int(255 * max(0.0, life)))
            p.setBrush(c)
            p.drawEllipse(QPointF(bx, by), 2.8, 2.8)
        for grow, alpha in ((4, 10), (2, 22)):  # knob
            p.setBrush(QColor(15, 23, 42, alpha))
            p.drawEllipse(QPointF(kx, cy + 1.5), h / 2 - 3 + grow / 2, h / 2 - 3 + grow / 2)
        p.setBrush(QColor("white"))
        p.setPen(QPen(QColor(139, 43, 226, int(22 + 110 * top)), 1 + 1.2 * top))  # a violet ring at the top
        p.drawEllipse(QPointF(kx, cy), h / 2 - 3, h / 2 - 3)
        p.end()


class ThinkingPopover(Popover):
    """The level, big, with the model as a chip under it (click: choose the model), ↺ (each agent's own setting);
    then the slider. The title follows the knob while you drag. levels / name: Lumen's 不思考 ... 最高, or an
    engine model's own levels by its own names (Low ... Ultra); a model without levels shows no slider."""
    level_chosen = Signal(object)   # a level key, or None (each agent's own)
    choose_model = Signal()

    def __init__(self, parent, level: str | None, model: str, levels: tuple | list = LEVELS,
                 name: Callable[[str], str] = level_name):
        super().__init__(parent)
        self.levels, self.name = list(levels), name
        self.setFixedWidth(372 + 2 * ThinkSlider.PAD_X + 2 * SHADOW)  # the track keeps its width; its halo has room
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.reset = IconButton("reset", "", 30, 18, GREY)
        self.reset.hide()  # a level is always chosen: there is no 默认 to go back to
        mid = QVBoxLayout()
        mid.setSpacing(4)
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(_font(17, bold=True))
        self.chip = QPushButton(f"{model}  ›")
        self.chip.setCursor(Qt.PointingHandCursor)
        self.chip.setFont(_font(13))
        self.chip.setToolTip(tr("choose_model"))
        self.chip.setStyleSheet("QPushButton { border: none; background: #f1f2f4; color: #5b6170; padding: 4px 12px;"
                                " border-radius: 8px; } QPushButton:hover { background: #e8e9ec; color: #1f2329; }")
        self.chip.clicked.connect(self.choose_model.emit)
        mid.addWidget(self.title)
        mid.addWidget(self.chip, 0, Qt.AlignHCenter)
        top.addSpacing(30)  # balances ↺ so the title sits in the middle
        top.addStretch(1)
        top.addLayout(mid)
        top.addStretch(1)
        top.addWidget(self.reset, 0, Qt.AlignTop)
        self.body.addLayout(top)
        self.body.addSpacing(8)
        if len(self.levels) < 2:  # nothing to choose: the model thinks as it does
            self.reset.hide()
            self.slider = None
            self.title.setText(tr("no_levels"))
            self.title.setStyleSheet(f"color: {GREY.name()};")
            return
        lv = self.levels
        start = lv.index(level) if level in lv else lv.index("medium") if "medium" in lv else len(lv) // 2
        self.slider = ThinkSlider(len(lv), start)
        self.body.addWidget(self.slider)
        self.slider.hovering.connect(lambda v: self._show(lv[v]))
        self.slider.changed.connect(lambda v: (self._show(lv[v]), self.level_chosen.emit(lv[v])))
        self._show(level if level in lv else None)

    def _show(self, level: str | None) -> None:
        level = level if level is not None else ("medium" if "medium" in self.levels else self.levels[0])
        text, color = self.name(level), VIOLET_A if level == self.levels[-1] else BLUE_DEEP
        self.title.setText(text)
        self.title.setStyleSheet(f"color: {color.name()};")


class _Row(QPushButton):
    """One choice in the model list: title, optional subtitle, a check when chosen, a key number on the right."""

    def __init__(self, title: str, subtitle: str = "", chosen: bool = False, key: str = ""):
        super().__init__()
        self.title, self.subtitle, self.chosen, self.key = title, subtitle, chosen, key
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(48 if subtitle else 36)
        self.setStyleSheet("border: none; background: transparent;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(ROW_HOVER)
            p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        p.setFont(_font(14))
        p.setPen(INK)
        if self.subtitle:
            p.drawText(QRectF(12, 6, self.width() - 60, 20), Qt.AlignVCenter | Qt.AlignLeft, self.title)
            p.setFont(_font(12))
            p.setPen(GREY)
            p.drawText(QRectF(12, 25, self.width() - 60, 18), Qt.AlignVCenter | Qt.AlignLeft, self.subtitle)
        else:
            p.drawText(QRectF(12, 0, self.width() - 60, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.title)
        if self.chosen:
            draw_icon(p, "check", QRectF(self.width() - 30, (self.height() - 18) / 2, 18, 18), INK, 1.6)
        elif self.key:
            p.setFont(_font(12))
            p.setPen(GREY)
            p.drawText(QRectF(self.width() - 34, 0, 22, self.height()), Qt.AlignCenter, self.key)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class ListPopover(Popover):
    """A list of choices on a card: grey headings, rows with a check on the chosen one, keys 1-9 for the first nine."""
    chosen = Signal(object)

    def __init__(self, parent, width: int = 320):
        super().__init__(parent)
        self.setFixedWidth(width + 2 * SHADOW)
        self.body.setContentsMargins(SHADOW + 6, SHADOW + 8, SHADOW + 6, SHADOW + 8)
        self.body.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        self.rows = QVBoxLayout(inner)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(1)
        self.scroll.setWidget(inner)
        self.body.addWidget(self.scroll)
        self.keys: list[_Row] = []

    def heading(self, text: str) -> QLabel:
        h = QLabel(text)
        h.setFont(_font(13))
        h.setStyleSheet(f"color: {GREY.name()}; padding: 8px 12px 4px 12px;")
        self.rows.addWidget(h)
        return h

    def row(self, value, title: str, subtitle: str = "", chosen: bool = False) -> _Row:
        r = _Row(title, subtitle, chosen, str(len(self.keys) + 1) if len(self.keys) < 9 else "")
        if len(self.keys) < 9:
            self.keys.append(r)
        r.clicked.connect(lambda: (self.chosen.emit(value), self.close()))
        self.rows.addWidget(r)
        return r

    def note(self, text: str) -> QLabel:
        n = QLabel(text)
        n.setWordWrap(True)
        n.setFont(_font(12))
        n.setStyleSheet(f"color: {GREY.name()}; padding: 6px 12px;")
        self.rows.addWidget(n)
        return n

    def clear_from(self, index: int) -> None:
        while self.rows.count() > index:
            item = self.rows.takeAt(index)
            if item.widget():
                if item.widget() in self.keys:
                    self.keys.remove(item.widget())
                item.widget().deleteLater()

    def finish(self, max_height: int = 460) -> None:
        self.rows.addStretch(1)
        def tall(w) -> int:  # a row's fixed height (its sizeHint is a plain button's), else what it asks for
            return w.maximumHeight() if w.maximumHeight() < 1000 else w.sizeHint().height()
        h = sum(tall(self.rows.itemAt(i).widget()) + 1 for i in range(self.rows.count()) if self.rows.itemAt(i).widget())
        self.scroll.setFixedHeight(min(h + 4, max_height))

    def keyPressEvent(self, e):
        if Qt.Key_1 <= e.key() <= Qt.Key_9 and e.key() - Qt.Key_1 < len(self.keys):
            self.keys[e.key() - Qt.Key_1].click()
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.keys:
            self.keys[0].click()
            return
        super().keyPressEvent(e)


TOOL_TINT = QColor("#6d5dfc")


class MentionChip(QPushButton):
    """A tool called in with @ ("@ CodeCut"): a violet pill with a film icon; × removes it (clicking anywhere on it)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(_font(13))
        self.setFixedHeight(30)
        self.setFixedWidth(self.fontMetrics().horizontalAdvance("@ " + name) + 62)
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(109, 93, 252, 60), 1))
        p.setBrush(QColor(109, 93, 252, 34 if self.underMouse() else 20))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        film = QRectF(11, (self.height() - 14) / 2, 14, 14)
        pen = QPen(TOOL_TINT, 1.5)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(film, 3, 3)
        for fx in (film.left() + 3.5, film.right() - 3.5):
            p.drawLine(QPointF(fx, film.top() + 1), QPointF(fx, film.bottom() - 1))
        p.setPen(TOOL_TINT)
        p.drawText(QRectF(31, 0, self.width() - 56, self.height()), Qt.AlignVCenter | Qt.AlignLeft, "@ " + self.name)
        x = self.width() - 18
        c = QColor(TOOL_TINT)
        c.setAlpha(255 if self.underMouse() else 150)
        p.setPen(QPen(c, 1.5))
        p.drawLine(QPointF(x - 4, self.height() / 2 - 4), QPointF(x + 4, self.height() / 2 + 4))
        p.drawLine(QPointF(x - 4, self.height() / 2 + 4), QPointF(x + 4, self.height() / 2 - 4))


def model_list(parent, choices: list[tuple[str, str, str]], current: dict | None,
               more: list | None, ask_more: Callable[[Callable], None] | None) -> ListPopover:
    """选择模型: the engines' models, the project's, then 更多模型 asked live from the services (filled in when they answer).
    There is no 默认: what is shown is what runs (the user's rule, 2026-11-05)."""
    pop = ListPopover(parent)
    pop.heading(tr("choose_model"))
    from codedoctor import engines

    for name in engines.NAMES:  # the user's own Claude Code / Codex does the work, with its own models (engines.py)
        if not engines.get(name).executable():
            continue
        title = engines.TITLES[name]
        pop.heading(tr(f"{name}_head")).setToolTip(tr(f"{name}_sub"))
        listed = engines.models(name)
        if not listed:  # its list is unknown: it uses its own setting
            pick = {"engine": name, "model": title}
            pop.row(pick, title, tr(f"{name}_sub"), current == pick)
        for m in listed:
            pick = {"engine": name, "id": m["id"], "model": f"{title} · {m['name']}"}
            pop.row(pick, m["name"], "", (current or {}).get("id") == m["id"] and (current or {}).get("engine") == name)
    if choices:
        pop.heading(tr("project_models"))
        for title, endpoint, model in choices:
            pop.row({"endpoint": endpoint, "model": model}, model, title.split(" · ")[0],
                    current == {"endpoint": endpoint, "model": model})
    pop.heading(tr("more_models"))
    start = pop.rows.count()
    known = {(e, m) for _, e, m in choices}

    def fill(result) -> None:
        pop.clear_from(start)
        if not result:
            pop.note(tr("no_services"))
        for service, endpoint, models in result:
            if isinstance(models, str):
                pop.note(tr("query_failed", service=service, why=models[:80]))
                continue
            for m in [m for m in models if (endpoint, m) not in known][:40]:
                pop.row({"endpoint": endpoint, "model": m}, m, service, current == {"endpoint": endpoint, "model": m})
        pop.finish()
        pop.adjustSize()

    if more is not None:
        fill(more)
    else:
        pop.note(tr("asking_models"))
        pop.finish()
        if ask_more is not None:
            ask_more(fill)
    return pop


class Chip(QPushButton):
    """A rounded suggestion chip (white, a hairline border); Qt's style sheets leave the corners of a translucent
    button square, so it is painted. It shrinks with the row and the text is elided (the full text is the tooltip)."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(_font(13))
        self.setFixedHeight(34)
        self.setMinimumWidth(80)
        self.setMaximumWidth(self.fontMetrics().horizontalAdvance(text) + 34)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setToolTip(text)
        self.setStyleSheet("border: none; background: transparent;")

    def sizeHint(self):
        return QSize(self.maximumWidth(), 34)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(15, 23, 42, 18), 1))
        p.setBrush(QColor(255, 255, 255, 250 if self.underMouse() else 195))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(INK if self.underMouse() else QColor("#4b5260"))
        p.setFont(self.font())
        p.drawText(r.adjusted(14, 0, -14, 0), Qt.AlignCenter,
                   self.fontMetrics().elidedText(self.text(), Qt.ElideRight, int(r.width()) - 28))
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)



APPROVAL = {"ask": "hand", "auto": "shield", "full": "warn"}  # key: icon; the words come from i18n (appr_<key>)


def approval_text(key: str) -> tuple[str, str]:
    return tr(f"appr_{key}"), tr(f"appr_{key}_sub")


class _ApprovalRow(QPushButton):
    def __init__(self, key: str, chosen: bool):
        super().__init__()
        self.key, self.chosen = key, chosen
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(54)
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, _e):
        (title, sub_text), icon = approval_text(self.key), APPROVAL[self.key]
        danger = self.key == "full"
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(ROW_HOVER)
            p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        draw_icon(p, icon, QRectF(12, 9, 18, 18), ORANGE if danger else INK, 1.5)
        p.setFont(_font(14))
        p.setPen(ORANGE if danger else INK)
        p.drawText(QRectF(40, 6, self.width() - 80, 22), Qt.AlignVCenter | Qt.AlignLeft, title)
        p.setFont(_font(12))
        p.setPen(ORANGE if danger else GREY)
        p.drawText(QRectF(40, 27, self.width() - 80, 20), Qt.AlignVCenter | Qt.AlignLeft, sub_text)
        if self.chosen:
            draw_icon(p, "check", QRectF(self.width() - 30, 18, 18, 18), INK, 1.6)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class ApprovalPopover(Popover):
    """应如何批准 Lumen 的操作？ - 请求批准 / 帮我批准 / 完全访问权限, the chosen one checked."""
    chosen = Signal(str)
    learn_more = Signal()
    turn_on = Signal()

    def __init__(self, parent, current: str, computer_on: bool):
        super().__init__(parent)
        self.setFixedWidth(380 + 2 * SHADOW)
        self.body.setContentsMargins(SHADOW + 8, SHADOW + 10, SHADOW + 8, SHADOW + 8)
        self.body.setSpacing(2)
        head = QHBoxLayout()
        head.setContentsMargins(10, 0, 10, 4)
        q = QLabel(tr("appr_q"))
        q.setFont(_font(13))
        q.setStyleSheet(f"color: {GREY.name()};")
        more = QPushButton(tr("learn_more"))
        more.setCursor(Qt.PointingHandCursor)
        more.setFont(_font(13))
        more.setStyleSheet("QPushButton { border: none; background: transparent; color: #5b6170; text-decoration: underline; }"
                           " QPushButton:hover { color: #1f2329; }")
        more.clicked.connect(lambda: (self.close(), self.learn_more.emit()))
        head.addWidget(q, 1)
        head.addWidget(more)
        self.body.addLayout(head)
        if not computer_on:  # the real switch, not a picture of one; the choices below stay, so that the choice can be made before it is on
            n = QLabel(_t("appr_off_note", "电脑操作还没打开：Lumen 现在不能看屏幕，也不能动鼠标键盘。打开后由 Iris 在你允许的窗口里操作，在后台进行。",
                          "Computer use is off: Lumen cannot look at the screen or move the mouse and keyboard yet. Once it is on, Iris works in the windows you allow, in the background."))
            n.setWordWrap(True)
            n.setFont(_font(12))
            n.setStyleSheet(f"color: {GREY.name()}; padding: 0 10px 6px 10px;")
            self.body.addWidget(n)
            on = QPushButton(_t("appr_turn_on", "打开电脑操作", "Turn on computer use"))
            on.setObjectName("Primary")
            on.setCursor(Qt.PointingHandCursor)
            on.clicked.connect(lambda: (self.close(), self.turn_on.emit()))
            self.body.addWidget(on)
        for key in APPROVAL:
            row = _ApprovalRow(key, key == current)
            row.clicked.connect(lambda _=False, k=key: (self.chosen.emit(k), self.close()))
            self.body.addWidget(row)


class TeamButton(QPushButton):
    """The way of working under the text box (双首脑集群, 双人互检 ...): a team icon and its name, grey like 请求批准;
    a click opens its settings (协作方式: how many agents, which roles)."""

    def __init__(self, text: str):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(_font(14))
        self.setFixedHeight(32)
        self.setStyleSheet("border: none; background: transparent;")
        self.setToolTip(tr("team_tip"))
        self.set_name(text)

    def set_name(self, text: str) -> None:
        self.name = text
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(text) + 46)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse() or self.isDown():
            p.setPen(Qt.NoPen)
            p.setBrush(ROW_HOVER)
            p.drawRoundedRect(QRectF(self.rect()), self.height() / 2, self.height() / 2)
        color = INK if self.underMouse() else GREY
        draw_icon(p, "team", QRectF(11, 8, 17, 17), color, 1.5)
        p.setFont(self.font())
        p.setPen(color)
        p.drawText(QRectF(34, 0, self.width() - 36, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.name)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class ApprovalButton(QPushButton):
    """The approval choice under the text box: its icon and name, grey; a light grey pill on hover or while open."""

    def __init__(self):
        super().__init__()
        self.key = "auto"  # the same start as the composer's approval ("auto": 帮我审查)
        self.off = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(_font(14))
        self.setFixedHeight(32)
        self.setStyleSheet("border: none; background: transparent;")
        self.setToolTip(tr("appr_tip"))
        self.set_key("auto")

    def text(self) -> str:
        return _t("appr_off_label", "电脑操作：关", "Computer use: off") if self.off else approval_text(self.key)[0]

    def set_off(self, off: bool) -> None:
        self.off = off
        self.set_key(self.key)

    def set_key(self, key: str) -> None:
        self.key = key
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(self.text()) + 46)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse() or self.isDown():
            p.setPen(Qt.NoPen)
            p.setBrush(ROW_HOVER)
            p.drawRoundedRect(QRectF(self.rect()), self.height() / 2, self.height() / 2)
        danger = self.key == "full"
        color = ORANGE if danger else (INK if self.underMouse() else GREY)
        draw_icon(p, APPROVAL[self.key], QRectF(11, 8, 16, 16), color, 1.5)
        p.setFont(self.font())
        p.setPen(color)
        p.drawText(QRectF(33, 0, self.width() - 36, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)



class StopButton(QPushButton):
    """Shown next to send while the investigation runs: a white circle with a dark square; it stops everything."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("stop_tip"))
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(15, 23, 42, 40), 1))
        p.setBrush(ROW_HOVER if self.underMouse() and self.isEnabled() else QColor("white"))
        p.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        p.setPen(Qt.NoPen)
        p.setBrush(INK if self.isEnabled() else QColor("#b4b8bf"))  # grey: the stop was taken, the task is ending
        p.drawRoundedRect(QRectF(12, 12, 12, 12), 2.5, 2.5)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)
