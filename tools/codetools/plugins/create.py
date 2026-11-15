"""Things to look at: logos, animation, diagrams, icons, sprites, textures, colours."""
from __future__ import annotations

from html import escape
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from kit import Action, Field, Plugin, Stop, done, font, need, number

PALETTES = {'日落': ('#2d2a5e', '#e8706a', '#f6c98e'), '海洋': ('#0b3954', '#087e8b', '#bfd7ea'), '森林': ('#1e3d2f', '#4f8a5b', '#cfe3c1'),
            '墨白': ('#111111', '#555555', '#f4f4f4'), '樱花': ('#7a2e4d', '#e77fa3', '#fde3ec'), '金属': ('#22262c', '#7d8a99', '#e4e8ee')}


def hex_rgb(c: str) -> tuple:
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# --- logos and posters --------------------------------------------------------------------------------------------------

def _svg_logo(name: str, shape: str, cols: tuple) -> str:
    deep, mid, light = cols
    s = 512
    letter = escape(name[0].upper())
    body = {
        '圆': f'<circle cx="256" cy="256" r="220" fill="url(#g)"/>',
        '方': f'<rect x="36" y="36" width="440" height="440" rx="96" fill="url(#g)"/>',
        '六边': '<path d="M256 28 454 142V370L256 484 58 370V142Z" fill="url(#g)"/>',
        '盾': '<path d="M256 30 450 92V260C450 372 360 448 256 486 152 448 62 372 62 260V92Z" fill="url(#g)"/>',
    }.get(shape)
    if body is None:
        raise Stop('形状只有 圆、方、六边、盾')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{mid}"/><stop offset="1" stop-color="{deep}"/></linearGradient></defs>'
            f'{body}<text x="256" y="256" dy=".36em" text-anchor="middle" font-family="Segoe UI,Microsoft YaHei,sans-serif" font-weight="700" font-size="250" fill="{light}">{letter}</text></svg>')


def _gradient(size, top, bottom):
    w, h = size
    im = Image.new('RGB', (1, h))
    a, b = hex_rgb(top), hex_rgb(bottom)
    for y in range(h):
        t = y / max(1, h - 1)
        im.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    return im.resize(size)


def logo(a, out):
    name = need(a, 'name', '名字')
    cols = PALETTES.get(a.get('palette'), PALETTES['日落'])
    shape = a.get('shape') or '方'
    svg = out / 'logo.svg'
    svg.write_text(_svg_logo(name, shape, cols), encoding='utf-8')
    size = 1024
    scale = size / 512
    grad = _gradient((size, size), cols[1], cols[0])
    mask = Image.new('L', (size * 2, size * 2), 0)
    d = ImageDraw.Draw(mask)
    k = scale * 2
    if shape == '圆':
        d.ellipse((36 * k, 36 * k, 476 * k, 476 * k), fill=255)
    elif shape == '方':
        d.rounded_rectangle((36 * k, 36 * k, 476 * k, 476 * k), 96 * k, fill=255)
    elif shape == '六边':
        d.polygon([(256 * k, 28 * k), (454 * k, 142 * k), (454 * k, 370 * k), (256 * k, 484 * k), (58 * k, 370 * k), (58 * k, 142 * k)], fill=255)
    else:
        d.polygon([(256 * k, 30 * k), (450 * k, 92 * k), (450 * k, 260 * k), (380 * k, 390 * k), (256 * k, 486 * k), (132 * k, 390 * k), (62 * k, 260 * k), (62 * k, 92 * k)], fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    letter = name[0].upper()
    f = font(500, True)
    box = d.textbbox((0, 0), letter, font=f)
    d.text(((size - box[2] - box[0]) / 2, (size - box[3] - box[1]) / 2), letter, font=f, fill=cols[2])
    png = out / 'logo.png'
    im.save(png)
    return done(f'{name} 的标志：SVG 可以无限放大，PNG 是 1024 像素', files=[svg, png], pictures=[png])


def poster(a, out):
    title = need(a, 'title', '标题')
    cols = PALETTES.get(a.get('palette'), PALETTES['海洋'])
    w, h = 1080, 1528
    im = _gradient((w, h), cols[0], cols[1]).convert('RGBA')
    rnd = random.Random(title)
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(14):
        r = rnd.randint(60, 340)
        x, y = rnd.randint(-80, w), rnd.randint(-80, int(h * .7))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*hex_rgb(cols[2]), rnd.randint(8, 34)))
    im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(4)))
    d = ImageDraw.Draw(im)
    size = 132 if len(title) <= 8 else 96
    f = font(size, True)
    lines, line = [], ''
    for ch in title:
        if d.textlength(line + ch, font=f) > w - 180:
            lines.append(line)
            line = ch
        else:
            line += ch
    lines.append(line)
    y = h * .56
    for text in lines:
        d.text((90, y), text, font=f, fill=cols[2])
        y += size * 1.25
    if a.get('sub'):
        d.text((90, y + 24), str(a['sub']), font=font(44), fill=(*hex_rgb(cols[2]), 220))
    path = out / 'poster.png'
    im.convert('RGB').save(path)
    return done('海报做好了，1080×1528', files=[path], pictures=[path])


# --- animation ---------------------------------------------------------------------------------------------------------

def anim_text(a, out):
    """Words that arrive one after another, on a moving background."""
    text = need(a, 'text', '文字')
    cols = PALETTES.get(a.get('palette'), PALETTES['日落'])
    seconds = max(1.0, min(12.0, number(a, 'seconds', 4)))
    fps = 15
    w, h = 720, 405
    count = int(seconds * fps)
    lines = str(text).split('\n')
    f = font(46, True)
    frames = []
    total = sum(len(x) for x in lines)
    for n in range(count):
        t = n / count
        im = _gradient((w, h), cols[0], cols[1]).convert('RGB')
        d = ImageDraw.Draw(im, 'RGBA')
        for k in range(6):
            r = 60 + k * 26
            x = w * (.5 + .42 * math.sin(k * 1.7 + t * math.tau))
            y = h * (.5 + .4 * math.cos(k * 2.3 + t * math.tau))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(*hex_rgb(cols[2]), 22))
        shown = int(total * min(1.0, t * 1.5))
        y = (h - len(lines) * 62) / 2
        for line in lines:
            part = line[:max(0, shown)]
            shown -= len(line)
            width = d.textlength(line, font=f)
            d.text(((w - width) / 2, y), part, font=f, fill=cols[2])
            y += 62
        frames.append(im.quantize(128))
    path = out / 'anim.gif'
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=True)
    still = out / 'anim.png'
    frames[-1].convert('RGB').save(still)
    return done(f'{count} 帧，{seconds:g} 秒', files=[path], pictures=[still])


def anim_chart(a, out):
    """Bars that grow: a number story as a moving picture."""
    pairs = [line.split('|') for line in str(need(a, 'data', '数据')).splitlines() if '|' in line]
    if not pairs:
        raise Stop('数据一行一个：名字|数字')
    names, values = [p[0].strip() for p in pairs], [float(p[1]) for p in pairs]
    top = max(values) or 1
    w, h = 720, 405
    frames = []
    label_font, title_font = font(22), font(30, True)
    for n in range(40):
        t = min(1.0, n / 30)
        ease = 1 - (1 - t) ** 3
        im = Image.new('RGB', (w, h), '#fcfcfb')
        d = ImageDraw.Draw(im)
        d.text((24, 16), str(a.get('title') or ''), font=title_font, fill='#111')
        row = (h - 80) / len(values)
        for i, (name, v) in enumerate(zip(names, values)):
            y = 70 + i * row
            d.text((24, y + 2), name, font=label_font, fill='#333')
            length = (w - 280) * v / top * ease
            d.rounded_rectangle((150, y + 4, 150 + max(4, length), y + min(32, row - 8)), 6, fill='#2a78d6')
            d.text((160 + length, y + 2), f'{v * ease:,.0f}', font=label_font, fill='#333')
        frames.append(im.quantize(64))
    path = out / 'chart.gif'
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=50, loop=0)
    still = out / 'chart.png'
    frames[-1].convert('RGB').save(still)
    return done('会动的条形图', files=[path], pictures=[still])


# --- diagrams ---------------------------------------------------------------------------------------------------------

def _svg_box(x, y, w, h, text, fill='#eef2fa', stroke='#2f6fed'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}"/><text x="{x + w / 2}" y="{y + h / 2}" dy=".35em" text-anchor="middle" font-size="15" fill="#111">{escape(text)}</text>'


def _layers(nodes: list, edges: list) -> dict:
    level = {n: 0 for n in nodes}
    for _ in range(len(nodes) + 1):
        for a, b in edges:
            if level[b] <= level[a] and a != b:
                level[b] = min(level[a] + 1, len(nodes))
    return level


def flow(a, out):
    """A -> B lines: drawn in layers from top to bottom, arrows and all."""
    edges, nodes = [], []
    for line in str(need(a, 'text', '内容')).splitlines():
        parts = [p.strip() for p in line.replace('→', '->').split('->') if p.strip()]
        for p in parts:
            if p not in nodes:
                nodes.append(p)
        edges += list(zip(parts, parts[1:]))
    if not nodes:
        raise Stop('每行写：开始 -> 下一步 -> 结束')
    level = _layers(nodes, edges)
    rows: dict = {}
    for n in nodes:
        rows.setdefault(level[n], []).append(n)
    bw, bh, gx, gy = 170, 54, 36, 62
    width = max(len(r) for r in rows.values()) * (bw + gx) + gx
    height = len(rows) * (bh + gy) + gy
    place = {}
    for lv, items in rows.items():
        x0 = (width - (len(items) * (bw + gx) - gx)) / 2
        for i, n in enumerate(items):
            place[n] = (x0 + i * (bw + gx), gy / 2 + lv * (bh + gy))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" font-family="Microsoft YaHei,sans-serif"><defs><marker id="m" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 9 4.5 0 9Z" fill="#555"/></marker></defs><rect width="100%" height="100%" fill="#fff"/>']
    for s, e in edges:
        x1, y1 = place[s][0] + bw / 2, place[s][1] + bh
        x2, y2 = place[e][0] + bw / 2, place[e][1]
        if y2 <= y1:  # going back up: round the side
            x1, y1, x2, y2 = place[s][0] + bw, place[s][1] + bh / 2, place[e][0] + bw, place[e][1] + bh / 2
            svg.append(f'<path d="M{x1} {y1} C{x1 + 70} {y1} {x2 + 70} {y2} {x2} {y2}" fill="none" stroke="#555" stroke-width="1.6" marker-end="url(#m)"/>')
        else:
            mid = (y1 + y2) / 2
            svg.append(f'<path d="M{x1} {y1} C{x1} {mid} {x2} {mid} {x2} {y2}" fill="none" stroke="#555" stroke-width="1.6" marker-end="url(#m)"/>')
    for n, (x, y) in place.items():
        svg.append(_svg_box(x, y, bw, bh, n))
    path = out / 'flow.svg'
    path.write_text(''.join(svg) + '</svg>', encoding='utf-8')
    png = out / 'flow.png'
    _png_flow(png, width, height, place, bw, bh, edges)
    return done(f'{len(nodes)} 个步骤，{len(edges)} 条连线', files=[path, png], pictures=[png])


def _png_flow(path, width, height, place, bw, bh, edges):
    k = 2
    im = Image.new('RGB', (int(width * k), int(height * k)), 'white')
    d = ImageDraw.Draw(im)
    f = font(15 * k)
    for s, e in edges:
        x1, y1 = (place[s][0] + bw / 2) * k, (place[s][1] + bh) * k
        x2, y2 = (place[e][0] + bw / 2) * k, place[e][1] * k
        d.line((x1, y1, x2, y2), fill='#555', width=3)
        ang = math.atan2(y2 - y1, x2 - x1)
        for da in (2.6, -2.6):
            d.line((x2, y2, x2 + 16 * math.cos(ang + da), y2 + 16 * math.sin(ang + da)), fill='#555', width=3)
    for n, (x, y) in place.items():
        d.rounded_rectangle((x * k, y * k, (x + bw) * k, (y + bh) * k), 24, fill='#eef2fa', outline='#2f6fed', width=2)
        w = d.textlength(n, font=f)
        d.text(((x + bw / 2) * k - w / 2, (y + bh / 2) * k - 15 * k * .7), n, font=f, fill='#111')
    im.save(path)


def mind(a, out):
    """An indented outline as a mind map, branches around the centre."""
    tree, stack = None, []
    for line in str(need(a, 'text', '内容')).splitlines():
        if not line.strip():
            continue
        depth = (len(line) - len(line.lstrip(' \t-'))) // 2
        node = {'t': line.strip(' \t-'), 'k': []}
        if tree is None:
            tree = node
            stack = [(-1, tree)]
            continue
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1]['k'].append(node)
        stack.append((depth, node))
    if tree is None:
        raise Stop('第一行写中心，下面用缩进写分支')
    w, h = 1400, 1000
    im = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(im)
    colours = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#6250d6', '#e34948', '#008300')
    f1, f2, f3 = font(40, True), font(30, True), font(25)
    cx, cy = w / 2, h / 2

    def draw(node, x, y, a0, a1, depth, colour):
        kids = node['k']
        for i, kid in enumerate(kids):
            ang = a0 + (a1 - a0) * (i + .5) / len(kids)
            r = 300 if depth == 0 else 190
            nx, ny = x + math.cos(ang) * r, y + math.sin(ang) * r * .72
            c = colours[i % len(colours)] if depth == 0 else colour
            d.line((x, y, nx, ny), fill=c, width=4 - min(depth, 2))
            draw(kid, nx, ny, ang - .55, ang + .55, depth + 1, c)
            text = kid['t']
            face = f2 if depth == 0 else f3
            tw = d.textlength(text, font=face)
            d.rounded_rectangle((nx - tw / 2 - 14, ny - 25, nx + tw / 2 + 14, ny + 25), 14, fill='white', outline=c, width=3)
            d.text((nx - tw / 2, ny - 19), text, font=face, fill='#111')

    draw(tree, cx, cy, 0, math.tau, 0, '#333')
    tw = d.textlength(tree['t'], font=f1)
    d.rounded_rectangle((cx - tw / 2 - 26, cy - 40, cx + tw / 2 + 26, cy + 40), 22, fill='#111')
    d.text((cx - tw / 2, cy - 28), tree['t'], font=f1, fill='white')
    path = out / 'mind.png'
    im.save(path)
    return done('思维导图做好了', files=[path], pictures=[path])


# --- icons, sprites, textures, colours ------------------------------------------------------------------------------------

def icon_set(a, out):
    """One picture to every size an app needs."""
    src = Image.open(str(need(a, 'image', '图片'))).convert('RGBA')
    side = min(src.size)
    left, top = (src.width - side) // 2, (src.height - side) // 2
    square = src.crop((left, top, left + side, top + side))
    files = []
    for size in (16, 32, 48, 64, 128, 180, 256, 512):
        p = out / f'icon_{size}.png'
        square.resize((size, size), Image.LANCZOS).save(p)
        files.append(p)
    ico = out / 'icon.ico'
    square.resize((256, 256), Image.LANCZOS).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return done('全部尺寸都做好了，还有一个 .ico', files=[*files, ico], pictures=[files[-1]])


def sprites(a, out):
    """Small symmetric creatures from a seed: every sheet is new, each one is repeatable."""
    rnd = random.Random(str(a.get('seed') or 'seed'))
    count = int(number(a, 'count', 16))
    cell, zoom = 12, 6
    cols = min(8, count)
    rows = (count + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * (cell + 2) * zoom, rows * (cell + 2) * zoom), (0, 0, 0, 0))
    for n in range(count):
        hue = rnd.choice([(232, 112, 106), (79, 138, 91), (42, 120, 214), (237, 161, 0), (98, 80, 214), (231, 127, 163)])
        dark = tuple(int(c * .55) for c in hue)
        grid = [[0] * cell for _ in range(cell)]
        for y in range(1, cell - 1):
            for x in range(1, cell // 2):
                if rnd.random() < .55 - abs(y - cell / 2) * .03:
                    grid[y][x] = grid[y][cell - 1 - x] = 1
        for y in range(cell):
            for x in range(cell):
                ox = (n % cols) * (cell + 2) + x + 1
                oy = (n // cols) * (cell + 2) + y + 1
                near = any(grid[y + dy][x + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= y + dy < cell and 0 <= x + dx < cell)
                colour = hue if grid[y][x] else dark if near else None
                if colour:
                    sheet.paste((*colour, 255), (ox * zoom, oy * zoom, (ox + 1) * zoom, (oy + 1) * zoom))
        eye = cell // 2 - 2
        ox, oy = (n % cols) * (cell + 2) + eye + 1, (n // cols) * (cell + 2) + cell // 2 - 1
        for ex in (ox, ox + 3):
            sheet.paste((255, 255, 255, 255), (ex * zoom, oy * zoom, (ex + 1) * zoom, (oy + 1) * zoom))
    path = out / 'sprites.png'
    sheet.save(path)
    return done(f'{count} 个小精灵，每格 {(cell + 2) * zoom} 像素', files=[path], pictures=[path])


def texture(a, out):
    kind = a.get('kind') or '石头'
    table = {'石头': ('#6f6a62', '#a8a196'), '木头': ('#6b4426', '#b98a55'), '草地': ('#3f6a2f', '#86a84f'), '沙子': ('#b89c6c', '#e6d3a8'), '水面': ('#1d4f76', '#5fa8c8'), '云': ('#7a8ea6', '#f4f7fb')}
    if kind not in table:
        raise Stop(f'材质有：{", ".join(table)}')
    from plugins.worlds import _noise_grid

    size = 256
    low, high = hex_rgb(table[kind][0]), hex_rgb(table[kind][1])
    im = Image.new('RGB', (size, size))
    px = im.load()
    seed = abs(hash_text(str(a.get('seed') or kind)))
    values = _noise_grid(size, seed, 4, 6)
    if kind == '木头':  # rings: the noise folded over and over along one direction
        values = [[(math.sin((x / size * 40 + values[y][x] * 14) * math.tau / 4) + 1) / 2 for x in range(size)] for y in range(size)]
    lo, hi = min(map(min, values)), max(map(max, values))
    for y in range(size):
        for x in range(size):
            t = (values[y][x] - lo) / (hi - lo)
            px[x, y] = tuple(int(low[i] + (high[i] - low[i]) * t) for i in range(3))
    path = out / f'{kind}.png'
    big = im.resize((1024, 1024), Image.BICUBIC)
    big.save(path)
    tiled = out / '铺开看.png'
    sheet = Image.new('RGB', (1024, 1024))
    small = im.resize((512, 512))
    for i in range(2):
        for j in range(2):
            sheet.paste(small, (i * 512, j * 512))
    sheet.save(tiled)
    return done('无缝材质：可以直接平铺，贴到 Code3D 或游戏里', files=[path, tiled], pictures=[tiled])


def hash_text(text: str) -> int:
    return int.from_bytes(text.encode('utf-8')[:6].ljust(6, b'.'), 'big')


def _lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = hex_rgb(c)
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def contrast(a, out):
    fg, bg = need(a, 'text', '文字色'), need(a, 'background', '背景色')
    l1, l2 = sorted((_lum(fg), _lum(bg)), reverse=True)
    ratio = (l1 + .05) / (l2 + .05)
    verdict = '正文可用' if ratio >= 4.5 else '只适合大字' if ratio >= 3 else '太淡了，看不清'
    return done(f'对比度 {ratio:.2f} : 1，{verdict}', table=[['等级', '要求', '结果'], ['正文 AA', '4.5', '过' if ratio >= 4.5 else '不过'], ['大字 AA', '3', '过' if ratio >= 3 else '不过'], ['正文 AAA', '7', '过' if ratio >= 7 else '不过']])


def palette(a, out):
    """A base colour and what goes with it, as a strip of swatches."""
    import colorsys

    r, g, b = [v / 255 for v in hex_rgb(need(a, 'base', '主色'))]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    plan = {'相邻': [0, .08, -.08, .16, -.16], '互补': [0, .5, .46, .54, .02], '三色': [0, .333, .667, .36, .7]}.get(a.get('rule') or '相邻')
    if plan is None:
        raise Stop('配色方式有：相邻、互补、三色')
    colours = []
    for k, dh in enumerate(plan):
        rr, gg, bb = colorsys.hls_to_rgb((h + dh) % 1, min(.92, max(.12, l + (k - 2) * .07)), s)
        colours.append('#%02x%02x%02x' % (int(rr * 255), int(gg * 255), int(bb * 255)))
    im = Image.new('RGB', (1000, 300), 'white')
    d = ImageDraw.Draw(im)
    f = font(24, True)
    for i, c in enumerate(colours):
        d.rectangle((i * 200, 0, i * 200 + 200, 300), fill=c)
        d.text((i * 200 + 24, 248), c, font=f, fill='#ffffff' if _lum(c) < .4 else '#111111')
    path = out / 'palette.png'
    im.save(path)
    return done('、'.join(colours), files=[path], pictures=[path])


CHOICE_PALETTE = tuple(PALETTES)
PLUGINS = [
    Plugin('logo', '标志设计', '创作', '从名字做出标志，SVG 和 PNG 都有', [
        Action('logo', '做标志', [Field('name', '名字', value='Lumen'), Field('shape', '形状', 'choice', '方', ('圆', '方', '六边', '盾')), Field('palette', '配色', 'choice', '日落', CHOICE_PALETTE)], logo, sample={'name': '列国'}),
        Action('poster', '做海报', [Field('title', '标题', value='春日音乐会'), Field('sub', '副标题', value='四月十二日'), Field('palette', '配色', 'choice', '海洋', CHOICE_PALETTE)], poster, sample={'title': '春日音乐会', 'sub': '四月十二日'})]),
    Plugin('anim', '小动画', '创作', '文字动画和会动的图表，出 GIF', [
        Action('text', '文字动画', [Field('text', '文字（可换行）', 'area', '把想法\n做成真的'), Field('seconds', '秒数', 'number', 4), Field('palette', '配色', 'choice', '日落', CHOICE_PALETTE)], anim_text, sample={'text': '把想法\n做成真的', 'seconds': 1}),
        Action('chart', '动态条形图', [Field('title', '标题', value='各地销量'), Field('data', '数据（名字|数字）', 'area', '华东|420\n华南|300\n华北|260')], anim_chart, sample={'title': '销量', 'data': '华东|420\n华南|300'})]),
    Plugin('diagram', '流程图和导图', '创作', '用文字写，自动排版成图', [
        Action('flow', '流程图', [Field('text', '每行写 甲 -> 乙', 'area', '开始 -> 写代码 -> 测试\n测试 -> 上线\n测试 -> 写代码')], flow, sample={'text': '开始 -> 写代码 -> 测试\n测试 -> 上线\n测试 -> 写代码'}),
        Action('mind', '思维导图', [Field('text', '第一行是中心，下面用两个空格缩进', 'area', '旅行\n  准备\n    机票\n    酒店\n  路线\n    第一天\n    第二天\n  预算')], mind, sample={'text': '旅行\n  准备\n    机票\n  路线\n  预算'})]),
    Plugin('icons', '图标全套', '创作', '一张图做出应用需要的全部尺寸和 .ico', [
        Action('make', '生成', [Field('image', '图片', 'file')], icon_set, sample={'_setup': lambda o: _pic(o)})]),
    Plugin('sprites', '像素精灵', '创作', '随机生成成批的像素小角色', [
        Action('make', '生成', [Field('seed', '种子（换一个就换一批）', value='森林'), Field('count', '数量', 'number', 16)], sprites, sample={'seed': 'x', 'count': 8})]),
    Plugin('texture', '无缝材质', '创作', '石头、木头、草地等可以平铺的贴图', [
        Action('make', '生成', [Field('kind', '材质', 'choice', '石头', ('石头', '木头', '草地', '沙子', '水面', '云')), Field('seed', '种子', value='1')], texture, sample={'kind': '云'})]),
    Plugin('color', '配色工具', '创作', '算文字和背景够不够清楚，生成一组配色', [
        Action('contrast', '查对比度', [Field('text', '文字色', value='#767676'), Field('background', '背景色', value='#ffffff')], contrast, sample={'text': '#767676', 'background': '#ffffff'}),
        Action('palette', '生成配色', [Field('base', '主色', value='#2f6fed'), Field('rule', '方式', 'choice', '相邻', ('相邻', '互补', '三色'))], palette, sample={'base': '#2f6fed'})]),
]


def _pic(out):
    p = out / 'in.png'
    Image.new('RGB', (600, 400), '#2f6fed').save(p)
    return {'image': str(p)}
