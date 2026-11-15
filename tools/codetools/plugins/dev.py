"""For programmers: APIs, databases, logs, regular expressions, data formats, timing."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re
import sqlite3
import statistics
import subprocess
import time
import tomllib
import urllib.error
import urllib.request

from PIL import Image, ImageDraw

from kit import Action, Field, Plugin, Stop, done, font, need, number, path_of


def api_test(a, out):
    """Requests from a list; each may say what it expects. One line: GET url 200 "word in the answer"."""
    rows = [['请求', '状态', '毫秒', '结果']]
    bad = []
    for line in str(need(a, 'requests', '请求')).splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        method, url = parts[0].upper(), parts[1]
        want = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        word = re.search(r'"(.*)"', line)
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method=method, headers={'User-Agent': 'CodeTools'}), timeout=number(a, 'timeout', 15)) as r:
                status, body = r.status, r.read(2_000_000).decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read(200000).decode('utf-8', 'replace')
        except (urllib.error.URLError, OSError, ValueError) as e:
            status, body = 0, str(e)
        ms = int((time.perf_counter() - started) * 1000)
        fine = (want is None or status == want) and status != 0 and (word is None or word.group(1) in body)
        rows.append([f'{method} {url}'[:60], status, ms, '通过' if fine else '不对'])
        if not fine:
            bad.append(f'{url}：状态 {status}' + (f'，要 {want}' if want else '') + (f'，没有“{word.group(1)}”' if word and word.group(1) not in body else ''))
    return done(f'{len(rows) - 1} 个请求，{len(bad)} 个不对', table=rows, warnings=bad)


def _server(o):
    """A little server on this computer, for the sample."""
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == '/ok' else 404)
            self.end_headers()
            self.wfile.write(b'hello world')

        def log_message(self, *x):
            pass

    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    p = s.server_address[1]
    return {'requests': f'GET http://127.0.0.1:{p}/ok 200 "hello"\nGET http://127.0.0.1:{p}/nope 404'}


def db_look(a, out):
    con = sqlite3.connect(path_of(a, 'file').resolve().as_uri() + '?mode=ro', uri=True)
    rows = [['表', '行数', '列']]
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols = [c[1] for c in con.execute(f'PRAGMA table_info("{name}")')]
        rows.append([name, con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0], '、'.join(cols)[:80]])
    con.close()
    return done(f'{len(rows) - 1} 张表', table=rows)


def db_query(a, out):
    """Read only: the file is opened so that nothing can change it."""
    sql = str(need(a, 'sql', '查询'))
    con = sqlite3.connect(path_of(a, 'file').resolve().as_uri() + '?mode=ro', uri=True)
    try:
        cur = con.execute(sql)
    except sqlite3.Error as e:
        raise Stop(f'查询有错：{e}') from e
    head = [d[0] for d in cur.description or []]
    data = cur.fetchmany(5000)
    con.close()
    path = out / 'result.csv'
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(data)
    return done(f'{len(data)} 行', table=[head] + [list(r) for r in data[:30]], files=[path])


def _db(o):
    p = o / 'a.db'
    con = sqlite3.connect(p)
    con.execute('CREATE TABLE t(id INTEGER, name TEXT)')
    con.execute("INSERT INTO t VALUES (1,'甲'),(2,'乙')")
    con.commit()
    con.close()
    return {'file': str(p)}


def log_read(a, out):
    """Error kinds, counted: numbers and paths are taken out, so that the same mistake is one line, however often it happened."""
    text = path_of(a, 'file').read_bytes().decode('utf-8', 'replace')
    lines = text.splitlines()
    kinds, hours = {}, {}
    level = re.compile(r'\b(ERROR|FATAL|CRITICAL|Exception|Traceback|错误|失败|WARN(?:ING)?|警告)\b', re.I)
    stamp = re.compile(r'(\d{4}-\d\d-\d\d[ T]\d\d)')
    for line in lines:
        s = stamp.search(line)
        if level.search(line):
            shape = re.sub(r'0x[0-9a-f]+|\d+', '#', line)
            shape = re.sub(r'[A-Za-z]:[\\/][^\s"]+|/[^\s"]+/[^\s"]+', '<路径>', shape)
            shape = re.sub(r'^\W*#[-#:. T#,]*', '', shape)[:110]
            kinds[shape] = kinds.get(shape, 0) + 1
            if s:
                hours[s.group(1)] = hours.get(s.group(1), 0) + 1
    rows = [['次数', '错误']] + [[c, k] for k, c in sorted(kinds.items(), key=lambda x: -x[1])[:30]]
    pictures = []
    if hours:
        w, h = 900, 300
        im = Image.new('RGB', (w, h), '#fcfcfb')
        d = ImageDraw.Draw(im)
        keys = sorted(hours)
        top = max(hours.values())
        f = font(13)
        bw = max(3, min(30, (w - 60) // len(keys) - 2))
        for i, k in enumerate(keys):
            x = 40 + i * (w - 60) / len(keys)
            hi = (h - 60) * hours[k] / top
            d.rounded_rectangle((x, h - 30 - hi, x + bw, h - 30), 3, fill='#2a78d6')
        d.text((40, 8), f'每小时的错误数，最多 {top}', font=f, fill='#333')
        d.text((40, h - 24), keys[0], font=f, fill='#555')
        d.text((w - 150, h - 24), keys[-1], font=f, fill='#555')
        p = out / 'errors.png'
        im.save(p)
        pictures.append(p)
    return done(f'{len(lines)} 行，{sum(kinds.values())} 处问题，{len(kinds)} 种', table=rows, pictures=pictures, files=pictures)


def _log(o):
    p = o / 'a.log'
    p.write_text('\n'.join(f'2026-01-0{1 + i % 3} 1{i % 4}:00:00 ERROR failed to open D:\\data\\f{i}.txt code {i}' for i in range(20)) + '\n2026-01-01 10:00:00 INFO ok\n2026-01-02 10:00:00 WARNING low memory 12 MB\n', encoding='utf-8')
    return {'file': str(p)}


def regex_try(a, out):
    pattern, text = str(need(a, 'pattern', '正则')), str(a.get('text') or '')
    try:
        rx = re.compile(pattern)
    except re.error as e:
        raise Stop(f'正则写错了，第 {e.pos} 个字符：{e.msg}') from e
    rows = [['位置', '匹配', '分组']]
    for m in rx.finditer(text):
        rows.append([f'{m.start()}-{m.end()}', m.group(0)[:50], '、'.join(str(g) for g in m.groups())[:50]])
        if len(rows) > 200:
            break
    extra = []
    if a.get('replace') not in (None, ''):
        extra.append('替换后：' + rx.sub(str(a['replace']), text)[:400])
    return done(f'{len(rows) - 1} 处匹配', *extra, table=rows)


EXPLAIN = [(r'\d', '一个数字'), (r'\w', '一个字母数字或汉字'), (r'\s', '一个空白'), (r'\b', '单词边界'), ('^', '开头'), ('$', '结尾'), ('.', '任意一个字符'), ('*', '前面的重复零次或多次'), ('+', '前面的重复一次或多次'), ('?', '前面的可有可无'), ('|', '或者')]


def regex_explain(a, out):
    pattern = str(need(a, 'pattern', '正则'))
    parts, i = [], 0
    while i < len(pattern):
        piece = pattern[i]
        if piece == '\\' and i + 1 < len(pattern):
            piece = pattern[i:i + 2]
        elif piece == '[':
            end = pattern.find(']', i)
            piece = pattern[i:end + 1] if end > 0 else piece
        elif piece == '{':
            end = pattern.find('}', i)
            piece = pattern[i:end + 1] if end > 0 else piece
        word = dict(EXPLAIN).get(piece)
        if word is None:
            word = f'其中一个：{piece[1:-1]}' if piece.startswith('[') else f'重复 {piece[1:-1]} 次' if piece.startswith('{') else '分组开始' if piece == '(' else '分组结束' if piece == ')' else f'字面的 {piece}'
        parts.append([piece, word])
        i += len(piece)
    return done(f'{len(parts)} 段', table=[['写法', '意思']] + parts)


def _parse(text: str, kind: str):
    if kind == 'json':
        return json.loads(text)
    if kind == 'toml':
        return tomllib.loads(text)
    if kind == 'csv':
        return list(csv.DictReader(io.StringIO(text)))
    raise Stop(f'不认识 {kind}')


def convert(a, out):
    """JSON, TOML and CSV into one another, and a check on the way."""
    source = path_of(a, 'file')
    kind = source.suffix.lower().lstrip('.')
    to = str(a.get('to') or 'json')
    try:
        data = _parse(source.read_text(encoding='utf-8-sig'), kind)
    except (ValueError, tomllib.TOMLDecodeError) as e:
        raise Stop(f'这个 {kind} 写错了：{e}') from e
    path = out / f'{source.stem}.{to}'
    if to == 'json':
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    elif to == 'csv':
        rows = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), None)
        if not rows or not isinstance(rows[0], dict):
            raise Stop('要转 CSV，内容得是一个表格样的列表')
        head = list(dict.fromkeys(k for r in rows for k in r))
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, head)
            w.writeheader()
            w.writerows(rows)
    elif to == 'toml':
        def line(k, v):
            return f'{k} = {json.dumps(v, ensure_ascii=False)}'
        if not isinstance(data, dict):
            data = {'rows': data}
        body = [line(k, v) for k, v in data.items() if not isinstance(v, dict)]
        for k, v in data.items():
            if isinstance(v, dict):
                body += [f'\n[{k}]'] + [line(x, y) for x, y in v.items()]
        path.write_text('\n'.join(body) + '\n', encoding='utf-8')
    else:
        raise Stop('能转成 json、csv、toml')
    return done(f'{kind} 转成了 {to}', files=[path])


def _json(o):
    p = o / 'a.json'
    p.write_text('[{"名字": "甲", "数": 1}, {"名字": "乙", "数": 2}]', encoding='utf-8')
    return {'file': str(p), 'to': 'csv'}


def shape(a, out):
    """What a JSON file is made of, without reading all of it."""
    data = json.loads(path_of(a, 'file').read_text(encoding='utf-8-sig'))
    rows = [['路径', '类型', '例子']]

    def walk(v, where):
        if len(rows) > 80:
            return
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f'{where}.{k}' if where else k)
        elif isinstance(v, list):
            rows.append([where or '根', f'列表（{len(v)} 项）', ''])
            if v:
                walk(v[0], where + '[]')
        else:
            rows.append([where, type(v).__name__, str(v)[:40]])

    walk(data, '')
    return done(f'{len(rows) - 1} 个字段', table=rows)


def bench(a, out):
    """Runs commands several times and compares them, as a benchmark should: same machine, same order, several rounds."""
    commands = [c.strip() for c in str(need(a, 'commands', '命令')).splitlines() if c.strip()]
    rounds = max(1, int(number(a, 'rounds', 5)))
    times = {c: [] for c in commands}
    for _ in range(rounds):
        for c in commands:
            start = time.perf_counter()
            res = subprocess.run(c, shell=True, capture_output=True, timeout=600, creationflags=0x08000000)
            times[c].append(time.perf_counter() - start)
            if res.returncode:
                raise Stop(f'这条命令失败了：{c}\n{res.stderr.decode("utf-8", "replace")[-300:]}')
    best = min(statistics.median(v) for v in times.values())
    rows = [['命令', '中位数（秒）', '最快', '最慢', '倍数']]
    for c, v in sorted(times.items(), key=lambda kv: statistics.median(kv[1])):
        m = statistics.median(v)
        rows.append([c[:60], f'{m:.3f}', f'{min(v):.3f}', f'{max(v):.3f}', f'{m / best:.2f}'])
    return done(f'{len(commands)} 条命令，各跑 {rounds} 次', table=rows)


PLUGINS = [
    Plugin('apitest', '接口测试', '开发', '一行一个请求，查状态码和返回内容', [
        Action('run', '运行', [Field('requests', '一行：GET 地址 200 "要包含的字"', 'area', 'GET https://example.com 200 "Example"'), Field('timeout', '超时秒数', 'number', 15)], api_test, sample={'_setup': _server})]),
    Plugin('sqlite', '数据库查看', '开发', '只读打开 SQLite，看表、查询、导出 CSV', [
        Action('look', '看结构', [Field('file', '数据库文件', 'file')], db_look, sample={'_setup': _db}),
        Action('query', '查询', [Field('file', '数据库文件', 'file'), Field('sql', 'SQL', 'area', 'SELECT * FROM t LIMIT 20')], db_query, sample={'_setup': _db, 'sql': 'SELECT * FROM t'})]),
    Plugin('logs', '日志分析', '开发', '把几万行日志归成几种错误，按时间画出来', [
        Action('read', '分析', [Field('file', '日志文件', 'file')], log_read, sample={'_setup': _log})]),
    Plugin('regex', '正则表达式', '开发', '试正则，看匹配和替换，逐段解释', [
        Action('try', '试一试', [Field('pattern', '正则', value=r'(\d+)-(\d+)'), Field('text', '文字', 'area', '10-20 和 30-40'), Field('replace', '替换成（可空）')], regex_try, sample={'pattern': r'(\d+)-(\d+)', 'text': '10-20 和 30-40', 'replace': r'\2-\1'}),
        Action('explain', '解释', [Field('pattern', '正则', value=r'^\d{3}[a-z]+$')], regex_explain, sample={'pattern': r'^\d{3}[a-z]+$'})]),
    Plugin('dataconv', '数据格式转换', '开发', 'JSON、CSV、TOML 互转，看 JSON 的结构', [
        Action('convert', '转换', [Field('file', '文件', 'file'), Field('to', '转成', 'choice', 'json', ('json', 'csv', 'toml'))], convert, sample={'_setup': _json}),
        Action('shape', '看结构', [Field('file', 'JSON 文件', 'file')], shape, sample={'_setup': _json})]),
    Plugin('bench', '性能对比', '开发', '把几条命令各跑几次，比出谁快', [
        Action('run', '开始', [Field('commands', '命令，一行一条', 'area', 'python -c "sum(range(10**6))"'), Field('rounds', '跑几次', 'number', 5)], bench, sample={'commands': 'cmd /c echo a\ncmd /c dir >nul', 'rounds': 2})]),
]
