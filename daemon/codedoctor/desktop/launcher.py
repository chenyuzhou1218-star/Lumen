"""What shows before the main window (2026-11-03). The very first time: the greeting, then the language and the
AIs (first_run.py). Every time after: nothing at all - the folder opened last (or ~/Lumen) opens on a worker thread and
the main window appears when it is ready. There is no 正在打开 card (2026-11-10, the user's rule: better a moment with
nothing on the screen than a card to look at); a card shows only when the folder could not be opened, saying why,
with 打开文件夹 to choose another.

Started by ``codedoctor-desktop`` (the desktop shortcut); with ``--config`` that configuration is opened instead.
The main window comes back here to open another folder (MainWindow.switch_to), in the same process.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from codedoctor import config as config_mod
from codedoctor.desktop import motion, projects
from codedoctor.desktop import prefs as ui_prefs
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.liquid import Atmosphere, Glass, MedicalMark
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import hbox, label


def second_window(cfg) -> bool:
    """A window opened on a folder another window already has open: it lives in data_dir/windows/N (another_window)."""
    return cfg.data_dir.parent.name == "windows"


def another_window(cfg, factory):
    """(cfg, backend). This folder is open already: another window opens on it all the same, with chats of its own in a
    data folder of its own, because two services on one database would run every task twice (store/lock.py)."""
    import dataclasses

    from codedoctor.store.lock import AlreadyRunning

    base = cfg.data_dir
    for n in range(1, 21):
        try:
            return cfg, factory(cfg)
        except AlreadyRunning:
            cfg = dataclasses.replace(cfg, data_dir=base / "windows" / str(n))
    raise AlreadyRunning("too many windows on this folder")


class _Opened(QObject):
    done = Signal(object)  # (cfg, backend) or the exception, from the worker thread


class Opening(Glass):
    """Why a folder could not be opened, with 打开文件夹 to choose another (opening itself shows nothing)."""
    choose = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, radius=28, padding=26, sheen=False)
        self.setMinimumWidth(360)
        self.setMaximumWidth(520)
        from codedoctor.desktop.team_ui import Figure

        self.body.addWidget(hbox(None, Figure("lumen", 120), None))
        self.text = label("", size=15, color=C["text2"], wrap=True)
        self.text.setAlignment(Qt.AlignCenter)
        self.why = label("", size=13, color=C["red"], wrap=True, selectable=True)
        self.body.addWidget(self.text)
        self.body.addWidget(self.why)
        self.pick = QPushButton(tr("open_folder"))
        self.pick.setObjectName("Primary")
        self.pick.setMinimumHeight(38)
        self.pick.setCursor(Qt.PointingHandCursor)
        self.pick.clicked.connect(self.choose.emit)
        self.body.addWidget(hbox(None, self.pick))

    def failed(self, name: str, why: str) -> None:
        self.text.setText(tr("open_failed", name=name) if name else tr("open_failed_any"))
        self.why.setText(why)
        self.pick.show()


class Launcher(QMainWindow):
    """The greeting and first-run setup (once), and the card for a folder that could not be opened, on the same
    wallpaper as the main window. While a folder opens it is hidden and nothing else is on the screen."""
    opened = Signal(object, object, object)  # (config, backend, task id to show or None)

    def __init__(self, backend_factory, config: str | None = None, task: str | None = None):
        super().__init__()
        from codedoctor.desktop.app import app_icon

        self.backend_factory = backend_factory
        self.setWindowTitle("Lumen")
        self.setWindowIcon(app_icon())
        self.ui = ui_prefs.load()
        motion.set_reduced(self.ui["reduced_motion"])
        backdrop = Atmosphere()
        backdrop.set_wallpaper(self.ui["wallpaper"])
        bl = QVBoxLayout(backdrop)
        bl.setContentsMargins(40, 40, 40, 40)
        self.stack = QStackedWidget()
        bl.addWidget(self.stack)
        self.setCentralWidget(backdrop)
        self.opening = Opening()
        self.opening.choose.connect(self.choose_folder)
        self.opening_screen = self._centered(self.opening, 3)
        self.stack.addWidget(self.opening_screen)
        self.setup_screen = None
        self._busy = False
        self.show_me = self.show  # how the card comes on screen (app.main places it like the main window)
        from codedoctor.desktop import web_chat

        self.web = None
        if web_chat.enabled(self.ui):  # the greeting, the setup and the card are the window's own page (web_onboarding.py)
            from codedoctor.desktop.web_onboarding import OnboardingView

            self.web = OnboardingView(self)
            self.setCentralWidget(self.web)
        if projects.load_setup() is None and self.web is not None:
            self.welcome_screen = True  # the page shows the greeting; _after_welcome goes on to the setup
            self.web.show_page({"page": "welcome"})
        elif projects.load_setup() is None:  # the first time: say hello, then ask the two things there are to ask
            from codedoctor.desktop.welcome import Welcome

            self.welcome = Welcome(reduced=self.ui["reduced_motion"])
            self.welcome.setMinimumHeight(520)
            self.welcome.proceed.connect(self._after_welcome)
            self.welcome_screen = self._centered(self.welcome)
            self.stack.addWidget(self.welcome_screen)
            self.stack.setCurrentWidget(self.welcome_screen)
        else:
            self.welcome_screen = None
            if config:
                self.open_config(config, task)
            else:
                self.open_default()

    # --- screens ------------------------------------------------------------------------------

    @staticmethod
    def _centered(card: QWidget, weight: int = 8) -> QWidget:
        screen = QWidget()
        sl = QVBoxLayout(screen)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addStretch(1)
        sl.addWidget(hbox(None, card, None), weight)
        sl.addStretch(1)
        return screen

    def _show(self, screen: QWidget) -> None:
        self.stack.setCurrentWidget(screen)
        motion.enter(screen, duration=380, dy=16)

    def _after_welcome(self) -> None:
        if self.welcome_screen is None:
            return  # proceed fires from a button and again when the greeting completes
        if self.web is not None:
            self.welcome_screen = None
            self.web.show_page({"page": "setup"})
            return
        screen, self.welcome_screen = self.welcome_screen, None
        self._setup()
        self.stack.removeWidget(screen)
        screen.hide()
        screen.deleteLater()

    def _setup(self) -> None:
        """The first-run card (built again in the new language when the user picks one)."""
        from codedoctor.desktop.first_run import FirstRun

        if self.setup_screen is not None:
            old, self.setup_screen = self.setup_screen, None
            self.stack.removeWidget(old)
            old.hide()
            old.deleteLater()
        card = FirstRun()
        card.relanguage.connect(self._setup)
        card.finished.connect(self.open_default)
        self.setup_screen = self._centered(card)
        self.stack.addWidget(self.setup_screen)
        self._show(self.setup_screen)

    # --- open ---------------------------------------------------------------------------------

    def open_default(self) -> None:
        """The folder opened last, else ~/Lumen."""
        try:
            path = projects.last_opened() or str(projects.for_folder(projects.workspace()))
        except Exception as e:  # shown on the card, with 打开文件夹 to choose one (once the window's owner is set up)
            why = f"{type(e).__name__}: {e}"
            QTimer.singleShot(0, lambda: self._failed("", why))
            return
        self.open_config(path)

    def choose_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(self, tr("open_folder").rstrip("…."), str(Path.home()))
        if folder:
            try:
                path = projects.for_folder(folder)
            except Exception as e:
                self._failed(Path(folder).name, f"{type(e).__name__}: {e}")
                return
            self.open_config(str(path))

    def open_config(self, path: str, task: str | None = None) -> None:
        """Load the configuration and start its service on a worker thread; then `opened` (on the UI thread). Nothing
        shows meanwhile: this card goes away, and the window that asked for another folder is closing."""
        if self._busy:
            return
        self._busy = True
        try:
            name = config_mod.load_raw(path)["project"]["name"]
        except Exception:
            name = Path(path).stem
        app = QApplication.instance()
        if app is not None:  # no window on the screen for a moment is not the end of the program
            app.setQuitOnLastWindowClosed(False)
        self.hide()
        bridge = self._bridge = _Opened()
        bridge.done.connect(lambda result: self._opened(result, path, task, name))
        factory = self.backend_factory

        def work():
            try:
                from codedoctor.desktop import projects

                try:
                    projects.ensure_team(path)  # the Lumen team joins projects made before it existed
                except Exception:  # a configuration it cannot extend still opens as it is
                    pass
                result = another_window(config_mod.load(path), factory)
            except Exception as e:  # shown on the card, never raised into Qt
                result = e
            bridge.done.emit(result)

        threading.Thread(target=work, daemon=True, name="codedoctor-open").start()

    def _opened(self, result, path: str, task: str | None, name: str = "") -> None:
        from codedoctor.store.lock import AlreadyRunning

        self._busy = False
        if isinstance(result, AlreadyRunning):
            self._failed(name, "这个文件夹打开的窗口太多了，先关掉几个。")
            return
        if isinstance(result, Exception):
            self._failed(name, f"{type(result).__name__}: {result}")
            return
        cfg, backend = result
        projects.register(cfg.name, path, str(cfg.root))
        try:
            self.opened.emit(cfg, backend, task)  # the main window is on the screen when this returns
        finally:
            self._quit_with_last_window()
        if second_window(cfg):  # Haiku check item 6: a second window keeps its chats apart - said, not silent
            from codedoctor.desktop.dialogs import notice

            notice(None, tr("第二个窗口"), tr("这个项目已经在另一个 Lumen 窗口里打开着。这个窗口的对话和任务记在另一份记录里，"
                                           "两个窗口的历史互不相通；要看全部对话，请只用一个窗口。"), kind="warning")
        if not any(w.isVisible() for w in QApplication.topLevelWidgets() if isinstance(w, QMainWindow)):
            # the window failed to build (the error is in crash.log): never a program running with nothing on screen
            self._failed(name, "窗口没能建起来，原因记在 ~/.codedoctor/crash.log。")

    def _failed(self, name: str, why: str) -> None:
        """The one card there is: why it did not open, with 打开文件夹."""
        if self.web is not None:
            self.web.show_page({"page": "failed", "title": tr("open_failed", name=name) if name else tr("open_failed_any"), "why": why})
            self.show_me()
            self._quit_with_last_window()
            return
        self.opening.failed(name, why)
        self.stack.setCurrentWidget(self.opening_screen)
        self.show_me()
        self._quit_with_last_window()

    @staticmethod
    def _quit_with_last_window() -> None:
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(True)
