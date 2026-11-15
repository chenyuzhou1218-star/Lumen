"""CodeCAD's window. It is app_window.py with what is particular to CodeCAD."""
from __future__ import annotations

from pathlib import Path
import sys

import right_python

right_python.use('PySide6')

from app_window import Action, Config, launch  # noqa: E402

HERE = Path(__file__).resolve().parent


def describe(answer: dict) -> list:
    out = []
    for p in answer.get('parts') or []:
        s = p.get('size_mm', ['?', '?', '?'])
        out.append(f"{p['name']}：{s[0]} × {s[1]} × {s[2]} mm，约 {p.get('weight_g')} 克（{p.get('material')}），估计打印 {p.get('print_minutes')} 分钟、用料 {p.get('plastic_g')} 克，{p.get('file')}")
    return out


CONFIG = Config('CodeCAD', HERE / 'codecad.py', '能 3D 打印的零件，单位是毫米。左边写零件，“生成零件”用 Blender 切出来并实际测量，STL 在 out 文件夹。',
                ('part.py',), [Action('生成零件', ['build', '{folder}'], True)], opens=[('打开文件夹', 'out')], describe=describe)


if __name__ == '__main__':
    sys.exit(launch(CONFIG))
