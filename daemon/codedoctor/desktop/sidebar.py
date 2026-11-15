"""The left side of the window: a narrow icon rail - home, chats, browser, terminal, settings - and beside it the chat list:
新聊天, search, 置顶, then the projects as a tree with its branches drawn, each with its chats. A chat is a conversation (its first message and every one continuing it,
Daemon.chat_turns); clicking one opens its latest turn. Another folder's chat opens that folder on it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLineEdit, QMenu, QScrollArea, QVBoxLayout,
                               QWidget)

from codedoctor.desktop import chat_tools, icons, projects
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.theme import APP_NAME, C, FONT_FAMILY
from codedoctor.ui_text import task_status

INK = QColor(C["ink"])
INK2 = QColor(C["text2"])
FAINT = QColor(C["text3"])
ACCENT = QColor(C["ink"])     # the current icon
RUN_DOT = QColor(C["accent"])  # a chat working now
HOVER = QColor(C["sidebar_hover"])
CURRENT = QColor(C["sidebar_sel"])
BRANCH = QColor("#c6bfb2")
RUNNING = {"运行中", "排队中"}


def _font(px: float, weight: int = QFont.Normal) -> QFont:
    f = QFont(FONT_FAMILY)
    f.setPixelSize(int(px))
    f.setWeight(weight)
    return f


def _pins_path() -> Path:
    import os

    return Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor") / "pins.json"


def load_pins() -> dict[str, list[str]]:
    """{configuration path: [pinned chat ids]} (~/.codedoctor/pins.json; a convenience, never required)."""
    import json

    try:
        data = json.loads(_pins_path().read_text(encoding="utf-8"))
        return {k: [t for t in v if isinstance(t, str)] for k, v in data.items() if isinstance(v, list)}
    except (OSError, ValueError, AttributeError):
        return {}


def save_pins(pins: dict[str, list[str]]) -> None:
    import json

    try:
        _pins_path().parent.mkdir(parents=True, exist_ok=True)
        _pins_path().write_text(json.dumps(pins, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def other_project_tasks(config_path: str, limit: int = 8) -> list[dict]:
    """Recent chats of another folder, read-only from its database (its window may be open): each conversation once,
    by its first message, with the id of its latest turn ("open")."""
    import sqlite3

    from codedoctor import config as config_mod

    try:
        cfg = config_mod.load(config_path)
        db = cfg.data_dir / "codedoctor.sqlite3"
        if not db.exists():
            return []
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute("SELECT id, title, state, outcome, json_extract(body, '$.chat_of') AS chat_of FROM tasks "
                               "WHERE parent_task_id IS NULL ORDER BY created_at DESC LIMIT ?", (limit * 4,)).fetchall()
        finally:
            con.close()
        return chats([dict(r) for r in rows])[:limit]
    except Exception:  # an old or broken folder must not break the list
        return []


def chats(rows: list[dict]) -> list[dict]:
    """Root task rows (newest first) as conversations, newest first: {"id" (the chat), "title", "open" (its latest
    turn), "state", "outcome"} - the title is the first message's, the state the latest turn's."""
    out: dict[str, dict] = {}
    titles = {r["id"]: r["title"] for r in rows}
    for r in rows:
        if r.get("parent_task_id"):
            continue
        cid = r.get("chat_of") or r["id"]
        if cid not in out:
            out[cid] = {"id": cid, "title": titles.get(cid, r["title"]), "open": r["id"], "state": r["state"],
                        "outcome": r["outcome"]}
    return list(out.values())


# --- the rail -------------------------------------------------------------------------------------------------------

class RailButton(QAbstractButton):
    """A 40 px rounded square with a line icon; a soft white tile when hovered, a brighter one when current."""

    def __init__(self, kind: str, tip: str, checkable: bool = True):
        super().__init__()
        self.kind = kind
        self.setCheckable(checkable)
        self.setFixedSize(42, 42)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.alert = False

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self.isChecked() or self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(CURRENT if self.isChecked() else HOVER)
            p.drawRoundedRect(r, min(r.height() / 2, 14), min(r.height() / 2, 14))
        color = ACCENT if self.isChecked() else INK2
        size = min(20.0, r.width() - 7)
        icons.paint(p, self.kind, QRectF(r.center().x() - size / 2, r.center().y() - size / 2, size, size), color, 1.6)
        if self.alert:
            p.setPen(QPen(QColor("white"), 2))
            p.setBrush(QColor(C["red"]))
            p.drawEllipse(QPointF(self.width() - 10, 10), 5, 5)
        p.end()


class Rail(QFrame):
    """主页 · 聊天 · 浏览器 · 终端 · (space) · 设置. Lumen's own mark on top; nobody's portrait at the bottom: this is a program
    on this computer, there is no account to show. A red dot on 设置 when a service's key is missing."""
    navigate = Signal(str)
    toggle_list = Signal()

    def __init__(self):
        super().__init__()
        from codedoctor.desktop.liquid import MedicalMark

        self.setObjectName("Rail")
        self.setFixedWidth(64)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 14, 10, 14)
        lay.setSpacing(6)
        lay.addWidget(MedicalMark(38), 0, Qt.AlignHCenter)
        lay.addSpacing(10)
        self.home = RailButton("home", tr("rail_home"))
        self.chats = RailButton("chat", tr("rail_chats"))
        self.chats.setChecked(True)
        self.browser = RailButton("globe", tr("rail_browser"))
        self.terminal = RailButton("terminal", "终端")
        self.settings = RailButton("gear", tr("settings"))
        self.home.clicked.connect(lambda: self.navigate.emit("home"))
        self.chats.clicked.connect(self.toggle_list.emit)
        self.browser.clicked.connect(lambda: self.navigate.emit("browser"))
        self.terminal.clicked.connect(lambda: self.navigate.emit("terminal"))
        self.settings.clicked.connect(lambda: self.navigate.emit("settings"))
        for b in (self.home, self.chats, self.browser, self.terminal):
            lay.addWidget(b, 0, Qt.AlignHCenter)
        lay.addStretch(1)
        lay.addWidget(self.settings, 0, Qt.AlignHCenter)


# --- the chat list ----------------------------------------------------------------------------------------------------

class Row(QAbstractButton):
    """One line of the list: an optional icon, the text, a status dot while a chat runs; hover and current tiles."""

    def __init__(self, text: str, kind: str | None = None, indent: int = 0, bold: bool = False, height: int = 34):
        super().__init__()
        self.text_, self.kind, self.indent, self.bold = text, kind, indent, bold
        self.running = False
        self.current = False
        self.extra: QAbstractButton | None = None  # a small button shown on hover (+ for a folder)
        self.branch: str | None = None  # in a tree: "mid" (more below it) or "last"
        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(text)

    def enterEvent(self, e):
        self.update()
        if self.extra:
            self.extra.show()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        if self.extra:
            self.extra.hide()
        super().leaveEvent(e)

    def resizeEvent(self, e):
        if self.extra:
            self.extra.move(self.width() - self.extra.width() - 6, (self.height() - self.extra.height()) // 2)
        super().resizeEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2 + (30 if self.branch else 0), 1, -2, -1)
        if self.current or self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(CURRENT if self.current else HOVER)
            p.drawRoundedRect(r, 11, 11)
        x = 12 + self.indent
        if self.branch:  # the tree's branch: down from the project, round into this chat
            p.setPen(QPen(BRANCH, 1.2))
            p.setBrush(Qt.NoBrush)
            trunk, mid = 21.0, self.height() / 2
            path = QPainterPath(QPointF(trunk, -2))
            if self.branch == "mid":
                path.lineTo(trunk, self.height() + 2)
                path.moveTo(trunk, mid)
                path.lineTo(trunk + 10, mid)
            else:
                path.lineTo(trunk, mid - 7)
                path.quadTo(trunk, mid, trunk + 7, mid)
                path.lineTo(trunk + 10, mid)
            p.drawPath(path)
        if self.kind:
            icons.paint(p, self.kind, QRectF(x, (self.height() - 18) / 2, 18, 18), INK2 if not self.current else INK, 1.5)
            x += 26
        right = 10 + (24 if self.extra else 0) + (14 if self.running else 0)
        p.setPen(INK if self.current else QColor(C["text"]))
        p.setFont(_font(13.5 if self.indent else 14, QFont.Medium if self.bold or self.current else QFont.Normal))
        text = p.fontMetrics().elidedText(self.text_, Qt.ElideRight, int(self.width() - x - right))
        p.drawText(QRectF(x, 0, self.width() - x - right, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
        if self.running:  # a soft blue dot: this chat is working now
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(47, 107, 255, 50))
            p.drawEllipse(QPointF(self.width() - 16, self.height() / 2), 6, 6)
            p.setBrush(RUN_DOT)
            p.drawEllipse(QPointF(self.width() - 16, self.height() / 2), 3, 3)
        p.end()


class FolderRow(Row):
    """A project: ▸/▾, its icon and name; + (new chat in it) on hover."""
    new_chat = Signal()

    def __init__(self, name: str, root: str, expanded: bool, current: bool):
        super().__init__(name, None, 0, False, 34)
        self.expanded, self.is_current = expanded, current
        self.setToolTip(root)
        plus = RailButton("plus", tr("new_chat_here"), checkable=False)
        plus.setFixedSize(24, 24)
        plus.setParent(self)
        plus.hide()
        plus.clicked.connect(self.new_chat.emit)
        self.extra = plus

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(HOVER)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 1, -2, -1), 9, 9)
        icons.paint(p, "chevron_down" if self.expanded else "chevron_right", QRectF(13, (self.height() - 16) / 2, 16, 16), INK2, 1.6)
        p.setPen(QColor(C["ink"] if self.is_current else C["text"]))
        p.setFont(_font(14, QFont.DemiBold if self.is_current else QFont.Medium))
        text = p.fontMetrics().elidedText(self.text_, Qt.ElideRight, self.width() - 66)
        p.drawText(QRectF(34, 0, self.width() - 66, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
        p.end()


class Sidebar(QFrame):
    """The rail and the chat list (the list can be hidden from the rail's 聊天 button)."""
    navigate = Signal(str)        # "home", "settings" or a settings page
    open_task = Signal(str)
    open_project_task = Signal(str, str)  # (configuration path, task id): another folder, on that chat
    switch_project = Signal(str)  # configuration path of another folder
    open_folder = Signal()  # 打开文件夹: any folder opens with the AIs chosen the first time
    export_chat = Signal(str)  # a chat, to be saved as a file
    renamed = Signal(str)      # a chat got a new name

    def __init__(self, project: str, root: str, key_problems: list[str], config_path: str | None = None):
        super().__init__()
        self.setObjectName("Sidebar")
        self.config_path = config_path
        self.project, self.root = project, root
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.rail = Rail()
        self.rail.navigate.connect(self._nav)
        self.rail.toggle_list.connect(self._toggle_list)
        self.rail.setVisible(False)  # only when the list is put away: two columns of navigation looked like a control room
        outer.addWidget(self.rail)

        self.panel = QFrame()
        self.panel.setObjectName("ChatPanel")
        self.panel.setFixedWidth(264)
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(2)
        title = QHBoxLayout()  # very small, top left, as the user asked: they open the panel on the right and are all that is needed for it
        title.setContentsMargins(2, 0, 0, 8)
        title.setSpacing(2)

        def small(kind: str, tip: str, checkable: bool = True) -> RailButton:
            b = RailButton(kind, tip, checkable=checkable)
            b.setFixedSize(28, 28)
            return b

        self.mini_browser = small("globe", tr("rail_browser"))
        self.mini_terminal = small("terminal", "终端")
        self.mini_browser.clicked.connect(lambda: self._nav_dock("browser"))
        self.mini_terminal.clicked.connect(lambda: self._nav_dock("terminal"))
        title.addWidget(self.mini_browser)
        title.addWidget(self.mini_terminal)
        title.addStretch(1)
        self.search_btn = small("search", tr("search_chats"))
        self.search_btn.toggled.connect(self._toggle_search)
        title.addWidget(self.search_btn)
        self.hide_btn = small("sidebar", tr("rail_chats"), checkable=False)
        self.hide_btn.clicked.connect(self._toggle_list)
        title.addWidget(self.hide_btn)
        pl.addLayout(title)
        self.new_btn = Row(tr("new_chat"), "compose", height=36)
        self.new_btn.clicked.connect(lambda: self._nav("home"))
        pl.addWidget(self.new_btn)
        self.plugins_btn = Row(tr("plugins"), "grid", height=36)
        self.plugins_btn.clicked.connect(lambda: self._nav("plugins"))
        pl.addWidget(self.plugins_btn)
        self.search = QLineEdit()
        self.search.setObjectName("ChatSearch")
        self.search.setPlaceholderText(tr("search_chats"))
        self.search.textChanged.connect(lambda _: self._rebuild())
        self.search.setVisible(False)
        pl.addWidget(self.search)
        pl.addSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        self.col = QVBoxLayout(inner)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(1)
        scroll.setWidget(inner)
        pl.addWidget(scroll, 1)
        self.settings_btn = Row(tr("settings"), "gear", height=36)
        self.settings_btn.clicked.connect(lambda: self._nav("settings"))
        pl.addWidget(self.settings_btn)
        outer.addWidget(self.panel)

        self.pins = load_pins().get(self.config_path or "", [])
        self.names = chat_tools.names_of(self.config_path or "")
        self._chats: list[dict] = []
        self._selected: str | None = None
        self._sig = None
        self._open_folders: set[str] = {self.config_path or ""}
        self._others: dict[str, list[dict]] = {}  # another folder's chats, read when it is first opened
        self.set_key_problems(key_problems)
        self._rebuild()

    # --- painting and small parts -------------------------------------------------------------------

    def _paint_brand(self, w: QWidget) -> None:
        p = QPainter(w)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(INK)
        p.setFont(_font(19, QFont.DemiBold))
        p.drawText(QRectF(0, 0, w.width(), w.height()), Qt.AlignVCenter | Qt.AlignLeft, APP_NAME)
        p.end()

    @staticmethod
    def _heading(text: str) -> QWidget:
        w = QWidget()
        w.setFixedHeight(30)

        def paint(_e, w=w):
            p = QPainter(w)
            p.setPen(FAINT)
            p.setFont(_font(13))
            p.drawText(QRectF(12, 6, w.width() - 12, 24), Qt.AlignVCenter | Qt.AlignLeft, text)
            p.end()
        w.paintEvent = paint
        return w

    def set_key_problems(self, missing: list[str]) -> None:
        """Services an agent uses that have no key now: a red dot on 设置, the names in its tip."""
        self.key_problems = list(missing)
        self.rail.settings.alert = bool(missing)
        self.rail.settings.setToolTip(tr("keys_missing", names="、".join(missing)) if missing else tr("settings"))
        self.rail.settings.update()
        self.settings_btn.running = bool(missing)
        self.settings_btn.setToolTip(self.rail.settings.toolTip())
        self.settings_btn.update()

    def set_dock(self, key: str | None) -> None:
        """Which of the right panel's pages is open."""
        self.rail.browser.setChecked(key == "browser")
        self.rail.terminal.setChecked(key == "terminal")
        self.mini_browser.setChecked(key == "browser")
        self.mini_terminal.setChecked(key == "terminal")

    def _nav_dock(self, key: str) -> None:
        self.navigate.emit(key)

    def _toggle_list(self) -> None:
        self.panel.setVisible(self.panel.isHidden())
        self.rail.setVisible(self.panel.isHidden())
        self.rail.chats.setChecked(not self.panel.isHidden())

    def set_focus(self, on: bool) -> None:
        """A page with a list of its own (settings): the chat list makes room, and comes back as it was after."""
        if on == getattr(self, "_focused", False):
            return
        self._focused = on
        if on:
            self._list_was = not self.panel.isHidden()
            self.panel.hide()
        else:
            self.panel.setVisible(getattr(self, "_list_was", True))
        self.rail.setVisible(self.panel.isHidden() and not on)
        self.rail.chats.setChecked(not self.panel.isHidden())

    def _toggle_search(self, on: bool) -> None:
        self.search.setVisible(on)
        if on:
            self.search.setFocus()
        else:
            self.search.clear()

    def _nav(self, key: str) -> None:
        self._selected = None
        self._rebuild()
        self.navigate.emit(key)

    def check(self, key: str | None) -> None:
        self.rail.home.setChecked(key == "home")
        self.rail.settings.setChecked(key not in (None, "home", "plugins"))
        self.new_btn.current = key == "home"
        self.new_btn.update()
        self.plugins_btn.current = key == "plugins"
        self.plugins_btn.update()

    # --- the list -------------------------------------------------------------------------------------

    def set_tasks(self, rows: list[dict], selected: str | None) -> None:
        listed = chats(rows)
        sig = ([(c["id"], c["title"], c["open"], c["state"], c["outcome"]) for c in listed],
               next((c["id"] for c in listed if selected in (c["id"], c["open"]) or
                     any(r["id"] == selected and (r.get("chat_of") or r["id"]) == c["id"] for r in rows)), None))
        if sig == self._sig:
            return
        self._sig = sig
        self._chats, self._selected = listed, sig[1]
        self._rebuild()

    def listed(self) -> list[dict]:
        """This project's chats as the list shows them: by the name given to them, without those put away."""
        return [{**c, "title": self.names["titles"].get(c["id"], c["title"])} for c in self._chats if c["id"] not in self.names["hidden"]]

    def _chat_row(self, chat: dict, indent: int, config: str | None) -> Row:
        row = Row(chat["title"], None, indent)
        row.running = task_status(chat) in RUNNING
        row.current = config is None and chat["id"] == self._selected
        if config is None:
            row.clicked.connect(lambda _=False, t=chat["open"]: self.open_task.emit(t))
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            row.customContextMenuRequested.connect(lambda pos, c=chat["id"], r=row: self._chat_menu(c, r, pos))
        else:
            row.clicked.connect(lambda _=False, c=config, t=chat["open"]: self.open_project_task.emit(c, t))
        return row

    def _rebuild(self) -> None:
        while self.col.count():
            item = self.col.takeAt(0)
            w = item.widget()
            if w is not None:  # off the screen now, not when Qt gets round to deleting it
                w.hide()
                w.setParent(None)
                w.deleteLater()
        needle = self.search.text().strip().lower()
        match = (lambda c: needle in c["title"].lower()) if needle else (lambda c: True)

        shown_here = self.listed()
        pinned = [c for c in shown_here if c["id"] in self.pins and match(c)]
        if pinned:
            self.col.addWidget(self._heading(tr("pinned")))
            for c in pinned:
                row = self._chat_row(c, 0, None)
                row.kind = "pin"
                self.col.addWidget(row)
            self.col.addSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 4, 0)
        head.addWidget(self._heading(tr("folders")), 1)
        add = RailButton("plus", tr("open_folder").rstrip("…."), checkable=False)
        add.setFixedSize(26, 26)
        add.clicked.connect(self.open_folder.emit)
        head.addWidget(add)
        holder = QWidget()
        holder.setLayout(head)
        self.col.addWidget(holder)

        here_item = next((p for p in projects.load() if self.config_path and projects._same(p["config"], self.config_path)), {})
        folders = [{"name": self.project, "label": here_item.get("label"), "config": self.config_path or "", "root": self.root}]
        folders += [p for p in projects.load() if p["config"] and Path(p["config"]).exists()
                    and not (self.config_path and projects._same(p["config"], self.config_path))]
        for f in folders[:20]:
            here = f["config"] == (self.config_path or "")
            open_ = f["config"] in self._open_folders or bool(needle)
            row = FolderRow(f.get("label") or f["name"], f.get("root") or "", open_, here)
            row.clicked.connect(lambda _=False, c=f["config"]: self._toggle_folder(c))
            row.new_chat.connect((lambda: self._nav("home")) if here else
                                 (lambda c=f["config"]: self.switch_project.emit(c)))
            self.col.addWidget(row)
            if not open_:
                continue
            if here:
                items = [c for c in shown_here if c["id"] not in self.pins and match(c)]
            else:
                if f["config"] not in self._others:
                    self._others[f["config"]] = other_project_tasks(f["config"])
                items = [c for c in self._others[f["config"]] if match(c)]
            shown = items[:60]
            for i, c in enumerate(shown):
                row = self._chat_row(c, 30, None if here else f["config"])
                row.branch = "last" if i == len(shown) - 1 else "mid"
                self.col.addWidget(row)
            if not items:
                empty = self._heading(tr("no_chats") if not needle else tr("no_match"))
                empty.setContentsMargins(26, 0, 0, 0)
                self.col.addWidget(empty)
        self.col.addStretch(1)

    def _toggle_folder(self, config: str) -> None:
        self._open_folders ^= {config}
        self._rebuild()

    def _chat_menu(self, chat_id: str, row: Row, pos) -> None:
        menu = QMenu(self)
        pinned = chat_id in self.pins
        menu.addAction(icons.icon("pin", "#3b4250", 16), tr("unpin") if pinned else tr("pin")).triggered.connect(
            lambda: self._toggle_pin(chat_id))
        menu.addAction("重命名…").triggered.connect(lambda: self._rename(chat_id))
        menu.addAction("导出为 Markdown…").triggered.connect(lambda: self.export_chat.emit(chat_id))
        menu.addSeparator()
        menu.addAction("从列表里收起").triggered.connect(lambda: self._put_away(chat_id))
        menu.exec(row.mapToGlobal(pos))

    def _rename(self, chat_id: str) -> None:
        from codedoctor.desktop.dialogs import ask_text

        now = next((c["title"] for c in self.listed() if c["id"] == chat_id), "")
        name = ask_text(self.window(), "给这个聊天起个名字", "留空就用回第一句话。", now)
        if name is not None:
            chat_tools.rename(self.config_path or "", chat_id, name)
            self.reload_names()
            self.renamed.emit(chat_id)

    def _put_away(self, chat_id: str) -> None:
        chat_tools.hide(self.config_path or "", chat_id)
        self.reload_names()

    def reload_names(self) -> None:
        self.names = chat_tools.names_of(self.config_path or "")
        self._rebuild()

    def _toggle_pin(self, chat_id: str) -> None:
        self.pins = [t for t in self.pins if t != chat_id] if chat_id in self.pins else [chat_id] + self.pins
        all_pins = load_pins()
        all_pins[self.config_path or ""] = self.pins[:30]
        save_pins(all_pins)
        self._rebuild()

    # kept for callers of the old list
    @property
    def nav(self) -> dict:
        return {"home": self.rail.home, "settings": self.rail.settings}

