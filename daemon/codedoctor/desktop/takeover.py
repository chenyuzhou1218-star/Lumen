"""Lumen is using the computer (2026-11-03), shown the way ChatGPT's agent shows it: a blue glowing frame around the
window it works in, a blue cursor that glides to where it acts, and a banner at the top - what it is doing, which
step, how long the last step took, and 停止. The user sees every move; the AI never sees these (they are excluded from
screen capture), and none of them takes the keyboard away from the window being used.

Stop: the banner's 停止, Ctrl+Alt+End anywhere, or the mouse pushed into the top-left corner (computer/gate.py).
"""

from __future__ import annotations

import ctypes
import math
import time

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from codedoctor.desktop import locale
from codedoctor.desktop.theme import APP_NAME, FONT_FAMILY

BLUE = QColor("#2f6bff")


def _font(px: float, bold: bool = False) -> QFont:
    f = QFont(FONT_FAMILY)
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f


def _overlay(widget: QWidget, click_through: bool) -> None:
    flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus
    if click_through:
        flags |= Qt.WindowTransparentForInput
    widget.setWindowFlags(flags)
    widget.setAttribute(Qt.WA_TranslucentBackground)
    widget.setAttribute(Qt.WA_ShowWithoutActivating)


def _hide_from_capture(widget: QWidget) -> None:
    """WDA_EXCLUDEFROMCAPTURE (Windows 10 2004+): screenshots - the AI's included - do not contain this window."""
    try:
        ctypes.windll.user32.SetWindowDisplayAffinity(int(widget.winId()), 0x11)
    except (AttributeError, OSError):
        pass


def _logical(rect: tuple[int, int, int, int], widget: QWidget) -> QRect:
    """Physical screen pixels (the gate's) to Qt's logical coordinates."""
    dpr = widget.devicePixelRatioF() or 1.0
    left, top, right, bottom = rect
    return QRect(int(left / dpr), int(top / dpr), int((right - left) / dpr), int((bottom - top) / dpr))


class Frame(QWidget):
    """A soft blue glow around the window being used; click-through."""

    def __init__(self):
        super().__init__()
        _overlay(self, click_through=True)
        self.phase = 0.0

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        breathe = 0.75 + 0.25 * math.sin(self.phase)
        for width, alpha in ((12, 22), (8, 40), (4, 90), (2, 220)):
            c = QColor(BLUE)
            c.setAlpha(int(alpha * breathe))
            p.setPen(QPen(c, width))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, 10, 10)
        p.end()


class Cursor(QWidget):
    """The AI's cursor: a blue arrow with a white edge and a soft glow; glides from point to point."""

    TIP = QPoint(2, 2)  # where the arrow's tip is drawn in this widget

    def __init__(self):
        super().__init__()
        _overlay(self, click_through=True)
        self.setFixedSize(18, 24)  # Windows' own arrow: about 12 x 19 at 100 %
        self.anim = QPropertyAnimation(self, b"pos", self)
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def glide(self, tip: QPoint) -> None:
        target = tip - self.TIP
        if not self.isVisible():
            self.move(target)
            return
        self.anim.stop()
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(target)
        self.anim.start()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x0, y0 = self.TIP.x() + 0.5, self.TIP.y() + 0.5
        arrow = QPainterPath(QPointF(x0, y0))  # the outline of Windows' standard arrow
        for x, y in ((0, 16.2), (3.9, 12.5), (6.6, 18.6), (9.1, 17.5), (6.5, 11.6), (11.6, 11.6)):
            arrow.lineTo(x0 + x, y0 + y)
        arrow.closeSubpath()
        shadow = QPainterPath(arrow)
        shadow.translate(0.8, 1.0)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawPath(shadow)
        p.setPen(QPen(QColor("white"), 1.2, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
        p.setBrush(BLUE)
        p.drawPath(arrow)
        p.end()


class StopButton(QWidget):
    """停止 - a small pill at the bottom right of the screen, away from where the AI clicks; clicking it never takes
    the keyboard from the game."""
    stop = Signal()

    def __init__(self):
        super().__init__()
        _overlay(self, click_through=False)
        self.setFixedSize(200, 52)
        self.button = QPushButton("■  停止 Lumen", self)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setFocusPolicy(Qt.NoFocus)
        self.button.setStyleSheet("QPushButton { background: #ffffff; color: #d93025; border: 1px solid #f2c4bf;"
                                  " border-radius: 18px; font-size: 14px; font-weight: 600; padding: 7px 18px; }"
                                  " QPushButton:hover { background: #fff1f0; }")
        self.button.clicked.connect(self.stop.emit)
        self.button.adjustSize()
        self.button.move(self.width() - self.button.width() - 6, (self.height() - self.button.height()) // 2)


class Banner(QWidget):
    """Lumen 正在使用你的电脑 · what it does now · step and timing. Clicks pass through it: it sits over the game,
    where the AI (or you) may click (a real test: a click there stopped the run)."""

    def __init__(self):
        super().__init__()
        _overlay(self, click_through=True)
        self.setFixedSize(520, 64)
        self.title = f"{APP_NAME} 正在使用你的电脑"
        self.line = ""
        self.phase = 0.0

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(6, 4, -6, -8)
        for i in range(6, 0, -1):  # a soft shadow
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 5))
            p.drawRoundedRect(r.adjusted(-i, -i + 3, i, i + 3), r.height() / 2 + i, r.height() / 2 + i)
        p.setPen(QPen(QColor("#e5e5e5"), 1))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        cx, cy = r.left() + 30, r.center().y()
        pulse = 0.5 + 0.5 * math.sin(self.phase * 2)
        ring = QColor(BLUE)
        ring.setAlpha(int(24 + 40 * pulse))
        p.setPen(Qt.NoPen)
        p.setBrush(ring)
        p.drawEllipse(QPointF(cx, cy), 19 + 3 * pulse, 19 + 3 * pulse)
        from codedoctor.desktop.team_ui import art

        figure = art("iris")  # the one at the controls
        if figure is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(QRectF(cx - 21, cy - 21 + 1.5 * math.sin(self.phase), 42, 42), figure)
        text_w = self.width() - 96
        p.setPen(QColor("#0d0d0d"))
        p.setFont(_font(14, bold=True))
        p.drawText(QRectF(cx + 28, r.top() + 7, text_w, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   locale.t(self.title) + "    " + locale.t("（Ctrl+Alt+End 停止）"))
        p.setPen(QColor("#5d5d5d"))
        p.setFont(_font(12.5))
        line = p.fontMetrics().elidedText(self.line, Qt.ElideRight, int(text_w))
        p.drawText(QRectF(cx + 28, r.top() + 27, text_w, 18), Qt.AlignLeft | Qt.AlignVCenter, line)
        p.end()


KIND_CN = {"move": "移动鼠标", "click": "点击", "type": "输入文字", "keys": "按键", "look": "转动视角", "hold": "按住按键",
           "mouse_hold": "按住鼠标", "launch": "启动程序", "close": "关闭程序", "terminal": "运行命令"}


def say(rec: dict) -> str:
    """An action in a few words, as the banner shows it."""
    a, k = rec.get("args") or {}, rec.get("kind")
    if k == "hold":
        return f"按住 {'+'.join(x.upper() for x in a.get('keys', []))} {a.get('seconds', '')} 秒"
    if k == "mouse_hold":
        return f"按住{'左' if a.get('button', 'left') == 'left' else '右'}键 {a.get('seconds', '')} 秒"
    if k == "keys":
        return "按 " + "+".join(x.upper() for x in a.get("keys", []))
    if k == "look":
        dx, dy = a.get("dx", 0), a.get("dy", 0)
        where = ("向右" if dx > 0 else "向左" if dx < 0 else "") + ("向下" if dy > 0 else "向上" if dy < 0 else "")
        return locale.t("转动视角") + "".join(locale.t(w) for w in (where[:2], where[2:]) if w)
    if k == "type":
        return f"输入 “{str(a.get('text', ''))[:20]}”"
    if k == "aim":
        return "对准目标"
    return KIND_CN.get(k, k or "")


class Takeover:
    """Shows the frame, the cursor and the banner while a task of this window uses the computer; follows the gate's
    action records (every 120 ms) and hides itself when nothing has happened for a while or the task ends."""

    def __init__(self, daemon, on_stop):
        self.d, self.on_stop = daemon, on_stop
        self.frame, self.cursor, self.banner, self.stop_button = Frame(), Cursor(), Banner(), StopButton()
        self.stop_button.stop.connect(self._stop)
        self.timer = QTimer()
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.shown = False
        self.task: str | None = None
        self.last_id: str | None = None
        self.last_at = 0.0
        self.step_s: float | None = None
        self.steps = 0

    def _stop(self) -> None:
        gate = self.d.s.computer
        if gate is not None:
            gate.stop("你在提示条上点了停止")
        self.on_stop(self.task)
        self.hide()

    def hide(self) -> None:
        for w in (self.frame, self.cursor, self.banner, self.stop_button):
            w.hide()
        self.shown = False

    def _show(self) -> None:
        screen = self.stop_button.screen().availableGeometry()
        self.stop_button.move(screen.right() - self.stop_button.width() - 16, screen.bottom() - self.stop_button.height() - 16)
        for w in (self.frame, self.cursor, self.banner, self.stop_button):
            if not w.isVisible():
                w.show()
                _hide_from_capture(w)
        self.shown = True

    def tick(self) -> None:
        gate = self.d.s.computer
        if gate is None or not gate.available or gate.policy.background:
            return  # in the background nothing covers what the user is doing; the steps show in the chat
        acts = gate.actions(limit=1)
        if not acts:
            return
        rec = acts[0]
        row = self.d.task(rec["task_id"]) if rec["task_id"] != self.task or not self.shown else None
        if rec["task_id"] != self.task:
            self.task, self.steps, self.step_s = rec["task_id"], 0, None
        running = (row or self.d.task(self.task) or {}).get("state") != "finished"
        if not running or gate.stopped():
            if self.shown:
                self.hide()
            return
        now = time.monotonic()
        if rec["id"] != self.last_id:  # a new action: the step before it took this long (look, think, act)
            if self.last_id is not None:
                self.step_s = now - self.last_at
            self.last_id, self.last_at = rec["id"], now
            self.steps += 1
        target = self._window(gate)
        if target is not None:
            self.frame.setGeometry(_logical(target, self.frame).adjusted(-6, -6, 6, 6))
            area = _logical(target, self.banner)
            self.banner.move(area.center().x() - self.banner.width() // 2, max(area.top() + 8, 0))
            point = rec.get("screen_point")
            tip = _logical((point[0], point[1], point[0], point[1]), self.cursor).topLeft() if point else area.center()
            if tip != getattr(self, "_tip", None):
                self._tip = tip
                self.cursor.glide(tip)
        doing = say(rec)
        if rec["status"] in ("executed", "failed", "refused", "denied") and now - self.last_at > 0.4:
            doing = f"正在看画面、想下一步（{now - self.last_at:.0f} 秒）"
        timing = locale.t(f"第 {self.steps} 步") + (locale.t(f" · 上一步 {self.step_s:.1f} 秒") if self.step_s else "")
        self.banner.line = f"{locale.t(doing)}  ·  {locale.t(timing)}"  # painted: no label translates it for us
        self.banner.phase += 0.25
        self.frame.phase += 0.12
        self._show()
        self.banner.update()
        self.frame.update()

    def _window(self, gate) -> tuple[int, int, int, int] | None:
        """The allowed window in front (else the first allowed one), in physical pixels."""
        try:
            wins = gate.allowed_windows(minimized=False)
            fg = gate.desktop.foreground()
        except Exception:
            return None
        front = next((w for w in wins if w.handle == fg), wins[0] if wins else None)
        return front.rect if front else None

