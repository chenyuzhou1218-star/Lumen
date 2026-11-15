"""The panel on the right, in the React window (2026-11-11, the user's design): the built-in browser and the terminal, one
above the other when both are open, either alone filling the panel.

The page draws the panel; the browser's pages stay a real Chromium view lying over the room the page leaves for it (as an
@ tool's window does, web_chat.WebChat.place). The terminal is drawn by the page too (xterm.js): Python runs PowerShell in a
real console (conpty.py) and passes its output on (Bridge.term); the keys pressed go back (Bridge.term_input).

WebDock answers what MainWindow asked of the Qt panel (dock.RightDock): isVisible, current, show_tab, hide_dock, toggle,
ai_ran, shutdown, closed, to_chat.
"""

from __future__ import annotations

import json
import os
import time

from PySide6.QtCore import QObject, Signal

KEEP = 400_000  # characters of the console's output kept, so that a terminal drawn again shows the same screen


class Console(QObject):
    """PowerShell in a real console (conpty.Pty), in the project's folder, as the user: its own banner, prompt, colours and
    line editing. Its output arrives on a reading thread and is handed to the window's thread through `got`."""
    got = Signal(str)
    gone = Signal()

    def __init__(self, folder: str, cols: int = 100, rows: int = 30):
        super().__init__()
        self.args = (folder, cols, rows)
        self.pty = None

    def start(self) -> None:
        """Only after the window's signals are connected: the shell's first words (its banner) must not go nowhere."""
        folder, cols, rows = self.args
        if os.name == "nt":
            from codedoctor.desktop import conpty

            self.pty = conpty.Pty("powershell.exe -NoProfile", folder, cols, rows, on_output=self._got, on_exit=self._gone)
        else:  # macOS, Linux: the user's own shell (posixpty.py)
            from codedoctor.desktop import posixpty

            self.pty = posixpty.Pty("", folder, cols, rows, on_output=self._got, on_exit=self._gone)

    def _got(self, text: str) -> None:
        try:
            self.got.emit(text)
        except RuntimeError:  # the window closed while the shell still wrote
            pass

    def _gone(self) -> None:
        try:
            self.gone.emit()
        except RuntimeError:
            pass

    def write(self, data: str) -> None:
        if self.pty is not None:
            self.pty.write(data)

    def resize(self, cols: int, rows: int) -> None:
        if self.pty is not None:
            self.pty.resize(cols, rows)

    def close(self) -> None:
        if self.pty is not None:
            self.pty.close()


class WebDock(QObject):
    closed = Signal()
    to_chat = Signal(str)

    def __init__(self, web, browser, folder: str):
        super().__init__()
        self.web, self.browser, self.folder = web, browser, folder
        self.open: list[str] = []      # "browser" and / or "terminal", in the order they were opened
        self.current = "browser"       # the one opened last
        self.console: Console | None = None
        self.log = ""                  # what the console wrote so far, for a terminal drawn again
        self.size = (100, 30)          # columns and rows, as the page measured them
        self.heard: list[tuple[str, str]] = []  # (who, command): what the team ran, listed above the terminal

    # --- what MainWindow asks ------------------------------------------------------------------------------------------

    def isVisible(self) -> bool:  # noqa: N802 (as the Qt panel)
        return bool(self.open)

    def show_tab(self, key: str) -> None:
        if key not in self.open:
            self.open.append(key)
        self.current = key
        if key == "terminal" and self.console is None:
            self._start()
        if key == "browser":
            self.browser.ensure()
        self._changed()

    def toggle(self, key: str) -> None:
        """The sidebar's two small buttons: each opens or closes its own half."""
        if key in self.open:
            self.closed_at = {**getattr(self, "closed_at", {}), key: time.monotonic()}  # the AI does not reopen it at once
            self.open.remove(key)
            if self.open:
                self.current = self.open[-1]
            self._changed()
            if not self.open:
                self.closed.emit()
        else:
            self.show_tab(key)

    def hide_dock(self) -> None:
        self.open = []
        self._changed()
        self.closed.emit()

    def ai_ran(self, who: str, command: str) -> None:
        """What the team runs is listed above the terminal, and written into the terminal itself in colour (the user,
        2026-11-14: the AI's terminal work goes into the panel on the side, where it can be watched); the panel opens for it
        unless the user closed it a moment ago. It is shown, not typed into the user's own shell."""
        self.heard = (self.heard + [(who, command)])[-200:]
        self.web.bridge.term.emit(json.dumps({"ran": {"who": who, "command": command}}, ensure_ascii=False))
        self.ai_opens("terminal")
        line = command.replace("\r", "").replace("\n", "\r\n    ")
        self.web.bridge.term.emit(json.dumps({"out": f"\r\n\x1b[38;5;214m● {who}\x1b[0m \x1b[2m›\x1b[0m {line}\r\n"}, ensure_ascii=False))

    def ai_opens(self, key: str) -> None:
        """The AI is working in this half (terminal or browser): it opens, unless the user closed it in the last minute."""
        if key in self.open or time.monotonic() - getattr(self, "closed_at", {}).get(key, -1e9) < 60:
            return
        self.show_tab(key)

    def shutdown(self) -> None:
        if self.console is not None:
            self.console.close()
            self.console = None

    # --- the terminal ---------------------------------------------------------------------------------------------------

    def _start(self) -> None:
        try:
            self.console = Console(self.folder, *self.size)
            self.console.got.connect(self._out)
            self.console.gone.connect(self._gone)
            self.console.start()
        except OSError as e:  # shown in the terminal itself
            self.console = None
            self._out(f"\r\n\x1b[31m{e}\x1b[0m\r\n")
            return

    def _out(self, text: str) -> None:
        self.log = (self.log + text)[-KEEP:]
        self.web.bridge.term.emit(json.dumps({"out": text}, ensure_ascii=False))

    def _gone(self) -> None:
        """The shell ended (exit): said in the terminal; the next key starts a new one in the same folder."""
        if self.console is not None:
            self.console.close()
            self.console = None
        self.web.bridge.term.emit(json.dumps({"exit": True}))

    def term_state(self) -> dict:
        return {"log": self.log, "alive": self.console is not None, "ran": [{"who": w, "command": c} for w, c in self.heard[-50:]]}

    def type(self, data: str) -> None:
        """Keys pressed in the terminal, as the console reads them."""
        if self.console is None:
            self.log = ""
            self._start()
            return
        self.console.write(data)

    def resize(self, cols: int, rows: int) -> None:
        self.size = (max(20, int(cols)), max(5, int(rows)))
        if self.console is not None:
            self.console.resize(*self.size)

    def interrupt(self) -> None:
        if self.console is not None:
            self.console.write("\x03")

    def _changed(self) -> None:
        self.web.push_side(force=True)
