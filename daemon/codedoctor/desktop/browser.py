"""The built-in browser: Chromium (Qt WebEngine) as a page of the window, with tabs and an address bar.

The user browses in it, and Ray works in it: an agent's tool (agents/tools_browser.py) runs on the service's thread and
reaches the page through BrowserBridge, in a tab of its own that the user can watch. Sign-ins stay here, apart from
the user's Chrome (~/.codedoctor/browser). Chromium starts the first time the page is shown or used, not with the
window: this computer's graphics are weak.
"""

from __future__ import annotations

import concurrent.futures
import ipaddress
import json
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from PySide6.QtCore import QBuffer, QEasingCurve, QEvent, QIODevice, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtCore import QObject
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QWheelEvent
from PySide6.QtWidgets import (QAbstractButton, QApplication, QFileDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QLineEdit, QStackedWidget, QTabBar, QVBoxLayout, QWidget)

from codedoctor import interface
from codedoctor.desktop import chat_tools, icons, locale
from codedoctor.desktop.theme import C

BAR = "#ffffff"
LINE = "#e5e5e5"
LOAD_TIMEOUT_MS = 25000
SETTLE_MS = 1500  # after a click: time for what it started

# Marks the page's visible controls so that an agent can name them by number; returns what it reads.
READ_JS = r"""(() => {
  const seen = []; let n = 0;
  const visible = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  document.querySelectorAll('[data-lumen-ref]').forEach(e => e.removeAttribute('data-lumen-ref'));
  document.querySelectorAll('a[href],button,input,textarea,select,[role=button],[role=link],[role=tab],[contenteditable=true]')
    .forEach(e => { if (n >= 150 || !visible(e) || e.type === 'hidden') return;
      n += 1; e.setAttribute('data-lumen-ref', String(n));
      const label = (e.innerText || e.value || e.getAttribute('aria-label') || e.placeholder || e.title || e.name || '')
        .trim().replace(/\s+/g, ' ').slice(0, 80);
      seen.push({ref: n, tag: e.tagName.toLowerCase(), type: e.type || '', label, href: e.href || ''}); });
  return JSON.stringify({title: document.title, url: location.href, text: (document.body ? document.body.innerText : '').slice(0, 16000), elements: seen});
})()"""
DESCRIBE_JS = r"""(() => { const e = document.querySelector('[data-lumen-ref="%d"]'); if (!e) return 'null';
  return JSON.stringify({tag: e.tagName.toLowerCase(), type: e.type || '', name: e.name || '', id: e.id || '',
    autocomplete: e.getAttribute('autocomplete') || '', placeholder: e.placeholder || '',
    label: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim().slice(0, 80)}); })()"""
POINT_JS = r"""(() => { const e = document.elementFromPoint(%d, %d); if (!e) return 'null';
  const c = e.closest('a,button,input,textarea,select,[role=button],[role=link]') || e;
  return JSON.stringify({tag: c.tagName.toLowerCase(), type: c.type || '', name: c.name || '', id: c.id || '',
    autocomplete: c.getAttribute('autocomplete') || '', placeholder: c.placeholder || '',
    label: (c.tagName === 'CANVAS' || c === document.body || c === document.documentElement) ? '' : (c.innerText || c.value || c.getAttribute('aria-label') || '').trim().slice(0, 80)}); })()"""
ACTIVE_JS = r"""(() => { const c = document.activeElement; if (!c || c === document.body) return 'null';
  return JSON.stringify({tag: c.tagName.toLowerCase(), type: c.type || '', name: c.name || '', id: c.id || '',
    autocomplete: c.getAttribute('autocomplete') || '', placeholder: c.placeholder || '', label: ''}); })()"""
RECT_JS = r"""(() => { const e = document.querySelector('[data-lumen-ref="%d"]'); if (!e) return 'null';
  e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect();
  return JSON.stringify({x: r.left + r.width / 2, y: r.top + r.height / 2}); })()"""
CLICK_JS = r"""(() => { const e = document.querySelector('[data-lumen-ref="%d"]'); if (!e) return false;
  e.scrollIntoView({block: 'center'}); e.click(); return true; })()"""
TYPE_JS = r"""(() => { const e = document.querySelector('[data-lumen-ref="%d"]'); if (!e) return false;
  e.scrollIntoView({block: 'center'}); e.focus(); const text = %s;
  if (e.isContentEditable) { e.innerText = text; } else {
    const proto = e.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, text); }
  e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true}));
  if (%s) { if (e.form && e.form.requestSubmit) e.form.requestSubmit();
    else e.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true})); }
  return true; })()"""


_profile = None  # one for the whole program: another project's window opens in this process, with the same sign-ins


def profile():
    global _profile
    if _profile is None:
        from PySide6.QtWebEngineCore import QWebEngineProfile

        _profile = QWebEngineProfile("lumen", QApplication.instance())
        folder = interface.home() / "browser"
        folder.mkdir(parents=True, exist_ok=True)
        _profile.setPersistentStoragePath(str(folder / "data"))
        _profile.setCachePath(str(folder / "cache"))
        _profile.setHttpCacheMaximumSize(200 * 1024 * 1024)
    return _profile


def looks_like_address(text: str) -> bool:
    text = text.strip()
    head = text.split("/")[0]
    return "://" in text or text.startswith(("localhost", "127.0.0.1")) or (" " not in text and "." in head and not head.endswith("."))


ENGINES = {"google": "https://www.google.com/search?q=", "bing": "https://www.bing.com/search?q="}


def typed_url(text: str, engine: str = "google") -> str:
    """What the address bar goes to: an address as it is, anything else a search."""
    text = text.strip()
    if "://" in text or text.startswith("about:"):
        return text
    host = text.split("/")[0].split(":")[0]
    if host in ("localhost", "127.0.0.1"):  # this computer: a development server speaks plain http (Haiku check item 18)
        return "http://" + text
    if " " not in text and "." in text.split("/")[0] and not text.split("/")[0].endswith("."):
        return "https://" + text
    return ENGINES.get(engine, ENGINES["google"]) + quote_plus(text)


def local_host(url: str) -> bool:
    """On this computer or the local network, by the address alone (a look-up would stall the window)."""
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "") or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _one_colour(image) -> bool:
    """Nothing drawn yet: the same colour at a spread of points."""
    w, h = image.width(), image.height()
    if w < 10 or h < 10:
        return True
    seen = {image.pixel(w * i // 7, h * j // 7) for i in range(1, 7) for j in range(1, 7)}
    return len(seen) == 1


class _Tool(QAbstractButton):
    """A round toolbar button with a line icon."""

    def __init__(self, kind: str, tip: str, size: int = 32):
        super().__init__()
        self.kind = kind
        self.icon_size = 18.0
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
        if self.underMouse() and self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ececec"))
            p.drawRoundedRect(QRectF(self.rect()), 6, 6)
        s = self.icon_size
        at = (self.width() - s) / 2
        icons.paint(p, self.kind, QRectF(at, at, s, s), QColor(C["ink"] if self.isEnabled() else "#c4c4c4"), 1.6)
        p.end()


class _MiniCursor(QWidget):
    """Ray's little mouse inside the page: the same arrow as the takeover's, small and blue, with its name."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(70, 34)
        self.anim = QPropertyAnimation(self, b"pos", self)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.hide()

    def glide(self, tip: QPoint, ms: int = 260) -> None:
        self.anim.stop()
        self.show()
        self.raise_()
        self.anim.setDuration(ms)
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(tip)
        self.anim.start()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        arrow = QPainterPath(QPointF(1, 1))
        for x, y in ((1, 17), (5.4, 13), (8.3, 19.6), (11, 18.4), (8.2, 12), (14, 12)):
            arrow.lineTo(x, y)
        arrow.closeSubpath()
        p.setPen(QPen(QColor("white"), 1.4))
        p.setBrush(QColor("#2F6BFF"))
        p.drawPath(arrow)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0EA5E9"))
        tag = QRectF(16, 15, 36, 17)
        p.drawRoundedRect(tag, 8.5, 8.5)
        p.setPen(QColor("white"))
        f = p.font()
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(tag, Qt.AlignCenter, "Ray")
        p.end()


class _SearchIcon(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(22, 22)

    def paintEvent(self, _e):
        p = QPainter(self)
        icons.paint(p, "search", QRectF(1, 1, 20, 20), QColor("#9aa0a6"), 1.7)
        p.end()


class StartPage(QWidget):
    """A new tab: its name and one search box, nothing else. It searches the web right here; an address opens."""
    go = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("BrowserStart")
        self.setStyleSheet("#BrowserStart { background: white; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.addStretch(4)
        title = QLabel(locale.t("Lumen 浏览器"))  # an empty tab says what it is (the user, 2026-11-10: "啥都没有")
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {C['ink']}; background: transparent;")
        lay.addWidget(title)
        lay.addSpacing(22)
        self.box = QFrame()
        self.box.setObjectName("BrowserSearch")
        self.box.setFixedHeight(50)
        self.box.setMaximumWidth(600)
        self.box.setStyleSheet("#BrowserSearch { background: white; border: 1px solid #e4e1dc; border-radius: 25px; }"
                               "#BrowserSearch:hover { border-color: #d3cfc8; }")
        glow = QGraphicsDropShadowEffect(self.box)
        glow.setBlurRadius(22)
        glow.setOffset(0, 3)
        glow.setColor(QColor(40, 34, 24, 26))
        self.box.setGraphicsEffect(glow)
        bl = QHBoxLayout(self.box)
        bl.setContentsMargins(18, 0, 18, 0)
        bl.setSpacing(12)
        bl.addWidget(_SearchIcon())
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(locale.t("搜索，或者输入网址"))
        self.edit.setStyleSheet("QLineEdit { border: none; background: transparent; font-size: 16px; color: #202124; padding: 0; }")
        self.edit.returnPressed.connect(self._enter)
        bl.addWidget(self.edit, 1)
        self.box.setMinimumWidth(240)
        from PySide6.QtWidgets import QSizePolicy

        self.box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row = QHBoxLayout()  # as wide as the panel lets it be (up to 600), always in the middle
        row.addStretch(1)
        row.addWidget(self.box, 12)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(6)

    def _enter(self) -> None:
        text = self.edit.text().strip()
        if text:
            self.edit.clear()
            self.go.emit(text)


class RayPanel(QFrame):
    """What Ray is doing for the question asked here, and its answer, under the page."""
    open_chat = Signal(str)

    def __init__(self):
        super().__init__()
        from codedoctor.desktop.team_ui import MemberAvatar
        from codedoctor.desktop.widgets import Markdown

        self.setObjectName("RayPanel")
        self.setStyleSheet(f"#RayPanel {{ background: white; border-top: 1px solid {LINE}; }}")
        self.task = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 12, 10)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(MemberAvatar("ray", 24))
        self.state = QLabel("")
        self.state.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {C['ink']}; background: transparent;")
        head.addWidget(self.state, 1)
        self.chat_btn = _Tool("chat", locale.t("在聊天里查看"), 26)
        self.chat_btn.icon_size = 16.0
        self.chat_btn.clicked.connect(lambda: self.task and self.open_chat.emit(self.task))
        head.addWidget(self.chat_btn)
        close = _Tool("close", locale.t("关闭"), 26)
        close.icon_size = 12.0
        close.clicked.connect(self._close)
        head.addWidget(close)
        lay.addLayout(head)
        self.answer = Markdown("", size=14)
        self.answer.setMaximumHeight(210)
        self.answer.hide()
        lay.addWidget(self.answer)
        self.hide()

    changed = Signal()  # for the page, which draws this panel in the React window
    frameless = False

    def _close(self) -> None:
        self.task = None
        self.hide()
        self.changed.emit()

    def follow(self, task_id: str) -> None:
        self.task, self.shown = task_id, False
        self.state.setText(locale.t("Ray 正在查……"))
        self.answer_text = ""
        self.answer.hide()
        if not self.frameless:
            self.show()
        self.changed.emit()

    def as_json(self) -> dict:
        return {"task": self.task, "state": self.state.text(), "answer": getattr(self, "answer_text", ""), "done": bool(getattr(self, "shown", False))}

    def refresh(self, daemon) -> None:
        if not self.task or getattr(self, "shown", False):
            return
        row = daemon.task(self.task)
        if row is None or row["state"] != "finished":
            return
        from codedoctor.agents import orchestration as orch

        rep = orch.report_of(daemon.s, self.task) or {}
        self.shown = True
        self.state.setText(locale.t("Ray 查完了") if row["outcome"] == "done" else locale.t("Ray 没查完"))
        self.answer_text = str(rep.get("summary", ""))
        self.answer.set(self.answer_text)
        self.answer.show()
        self.changed.emit()


class BrowserPage(QWidget):
    """Tabs, an address bar and the pages. Everything of Chromium is made on first use."""
    own_entrance = True  # a fading parent would blank the web view
    agent_tab_opened = Signal()
    show_me = Signal()       # Ray needs to see the page: it must be on screen to be drawn
    to_chat = Signal(str)    # a page the user wants to talk about
    changed = Signal()       # tabs, address, title, star: the React window draws them (web_dock.browser_json)

    def __init__(self):
        super().__init__()
        self.setObjectName("BrowserPage")
        self.setStyleSheet(f"#BrowserPage {{ background: {BAR}; }}")
        self.profile = None
        self.engine = "google"  # the window sets it from the preference (app.py); google is also the start
        self.views: list = []
        self.agent_view = None
        self.local_ok: set[str] = set()  # addresses on this computer the user named for this work (tools_browser.py)
        self.closed_tabs: list[str] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        strip = self.strip = QFrame()  # only when there is more than one tab: a lone tab is a title nobody needs
        strip.setObjectName("BrowserStrip")
        strip.setVisible(False)
        strip.setFixedHeight(36)
        strip.setStyleSheet(f"#BrowserStrip {{ background: {C['sidebar']}; border-bottom: 1px solid {C['border']}; }}")
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(8, 0, 8, 0)
        sl.setSpacing(4)
        self.tabs = QTabBar()
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.setDocumentMode(True)
        self.tabs.setDrawBase(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setFixedHeight(32)
        self.tabs.setStyleSheet(
            f"QTabBar {{ background: transparent; }}"
            f"QTabBar::tab {{ background: transparent; color: {C['text2']}; height: 32px; padding: 0 6px 0 12px; margin-right: 3px; font-size: 13px;"
            " border: none; border-radius: 10px; max-width: 200px; min-width: 96px; }"
            f"QTabBar::tab:selected {{ background: white; color: {C['ink']}; font-weight: 600; border: none; }}"
            f"QTabBar::tab:hover:!selected {{ background: {C['sidebar_hover']}; }}"
            "QTabBar::close-button { subcontrol-position: right; }")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.currentChanged.connect(lambda _=0: self.strip.setVisible(self.tabs.count() > 1 and not self.frameless))
        self.tabs.tabMoved.connect(self._tab_moved)
        sl.addWidget(self.tabs, 0, Qt.AlignVCenter)
        sl.addStretch(1)
        lay.addWidget(strip)

        bar = self.bar = QFrame()
        bar.setObjectName("BrowserBar")
        bar.setStyleSheet(f"#BrowserBar {{ background: {BAR}; border-bottom: 1px solid {LINE}; }}")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 6, 12, 6)
        bl.setSpacing(4)
        self.back_btn = _Tool("arrow_left", locale.t("后退"))
        self.forward_btn = _Tool("arrow_right", locale.t("前进"))
        self.reload_btn = _Tool("reload", locale.t("刷新"))
        self.back_btn.clicked.connect(lambda: self._act("back"))
        self.forward_btn.clicked.connect(lambda: self._act("forward"))
        self.reload_btn.clicked.connect(lambda: self._act("reload"))
        for b in (self.back_btn, self.forward_btn, self.reload_btn):
            bl.addWidget(b)
        self.address = QLineEdit()
        self.address.setObjectName("BrowserAddress")
        self.address.setPlaceholderText("输入网址，或者要搜索的内容")
        self.address.setStyleSheet(
            f"#BrowserAddress {{ background: {C['sidebar']}; border: 1px solid transparent; border-radius: 15px; padding: 5px 14px;"
            f" font-size: 13px; color: {C['ink']}; }} #BrowserAddress:focus {{ background: white; border: 1px solid #c9c9c9; }}")
        self.address.returnPressed.connect(self._go)
        bl.addWidget(self.address, 1)
        self.ask_btn = _Tool("chat", locale.t("把这一页发给 Lumen"))
        self.ask_btn.clicked.connect(self._to_chat)
        bl.addWidget(self.ask_btn)
        self.star_btn = _Tool("star", locale.t("收藏这一页"))
        self.star_btn.clicked.connect(self._toggle_star)
        bl.addWidget(self.star_btn)
        self.marks_btn = _Tool("bookmarks", locale.t("收藏夹"))
        self.marks_btn.clicked.connect(self._show_marks)
        bl.addWidget(self.marks_btn)
        self.new_tab_btn = _Tool("plus", locale.t("新标签页"))
        self.new_tab_btn.clicked.connect(lambda: self.add_tab())
        bl.addWidget(self.new_tab_btn)
        lay.addWidget(bar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: white;")
        self.start = StartPage()
        self.start.go.connect(lambda text: self._open(typed_url(text, self.engine)))
        self.stack.addWidget(self.start)
        lay.addWidget(self.stack, 1)
        self.panel = RayPanel()
        self.panel.changed.connect(self.changed)
        lay.addWidget(self.panel)
        self.cursor_widget = _MiniCursor(self)
        self.frameless = False

    def go_frameless(self) -> None:
        """The React window draws the tabs, the address bar, the start page and Ray's panel: only the pages are left here."""
        self.frameless = self.panel.frameless = True
        for part in (self.strip, self.bar, self.panel):
            part.hide()

    # --- Chromium, on first use --------------------------------------------------------------------------------------

    def ensure(self) -> None:
        if self.profile is not None:
            return
        self.profile = profile()
        self.profile.downloadRequested.connect(self._download)
        if not self.views:
            self.add_tab()

    def shutdown(self) -> None:
        """The window closes: pages go before the profile they belong to, and nothing of this window stays attached."""
        if self.profile is None:
            return
        self.profile.downloadRequested.disconnect(self._download)
        for view in self.views:
            view.setPage(None)
            view._page.deleteLater()
            view.deleteLater()
        self.views.clear()
        self.agent_view = None
        self.profile = None

    def showEvent(self, e):
        super().showEvent(e)
        if self.views or self.profile is None:
            self.ensure()

    def _blank(self, view) -> bool:
        return view.url().isEmpty() or view.url().toString().startswith("about:")

    def _show_current(self) -> None:
        """A tab with no page shows the start page, without an address bar."""
        view = self.current()
        blank = view is None or self._blank(view)
        self.stack.setCurrentWidget(self.start if blank else view)
        self.bar.setVisible(not blank and not self.frameless)
        if blank and not self.frameless:
            self.start.edit.setFocus()
        self.changed.emit()

    def _open(self, url: str) -> None:
        view = self.current()
        if view is not None:
            view.setUrl(QUrl(url))

    def add_tab(self, url: str | None = None, *, agent: bool = False):
        self.ensure()
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView

        owner = self

        class Page(QWebEnginePage):
            console: list = []

            def acceptNavigationRequest(self, target, kind, main):  # noqa: N802 (Qt naming)
                if self is not getattr(owner.agent_view, "_page", None) or not local_host(target.toString()):
                    return True
                return urlparse(target.toString()).netloc in owner.local_ok

            def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802 (Qt naming)
                self.console = [*self.console[-199:], (getattr(level, "name", str(level)), message, line, source)]

        class View(QWebEngineView):
            def createWindow(self, _kind):  # noqa: N802 (Qt naming): target=_blank opens a tab beside it
                tab = owner.add_tab()
                if self is owner.agent_view:  # Haiku check item 17: Ray's page opened a tab - Ray reads and acts in that one
                    owner.tabs.setTabText(owner.views.index(self), locale.t("新标签页"))
                    owner.agent_view = tab
                    tab._page.setVisible(True)
                    owner.tabs.setTabText(owner.views.index(tab), locale.t("Ray 在用"))
                return tab

        view = View()
        view._page = Page(self.profile, view)
        view.setPage(view._page)
        view._page.renderProcessTerminated.connect(lambda st, code, v=view: self._crashed(v, st, code))
        view.loadStarted.connect(lambda v=view: setattr(v._page, "console", []))  # one page load's messages, not all of them
        view.titleChanged.connect(lambda t, v=view: self._titled(v, t))
        view.urlChanged.connect(lambda u, v=view: self._moved(v, u))
        view.loadStarted.connect(lambda v=view: (setattr(v, "_loading", True), self.changed.emit()))
        view.loadFinished.connect(lambda _ok, v=view: (setattr(v, "_loading", False), self.changed.emit()))
        self.views.append(view)
        self.stack.addWidget(view)
        at = self.tabs.addTab(locale.t("Ray 在用") if agent else locale.t("新标签页"))
        close = _Tool("close", locale.t("关闭标签页"), 20)
        close.icon_size = 10.0
        close.clicked.connect(lambda _=False, v=view: self.close_tab(self.views.index(v)))
        self.tabs.setTabButton(at, QTabBar.RightSide, close)
        self.tabs.setCurrentIndex(at)
        self.stack.setCurrentWidget(view)
        if url:
            view.setUrl(QUrl(url))
        self._show_current()
        return view

    def _crashed(self, view, status, code) -> None:
        view._page.console = [*view._page.console, ("Crash", f"the page's process ended: {getattr(status, 'name', status)} ({code})", 0, "")]

    def reopen_tab(self) -> None:
        """Ctrl+Shift+T: the tab closed last comes back."""
        if self.closed_tabs:
            self.add_tab(self.closed_tabs.pop())

    def close_tab(self, index: int) -> None:
        view = self.views.pop(index)
        if not self._blank(view) and view is not self.agent_view:
            self.closed_tabs = (self.closed_tabs + [view.url().toString()])[-20:]
        if view is self.agent_view:
            self.agent_view = None
        self.tabs.removeTab(index)
        self.stack.removeWidget(view)
        view.deleteLater()
        if not self.views:
            self.add_tab()
        self.changed.emit()

    def _tab_moved(self, frm: int, to: int) -> None:
        self.views.insert(to, self.views.pop(frm))

    def _tab_changed(self, index: int) -> None:
        if 0 <= index < len(self.views):
            self._show_current()
            self._moved(self.views[index], self.views[index].url())

    def current(self):
        i = self.tabs.currentIndex()
        return self.views[i] if 0 <= i < len(self.views) else None

    def _titled(self, view, title: str) -> None:
        if view in self.views and title and view is not self.agent_view:
            self.tabs.setTabText(self.views.index(view), title)
            self.tabs.setTabToolTip(self.views.index(view), title)
            self.changed.emit()

    def _moved(self, view, url: QUrl) -> None:
        if view is self.current():
            self._show_current()
            text = url.toString()
            self.address.setText("" if text.startswith("about:") else text)
            self._mark_star(text)
            self.back_btn.setEnabled(view.history().canGoBack())
            self.forward_btn.setEnabled(view.history().canGoForward())

    # --- bookmarks: a star by the address, and a list behind the ribbon --------------------------------------------------

    def _to_chat(self) -> None:
        """The page's title and address, and what is selected on it, into the message box."""
        view = self.current()
        if view is None or self._blank(view):
            return
        picked = view.page().selectedText().strip()
        self.to_chat.emit(f"{view.title()}\n{view.url().toString()}" + (f"\n\n> {picked}" if picked else ""))

    def _mark_star(self, url: str) -> None:
        self.star_btn.kind = "star_on" if chat_tools.is_bookmarked(url) else "star"
        self.star_btn.setToolTip(locale.t("取消收藏") if self.star_btn.kind == "star_on" else locale.t("收藏这一页"))
        self.star_btn.update()
        self.changed.emit()

    def as_json(self) -> dict:
        """What the React window draws around the pages."""
        view = self.current()
        url = view.url().toString() if view is not None else ""
        return {"tabs": [{"title": self.tabs.tabText(i), "url": v.url().toString(), "agent": v is self.agent_view}
                         for i, v in enumerate(self.views)],
                "current": self.tabs.currentIndex(), "url": "" if url.startswith("about:") else url,
                "blank": view is None or self._blank(view), "back": bool(view and view.history().canGoBack()),
                "forward": bool(view and view.history().canGoForward()), "starred": bool(url) and chat_tools.is_bookmarked(url),
                "loading": bool(getattr(view, "_loading", False)), "ray": self.panel.as_json()}

    def go(self, text: str) -> None:
        """The address bar or the start page: an address opens, anything else is searched."""
        self.ensure()
        if self.current() is None:
            self.add_tab()
        self._open(typed_url(text, self.engine))

    def select_tab(self, index: int) -> None:
        if 0 <= index < len(self.views):
            self.tabs.setCurrentIndex(index)

    def _toggle_star(self) -> None:
        view = self.current()
        if view is None or self._blank(view):
            return
        url = view.url().toString()
        chat_tools.toggle_bookmark(url, view.title())
        self._mark_star(url)

    def _show_marks(self) -> None:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        kept = chat_tools.bookmarks()
        for mark in kept[:40]:
            title = mark.get("title") or mark["url"]
            act = menu.addAction(title if len(title) <= 46 else title[:45] + "…")
            act.setToolTip(mark["url"])
            act.triggered.connect(lambda _=False, u=mark["url"]: self._open(u))
        if not kept:
            none = menu.addAction(locale.t("还没有收藏：点地址栏旁边的星星"))
            none.setEnabled(False)
        menu.exec(self.marks_btn.mapToGlobal(self.marks_btn.rect().bottomLeft()))

    def _go(self) -> None:
        text = self.address.text().strip()
        view = self.current()
        if text and view is not None:
            view.setUrl(QUrl(typed_url(text, self.engine)))
            view.setFocus()

    def _act(self, what: str) -> None:
        view = self.current()
        if view is not None:
            getattr(view, what)()

    def _download(self, item) -> None:
        """Only what the user saves: nothing is downloaded for an agent."""
        if self.agent_view is not None and item.page() is self.agent_view._page:
            item.cancel()
            return
        path, _ = QFileDialog.getSaveFileName(self, locale.t("保存文件"), item.suggestedFileName())
        if not path:
            item.cancel()
            return
        target = Path(path)
        item.setDownloadDirectory(str(target.parent))
        item.setDownloadFileName(target.name)
        item.accept()

    # --- an agent's tab (agents/tools_browser.py) -----------------------------------------------------------------------

    def _agent(self):
        if self.agent_view is None:
            self.agent_view = self.add_tab(agent=True)
            self.agent_view._page.setVisible(True)  # it goes on drawing when the user is on another page
            self.agent_tab_opened.emit()
        return self.agent_view

    def _front(self) -> None:
        """Ray's tab on screen: a page behind others is not drawn, so nothing could be seen or pointed at."""
        view = self._agent()
        if self.current() is not view:
            self.tabs.setCurrentIndex(self.views.index(view))
        if not self.isVisible():
            self.show_me.emit()

    def _cursor_at(self, x: float, y: float, ms: int = 260) -> None:
        view = self.agent_view
        at = view.mapTo(self, QPoint(int(x), int(y)))
        self.cursor_widget.glide(at, ms)

    def _target(self):
        view = self.agent_view
        return view.focusProxy() or view

    def _send_mouse(self, kind, x: float, y: float, button, buttons) -> None:
        target = self._target()
        pos = QPointF(x, y)
        QApplication.sendEvent(target, QMouseEvent(kind, pos, QPointF(target.mapToGlobal(QPoint(int(x), int(y)))), button, buttons, Qt.NoModifier))

    def agent_allow(self, netloc: str, done) -> None:
        self.local_ok.add(netloc)
        done(True)

    def agent_look(self, done) -> None:
        self._front()

        tries = {"left": 8}

        def grab():
            view = self.agent_view
            if view is None or not self.isVisible():
                done({"error": "the Lumen window is minimized, so the page is not drawn"})
                return
            self.cursor_widget.setVisible(False)
            pic = view.grab().toImage().scaled(view.width(), view.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.cursor_widget.setVisible(self.cursor_widget.anim.endValue() is not None)
            if tries["left"] and _one_colour(pic):  # just brought up: not drawn yet (a page takes seconds on this graphics chip)
                tries["left"] -= 1
                QTimer.singleShot(500, grab)
                return
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            pic.save(buf, "PNG")
            done({"png": bytes(buf.data()), "width": pic.width(), "height": pic.height(), "url": view.url().toString(),
                  "title": view.title()})
        QTimer.singleShot(700, grab)

    def agent_console(self, done) -> None:
        view = self.agent_view
        done([] if view is None else [list(x) for x in view._page.console])

    def agent_point(self, x: int, y: int, done) -> None:
        if self.agent_view is None:
            done(None)
            return

        def got(text):
            try:
                done(json.loads(text) if text else None)
            except ValueError:
                done(None)
        self._js(self.agent_view, POINT_JS % (int(x), int(y)), got)

    def agent_active(self, done) -> None:
        if self.agent_view is None:
            done(None)
            return

        def got(text):
            try:
                done(json.loads(text) if text else None)
            except ValueError:
                done(None)
        self._js(self.agent_view, ACTIVE_JS, got)

    def agent_mouse(self, action: str, x: float, y: float, to_x: float, to_y: float, seconds: float, delta: int, done) -> None:
        """A real mouse inside the page: what a canvas or a game hears, and the user sees the little cursor do it."""
        self._front()
        left, right = Qt.LeftButton, Qt.RightButton
        none = Qt.NoButton
        press, release, move = QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseMove
        self._cursor_at(x, y)
        view = self.agent_view
        view.setFocus()
        self._target().setFocus()

        def finish():
            QTimer.singleShot(300, lambda: done({"ok": True}))

        def act():
            self._send_mouse(move, x, y, none, none)
            if action in ("click", "double"):
                for n in range(2 if action == "double" else 1):
                    self._send_mouse(press, x, y, left, left)
                    self._send_mouse(release, x, y, left, none)
                finish()
            elif action == "right":
                self._send_mouse(press, x, y, right, right)
                self._send_mouse(release, x, y, right, none)
                finish()
            elif action == "move":
                finish()
            elif action == "hold":
                self._send_mouse(press, x, y, left, left)
                QTimer.singleShot(int(seconds * 1000), lambda: (self._send_mouse(release, x, y, left, none), finish()))
            elif action == "wheel":
                t = self._target()
                pos = QPointF(x, y)
                QApplication.sendEvent(t, QWheelEvent(pos, QPointF(t.mapToGlobal(QPoint(int(x), int(y)))), QPoint(0, 0), QPoint(0, int(delta)),
                                                      Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
                finish()
            elif action == "drag":
                self._send_mouse(press, x, y, left, left)
                steps = max(4, int(max(seconds, 0.3) * 30))
                self._cursor_at(to_x, to_y, int(max(seconds, 0.3) * 1000))
                state = {"n": 0}

                def step():
                    state["n"] += 1
                    k = state["n"] / steps
                    self._send_mouse(move, x + (to_x - x) * k, y + (to_y - y) * k, none, left)
                    if state["n"] < steps:
                        QTimer.singleShot(33, step)
                    else:
                        self._send_mouse(release, to_x, to_y, left, none)
                        finish()
                step()
            else:
                done({"error": f"unknown mouse action {action!r}"})
        QTimer.singleShot(280, act)

    def agent_keys(self, keys: list, text: str, seconds: float, done) -> None:
        """Real keys inside the page: letters for a text box, or keys held down for a game."""
        self._front()
        view = self.agent_view
        view.setFocus()
        target = self._target()
        target.setFocus()
        named = {"space": Qt.Key_Space, "enter": Qt.Key_Return, "esc": Qt.Key_Escape, "escape": Qt.Key_Escape, "tab": Qt.Key_Tab, "up": Qt.Key_Up,
                 "down": Qt.Key_Down, "left": Qt.Key_Left, "right": Qt.Key_Right, "shift": Qt.Key_Shift, "ctrl": Qt.Key_Control, "alt": Qt.Key_Alt,
                 "backspace": Qt.Key_Backspace, "delete": Qt.Key_Delete}
        codes = []
        for k in keys:
            low = str(k).lower()
            if low in named:
                codes.append((named[low], "\r" if low == "enter" else " " if low == "space" else ""))
            elif len(low) == 1 and low.isalnum():
                codes.append((Qt.Key(ord(low.upper())), low))
            else:
                done({"error": f"unknown key {k!r}"})
                return
        for ch in text:
            QApplication.sendEvent(target, QKeyEvent(QEvent.KeyPress, 0, Qt.NoModifier, ch))
            QApplication.sendEvent(target, QKeyEvent(QEvent.KeyRelease, 0, Qt.NoModifier, ch))

        def up():
            for code, ch in reversed(codes):
                QApplication.sendEvent(target, QKeyEvent(QEvent.KeyRelease, code, Qt.NoModifier, ch))
            QTimer.singleShot(300, lambda: done({"ok": True}))

        for code, ch in codes:
            QApplication.sendEvent(target, QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier, ch))
        QTimer.singleShot(int(seconds * 1000) if codes else 0, up)

    def _js(self, view, code: str, done) -> None:
        view.page().runJavaScript(code, 0, done)

    def _read(self, view, done) -> None:
        def got(text):
            try:
                done(json.loads(text) if text else {"error": "the page gave no text"})
            except ValueError:
                done({"error": "the page could not be read"})
        self._js(view, READ_JS, got)

    def _after_load(self, view, done, *, started: bool) -> None:
        """Call done once the page has loaded (timed out: it reads what is there)."""
        state = {"over": False}

        def finish(_ok=True):
            if state["over"]:
                return
            state["over"] = True
            try:
                view.loadFinished.disconnect(finish)
            except (RuntimeError, TypeError):
                pass
            self._read(view, done)

        view.loadFinished.connect(finish)
        QTimer.singleShot(LOAD_TIMEOUT_MS if started else SETTLE_MS, finish)

    def agent_open(self, url: str, done) -> None:
        view = self._agent()
        self._after_load(view, done, started=True)
        view.setUrl(QUrl(url))

    def agent_read(self, done) -> None:
        if self.agent_view is None:
            done({"error": "no page is open; use browser_open first"})
            return
        self._read(self.agent_view, done)

    def agent_back(self, done) -> None:
        if self.agent_view is None:
            done({"error": "no page is open; use browser_open first"})
            return
        self._after_load(self.agent_view, done, started=False)
        self.agent_view.back()

    def agent_describe(self, ref: int, done) -> None:
        if self.agent_view is None:
            done(None)
            return

        def got(text):
            try:
                done(json.loads(text) if text else None)
            except ValueError:
                done(None)
        self._js(self.agent_view, DESCRIBE_JS % int(ref), got)

    def agent_click(self, ref: int, done) -> None:
        view = self.agent_view

        def clicked(ok):
            if ok:
                self._after_load(view, done, started=False)
            else:
                done({"error": f"no element [{ref}] on this page; read the page again"})

        def placed(text):
            spot = json.loads(text) if text else None
            if spot and self.isVisible():
                self._cursor_at(spot["x"], spot["y"])
                QTimer.singleShot(280, lambda: self._js(view, CLICK_JS % int(ref), clicked))
            else:
                self._js(view, CLICK_JS % int(ref), clicked)
        self._js(view, RECT_JS % int(ref), placed)

    def agent_type(self, ref: int, text: str, submit: bool, done) -> None:
        view = self.agent_view

        def typed(ok):
            if ok:
                self._after_load(view, done, started=False)
            else:
                done({"error": f"no element [{ref}] on this page; read the page again"})

        def placed(where):
            spot = json.loads(where) if where else None
            if spot and self.isVisible():
                self._cursor_at(spot["x"], spot["y"])
            self._js(view, TYPE_JS % (int(ref), json.dumps(text, ensure_ascii=False), "true" if submit else "false"), typed)
        self._js(view, RECT_JS % int(ref), placed)


class BrowserBridge(QObject):
    """From the service's thread to the page's: call() returns a future the tool awaits."""
    _job = Signal(object)

    def __init__(self, page: BrowserPage):
        super().__init__()
        self.page = page
        self._job.connect(self._run, Qt.QueuedConnection)

    def _run(self, job) -> None:
        job()

    def call(self, op: str, *args) -> concurrent.futures.Future:
        future: concurrent.futures.Future = concurrent.futures.Future()

        def done(result):
            if not future.done():
                future.set_result(result)

        def job():
            try:
                getattr(self.page, f"agent_{op}")(*args, done)
            except Exception as e:  # reported to the agent; the window stays
                if not future.done():
                    future.set_exception(e)

        self._job.emit(job)
        return future
