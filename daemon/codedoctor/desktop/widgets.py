"""Small reusable widgets: avatar, status chip, pulsing dot, auto-height markdown, cards, step rows."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal, Property
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QTextFormat
from PySide6.QtWidgets import QApplication, QGridLayout, QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget

from codedoctor.desktop.theme import C, FONT_FAMILY, MONO_FAMILY, ROLE_COLOR, STATUS_STYLE


def shadow(widget: QWidget, blur: int = 24, alpha: int = 28, dy: int = 3, radius: int = 18) -> None:
    """A soft drop shadow under the widget. Painted by a sibling from a cached image: a QGraphicsDropShadowEffect
    would render the widget off screen and blur it again on every repaint of anything inside it (each key typed in
    the composer, each caret blink)."""
    _Shadow(widget, blur, alpha, dy, radius)


class _Shadow(QWidget):
    def __init__(self, target: QWidget, blur: int, alpha: int, dy: int, radius: int):
        super().__init__(None)
        self.target, self.spread, self.alpha, self.dy, self.radius = target, max(2, blur // 2), alpha, dy, radius
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        self._pix = None
        self._key = None
        target.installEventFilter(self)
        target.destroyed.connect(self.deleteLater)
        self._follow()

    def _follow(self) -> None:
        parent = self.target.parentWidget()
        if parent is None:
            return
        if self.parentWidget() is not parent:
            self.setParent(parent)
        s = self.spread
        self.setGeometry(self.target.geometry().adjusted(-s, -s + self.dy, s, s + self.dy))
        self.setVisible(self.target.isVisible())
        self.stackUnder(self.target)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind in (QEvent.ParentChange, QEvent.Move, QEvent.Resize, QEvent.Show):
            self._follow()
        elif kind == QEvent.Hide:
            self.hide()
        return False

    def paintEvent(self, _e):
        from PySide6.QtGui import QImage

        dpr = self.devicePixelRatioF() or 1.0
        key = (self.width(), self.height(), dpr)
        if key != self._key:  # a blur by scaling a small copy up: cheap, and only when the size changes
            self._key = key
            s, k = self.spread, 4
            w, h = max(1, self.width() // k), max(1, self.height() // k)
            small = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            small.fill(Qt.transparent)
            p = QPainter(small)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(60, 50, 30, min(255, self.alpha * 3)))
            p.drawRoundedRect(QRectF(s / k, s / k, max(1.0, w - 2 * s / k), max(1.0, h - 2 * s / k)),
                              self.radius / k, self.radius / k)
            p.end()
            for _ in range(2):
                small = small.scaled(max(1, w // 2), max(1, h // 2), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                small = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            from PySide6.QtGui import QPixmap

            self._pix = QPixmap.fromImage(small.scaled(int(self.width() * dpr), int(self.height() * dpr),
                                                       Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            self._pix.setDevicePixelRatio(dpr)
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pix)


def label(text: str = "", name: str | None = None, wrap: bool = False, selectable: bool = False, size: int | None = None,
          bold: bool = False, color: str | None = None) -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    if selectable:
        lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
    style = []
    if size:
        style.append(f"font-size: {size}px;")
    if bold:
        style.append("font-weight: 700;")
    if color:
        style.append(f"color: {color};")
    if style:
        lb.setStyleSheet(" ".join(style))
    return lb


class Avatar(QWidget):
    """Coloured circle with a short role glyph."""

    def __init__(self, role: str, size: int = 28, text: str | None = None):
        super().__init__()
        self.role, self.size_px = role, size
        self.text = text or {"general": "医", "head_dispatch": "调", "head_logic": "逻", "worker": "工", "guardian": "监",
                             "investigator": "查", "system": "系", "user": "你"}.get(role, "A")
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(ROLE_COLOR.get(self.role, "#888")))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self.size_px, self.size_px)
        f = QFont(FONT_FAMILY)
        f.setPixelSize(int(self.size_px * 0.46))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(self.rect(), Qt.AlignCenter, self.text)


class Chip(QLabel):
    """Rounded status pill coloured by its text (完成 / 运行中 / 成立 / 高 ...)."""

    def __init__(self, text: str = "", fg: str | None = None, bg: str | None = None):
        super().__init__()
        self._fixed = (fg, bg)
        self.set(text)

    def set(self, text: str) -> None:
        if getattr(self, "_shown", None) == text:  # refreshed every second: a style sheet re-polishes the widget
            return
        self._shown = text
        fg, bg = self._fixed
        sfg, sbg = STATUS_STYLE.get(text, (C["text2"], C["gray_soft"]))
        self.setText(text)
        self.setStyleSheet(f"background: {bg or sbg}; color: {fg or sfg}; border-radius: 10px; padding: 2px 9px; "
                           f"font-size: 12px; font-weight: 600;")
        # A parentless widget made visible becomes a window of its own: on Windows a tiny titled window appears,
        # and stays while the UI thread is busy (the risk list makes dozens of chips). Chips are usually created
        # before they are put in a layout, so until then only remember the wish; event() applies it.
        self._want_visible = bool(text)
        if self.parent() is not None or not text:
            self.setVisible(self._want_visible)

    def event(self, e) -> bool:
        if e.type() == QEvent.ParentChange and self.parent() is not None:
            self.setVisible(self._want_visible)
        return super().event(e)


class PulseDot(QWidget):
    """Status dot; pulses while `active`."""

    def __init__(self, color: str = C["blue"], size: int = 10):
        super().__init__()
        self._color, self._size, self._phase, self._active = QColor(color), size, 0.0, False
        self.setFixedSize(size + 6, size + 6)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_state(self, color: str, active: bool) -> None:
        self._color = QColor(color)
        if active and not self._active:
            self._timer.start(60)
        elif not active and self._active:
            self._timer.stop()
            self._phase = 0.0
        self._active = active
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.06) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QRectF(3, 3, self._size, self._size)
        if self._active:
            halo = QColor(self._color)
            halo.setAlphaF(0.35 * (1 - self._phase))
            grow = 3 * self._phase
            p.setBrush(halo)
            p.setPen(Qt.NoPen)
            p.drawEllipse(c.adjusted(-grow, -grow, grow, grow))
        p.setBrush(self._color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(c)


class Spinner(QWidget):
    """Small rotating arc for 'thinking...'."""

    def __init__(self, size: int = 16, color: str = C["accent"]):
        super().__init__()
        self._angle, self._color = 0, QColor(color)
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def _tick(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self._color, 2.2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.drawArc(r, -self._angle * 16, 270 * 16)


class CardGrid(QWidget):
    """Cards in as many columns as fit: a narrow window gets one column, never a card cut off at its edge."""

    def __init__(self, cards: list, card_width: int = 420, spacing: int = 12, most: int = 3):
        super().__init__()
        self.cards, self.card_width, self.most = cards, card_width, most
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self.columns = 0
        self._place(1)

    def _place(self, columns: int) -> None:
        if columns == self.columns:
            return
        for i in range(max(self.columns, columns)):
            self.grid.setColumnStretch(i, 1 if i < columns else 0)
        self.columns = columns
        for card in self.cards:
            self.grid.removeWidget(card)
        for i, card in enumerate(self.cards):
            self.grid.addWidget(card, i // columns, i % columns)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place(max(1, min(self.most, (self.width() + 12) // (self.card_width + 12))))


link_handler = None  # the window sets this: web links go to the browser on the right


def open_link(url: str) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    if link_handler is not None and url.startswith(("http://", "https://")):
        link_handler(url)
    else:
        QDesktopServices.openUrl(QUrl(url))


class Markdown(QTextBrowser):
    """Read-only markdown that sizes itself to its content (no inner scrollbar)."""

    def __init__(self, text: str = "", mono: bool = False, size: int = 14):
        super().__init__()
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)  # a clicked link opens in the panel on the right (open_link), not out of the window
        self.anchorClicked.connect(lambda url: open_link(url.toString()))
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        fam = MONO_FAMILY if mono else FONT_FAMILY
        self.setStyleSheet(f"background: transparent; font-family: {fam}; font-size: {size}px; color: {C['text']};")
        self.document().setDefaultStyleSheet(
            f"h1 {{ font-size: {size + 6}px; font-weight: 700; }} h2 {{ font-size: {size + 3}px; font-weight: 700; }} "
            f"h3 {{ font-size: {size + 1}px; font-weight: 700; }} code {{ font-family: {MONO_FAMILY}; color: #8a3b22; }} "
            f"p, li {{ line-height: 150%; }}")
        self.document().setDocumentMargin(2)
        self.document().contentsChanged.connect(self._fit)
        self._mono = mono
        self._size = size
        self.set(text)

    def _code_at(self, cursor) -> str:
        """The whole code block the cursor is in, without its fence; "" outside one."""
        if self._mono:
            return self.toPlainText()

        def fenced(block) -> bool:
            return block.isValid() and block.blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence)

        block = cursor.block()
        if not fenced(block):
            return ""
        while fenced(block.previous()):
            block = block.previous()
        lines = []
        while fenced(block):
            lines.append(block.text())
            block = block.next()
        return "\n".join(lines)

    def contextMenuEvent(self, e):  # noqa: N802 (Qt naming)
        menu = self.createStandardContextMenu(e.pos())
        code = self._code_at(self.cursorForPosition(e.pos()))
        if code:
            menu.addSeparator()
            menu.addAction("复制这段代码").triggered.connect(lambda: QApplication.clipboard().setText(code))
        menu.exec(e.globalPos())

    def set(self, text: str) -> None:
        if self._mono:
            self.setPlainText(text)
        else:
            self.setMarkdown(text)
            self._style_headings()
            self._style_body()
            self._style_code()
            self._style_tables()
        self._fit()

    def _style_body(self) -> None:
        """Air between paragraphs and lines: Qt's Markdown sets everything tight."""
        from PySide6.QtGui import QTextBlockFormat, QTextCursor

        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        block = self.document().begin()
        while block.isValid():
            cursor.setPosition(block.position())
            if cursor.currentTable() is None:  # the cells have their own padding
                fmt = QTextBlockFormat()
                listed = block.textList() is not None
                fmt.setLineHeight(150.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                fmt.setBottomMargin(3 if listed else 9)
                cursor.mergeBlockFormat(fmt)
            else:
                fmt = QTextBlockFormat()
                fmt.setTopMargin(0)
                fmt.setBottomMargin(0)
                cursor.mergeBlockFormat(fmt)
            block = block.next()
        cursor.endEditBlock()

    def _style_tables(self) -> None:
        from PySide6.QtGui import QBrush, QTextFrameFormat, QTextLength, QTextTable

        for frame in self.document().rootFrame().childFrames():
            if isinstance(frame, QTextTable):
                fmt = frame.format()
                fmt.setBorder(1)
                fmt.setBorderBrush(QBrush(QColor("#e4e4e4")))
                fmt.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
                fmt.setBorderCollapse(True)
                fmt.setCellPadding(7)
                fmt.setCellSpacing(0)
                fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
                frame.setFormat(fmt)

    def _style_code(self) -> None:
        """A fenced block is a soft grey box in a fixed-width font, as it is everywhere else people read code."""
        from PySide6.QtGui import QBrush, QFont, QTextBlockFormat, QTextCharFormat, QTextCursor

        block = self.document().begin()
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        while block.isValid():
            if block.blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence):
                cursor.setPosition(block.position())
                fmt = QTextBlockFormat()
                fmt.setBackground(QBrush(QColor("#f5f5f5")))
                fmt.setLeftMargin(0)
                fmt.setTopMargin(0)
                fmt.setBottomMargin(0)
                fmt.setLineHeight(135.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                cursor.mergeBlockFormat(fmt)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                ch = QTextCharFormat()
                ch.setFontFamilies(["Cascadia Mono", "Consolas"])
                ch.setFontPointSize(max(8.0, self._size * .68))
                ch.setFontWeight(QFont.Normal)
                cursor.mergeCharFormat(ch)
            block = block.next()
        cursor.endEditBlock()

    def _style_headings(self) -> None:
        from PySide6.QtGui import QTextCharFormat, QTextCursor
        base = self._size
        sizes = {1: base + 6, 2: base + 3, 3: base + 1, 4: base, 5: base, 6: base}
        block = self.document().begin()
        while block.isValid():
            level = block.blockFormat().headingLevel()
            if level:
                # select only this block's text: a selection crossing the block boundary would also
                # restyle the previous block (and drop its list bullet)
                cur = QTextCursor(block)
                cur.movePosition(QTextCursor.StartOfBlock)
                cur.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                fmt = QTextCharFormat()
                fmt.setFontPointSize(sizes.get(level, base) * 0.75)
                fmt.setFontWeight(QFont.Bold)
                cur.mergeCharFormat(fmt)
                bf = block.blockFormat()
                bf.setTopMargin(10)
                bf.setBottomMargin(4)
                QTextCursor(block).setBlockFormat(bf)
            block = block.next()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def _fit(self):
        self.document().setTextWidth(self.viewport().width() or 600)
        h = int(self.document().size().height()) + 6
        if self.height() != h:
            self.setFixedHeight(h)


class Card(QFrame):
    def __init__(self, padding: int = 14, spacing: int = 8, raised: bool = False):
        super().__init__()
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(padding, padding - 2, padding, padding - 2)
        self.lay.setSpacing(spacing)
        if raised:
            shadow(self, 18, 18, 2)


class Collapsible(QWidget):
    """A clickable header row that shows / hides a body widget, with a rotating chevron."""

    toggled = Signal(bool)

    def __init__(self, header: QWidget, body: QWidget, expanded: bool = False):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.header, self.body = header, body
        self.chev = QLabel()
        self.chev.setFixedSize(16, 16)
        hl = header.layout()
        if hl is not None:
            hl.addWidget(self.chev)
        else:  # a bare label as the header: put the chevron in front of it, or nothing shows it can open
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(6)
            rl.addWidget(self.chev)
            rl.addWidget(header)
            rl.addStretch(1)
            header = row
            self.header = row
        lay.addWidget(header)
        lay.addWidget(body)
        header.setCursor(Qt.PointingHandCursor)
        header.mousePressEvent = lambda e: self.set_expanded(not self.expanded)
        self.expanded = not expanded
        self.set_expanded(expanded)

    def set_expanded(self, on: bool) -> None:
        if on == self.expanded:
            return
        self.expanded = on
        self.body.setVisible(on)
        from codedoctor.desktop import icons

        self.chev.setPixmap(icons.icon("chevron_down" if on else "chevron_right", C["text3"], 16).pixmap(16, 16))
        self.toggled.emit(on)


BADGE = {  # tool -> (glyph, colour)
    "read_file": ("读", "#3b6fd6"), "list_dir": ("目", "#3b6fd6"), "search_text": ("搜", "#3b6fd6"),
    "read_evidence": ("证", "#3b6fd6"), "run_command": ("令", "#5a5751"),
    "edit_file": ("改", "#c96442"), "create_file": ("新", "#c96442"),
    "graph_overview": ("图", "#7a52c7"), "graph_rebuild": ("图", "#7a52c7"), "graph_find": ("图", "#7a52c7"),
    "graph_neighbors": ("联", "#7a52c7"), "graph_impact": ("响", "#7a52c7"), "graph_common_cause": ("因", "#7a52c7"),
    "graph_risks": ("险", "#c8463d"), "submit_claim": ("论", "#2f8f5b"), "check_claim": ("核", "#2f8f5b"),
    "withdraw_claim": ("撤", "#8a877f"), "review_claim": ("审", "#c97a22"), "remember": ("记", "#1a7f86"),
    "recall": ("忆", "#1a7f86"), "delegate": ("派", "#c96442"), "wait_for": ("等", "#c96442"),
    "consult": ("问", "#c96442"), "task_status": ("况", "#c96442"), "raise_objection": ("异", "#c8463d"),
    "withdraw_objection": ("撤", "#8a877f"), "send_message": ("信", "#c96442"),
    "_thought": ("思", "#9a978f"), "_error": ("!", "#c8463d"), "_switch": ("换", "#b7791f"), "_stop": ("停", "#b7791f"),
    "_resume": ("续", "#2f8f5b"),
    "_test": ("测", "#2f8f5b"),
}


class Badge(QWidget):
    def __init__(self, glyph: str, color: str, size: int = 22):
        super().__init__()
        self.glyph, self.color = glyph, QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor(self.color)
        bg.setAlpha(34)
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 6, 6)
        f = QFont(FONT_FAMILY)
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        p.setPen(self.color)
        p.drawText(self.rect(), Qt.AlignCenter, self.glyph)


class StepRow(QWidget):
    """One agent action: icon, description, result mark, time; click to show the full content."""

    clicked = Signal()

    def __init__(self, icon: str, text: str, when: str, sub: str = ""):
        super().__init__()
        self.setObjectName("StepRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)
        glyph, color = BADGE.get(icon, ("•", "#8a877f"))
        ic = Badge(glyph, color)
        self.text = label(text, size=13)
        self.text.setTextFormat(Qt.PlainText)
        self.text.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.sub = label(sub, "Faint")
        self.mark = QLabel("")
        self.mark.setFixedWidth(18)
        self.time = label(when, "Faint")
        lay.addWidget(ic)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.sub)
        lay.addWidget(self.mark)
        lay.addWidget(self.time)

    def set_result(self, ok: bool | None, sub: str = "") -> None:
        if ok is None:
            self.mark.setText("")
        else:
            self.mark.setText("✓" if ok else "✕")
            self.mark.setStyleSheet(f"color: {C['green'] if ok else C['red']}; font-weight: 700;")
        if sub:
            self.sub.setText(sub)

    def mousePressEvent(self, e):
        self.clicked.emit()


def elided(text: str, width: int, widget: QWidget) -> str:
    return widget.fontMetrics().elidedText(text, Qt.ElideMiddle, width)


def line_icon(kind: str, color: str = "#3d3b36", size: int = 18):
    """Consistent stroke icons for navigation: plus, search, graph, agents, key."""
    from PySide6.QtGui import QIcon, QPixmap
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.6)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    s = size
    if kind == "plus":
        p.drawRoundedRect(QRectF(2.5, 2.5, s - 5, s - 5), 4, 4)
        p.drawLine(s / 2, 6, s / 2, s - 6)
        p.drawLine(6, s / 2, s - 6, s / 2)
    elif kind == "shield":  # 帮我批准
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPainterPath

        path = QPainterPath(QPointF(s / 2, 2.5))
        path.lineTo(s - 3, s * 0.25)
        path.cubicTo(s - 3, s * 0.62, s * 0.72, s * 0.84, s / 2, s - 2.5)
        path.cubicTo(s * 0.28, s * 0.84, 3, s * 0.62, 3, s * 0.25)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(s * 0.36, s * 0.5, s * 0.47, s * 0.62)
        p.drawLine(s * 0.47, s * 0.62, s * 0.66, s * 0.4)
    elif kind == "chevron":  # a small down arrow (menus that open from a button)
        p.drawLine(s * 0.28, s * 0.4, s * 0.5, s * 0.62)
        p.drawLine(s * 0.5, s * 0.62, s * 0.72, s * 0.4)
    elif kind == "search":
        p.drawEllipse(QRectF(3, 3, s * 0.55, s * 0.55))
        p.drawLine(s * 0.62, s * 0.62, s - 3, s - 3)
    elif kind == "graph":
        pts = [(s * 0.22, s * 0.3), (s * 0.78, s * 0.22), (s * 0.5, s * 0.78), (s * 0.82, s * 0.7)]
        for a, b in ((0, 1), (0, 2), (1, 3), (2, 3)):
            p.drawLine(pts[a][0], pts[a][1], pts[b][0], pts[b][1])
        p.setBrush(QColor(color))
        for x, y in pts:
            p.drawEllipse(QRectF(x - 2.3, y - 2.3, 4.6, 4.6))
    elif kind == "agents":
        p.drawEllipse(QRectF(s * 0.18, s * 0.12, s * 0.3, s * 0.3))
        p.drawEllipse(QRectF(s * 0.56, s * 0.2, s * 0.26, s * 0.26))
        p.drawArc(QRectF(s * 0.06, s * 0.48, s * 0.54, s * 0.5), 0, 180 * 16)
        p.drawArc(QRectF(s * 0.5, s * 0.52, s * 0.42, s * 0.42), 0, 180 * 16)
    elif kind == "key":
        p.drawEllipse(QRectF(2.5, s * 0.3, s * 0.4, s * 0.4))
        p.drawLine(s * 0.42, s / 2, s - 2.5, s / 2)
        p.drawLine(s * 0.72, s / 2, s * 0.72, s * 0.72)
        p.drawLine(s * 0.88, s / 2, s * 0.88, s * 0.66)
    elif kind == "alert":  # triangle with an exclamation mark
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF

        p.drawPolygon(QPolygonF([QPointF(s / 2, 2.5), QPointF(s - 2.5, s - 3), QPointF(2.5, s - 3)]))
        p.drawLine(s / 2, s * 0.4, s / 2, s * 0.6)
        p.drawPoint(QPointF(s / 2, s * 0.74))
    elif kind == "gear":
        import math

        cx = cy = s / 2
        for i in range(8):  # teeth
            a = i * math.pi / 4
            p.drawLine(cx + math.cos(a) * s * 0.30, cy + math.sin(a) * s * 0.30,
                       cx + math.cos(a) * s * 0.44, cy + math.sin(a) * s * 0.44)
        p.drawEllipse(QRectF(cx - s * 0.30, cy - s * 0.30, s * 0.60, s * 0.60))
        p.drawEllipse(QRectF(cx - s * 0.12, cy - s * 0.12, s * 0.24, s * 0.24))
    elif kind == "book":
        p.drawRoundedRect(QRectF(3.5, 2.5, s - 7, s - 5), 2, 2)
        p.drawLine(s * 0.38, 2.5, s * 0.38, s - 2.5)
        p.drawLine(s * 0.52, s * 0.35, s * 0.72, s * 0.35)
    elif kind == "sliders":
        for x, k in ((0.3, 0.35), (0.5, 0.68), (0.72, 0.45)):
            p.drawLine(3, s * x, s - 3, s * x)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(s * k - 2.2, s * x - 2.2, 4.4, 4.4))
            p.setBrush(Qt.NoBrush)
    elif kind == "screen":
        p.drawRoundedRect(QRectF(2.5, 3, s - 5, s * 0.6), 2, 2)
        p.drawLine(s / 2, s * 0.6 + 3, s / 2, s - 3.5)
        p.drawLine(s * 0.32, s - 3, s * 0.68, s - 3)
    p.end()
    return QIcon(pm)


def hline() -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {C['border']};")
    return f


def hbox(*widgets, spacing: int = 8, margins=(0, 0, 0, 0), stretch_at: int | None = None) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for i, x in enumerate(widgets):
        if x is None:
            lay.addStretch(1)
        else:
            lay.addWidget(x, 1 if stretch_at == i else 0)
    return w


def vbox(*widgets, spacing: int = 8, margins=(0, 0, 0, 0)) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for x in widgets:
        if x is None:
            lay.addStretch(1)
        else:
            lay.addWidget(x)
    return w
