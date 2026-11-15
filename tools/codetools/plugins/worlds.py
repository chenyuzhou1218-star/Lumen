"""For games and films: worlds, balance, and pictures, words and music put together into a video."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys

from PIL import Image, ImageDraw

from kit import Action, Field, Plugin, Stop, done, font, need, number, path_of

TOOLS = Path(__file__).resolve().parents[2]


def _noise_grid(size: int, seed: int, base: int = 4, octaves: int = 6) -> list:
    """Fractal value noise that wraps around, so that a map can tile."""
    rnd = random.Random(seed)
    out = [[0.0] * size for _ in range(size)]
    amp, cells = 1.0, base
    for _ in range(octaves):
        lattice = [[rnd.random() for _ in range(cells)] for _ in range(cells)]
        step = size / cells
        for y in range(size):
            fy = y / step
            y0 = int(fy) % cells
            y1 = (y0 + 1) % cells
            ty = fy - int(fy)
            ty = ty * ty * (3 - 2 * ty)
            row0, row1 = lattice[y0], lattice[y1]
            line = out[y]
            for x in range(size):
                fx = x / step
                x0 = int(fx) % cells
                x1 = (x0 + 1) % cells
                tx = fx - int(fx)
                tx = tx * tx * (3 - 2 * tx)
                top = row0[x0] + (row0[x1] - row0[x0]) * tx
                low = row1[x0] + (row1[x1] - row1[x0]) * tx
                line[x] += amp * (top + (low - top) * ty)
        amp *= .5
        cells = min(cells * 2, size)
    lo = min(map(min, out))
    hi = max(map(max, out))
    return [[(v - lo) / (hi - lo) for v in row] for row in out]


BIOME = [(.34, (28, 72, 122)), (.42, (52, 112, 168)), (.45, (214, 200, 148)), (.58, (98, 150, 78)), (.72, (56, 112, 62)), (.84, (118, 106, 92)), (1.01, (240, 240, 245))]


def world(a, out):
    """A map from nothing: height, water, rivers running downhill, cities in good places, and files a game can read."""
    seed = int(number(a, 'seed', 7))
    size = 384
    h = _noise_grid(size, seed)
    wet = _noise_grid(size, seed + 1, 3, 4)
    island = bool(a.get('island'))
    if island:
        for y in range(size):
            for x in range(size):
                d = math.hypot(x / size - .5, y / size - .5) / .55
                h[y][x] *= max(0.0, 1.15 - d * d)
    sea = .38
    rnd = random.Random(seed)
    rivers = set()
    for _ in range(int(number(a, 'rivers', 14))):
        for _try in range(40):
            x, y = rnd.randrange(size), rnd.randrange(size)
            if h[y][x] > .62:
                break
        for _step in range(size * 2):
            rivers.add((x, y))
            if h[y][x] < sea:
                break
            best = min(((h[(y + dy) % size][(x + dx) % size], dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if ((x + dx) % size, (y + dy) % size) not in rivers), default=None)
            if best is None:
                break
            x, y = (x + best[1]) % size, (y + best[2]) % size
    im = Image.new('RGB', (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            v = h[y][x]
            colour = next(c for top, c in BIOME if min(v, 1.0) < top + (sea - .34) * (top < .46))
            if .46 < v < .72 and wet[y][x] < .36:
                colour = (178, 170, 106)
            nx = h[y][(x + 1) % size] - v
            ny = h[(y + 1) % size][x] - v
            shade = 1 + (nx + ny) * 7 if v > sea else 1
            px[x, y] = tuple(max(0, min(255, int(c * shade))) for c in colour)
    for x, y in rivers:
        if h[y][x] >= sea:
            px[x, y] = (52, 112, 168)
    places = []
    score = []
    for y in range(8, size - 8, 6):
        for x in range(8, size - 8, 6):
            v = h[y][x]
            if sea + .03 < v < .6:
                near = sum(1 for r in rivers if abs(r[0] - x) + abs(r[1] - y) < 10)
                score.append((min(near, 6) + (1 - abs(v - .5) * 6) + rnd.random() * .6, x, y))
    for _, x, y in sorted(score, reverse=True):
        if all(math.hypot(x - p[0], y - p[1]) > 48 for p in places):
            places.append((x, y))
        if len(places) >= int(number(a, 'cities', 8)):
            break
    big = im.resize((size * 2, size * 2), Image.BICUBIC)
    d = ImageDraw.Draw(big)
    f = font(16, True)
    names = ['青州', '云阳', '临海', '白水', '长平', '定远', '安澜', '朔方', '南浦', '西陵', '北固', '东川']
    cities = []
    for i, (x, y) in enumerate(places):
        name = names[i % len(names)]
        cities.append({'name': name, 'x': x, 'y': y, 'height': round(h[y][x], 3)})
        d.ellipse((x * 2 - 5, y * 2 - 5, x * 2 + 5, y * 2 + 5), fill='white', outline='#222', width=2)
        d.text((x * 2 + 8, y * 2 - 11), name, font=f, fill='#111', stroke_width=2, stroke_fill='white')
    path = out / 'map.png'
    big.save(path)
    height = Image.new('L', (size, size))
    height.putdata([int(v * 255) for row in h for v in row])
    hp = out / 'height.png'
    height.save(hp)
    data = out / 'world.json'
    data.write_text(json.dumps({'size': size, 'sea': sea, 'seed': seed, 'cities': cities}, ensure_ascii=False, indent=1), encoding='utf-8')
    land = sum(v >= sea for row in h for v in row) / size ** 2
    return done(f'陆地占 {land:.0%}，{len(rivers)} 格河流，{len(cities)} 座城', files=[path, hp, data], pictures=[path])


# --- balance ------------------------------------------------------------------------------------------------------------

def _units(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        p = [x.strip() for x in line.split('|')]
        if len(p) >= 5:
            out[p[0]] = {'hp': float(p[1]), 'attack': float(p[2]), 'armor': float(p[3]), 'speed': float(p[4]), 'cost': float(p[5]) if len(p) > 5 else 100.0, 'range': float(p[6]) if len(p) > 6 else 0}
    if len(out) < 2:
        raise Stop('至少两个兵种：名字|生命|攻击|护甲|速度|价格|射程')
    return out


def _fight(a: dict, b: dict, count_a: int, count_b: int, rnd) -> bool:
    """Two groups strike by turns with a little luck. True if a wins."""
    ha, hb = a['hp'] * count_a, b['hp'] * count_b
    head = max(0.0, (a['range'] - b['range']) * .5)
    t = 0.0
    for _ in range(4000):
        na, nb = math.ceil(ha / a['hp']), math.ceil(hb / b['hp'])
        if t >= -head or a['range'] > 0:
            hb -= na * max(1.0, a['attack'] * rnd.uniform(.8, 1.2) - b['armor']) * a['speed'] * .1
        if b['range'] > 0 or t >= head:
            ha -= nb * max(1.0, b['attack'] * rnd.uniform(.8, 1.2) - a['armor']) * b['speed'] * .1
        t += .1
        if ha <= 0 or hb <= 0:
            return ha > hb
    return ha / (a['hp'] * count_a) > hb / (b['hp'] * count_b)


def balance(a, out):
    """Equal money on both sides, thousands of fights, for every pair. It finds what nothing beats and what beats nothing."""
    units = _units(str(need(a, 'units', '兵种')))
    games = int(number(a, 'games', 400))
    money = 3000
    rnd = random.Random(1)
    names = list(units)
    table = {x: {} for x in names}
    for x in names:
        for y in names:
            if x == y:
                table[x][y] = .5
            elif y in table and x in table[y]:
                table[x][y] = 1 - table[y][x]
            else:
                ca, cb = max(1, int(money / units[x]['cost'])), max(1, int(money / units[y]['cost']))
                table[x][y] = sum(_fight(units[x], units[y], ca, cb, rnd) for _ in range(games)) / games
    rows = [['', *names, '平均胜率']]
    means = {}
    for x in names:
        others = [table[x][y] for y in names if y != x]
        means[x] = sum(others) / len(others)
        rows.append([x, *[f'{table[x][y]:.0%}' for y in names], f'{means[x]:.0%}'])
    warnings = []
    for x in names:
        if means[x] > .72:
            warnings.append(f'{x} 太强了：同样的钱，平均胜率 {means[x]:.0%}')
        if means[x] < .28:
            warnings.append(f'{x} 太弱了：同样的钱，平均胜率 {means[x]:.0%}')
        if all(table[x][y] > .6 for y in names if y != x):
            warnings.append(f'{x} 没有克星：所有兵种都打不过它')
    w = 110 + 96 * len(names)
    h = 70 + 56 * len(names)
    im = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(im)
    f = font(17)
    for i, x in enumerate(names):
        d.text((110 + i * 96 + 8, 24), x[:5], font=f, fill='#333')
        d.text((10, 74 + i * 56), x[:6], font=f, fill='#333')
        for j, y in enumerate(names):
            v = table[x][y]
            colour = (int(232 - 110 * max(0, v - .5) * 2), int(90 + 140 * v), int(90 + 60 * v)) if v >= .5 else (232, int(90 + 140 * v), int(90 + 120 * v))
            d.rounded_rectangle((110 + j * 96, 60 + i * 56, 200 + j * 96, 112 + i * 56), 8, fill=colour)
            d.text((130 + j * 96, 74 + i * 56), f'{v:.0%}', font=f, fill='#111')
    path = out / 'balance.png'
    im.save(path)
    return done(f'{len(names)} 个兵种，每一对打 {games} 场，每边 {money} 块钱', table=rows, warnings=warnings, files=[path], pictures=[path])


def economy(a, out):
    """Does a game's income and price curve work? A simple player buying whenever they can."""
    income, growth, cost, cost_up = number(a, 'income', 10), number(a, 'growth', 1.0), number(a, 'cost', 50), number(a, 'cost_up', 1.15)
    minutes = int(number(a, 'minutes', 30))
    gold, level = 0.0, 0
    series = []
    for m in range(minutes * 60):
        gold += (income + growth * level) / 60
        price = cost * cost_up ** level
        if gold >= price:
            gold -= price
            level += 1
        if m % 60 == 0:
            series.append(level)
    gaps = [i for i in range(1, len(series)) if series[i] == series[i - 1]]
    w, h = 800, 320
    im = Image.new('RGB', (w, h), '#fcfcfb')
    d = ImageDraw.Draw(im)
    top = max(series) or 1
    d.line([(40 + i * (w - 60) / len(series), h - 30 - v / top * (h - 60)) for i, v in enumerate(series)], fill='#2a78d6', width=2)
    d.text((44, 8), f'{minutes} 分钟内的等级', font=font(14), fill='#333')
    path = out / 'economy.png'
    im.save(path)
    warnings = [f'后期太慢：最后十分钟只升了 {series[-1] - series[-11]} 级'] if len(series) > 11 and series[-1] - series[-11] < 2 else []
    return done(f'{minutes} 分钟到 {level} 级，有 {len(gaps)} 分钟一级没升', files=[path], pictures=[path], warnings=warnings)


# --- a film -----------------------------------------------------------------------------------------------------------

def film(a, out):
    """Pictures of a folder, a line of words on each, music under it: a CodeCut project, cut and exported."""
    folder = path_of(a, 'folder')
    items = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in ('.png', '.jpg', '.jpeg')]
    if not items:
        raise Stop('文件夹里没有图片')
    lines = [x.strip() for x in str(a.get('text') or '').splitlines()]
    seconds = number(a, 'seconds', 4)
    size = (1280, 720)
    frames = out / 'slides'
    frames.mkdir(exist_ok=True)
    f = font(46, True)
    clips = []
    for i, p in enumerate(items):
        im = Image.open(p).convert('RGB')
        scale = max(size[0] / im.width, size[1] / im.height)
        im = im.resize((int(im.width * scale) + 1, int(im.height * scale) + 1), Image.LANCZOS)
        x, y = (im.width - size[0]) // 2, (im.height - size[1]) // 2
        im = im.crop((x, y, x + size[0], y + size[1]))
        if i < len(lines) and lines[i]:
            d = ImageDraw.Draw(im, 'RGBA')
            d.rectangle((0, size[1] - 130, size[0], size[1]), fill=(0, 0, 0, 120))
            w = d.textlength(lines[i], font=f)
            d.text(((size[0] - w) / 2, size[1] - 104), lines[i], font=f, fill='white')
        path = frames / f'{i:03d}.png'
        im.save(path)
        clips.append(path)
    cut = TOOLS / 'codecut' / 'codecut.py'
    if not cut.is_file():
        raise Stop('没有找到 CodeCut')
    project = out / 'film.json'
    project.unlink(missing_ok=True)
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}

    def call(*args):
        res = subprocess.run([sys.executable, str(cut), *args], capture_output=True, env=env, creationflags=0x08000000 if os.name == 'nt' else 0, timeout=900)
        for line in reversed(res.stdout.decode('utf-8', 'replace').splitlines()):
            try:
                return json.loads(line)
            except ValueError:
                continue
        raise Stop(res.stderr.decode('utf-8', 'replace')[-500:] or '没有结果')

    return _assemble(call, project, clips, seconds, a, out)


def _assemble(call, project, clips, seconds, a, out):
    res = call('init', str(project), '--width', '1280', '--height', '720', '--fps', '30')
    if res.get('ok') is False:
        raise Stop(str(res.get('error')))
    at = 0.0
    for c in clips:
        res = call('add', str(project), 'image', str(c), '--duration', str(seconds))
        if res.get('ok') is False:
            raise Stop(str(res.get('error')))
        at += seconds
    if a.get('music'):
        res = call('add', str(project), 'audio', str(a['music']), '--start', '0', '--duration', str(at))
        if res.get('ok') is False:
            raise Stop(str(res.get('error')))
    target = out / 'film.mp4'
    res = call('render', str(project), '-o', str(target), '--force')
    if res.get('ok') is False or not target.is_file():
        raise Stop(f'导出失败：{res}')
    return done(f'{len(clips)} 个画面，{at:g} 秒', files=[target, project], pictures=[clips[0]])


def _units_text():
    return '步兵|100|12|4|1.0|100\n骑兵|140|18|3|1.6|180\n弓手|60|16|1|1.0|120|5\n重甲|220|10|12|.7|220'


def _film_sample(o):
    d = o / 'pics'
    d.mkdir()
    for i, c in enumerate(('#2f6fed', '#e8702a')):
        Image.new('RGB', (800, 600), c).save(d / f'p{i}.png')
    return {'folder': str(d), 'text': '第一幕\n第二幕', 'seconds': 1}


PLUGINS = [
    Plugin('world', '世界地图', '游戏', '生成地形、河流和城市，给游戏用的高度图和数据', [
        Action('make', '生成', [Field('seed', '种子', 'number', 7), Field('island', '做成岛屿', 'check', False), Field('rivers', '河流数', 'number', 14), Field('cities', '城市数', 'number', 8)], world, sample={'seed': 3, 'island': True})]),
    Plugin('balance', '数值平衡', '游戏', '让兵种成千上万次对打，找出太强太弱；模拟经济曲线', [
        Action('fight', '兵种对打', [Field('units', '名字|生命|攻击|护甲|速度|价格|射程', 'area', _units_text()), Field('games', '每对打几场', 'number', 400)], balance, sample={'units': _units_text(), 'games': 60}),
        Action('economy', '经济曲线', [Field('income', '每分钟收入', 'number', 10), Field('growth', '每级加收入', 'number', 1), Field('cost', '第一级价格', 'number', 50), Field('cost_up', '涨价倍数', 'number', 1.15), Field('minutes', '分钟', 'number', 30)], economy, sample={})]),
    Plugin('film', '短片合成', '游戏', '图片加字幕加音乐，用 CodeCut 导出成 MP4', [
        Action('make', '合成', [Field('folder', '图片文件夹', 'folder'), Field('text', '每张图一句话', 'area'), Field('seconds', '每张几秒', 'number', 4), Field('music', '音乐文件（可空）', 'file')], film, sample={'_setup': _film_sample})]),
]
