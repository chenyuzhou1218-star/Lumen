"""The composer's voice mode (2026-11-03), in the manner of ChatGPT: × on the left cancels, the waveform runs across
the middle - quiet moments as a dotted line, speech as rounded bars that grow with the voice, newest on the right -
then ■ (stop and write it into the box) and the blue ↑ (stop and send)."""

from __future__ import annotations

import threading
from collections import deque

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QWidget

from codedoctor.desktop import i18n, icons, voice
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.theme import FONT_FAMILY

INK = QColor("#2b3240")
DOT = QColor("#b9bfca")
BLUE = QColor("#2f6bff")


class Round(QAbstractButton):
    """A round button: white with a hairline (× and ■), or filled blue (↑)."""

    def __init__(self, kind: str, tip: str, filled: bool = False, size: int = 36):
        super().__init__()
        self.kind, self.filled = kind, filled
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.filled:
            p.setPen(Qt.NoPen)
            p.setBrush(BLUE.lighter(112) if self.underMouse() else BLUE)
            p.drawEllipse(r)
            icons.paint(p, self.kind, r.adjusted(8, 8, -8, -8), QColor("white"), 2.0)
        else:
            p.setPen(QPen(QColor(31, 38, 51, 34), 1))
            p.setBrush(QColor("#f1f3f7") if self.underMouse() else QColor("white"))
            p.drawEllipse(r)
            icons.paint(p, self.kind, r.adjusted(9, 9, -9, -9), INK, 1.9)
        p.end()


class MicButton(QAbstractButton):
    """The composer's microphone: a line icon, a soft grey disc on hover."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("voice"))

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(31, 38, 51, 18))
            p.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        icons.paint(p, "mic", QRectF(8, 8, 20, 20), INK, 1.7)
        p.end()


class Waveform(QWidget):
    """Levels as they come (0..1), newest at the right edge: a dot when quiet, a bar when speaking."""
    STEP = 6

    def __init__(self):
        super().__init__()
        self.levels: deque[float] = deque(maxlen=400)
        self.shown: list[float] = []
        self.writing = False
        self.phase = 0.0
        self.setMinimumHeight(36)
        self.tick = QTimer(self)
        self.tick.setInterval(33)  # eases bars toward their level: ~30 frames a second while visible
        self.tick.timeout.connect(self._step)

    def start(self) -> None:
        self.levels.clear()
        self.shown = []
        self.writing = False
        self.tick.start()

    def stop(self) -> None:
        self.tick.stop()

    def push(self, level: float) -> None:
        self.levels.append(level)

    def _step(self) -> None:
        n = max(1, self.width() // self.STEP)
        target = list(self.levels)[-n:]
        target = [0.0] * (n - len(target)) + target
        if len(self.shown) != n:
            self.shown = list(target)
        self.shown = [s + (t - s) * 0.45 for s, t in zip(self.shown, target)]
        self.phase += 0.12
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h, mid = self.height(), self.height() / 2
        if self.writing:  # transcribing: a calm travelling shimmer through the dots, and the words saying so
            import math

            p.setPen(Qt.NoPen)
            for i in range(self.width() // self.STEP):
                glow = 0.5 + 0.5 * math.sin(self.phase * 2 - i * 0.35)
                c = QColor(DOT)
                c.setAlpha(int(90 + 140 * glow))
                p.setBrush(c)
                p.drawEllipse(QPointF(i * self.STEP + 3, mid), 1.4, 1.4)
            f = QFont(FONT_FAMILY)
            f.setPixelSize(13)
            p.setFont(f)
            p.setPen(QColor("#5b6474"))
            w = p.fontMetrics().horizontalAdvance(tr("voice_writing")) + 24
            bg = QRectF((self.width() - w) / 2, mid - 12, w, 24)
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawRoundedRect(bg, 12, 12)
            p.drawText(bg, Qt.AlignCenter, tr("voice_writing"))
            p.end()
            return
        n = len(self.shown)
        for i, level in enumerate(self.shown):
            x = self.width() - (n - i) * self.STEP + self.STEP / 2
            if level < 0.08:  # quiet: a dot on the line
                p.setPen(Qt.NoPen)
                p.setBrush(DOT)
                p.drawEllipse(QPointF(x, mid), 1.3, 1.3)
                continue
            bar = max(4.0, level * (h - 6))
            recent = i > n - 8
            p.setPen(Qt.NoPen)
            p.setBrush(INK if recent else QColor("#7d8594"))
            p.drawRoundedRect(QRectF(x - 1.5, mid - bar / 2, 3, bar), 1.5, 1.5)
        p.end()


class _Written(QObject):
    done = Signal(object)  # the text, or the exception, from the worker thread


class VoiceBar(QWidget):
    """Recording in the composer: × | waveform | ■ | ↑. `text(str, send)` when written out; `closed` on ×."""
    text = Signal(str, bool)
    closed = Signal()
    problem = Signal(str)

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(10)
        self.cancel = Round("close", tr("voice_cancel"))
        self.wave = Waveform()
        self.stop_btn = Round("stop", tr("voice_stop"))
        self.send_btn = Round("send", tr("voice_send"), filled=True)
        lay.addWidget(self.cancel)
        lay.addWidget(self.wave, 1)
        lay.addWidget(self.stop_btn)
        lay.addWidget(self.send_btn)
        self.recorder = voice.Recorder()
        self.recorder.level.connect(self.wave.push)
        self.recorder.failed.connect(lambda _: self._fail(tr("voice_no_mic")))
        self.cancel.clicked.connect(self._cancel)
        self.stop_btn.clicked.connect(lambda: self._finish(False))
        self.send_btn.clicked.connect(lambda: self._finish(True))
        self.busy = False
        self.abandoned = False

    def begin(self) -> None:
        self.busy = False
        self.abandoned = False
        for b in (self.stop_btn, self.send_btn, self.cancel):
            b.setEnabled(True)
        self.wave.start()
        self.recorder.start()
        voice.warm()  # the speech model loads while the person speaks

    def _cancel(self) -> None:
        if self.busy:  # already being written out: the text that comes back is thrown away, never sent or put in the box
            self.abandoned = True
        self.recorder.stop()
        self.wave.stop()
        self.closed.emit()

    def _fail(self, why: str) -> None:
        self.recorder.stop()
        self.wave.stop()
        self.problem.emit(why)
        self.closed.emit()

    def _finish(self, send: bool) -> None:
        if self.busy:
            return
        self.busy = True
        pcm = self.recorder.stop()
        self.wave.writing = True
        for b in (self.stop_btn, self.send_btn):
            b.setEnabled(False)
        bridge = self._bridge = _Written()
        bridge.done.connect(lambda result: self._written(result, send))
        language = i18n.language()

        def work():
            try:
                result = voice.transcribe(pcm, language)
            except Exception as e:  # said in the composer, never raised into Qt
                result = e
            bridge.done.emit(result)

        threading.Thread(target=work, daemon=True, name="codedoctor-transcribe").start()

    def _written(self, result, send: bool) -> None:
        self.wave.stop()
        self.busy = False
        if self.abandoned:  # the person pressed × while it was written out: nothing comes back
            self.abandoned = False
            return
        if isinstance(result, Exception):
            self.problem.emit(tr("voice_failed", why=str(result)[:160]))
            self.closed.emit()
        elif not result:
            self.problem.emit(tr("voice_none"))
            self.closed.emit()
        else:
            self.text.emit(result, send)
