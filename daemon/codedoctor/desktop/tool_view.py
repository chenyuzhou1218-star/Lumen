"""A tool's own window inside Lumen, above the chat (2026-11-10, the user: @CodePage, @Code3D ... should show the tool's
main view on top and the message box below, not answer that it cannot run here).

The tool runs in its own process as before (tools/<tool>/editor.py, following the project folder). Started with
LUMEN_EMBED=1 it never puts a window on the desktop: it makes its window frameless and off-screen and prints its
handle (embed.py in each tool); Lumen takes that window into this widget (QWindow.fromWinId). One process per tool and
folder, kept while Lumen runs, so switching back is immediate.
"""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from codedoctor.desktop.theme import C

pending: str | None = None  # a tool to show again after the window reopened to allow it (MainWindow.allow_tools)
# the @ tools that have a window, and how each follows a folder
ARGS = {"codecut": ["--follow", "{root}", "--compact"], "codetools": [], "codepdf": []}
WINDOWED = ("codecut", "code3d", "codesound", "codepage", "codegame", "codedeck", "codedata", "codecad", "codefilm", "codetools", "codepdf")
# Tools with a window of their own that is not tied to a project folder (no editor.py --watch): CodeTools, CodePDF. Both have
# embed.py and print LUMEN_HWND like the others, so they sit in the right pane; they take no arguments here.
NO_FOLDER = ("codetools", "codepdf")


def home(tool: str) -> Path | None:
    from codedoctor import makers, model3d, video

    if tool == "codecut":
        return video.home()
    if tool == "code3d":
        return model3d.home()
    return makers.home(tool) if tool in makers.MAKERS and (makers.MAKERS[tool].window or tool in NO_FOLDER) else None


def window_tool(keys) -> str | None:
    """The first of these @ tools that has a window here."""
    return next((k for k in keys or () if k in WINDOWED and home(k) is not None), None)


def window_tools(keys) -> list[str]:
    """All of these @ tools that have a window here, each once, in the order asked."""
    out: list[str] = []
    for k in keys or ():
        if k in WINDOWED and k not in out and home(k) is not None:
            out.append(k)
    return out


def needs_permission(tool: str, config) -> bool:
    """Never: there is no 允许 bar any more. A tool changes files and runs commands as the user's approval choice (批准方式) for
    the chat says; an old configuration that says "deny" reads as the allowlist (config.normalize_raw)."""
    return False


STANDALONE = "这个工具在它自己的窗口里打开了（这个系统不能把它放进 Lumen 里）。"


class _Started(QObject):
    hwnd = Signal(str, int)   # key, window handle
    failed = Signal(str, str)


class ToolView(QWidget):
    """The tool's window, a thin row above it when the project must first allow it to work, and a word while it starts.
    In the React window (frameless = True) the page draws the row, the word and any error (web_chat.WebChat): this widget
    is then only the tool's own window, laid where the page leaves room, and `changed` tells the page how it stands."""
    changed = Signal()  # starting, ready or failed, or the permission row came or went

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToolView")
        self.setStyleSheet(f"#ToolView {{ background: white; border-bottom: 1px solid {C['border']}; }}")
        self.procs: dict[str, subprocess.Popen] = {}
        self.pages: dict[str, QWidget] = {}
        self.hwnds: dict[str, int] = {}  # each tool's own window handle (the AI works in it: sandbox_windows)
        self.current: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.stack = QStackedWidget()
        self.wait = QLabel("")
        self.wait.setAlignment(Qt.AlignCenter)
        self.wait.setStyleSheet(f"color: {C['text3']}; font-size: 14px;")
        self.stack.addWidget(self.wait)
        lay.addWidget(self.stack, 1)
        self.bridge = _Started()
        self.bridge.hwnd.connect(self._embed)
        self.bridge.failed.connect(self._failed)
        self.frameless = False
        self.info: dict = {}  # what the page shows: name, ask (the permission row's words, or ""), state, why

    def show_tool(self, tool: str, root: str, config) -> None:
        from codedoctor.desktop.composer import MENTIONS

        name = MENTIONS.get(tool, tool)
        key = f"{tool}:{Path(root).resolve()}".lower()
        self.current = key
        self._reap(key)
        self.info = {"name": name, "ask": "", "state": "ready" if key in self.pages else "starting", "why": ""}
        if key in self.pages:
            self.stack.setCurrentWidget(self.pages[key])
        else:
            self.wait.setText(f"正在打开 {name}……")
            self.stack.setCurrentWidget(self.wait)
            self._start(tool, root, key)
        if not self.frameless:  # in the React window web_chat._apply alone shows and hides it (two callers made it flash)
            self.setVisible(True)
        self.changed.emit()

    def _reap(self, key: str) -> bool:
        """A tool that quit has a dead window handle: its page is taken away (the blank window must not lie over the chat) and
        the next time it is asked for it starts again. True when something was removed."""
        proc = self.procs.get(key)
        if key not in self.pages or proc is None or proc.poll() is None:
            return False
        dead = self.pages.pop(key)
        self.stack.removeWidget(dead)
        dead.hide()
        dead.deleteLater()
        self.procs.pop(key, None)
        return True

    def ready(self) -> bool:
        """The tool's own window is in place and its program is still running (until then the page shows that it is starting,
        or why it did not)."""
        if self.current is None or self.info.get("state") != "ready":
            return False
        if self._reap(self.current):
            self.info = {**self.info, "state": "failed", "why": "这个工具已经退出了。再点一次 @ 打开它。"}
            return False
        return True

    def _failed(self, key: str, why: str) -> None:
        if key != self.current:
            return
        self.wait.setText(why)
        self.info = {**self.info, "state": "failed", "why": why}
        self.changed.emit()

    def _start(self, tool: str, root: str, key: str) -> None:
        if key in self.procs and self.procs[key].poll() is None:
            if os.name != "nt":  # started before, in a window of its own: say so again instead of staying at 正在打开
                self.bridge.failed.emit(key, STANDALONE)
            return
        from codedoctor import video

        where = home(tool)
        args = [a.replace("{root}", str(Path(root).resolve())) for a in ARGS.get(tool, ["--watch", "{root}"])]
        env = {**os.environ, "LUMEN_EMBED": "1", "PYTHONIOENCODING": "utf-8"}
        if os.name != "nt":
            # No HWND to take over here (macOS): the tool opens as a window of its own beside Lumen, started once.
            env.pop("LUMEN_EMBED")
            try:
                self.procs[key] = subprocess.Popen([video.python(), str(where / "editor.py"), *args], cwd=str(where), env=env,
                                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            except OSError as e:
                self.bridge.failed.emit(key, f"打不开：{e}")
                return
            self.bridge.failed.emit(key, STANDALONE)
            return
        try:
            proc = subprocess.Popen([video.python(), str(where / "editor.py"), *args], cwd=str(where), env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            self.bridge.failed.emit(key, f"打不开：{e}")
            return
        from codedoctor.desktop import job

        job.adopt(proc)  # it ends with Lumen even if Lumen cannot close it (desktop/job.py)
        self.procs[key] = proc

        def read():
            shaken = False
            for raw in proc.stdout:  # after the handshake it is read on and thrown away: a full pipe would stop the tool
                if shaken:
                    continue
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("LUMEN_HWND="):
                    try:
                        self.bridge.hwnd.emit(key, int(line.split("=", 1)[1]))
                        shaken = True
                    except (RuntimeError, ValueError):
                        pass
            if not shaken:
                try:
                    self.bridge.failed.emit(key, "这个工具没有打开（它的窗口没有出来）。")
                except RuntimeError:
                    pass
        threading.Thread(target=read, daemon=True, name=f"tool-{tool}").start()

    def sandbox_windows(self) -> list:
        """The tool window on the screen now, for the AI to work in (computer/gate.py `sandbox`): read from the agents' thread,
        so only plain values and Win32 calls here, nothing of Qt."""
        key, hwnd = self.current, self.hwnds.get(self.current or "")
        proc = self.procs.get(key or "")
        if not hwnd or proc is None or proc.poll() is not None or os.name != "nt":
            return []
        import ctypes
        from ctypes import wintypes

        from codedoctor.computer.desktop import Window

        u = ctypes.windll.user32
        if not u.IsWindowVisible(wintypes.HWND(hwnd)):
            return []
        r = wintypes.RECT()
        if not u.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)) or r.right - r.left < 20:
            return []
        name = self.info.get("name") or key
        return [Window(handle=hwnd, title=f"{name} (Lumen)", pid=proc.pid, rect=(r.left, r.top, r.right, r.bottom))]

    def _embed(self, key: str, hwnd: int) -> None:
        self.hwnds[key] = hwnd
        win = QWindow.fromWinId(hwnd)
        if win is None:  # this platform cannot take another program's window in (off-screen runs): said, never raised
            if key == self.current:
                self.info = {**self.info, "state": "failed", "why": "这个工具的窗口没法放进 Lumen。"}
                self.changed.emit()
            return
        win.setFlags(Qt.FramelessWindowHint)
        holder = QWidget.createWindowContainer(win, self.stack)
        holder.setFocusPolicy(Qt.StrongFocus)
        self.pages[key] = holder
        self.stack.addWidget(holder)
        if key == self.current:
            self.stack.setCurrentWidget(holder)
            self.info = {**self.info, "state": "ready"}
            self.changed.emit()

    def hide_tool(self) -> None:
        self.current = None
        if not self.frameless:
            self.setVisible(False)

    def shutdown(self) -> None:
        """Lumen closes: the tools' processes go with it (their windows live inside this one)."""
        for proc in self.procs.values():
            if proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
        self.procs.clear()
