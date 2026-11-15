"""Lumen desktop app (Qt). The service runs inside this process; closing the window stops it.

    codedoctor-desktop --config local/codedoctor.toml
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QSplitter, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget

from codedoctor import config as config_mod
from codedoctor import secrets
from codedoctor.backend import Backend
from codedoctor.desktop.composer import HomePage
from codedoctor.desktop.computer_view import ComputerBar
from codedoctor.desktop.dialogs import notice
from codedoctor.desktop import chat_tools, locale, motion, palette, projects
from codedoctor.desktop import prefs as ui_prefs
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.liquid import Atmosphere
from codedoctor.desktop.settings_view import ModelsPage
from codedoctor.desktop.sidebar import Sidebar
from codedoctor.desktop.task_view import TaskView
from codedoctor.desktop.theme import C, FONT_FAMILY, configure, qss

REFRESH_MS = 800


def mark_pixmap(size: int) -> QPixmap:
    """Lumen itself as a picture: window, taskbar, shortcut."""
    from codedoctor.desktop.team_ui import art

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    image = art("lumen")
    if image is not None:
        p = QPainter(pm)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, size, size), image)
        p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(mark_pixmap(size))
    return icon


class Pages(motion.FadeStack):
    """FadeStack animates setCurrentIndex; this window switches pages by widget, so route that through it too."""

    def setCurrentWidget(self, widget) -> None:  # noqa: N802 (Qt naming)
        self.setCurrentIndex(self.indexOf(widget))


class MainWindow(QMainWindow):
    switch_to = Signal(str, object)  # (configuration, task id or None): open that folder in this process when closed

    def __init__(self, cfg, backend: Backend, welcome: bool = False):
        """welcome: play the opening greeting first (the desktop entry point passes the user's preference;
        tests and scripts get the working window at once)."""
        super().__init__()
        self.cfg, self.b, self.d = cfg, backend, backend.daemon
        self.setWindowTitle(f"Lumen — {cfg.name}")
        self.setWindowIcon(app_icon())
        roles = {a.role: a.id for a in reversed(list(cfg.agents.values())) if not a.team}
        self.modes = []
        if "lumen" in cfg.agents and cfg.agents["lumen"].team:  # the Lumen team: the user talks to Lumen (team.py)
            self.modes.append(("team", tr("mode_team"), "lumen"))
        if "general" in roles:
            self.modes.append(("single", tr("mode_single"), roles["general"]))
        if cfg.cluster.mode == "dual" and "worker" in roles:  # 双人互检: the worker takes the task, its guardian re-checks
            self.modes.append(("dual", tr("mode_dual"), roles["worker"]))
        elif "head_dispatch" in roles and cfg.cluster.mode != "basic":  # basic: the user chose single agent only (ADR 0014)
            title = tr("mode_small") if cfg.cluster.mode == "small" else tr("mode_cluster")
            self.modes.append(("cluster", title, roles["head_dispatch"]))
        if "general" not in roles and "worker" in roles:  # a team configured: one of its workers answers on its own
            self.modes.append(("single", tr("mode_single"), roles["worker"]))
        if not self.modes:
            first = next(iter(cfg.agents.values()))
            self.modes.append(("single", first.id, first.id))
        # The window is a chat (2026-11-03, the user's choice): one AI answers - no cluster unless nothing else exists.
        self.modes.sort(key=lambda m: ("team", "single", "dual", "cluster").index(m[0]))
        missing = self._missing_keys()
        warnings = self._data_class_warnings() + self._key_warnings(missing)  # only what stops work (no git hint)
        self._keys_at = time.monotonic()
        self._restart = False
        self._next_config: str | None = None  # another project to open when this window closes
        self._next_task: str | None = None    # and the investigation to show there (clicked in the sidebar)
        if cfg.source:
            projects.register(cfg.name, str(cfg.source), str(cfg.root))

        # The window is a wallpaper (ported from ChatGPT's studio build); everything else is glass laid over it.
        self.ui = ui_prefs.load()
        motion.set_reduced(self.ui["reduced_motion"])
        self.backdrop = Atmosphere()
        self.backdrop.set_wallpaper(self.ui["wallpaper"])
        bl = QVBoxLayout(self.backdrop)
        bl.setContentsMargins(0, 0, 0, 0)
        self.root = QStackedWidget()
        bl.addWidget(self.root)
        central = QWidget()
        self.main_ui = central
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        from codedoctor.desktop import web_chat

        # The window is one page drawn in React (web_chat.py): the sidebar, the new chat, the conversation. What stays Qt -
        # the pages not drawn there yet and an @ tool's window - lies over it where it leaves room. Without the built page
        # (or with LUMEN_WEB_CHAT=0) the Qt window as before.
        use_web = web_chat.enabled(self.ui)
        self.web_draft: str | None = None
        self.sidebar = Sidebar(cfg.name, str(cfg.root), missing, str(cfg.source) if cfg.source else None)
        if not use_web:
            lay.addWidget(self.sidebar)
        else:  # kept for its lists (pins, names, the selection), never shown: the page draws the sidebar
            self.sidebar.setParent(central)
            self.sidebar.hide()
        right = QWidget()
        right.setMinimumWidth(560 if use_web else 380)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.computer_bar = ComputerBar(self.d, right)  # stop button and approvals, above every page (ADR 0012)
        rl.addWidget(self.computer_bar)
        self.pages = Pages()  # pages arrive with the same short rise as the greeting
        from codedoctor.desktop.tool_view import ToolView

        self.tool_view = ToolView()  # an @ tool's own window above the chat (tool_view.py)
        if getattr(self.d.s, "computer", None) is not None:  # the tool on the right is the AI's own to work in (gate.sandbox)
            self.d.s.computer.sandbox = self.tool_view.sandbox_windows
        self.tool_view.setVisible(False)
        self.web = web_chat.WebChat(self) if use_web else None
        if self.web is not None:  # an approval or a question for the user is pushed to the page the moment it is made
            self.d.s.asks_changed = self.web.bridge.asks_poke.emit
            self.computer_bar.quiet = True  # the page draws them (the long button, the question panel)
        if self.web is not None:
            self.main_split = None
            rl.addWidget(self.web, 1)
        else:
            self.main_split = QSplitter(Qt.Vertical)
            self.main_split.setHandleWidth(1)
            self.main_split.setChildrenCollapsible(False)
            self.main_split.addWidget(self.tool_view)
            self.main_split.addWidget(self.pages)
            self.main_split.setStretchFactor(0, 3)
            self.main_split.setStretchFactor(1, 2)
            rl.addWidget(self.main_split, 1)
        self.body_split = QSplitter(Qt.Horizontal)  # the chat, and beside it the browser and the terminal (dock.py)
        self.body_split.setHandleWidth(1)
        self.body_split.setChildrenCollapsible(False)
        self.body_split.addWidget(right)
        lay.addWidget(self.body_split, 1)
        self.root.addWidget(central)
        self.welcome_screen = None
        if welcome:
            self._show_welcome()
        self.setCentralWidget(self.backdrop)

        self.home = HomePage(cfg.name, str(cfg.root), self.modes, warnings, str(cfg.source) if cfg.source else None)
        self.home.new_chat.connect(lambda: self.navigate("home"))
        self.task_view = TaskView(self.d, self.modes)
        from codedoctor.desktop.browser import BrowserBridge, BrowserPage
        from codedoctor.desktop.dock import RightDock
        from codedoctor.desktop import widgets

        self.browser = BrowserPage()  # Chromium itself starts on first use
        self.browser.engine = self.ui["search_engine"]
        if self.web is not None:  # the panel on the right is the page's own; the browser's pages lie over its room
            from codedoctor.desktop.web_dock import WebDock

            self.dock = WebDock(self.web, self.browser, str(cfg.root))
            self.web.adopt(self.pages, self.tool_view, self.browser)
        else:
            self.dock = RightDock(self.browser, str(cfg.root))
            self.body_split.addWidget(self.dock)
            self.body_split.setStretchFactor(0, 3)
            self.body_split.setStretchFactor(1, 2)
        self.dock.closed.connect(lambda: (self.sidebar.set_dock(None), self.web and self.web.push_side()))
        self.dock.to_chat.connect(self.put_in_box)
        self.browser.to_chat.connect(self.put_in_box)
        self.d.s.browser = BrowserBridge(self.browser)  # Ray works in it (agents/tools_browser.py)
        self.browser.show_me.connect(lambda: self.open_dock("browser"))
        self.browser.panel.open_chat.connect(self.open_task)
        widgets.link_handler = self.open_link
        QShortcut(QKeySequence("Ctrl+Shift+N"), self).activated.connect(new_window)
        for keys, action in (("Ctrl+K", self.open_palette), ("Ctrl+N", lambda: self.navigate("home")), ("Ctrl+B", self.toggle_sidebar),
                             ("Ctrl+J", lambda: self.navigate("terminal")), ("Ctrl+Shift+B", lambda: self.navigate("browser")),
                             ("Ctrl+,", lambda: self.navigate("settings")), ("Ctrl+F", self.find_in_chat), ("F1", lambda: self.navigate("book")),
                             ("Ctrl+/", self.show_keys), ("Ctrl+=", lambda: self.step_text(1)), ("Ctrl+-", lambda: self.step_text(-1)),
                             ("Ctrl+Shift+T", lambda: (self.browser.reopen_tab(), self.open_dock("browser")))):
            QShortcut(QKeySequence(keys), self).activated.connect(action)
        self.tray: QSystemTrayIcon | None = None  # made the first time there is something to tell
        self._done_task: str | None = None
        self.models_page = ModelsPage(cfg)
        self.models_page.restart_requested.connect(self.restart)
        self.models_page.keys_changed.connect(self.check_keys)
        self.models_page.appearance_changed.connect(self.apply_appearance)
        self.models_page.replay_welcome.connect(self._show_welcome)
        self.models_page.open_page.connect(self.navigate)
        for w in (self.home, self.task_view):
            self.pages.addWidget(w)

        self.home.composer.send.connect(lambda t, a: self.submit(t, a, self.home.composer.options()))
        self.task_view.follow_up.connect(lambda t, a: self.submit(  # the same chat: earlier turns go with it
            t, a, {**self.task_view.composer.options(), "chat_of": self.task_view.chat_id}))
        self.task_view.composer.stop.connect(lambda: self.control("cancel_task", confirm=False))
        for composer in (self.home.composer, self.task_view.composer):
            composer.team.connect(lambda: self.navigate("agent_models"))
            composer.set_models(self._model_choices())
            composer.fetch_models = self._fetch_models
            if self.web is not None:  # the model the user chose last, or none: never one chosen for them (the user, 2026-11-12)
                self.apply_pick(composer, *self.remembered_pick())
            else:
                composer._set_model(self._lead_choice(), "")  # what runs is what is shown: there is no 默认
        self.task_view.cancel_btn.clicked.connect(lambda: self.control("cancel_task"))
        self.home.composer.mentions_changed.connect(lambda _=None: self.follow_tool())
        from codedoctor.desktop import tool_view

        if tool_view.pending:  # the project was just allowed to run the tool: it comes back where it was
            self.home.composer.add_mention(tool_view.pending)
            tool_view.pending = None
        self.task_view.resume_btn.clicked.connect(lambda: self.control("resume_task"))
        self.sidebar.navigate.connect(self.navigate)
        self.sidebar.open_task.connect(self.open_task)
        self.sidebar.switch_project.connect(self.switch_project)
        self.sidebar.open_project_task.connect(self.switch_project)
        self.sidebar.open_folder.connect(self.open_folder)
        self.sidebar.export_chat.connect(self.export_chat)
        self.sidebar.renamed.connect(self._chat_renamed)

        from codedoctor.desktop.plugins_view import PluginsPage

        self.plugins_page = PluginsPage()
        self.pages.addWidget(self.plugins_page)
        self.navigate("home")
        self.draft_key = str(cfg.source or "")
        self.home.composer.edit.setPlainText(chat_tools.draft(self.draft_key))  # what was being written when this window last closed
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_MS)
        self.refresh()
        QTimer.singleShot(1500, self._warm_engine)
        self.takeover = None
        if cfg.computer.enabled and self.d.s.computer is not None:  # the blue frame, cursor and banner (takeover.py)
            from codedoctor.desktop.takeover import Takeover

            self.takeover = Takeover(self.d, self._stop_computer_task)

    # --- opening greeting -------------------------------------------------------------------------

    def _show_welcome(self) -> None:
        from codedoctor.desktop.welcome import Welcome

        if self.web is not None:  # 播放一次开场动画: the page plays it over itself
            self.web.command("welcome")
            return
        if self.welcome_screen is not None:
            return
        screen = QWidget()
        sl = QVBoxLayout(screen)
        sl.setContentsMargins(40, 40, 40, 40)
        row = QHBoxLayout()
        row.addStretch(1)
        self.welcome = Welcome(reduced=self.ui["reduced_motion"])
        self.welcome.setMinimumHeight(520)
        self.welcome.proceed.connect(self._enter_app)
        row.addWidget(self.welcome, 6)
        row.addStretch(1)
        sl.addStretch(1)
        sl.addLayout(row, 8)
        sl.addStretch(1)
        self.welcome_screen = screen
        self.root.addWidget(screen)
        self.root.setCurrentWidget(screen)

    def _enter_app(self) -> None:
        if self.welcome_screen is None:
            return  # proceed fires once from a button and again when the greeting completes
        screen, self.welcome_screen = self.welcome_screen, None
        self.root.setCurrentWidget(self.main_ui)
        motion.enter(self.main_ui, duration=420, dy=18)
        if self.web is None:
            motion.stagger([self.sidebar, self.home], step=70, duration=380, dy=14)
        self.root.removeWidget(screen)
        screen.hide()
        screen.deleteLater()  # stops the greeting's timers
        self.home.composer.edit.setFocus()

    def apply_appearance(self, ui: dict) -> None:
        """Wallpaper / motion changed on the settings page: apply now, remember for next time."""
        self.ui = {**self.ui, **ui}
        ui_prefs.save(self.ui)
        motion.set_reduced(self.ui["reduced_motion"])
        self.backdrop.set_wallpaper(self.ui["wallpaper"])
        configure(self.ui)
        QApplication.instance().setStyleSheet(qss())
        self.task_view.apply_prefs(self.ui)
        self.browser.engine = self.ui["search_engine"]
        if self.web is not None:
            self.web.push_prefs()

    # --- API keys: one check for the sidebar and the home page ----------------------------------

    def _missing_keys(self) -> list[str]:
        """Services an agent of this window uses that have no key right now (environment or Credential Manager)."""
        used = {c.endpoint for a in self.cfg.agents.values() for c in (a.primary, *a.fallbacks)}
        return [e.name or e.id for e in self.cfg.endpoints.values() if e.id in used and secrets.key_status(e) == "missing"]

    @staticmethod
    def _key_warnings(missing: list[str]) -> list[str]:
        return [f"{'、'.join(missing)} 还没有 API 密钥，用到它的 Agent 调用模型时会停下并提示。请到左侧“设置 → 服务与密钥”"
                "→“编辑与测试”里填写密钥，再点“保存”（保存在 Windows 凭据管理器），保存后立即生效，不用重启。"] if missing else []

    def _data_class_warnings(self) -> list:
        """The project's 代码级别 is above what every service of some agents may receive (仅本机 code, a cloud model):
        each of their model calls would be refused. Say it before the user asks, with the fix one click away."""
        from codedoctor.evidence.registry import DATA_CLASS_CN as CN, blocked_agents

        blocked = blocked_agents(self.cfg)
        if not blocked or not self.cfg.source:
            return []
        level = CN.get(self.cfg.code_data_class, self.cfg.code_data_class)
        who = "所有 Agent" if len(blocked) == len(self.cfg.agents) else "、".join(blocked[:6]) + ("……" if len(blocked) > 6 else "")
        return [(f"这个项目的代码级别是“{level}”，{who}用的模型服务都收不到这个级别的代码，调查会一开始就停下。"
                 "如果可以把代码发给你选的模型服务（例如 DeepSeek），点右边改成“内部代码”；"
                 "否则请在“设置 → Agent 模型”里给它们换成本机运行的模型。", ("改成内部代码", self._allow_internal))]

    def _allow_internal(self) -> None:
        from codedoctor import config as config_mod
        from codedoctor.evidence.registry import DATA_CLASS_CN as CN

        level = CN.get(self.cfg.code_data_class, self.cfg.code_data_class)
        if QMessageBox.question(self, "代码级别", f"把这个项目的代码级别从“{level}”改成“内部”？\n之后这个项目的代码"
                                "可以发给你在设置里选的模型服务（包括云端服务）。窗口会重新打开。") != QMessageBox.Yes:
            return
        try:
            raw = config_mod.load_raw(self.cfg.source)
            raw["project"]["code_data_class"] = "internal"
            config_mod.save_raw(raw, self.cfg.source)
        except Exception as e:
            notice(self, "没有改成", "配置文件没有保存。原因：", kind="error", details=[str(e)])
            return
        self.restart()

    def check_keys(self) -> None:
        missing = self._missing_keys()
        self.sidebar.set_key_problems(missing)
        self.home.set_warnings(self._data_class_warnings() + self._key_warnings(missing))
        self._keys_at = time.monotonic()

    # --- navigation -------------------------------------------------------------------

    def navigate(self, key: str) -> None:
        """"home", "settings" (the 设置 hub where it was left), or any hub key (graph, anomalies, schedule ...)."""
        if key in ("browser", "terminal"):  # beside what is open, not instead of it
            if self.web is not None:  # each of the two opens or closes its own half of the panel
                self.dock.toggle(key)
            elif self.dock.isVisible() and self.dock.current == key:
                self.dock.hide_dock()
            else:
                self.open_dock(key)
            return
        self.sidebar.check(key)
        if self.web is not None:  # the sidebar is the page's own and stays; a page not drawn in React lies beside it
            from codedoctor.desktop import web_settings

            key = {"models": "services"}.get(key, key)  # an older navigation key
            if key == "home":
                pick, level = self.remembered_pick()  # a new chat starts with the model chosen last
                if pick is not None:
                    self.apply_pick(self.home.composer, pick, level)
                self.home.composer.approval = "auto"  # a new chat starts with 帮我审查
                self.web.show_home()
            elif key == "plugins":
                self.web.show_view({"page": "plugins"})
            elif key == "settings" or key in web_settings.SECTIONS:  # 设置, drawn in React (web_settings.py)
                section = key if key != "settings" else getattr(self, "settings_section", "services")
                self.web.show_view({"page": "settings", "section": section})
            self.follow_tool()
            return
        self.sidebar.set_focus(key not in ("home", "plugins"))  # settings have their own list: the chats make room
        if key == "home":
            self.pages.setCurrentWidget(self.home)
            self.follow_tool()
            self.home.composer.edit.setFocus()
            return
        if key == "plugins":
            self.pages.setCurrentWidget(self.plugins_page)
            self.plugins_page.load()
            return
        return  # there is no Qt settings page any more: the page is drawn in React

    def open_task(self, task_id: str) -> None:
        self.sidebar.check(None)
        self.sidebar.set_focus(False)
        if self.web is not None:  # the React chat; the Qt page keeps which task and chat the box's buttons act on
            row = self.d.task(task_id) or {}
            from codedoctor.agents import orchestration as orch

            self.task_view.task_id = task_id
            self.task_view.chat_id = orch.body_of(row).get("chat_of") or task_id if row else task_id
            if getattr(self.web, "_box_chat", None) != self.task_view.chat_id:  # another chat: its own model, not the last one's
                self.follow_chat_pick(task_id)
            self.web.show_chat(task_id)
        else:
            self.task_view.show_task(task_id)
            self.pages.setCurrentWidget(self.task_view)
        task = self.d.task(task_id) or {}
        from codedoctor.agents import orchestration as orch

        # what the user called in, and the tools the team picked by itself in this chat (_tool_in_use)
        called = orch.called_tools(orch.body_of(task)) if task else []
        self._task_tools = list(dict.fromkeys([*called, *self.__dict__.get("_used_tools", {}).get(self.task_view.chat_id, [])]))
        self.follow_tool()

    # --- actions ----------------------------------------------------------------------

    # --- the model in the message boxes: the user's own choice, remembered; a chat's own, as it ran ----------------------

    def valid_pick(self, pick: dict | None) -> bool:
        """Can this choice run here now: Claude Code or Codex installed with that model, or a service of this project."""
        if not pick:
            return False
        if pick.get("engine"):
            from codedoctor import engines

            try:
                return engines.get(pick["engine"]).executable() and any(m["id"] == pick.get("id") for m in engines.models(pick["engine"]))
            except Exception:
                return False
        if pick.get("own"):
            return False  # "each agent's own" is never remembered: it is the project's model, not one the user chose
        return bool(pick.get("endpoint")) and pick["endpoint"] in self.cfg.endpoints and bool(pick.get("model"))

    def remembered_pick(self) -> tuple[dict | None, str | None]:
        ui = ui_prefs.load()
        pick = ui.get("last_pick") or None
        return (pick, ui.get("last_level") or None) if self.valid_pick(pick) else (None, None)

    def remember_pick(self, composer) -> None:
        """The user chose a model or a level in a box: kept for the next box, the next chat and the next start."""
        if not self.valid_pick(composer.model_choice):
            return
        ui = ui_prefs.load()
        ui["last_pick"], ui["last_level"] = dict(composer.model_choice), composer.level or ""
        ui_prefs.save(ui)
        self.ui = {**self.ui, "last_pick": ui["last_pick"], "last_level": ui["last_level"]}

    @staticmethod
    def apply_pick(composer, pick: dict | None, level: str | None) -> None:
        composer._set_model(pick, "")
        if pick and level and level in composer._levels()[0]:
            composer._set_level(level, "")

    def pick_of_turn(self, row: dict) -> tuple[dict | None, str | None]:
        """The model and level a turn really ran with, from its body, as a box shows them."""
        from codedoctor import engines
        from codedoctor.agents import orchestration as orch

        body = orch.body_of(row)
        if body.get("engine"):
            name, mid = body["engine"], body.get("engine_model")
            shown = next((m["name"] for m in engines.models(name) if m["id"] == mid), mid)
            return {"engine": name, "id": mid, "model": f"{engines.TITLES.get(name, name)} · {shown}"}, body.get("engine_effort")
        if body.get("model"):
            m = body["model"]
            return {"endpoint": m["endpoint"], "model": m["model"]}, body.get("reasoning")
        return None, body.get("reasoning")  # it ran on the agent's own settings: nothing chosen to show

    # --- what a question may spend: the user's limit, watched for every AI working on it ---------------------------------

    def spent(self, task_id: str) -> int:
        """New tokens of a question so far: every model call of its whole tree, cache re-reads not counted."""
        from codedoctor.agents import orchestration as orch

        done = max(0, orch.tree_tokens(self.d.s, task_id) - orch.tree_cached(self.d.s, task_id))
        live = self.d.s.__dict__.get("_live_tokens", {})  # Claude Code's running count, before its result says the total
        running = sum(live.get(t, 0) for t in orch.tree(self.d.s, task_id)) if live else 0
        return max(done, running)

    def _watch_spend(self, rows: list[dict]) -> None:
        """A question that reached the user's limit is stopped (Claude Code and Codex too: their process ends) and its
        chat says so, with 接着做 and the limit. Recorded in the journal (spend_stop), so it is said again after a restart."""
        limit = ui_prefs.load()["spend_limit"]
        stopped = self.__dict__.setdefault("_spend_stopped", set())
        for r in rows:
            if r.get("parent_task_id") or r["state"] == "finished" or r["id"] in stopped:
                continue
            used = self.spent(r["id"])
            if not limit or used < limit:  # 0: 不限
                continue
            stopped.add(r["id"])
            self.d.s.journal.append("system", "spend_stop", {"tokens": used, "limit": limit}, task_id=r["id"])
            from codedoctor import interface

            try:
                self.b.run(interface.cancel, self.d, r["id"])
            except Exception as e:  # said in the title; the next refresh tries nothing again for this question
                self.setWindowTitle(f"Lumen — {type(e).__name__}: {e}")

    def estimate(self, composer) -> dict:
        """What questions like this one used before in this project (finished ones, not small talk): the median of the
        same way of working (the same engine or service, the same @ tools), else of all; nothing with fewer than 3."""
        from statistics import median

        from codedoctor.agents import orchestration as orch

        opts = composer.options()
        way = (opts.get("engine") or (opts.get("model") or {}).get("endpoint") or "own", tuple(sorted(opts.get("tools") or ())))
        same, every = [], []
        for r in self.d.recent_tasks(300):
            if r.get("parent_task_id") or r["state"] != "finished" or r.get("outcome") != "done":
                continue
            b = orch.body_of(r)
            if b.get("chat"):
                continue
            used = self.spent(r["id"])
            if not used:
                continue
            every.append(used)
            if (b.get("engine") or (b.get("model") or {}).get("endpoint") or "own", tuple(sorted(b.get("toolsets") or ()))) == way:
                same.append(used)
        pool = same if len(same) >= 3 else every
        return {"typical": int(median(pool)) if len(pool) >= 3 else 0, "count": len(pool), "limit": ui_prefs.load()["spend_limit"]}

    def follow_chat_pick(self, task_id: str) -> None:
        """A chat on the screen: its box shows what its last turn ran with; failing that, what the user chose last;
        failing that, nothing (they choose)."""
        row = self.d.task(task_id) or {}
        if not row:
            return
        from codedoctor.agents import orchestration as orch

        chat = orch.body_of(row).get("chat_of") or task_id
        turns = self.d.chat_turns(chat) or [row]
        pick, level = self.pick_of_turn(turns[-1])
        if not self.valid_pick(pick):
            pick, level = self.remembered_pick()
        self.apply_pick(self.task_view.composer, pick, level)
        # 批准方式 follows the chat as it ran, the same way (a chat that never chose one: 帮我审查)
        self.task_view.composer.approval = orch.body_of(turns[-1]).get("approval") or "auto"

    def _lead_choice(self) -> dict | None:
        """What the message box shows at first: the engine of the agent that takes questions, else that agent's own model."""
        engine = self._engine_choice()
        if engine is not None:
            return engine
        agent = self.cfg.agents.get(self.modes[0][2])
        return {"model": agent.primary.model, "own": True} if agent else None

    def _engine_choice(self) -> dict | None:
        """The composer's choice when the agent that takes questions is on Claude Code or Codex (an 'engine' service)."""
        agent = self.cfg.agents.get(self.modes[0][2])
        ep = self.cfg.endpoints.get(agent.primary.endpoint) if agent else None
        if ep is None or ep.kind != "engine":
            return None
        from codedoctor import engines

        name = ep.base_url.split(":", 1)[1]
        shown = next((m["name"] for m in engines.models(name) if m["id"] == agent.primary.model), agent.primary.model)
        return {"engine": name, "id": agent.primary.model, "model": f"{engines.TITLES[name]} · {shown}"}

    def _model_choices(self) -> list[tuple[str, str, str]]:
        """Every model of the project's services the user listed or gave an agent: [(label, endpoint, model)]."""
        out, seen = [], set()
        used = [(c.endpoint, c.model) for a in self.cfg.agents.values() for c in (a.primary, *a.fallbacks)]
        for ep in self.cfg.endpoints.values():
            if (ep.kind == "scripted" and not used) or ep.kind == "engine":  # engines list their models apart
                continue
            for model in list(dict.fromkeys([m for e, m in used if e == ep.id] + list(ep.models))):
                if (ep.id, model) not in seen:
                    seen.add((ep.id, model))
                    out.append((f"{ep.name or ep.id} · {model}", ep.id, model))
        return out

    def _fetch_models(self, done) -> None:
        """更多模型: ask every service with a key (or a local one) for the models it offers now, on the service loop;
        `done([(service, endpoint, models or the error)])` runs on this thread when all have answered."""
        import asyncio

        eps = [ep for ep in self.cfg.endpoints.values() if ep.kind not in ("scripted", "engine")]

        async def ask_all():
            async def one(ep):
                try:
                    models = await asyncio.wait_for(self.d.s.models.client(ep.id).list_models(), 20)
                    return (ep.name or ep.id, ep.id, sorted(models) or "这个服务没有列出模型")
                except Exception as e:  # shown in the menu; nothing else depends on it
                    return (ep.name or ep.id, ep.id, f"{type(e).__name__}: {e}")
            return list(await asyncio.gather(*(one(ep) for ep in eps)))

        fut = asyncio.run_coroutine_threadsafe(ask_all(), self.b.loop)
        timer = QTimer(self)

        def poll():
            if fut.done():
                timer.stop()
                timer.deleteLater()
                try:
                    done(fut.result())
                except Exception as e:
                    done([("服务", "", f"{type(e).__name__}: {e}")])
        timer.timeout.connect(poll)
        timer.start(150)

    def submit(self, text: str, agent: str, options: dict | None = None) -> None:
        title = text.strip().splitlines()[0][:60]
        self.last_submit_ok = False
        try:
            sub = self.b.run(self.d.submit_task, agent, title, text, **(options or {}))
        except Exception as e:
            for box in (self.home.composer, self.task_view.composer):  # the box that sent it gets its words and files back
                box.give_back()
            notice(self, "提交失败", "没有发出去，你写的和加的文件都还在框里。原因：", kind="error", details=[human_why(e)])
            return
        self.last_submit_ok = True
        # @CodePage, @Code3D ...: the tool's own window is above the chat (tool_view.py), not a window of its own
        self.refresh()
        self.open_task(sub["task_id"])

    # --- the panel on the right ---------------------------------------------------------------------------------------

    def _in_chat(self) -> bool:
        """A conversation is on the screen (the React one or the Qt page)."""
        if self.web is not None:
            return self.web.last.get("page") == "chat" or self.web.last.get("key") == "details"
        return self.pages.currentWidget() is self.task_view

    def _on_home(self) -> bool:
        if self.web is not None:
            return self.web.last.get("page") == "home"
        return self.pages.currentWidget() is self.home

    def _qt_page(self):
        """The Qt page on the screen, if one is (in the React window: one lying beside the sidebar)."""
        if self.web is not None and self.web.last.get("page") != "native":
            return None
        cur = self.pages.currentWidget()
        return cur

    def open_details(self, task_id: str) -> None:
        """详细 under an answer: the full Qt page, with claims, anomalies, changes and computer actions."""
        if self.web is not None:  # the page draws the details under the answer (web_details.py)
            self.open_task(task_id)
            self.web.show_view({"page": "chat", "task_id": task_id, "details": task_id})
            return
        self.task_view.show_task(task_id)
        self.pages.setCurrentWidget(self.task_view)

    def follow_tool(self) -> None:
        """The @ tools of what is on the screen - the new chat's chips, or the open chat's - shown on the right, one at a
        time with a tab each when there are two; none (or all closed by the user): hidden."""
        from codedoctor.desktop import tool_view
        from codedoctor.desktop.composer import MENTIONS

        keys = self.home.composer.mentions if self._on_home() else getattr(self, "_task_tools", []) if self._in_chat() else []
        closed = getattr(self, "_tools_closed", set())
        closed &= set(keys)  # @ it again after closing it and it comes back
        self._tools_closed = closed
        tools = [k for k in tool_view.window_tools(keys) if k not in closed]
        if not tools and self.web is not None and self.tool_view.current and not getattr(self, "_tool_dismissed", False):
            # The tool on the right stays until the user closes it (2026-11-14: CodeCut vanished and came back by itself -
            # the box emptied after sending, or a chat without @ was shown - and the user saw it as a flash)
            return
        if not tools:
            self.tool_view.hide_tool()
            self.home.set_compact(False)
            if self.web is not None:
                self.web.set_tool(False)
            return
        pick = getattr(self, "_tool_pick", None)
        tool = pick if pick in tools else tools[0]
        self._tool_pick = tool
        self._tool_dismissed = False
        self.tool_view.show_tool(tool, str(self.d.s.config.root), self.d.s.config)
        if self.web is not None:
            self.web.set_tool(True, MENTIONS.get(tool, tool), [{"key": k, "name": MENTIONS.get(k, k)} for k in tools], tool)
            return
        self.home.set_compact(self._on_home())
        total = self.main_split.height()
        if total > 0 and self.main_split.sizes()[0] < 200:
            self.main_split.setSizes([int(total * .66), total - int(total * .66)])

    def close_tool(self) -> None:
        """The x on the tool's side: it goes away (the process keeps, so opening it again is immediate)."""
        cur = getattr(self, "_tool_pick", None)
        if cur:
            self._tools_closed = getattr(self, "_tools_closed", set()) | {cur}
        self._tool_dismissed = True  # only the user's x takes the tool away (follow_tool keeps it otherwise)
        self.follow_tool()

    def pick_tool(self, tool: str) -> None:
        self._tool_pick = tool
        self.follow_tool()

    def prepare(self) -> None:
        """Before the window is first shown: the browser's first page. Made later, the first web view switched the whole
        window to another kind of surface, so Qt closed and remade it (the window flashed away and back), and the click
        froze for two seconds while Chromium started (a real bug, 2026-11-10). Done here, that second passes while nothing
        is on the screen yet, which the user prefers, and the browser opens at once."""
        self.browser.ensure()

    def open_dock(self, key: str) -> None:
        self.dock.show_tab(key)
        self.sidebar.set_dock(key)
        if self.web is not None:
            self.web.push_side()
            return
        total = self.body_split.width()
        if total > 0 and self.body_split.sizes()[1] < 340:
            right = min(max(420, int(total * .42)), total - 360)
            self.body_split.setSizes([total - right, right])

    def _warm_engine(self) -> None:
        """A Claude Code ready before the first message: it spends no tokens while it waits (engine_sessions.py)."""
        choice = self._engine_choice()
        agent = self.d.agents.get(self.modes[0][2])
        if self.d.s.config.agents.get("lumen") is None or agent is None or agent.id != "lumen" or (choice or {}).get("engine") != "claude_code":
            return
        import asyncio

        from codedoctor import claude_code

        self.d.s.warm_engines = True
        asyncio.run_coroutine_threadsafe(claude_code.warm(agent, {"engine": "claude_code", "engine_model": choice.get("id"),
                                                                  "engine_effort": self.home.composer.level}), self.b.loop)

    def open_link(self, url: str) -> None:
        """A link clicked in a chat opens on the right, next to the chat."""
        self.open_dock("browser")
        self.browser.ensure()
        view = self.browser.current()
        if view is not None and self.browser._blank(view):
            self.browser._open(url)
        else:
            self.browser.add_tab(url)

    def _ask_ray(self, text: str) -> None:
        """A question from the browser's start page: Ray looks it up in the browser, the user watches."""
        if "ray" not in self.cfg.agents:
            return
        task = f"Look this up in the built-in browser, open the pages yourself, and answer in the language of the question, with sources: {text}"
        try:
            sub = self.b.run(self.d.submit_task, "ray", text[:60], task)
        except Exception as e:
            notice(self, "提交失败", "没有开始。原因：", kind="error", details=[human_why(e)])
            return
        self.browser.panel.follow(sub["task_id"])

    def _stop_computer_task(self, task_id: str | None) -> None:
        """停止 on the takeover banner: computer use is stopped (the gate refuses every action) and the task cancelled."""
        if not task_id:
            return
        from codedoctor import interface

        try:
            self.b.run(interface.cancel, self.d, task_id)
        except Exception:
            pass  # computer use is stopped either way

    def control(self, command: str, confirm: bool = True) -> None:
        tid = self.task_view.task_id
        if not tid:
            return
        row = self.d.task(tid)
        if command == "cancel_task" and confirm and QMessageBox.question(
                self, "取消任务", "确定取消这个调查？所有子任务会一起取消，已经完成的步骤会保留。") != QMessageBox.Yes:
            return
        try:
            if command == "cancel_task":  # the investigation and every subtask still running
                from codedoctor import interface

                self.b.run(interface.cancel, self.d, tid)
            else:
                self.b.run(self.d.control, row["agent"], command, task_id=tid)
        except Exception as e:
            notice(self, "操作失败", "没有执行。原因：", kind="error", details=[str(e)])

    def refresh(self) -> None:
        try:
            if time.monotonic() - self._keys_at > 5:  # also catches a key set in an environment variable meanwhile
                self.check_keys()
            self.computer_bar.refresh()
            rows = self.d.recent_tasks(300)
            self.sidebar.set_tasks(rows, self.task_view.task_id if self._in_chat() else None)
            if self.web is not None:
                self.web.push_side()
                self._watch_spend(rows)
            self.browser.panel.refresh(self.d)
            self._watch_commands()
            self._watch_done(rows)
            cur = self._qt_page()
            if cur is self.task_view:
                self.task_view.refresh()
        except Exception as e:  # keep the window alive; show the problem in the title
            self.setWindowTitle(f"Lumen — 刷新出错：{type(e).__name__}: {e}")

    # --- Ctrl+K, and what it can reach ------------------------------------------------------------------------------------

    def open_palette(self) -> None:
        def said(needle: str) -> list:  # what was said in any chat here, not only their first lines
            return [palette.Item(c["title"], c["snippet"], lambda task=c["task"]: self.open_task(task)) for c in chat_tools.search_chats(self.d, needle)]

        palette.ask(self, self._palette_items(), said)

    def _palette_items(self) -> list:
        t, Item = locale.t, palette.Item
        act, page, chat, folder = t("操作"), t("页面"), t("聊天"), t("项目")
        items = [Item(t("新聊天"), act, lambda: self.navigate("home"), "new chat xinliaotian", "Ctrl+N"),
                 Item(t("新窗口"), act, new_window, "new window xinchuangkou", "Ctrl+Shift+N"),
                 Item(t("插件"), page, lambda: self.navigate("plugins"), "plugins chajian tools gongju"),
                 Item(t("打开或关闭终端"), act, lambda: self.navigate("terminal"), "terminal zhongduan powershell", "Ctrl+J"),
                 Item(t("打开或关闭浏览器"), act, lambda: self.navigate("browser"), "browser liulanqi web", "Ctrl+Shift+B"),
                 Item(t("显示或收起聊天列表"), act, self.toggle_sidebar, "sidebar liebiao", "Ctrl+B"),
                 Item(t("在这个聊天里查找"), act, self.find_in_chat, "find chazhao search", "Ctrl+F"),
                 Item(t("导出这个聊天"), act, self.export_chat, "export daochu markdown"),
                 Item(t("把所有聊天存成文件"), act, self.export_everything, "backup export all beifen daochu"),
                 Item(t("打开项目文件夹"), act, self.open_project_folder, "folder explorer wenjianjia"),
                 Item(t("打开别的文件夹"), act, self.open_folder, "open folder dakai"),
                 Item(t("放回收起的聊天"), act, self.bring_chats_back, "hidden restore shouqi"),
                 Item(t("快捷键一览"), act, self.show_keys, "keys shortcuts kuaijiejian", "Ctrl+/")]
        for key, title, words in (("services", "服务", "api key fuwu miyao"), ("agent_models", "AI 模型", "model moxing"), ("memory", "长期记忆", "memory jiyi"),
                                  ("appearance", "外观", "look theme waiguan zhuti"), ("usage", "用量", "usage token yongliang"), ("book", "功能手册", "manual help shouce")):
            items.append(Item(t(title), page, lambda k=key: self.navigate(k), words, "F1" if key == "book" else ""))
        for c in self.sidebar.listed()[:300]:
            items.append(Item(c["title"], chat, lambda task=c["open"]: self.open_task(task)))
        for p in projects.load():
            if p.get("config") and Path(p["config"]).exists() and not (self.sidebar.config_path and projects._same(p["config"], self.sidebar.config_path)):
                items.append(Item(p.get("label") or p.get("name") or p["config"], folder, lambda c=p["config"]: self.switch_project(c), str(p.get("root") or "")))
        return items

    def show_keys(self) -> None:
        notice(self, "快捷键", "这些键在 Lumen 的任何地方都能用。", details=[
            "Ctrl+K　找聊天、页面或操作", "Ctrl+N　新聊天", "Ctrl+Shift+N　新窗口", "Ctrl+F　在聊天里查找", "Ctrl+B　显示或收起聊天列表", "Ctrl+J　终端",
            "Ctrl+Shift+B　浏览器", "Ctrl+,　设置", "F1　功能手册", "Ctrl+/　这张表", "Ctrl+=　字大一点，Ctrl+-　字小一点", "输入框里：Ctrl+S 存为常用语，空的时候打 / 调出常用语"])

    def step_text(self, by: int) -> None:
        """Ctrl+= and Ctrl+-: the same three sizes as in 外观."""
        sizes = ["small", "normal", "large"]
        now = sizes.index(self.ui["font_size"]) if self.ui["font_size"] in sizes else 1
        self.apply_appearance({"font_size": sizes[max(0, min(2, now + by))]})

    def put_in_box(self, text: str) -> None:
        """Something from the panel on the right, into the message box in front of the user; nothing is sent."""
        if self.web is not None:  # into the React box in front of the user
            if not self._in_chat() and not self._on_home():
                self.navigate("home")
            import json

            self.web.bridge.put.emit(json.dumps({"text": text}, ensure_ascii=False))
            return
        here = self.pages.currentWidget() is self.task_view
        if not here and self.pages.currentWidget() is not self.home:
            self.navigate("home")
        box = (self.task_view if here else self.home).composer
        now = box.edit.toPlainText().strip()
        box.set_text(f"{now}\n\n{text}" if now else text)

    def find_in_chat(self) -> None:
        if self._qt_page() is self.task_view:
            self.task_view.open_find()
        elif self.web is not None and self.web.last.get("page") == "chat":
            self.web.command("find")

    def toggle_sidebar(self) -> None:
        """Ctrl+B: the chat list shown or put away."""
        if self.web is not None:
            self.web.command("toggle_side")
        else:
            self.sidebar._toggle_list()

    def open_project_folder(self) -> None:
        folder = str(self.cfg.root)  # the project's own folder, in Explorer / Finder / the file manager
        if sys.platform.startswith("win"):
            os.startfile(folder)  # noqa: S606
        else:
            import subprocess

            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])

    def bring_chats_back(self) -> None:
        count = chat_tools.bring_back(self.sidebar.config_path or "")
        self.sidebar.reload_names()
        if self.web is not None:
            self.web.push_side(force=True)
        notice(self, "放回收起的聊天", f"放回了 {count} 个聊天。" if count else "没有收起的聊天。", kind="ok" if count else "info")

    def _chat_renamed(self, chat_id: str) -> None:
        if self.task_view.chat_id == chat_id and self.task_view.task_id:
            self.task_view.show_task(self.task_view.task_id)

    def export_chat(self, chat_id: str | None = None) -> None:
        """The chat asked for, or the one on the screen, as a Markdown file where the user says."""
        here = self._in_chat()
        chat_id = chat_id or (self.task_view.chat_id if here else None)
        if not chat_id:
            notice(self, "导出聊天", "先打开一个聊天。")
            return
        title = next((c["title"] for c in self.sidebar.listed() if c["id"] == chat_id), None)
        text = chat_tools.as_markdown(self.d, chat_id, title)
        if not text:
            notice(self, "导出聊天", "这个聊天里还没有内容。")
            return
        target, _ = QFileDialog.getSaveFileName(self, locale.t("导出聊天"), str(Path.home() / "Documents" / chat_tools.file_name(title or "chat")), "Markdown (*.md)")
        if not target:
            return
        try:
            Path(target).write_text(text, encoding="utf-8")
        except OSError as e:
            notice(self, "导出聊天", "没有写成。原因：", kind="error", details=[str(e)])
            return
        notice(self, "导出聊天", f"已经存到 {target}", kind="ok")

    def export_everything(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, locale.t("把所有聊天存到哪里"), str(Path.home() / "Documents"))
        if not folder:
            return
        try:
            count = chat_tools.export_all(self.d, self.sidebar.config_path or "", Path(folder))
        except OSError as e:
            notice(self, "把所有聊天存成文件", "没有写成。原因：", kind="error", details=[str(e)])
            return
        notice(self, "把所有聊天存成文件", f"存好了 {count} 个聊天，在 {folder}。", kind="ok")

    # --- telling the user an answer is ready ------------------------------------------------------------------------------

    def _watch_done(self, rows: list[dict]) -> None:
        """A question the user asked has ended while the window is behind something else."""
        roots = [r for r in rows if not r.get("parent_task_id")]
        before = getattr(self, "_running", None)
        self._running = {r["id"] for r in roots if r["state"] != "finished"}
        if before is None or self.isActiveWindow() or not self.ui.get("notify_done", True):
            return
        done = [r for r in roots if r["id"] in before and r["state"] == "finished"]
        if done:
            self._tell_done(done[0])

    def _tell_done(self, row: dict) -> None:
        QApplication.alert(self, 0)  # the taskbar button lights up until the window is opened
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self.tray is None:
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray.setToolTip("Lumen")
            self.tray.messageClicked.connect(self._open_done)
            self.tray.activated.connect(lambda _reason: self._open_done())
            self.tray.show()
        self._done_task = row["id"]
        head = locale.t("Lumen 做完了") if row.get("outcome") == "done" else locale.t("Lumen 停下来了")
        self.tray.showMessage(head, row["title"][:80], self.windowIcon(), 6000)

    def _open_done(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self._done_task:
            self.open_task(self._done_task)

    def _watch_commands(self) -> None:
        """New shell commands of any agent, for the terminal on the right."""
        if not hasattr(self, "_command_seq"):
            newest = self.d.s.journal.read(after_seq=0, limit=1)
            self._command_seq = 0 if not newest else self._last_seq()
        for e in self.d.s.journal.read(after_seq=self._command_seq, limit=200):
            self._command_seq = e["seq"]
            data = e["data"]
            if e["type"] != "tool_call":
                continue
            args = data.get("arguments") or {}
            shell = data.get("tool") == "run_command" or (data.get("tool") in ("claude_code", "codex") and args.get("tool") == "Bash")
            if shell and args.get("command"):
                self.dock.ai_ran(e["agent"], str(args["command"])[:300])
            names = f"{data.get('tool', '')} {args.get('tool', '') if isinstance(args, dict) else ''}"
            if "browser_" in names and hasattr(self.dock, "ai_opens"):  # Ray works in the browser on the side: it is shown there
                self.dock.ai_opens("browser")
            used = self._tool_used(data, args)
            if used:
                self._tool_in_use(used, e.get("task_id"))

    @staticmethod
    def _tool_used(data: dict, args) -> str | None:
        """Which Lumen tool a tool call works with: CodeCut, Code3D or a maker (codepdf, codepage ...), else None. An agent
        of its own loop names the maker in args["tool"]; an engine's call is journaled as {"tool": "maker_run",
        "description": "run codepdf <folder> images"}."""
        from codedoctor import makers

        args = args if isinstance(args, dict) else {}
        engine = data.get("tool") in ("claude_code", "codex")
        name = args.get("tool") if engine else data.get("tool")
        if not isinstance(name, str):
            return None
        if name.startswith("video_"):
            return "codecut"
        if name.startswith("code3d_"):
            return "code3d"
        if name in ("maker_run", "maker_read"):
            maker = (str(args.get("description") or "").split() + ["", ""])[1] if engine else args.get("tool")
            return maker if maker in makers.MAKERS else None
        return None

    def _tool_in_use(self, key: str, task_id: str | None) -> None:
        """The team picked a tool by itself (no @): it opens on the right in that chat, as if the user had called it in."""
        from codedoctor.agents import orchestration as orch

        try:
            root = orch.root_of(self.d.s, task_id) if task_id else None
            chat = (orch.body_of(orch.task_row(self.d.s, root) or {}).get("chat_of") or root) if root else None
        except Exception:
            chat = None
        if chat is None:
            return
        used = self.__dict__.setdefault("_used_tools", {})
        if key in used.setdefault(chat, []):
            return
        used[chat].append(key)
        if self._in_chat() and getattr(self.task_view, "chat_id", None) == chat and key not in self._task_tools:
            self._task_tools = [*self._task_tools, key]
            self.follow_tool()

    def _last_seq(self) -> int:
        """Where the journal stands now: what ran before this window opened is not news."""
        seq, rows = 0, self.d.s.journal.read(after_seq=0, limit=500)
        while rows:
            seq = rows[-1]["seq"]
            rows = self.d.s.journal.read(after_seq=seq, limit=500)
        return seq

    # --- projects ---------------------------------------------------------------------

    def switch_project(self, config_path: str, task_id: str | None = None) -> None:
        """Open another folder: this window closes (asking first if tasks are running) and the same process opens
        the other one (switch_to) - on `task_id` when one was clicked in the sidebar."""
        self._next_config, self._next_task = config_path, task_id
        if not self.close():
            self._next_config = self._next_task = None

    def open_folder(self) -> None:
        """创建项目: a name and a source folder, in a dialog over the blurred window (desktop/projects_ui.py); the
        project opens with the AIs chosen the first time - nothing else to set up."""
        from codedoctor.desktop.projects_ui import CreateProject

        path = CreateProject(self, projects.load_setup() or self._setup_from_here()).exec()
        if path:
            self.switch_project(path)

    def _setup_from_here(self) -> dict:
        """This folder's AI services and models, for a folder opened before the first-run setup existed."""
        raw = config_mod.load_raw(self.cfg.source)
        return {"endpoints": raw["endpoints"], "agents": raw["agents"], "permissions": raw.get("permissions", {})}

    def restart(self) -> None:
        """Close (asking first if tasks are running), then start a new window on the same configuration."""
        self._restart = True
        if not self.close():
            self._restart = False

    def _sure_to_close(self, text: str) -> bool:
        """关闭 / 取消 in the window's language (QMessageBox.question showed English Yes / No, 2026-11-14)."""
        from codedoctor.desktop.locale import t as _t

        box = QMessageBox(QMessageBox.Question, _t("关闭 Lumen"), text, parent=self)
        close = box.addButton(_t("关闭"), QMessageBox.AcceptRole)
        box.addButton(_t("取消"), QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is close

    def closeEvent(self, e):
        from codedoctor.desktop.locale import t as _t

        # the old Qt settings page only counts when it is the one on the screen: in the React window it is hidden and could
        # not be saved, so its leftover "dirty" asked about changes the user never made (2026-11-14)
        if self.web is None and self.models_page.dirty and not self._sure_to_close(
                _t("设置里有没有保存的修改（包括刚填的 API 密钥），关闭会丢弃它们，密钥不会留在电脑上。确定关闭？")):
            e.ignore()
            return
        running = [r for r in self.d.recent_tasks(300) if r["state"] != "finished"]
        if running and not self._sure_to_close(
                _t("还有 {0} 个任务没有结束。关闭会中断它们（下次打开后可以点“继续执行”）。确定关闭？").replace("{0}", str(len(running)))):
            e.ignore()
            return
        self.timer.stop()
        draft = self.web_draft if self.web is not None and self.web_draft is not None else self.home.composer.edit.toPlainText()
        chat_tools.keep_draft(self.draft_key, draft)
        place = self.normalGeometry()
        chat_tools.keep_window_place(place.x(), place.y(), place.width(), place.height(), self.isMaximized())
        if self.tray is not None:
            self.tray.hide()
        if self.takeover is not None:
            self.takeover.timer.stop()
            self.takeover.hide()
        self.browser.shutdown()
        self.tool_view.shutdown()
        self.dock.shutdown()
        try:
            self.b.close()
        finally:
            e.accept()
        target = self._next_config or (str(self.cfg.source) if self._restart and self.cfg.source else None)
        if target:  # opened again in this process: no new program to start, no seconds of loading
            self.switch_to.emit(target, self._next_task if self._next_config else None)


def new_window() -> None:
    """One more Lumen, asked for on purpose (新窗口, Ctrl+Shift+N): on the same folder if that is what is open
    (launcher.another_window). Only this start gets past the one-Lumen rule (_hand_to_running)."""
    import subprocess

    exe = Path(sys.executable)
    if exe.with_name("pythonw.exe").is_file():
        exe = exe.with_name("pythonw.exe")
    subprocess.Popen([str(exe), "-m", "codedoctor.desktop.app"], close_fds=True, env={**os.environ, "LUMEN_NEW_WINDOW": "1"})


def _instance_name() -> str:
    """One Lumen per user and data folder (tests with their own CODEDOCTOR_HOME do not meet the user's)."""
    import hashlib

    home = os.environ.get("CODEDOCTOR_HOME") or str(Path.home() / ".codedoctor")
    return "lumen-desktop-" + hashlib.sha1(home.casefold().encode("utf-8")).hexdigest()[:12]


_MUTEX = None  # held for the life of the first Lumen


def _first_lumen() -> bool:
    """True for the first Lumen of this user and data folder: a named Windows mutex, taken in one step, so two starts a moment
    apart cannot both win (the local server below only listens once the window is being built). Elsewhere: a lock file."""
    global _MUTEX
    name = _instance_name()
    if os.name == "nt":
        import ctypes

        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        handle = k32.CreateMutexW(None, False, f"Local\\{name}")
        if not handle:
            return True
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            k32.CloseHandle(ctypes.c_void_p(handle))
            return False
        _MUTEX = handle
        return True
    import fcntl
    import tempfile

    f = open(Path(tempfile.gettempdir()) / f"{name}.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _MUTEX = f
    return True


def _hand_to_running(args) -> bool:
    """Clicking the shortcut again, even many times, opens nothing new (the user, 2026-11-14): the Lumen already open is
    told to come to the front, and this start ends. True when there was one."""
    if os.environ.pop("LUMEN_NEW_WINDOW", None) == "1":
        return False
    first = _first_lumen()
    from PySide6.QtNetwork import QLocalSocket

    sock = QLocalSocket()
    # Two quick clicks started two Lumens (2026-11-14): the first was still loading and not yet listening. The mark below is
    # taken at once by the first; a later start that finds it waits up to 20 s for the first to listen, and never opens.
    deadline = time.monotonic() + (0 if first else 20)
    while True:
        sock.connectToServer(_instance_name())
        if sock.waitForConnected(400):
            break
        if first or time.monotonic() > deadline:
            return not first  # nobody answered: the first runs on; a later one ends anyway (the first is still starting)
        time.sleep(0.25)
    import json

    sock.write(json.dumps({"config": args.config, "task": args.task}).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(400)
    sock.disconnectFromServer()
    return True


def _listen_for_starts(current):
    """The running Lumen hears later starts (_hand_to_running) and brings its window to the front."""
    from PySide6.QtNetwork import QLocalServer

    name = _instance_name()
    server = QLocalServer()
    if not server.listen(name):
        QLocalServer.removeServer(name)  # left over from a Lumen that ended without closing it
        server.listen(name)

    def come_forward():
        win = current()
        if win is None:
            return
        if win.isMinimized():
            win.showNormal()
        win.show()
        win.raise_()
        win.activateWindow()

    def arrived():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.readyRead.connect(conn.readAll)  # what it says is not needed: any start means "show Lumen"
            conn.disconnected.connect(conn.deleteLater)
        QTimer.singleShot(0, come_forward)

    server.newConnection.connect(arrived)
    return server


def make_app() -> QApplication:
    if QApplication.instance() is None:  # the built-in browser needs this before the application exists (browser.py)
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        # Ray works in it while the user does something else: a covered window must go on drawing and running its pages
        flags = "--disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows --disable-renderer-backgrounding"
        # The flash the user kept seeing (2026-11-14, a screen recording taken apart frame by frame): for two frames the
        # parts of the page drawn on their own GPU layers (the Lumen figure, the message box) vanished while plain text
        # stayed, and the log had Chromium's "d3d_image_backing: Already being accessed for read" and "Context lost". The
        # page is drawn without the GPU's compositing and rasterizing: a chat page needs neither, and nothing vanishes.
        # LUMEN_GPU=1 gives them back (to compare).
        if os.environ.get("LUMEN_GPU") != "1":
            flags += " --disable-gpu-compositing --disable-gpu-rasterization"
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')} {flags}".strip()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    f = QFont(FONT_FAMILY)
    f.setPixelSize({"small": 13, "large": 15}.get(ui_prefs.load()["font_size"], 14))
    app.setFont(f)
    ui = ui_prefs.load()
    configure(ui)
    app.setStyleSheet(qss())
    app.setWindowIcon(app_icon())
    return app


def human_why(e: Exception) -> str:
    """Why something could not be done, for the user: our own sentences pass; a schema's or a library's English does not."""
    text = str(e)
    if re.search(r"[\u4e00-\u9fff]", text):
        return text
    if re.search(r"invalid message|is not one of|required property|schema|additional properties|ValidationError|not valid under", text, re.I):
        return "这条消息的内容 Lumen 没能接受。你写的字和加的文件都还在，再点一次发送；还是不行，请重启 Lumen 再试。"
    return "出了点意外，这次没能完成。你写的字和加的文件都还在，再试一次。"


def _crash_log() -> None:
    """Record why the window died: Python errors in a click handler (shown and logged, the window stays open) and
    hard crashes (faulthandler writes the stack of every thread). ~/.codedoctor/crash.log."""
    import faulthandler
    import os
    import time
    import traceback

    home = Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor")
    try:
        home.mkdir(parents=True, exist_ok=True)
        log = open(home / "crash.log", "a", encoding="utf-8", buffering=1)  # kept open for faulthandler
    except OSError:
        return
    log.write(f"\n=== Lumen started {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    faulthandler.enable(log, all_threads=True)

    def hook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        log.write(f"\n--- {time.strftime('%H:%M:%S')} unhandled error ---\n{text}")
        try:
            notice(None, "Lumen 出错了", f"窗口没有关闭，可以继续用。详细信息已记录到 {home / 'crash.log'}。",
                   kind="warning", details=[f"{kind.__name__}: {value}"])
        except Exception:
            pass

    sys.excepthook = hook


def _show_main(app, win) -> None:
    screen = app.primaryScreen().availableGeometry()
    win.resize(int(screen.width() * 0.82), int(screen.height() * 0.86))
    win.move(screen.x() + int(screen.width() * 0.09), screen.y() + int(screen.height() * 0.05))
    place = chat_tools.window_place()  # where it was left, if that spot still exists (a second screen may be gone)
    if all(isinstance(place.get(k), int) for k in ("x", "y", "width", "height")) and app.screenAt(QPoint(place["x"] + 80, place["y"] + 20)) is not None:
        win.setGeometry(place["x"], place["y"], max(place["width"], 640), max(place["height"], 480))
    win.show()
    if place.get("maximized") is True:
        win.showMaximized()
        return
    fit_on_screen(win)


def fit_on_screen(win) -> None:
    """The whole window inside the screen's free area, above the taskbar: what is beyond its edge cannot be clicked
    (a real bug: the stop button sat off the screen)."""
    area = (win.screen() or QApplication.primaryScreen()).availableGeometry()
    frame = win.frameGeometry()
    extra_w, extra_h = frame.width() - win.width(), frame.height() - win.height()
    w = min(win.width(), area.width() - extra_w)
    h = min(win.height(), area.height() - extra_h)
    if (w, h) != (win.width(), win.height()):
        win.resize(max(w, 200), max(h, 200))
    frame = win.frameGeometry()
    x = max(min(frame.x(), area.right() - frame.width() + 1), area.x())  # too big even so: its top-left stays on
    y = max(min(frame.y(), area.bottom() - frame.height() + 1), area.y())
    if (x, y) != (frame.x(), frame.y()):
        win.move(x, y)


def main(argv: list[str] | None = None) -> int:
    from codedoctor.desktop import i18n

    i18n.set_language(ui_prefs.load()["language"])
    p = argparse.ArgumentParser(prog="codedoctor-desktop")
    p.add_argument("--config", help="open this configuration; without it, the folder opened last")
    p.add_argument("--task", help="and show this investigation")
    args = p.parse_args(argv)
    _crash_log()
    app = make_app()
    if _hand_to_running(args):  # Lumen is already open: it comes to the front, and this start ends here
        return 0
    from codedoctor import claude_code
    from codedoctor.desktop.launcher import Launcher

    claude_code.refresh_later()  # its model menu as it is today, asked while the folder opens
    # The greeting and first-run setup the first time only; then the folder opens straight away on a worker thread,
    # with nothing on the screen until the window is ready (no 正在打开 card: the user's rule, 2026-11-10). Opening
    # another folder comes back here: one process, no restart.
    launcher = Launcher(Backend, args.config, args.task)
    launcher.show_me = lambda: _show_main(app, launcher)  # only for the greeting and for a folder that did not open
    windows: list[MainWindow] = []

    def opened(cfg, backend, task):
        win = MainWindow(cfg, backend)
        win.prepare()
        win.switch_to.connect(launcher.open_config)
        windows[:] = [win]
        _show_main(app, win)
        if task and backend.daemon.task(task):
            win.open_task(task)

    launcher.opened.connect(opened)
    server = _listen_for_starts(lambda: windows[0] if windows else launcher)  # kept alive while the program runs
    if launcher.welcome_screen is not None:
        _show_main(app, launcher)
    code = app.exec()
    del server
    # Everything that matters closed with the window. Letting Python take Qt and Chromium apart in whatever order ended the
    # program with an access violation on every exit, so it stops here, keeping only the last duty: no engine left running.
    from codedoctor import engines

    engines._stop_all()
    for stream in (sys.stdout, sys.stderr):  # pythonw has none: nothing to flush, and not an error at exit
        if stream is not None:
            stream.flush()
    os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
