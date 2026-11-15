"""The opening animation: a greeting written stroke by stroke in ten languages, on a glass card.

WrittenGreeting is ported unchanged from ChatGPT's studio build (Codex work dir business-cluster-backend,
2026-10-26); the user asked for this animation in this app. The card around it uses this app's widgets.
"""
from __future__ import annotations

import math
import bisect
import os
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QTimer, Qt, QRectF, Signal, QPointF, QEvent
from PySide6.QtGui import QPainter, QPainterPath, QFont, QFontDatabase, QColor, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget, QApplication

from codedoctor.desktop.i18n import tr
from codedoctor.desktop.liquid import Glass, MedicalMark
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import label

GREETINGS = (("Hello", "Segoe Script"), ("Bonjour", "Segoe Script"), ("你好", "KaiTi"),
             ("Hola", "Segoe Script"), ("Olá", "Segoe Script"), ("こんにちは", "MS Gothic"),
             ("Привет", "Segoe Script"), ("Hallo", "Segoe Script"), ("Ciao", "Segoe Script"), ("안녕하세요", "Malgun Gothic"))


class WrittenGreeting(QWidget):
    completed = Signal()

    def __init__(self, reduced=False, parent=None):
        super().__init__(parent)
        self.reduced = reduced
        self.elapsed = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.advance)
        self.index, self.progress = 0, 0.0
        self.path = QPainterPath()
        self._samples = []
        self._lengths = []
        self._key = None
        self._played_ms=0
        self._started=False
        self._complete=False
        self._watched_window=None
        self._gate=QTimer(self)
        self._gate.setSingleShot(True)
        self._gate.timeout.connect(self._sync_visibility)
        self.setMinimumHeight(140)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        app=QApplication.instance()
        if not app.property("greetingFontsReady"):
            font_dir = Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts"
            for filename in ("segoesc.ttf", "simkai.ttf", "msgothic.ttc", "malgun.ttf"):
                path = font_dir/filename
                if path.is_file():
                    QFontDatabase.addApplicationFont(str(path))
            app.setProperty("greetingFontsReady",True)

    def showEvent(self, event):
        super().showEvent(event)
        if self._watched_window is None:
            self._watched_window=self.window()
            self._watched_window.installEventFilter(self)
        if self.reduced:
            self.progress = 1.0
            self.update()
        else:
            self._gate.start(0)

    def hideEvent(self, event):
        self._gate.stop()
        self._set_active(False)
        super().hideEvent(event)

    def _set_active(self,active):
        if self.reduced or self._complete:
            return
        if active and not self.timer.isActive():
            self.elapsed.start()
            self._started=True
            self.timer.start()
        elif not active and self.timer.isActive():
            self._played_ms+=self.elapsed.elapsed()
            self.timer.stop()

    def _sync_visibility(self):
        headless=QApplication.instance().platformName() in {"offscreen","minimal"}
        self._set_active(self.isVisible() and not self.window().isMinimized() and (headless or self.window().isActiveWindow()))

    def eventFilter(self,obj,event):
        if obj is self._watched_window:
            if event.type() in {QEvent.WindowDeactivate,QEvent.Hide}:
                self._set_active(False)
            elif event.type() in {QEvent.WindowActivate,QEvent.WindowStateChange,QEvent.Show}:
                self._gate.start(0)
        return super().eventFilter(obj,event)

    def advance(self, milliseconds=None):
        time = self._played_ms+self.elapsed.elapsed() if milliseconds is None else milliseconds
        cycle = 1800
        if time >= len(GREETINGS)*cycle:
            self.timer.stop()
            self._complete=True
            self.completed.emit()
            return
        self.index = int(time//cycle)
        phase = (time % cycle)/cycle
        self.progress = min(1.0, phase/.54) if phase < .77 else max(0.0, 1-(phase-.77)/.23)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        word, family = GREETINGS[self.index]
        key = (self.index, self.width(), self.height())
        if self._key != key:
            font = QFont(family)
            font.setPixelSize(min(110, max(46, self.width()//8)))
            self.path = QPainterPath()
            self.path.addText(0,0,font,word)
            # Flatten once. Calling percentAtLength hundreds of times on each
            # glyph curve caused a visible pause on the first writing frame.
            self._samples=[]
            self._lengths=[]
            length=0.0
            for polygon in self.path.toSubpathPolygons():
                previous=None
                for point in polygon:
                    if previous is not None:
                        length+=math.hypot(point.x()-previous.x(),point.y()-previous.y())
                    self._samples.append((point,previous is None))
                    self._lengths.append(length)
                    previous=point
            self._key = key
        bounds = self.path.boundingRect()
        scale = min(1.0, (self.width()-30)/max(1,bounds.width()))
        painter.translate(self.width()/2,self.height()/2)
        painter.scale(scale,scale)
        painter.translate(-bounds.center().x(),-bounds.center().y())
        # Trace the glyph contours and gradually ink the filled letterforms.
        # This is a designed path reveal, not genuine handwriting recognition.
        progress = self.progress*self.progress*(3-2*self.progress)
        trace = QPainterPath()
        last = None
        end=bisect.bisect_right(self._lengths,(self._lengths[-1] if self._lengths else 0)*progress)
        for point,start in self._samples[:end]:
            if start or last is None:
                trace.moveTo(point)
            else:
                trace.lineTo(point)
            last = point
        painter.setPen(QPen(QColor(48,66,98,235),1.4,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        painter.drawPath(trace)
        painter.save()
        painter.setClipRect(QRectF(bounds.left()-2,bounds.top()-2,(bounds.width()+4)*progress,bounds.height()+4))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(44,62,95,round(235*min(1,progress*1.3))))
        painter.drawPath(self.path)
        painter.restore()


class Welcome(Glass):
    """The greeting card. ``proceed`` fires on 进入, on 跳过动画, or when all ten greetings were written."""
    own_entrance = True
    proceed = Signal()

    def __init__(self, reduced: bool = False, parent=None):
        super().__init__(parent, radius=36, padding=26)
        self.body.setSpacing(10)
        self.setMaximumWidth(900)
        self.setMinimumWidth(560)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(MedicalMark(44))
        top.addWidget(label("Lumen", size=17, bold=True, color=C["ink"]))
        top.addStretch()
        top.addWidget(label("SOFTWARE · SYSTEMS · LOGIC", size=10, bold=True, color=C["text3"]))
        self.body.addLayout(top)
        self.body.addSpacing(16)
        self.greeting = WrittenGreeting(reduced)
        self.body.addWidget(self.greeting, 1)
        subtitle = label(tr("tagline"), size=14, color=C["text2"])
        subtitle.setAlignment(Qt.AlignCenter)
        self.body.addWidget(subtitle)
        self.body.addSpacing(16)
        row = QHBoxLayout()
        row.addStretch()
        self.skip = QPushButton(tr("skip"))
        self.skip.setObjectName("Ghost")
        self.begin = QPushButton(tr("enter"))
        self.begin.setObjectName("Primary")
        for b in (self.skip, self.begin):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(38)
        self.skip.clicked.connect(self.proceed)
        self.begin.clicked.connect(self.proceed)
        self.greeting.completed.connect(self.proceed)
        row.addWidget(self.skip)
        row.addWidget(self.begin)
        self.body.addLayout(row)
