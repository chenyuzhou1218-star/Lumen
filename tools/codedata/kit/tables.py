"""Reading data, and a small table to work with. Only Python's own library: no pandas here.

CSV (any common encoding), TSV, JSON, and Excel .xlsx: an .xlsx is a zip of XML, which is read directly.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
import io
import json
import math
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
NUMBER = re.compile(r'^[-+]?[¥$€£]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*%?$')
DATE = re.compile(r'^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$')
MISSING = {'', 'na', 'n/a', 'null', 'none', 'nan', '-', '--', '无', '空'}


class DataError(Exception):
    """A problem with the data, in words."""


def _value(text):
    """A cell as it means: number, date, or text. Missing is None."""
    if text is None:
        return None
    if not isinstance(text, str):
        return text
    s = text.strip()
    if s.lower() in MISSING:
        return None
    if NUMBER.match(s):
        n = float(re.sub(r'[,¥$€£\s%]', '', s))
        n = n / 100 if s.endswith('%') else n
        return int(n) if n.is_integer() and '.' not in s and '%' not in s else n
    if DATE.match(s):
        try:
            return datetime.fromisoformat(s.replace('/', '-').replace('.', '-').replace('T', ' ')).date() if ':' not in s else datetime.fromisoformat(s.replace('/', '-').replace('.', '-').replace('T', ' '))
        except ValueError:
            return s
    return s


def _decode(raw: bytes) -> str:
    for enc in ('utf-8-sig', 'gb18030', 'utf-16'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise DataError('读不出这个文件的编码')


def _read_csv(path: Path, sep=None) -> tuple:
    text = _decode(path.read_bytes())
    if sep is None:
        sample = text[:4000]
        sep = max(',\t;|', key=sample.count)
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=sep) if any(c.strip() for c in r)]
    if not rows:
        raise DataError('文件是空的')
    return rows[0], rows[1:]


def _col_index(ref: str) -> int:
    n = 0
    for c in ref:
        if c.isalpha():
            n = n * 26 + ord(c.upper()) - 64
        else:
            break
    return n - 1


def _excel_date(n: float):
    moment = datetime(1899, 12, 30) + timedelta(days=n)
    return moment.date() if float(n).is_integer() else moment


DATE_FORMATS = {14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 30, 36, 45, 46, 47, 50, 57}


def sheets_of(path: Path) -> list:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('xl/workbook.xml'))
    return [s.get('name') for s in root.find('m:sheets', NS)]


def _read_xlsx(path: Path, sheet=None) -> tuple:
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise DataError('这不是有效的 .xlsx 文件') from e
    with z:
        names = set(z.namelist())
        shared = []
        if 'xl/sharedStrings.xml' in names:
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS):
                shared.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
        book = ET.fromstring(z.read('xl/workbook.xml'))
        rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets = book.find('m:sheets', NS)
        chosen = None
        for s in sheets:
            if sheet is None or s.get('name') == sheet:
                chosen = s
                break
        if chosen is None:
            raise DataError(f'没有 {sheet} 这张表；有：{", ".join(s.get("name") for s in sheets)}')
        target = rels[chosen.get('{%s}id' % NS['r'])]
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        date_styles = set()
        if 'xl/styles.xml' in names:
            styles = ET.fromstring(z.read('xl/styles.xml'))
            custom = {}
            fmts = styles.find('m:numFmts', NS)
            for f in fmts if fmts is not None else []:
                code = f.get('formatCode', '').lower()
                custom[int(f.get('numFmtId'))] = re.search(r'[ymdh]', re.sub(r'\[[^\]]*\]|"[^"]*"', '', code)) is not None
            xfs = styles.find('m:cellXfs', NS)
            for i, xf in enumerate(xfs if xfs is not None else []):
                fid = int(xf.get('numFmtId', '0'))
                if fid in DATE_FORMATS or custom.get(fid):
                    date_styles.add(i)
        rows = []
        for row in ET.fromstring(z.read(target)).iter('{%s}row' % NS['m']):
            cells: dict = {}
            for c in row.findall('m:c', NS):
                kind = c.get('t')
                v = c.find('m:v', NS)
                value = None
                if kind == 's' and v is not None:
                    value = shared[int(v.text)]
                elif kind == 'inlineStr':
                    value = ''.join(t.text or '' for t in c.iter('{%s}t' % NS['m']))
                elif kind == 'b' and v is not None:
                    value = v.text == '1'
                elif v is not None and v.text is not None:
                    if kind == 'str':
                        value = v.text
                    else:
                        try:
                            value = float(v.text)
                            if value.is_integer():
                                value = int(value)
                            if int(c.get('s', '0')) in date_styles:
                                value = _excel_date(float(v.text))
                        except ValueError:
                            value = v.text
                cells[_col_index(c.get('r', 'A1'))] = value
            rows.append(cells)
    rows = [r for r in rows if any(v not in (None, '') for v in r.values())]
    if not rows:
        raise DataError('这张表是空的')
    width = max(max(r) for r in rows if r) + 1
    grid = [[r.get(i) for i in range(width)] for r in rows]
    return grid[0], grid[1:]


def _read_json(path: Path) -> tuple:
    data = json.loads(_decode(path.read_bytes()))
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        if not lists:
            raise DataError('JSON 里没有列表')
        data = max(lists, key=len)
    if not data or not isinstance(data[0], dict):
        raise DataError('JSON 要是一个对象列表')
    head = list(dict.fromkeys(k for row in data for k in row))
    return head, [[row.get(k) for k in head] for row in data]


class Table:
    """Rows and named columns. Every step returns a new Table, so that a report can say how a number was reached."""

    def __init__(self, columns: list, rows: list, source: str = ''):
        self.columns = columns
        self.rows = rows
        self.source = source

    def __len__(self):
        return len(self.rows)

    def _at(self, name: str) -> int:
        if name not in self.columns:
            raise DataError(f'没有 {name} 这一列。有：{", ".join(map(str, self.columns))}')
        return self.columns.index(name)

    def col(self, name: str) -> list:
        i = self._at(name)
        return [r[i] for r in self.rows]

    def numbers(self, name: str) -> list:
        return [v for v in self.col(name) if isinstance(v, (int, float)) and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v))]

    def where(self, test) -> 'Table':
        """t.where(lambda r: r['地区'] == '华东')"""
        return Table(self.columns, [r for r in self.rows if test(dict(zip(self.columns, r)))], self.source)

    def pick(self, *names) -> 'Table':
        idx = [self._at(n) for n in names]
        return Table(list(names), [[r[i] for i in idx] for r in self.rows], self.source)

    def sort(self, name: str, down=False) -> 'Table':
        i = self._at(name)
        have = [r for r in self.rows if r[i] is not None]
        none = [r for r in self.rows if r[i] is None]
        try:
            have.sort(key=lambda r: r[i], reverse=down)
        except TypeError:
            have.sort(key=lambda r: str(r[i]), reverse=down)
        return Table(self.columns, have + none, self.source)

    def head(self, n=10) -> 'Table':
        return Table(self.columns, self.rows[:n], self.source)

    def add(self, name: str, fn) -> 'Table':
        """A new column worked out from each row."""
        return Table(self.columns + [name], [r + [fn(dict(zip(self.columns, r)))] for r in self.rows], self.source)

    def group(self, *names, sum=None, mean=None, count=None, max=None, min=None) -> 'Table':  # noqa: A002
        """t.group('地区', sum='销售额', count='订单') gives one row per 地区: 地区, 销售额（合计）, 订单（数量）. Text in a sum column is left out, and reported by checks()."""
        idx = [self._at(n) for n in names]
        groups: dict = {}
        for r in self.rows:
            groups.setdefault(tuple(r[i] for i in idx), []).append(r)
        ops = []
        for op, field in (('合计', sum), ('平均', mean), ('数量', count), ('最大', max), ('最小', min)):
            for f in ([field] if isinstance(field, str) else field or []):
                ops.append((op, f, self._at(f)))
        rows = []
        for key, members in groups.items():
            row = list(key)
            for op, _, i in ops:
                vals = [m[i] for m in members if isinstance(m[i], (int, float)) and not isinstance(m[i], bool)]
                if op == '数量':
                    row.append(len([m for m in members if m[i] is not None]))
                elif not vals:
                    row.append(None)
                elif op == '合计':
                    row.append(_tidy(_sum(vals)))
                elif op == '平均':
                    row.append(_sum(vals) / len(vals))
                else:
                    row.append(_biggest(vals) if op == '最大' else _smallest(vals))
            rows.append(row)
        return Table(list(names) + [f'{f}（{op}）' for op, f, _ in ops], rows, self.source)

    def unique(self) -> 'Table':
        """Rows that are exactly the same, once."""
        seen, rows = set(), []
        for r in self.rows:
            key = tuple(str(c) for c in r)
            if key not in seen:
                seen.add(key)
                rows.append(r)
        return Table(self.columns, rows, self.source)

    def fill(self, name: str, value) -> 'Table':
        i = self._at(name)
        return Table(self.columns, [r[:i] + [value if r[i] is None else r[i]] + r[i + 1:] for r in self.rows], self.source)

    def rename(self, old: str, new: str) -> 'Table':
        i = self._at(old)
        return Table(self.columns[:i] + [new] + self.columns[i + 1:], self.rows, self.source)

    def replace(self, name: str, mapping: dict) -> 'Table':
        """Two spellings of one name made one: t.replace('地区', {'华 东': '华东'})"""
        i = self._at(name)
        return Table(self.columns, [r[:i] + [mapping.get(r[i], r[i])] + r[i + 1:] for r in self.rows], self.source)

    def month(self, name: str, new: str = '月份') -> 'Table':
        """A column of dates gets a column of 2026-03."""
        i = self._at(name)
        return Table(self.columns + [new], [r + [str(r[i])[:7] if r[i] is not None else None] for r in self.rows], self.source)

    def join(self, other: 'Table', on: str, other_on: str | None = None) -> 'Table':
        """Every row here, with the matching row of the other table; a row with no match keeps blanks."""
        key = other._at(other_on or on)
        look = {}
        for r in other.rows:
            look.setdefault(r[key], r)
        extra = [c for j, c in enumerate(other.columns) if j != key]
        names = self.columns + [c if c not in self.columns else f'{c}_2' for c in extra]
        i = self._at(on)
        rows = []
        for r in self.rows:
            hit = look.get(r[i])
            rows.append(r + ([c for j, c in enumerate(hit) if j != key] if hit else [None] * len(extra)))
        return Table(names, rows, self.source)

    def pivot(self, row: str, col: str, value: str) -> 'Table':
        """A cross table: one row per `row`, one column per `col`, the sums of `value` inside."""
        ri, ci, vi = self._at(row), self._at(col), self._at(value)
        cols = sorted({str(r[ci]) for r in self.rows if r[ci] is not None})
        cells: dict = {}
        for r in self.rows:
            if r[ci] is not None and isinstance(r[vi], (int, float)):
                cells.setdefault(r[ri], {}).setdefault(str(r[ci]), 0)
                cells[r[ri]][str(r[ci])] += r[vi]
        return Table([row, *cols], [[k, *[_tidy(v.get(c, 0)) for c in cols]] for k, v in cells.items()], self.source)

    def as_records(self) -> list:
        return [dict(zip(self.columns, r)) for r in self.rows]


_biggest = max
_smallest = min
_sum = sum


def _tidy(v):
    return round(v, 10) if isinstance(v, float) else v


def read(path, sheet=None, header_row=0) -> Table:
    path = Path(path)
    if not path.is_file():
        raise DataError(f'没有这个文件：{path}')
    kind = path.suffix.lower()
    if kind == '.xlsx':
        head, rows = _read_xlsx(path, sheet)
    elif kind == '.tsv':
        head, rows = _read_csv(path, '\t')
    elif kind in ('.csv', '.txt'):
        head, rows = _read_csv(path)
    elif kind == '.json':
        head, rows = _read_json(path)
    elif kind == '.xls':
        raise DataError('.xls 是旧格式，读不了：在 Excel 里另存为 .xlsx')
    else:
        raise DataError(f'不认识 {kind} 文件')
    if header_row:
        head, rows = rows[header_row - 1], rows[header_row:]
    names = []
    for i, name in enumerate(head):
        text = str(name).strip() if name not in (None, '') else f'列{i + 1}'
        while text in names:
            text += '_2'
        names.append(text)
    width = len(names)
    clean = [[_value(c) for c in (list(r) + [None] * width)[:width]] for r in rows]
    return Table(names, clean, path.name)


def profile(t: Table) -> dict:
    """What is in the data, before anything is concluded from it: the checks a careful analyst does first."""
    columns = []
    warnings = []
    seen = {}
    for r in t.rows:
        key = tuple(str(c) for c in r)
        seen[key] = seen.get(key, 0) + 1
    repeated = _sum(v - 1 for v in seen.values())
    if repeated:
        warnings.append(f'有 {repeated} 行和别的行一模一样：确认是不是重复录入。')
    for name in t.columns:
        vals = t.col(name)
        have = [v for v in vals if v is not None]
        missing = len(vals) - len(have)
        info: dict = {'name': name, 'missing': missing, 'unique': len({str(v) for v in have})}
        nums = [v for v in have if isinstance(v, (int, float)) and not isinstance(v, bool)]
        dates = [v for v in have if isinstance(v, (date, datetime))]
        text = [v for v in have if isinstance(v, str)]
        if len(nums) >= max(1, len(have) * .8):
            info['kind'] = 'number'
            info.update(min=_smallest(nums), max=_biggest(nums), mean=round(statistics.fmean(nums), 4), median=statistics.median(nums), sum=_tidy(_sum(nums)))
            if text:
                warnings.append(f'{name} 是数字列，但有 {len(text)} 个不是数字（如 {text[0]!r}）：它们不会被算进合计。')
            if len(nums) >= 12:
                q = statistics.quantiles(nums, n=4)
                spread = q[2] - q[0]
                far = [v for v in nums if spread and (v < q[0] - 3 * spread or v > q[2] + 3 * spread)]
                if far:
                    info['far_values'] = len(far)
                    warnings.append(f'{name} 有 {len(far)} 个离群的值（最远 {_biggest(far, key=lambda v: abs(v - statistics.median(nums))):g}）：是真的，还是录错了？')
        elif dates:
            info['kind'] = 'date'
            info.update(first=str(_smallest(dates)), last=str(_biggest(dates)))
        else:
            info['kind'] = 'text'
            counts: dict = {}
            for v in have:
                counts[str(v)] = counts.get(str(v), 0) + 1
            info['top'] = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
            lowered: dict = {}
            for v in counts:
                lowered.setdefault(re.sub(r'\s+', '', v).lower(), []).append(v)
            alike = [v for v in lowered.values() if len(v) > 1]
            if alike:
                warnings.append(f'{name} 里有写法不同的同一个值：{" / ".join(alike[0])}。')
        if vals and missing / len(vals) > .2:
            warnings.append(f'{name} 缺了 {missing / len(vals):.0%}。')
        columns.append(info)
    return {'rows': len(t.rows), 'columns': columns, 'warnings': warnings}
