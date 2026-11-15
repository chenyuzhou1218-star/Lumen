"""CodeGame's window. It is app_window.py with what is particular to CodeGame."""
from __future__ import annotations

from pathlib import Path
import sys

import right_python

right_python.use('PySide6')

from app_window import Action, Config, launch  # noqa: E402

HERE = Path(__file__).resolve().parent


def describe(answer: dict) -> list:
    out = []
    for r in answer.get('played') or []:
        p = r.get('player') or {}
        out.append(f"第 {r['step']} 步：玩家在 {p.get('pos')}，走了 {p.get('moved')}，{r.get('fps')} 帧" + (f"，结束：{r['ended']}" if r.get('ended') else ''))
    return out or [f"做好了：{answer.get('output', '')}"]


CONFIG = Config('CodeGame', HERE / 'codegame.py', '3D 小游戏。左边写游戏代码，“开始玩”在浏览器里打开；“机器试玩”让程序自己按键试一遍，看有没有问题。WASD 走，空格跳，点一下画面后用鼠标转视角。',
                ('game.js',), [Action('开始玩', ['build', '{folder}'], True, 'out/index.html'), Action('机器试玩', ['play', '{folder}'])], describe=describe)


if __name__ == '__main__':
    sys.exit(launch(CONFIG))
