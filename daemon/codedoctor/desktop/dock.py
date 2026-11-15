"""The panel on the right of the window (2026-11-05, the user's design): the built-in browser and a small terminal, side by
side with the chat instead of over it. Links clicked in a chat open here.

The terminal is a real PowerShell, kept alive between commands, so `cd` and variables stay. It runs in the project's folder
as the user, like any terminal; programs that need a full screen (vim) do not work in it, the rest does.
"""

from __future__ import annotations

import os
import re

from PySide6.QtCore import QProcess, QProcessEnvironment, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCursor
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QStackedWidget, QVBoxLayout, QWidget)

from codedoctor.desktop import icons
from codedoctor.desktop.theme import C, FONT_FAMILY, MONO_FAMILY

MARK = "\x1fLUMEN-DONE:"


class Terminal(QWidget):
    """Type a command, press Enter. ↑ ↓ go through what was typed; 停止 ends what is running."""
    to_chat = Signal(str)  # text the user wants to show Lumen

    def __init__(self, folder: str):
        super().__init__()
        self.folder = folder
        self.proc: QProcess | None = None
        self.buffer = ""
        self.busy = False
        self.history: list[str] = []
        self.at = 0
        self.setObjectName("Terminal")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(f"#Terminal {{ background: {C['term_bg']}; }}"
                           f"QPlainTextEdit#TermOut {{ background: {C['term_bg']}; border: none; border-radius: 0; color: {C['term_ink']}; padding: 10px 12px;"
                           f" font-family: {MONO_FAMILY}; font-size: 13px; selection-background-color: #dfe5ff; selection-color: #111113; }}"
                           f"QLineEdit#TermIn {{ background: transparent; border: none; color: #111113; font-family: {MONO_FAMILY}; font-size: 13px; padding: 0; }}"
                           f"QLabel#TermWhere {{ color: {C['accent']}; font-family: {MONO_FAMILY}; font-size: 13px; }}"
                           "QFrame#TermBar { background: #ffffff; border: none; border-top: 1px solid #ededee; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.out = QPlainTextEdit()
        self.out.setObjectName("TermOut")
        self.out.setReadOnly(True)
        self.out.setMaximumBlockCount(5000)
        self.out.setContextMenuPolicy(Qt.CustomContextMenu)
        self.out.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.out, 1)
        bar = QFrame()
        bar.setObjectName("TermBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 9, 12, 9)
        bl.setSpacing(8)
        self.where = QLabel("")
        self.where.setObjectName("TermWhere")
        bl.addWidget(self.where)
        self.edit = QLineEdit()
        self.edit.setObjectName("TermIn")
        self.edit.returnPressed.connect(self.run)
        self.edit.installEventFilter(self)
        bl.addWidget(self.edit, 1)
        lay.addWidget(bar)
        self.setFocusProxy(self.edit)

    def _menu(self, pos) -> None:
        """Right click: what was selected, or the last screenful, goes to the message box. An error message is one click from a question."""
        menu = self.out.createStandardContextMenu()
        picked = self.out.textCursor().selectedText().replace("\u2029", "\n")
        text = picked or "\n".join(self.out.toPlainText().splitlines()[-40:])
        menu.addSeparator()
        menu.addAction("把选中的发给 Lumen" if picked else "把最近的输出发给 Lumen").triggered.connect(lambda: self.to_chat.emit(f"```\n{text}\n```"))
        menu.exec(self.out.mapToGlobal(pos))

    def showEvent(self, e):
        super().showEvent(e)
        if self.proc is None:
            self.start()
        self.edit.setFocus()

    def start(self) -> None:
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(self.folder if os.path.isdir(self.folder) else os.path.expanduser("~"))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.ended)
        self.proc.start("powershell.exe", ["-NoLogo", "-NoProfile", "-NoExit", "-Command", "-"])
        self.busy = True
        self.send("[Console]::OutputEncoding=[Text.Encoding]::UTF8;$OutputEncoding=[Text.Encoding]::UTF8;$ProgressPreference='SilentlyContinue'")

    def send(self, command: str) -> None:
        self.proc.write((command + f"; [Console]::Out.Write(\"`n{MARK[0]}{MARK[1:]}\" + $PWD.Path + \"`n\")\n").encode("utf-8"))

    def run(self) -> None:
        text = self.edit.text().strip()
        if not text:
            return
        self.edit.clear()
        self.history.append(text)
        self.at = len(self.history)
        if text in ("cls", "clear"):
            self.out.clear()
            return
        if self.proc is None or self.proc.state() == QProcess.NotRunning:
            self.start()
        self.write(f"{self.where.text()} {text}\n", colour=True)
        self.busy = True
        self.send(text)

    def write(self, text: str, colour: bool = False) -> None:
        cur = self.out.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = cur.charFormat()
        fmt.setForeground(QColor(C["accent"] if colour else C["term_ink"]))
        cur.setCharFormat(fmt)
        cur.insertText(text)
        self.out.setTextCursor(cur)
        self.out.ensureCursorVisible()

    def read(self) -> None:
        self.buffer += bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace").replace("\r\n", "\n")
        while MARK in self.buffer:
            before, _, rest = self.buffer.partition(MARK)
            path, _, self.buffer = rest.partition("\n")
            if before.strip("\n"):
                self.write(before.rstrip("\n") + "\n")
            self.busy = False
            self.where.setText(f"{re.sub(r'.*[\\/]', '', path) or path} ›")
            self.where.setToolTip(path)
        if self.buffer and "\x1f" not in self.buffer and self.buffer.endswith("\n"):
            self.write(self.buffer)
            self.buffer = ""

    def ended(self, *_):
        self.read()
        self.busy = False

    def stop(self) -> None:
        """Ctrl+C: what runs goes, and a new shell takes over in the same folder."""
        if self.proc is not None:
            self.proc.finished.disconnect(self.ended)
            self.proc.kill()
            self.proc.waitForFinished(2000)
            self.proc.deleteLater()
            self.proc = None
        self.buffer = ""
        self.write("^C\n")
        self.start()

    def shutdown(self) -> None:
        if self.proc is not None:
            self.proc.finished.disconnect(self.ended)
            self.proc.kill()
            self.proc.waitForFinished(2000)
            self.proc = None

    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() == e.Type.KeyPress:
            if e.key() == Qt.Key_Up and self.history:
                self.at = max(0, self.at - 1)
                self.edit.setText(self.history[self.at])
                return True
            if e.key() == Qt.Key_Down and self.history:
                self.at = min(len(self.history), self.at + 1)
                self.edit.setText(self.history[self.at] if self.at < len(self.history) else "")
                return True
            if e.key() == Qt.Key_C and e.modifiers() & Qt.ControlModifier and not self.edit.hasSelectedText():
                self.stop()
                return True
        return super().eventFilter(obj, e)


class RightDock(QFrame):
    """浏览器 and 终端 on the right; both stay as they were when the panel closes."""
    closed = Signal()
    to_chat = Signal(str)

    def __init__(self, browser: QWidget, folder: str):
        super().__init__()
        self.setObjectName("RightDock")
        self.setMinimumWidth(340)
        self.folder = folder
        self.terminal: Terminal | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.stack = QStackedWidget()  # no title row: the two small buttons at the top left of the window open and close these
        self.browser = browser
        self.stack.addWidget(browser)
        lay.addWidget(self.stack, 1)
        self.current = "browser"
        self.setVisible(False)

    def ai_ran(self, who: str, command: str) -> None:
        """What the team runs shows here as well: the terminal is where you look to see what happened."""
        self.heard = (getattr(self, "heard", []) + [(who, command)])[-200:]
        if self.terminal is not None:
            self.terminal.write(f"[{who}] {command}\n", colour=True)

    def show_tab(self, key: str) -> None:
        if key == "terminal" and self.terminal is None:
            self.terminal = Terminal(self.folder)
            self.terminal.to_chat.connect(self.to_chat)
            self.stack.addWidget(self.terminal)
            for who, command in getattr(self, "heard", []):
                self.terminal.write(f"[{who}] {command}\n", colour=True)
        self.current = key
        self.stack.setCurrentWidget(self.terminal if key == "terminal" else self.browser)
        self.setVisible(True)
        if key == "terminal":
            self.terminal.setFocus()

    def toggle(self, key: str) -> None:
        if self.isVisible() and self.current == key:
            self.hide_dock()
        else:
            self.show_tab(key)

    def hide_dock(self) -> None:
        self.setVisible(False)
        self.closed.emit()

    def shutdown(self) -> None:
        if self.terminal is not None:
            self.terminal.shutdown()
