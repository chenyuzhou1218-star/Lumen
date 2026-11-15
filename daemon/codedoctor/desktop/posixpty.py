"""The terminal on macOS and Linux: the user's own shell in a pseudo terminal (the standard `pty` module), with the same
face as conpty.Pty on Windows (write, resize, running, close; on_output(text) from a reading thread, on_exit())."""

from __future__ import annotations

import codecs
import fcntl
import os
import pty
import signal
import struct
import termios
import threading


def shell() -> str:
    return os.environ.get("SHELL") or ("/bin/zsh" if os.path.exists("/bin/zsh") else "/bin/bash")


class Pty:
    def __init__(self, command: str, cwd: str, cols: int = 100, rows: int = 30, on_output=None, on_exit=None):
        self.on_output, self.on_exit = on_output, on_exit
        self.alive = False
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # the shell, as a login-less interactive one
            try:
                os.chdir(cwd if os.path.isdir(cwd) else os.path.expanduser("~"))
                os.environ["TERM"] = "xterm-256color"
                os.execv(shell(), [shell(), "-i"])
            finally:
                os._exit(127)
        self.alive = True
        self.resize(cols, rows)
        threading.Thread(target=self._read, daemon=True, name="posix-pty").start()

    def _read(self) -> None:
        dec = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                break
            if not data:
                break
            if self.on_output:
                self.on_output(dec.decode(data))
        self.alive = False
        try:
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        try:
            os.close(self.fd)  # closed here, by the thread that reads it: never under its feet
        except OSError:
            pass
        if self.on_exit:
            self.on_exit()

    def write(self, text: str) -> None:
        if self.alive:
            try:
                os.write(self.fd, text.encode("utf-8"))
            except OSError:
                pass

    def resize(self, cols: int, rows: int) -> None:
        try:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", max(5, rows), max(20, cols), 0, 0))
        except OSError:
            pass

    def running(self) -> bool:
        return self.alive

    def close(self) -> None:
        self.alive = False
        try:
            os.kill(self.pid, signal.SIGHUP)  # the shell ends, the reading thread sees it and closes the descriptor
        except OSError:
            pass
