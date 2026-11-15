"""Every call the page makes reaches Python (a few seconds, no model, no window shown).

The page talks to Python through QWebChannel: only methods marked @Slot can be called from it. On 2026-11-14 a helper was put
between `send` and its @Slot, so the mark sat on the helper: pressing Enter emptied the box and nothing was sent, and no test
noticed (they called `send` from Python, where the mark does not matter). This reads every call in web/src/bridge.js and
checks it is a slot of Bridge (desktop/web_chat.py) or of the first-run page (desktop/web_onboarding.py).

    .venv\\Scripts\\python tools\\check_bridge.py        exit code 0: all reach; 1: names the ones that do not

It runs before every commit (.git/hooks/pre-commit, installed by: .venv\\Scripts\\python tools\\check_bridge.py --install).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def slots(cls) -> set[str]:
    mo = cls.staticMetaObject
    return {bytes(mo.method(i).name()).decode() for i in range(mo.methodCount())}


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "daemon"))
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from codedoctor.desktop import web_chat, web_onboarding

    have = slots(web_chat.Bridge)
    for name in dir(web_onboarding):
        obj = getattr(web_onboarding, name)
        if isinstance(obj, type) and hasattr(obj, "staticMetaObject") and obj.__module__ == web_onboarding.__name__:
            have |= slots(obj)
    js = (ROOT / "web" / "src" / "bridge.js").read_text(encoding="utf-8")
    called = set(re.findall(r"call\('([a-zA-Z_]+)'", js)) | set(re.findall(r"\bobj\.([a-zA-Z_]+)\(", js))
    missing = sorted(c for c in called if c not in have)
    if missing:
        print("The page calls these, and Python has no slot for them (the page would do nothing):", ", ".join(missing))
        return 1
    print(f"bridge ok: all {len(called)} calls of the page reach Python")
    return 0


def install() -> None:
    hook = ROOT / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\n# Lumen: every call of the page must reach Python (tools/check_bridge.py)\n"
                    "py=.venv/Scripts/python.exe; [ -x \"$py\" ] || py=.venv/bin/python\n"
                    "exec \"$py\" tools/check_bridge.py\n", encoding="utf-8", newline="\n")
    print(f"installed {hook}")


if __name__ == "__main__":
    if "--install" in sys.argv:
        install()
        sys.exit(0)
    sys.exit(main())
