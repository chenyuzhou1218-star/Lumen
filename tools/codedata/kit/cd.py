"""What analysis.py imports. It reads data, works it out, and writes a report: every number in the report came from the data by this code.

    import cd
    t = cd.read('sales.xlsx')
    by = t.group('地区', sum='销售额').sort('销售额（合计）', down=True)
    cd.title('一季度销售')
    cd.say('华东最多。', evidence=by.head(1))
    cd.chart(cd.hbar(by.col('地区'), by.col('销售额（合计）'), '各地区销售额'))
    cd.table(by)
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import json
from pathlib import Path

from charts import bar, donut, histogram, hbar, line, scatter  # noqa: F401  (for analysis.py)
from stats import correlate, forecast, rank_outliers, share, trend  # noqa: F401
from tables import DataError, Table, profile  # noqa: F401
from tables import read as _read

REPORT: list = []
FACTS: list = []
SOURCES: list = []
TITLE = {'text': ''}


def read(path: str, sheet=None, header_row=0) -> Table:
    t = _read(path, sheet, header_row)
    SOURCES.append({'file': str(path), 'rows': len(t), 'columns': t.columns})
    return t


def title(text: str) -> None:
    TITLE['text'] = text


def head(text: str) -> None:
    REPORT.append(f'<h2>{escape(text)}</h2>')


def say(text: str, evidence=None) -> None:
    """A sentence of the report. evidence: the Table or number it rests on, kept in out/facts.json so that it can be checked again."""
    REPORT.append(f'<p>{escape(text)}</p>')
    if evidence is not None:
        FACTS.append({'said': text, 'evidence': _plain(evidence)})


def chart(svg: str) -> None:
    REPORT.append(f'<figure>{svg}</figure>')


def stats(items: dict) -> None:
    """A row of headline numbers: cd.stats({'总销售额': 1200, '订单数': 86})"""
    cells = ''.join(f'<div><strong>{escape(_show(v))}</strong><span>{escape(str(k))}</span></div>' for k, v in items.items())
    REPORT.append(f'<div class="stats">{cells}</div>')
    FACTS.append({'said': '头条数字', 'evidence': _plain(items)})


def table(t: Table, most=30) -> None:
    head_row = ''.join(f'<th>{escape(str(c))}</th>' for c in t.columns)
    rows = []
    for r in t.rows[:most]:
        rows.append('<tr>' + ''.join(f'<td class="{"n" if isinstance(c, (int, float)) else ""}">{escape(_show(c))}</td>' for c in r) + '</tr>')
    more = f'<p class="note">共 {len(t)} 行，这里显示前 {most} 行。</p>' if len(t) > most else ''
    REPORT.append(f'<div class="scroll"><table><thead><tr>{head_row}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{more}')


def _show(v) -> str:
    if v is None:
        return '—'
    if isinstance(v, bool):
        return '是' if v else '否'
    if isinstance(v, float):
        return f'{v:,.2f}'.rstrip('0').rstrip('.')
    if isinstance(v, int):
        return f'{v:,}'
    return str(v)


def _plain(v):
    if isinstance(v, Table):
        return {'columns': v.columns, 'rows': [[_plain(c) for c in r] for r in v.rows[:50]], 'count': len(v)}
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v[:50]]
    if isinstance(v, (date, datetime)):
        return str(v)
    return v


STYLE = """
:root{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e5e4df;--soft:#f2f1ec}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--ink);font:16px/1.7 system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif}
main{max-width:820px;margin:0 auto;padding:40px 20px 64px}h1{font-size:30px;line-height:1.25;margin:0 0 6px}h2{font-size:21px;margin:34px 0 8px}p{margin:8px 0}
figure{margin:18px 0}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.stats div{flex:1;min-width:130px;background:var(--soft);border-radius:12px;padding:12px 16px}
.stats strong{display:block;font-size:26px;line-height:1.3}.stats span{color:var(--ink2);font-size:14px}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0}
th{text-align:left;color:var(--ink2);font-weight:600;border-bottom:1px solid var(--ink2);padding:6px 10px}td{border-bottom:1px solid var(--line);padding:6px 10px}td.n{text-align:right;font-variant-numeric:tabular-nums}
.note,footer{color:var(--ink2);font-size:13px}footer{margin-top:40px;border-top:1px solid var(--line);padding-top:10px}
"""


def save_csv(t: Table, name: str) -> None:
    """A cleaned table as a new file, beside the report. The user's own file stays as it was."""
    import csv

    path = Path('out') / f'{name}.csv'
    path.parent.mkdir(exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(t.columns)
        w.writerows(t.rows)
    FACTS.append({'said': f'存了 {path}', 'evidence': len(t)})


def finish(folder: Path) -> dict:
    out = folder / 'out'
    out.mkdir(exist_ok=True)
    origin = '、'.join(f"{s['file']}（{s['rows']} 行）" for s in SOURCES) or '没有读取数据'
    page = (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(TITLE["text"] or "数据报告")}</title>'
            f'<style>{STYLE}</style></head><body><main><h1>{escape(TITLE["text"])}</h1>{"".join(REPORT)}<footer>数据来源：{escape(origin)}</footer></main></body></html>')
    (out / 'report.html').write_text(page, encoding='utf-8')
    (out / 'facts.json').write_text(json.dumps({'sources': SOURCES, 'facts': FACTS}, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'output': 'out/report.html', 'sources': SOURCES, 'facts': len(FACTS), 'parts': len(REPORT)}
