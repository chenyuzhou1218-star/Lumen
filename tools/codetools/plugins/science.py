"""Numbers and thinking: exact maths, circuits, logic, physics, plans, spreadsheets, notes."""
from __future__ import annotations

import ast
from datetime import date, timedelta
from fractions import Fraction
import itertools
import json
import math
from pathlib import Path
import re
import zipfile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw

from kit import Action, Field, Plugin, Stop, done, font, need, number, path_of

OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b, ast.FloorDiv: lambda a, b: a // b}
FUNCS = {k: getattr(math, k) for k in ('sin', 'cos', 'tan', 'sqrt', 'log', 'log10', 'exp', 'floor', 'ceil', 'radians', 'degrees', 'asin', 'acos', 'atan')} | {'abs': abs, 'round': round, 'max': max, 'min': min}
NAMES = {'pi': math.pi, 'e': math.e}


def _value(node, names):
    if isinstance(node, ast.Expression):
        return _value(node.body, names)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Fraction(str(node.value)) if isinstance(node.value, float) else node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        a, b = _value(node.left, names), _value(node.right, names)
        if isinstance(node.op, ast.Pow) and isinstance(a, Fraction) and b != int(b):
            a = float(a)
        if isinstance(node.op, ast.Pow) and isinstance(b, Fraction) and b.denominator == 1:
            b = int(b)
        if isinstance(node.op, ast.Pow) and abs(float(b)) > 4096:
            raise Stop('指数太大了')
        if isinstance(node.op, ast.Div) and isinstance(a, int):
            a = Fraction(a)
        return OPS[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _value(node.operand, names)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS:
        return FUNCS[node.func.id](*[float(_value(x, names)) for x in node.args])
    raise Stop(f'不认识：{ast.unparse(node) if isinstance(node, ast.AST) else node}')


def evaluate(text: str, names: dict | None = None):
    try:
        tree = ast.parse(text.strip().replace('^', '**').replace('×', '*').replace('÷', '/'), mode='eval')
    except SyntaxError as e:
        raise Stop(f'算式写错了：{text}') from e
    try:
        return _value(tree, {**NAMES, **(names or {})})
    except ZeroDivisionError as e:
        raise Stop('除以零了') from e


def calc(a, out):
    """Fractions stay exact: 1/3 + 1/6 is 1/2, not 0.5000000001."""
    lines = []
    names = {}
    for line in str(need(a, 'text', '算式')).splitlines():
        if not line.strip():
            continue
        m = re.match(r'^\s*([A-Za-z_一-鿿]\w*)\s*=(?!=)(.+)$', line)
        v = evaluate(m.group(2) if m else line, names)
        if m:
            names[m.group(1)] = v
        shown = f'{v}' + (f'  ≈ {float(v):.10g}' if isinstance(v, Fraction) and v.denominator != 1 else '')
        lines.append(f'{line.strip()}  =  {shown}')
    return done(*lines)


def plot(a, out):
    expr = str(need(a, 'expr', '函数'))
    lo, hi = number(a, 'from', -10), number(a, 'to', 10)
    if hi <= lo:
        raise Stop('右端要大于左端')
    n = 400
    pts = []
    tree = ast.parse(expr.replace('^', '**'), mode='eval')
    for i in range(n + 1):
        x = lo + (hi - lo) * i / n
        try:
            y = float(_value(tree, {**NAMES, 'x': x}))
            if math.isfinite(y):
                pts.append((x, y))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            pass
    if not pts:
        raise Stop('这个区间里算不出值')
    ys = sorted(p[1] for p in pts)
    ylo, yhi = ys[len(ys) // 100], ys[-1 - len(ys) // 100]
    if yhi == ylo:
        yhi += 1
    w, h = 900, 520
    im = Image.new('RGB', (w, h), '#fcfcfb')
    d = ImageDraw.Draw(im)
    fx = lambda x: 50 + (x - lo) / (hi - lo) * (w - 70)  # noqa: E731
    fy = lambda y: h - 40 - (y - ylo) / (yhi - ylo) * (h - 70)  # noqa: E731
    if lo < 0 < hi:
        d.line((fx(0), 20, fx(0), h - 40), fill='#cccccc')
    if ylo < 0 < yhi:
        d.line((50, fy(0), w - 20, fy(0)), fill='#cccccc')
    last = None
    for x, y in pts:
        if ylo - (yhi - ylo) <= y <= yhi + (yhi - ylo):
            p = (fx(x), fy(y))
            if last and abs(p[1] - last[1]) < h:
                d.line((*last, *p), fill='#2a78d6', width=2)
            last = p
        else:
            last = None
    f = font(14)
    d.text((54, 8), f'y = {expr}', font=f, fill='#333')
    d.text((50, h - 28), f'{lo:g}', font=f, fill='#555')
    d.text((w - 60, h - 28), f'{hi:g}', font=f, fill='#555')
    d.text((6, 20), f'{yhi:.3g}', font=f, fill='#555')
    d.text((6, h - 56), f'{ylo:.3g}', font=f, fill='#555')
    path = out / 'plot.png'
    im.save(path)
    return done(f'x 从 {lo:g} 到 {hi:g}', files=[path], pictures=[path])


UNITS = {'长度': {'米': 1, '千米': 1000, '厘米': .01, '毫米': .001, '英寸': .0254, '英尺': .3048, '英里': 1609.344, '市尺': 1 / 3}, '重量': {'千克': 1, '克': .001, '吨': 1000, '斤': .5, '磅': .45359237, '盎司': .0283495},
         '面积': {'平方米': 1, '平方千米': 1e6, '亩': 666.667, '公顷': 1e4, '平方英尺': .092903}, '时间': {'秒': 1, '分': 60, '小时': 3600, '天': 86400}, '容量': {'升': 1, '毫升': .001, '加仑': 3.78541}, '数据': {'字节': 1, 'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3, 'TB': 1024 ** 4}}


def units(a, out):
    v = number(a, 'value', 1)
    src, dst = str(need(a, 'from', '原单位')), str(need(a, 'to', '目标单位'))
    if {src, dst} <= {'摄氏', '华氏', '开尔文'}:
        c = {'摄氏': v, '华氏': (v - 32) / 1.8, '开尔文': v - 273.15}[src]
        return done(f'{v:g} {src} = {({"摄氏": c, "华氏": c * 1.8 + 32, "开尔文": c + 273.15}[dst]):.6g} {dst}')
    for table in UNITS.values():
        if src in table and dst in table:
            return done(f'{v:g} {src} = {v * table[src] / table[dst]:.8g} {dst}')
    raise Stop('这两个单位换算不了。有：' + '；'.join('、'.join(t) for t in UNITS.values()))


# --- circuits ----------------------------------------------------------------------------------------------------------

def _solve(m: list, b: list) -> list:
    n = len(m)
    a = [row[:] + [b[i]] for i, row in enumerate(m)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(a[r][i]))
        if abs(a[p][i]) < 1e-12:
            raise Stop('电路解不出来：有节点悬空，或者电压源成了回路')
        a[i], a[p] = a[p], a[i]
        for r in range(n):
            if r != i:
                k = a[r][i] / a[i][i]
                for c in range(i, n + 1):
                    a[r][c] -= k * a[i][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def _parts(text: str) -> list:
    out = []
    for line in text.splitlines():
        p = line.split()
        if len(p) >= 4:
            scale = {'k': 1e3, 'M': 1e6, 'm': 1e-3, 'u': 1e-6, 'n': 1e-9}
            v = p[3]
            value = float(v[:-1]) * scale[v[-1]] if v[-1] in scale else float(v)
            out.append((p[0], p[1], p[2], value))
    if not out:
        raise Stop('一行一个元件：R1 a b 1k（节点 0 是地）')
    return out


def circuit(a, out):
    """Modified nodal analysis, the method SPICE uses. R1 a b 1k · V1 a 0 5 · I1 a 0 1m."""
    parts = _parts(str(need(a, 'text', '电路')))
    nodes = sorted({n for _, x, y, _ in parts for n in (x, y)} - {'0'})
    if '0' not in {n for _, x, y, _ in parts for n in (x, y)}:
        raise Stop('要有一个节点 0 作为地')
    sources = [p for p in parts if p[0][0].upper() == 'V']
    size = len(nodes) + len(sources)
    G = [[0.0] * size for _ in range(size)]
    b = [0.0] * size
    at = {n: i for i, n in enumerate(nodes)}
    for name, x, y, v in parts:
        i, j = at.get(x), at.get(y)
        kind = name[0].upper()
        if kind == 'R':
            g = 1 / v
            if i is not None:
                G[i][i] += g
            if j is not None:
                G[j][j] += g
            if i is not None and j is not None:
                G[i][j] -= g
                G[j][i] -= g
        elif kind == 'I':
            if i is not None:
                b[i] -= v
            if j is not None:
                b[j] += v
        elif kind == 'V':
            k = len(nodes) + sources.index((name, x, y, v))
            if i is not None:
                G[i][k] += 1
                G[k][i] += 1
            if j is not None:
                G[j][k] -= 1
                G[k][j] -= 1
            b[k] = v
        else:
            raise Stop(f'{name}：这里只算电阻 R、电压源 V、电流源 I')
    x = _solve(G, b)
    volts = {n: x[at[n]] for n in nodes}
    volts['0'] = 0.0
    rows = [['元件', '电压 V', '电流 mA', '功率 mW']]
    for name, n1, n2, v in parts:
        dv = volts[n1] - volts[n2]
        if name[0].upper() == 'R':
            i = dv / v
        elif name[0].upper() == 'V':
            i = x[len(nodes) + sources.index((name, n1, n2, v))]
        else:
            i = v
        rows.append([name, f'{dv:.4g}', f'{i * 1000:.4g}', f'{abs(dv * i) * 1000:.4g}'])
    return done('节点电压：' + '，'.join(f'{k}={v:.4g} V' for k, v in sorted(volts.items()) if k != '0'), table=rows)


def rc(a, out):
    """A capacitor charging through a resistor, stepped in time."""
    r, c, v = number(a, 'r', 1000), number(a, 'c', 1e-6), number(a, 'v', 5)
    tau = r * c
    w, h = 800, 360
    im = Image.new('RGB', (w, h), '#fcfcfb')
    d = ImageDraw.Draw(im)
    pts = []
    q = 0.0
    dt = tau / 200
    for i in range(1000):
        pts.append((50 + i * (w - 80) / 1000, h - 40 - q / v * (h - 80)))
        q += (v - q) / tau * dt
    d.line(pts, fill='#2a78d6', width=2)
    f = font(14)
    d.text((54, 10), f'时间常数 {tau * 1000:.3g} ms，五倍后基本充满', font=f, fill='#333')
    path = out / 'rc.png'
    im.save(path)
    return done(f'τ = {tau:.3g} 秒，一个 τ 后 {v * (1 - math.exp(-1)):.3g} V', files=[path], pictures=[path])


# --- logic ------------------------------------------------------------------------------------------------------------

def _logic_parse(text: str):
    """Tighter to looser: not, and, or, ->, <->. A statement becomes nested tuples."""
    tokens = re.findall(r'<->|->|\(|\)|[A-Za-z_一-鿿]\w*', text)
    if ''.join(tokens) != re.sub(r'\s+', '', text):
        raise Stop('只认识 and or not，-> 表示推出，<-> 表示等价')
    at = [0]

    def peek():
        return tokens[at[0]] if at[0] < len(tokens) else None

    def take():
        at[0] += 1
        return tokens[at[0] - 1]

    def atom():
        t = peek()
        if t is None:
            raise Stop('命题没写完')
        take()
        if t == 'not':
            return ('not', atom())
        if t == '(':
            inner = iff()
            if peek() != ')':
                raise Stop('括号没有配对')
            take()
            return inner
        if t in (')', '->', '<->', 'and', 'or'):
            raise Stop(f'这里不该是 {t}')
        return ('var', t)

    def conj():
        left = atom()
        while peek() == 'and':
            take()
            left = ('and', left, atom())
        return left

    def disj():
        left = conj()
        while peek() == 'or':
            take()
            left = ('or', left, conj())
        return left

    def impl():
        left = disj()
        if peek() == '->':
            take()
            return ('imp', left, impl())
        return left

    def iff():
        left = impl()
        while peek() == '<->':
            take()
            left = ('iff', left, impl())
        return left

    tree = iff()
    if peek() is not None:
        raise Stop(f'多了 {peek()}')
    return tree


def _logic_eval(t, env):
    kind = t[0]
    if kind == 'var':
        return env[t[1]]
    if kind == 'not':
        return not _logic_eval(t[1], env)
    a, b = _logic_eval(t[1], env), _logic_eval(t[2], env)
    return {'and': a and b, 'or': a or b, 'imp': (not a) or b, 'iff': a == b}[kind]


def _logic_vars(t) -> set:
    return {t[1]} if t[0] == 'var' else set().union(*[_logic_vars(x) for x in t[1:]])


def logic(a, out):
    """Is a statement always true? A truth table does not guess: it checks every case and shows a counterexample."""
    text = str(need(a, 'text', '命题')).replace('∧', ' and ').replace('∨', ' or ').replace('¬', ' not ').replace('→', '->').replace('↔', '<->')
    tree = _logic_parse(text)
    names = sorted(_logic_vars(tree))
    if len(names) > 14:
        raise Stop('变量太多了，最多 14 个')
    rows = [[*names, '结果']]
    bad = None
    trues = 0
    for values in itertools.product((False, True), repeat=len(names)):
        env = dict(zip(names, values))
        v = _logic_eval(tree, env)
        trues += v
        if len(rows) <= 32:
            rows.append(['真' if x else '假' for x in values] + ['真' if v else '假'])
        if not v and bad is None:
            bad = env
    total = 2 ** len(names)
    if bad is None:
        verdict = f'恒真：{total} 种情况全部成立'
    elif trues == 0:
        verdict = '恒假：没有一种情况成立'
    else:
        verdict = f'不总成立，反例：{"，".join(f"{k}={"真" if v else "假"}" for k, v in bad.items())}'
    return done(verdict, table=rows)


# --- physics ----------------------------------------------------------------------------------------------------------

def _gif(frames, out, name):
    path = out / name
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=33, loop=0)
    still = out / (Path(name).stem + '.png')
    frames[len(frames) // 2].convert('RGB').save(still)
    return path, still


def throw(a, out):
    """A throw with air resistance, stepped by Runge-Kutta. Without drag it is the textbook parabola."""
    v0, angle, drag = number(a, 'speed', 30), math.radians(number(a, 'angle', 45)), number(a, 'drag', .02)
    g = 9.81

    def f(s):
        x, y, vx, vy = s
        speed = math.hypot(vx, vy)
        return (vx, vy, -drag * speed * vx, -g - drag * speed * vy)

    s = (0.0, 0.0, v0 * math.cos(angle), v0 * math.sin(angle))
    dt = .01
    path = [s]
    while s[1] >= 0 and len(path) < 200000:
        k1 = f(s)
        k2 = f(tuple(a_ + dt / 2 * b for a_, b in zip(s, k1)))
        k3 = f(tuple(a_ + dt / 2 * b for a_, b in zip(s, k2)))
        k4 = f(tuple(a_ + dt * b for a_, b in zip(s, k3)))
        s = tuple(a_ + dt / 6 * (p + 2 * q + 2 * r_ + t) for a_, p, q, r_, t in zip(s, k1, k2, k3, k4))
        path.append(s)
    reach, top, flight = path[-1][0], max(p[1] for p in path), (len(path) - 1) * dt
    w, h = 800, 400
    scale = min((w - 80) / max(reach, 1), (h - 80) / max(top, 1))
    frames = []
    for i in range(0, len(path), max(1, len(path) // 60)):
        im = Image.new('RGB', (w, h), '#fcfcfb')
        d = ImageDraw.Draw(im)
        d.line((30, h - 30, w - 20, h - 30), fill='#888')
        trail = [(30 + p[0] * scale, h - 30 - p[1] * scale) for p in path[:i + 1:max(1, i // 200 + 1)]]
        if len(trail) > 1:
            d.line(trail, fill='#2a78d6', width=2)
        x, y = 30 + path[i][0] * scale, h - 30 - path[i][1] * scale
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill='#eb6834')
        frames.append(im.quantize(32))
    gif, still = _gif(frames, out, 'throw.gif')
    return done(f'飞了 {reach:.1f} 米，最高 {top:.1f} 米，用时 {flight:.2f} 秒', files=[gif], pictures=[still])


def pendulum(a, out):
    L, theta, damp = number(a, 'length', 1), math.radians(number(a, 'angle', 40)), number(a, 'damp', .1)
    w0, om = 0.0, 0.0
    w, h = 500, 400
    frames = []
    dt = .005
    t = 0.0
    crossings = []
    last = theta
    for i in range(int(8 / dt)):
        om += (-9.81 / L * math.sin(theta) - damp * om) * dt
        theta += om * dt
        t += dt
        if last > 0 >= theta:
            crossings.append(t)
        last = theta
        if i % 12 == 0:
            im = Image.new('RGB', (w, h), '#fcfcfb')
            d = ImageDraw.Draw(im)
            x, y = 250 + math.sin(theta) * 280, 40 + math.cos(theta) * 280
            d.line((250, 40, x, y), fill='#333', width=3)
            d.ellipse((x - 18, y - 18, x + 18, y + 18), fill='#2a78d6')
            frames.append(im.quantize(16))
    period = (crossings[1] - crossings[0]) if len(crossings) > 1 else 2 * math.pi * math.sqrt(L / 9.81)
    gif, still = _gif(frames, out, 'pendulum.gif')
    return done(f'周期约 {period:.3f} 秒（小角度公式给 {2 * math.pi * math.sqrt(L / 9.81):.3f}）', files=[gif], pictures=[still], w0=w0)


# --- plans ------------------------------------------------------------------------------------------------------------

def plan(a, out):
    """Tasks with lengths and what they wait for: the dates, the critical path, a chart."""
    tasks = {}
    for line in str(need(a, 'text', '任务')).splitlines():
        p = [x.strip() for x in line.split('|')]
        if len(p) >= 2:
            tasks[p[0]] = {'days': float(p[1]), 'after': [x for x in re.split(r'[,，、]', p[2])] if len(p) > 2 and p[2] else []}
    if not tasks:
        raise Stop('一行一个任务：名字|天数|前置任务')
    for k, t in tasks.items():
        for x in t['after']:
            if x not in tasks:
                raise Stop(f'{k} 等的“{x}”不在列表里')
    finish, state = {}, {}

    def end(k):
        if state.get(k) == 1:
            raise Stop(f'任务绕成了圈：{k}')
        if k not in finish:
            state[k] = 1
            start = max((end(x) for x in tasks[k]['after']), default=0)
            finish[k] = start + tasks[k]['days']
            state[k] = 2
        return finish[k]

    total = max(end(k) for k in tasks)
    late = {k: total for k in tasks}
    for k in sorted(tasks, key=lambda k: -finish[k]):
        for x in tasks[k]['after']:
            late[x] = min(late[x], late[k] - tasks[k]['days'])
    critical = [k for k in tasks if abs(late[k] - finish[k]) < 1e-9]
    start_day = date.fromisoformat(str(a.get('start') or date.today().isoformat()))
    rows = [['任务', '开始', '结束', '可以拖几天']]
    w, h = 1000, 70 + 34 * len(tasks)
    im = Image.new('RGB', (w, h), '#fcfcfb')
    d = ImageDraw.Draw(im)
    f = font(15)
    scale = (w - 230) / total
    for i, k in enumerate(sorted(tasks, key=lambda k: finish[k] - tasks[k]['days'])):
        s = finish[k] - tasks[k]['days']
        rows.append([k, str(start_day + timedelta(days=s)), str(start_day + timedelta(days=finish[k])), f'{late[k] - finish[k]:g}'])
        y = 40 + i * 34
        d.text((14, y + 2), k[:12], font=f, fill='#333')
        d.rounded_rectangle((200 + s * scale, y, 200 + finish[k] * scale, y + 24), 5, fill='#e34948' if k in critical else '#2a78d6')
    d.text((14, 10), f'共 {total:g} 天，红色是不能耽误的', font=f, fill='#333')
    path = out / 'plan.png'
    im.save(path)
    return done(f'一共 {total:g} 天，到 {start_day + timedelta(days=total)}', '不能耽误的：' + ' → '.join(sorted(critical, key=lambda k: finish[k])), table=rows, files=[path], pictures=[path])


# --- a spreadsheet -----------------------------------------------------------------------------------------------------

def _col(n: int) -> str:
    out = ''
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def sheet(a, out):
    """A real .xlsx from a table written as text: numbers are numbers, =SUM(...) stays a formula, the header is fixed."""
    rows = [[c.strip() for c in line.split('|')] for line in str(need(a, 'text', '表格')).splitlines() if line.strip()]
    xml = []
    strings: list = []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, v in enumerate(row):
            ref = f'{_col(c)}{r}'
            style = ' s="1"' if r == 1 else ''
            if v.startswith('='):
                cells.append(f'<c r="{ref}"{style}><f>{escape(v[1:])}</f></c>')
            elif re.fullmatch(r'-?\d+(\.\d+)?', v):
                cells.append(f'<c r="{ref}"{style}><v>{v}</v></c>')
            elif v:
                if v not in strings:
                    strings.append(v)
                cells.append(f'<c r="{ref}" t="s"{style}><v>{strings.index(v)}</v></c>')
        xml.append(f'<row r="{r}">{"".join(cells)}</row>')
    widths = ''.join(f'<col min="{i + 1}" max="{i + 1}" width="16" customWidth="1"/>' for i in range(max(map(len, rows))))
    NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    path = out / 'table.xlsx'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(str(a.get("name") or "表格"))}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{widths}</cols><sheetData>{"".join(xml)}</sheetData></worksheet>')
        z.writestr('xl/sharedStrings.xml', f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="{NS}" count="{len(strings)}" uniqueCount="{len(strings)}">' + ''.join(f'<si><t>{escape(s)}</t></si>' for s in strings) + '</sst>')
        z.writestr('xl/styles.xml', f'<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="{NS}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEEF2FA"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs></styleSheet>')
    return done(f'{len(rows)} 行的表格', files=[path])


# --- notes ------------------------------------------------------------------------------------------------------------

def notes(a, out):
    """A folder of Markdown notes linked by [[names]]: who points at whom, what is orphaned, and links that lead nowhere."""
    folder = path_of(a, 'folder')
    pages = {p.stem: p.read_text(encoding='utf-8', errors='replace') for p in folder.rglob('*.md')}
    if not pages:
        raise Stop('这个文件夹里没有 .md 笔记')
    links = {k: re.findall(r'\[\[([^\]|#]+)', t) for k, t in pages.items()}
    back = {k: [] for k in pages}
    broken = []
    for k, out_links in links.items():
        for t in out_links:
            t = t.strip()
            if t in back:
                back[t].append(k)
            else:
                broken.append(f'{k} 指向不存在的 [[{t}]]')
    alone = [k for k in pages if not links[k] and not back[k]]
    names = list(pages)
    w, h = 1000, 800
    im = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(im)
    place = {k: (w / 2 + (300 + 60 * (i % 2)) * math.cos(i / len(names) * math.tau), h / 2 + (280 + 40 * (i % 2)) * math.sin(i / len(names) * math.tau)) for i, k in enumerate(names)}
    for k, out_links in links.items():
        for t in out_links:
            if t.strip() in place:
                d.line((*place[k], *place[t.strip()]), fill='#bbbbbb', width=2)
    f = font(16)
    for k, (x, y) in place.items():
        r = 6 + 3 * len(back[k])
        d.ellipse((x - r, y - r, x + r, y + r), fill='#2a78d6')
        d.text((x + r + 4, y - 10), k[:14], font=f, fill='#222')
    path = out / 'graph.png'
    im.save(path)
    rows = [['笔记', '字数', '指出去', '被指向']] + [[k, len(pages[k]), len(links[k]), len(back[k])] for k in sorted(pages, key=lambda k: -len(back[k]))[:40]]
    return done(f'{len(pages)} 篇笔记，{sum(map(len, links.values()))} 条链接', table=rows, files=[path], pictures=[path], warnings=broken[:20] + [f'{k} 是孤岛：没有任何连接' for k in alone[:10]])


def _notes(o):
    d = o / 'n'
    d.mkdir()
    (d / '甲.md').write_text('看 [[乙]] 和 [[丙]]', encoding='utf-8')
    (d / '乙.md').write_text('回到 [[甲]]', encoding='utf-8')
    (d / '孤岛.md').write_text('没有链接', encoding='utf-8')
    return {'folder': str(d)}


PLUGINS = [
    Plugin('calc', '精确计算', '科学', '分数不丢精度，能画函数，能换单位', [
        Action('calc', '计算', [Field('text', '算式，一行一个，可以写 a = 3', 'area', '1/3 + 1/6\na = 2^10\na / 3')], calc, sample={'text': '1/3 + 1/6\na = 2^10\na / 3\nsqrt(2)'}),
        Action('plot', '画函数', [Field('expr', 'y =', value='sin(x)/x'), Field('from', '从', 'number', -10), Field('to', '到', 'number', 10)], plot, sample={'expr': 'sin(x)/x'}),
        Action('units', '换单位', [Field('value', '数值', 'number', 1), Field('from', '原单位', value='英里'), Field('to', '目标单位', value='千米')], units, sample={'value': 1, 'from': '英里', 'to': '千米'})]),
    Plugin('circuit', '电路计算', '科学', '解直流电路的电压电流，算 RC 充电', [
        Action('solve', '解电路', [Field('text', '一行一个元件：R1 a b 1k，节点 0 是地', 'area', 'V1 a 0 5\nR1 a b 1k\nR2 b 0 1k')], circuit, sample={'text': 'V1 a 0 5\nR1 a b 1k\nR2 b 0 1k'}),
        Action('rc', 'RC 充电', [Field('r', '电阻 Ω', 'number', 1000), Field('c', '电容 F', 'number', 1e-6), Field('v', '电压 V', 'number', 5)], rc, sample={'r': 1000, 'c': 1e-6, 'v': 5})]),
    Plugin('logic', '逻辑验证', '科学', '穷举所有情况，判断命题是否恒真，给出反例', [
        Action('check', '验证', [Field('text', '用 and or not -> <->', value='(p -> q) and p -> q')], logic, sample={'text': '(p -> q) and p -> q'})]),
    Plugin('physics', '物理模拟', '科学', '抛体和单摆，算数值，出动画', [
        Action('throw', '抛体', [Field('speed', '速度 m/s', 'number', 30), Field('angle', '角度', 'number', 45), Field('drag', '空气阻力系数', 'number', .02)], throw, sample={'speed': 20}),
        Action('pendulum', '单摆', [Field('length', '长度 m', 'number', 1), Field('angle', '起始角度', 'number', 40), Field('damp', '阻尼', 'number', .1)], pendulum, sample={'length': 1})]),
    Plugin('plan', '项目排期', '科学', '任务和依赖算出日期、关键路径和甘特图', [
        Action('make', '排期', [Field('text', '名字|天数|前置任务', 'area', '设计|3|\n开发|7|设计\n测试|3|开发\n文档|2|设计\n上线|1|测试,文档'), Field('start', '开始日期', value='')], plan, sample={'text': '设计|3|\n开发|7|设计\n测试|3|开发\n文档|2|设计\n上线|1|测试,文档', 'start': '2026-12-01'})]),
    Plugin('sheet', '做 Excel', '科学', '用文字写表格，生成真的 .xlsx，公式也能算', [
        Action('make', '生成', [Field('name', '表名', value='表格'), Field('text', '用 | 分列，公式写 =', 'area', '产品|数量|单价|金额\n茶|3|20|=B2*C2\n咖啡|2|30|=B3*C3\n合计|||=SUM(D2:D3)')], sheet, sample={'text': '产品|数量|单价|金额\n茶|3|20|=B2*C2\n合计|||=SUM(D2:D2)'})]),
    Plugin('notes', '笔记关系图', '科学', '分析 Markdown 笔记的 [[链接]]，找孤岛和断链', [
        Action('map', '分析', [Field('folder', '笔记文件夹', 'folder')], notes, sample={'_setup': _notes})]),
]
