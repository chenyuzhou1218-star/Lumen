"""CodeLab's window. It is app_window.py with what is particular to CodeLab."""
from __future__ import annotations

from pathlib import Path
import sys

import right_python

right_python.use('PySide6')

from app_window import Action, Config, launch  # noqa: E402

HERE = Path(__file__).resolve().parent


def describe(answer: dict) -> list:
    out = [answer['summary']] if answer.get('summary') else []
    if answer.get('progress_percent') is not None:
        out.append(f"进度 {answer['progress_percent']}%" + (f"，还要 {answer['time_left']}" if answer.get('time_left') else ''))
    for m in answer.get('metrics') or []:
        if m.get('all_bad'):
            out.append(f"{m['name']}：全是 NaN")
        else:
            out.append(f"{m['name']}：现在 {m['last']}，最好 {m['best']}（第 {m['best_at']} 步）")
    return out


CONFIG = Config('CodeLab', HERE / 'codelab.py', '打开一份训练日志，看进度、曲线和哪里不对。只读文件，不影响正在跑的训练。',
                ('',), [Action('看日志', ['watch', '{folder}'], True), Action('画曲线', ['picture', '{folder}'])], describe=describe, log_mode=True)


if __name__ == '__main__':
    sys.exit(launch(CONFIG))
