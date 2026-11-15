"""Where agents may work besides the project folder: anywhere on this computer (the user, 2026-11-14: "以后再也不让我再见到
那个权限的问题了 ... 帮我清一下 C 盘都不行"). There is no forbidden place any more - not the system drive, not C:\\Windows.
What protects the user is their 批准方式 (computer/gate.asks_user): 全部问我 asks before every change, 帮我审查 before
every deletion (and every mouse or keyboard action), 完全放开 never asks.
"""

from __future__ import annotations

import os
import string
from pathlib import Path


def dirs() -> list[Path]:
    """The folders an engine is opened to besides the project: the user's home and the root of every drive."""
    out = [Path.home()]
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            if root.exists():
                out.append(root)
    else:
        out.append(Path("/"))
        for base in ("/Volumes", "/mnt", "/media"):
            p = Path(base)
            if p.is_dir():
                out += [c for c in p.iterdir() if c.is_dir()]
    return out


def forbidden(path: Path) -> bool:
    """Nothing is forbidden (kept for the callers that ask)."""
    return False


def allowed(path: Path) -> bool:
    """May an agent work here? Anywhere it can name."""
    try:
        path.resolve()
    except OSError:
        return False
    return True
