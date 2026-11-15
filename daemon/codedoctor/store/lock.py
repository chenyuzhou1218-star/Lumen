"""One running service per project data directory.

Two services on the same database would both take messages from the same
inboxes and run every task twice. The lock is an OS-level file lock, so it is
released automatically if the process dies.
"""

from __future__ import annotations

import os
from pathlib import Path


class AlreadyRunning(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "service.lock"
        self._fh = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise AlreadyRunning(f"Lumen is already running for this project ({self.path.parent})") from None
        self._fh = fh

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None
