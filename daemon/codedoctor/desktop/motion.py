"""One motion vocabulary for the whole window.

Short, decelerating and staggered — the same rhythm as the written greeting.
Every entrance goes through :func:`enter`, so a page, a rail item and a message
bubble all arrive with the same curve instead of three different ones.

The rise is animated through the container's layout margins rather than its
geometry: a layout-managed widget must not have its ``pos`` animated, or the
layout snaps it back on the next relayout.
"""
# Ported 2026-10-27 from ChatGPT's studio build (Codex work dir business-cluster-backend, 2026-10-26),
# unchanged except for this note; the user asked for its look and opening animation in this app.
from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, QTimer, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QSizePolicy, QStackedWidget, QWidget

# Decelerating curves: quick out of the gate, long settle. This is what reads as
# "silky"; a linear or symmetric curve at the same duration feels mechanical.
OUT = QEasingCurve(QEasingCurve.OutCubic)
SETTLE = QEasingCurve(QEasingCurve.OutQuint)
BOTH = QEasingCurve(QEasingCurve.InOutCubic)

_reduced = False


def set_reduced(flag: bool) -> None:
    """Honour the user's reduced-motion preference for every later animation."""
    global _reduced
    _reduced = bool(flag)


def reduced() -> bool:
    return _reduced


def alive(widget) -> bool:
    try:
        widget.objectName()
        return True
    except RuntimeError:  # already destroyed on the C++ side
        return False


def _rise(widget: QWidget, dy: int, duration: int, curve: QEasingCurve) -> None:
    """Slide a layout container up by ``dy`` pixels by shrinking its top margin."""
    layout = widget.layout()
    if layout is None or not dy:
        return
    base = layout.contentsMargins()
    previous=getattr(widget,"_rise",None)
    if previous is not None and previous.state()==QAbstractAnimation.Running:
        remembered=getattr(widget,"_rise_base",None)
        if remembered is not None:
            from PySide6.QtCore import QMargins
            base=QMargins(*remembered)
        previous.stop()
        previous.deleteLater()
    widget._rise_base=(base.left(),base.top(),base.right(),base.bottom())
    top = base.top()
    animation = QVariantAnimation(widget)
    animation.setDuration(duration)
    animation.setStartValue(float(top + dy))
    animation.setEndValue(float(top))
    animation.setEasingCurve(curve)

    def step(value):
        try:
            margins = layout.contentsMargins()
            layout.setContentsMargins(margins.left(), int(value), margins.right(), margins.bottom())
        except RuntimeError:
            animation.stop()

    animation.valueChanged.connect(step)
    def settle():
        if alive(widget):
            layout.setContentsMargins(*widget._rise_base)
    animation.finished.connect(settle)
    animation.start(QAbstractAnimation.KeepWhenStopped)
    widget._rise = animation


def enter(widget: QWidget | None, *, delay: int = 0, duration: int = 320, dy: int = 12,
          start: float = 0.0, curve: QEasingCurve | None = None) -> None:
    """Slide a widget in by ``dy`` pixels.

    Deliberately no opacity: a QGraphicsOpacityEffect renders the widget into a
    transparent layer, which turns off subpixel text rendering and makes glyphs
    look uneven and washed out over a textured backdrop. Movement alone is
    enough — and text stays crisp.
    """
    if widget is None or not alive(widget) or _reduced:
        return
    curve = curve or OUT

    def begin():
        if alive(widget):
            _rise(widget, dy, duration, curve)

    if delay:
        QTimer.singleShot(delay, begin)
    else:
        begin()


def stagger(widgets, *, step: int = 45, duration: int = 320, dy: int = 12) -> None:
    """Reveal a series of widgets one after another."""
    for index, widget in enumerate(widgets):
        if widget is not None:
            enter(widget, delay=index * step, duration=duration, dy=dy)


class FadeStack(QStackedWidget):
    """A stacked widget whose pages arrive instead of appearing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token = 0
        self.currentChanged.connect(lambda _i: self._fit_current())

    def addWidget(self, widget) -> int:  # noqa: N802 (Qt naming)
        index = super().addWidget(widget)
        self._fit_current()
        return index

    def _fit_current(self) -> None:
        """Only the page on screen counts for the window's size. A real bug: the settings page (a long file path)
        needed 1350 px, every page then did, the window grew past a 1536 px screen and the stop button next to
        send was off the screen - it could not be clicked."""
        for i in range(self.count()):
            page = self.widget(i)
            on = page is self.currentWidget()
            page.setSizePolicy(QSizePolicy.Preferred if on else QSizePolicy.Ignored,
                               QSizePolicy.Preferred if on else QSizePolicy.Ignored)
        self.updateGeometry()

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802 (Qt naming)
        if index == self.currentIndex():
            return
        super().setCurrentIndex(index)
        self._token += 1
        token = self._token
        page = self.currentWidget()
        if page is None or getattr(page, "own_entrance", False):
            return  # the page animates its own children instead

        def show():
            if token == self._token and alive(page):
                enter(page, duration=280, dy=10)

        QTimer.singleShot(0, show)


def tween(widget: QWidget, prop: bytes, start, end, *, duration: int = 260,
          curve: QEasingCurve | None = None) -> QPropertyAnimation | None:
    """Animate any Qt property on a widget (used for the composer's focus glow)."""
    if widget is None or not alive(widget):
        return None
    if _reduced:
        setattr(widget, prop.decode(), end)
        widget.update()
        return None
    animation = QPropertyAnimation(widget, prop, widget)
    animation.setDuration(duration)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(curve or OUT)
    animation.start(QAbstractAnimation.KeepWhenStopped)
    widget._tween = animation
    return animation


def spring_height(widget: QWidget, target: int, *, duration: int = 300) -> None:
    """Grow or shrink a widget with a small overshoot — the jelly in the composer."""
    if widget is None or not alive(widget):
        return
    target = int(target)
    if _reduced or widget.height() == target:
        widget.setFixedHeight(target)
        return
    previous = getattr(widget, "_height_anim", None)
    if previous is not None:
        previous.stop()
    animation = QVariantAnimation(widget)
    animation.setDuration(duration)
    animation.setStartValue(float(widget.height()))
    animation.setEndValue(float(target))
    animation.setEasingCurve(QEasingCurve(QEasingCurve.OutBack))

    def step(value):
        if not alive(widget):
            animation.stop()
            return
        widget.setFixedHeight(max(1, int(round(value))))

    animation.valueChanged.connect(step)
    animation.start(QAbstractAnimation.KeepWhenStopped)
    widget._height_anim = animation


def pop(widget: QWidget, size: int, *, duration: int = 280) -> None:
    """A short elastic pop, used when the send button becomes available."""
    if widget is None or not alive(widget):
        return
    if _reduced:
        widget.setFixedSize(size, size)
        return
    previous = getattr(widget, "_pop_anim", None)
    if previous is not None:
        previous.stop()
    animation = QVariantAnimation(widget)
    animation.setDuration(duration)
    animation.setStartValue(float(size * 0.78))
    animation.setEndValue(float(size))
    animation.setEasingCurve(QEasingCurve(QEasingCurve.OutBack))

    def step(value):
        if not alive(widget):
            animation.stop()
            return
        side = max(1, int(round(value)))
        widget.setFixedSize(side, side)

    animation.valueChanged.connect(step)
    animation.finished.connect(lambda: alive(widget) and widget.setFixedSize(size, size))
    animation.start(QAbstractAnimation.KeepWhenStopped)
    widget._pop_anim = animation
