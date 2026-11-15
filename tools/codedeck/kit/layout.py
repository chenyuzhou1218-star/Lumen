"""One slide -> a list of placed things on a 1280 x 720 page. The web page, the PDF and the PowerPoint file are all drawn from this list,
so that they show the same thing.

A thing is {'kind': 'text'|'rect'|'image'|'chart'|'table', 'x','y','w','h', ...}.
Text: 'paras': [{'text', 'size', 'bold', 'color', 'align', 'bullet', 'space'}].
"""
from __future__ import annotations

W, H = 1280, 720


def on(color: str) -> str:
    """White or near-black text, whichever reads on this background: a light accent with white words on it could not be read."""
    c = str(color).lstrip('#')
    if len(c) != 6:
        return '#ffffff'
    r, g, b = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in (r, g, b)]
    return '#111111' if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 else '#ffffff'
PAD = 72

THEMES = {
    '清爽': {'bg': '#ffffff', 'ink': '#1c1f26', 'ink2': '#5d6370', 'accent': '#2f6fed', 'soft': '#eef2fa', 'dark': '#16243f', 'on_dark': '#ffffff'},
    '商务': {'bg': '#fbfaf7', 'ink': '#1d2329', 'ink2': '#5e656c', 'accent': '#0f6e6e', 'soft': '#e9efec', 'dark': '#0e3536', 'on_dark': '#ffffff'},
    '暖色': {'bg': '#fffaf4', 'ink': '#2a211a', 'ink2': '#6d5f53', 'accent': '#d9622b', 'soft': '#fbecde', 'dark': '#3f2416', 'on_dark': '#fff4e8'},
    '深色': {'bg': '#14161d', 'ink': '#eceef4', 'ink2': '#a4a8b5', 'accent': '#7c9cff', 'soft': '#22252f', 'dark': '#0c0d12', 'on_dark': '#ffffff'},
    '科技': {'bg': '#0d1422', 'ink': '#e8eefb', 'ink2': '#9fb0cc', 'accent': '#3fd0c9', 'soft': '#17233a', 'dark': '#070c16', 'on_dark': '#ffffff'},
    '极简': {'bg': '#ffffff', 'ink': '#111111', 'ink2': '#6b6b6b', 'accent': '#111111', 'soft': '#f3f3f3', 'dark': '#111111', 'on_dark': '#ffffff'},
    '森林': {'bg': '#fbfcf8', 'ink': '#1d2a22', 'ink2': '#5d6a60', 'accent': '#2c7a55', 'soft': '#e8f1e8', 'dark': '#163528', 'on_dark': '#ffffff'},
    '水墨': {'bg': '#f8f6f0', 'ink': '#20201e', 'ink2': '#66645d', 'accent': '#a3322b', 'soft': '#ece8dc', 'dark': '#22221f', 'on_dark': '#f8f6f0'},
}
KINDS = ('title', 'section', 'points', 'two', 'image', 'quote', 'numbers', 'chart', 'table', 'steps', 'big', 'agenda', 'timeline', 'pictures', 'end')


def text(x, y, w, h, paras, valign='top'):
    return {'kind': 'text', 'x': x, 'y': y, 'w': w, 'h': h, 'paras': paras, 'valign': valign}


def rect(x, y, w, h, fill, radius=0):
    return {'kind': 'rect', 'x': x, 'y': y, 'w': w, 'h': h, 'fill': fill, 'radius': radius}


def _heading(s, t):
    return [text(PAD, 48, W - 2 * PAD, 74, [{'text': s.get('title', ''), 'size': 38, 'bold': True, 'color': t['ink']}], 'bottom'),
            rect(PAD, 130, 56, 5, t['accent'], 2)]


def _points(items, t, size=30):
    out = []
    for item in items:
        if isinstance(item, dict):  # a point with a line under it
            out.append({'text': item.get('text', ''), 'size': size, 'color': t['ink'], 'bullet': True, 'space': 6})
            if item.get('note'):
                out.append({'text': item['note'], 'size': size - 6, 'color': t['ink2'], 'indent': True, 'space': 12})
        else:
            out.append({'text': str(item), 'size': size, 'color': t['ink'], 'bullet': True, 'space': 14})
    return out


def place(s: dict, t: dict, number: int, total: int) -> tuple:
    """Returns (background colour, things)."""
    kind = s.get('kind', 'points')
    bg = t['bg']
    out: list = []
    if kind == 'title':
        bg = t['dark']
        out.append(rect(PAD, 262, 90, 6, t['accent'], 3))
        out.append(text(PAD, 286, W - 2 * PAD, 170, [{'text': s.get('title', ''), 'size': 60, 'bold': True, 'color': t['on_dark']}]))
        out.append(text(PAD, 468, W - 2 * PAD, 100, [{'text': s.get('subtitle', ''), 'size': 26, 'color': t['on_dark']}]))
    elif kind == 'section':
        bg = t['accent']
        out.append(text(PAD, 270, W - 2 * PAD, 180, [{'text': s.get('title', ''), 'size': 54, 'bold': True, 'color': on(t['accent'])}, {'text': s.get('subtitle', ''), 'size': 24, 'color': on(t['accent'])}], 'middle'))
    elif kind == 'points':
        out += _heading(s, t)
        out.append(text(PAD, 164, W - 2 * PAD, 480, _points(s.get('points', []), t)))
    elif kind == 'two':
        out += _heading(s, t)
        gap = 40
        w = (W - 2 * PAD - gap) // 2
        for i, side in enumerate(('left', 'right')):
            x = PAD + i * (w + gap)
            part = s.get(side, {})
            out.append(rect(x, 164, w, 476, t['soft'], 14))
            out.append(text(x + 28, 184, w - 56, 52, [{'text': part.get('title', ''), 'size': 26, 'bold': True, 'color': t['ink']}]))
            out.append(text(x + 28, 244, w - 56, 380, _points(part.get('points', []), t, 26)))
    elif kind == 'image':
        out += _heading(s, t)
        left = s.get('side', 'right') == 'left'
        iw = 600
        ix = PAD if left else W - PAD - iw
        tx = PAD + iw + 40 if left else PAD
        out.append({'kind': 'image', 'x': ix, 'y': 164, 'w': iw, 'h': 476, 'path': s.get('image', ''), 'radius': 14})
        out.append(text(tx, 164, W - 2 * PAD - iw - 40, 476, _points(s.get('points', []), t, 28)))
    elif kind == 'quote':
        bg = t['soft']
        out.append(text(PAD + 40, 150, W - 2 * PAD - 80, 320, [{'text': f'“{s.get("text", "")}”', 'size': 40, 'color': t['ink']}], 'middle'))
        out.append(text(PAD + 40, 490, W - 2 * PAD - 80, 60, [{'text': s.get('who', ''), 'size': 22, 'color': t['ink2']}]))
    elif kind == 'numbers':
        out += _heading(s, t)
        items = s.get('numbers', [])[:4]
        gap = 28
        w = (W - 2 * PAD - gap * (len(items) - 1)) // max(1, len(items))
        for i, n in enumerate(items):
            x = PAD + i * (w + gap)
            out.append(rect(x, 196, w, 320, t['soft'], 14))
            out.append(text(x + 18, 240, w - 36, 130, [{'text': str(n.get('value', '')), 'size': 58, 'bold': True, 'color': t['accent'], 'align': 'center'}], 'middle'))
            out.append(text(x + 18, 384, w - 36, 110, [{'text': str(n.get('label', '')), 'size': 22, 'color': t['ink2'], 'align': 'center'}]))
    elif kind == 'chart':
        out += _heading(s, t)
        note = s.get('points')
        cw = 760 if note else W - 2 * PAD
        out.append({'kind': 'chart', 'x': PAD, 'y': 156, 'w': cw, 'h': 500, 'chart': s.get('chart', {})})
        if note:
            out.append(text(PAD + cw + 28, 164, W - 2 * PAD - cw - 28, 480, _points(note, t, 26)))
    elif kind == 'table':
        out += _heading(s, t)
        out.append({'kind': 'table', 'x': PAD, 'y': 164, 'w': W - 2 * PAD, 'h': 476, 'rows': s.get('rows', []), 'theme': t})
    elif kind == 'steps':
        out += _heading(s, t)
        items = s.get('steps', [])[:5]
        gap = 22
        w = (W - 2 * PAD - gap * (len(items) - 1)) // max(1, len(items))
        for i, step in enumerate(items):
            x = PAD + i * (w + gap)
            out.append(rect(x, 214, w, 8, t['accent'], 4))
            out.append(text(x, 236, w, 60, [{'text': f'{i + 1}', 'size': 34, 'bold': True, 'color': t['accent']}]))
            out.append(text(x, 298, w, 62, [{'text': step.get('title', ''), 'size': 27, 'bold': True, 'color': t['ink']}]))
            out.append(text(x, 364, w, 270, [{'text': step.get('text', ''), 'size': 24, 'color': t['ink2']}]))
    elif kind == 'big':  # one sentence, alone on a page
        bg = t['bg']
        out.append(text(PAD + 30, 170, W - 2 * PAD - 60, 380, [{'text': s.get('text', ''), 'size': 62, 'bold': True, 'color': t['ink'], 'align': 'center'}, {'text': s.get('note', ''), 'size': 26, 'color': t['ink2'], 'align': 'center'}], 'middle'))
    elif kind == 'agenda':
        out += _heading(s, t)
        items = s.get('items', [])[:7]
        for i, item in enumerate(items):
            y = 170 + i * 66
            out.append(rect(PAD, y, 46, 46, t['accent'], 23))
            out.append(text(PAD, y, 46, 46, [{'text': str(i + 1), 'size': 22, 'bold': True, 'color': on(t['accent']), 'align': 'center'}], 'middle'))
            out.append(text(PAD + 66, y, W - 2 * PAD - 70, 46, [{'text': str(item), 'size': 28, 'color': t['ink']}], 'middle'))
    elif kind == 'timeline':
        out += _heading(s, t)
        items = s.get('items', [])[:6]
        w = (W - 2 * PAD) // max(1, len(items))
        out.append(rect(PAD, 318, W - 2 * PAD, 4, t['accent'], 2))
        for i, item in enumerate(items):
            x = PAD + i * w
            out.append(rect(x, 308, 24, 24, t['accent'], 12))
            out.append(text(x, 238, w - 16, 60, [{'text': str(item.get('when', '')), 'size': 28, 'bold': True, 'color': t['ink']}], 'bottom'))
            out.append(text(x, 348, w - 16, 240, [{'text': str(item.get('what', '')), 'size': 22, 'color': t['ink2']}]))
    elif kind == 'pictures':
        out += _heading(s, t)
        items = s.get('images', [])[:3]
        gap = 20
        w = (W - 2 * PAD - gap * (len(items) - 1)) // max(1, len(items))
        for i, path in enumerate(items):
            out.append({'kind': 'image', 'x': PAD + i * (w + gap), 'y': 164, 'w': w, 'h': 476, 'path': path, 'radius': 14})
    elif kind == 'end':
        bg = t['dark']
        out.append(text(PAD, 260, W - 2 * PAD, 200, [{'text': s.get('title', '谢谢'), 'size': 60, 'bold': True, 'color': t['on_dark'], 'align': 'center'}, {'text': s.get('subtitle', ''), 'size': 24, 'color': t['on_dark'], 'align': 'center'}], 'middle'))
    if kind not in ('title', 'section', 'end'):
        out.append(text(W - PAD - 100, 672, 100, 28, [{'text': f'{number} / {total}', 'size': 13, 'color': t['ink2'], 'align': 'right'}]))
    return bg, out
