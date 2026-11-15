"""On this computer `python` and a double-click find Python 3.14, which has none of what the tools need; CodeCut's Python 3.12 has it all.
A tool started by the wrong one starts itself again with the right one."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys


def use(*needs: str) -> None:
    if all(importlib.util.find_spec(n) is not None for n in needs):
        return
    if os.environ.get('LUMEN_PY_FORWARDED') == '1':  # already handed over once: do not pass it back and forth between two Pythons
        print('{"ok": false, "error": "这个 Python 也没有 ' + '、'.join(needs) + '。"}', flush=True)
        sys.exit(1)
    venv = Path(__file__).resolve().parents[2] / '.venv'  # Lumen's own Python (Windows: Scripts/python.exe, macOS and Linux: bin/python)
    candidates = [os.environ.get('CODECUT_PYTHON'), venv / 'Scripts' / 'python.exe', venv / 'bin' / 'python',
                  Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Python' / 'Python312' / 'python.exe']
    for cand in candidates:
        if cand and Path(cand).is_file() and Path(cand).resolve() != Path(sys.executable).resolve():
            sys.exit(subprocess.call([str(cand), *sys.argv], env={**os.environ, 'LUMEN_PY_FORWARDED': '1'}))
    print('{"ok": false, "error": "找不到带 ' + '、'.join(needs) + ' 的 Python。设环境变量 CODECUT_PYTHON 指向它。"}', flush=True)
    sys.exit(1)
