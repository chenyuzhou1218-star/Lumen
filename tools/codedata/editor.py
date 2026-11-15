"""CodeData's window. It is app_window.py with what is particular to CodeData."""
from __future__ import annotations

from pathlib import Path
import sys

import right_python

right_python.use('PySide6')

from app_window import Action, Config, launch  # noqa: E402

HERE = Path(__file__).resolve().parent


def describe(answer: dict) -> list:
    out = []
    for f in answer.get('files') or []:
        out.append(f"{f['file']}：{f['rows']} 行")
        for c in f['columns']:
            bits = f"{c['name']}（{c.get('kind')}）缺 {c['missing']} 个，{c['unique']} 种"
            if c.get('kind') == 'number':
                bits += f"，{c['min']} 到 {c['max']}，合计 {c['sum']}"
            out.append(bits)
    if answer.get('output'):
        out.append(f"报告做好了：{answer['output']}，{answer.get('facts', 0)} 条结论带着依据")
    if not out:
        out.append(f"复核通过：{answer.get('facts', 0)} 条结论的数字都和上次一样")
    return out


CONFIG = Config('CodeData', HERE / 'codedata.py', '把 Excel 或 CSV 用“加入文件”放进项目。“体检”看数据有没有问题，“生成报告”运行左边的分析代码，“复核”重算一遍对比每个数字。',
                ('analysis.py',), [Action('体检', ['look', '{folder}']), Action('生成报告', ['run', '{folder}', '--pictures'], True), Action('复核', ['recheck', '{folder}'])],
                opens=[('打开报告', 'out/report.html')], add_files='数据 (*.xlsx *.csv *.tsv *.json *.txt)', describe=describe)


if __name__ == '__main__':
    sys.exit(launch(CONFIG))
