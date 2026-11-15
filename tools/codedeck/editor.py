"""CodeDeck's window. It is app_window.py with what is particular to CodeDeck."""
from __future__ import annotations

from pathlib import Path
import sys

import right_python

right_python.use('PySide6')

from app_window import Action, Config, launch  # noqa: E402

HERE = Path(__file__).resolve().parent


def describe(answer: dict) -> list:
    return [f"做好了：{'、'.join(answer.get('files') or [])}"]


CONFIG = Config('CodeDeck', HERE / 'codedeck.py', '幻灯片写在 deck.json，文档写在 doc.md。点“生成”出 PowerPoint 或 Word，还有 PDF，并给每一页出图。',
                ('deck.json', 'doc.md'), [Action('生成', ['build', '{folder}'], True)],
                opens=[('打开 PPT', 'out/deck.pptx'), ('打开 Word', 'out/doc.docx'), ('打开 PDF', 'out/deck.pdf')], new_kinds=[('幻灯片', []), ('文档', ['--doc'])], describe=describe)


if __name__ == '__main__':
    sys.exit(launch(CONFIG))
