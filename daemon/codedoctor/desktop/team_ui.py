"""The Lumen team in the window: each member is a little 3D figure of its element (assets/team, made in Blender by
make_team.py), its name card, and the group-chat messages of a conversation where Lumen hands out work."""

from __future__ import annotations

import math
from pathlib import Path
import time

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from codedoctor.agents import orchestration as orch
from codedoctor.agents import team
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import Chip, Collapsible, Markdown, PulseDot, hbox, label, vbox


TEAM_ART = Path(__file__).resolve().parent / "assets" / "team"
_art: dict[str, QImage] = {}


def art(member_id: str) -> QImage | None:
    """The member's figure, trimmed to what is drawn, square."""
    if member_id not in _art:
        image = QImage(str(TEAM_ART / f"{member_id}.png"))
        if image.isNull():
            return None
        image = image.convertToFormat(QImage.Format_ARGB32)
        left, top, right, bottom = image.width(), image.height(), 0, 0
        for y in range(0, image.height(), 2):
            for x in range(0, image.width(), 2):
                if image.pixelColor(x, y).alpha() > 12:
                    left, top, right, bottom = min(left, x), min(top, y), max(right, x), max(bottom, y)
        side = max(right - left, bottom - top) + 8
        cx, cy = (left + right) // 2, (top + bottom) // 2
        _art[member_id] = image.copy(QRect(cx - side // 2, cy - side // 2, side, side))
    return _art[member_id]


class Figure(QWidget):
    """A member standing in the window, in a soft glow of its colour, floating a little."""

    def __init__(self, member_id: str, size: int = 120, moving: bool = True):
        super().__init__()
        self.m = team.member(member_id) or team.BY_ID["lumen"]
        self.px = size
        self.setFixedSize(size, size + 10)
        self.setToolTip(f"{self.m.name} · {self.m.cn}")
        self.image = art(self.m.id)
        self.y = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.moving = moving

    def _tick(self) -> None:
        self.y = math.sin(time.monotonic() * 1.6) * 3.5
        self.update()

    def showEvent(self, e):
        from codedoctor.desktop import motion

        from codedoctor.desktop import prefs

        if self.moving and not motion.reduced() and prefs.load()["figure_motion"]:
            self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self.px
        glow = QRadialGradient(QPointF(s / 2, s / 2 + 5), s * .5)
        colour = QColor(self.m.colour)
        colour.setAlpha(46)
        glow.setColorAt(0, colour)
        colour.setAlpha(0)
        glow.setColorAt(1, colour)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(0, 5, s, s))
        shadow = QRadialGradient(QPointF(s / 2, s + 2), s * .22)
        shadow.setColorAt(0, QColor(60, 40, 10, 44))
        shadow.setColorAt(1, QColor(60, 40, 10, 0))
        p.setBrush(shadow)
        p.drawEllipse(QRectF(s * .28, s - 5, s * .44, 14))
        if self.image is not None:
            inset = s * .08
            p.drawImage(QRectF(inset, inset + self.y, s - 2 * inset, s - 2 * inset), self.image)
        p.end()


class MemberAvatar(QWidget):
    """A round tile in the member's colour with its figure on it."""

    def __init__(self, member_id: str, size: int = 32):
        super().__init__()
        self.m = team.member(member_id) or team.BY_ID["lumen"]
        self.px = size
        self.setFixedSize(size, size)
        self.setToolTip(f"{self.m.name} · {self.m.cn}")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.px
        base = QColor(self.m.colour)
        image = art(self.m.id)
        if image is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            soft = QColor(base)
            soft.setAlpha(36)
            p.setPen(Qt.NoPen)
            p.setBrush(soft)
            p.drawEllipse(QRectF(0, 0, s, s))
            inset = s * .07
            p.drawImage(QRectF(inset, inset, s - 2 * inset, s - 2 * inset), image)
            p.end()
            return
        g = QLinearGradient(0, 0, s, s)
        g.setColorAt(0, base.lighter(118))
        g.setColorAt(1, base.darker(108))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QRectF(0, 0, s, s))
        p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(0.5, 0.5, s - 1, s - 1))
        p.translate(s / 2, s / 2)
        p.scale(s / 32, s / 32)  # the drawings are made for a 32 px circle around (0, 0)
        white = QColor("white")
        pen = QPen(white, 1.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        DRAW.get(self.m.id, _sun)(p, pen, white)
        p.end()


def _sun(p, pen, white):
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawEllipse(QPointF(0, 0), 4.6, 4.6)
    p.setPen(pen)
    for i in range(8):
        a = i * math.pi / 4
        p.drawLine(QPointF(7.6 * math.cos(a), 7.6 * math.sin(a)), QPointF(10.4 * math.cos(a), 10.4 * math.sin(a)))


def _spark(p, pen, white):
    path = QPainterPath()
    path.moveTo(0, -10)
    for x, y in ((2.4, -2.4), (10, 0), (2.4, 2.4), (0, 10), (-2.4, 2.4), (-10, 0), (-2.4, -2.4)):
        path.lineTo(x, y)
    path.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawPath(path)
    p.drawEllipse(QPointF(7.5, -7.5), 1.6, 1.6)


def _prism(p, pen, white):
    tri = QPainterPath()
    tri.moveTo(0, -8.5)
    tri.lineTo(8, 6.5)
    tri.lineTo(-8, 6.5)
    tri.closeSubpath()
    p.setPen(pen)
    p.setBrush(QColor(255, 255, 255, 60))
    p.drawPath(tri)
    p.drawLine(QPointF(-11, 1.5), QPointF(-3.5, -0.5))
    thin = QPen(pen)
    thin.setWidthF(1.4)
    p.setPen(thin)
    for dy in (-2.5, 0.5, 3.5):
        p.drawLine(QPointF(3.5, -0.5), QPointF(11, dy))


def _torch(p, pen, white):
    flame = QPainterPath()
    flame.moveTo(0, -10)
    flame.cubicTo(5.5, -4, 6, 1, 0, 3.5)
    flame.cubicTo(-6, 1, -5.5, -4, 0, -10)
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawPath(flame)
    handle = QPainterPath()
    handle.moveTo(-3.5, 5)
    handle.lineTo(3.5, 5)
    handle.lineTo(1.6, 11)
    handle.lineTo(-1.6, 11)
    handle.closeSubpath()
    p.setBrush(QColor(255, 255, 255, 200))
    p.drawPath(handle)


def _ray(p, pen, white):
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawEllipse(QPointF(-7.5, 0), 3.2, 3.2)
    p.setPen(pen)
    for dy in (-6.5, 0, 6.5):
        p.drawLine(QPointF(-3, dy * 0.25), QPointF(10, dy))


def _lantern(p, pen, white):
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-3.5, -11, 7, 6), 0, 180 * 16)
    p.setBrush(QColor(255, 255, 255, 70))
    p.drawRoundedRect(QRectF(-6, -6, 12, 14), 3.5, 3.5)
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawEllipse(QPointF(0, 1), 2.6, 3.2)
    p.drawRect(QRectF(-4, 8, 8, 2))


def _beacon(p, pen, white):
    tower = QPainterPath()
    tower.moveTo(-3, -3)
    tower.lineTo(3, -3)
    tower.lineTo(5.5, 10)
    tower.lineTo(-5.5, 10)
    tower.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawPath(tower)
    p.drawRoundedRect(QRectF(-3.4, -9.5, 6.8, 5), 1.5, 1.5)
    p.setPen(pen)
    p.drawLine(QPointF(-6, -7), QPointF(-11, -9.5))
    p.drawLine(QPointF(6, -7), QPointF(11, -9.5))
    p.setPen(QPen(QColor(0, 0, 0, 60), 1.6))  # the tower's stripe
    p.drawLine(QPointF(-4.3, 3.5), QPointF(4.3, 3.5))


def _iris(p, pen, white):
    eye = QPainterPath()
    eye.moveTo(-11, 0)
    eye.quadTo(0, -10, 11, 0)
    eye.quadTo(0, 10, -11, 0)
    p.setPen(pen)
    p.setBrush(QColor(255, 255, 255, 60))
    p.drawPath(eye)
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawEllipse(QPointF(0, 0), 4.2, 4.2)


DRAW = {"lumen": _sun, "spark": _spark, "prism": _prism, "torch": _torch, "ray": _ray, "lantern": _lantern,
        "beacon": _beacon, "iris": _iris}


def name_line(member_id: str, size: int = 14) -> QWidget:
    """Spark 火花 · 写代码"""
    m = team.member(member_id)
    helper = "-h" in member_id
    from codedoctor.desktop import i18n

    chinese = i18n.language() in ("zh", "zh-TW")  # the Chinese name beside the English one only in a Chinese interface
    return hbox(label(m.name, size=size, bold=True, color=C["ink"]),
                label(m.cn if chinese else "", size=size - 1, color=m.colour),
                label(("一次性助手" if helper else m.job), size=12, color=C["text3"]), None, spacing=6)


class MemberMessage(QFrame):
    """One member's job in the group chat: Lumen's request to it, then its reply (or that it is working), its
    one-off helpers, its steps on demand, and Beacon's review of it."""

    def __init__(self, daemon, row: dict):
        super().__init__()
        from codedoctor.desktop.task_view import StepList

        self.d, self.task_id, self.agent = daemon, row["id"], row["agent"]
        body = orch.body_of(row)
        self.review = bool(body.get("review_of"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 6)
        lay.setSpacing(10)
        if not self.review:  # Lumen's request, as a message in the group
            ask = QFrame()
            ask.setObjectName("TeamAsk")
            ask.setStyleSheet(f"#TeamAsk {{ background: {C['sidebar']}; border: 1px solid {C['border']}; border-radius: 18px; }}")
            al = QVBoxLayout(ask)
            al.setContentsMargins(12, 8, 12, 9)
            al.setSpacing(3)
            sender = row.get("requester") or "lumen"
            who = team.member(sender)
            al.addWidget(hbox(MemberAvatar(sender if who else "lumen", 22),
                              label(f"{who.name if who else 'Lumen'} → {team.member(self.agent).name}", size=12, bold=True,
                                    color=C["text2"]), None, spacing=6))
            text = label(str(body.get("instructions", row["title"]))[:1200], wrap=True, selectable=True, size=13,
                         color=C["text2"])
            widest = max((text.fontMetrics().horizontalAdvance(ln) for ln in text.text().splitlines() or [""]), default=0)
            text.setMinimumWidth(min(widest + 6, 560))  # a request reads as one bubble, not a narrow column
            al.addWidget(text)
            ask.setMaximumWidth(620)
            lay.addWidget(hbox(ask, None))
        head = hbox(MemberAvatar(self.agent, 38), name_line(self.agent), spacing=10)
        if self.review:  # Beacon re-checks on its own, nobody asked it: say whose work
            worker = (orch.task_row(daemon.s, body["review_of"]) or {}).get("agent", "")
            m = team.member(worker)
            head.layout().itemAt(1).widget().layout().itemAt(2).widget().setText(
                f"自动复查 {m.name if m else worker} 的工作")
        self.dot, self.chip = PulseDot(), Chip()
        head.layout().addWidget(self.dot)
        head.layout().addWidget(self.chip)
        lay.addWidget(head)
        self.reply = vbox(spacing=4, margins=(48, 0, 0, 0))
        lay.addWidget(self.reply)
        self.helpers = label("", size=12, color=C["text3"])
        self.helpers.setContentsMargins(48, 0, 0, 0)
        self.helpers.setVisible(False)
        lay.addWidget(self.helpers)
        self.steps = StepList(daemon, row["id"])
        self.coll = Collapsible(label("查看它的每一步", size=12, color=C["text3"]), self.steps, expanded=False)
        self.coll.setContentsMargins(48, 0, 0, 0)
        lay.addWidget(self.coll)
        self.has_reply = False
        self.update_row(row)

    def update_row(self, row: dict) -> None:
        from codedoctor.desktop.task_view import task_status

        running = row["state"] != "finished"
        self.dot.set_state(C["blue"], running)
        self.dot.setVisible(running)
        self.chip.set("复查中" if running and self.review else "工作中" if running else task_status(row))
        if not running and not self.has_reply:
            rep = orch.report_of(self.d.s, self.task_id)
            if rep:
                self.reply.layout().addWidget(Markdown(rep.get("summary", ""), size=14))
                self.has_reply = True
        kids = [c for c in orch.children(self.d.s, self.task_id) if "-h" in c["agent"]]
        if kids:
            busy = sum(c["state"] != "finished" for c in kids)
            from codedoctor.desktop import locale

            self.helpers.setText(locale.t(f"派了 {len(kids)} 个一次性助手")  # pieces: each one is in the catalog
                                 + locale.t(f"，{busy} 个还在干活" if busy else "，都已交差"))
            self.helpers.setVisible(True)
        if self.coll.expanded:
            self.steps.refresh()


def is_team_task(daemon, row: dict) -> bool:
    a = daemon.s.config.agents.get(row["agent"]) or daemon.s.config.agents.get(row["agent"].split("-h", 1)[0])
    return bool(a is not None and a.team)
