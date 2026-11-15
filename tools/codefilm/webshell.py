"""A tool's window as a web page (2026-11-11): the user asked for every tool to look like the AI apps people know, with
no Qt controls left. The window is an empty Qt frame holding one web view; the page (ui_dist/, built from ui/ with
tools/webkit) draws everything, and talks to the tool's Python over QWebChannel - one call and one signal:

    page -> Python   tool.call(name, json_args)  runs handler.api_<name>(**args), answers its result as JSON
    Python -> page   tool.event(json)            {"type": ..., ...}: handler.emit(type, **data)

The handler is the tool's own logic (a plain object); it gets `emit` and `shell` set on it. Before the window closes,
handler.unsaved() is asked; if it says there is something unsaved the page asks the user (event "close_ask") and calls
close_window(save) back.

浅色 / 深色 follows Lumen: `--mode light|dark` on the command line, else $LUMEN_MODE, else "mode" in
~/.codedoctor/ui.json (Lumen's desktop/prefs.py; $CODEDOCTOR_HOME moves it), which is watched so a change in Lumen's
settings shows at once. Inside Lumen (LUMEN_EMBED=1) the window is taken in as before (embed.py).

Every tool carries this same file (tools/webkit/webshell.py is the original; tools/webkit/build.mjs copies it).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

from PySide6.QtCore import QObject, QTimer, QUrl, Qt, Signal, Slot

PAPER = {'light': '#ffffff', 'dark': '#1c1c1f'}


# --- 浅色 / 深色 ----------------------------------------------------------------------------------------------------
def ui_json() -> Path:
    return Path(os.environ.get('CODEDOCTOR_HOME') or Path.home() / '.codedoctor') / 'ui.json'


def lumen_mode() -> str:
    try:
        mode = json.loads(ui_json().read_text(encoding='utf-8')).get('mode')
    except (OSError, ValueError, AttributeError):
        mode = None
    return mode if mode in PAPER else 'light'


def take_mode(argv: list) -> tuple[str | None, list]:
    """`--mode dark` / `--mode=light` / `--dark` / `--light` out of the arguments: (the mode or None, the rest)."""
    rest, mode, skip = [], None, False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a in ('--dark', '--light'):
            mode = a[2:]
        elif a.startswith('--mode='):
            mode = a.split('=', 1)[1]
        elif a == '--mode' and i + 1 < len(argv):
            mode, skip = argv[i + 1], True
        else:
            rest.append(a)
    return (mode if mode in PAPER else None), rest


def fixed_mode(argv_mode: str | None) -> str | None:
    """A mode the window keeps (from the command line or $LUMEN_MODE), or None to follow Lumen's setting."""
    env = os.environ.get('LUMEN_MODE', '').strip().lower()
    return argv_mode or (env if env in PAPER else None)


# --- the bridge -----------------------------------------------------------------------------------------------------
class Api(QObject):
    event = Signal(str)

    def __init__(self, handler, shell):
        super().__init__()
        self.handler = handler
        self.shell = shell

    @Slot(str, str, result=str)
    def call(self, name: str, args: str) -> str:
        fn = getattr(self.handler, f'api_{name}', None) or getattr(self.shell, f'api_{name}', None)
        if fn is None:
            return json.dumps({'__error': f'no such call: {name}'})
        try:
            result = fn(**(json.loads(args) if args else {}))
        except Exception as e:  # noqa: BLE001 - the page gets the reason, the console the whole story
            traceback.print_exc()
            return json.dumps({'__error': f'{type(e).__name__}: {e}'}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False, default=str)


def make_app(argv: list | None = None):
    """The application, with what the web view needs set before it exists."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication
    import PySide6.QtWebEngineWidgets  # noqa: F401  (must be loaded before the application is made)

    app = QApplication.instance()
    if app is None:
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
        app = QApplication((argv or sys.argv)[:1])
        try:  # a dark Windows made unstyled text white on white (内容看不见); these windows are light, whatever the system is
            app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        except (AttributeError, RuntimeError):
            pass
    return app


def _window_class():
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtGui import QColor, QDesktopServices, QIcon
    from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

    class Shell(QMainWindow):
        """The empty frame: one web view, the bridge, the mode, closing."""

        def __init__(self, handler, title: str, dist: Path, size=(1280, 820), minimum=(720, 480), icon: Path | None = None, mode: str | None = None, query: dict | None = None):
            super().__init__()
            self.handler = handler
            self.fixed = mode
            self.mode = mode or lumen_mode()
            self.closing = False
            self.setWindowTitle(title)
            if icon and Path(icon).is_file():
                self.setWindowIcon(QIcon(str(icon)))
            self.resize(*size)
            self.setMinimumSize(*minimum)
            self.view = QWebEngineView(self)
            s = self.view.settings()
            s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
            self.view.setContextMenuPolicy(Qt.NoContextMenu)  # the page has its own menus
            self.view.page().setBackgroundColor(QColor(PAPER[self.mode]))  # nothing white flashes in the dark mode
            self.api = Api(handler, self)
            self.channel = QWebChannel(self)
            self.channel.registerObject('tool', self.api)
            self.view.page().setWebChannel(self.channel)
            self.setCentralWidget(self.view)
            handler.shell = self
            handler.emit = self.emit
            url = QUrl.fromLocalFile(str(Path(dist) / 'index.html'))
            q = {'mode': self.mode, **(query or {})}
            url.setQuery('&'.join(f'{k}={v}' for k, v in q.items()))
            self.view.load(url)
            self.loaded = False
            self.view.loadFinished.connect(self._loaded)
            self._ui_time = self._ui_mtime()
            self.watcher = QTimer(self)
            self.watcher.timeout.connect(self._follow_mode)
            self.watcher.start(1000)

        # --- talking to the page ------------------------------------------------------------------------------------
        def emit(self, kind: str, **data) -> None:
            self.api.event.emit(json.dumps({'type': kind, **data}, ensure_ascii=False, default=str))

        def js(self, code: str, done=None) -> None:
            self.view.page().runJavaScript(code, 0, done or (lambda _r: None))

        def _loaded(self, ok: bool) -> None:
            self.loaded = ok
            if ok:
                try:  # the page's words in Lumen's language (i18n.py + en.json)
                    import i18n
                    script = i18n.web_script(Path(__file__).resolve().parent, Path(__file__).resolve().parent / 'ui' / 'kit')
                    if script:
                        self.js(script)
                except ImportError:
                    pass
            self.emit('theme', mode=self.mode)

        # --- 浅色 / 深色 ------------------------------------------------------------------------------------------
        @staticmethod
        def _ui_mtime() -> float:
            try:
                return ui_json().stat().st_mtime
            except OSError:
                return 0.0

        def _follow_mode(self) -> None:
            if self.fixed:
                return
            t = self._ui_mtime()
            if t == self._ui_time:
                return
            self._ui_time = t
            self.set_mode(lumen_mode())

        def set_mode(self, mode: str) -> None:
            if mode not in PAPER or mode == self.mode:
                return
            self.mode = mode
            self.view.page().setBackgroundColor(QColor(PAPER[mode]))
            self.emit('theme', mode=mode)

        # --- what the page may ask of the window --------------------------------------------------------------------
        def api_mode(self) -> dict:
            return {'mode': self.mode}

        def api_open_path(self, path: str) -> dict:
            p = Path(path)
            if not p.exists():
                return {'ok': False, 'error': f'还没有 {p.name}'}
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
            return {'ok': True}

        def api_open_url(self, url: str) -> dict:
            QDesktopServices.openUrl(QUrl(url))
            return {'ok': True}

        def api_copy(self, text: str) -> dict:
            QApplication.clipboard().setText(text)
            return {'ok': True}

        def api_paste(self) -> dict:
            return {'text': QApplication.clipboard().text()}

        def api_close_window(self, save: bool = False) -> dict:
            """The answer to "close_ask": save first (when asked) and close; a failed save keeps the window."""
            if save and hasattr(self.handler, 'save_all') and not self.handler.save_all():
                return {'ok': False}
            self.closing = True
            QTimer.singleShot(0, self.close)
            return {'ok': True}

        # --- the system's own pickers (files live on the computer, so these stay the computer's) --------------------
        def pick_folder(self, title: str, start: str = '') -> Path | None:
            folder = QFileDialog.getExistingDirectory(self, title, start)
            return Path(folder) if folder else None

        def pick_file(self, title: str, filters: str = '', start: str = '') -> Path | None:
            path, _ = QFileDialog.getOpenFileName(self, title, start, filters)
            return Path(path) if path else None

        def pick_files(self, title: str, filters: str = '', start: str = '') -> list:
            paths, _ = QFileDialog.getOpenFileNames(self, title, start, filters)
            return [Path(p) for p in paths]

        def save_as(self, title: str, start: str = '', filters: str = '') -> Path | None:
            path, _ = QFileDialog.getSaveFileName(self, title, start, filters)
            return Path(path) if path else None

        # --- closing ------------------------------------------------------------------------------------------------
        def closeEvent(self, e):
            unsaved = getattr(self.handler, 'unsaved', None)
            if not self.closing and self.loaded and unsaved is not None and unsaved():
                e.ignore()
                self.emit('close_ask')
                return
            closing = getattr(self.handler, 'closing', None)
            if closing is not None:
                closing()
            super().closeEvent(e)

    return Shell


def window(handler, title: str, dist: Path, **kw):
    """The window, not shown yet (a check drives it offscreen)."""
    return _window_class()(handler, title, dist, **kw)


def run(handler, title: str, dist: Path, argv: list | None = None, **kw) -> int:
    """Make the application and the window, show it (or hand it to Lumen) and run."""
    mode, _rest = take_mode(list(argv if argv is not None else sys.argv[1:]))
    app = make_app()
    win = window(handler, title, dist, mode=fixed_mode(mode), **kw)
    import embed

    embed.show(win)
    return app.exec()
