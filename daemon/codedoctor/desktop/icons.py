"""The window's line icons (2026-11-03): one stroke weight, rounded ends, drawn as paths so they stay crisp at any
scale - the rail (home, chats, settings), the chat list (new chat, folders, search, pin) and the composer (mic, stop,
close, send). paint() draws into any painter; icon() makes a QIcon for buttons and menus."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTransform


def _gear(s: float) -> QPainterPath:
    """A cog outline: a ring with eight rounded teeth, as one path."""
    body = QPainterPath()
    body.addEllipse(QPointF(s / 2, s / 2), s * 0.31, s * 0.31)
    for i in range(8):
        tooth = QPainterPath()
        tooth.addRoundedRect(QRectF(-s * 0.075, -s * 0.44, s * 0.15, s * 0.2), s * 0.04, s * 0.04)
        body = body.united(QTransform().translate(s / 2, s / 2).rotate(i * 45).map(tooth))
    return body.simplified()


def paint(p: QPainter, kind: str, rect: QRectF, color: QColor | str, width: float = 1.6) -> None:
    color = QColor(color)
    s = min(rect.width(), rect.height())
    p.save()
    p.translate(rect.x() + (rect.width() - s) / 2, rect.y() + (rect.height() - s) / 2)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if kind == "home":  # a house: roof, walls, a door
        path = QPainterPath(QPointF(s * 0.14, s * 0.47))
        path.lineTo(s * 0.5, s * 0.16)
        path.lineTo(s * 0.86, s * 0.47)
        p.drawPath(path)
        walls = QPainterPath(QPointF(s * 0.24, s * 0.4))
        walls.lineTo(s * 0.24, s * 0.82)
        walls.lineTo(s * 0.76, s * 0.82)
        walls.lineTo(s * 0.76, s * 0.4)
        p.drawPath(walls)
        p.drawRoundedRect(QRectF(s * 0.42, s * 0.6, s * 0.16, s * 0.22), 1.5, 1.5)
    elif kind == "chat":  # a speech bubble
        path = QPainterPath()
        path.addRoundedRect(QRectF(s * 0.14, s * 0.18, s * 0.72, s * 0.52), s * 0.16, s * 0.16)
        tail = QPainterPath(QPointF(s * 0.3, s * 0.66))
        tail.lineTo(s * 0.26, s * 0.84)
        tail.lineTo(s * 0.46, s * 0.7)
        p.drawPath(path.united(tail).simplified())
        for x in (0.36, 0.5, 0.64):
            p.drawPoint(QPointF(s * x, s * 0.44))
    elif kind == "compose":  # new chat: a page with a pencil across its corner
        page = QPainterPath(QPointF(s * 0.5, s * 0.18))
        page.lineTo(s * 0.28, s * 0.18)
        page.quadTo(s * 0.16, s * 0.18, s * 0.16, s * 0.3)
        page.lineTo(s * 0.16, s * 0.72)
        page.quadTo(s * 0.16, s * 0.84, s * 0.28, s * 0.84)
        page.lineTo(s * 0.7, s * 0.84)
        page.quadTo(s * 0.82, s * 0.84, s * 0.82, s * 0.72)
        page.lineTo(s * 0.82, s * 0.52)
        p.drawPath(page)
        pencil = QPainterPath(QPointF(s * 0.42, s * 0.6))
        pencil.lineTo(s * 0.45, s * 0.48)
        pencil.lineTo(s * 0.76, s * 0.17)
        pencil.quadTo(s * 0.83, s * 0.12, s * 0.88, s * 0.18)
        pencil.quadTo(s * 0.92, s * 0.24, s * 0.86, s * 0.29)
        pencil.lineTo(s * 0.55, s * 0.6)
        pencil.closeSubpath()
        p.drawPath(pencil)
    elif kind == "gear":
        p.drawPath(_gear(s))
        p.drawEllipse(QPointF(s / 2, s / 2), s * 0.12, s * 0.12)
    elif kind in ("folder", "folder_open"):
        path = QPainterPath(QPointF(s * 0.12, s * 0.74))
        path.lineTo(s * 0.12, s * 0.28)
        path.quadTo(s * 0.12, s * 0.2, s * 0.2, s * 0.2)
        path.lineTo(s * 0.38, s * 0.2)
        path.lineTo(s * 0.46, s * 0.3)
        path.lineTo(s * 0.8, s * 0.3)
        path.quadTo(s * 0.88, s * 0.3, s * 0.88, s * 0.38)
        if kind == "folder":
            path.lineTo(s * 0.88, s * 0.74)
            path.quadTo(s * 0.88, s * 0.82, s * 0.8, s * 0.82)
            path.lineTo(s * 0.2, s * 0.82)
            path.quadTo(s * 0.12, s * 0.82, s * 0.12, s * 0.74)
            p.drawPath(path)
            p.drawLine(QPointF(s * 0.12, s * 0.42), QPointF(s * 0.88, s * 0.42))
        else:  # the front flap tilts open
            path.lineTo(s * 0.88, s * 0.44)
            p.drawPath(path)
            flap = QPainterPath(QPointF(s * 0.12, s * 0.8))
            flap.lineTo(s * 0.26, s * 0.46)
            flap.lineTo(s * 0.94, s * 0.46)
            flap.lineTo(s * 0.8, s * 0.82)
            flap.lineTo(s * 0.16, s * 0.82)
            p.drawPath(flap)
    elif kind == "globe":  # 浏览器
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.37, s * 0.37)
        p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.16, s * 0.37)
        p.drawLine(QPointF(s * 0.13, s * 0.5), QPointF(s * 0.87, s * 0.5))
    elif kind in ("arrow_left", "arrow_right"):
        tip, tail = (s * 0.2, s * 0.8) if kind == "arrow_left" else (s * 0.8, s * 0.2)
        head = s * 0.46 if kind == "arrow_left" else s * 0.54
        p.drawLine(QPointF(tail, s * 0.5), QPointF(tip, s * 0.5))
        p.drawLine(QPointF(tip, s * 0.5), QPointF(head, s * 0.24))
        p.drawLine(QPointF(tip, s * 0.5), QPointF(head, s * 0.76))
    elif kind == "reload":  # an open ring with a head
        p.drawArc(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64), 40 * 16, 280 * 16)
        p.drawLine(QPointF(s * 0.82, s * 0.16), QPointF(s * 0.8, s * 0.34))
        p.drawLine(QPointF(s * 0.8, s * 0.34), QPointF(s * 0.62, s * 0.32))
    elif kind == "terminal":  # a window with a prompt
        p.drawRoundedRect(QRectF(s * 0.12, s * 0.2, s * 0.76, s * 0.6), s * 0.12, s * 0.12)
        p.drawPolyline([QPointF(s * 0.28, s * 0.38), QPointF(s * 0.42, s * 0.5), QPointF(s * 0.28, s * 0.62)])
        p.drawLine(QPointF(s * 0.5, s * 0.62), QPointF(s * 0.68, s * 0.62))
    elif kind == "laptop":  # 此计算机
        p.drawRoundedRect(QRectF(s * 0.2, s * 0.24, s * 0.6, s * 0.4), s * 0.05, s * 0.05)
        p.drawLine(QPointF(s * 0.1, s * 0.74), QPointF(s * 0.9, s * 0.74))
        p.drawLine(QPointF(s * 0.2, s * 0.64), QPointF(s * 0.12, s * 0.74))
        p.drawLine(QPointF(s * 0.8, s * 0.64), QPointF(s * 0.88, s * 0.74))
    elif kind == "folder_plus":  # 添加 (a folder)
        path = QPainterPath(QPointF(s * 0.56, s * 0.82))
        path.lineTo(s * 0.2, s * 0.82)
        path.quadTo(s * 0.12, s * 0.82, s * 0.12, s * 0.74)
        path.lineTo(s * 0.12, s * 0.28)
        path.quadTo(s * 0.12, s * 0.2, s * 0.2, s * 0.2)
        path.lineTo(s * 0.38, s * 0.2)
        path.lineTo(s * 0.46, s * 0.3)
        path.lineTo(s * 0.8, s * 0.3)
        path.quadTo(s * 0.88, s * 0.3, s * 0.88, s * 0.38)
        path.lineTo(s * 0.88, s * 0.5)
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.76, s * 0.6), QPointF(s * 0.76, s * 0.9))
        p.drawLine(QPointF(s * 0.61, s * 0.75), QPointF(s * 0.91, s * 0.75))
    elif kind == "search":
        p.drawEllipse(QPointF(s * 0.44, s * 0.44), s * 0.26, s * 0.26)
        p.drawLine(QPointF(s * 0.64, s * 0.64), QPointF(s * 0.84, s * 0.84))
    elif kind == "plus":
        p.drawLine(QPointF(s / 2, s * 0.2), QPointF(s / 2, s * 0.8))
        p.drawLine(QPointF(s * 0.2, s / 2), QPointF(s * 0.8, s / 2))
    elif kind == "close":
        p.drawLine(QPointF(s * 0.28, s * 0.28), QPointF(s * 0.72, s * 0.72))
        p.drawLine(QPointF(s * 0.72, s * 0.28), QPointF(s * 0.28, s * 0.72))
    elif kind == "mic":
        p.drawRoundedRect(QRectF(s * 0.37, s * 0.12, s * 0.26, s * 0.44), s * 0.13, s * 0.13)
        arc = QPainterPath(QPointF(s * 0.24, s * 0.44))
        arc.cubicTo(s * 0.24, s * 0.82, s * 0.76, s * 0.82, s * 0.76, s * 0.44)
        p.drawPath(arc)
        p.drawLine(QPointF(s / 2, s * 0.72), QPointF(s / 2, s * 0.88))
    elif kind == "stop":
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(s * 0.3, s * 0.3, s * 0.4, s * 0.4), s * 0.07, s * 0.07)
    elif kind == "send":  # an arrow up
        p.drawLine(QPointF(s / 2, s * 0.8), QPointF(s / 2, s * 0.22))
        p.drawLine(QPointF(s * 0.28, s * 0.44), QPointF(s / 2, s * 0.22))
        p.drawLine(QPointF(s * 0.72, s * 0.44), QPointF(s / 2, s * 0.22))
    elif kind == "pin":
        head = QPainterPath(QPointF(s * 0.36, s * 0.14))
        head.lineTo(s * 0.64, s * 0.14)
        head.lineTo(s * 0.6, s * 0.4)
        head.lineTo(s * 0.74, s * 0.56)
        head.lineTo(s * 0.26, s * 0.56)
        head.lineTo(s * 0.4, s * 0.4)
        head.closeSubpath()
        p.drawPath(head)
        p.drawLine(QPointF(s / 2, s * 0.56), QPointF(s / 2, s * 0.88))
    elif kind == "chevron_down":
        p.drawLine(QPointF(s * 0.3, s * 0.42), QPointF(s / 2, s * 0.6))
        p.drawLine(QPointF(s * 0.5, s * 0.6), QPointF(s * 0.7, s * 0.42))
    elif kind == "chevron_right":
        p.drawLine(QPointF(s * 0.42, s * 0.3), QPointF(s * 0.6, s / 2))
        p.drawLine(QPointF(s * 0.6, s / 2), QPointF(s * 0.42, s * 0.7))
    elif kind == "sidebar":  # show / hide the chat list
        p.drawRoundedRect(QRectF(s * 0.14, s * 0.2, s * 0.72, s * 0.6), s * 0.12, s * 0.12)
        p.drawLine(QPointF(s * 0.4, s * 0.2), QPointF(s * 0.4, s * 0.8))
    elif kind == "more":
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        for x in (0.28, 0.5, 0.72):
            p.drawEllipse(QPointF(s * x, s / 2), s * 0.055, s * 0.055)
    elif kind == "book":
        p.drawRoundedRect(QRectF(s * 0.2, s * 0.14, s * 0.6, s * 0.72), s * 0.08, s * 0.08)
        p.drawLine(QPointF(s * 0.34, s * 0.14), QPointF(s * 0.34, s * 0.86))
    elif kind == "key":
        p.drawEllipse(QPointF(s * 0.3, s / 2), s * 0.16, s * 0.16)
        p.drawLine(QPointF(s * 0.46, s / 2), QPointF(s * 0.86, s / 2))
        p.drawLine(QPointF(s * 0.72, s / 2), QPointF(s * 0.72, s * 0.66))
        p.drawLine(QPointF(s * 0.84, s / 2), QPointF(s * 0.84, s * 0.62))
    elif kind == "agents":
        p.drawEllipse(QPointF(s / 2, s * 0.34), s * 0.15, s * 0.15)
        arc = QPainterPath(QPointF(s * 0.2, s * 0.84))
        arc.cubicTo(s * 0.2, s * 0.56, s * 0.8, s * 0.56, s * 0.8, s * 0.84)
        p.drawPath(arc)
    elif kind == "memory":  # a brain-like double loop
        p.drawEllipse(QPointF(s * 0.38, s * 0.42), s * 0.2, s * 0.22)
        p.drawEllipse(QPointF(s * 0.62, s * 0.42), s * 0.2, s * 0.22)
        p.drawLine(QPointF(s / 2, s * 0.62), QPointF(s / 2, s * 0.84))
    elif kind == "palette":
        path = QPainterPath()
        path.addEllipse(QPointF(s / 2, s / 2), s * 0.36, s * 0.34)
        p.drawPath(path)
        p.setBrush(color)
        for x, y in ((0.36, 0.38), (0.56, 0.32), (0.66, 0.5)):
            p.drawEllipse(QPointF(s * x, s * y), s * 0.045, s * 0.045)
    elif kind == "grid":  # 插件: four tiles
        for x, y in ((.14, .14), (.56, .14), (.14, .56), (.56, .56)):
            p.drawRoundedRect(QRectF(x * s, y * s, s * .3, s * .3), s * .07, s * .07)
    elif kind == "chart":  # 用量: three bars on a line
        p.drawLine(QPointF(s * 0.16, s * 0.82), QPointF(s * 0.84, s * 0.82))
        for x, y in ((0.3, 0.56), (0.5, 0.3), (0.7, 0.44)):
            p.drawLine(QPointF(s * x, s * 0.72), QPointF(s * x, s * y))
    elif kind in ("star", "star_on"):
        path = QPainterPath()
        for i in range(10):
            r = s * (0.38 if i % 2 == 0 else 0.16)
            a = math.pi * (i / 5 - .5)
            spot = QPointF(s / 2 + math.cos(a) * r, s * 0.53 + math.sin(a) * r)
            path.moveTo(spot) if i == 0 else path.lineTo(spot)
        path.closeSubpath()
        if kind == "star_on":
            p.setBrush(color)
        p.drawPath(path)
    elif kind == "bookmarks":  # a ribbon
        path = QPainterPath()
        path.moveTo(s * 0.28, s * 0.18)
        path.lineTo(s * 0.72, s * 0.18)
        path.lineTo(s * 0.72, s * 0.84)
        path.lineTo(s * 0.5, s * 0.66)
        path.lineTo(s * 0.28, s * 0.84)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "logout":
        p.drawLine(QPointF(s * 0.42, s * 0.2), QPointF(s * 0.2, s * 0.2))
        p.drawLine(QPointF(s * 0.2, s * 0.2), QPointF(s * 0.2, s * 0.8))
        p.drawLine(QPointF(s * 0.2, s * 0.8), QPointF(s * 0.42, s * 0.8))
        p.drawLine(QPointF(s * 0.44, s / 2), QPointF(s * 0.84, s / 2))
        p.drawLine(QPointF(s * 0.7, s * 0.36), QPointF(s * 0.84, s / 2))
        p.drawLine(QPointF(s * 0.7, s * 0.64), QPointF(s * 0.84, s / 2))
    p.restore()


def icon(kind: str, color: str = "#3b4250", size: int = 18, width: float = 1.6) -> QIcon:
    pm = QPixmap(size * 3, size * 3)
    pm.setDevicePixelRatio(3)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    paint(p, kind, QRectF(0, 0, size, size), color, width)
    p.end()
    return QIcon(pm)
