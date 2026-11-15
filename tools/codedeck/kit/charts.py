"""Charts as SVG, drawn from nothing. CodeData's reports and CodeDeck's slides both use this file.

The colours are a palette whose order is checked for colour-blind readers, always given out in the same order; after eight series
the rest fold into 其他. One axis, thin marks, a legend from two series up, and a hover note on every mark.
"""
from __future__ import annotations

from html import escape
import math

SERIES = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948')
INK = '#0b0b0b'
INK2 = '#52514e'
GRID = '#e5e4df'
SURFACE = '#fcfcfb'
FONT = "system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif"
MOST_SERIES = len(SERIES)


def nice_step(span: float, count: int = 5) -> float:
    if span <= 0:
        return 1.0
    raw = span / count
    power = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * power:
            return m * power
    return 10 * power


def ticks(lo: float, hi: float, count: int = 5) -> list:
    step = nice_step(hi - lo, count)
    start = math.floor(lo / step) * step
    out = []
    v = start
    while v <= hi + step * 1.001 and len(out) < 14:
        out.append(round(v, 10))
        if v >= hi:
            break
        v += step
    return out


def short(v: float) -> str:
    """Whole under 10,000; 10K, 2.5M above."""
    a = abs(v)
    if a >= 1e9:
        return f'{v / 1e9:g}B'
    if a >= 1e6:
        return f'{v / 1e6:g}M'
    if a >= 1e4:
        return f'{v / 1e3:g}K'
    if float(v).is_integer():
        return f'{int(v):,}'
    return f'{v:,.2f}'.rstrip('0').rstrip('.')


def _width_of(text: str, size: float) -> float:
    """Estimate: a Chinese character is one em, a Latin one about half."""
    return sum(size if ord(c) > 0x2E7F else size * .55 for c in str(text))


def _clip(text: str, room: float, size: float) -> str:
    text = str(text)
    if _width_of(text, size) <= room:
        return text
    while text and _width_of(text + '…', size) > room:
        text = text[:-1]
    return text + '…'


class Svg:
    def __init__(self, width, height, title, subtitle=''):
        self.w, self.h = width, height
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{escape(str(title))}" '
                      f'style="max-width:100%;height:auto;font-family:{FONT}">', f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>']
        self.top = 10
        if title:
            self.text(16, 26, _clip(title, width - 32, 16), 16, INK, weight=600)
            self.top = 38
        if subtitle:
            self.text(16, 46, _clip(subtitle, width - 32, 12), 12, INK2)
            self.top = 54

    def text(self, x, y, value, size=12, fill=INK2, anchor='start', weight=400):
        self.parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{escape(str(value))}</text>')

    def add(self, text):
        self.parts.append(text)

    def done(self) -> str:
        return ''.join(self.parts) + '</svg>'


def _legend(svg: Svg, names: list, y: float) -> None:
    x = 16.0
    for i, name in enumerate(names):
        label = _clip(name, 140, 12)
        room = 16 + _width_of(label, 12) + 16
        if x + room > svg.w - 12:
            x = 16.0
            y += 18
        svg.add(f'<rect x="{x:.1f}" y="{y - 9:.1f}" width="10" height="10" rx="2" fill="{SERIES[i]}"/>')
        svg.text(x + 15, y, label, 12)
        x += room


def _fold(series: dict) -> dict:
    """At most eight series: a ninth colour would look like one of the eight."""
    if len(series) <= MOST_SERIES:
        return series
    names = sorted(series, key=lambda k: -sum(abs(v or 0) for v in series[k]))
    keep = names[:MOST_SERIES - 1]
    rest = [k for k in series if k not in keep]
    length = len(next(iter(series.values())))
    other = [sum((series[k][i] or 0) for k in rest) for i in range(length)]
    return {**{k: series[k] for k in series if k in keep}, '其他': other}


def bar(labels: list, series, title='', subtitle='', width=720, height=380, unit='') -> str:
    """Upright bars from one baseline. series: a list of numbers, or {name: list} for bars side by side."""
    data = _fold(series if isinstance(series, dict) else {'': series})
    names = [k for k in data]
    values = [v for s in data.values() for v in s if v is not None]
    if not values:
        return empty(title, width, height)
    lo, hi = min(0, *values), max(0, *values)
    scale = ticks(lo, hi)
    lo, hi = scale[0], scale[-1]
    svg = Svg(width, height, title, subtitle)
    legend = 22 if len(names) > 1 else 0
    top, bottom, left, right = svg.top + 8 + legend, height - 44, 58, width - 16
    if legend:
        _legend(svg, names, svg.top + 8)
    y_of = lambda v: bottom - (v - lo) / (hi - lo or 1) * (bottom - top)  # noqa: E731
    for t in scale:
        svg.add(f'<line x1="{left}" x2="{right}" y1="{y_of(t):.1f}" y2="{y_of(t):.1f}" stroke="{GRID}"/>')
        svg.text(left - 8, y_of(t) + 4, short(t), 11, INK2, 'end')
    band = (right - left) / max(1, len(labels))
    count = len(names)
    thick = max(2.0, min(24.0, (band * .7 - 2 * (count - 1)) / count))
    every = max(1, math.ceil(_width_of(max(map(str, labels), key=len), 11) / band))
    for i, label in enumerate(labels):
        mid = left + band * (i + .5)
        if i % every == 0:
            svg.text(mid, bottom + 18, _clip(label, band * every - 4, 11), 11, INK2, 'middle')
        for k, name in enumerate(names):
            v = data[name][i] if i < len(data[name]) else None
            if v is None:
                continue
            x = mid - (count * thick + (count - 1) * 2) / 2 + k * (thick + 2)
            y0, y1 = y_of(0), y_of(v)
            high, low = min(y0, y1), max(y0, y1)
            size = max(low - high, 1)
            r = min(4, size, thick / 2)
            note = f'{label}{" · " + name if name else ""}：{v:,.6g}{unit}'
            if v >= 0:  # rounded at the data's end, square at the baseline
                path = f'M{x:.1f} {low:.1f}V{high + r:.1f}Q{x:.1f} {high:.1f} {x + r:.1f} {high:.1f}H{x + thick - r:.1f}Q{x + thick:.1f} {high:.1f} {x + thick:.1f} {high + r:.1f}V{low:.1f}Z'
            else:
                path = f'M{x:.1f} {high:.1f}V{low - r:.1f}Q{x:.1f} {low:.1f} {x + r:.1f} {low:.1f}H{x + thick - r:.1f}Q{x + thick:.1f} {low:.1f} {x + thick:.1f} {low - r:.1f}V{high:.1f}Z'
            svg.add(f'<path d="{path}" fill="{SERIES[k]}"><title>{escape(note)}</title></path>')
    svg.add(f'<line x1="{left}" x2="{right}" y1="{y_of(0):.1f}" y2="{y_of(0):.1f}" stroke="{INK2}"/>')
    return svg.done()


def hbar(labels: list, values: list, title='', subtitle='', width=720, unit='', sort=True) -> str:
    """Bars lying down, for long names. One series, largest first; the value is at the tip."""
    pairs = list(zip(labels, values))
    if not pairs:
        return empty(title, width, 200)
    if sort:
        pairs.sort(key=lambda p: -(p[1] or 0))
    row = 34
    height = 62 + row * len(pairs)
    svg = Svg(width, height, title, subtitle)
    label_room = min(200, max(_width_of(p[0], 12) for p in pairs) + 12)
    left, right, top = 16 + label_room, width - 70, svg.top + 8
    most = max(abs(p[1] or 0) for p in pairs) or 1
    for i, (label, v) in enumerate(pairs):
        y = top + i * row
        svg.text(left - 8, y + 16, _clip(label, label_room - 4, 12), 12, INK, 'end')
        length = max(1.0, abs(v or 0) / most * (right - left))
        r = min(4, length)
        svg.add(f'<path d="M{left} {y + 4}H{left + length - r:.1f}Q{left + length:.1f} {y + 4} {left + length:.1f} {y + 4 + r}V{y + 20}Q{left + length:.1f} {y + 24} {left + length - r:.1f} {y + 24}H{left}Z" fill="{SERIES[0]}">'
                f'<title>{escape(str(label))}：{(v or 0):,.6g}{unit}</title></path>')
        svg.text(left + length + 6, y + 18, short(v or 0) + unit, 12, INK)
    return svg.done()


def line(labels: list, series, title='', subtitle='', width=720, height=380, unit='') -> str:
    """Lines over a shared x; one y axis. The ends are named when there are few."""
    data = _fold(series if isinstance(series, dict) else {'': series})
    names = list(data)
    values = [v for s in data.values() for v in s if v is not None]
    if not values or not labels:
        return empty(title, width, height)
    lo, hi = min(values), max(values)
    if lo > 0 and lo < hi * .4:
        lo = 0
    scale = ticks(lo, hi if hi > lo else lo + 1)
    lo, hi = scale[0], scale[-1]
    svg = Svg(width, height, title, subtitle)
    legend = 22 if len(names) > 1 else 0
    top, bottom, left, right = svg.top + 8 + legend, height - 44, 58, width - (96 if 1 < len(names) <= 4 else 24)
    if legend:
        _legend(svg, names, svg.top + 8)
    y_of = lambda v: bottom - (v - lo) / (hi - lo or 1) * (bottom - top)  # noqa: E731
    x_of = lambda i: left + (right - left) * (i / max(1, len(labels) - 1))  # noqa: E731
    for t in scale:
        svg.add(f'<line x1="{left}" x2="{right}" y1="{y_of(t):.1f}" y2="{y_of(t):.1f}" stroke="{GRID}"/>')
        svg.text(left - 8, y_of(t) + 4, short(t), 11, INK2, 'end')
    every = max(1, math.ceil((_width_of(max(map(str, labels), key=len), 11) + 10) / ((right - left) / max(1, len(labels) - 1) or 1)))
    for i, label in enumerate(labels):
        if i % every == 0:
            svg.text(x_of(i), bottom + 18, label, 11, INK2, 'middle')
    for k, name in enumerate(names):
        points = [(x_of(i), y_of(v)) for i, v in enumerate(data[name]) if v is not None]
        path = ' '.join(('M' if i == 0 else 'L') + f'{x:.1f} {y:.1f}' for i, (x, y) in enumerate(points))
        if len(names) == 1 and points:
            svg.add(f'<path d="{path} L{points[-1][0]:.1f} {bottom} L{points[0][0]:.1f} {bottom}Z" fill="{SERIES[0]}" opacity=".1"/>')
        svg.add(f'<path d="{path}" fill="none" stroke="{SERIES[k]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for i, v in enumerate(data[name]):
            if v is not None:  # a big invisible circle: the note appears without having to hit a thin line
                svg.add(f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="9" fill="transparent"><title>{escape(str(labels[i]))}{" · " + escape(name) if name else ""}：{v:,.6g}{escape(unit)}</title></circle>')
        if points:
            x, y = points[-1]
            svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{SERIES[k]}" stroke="{SURFACE}" stroke-width="2"/>')
            if 1 < len(names) <= 4:
                svg.text(x + 9, y + 4, _clip(name, 84, 11), 11, INK)
    return svg.done()


def donut(labels: list, values: list, title='', subtitle='', width=520, height=320) -> str:
    """Parts of one whole; at most six parts, the rest fold into 其他."""
    pairs = sorted(zip(labels, values), key=lambda p: -(p[1] or 0))
    if len(pairs) > 6:
        pairs = pairs[:5] + [('其他', sum(p[1] or 0 for p in pairs[5:]))]
    total = sum(p[1] or 0 for p in pairs)
    if total <= 0:
        return empty(title, width, height)
    svg = Svg(width, height, title, subtitle)
    cx, cy, r = 150, (svg.top + height) / 2, min(106, (height - svg.top) / 2 - 12)
    start = -math.pi / 2
    for i, (label, v) in enumerate(pairs):
        share = (v or 0) / total
        gap = min(.02, share * math.pi)
        a0, a1 = start + gap, start + share * 2 * math.pi - gap
        large = 1 if a1 - a0 > math.pi else 0
        svg.add(f'<path d="M{cx + r * math.cos(a0):.1f} {cy + r * math.sin(a0):.1f}A{r} {r} 0 {large} 1 {cx + r * math.cos(a1):.1f} {cy + r * math.sin(a1):.1f}" fill="none" stroke="{SERIES[i]}" stroke-width="30">'
                f'<title>{escape(str(label))}：{(v or 0):,.6g}（{share:.1%}）</title></path>')
        start += share * 2 * math.pi
        y = svg.top + 26 + i * 24
        svg.add(f'<rect x="300" y="{y - 10}" width="11" height="11" rx="2" fill="{SERIES[i]}"/>')
        svg.text(317, y, _clip(label, width - 390, 12), 12, INK)
        svg.text(width - 16, y, f'{share:.0%}', 12, INK2, 'end')
    return svg.done()


def scatter(xs: list, ys: list, title='', subtitle='', xname='', yname='', width=720, height=420) -> str:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if not pairs:
        return empty(title, width, height)
    scale_x = ticks(min(p[0] for p in pairs), max(p[0] for p in pairs))
    scale_y = ticks(min(p[1] for p in pairs), max(p[1] for p in pairs))
    svg = Svg(width, height, title, subtitle)
    top, bottom, left, right = svg.top + (24 if yname else 8), height - 52, 62, width - 20
    x_of = lambda v: left + (v - scale_x[0]) / (scale_x[-1] - scale_x[0] or 1) * (right - left)  # noqa: E731
    y_of = lambda v: bottom - (v - scale_y[0]) / (scale_y[-1] - scale_y[0] or 1) * (bottom - top)  # noqa: E731
    for t in scale_y:
        svg.add(f'<line x1="{left}" x2="{right}" y1="{y_of(t):.1f}" y2="{y_of(t):.1f}" stroke="{GRID}"/>')
        svg.text(left - 8, y_of(t) + 4, short(t), 11, INK2, 'end')
    for t in scale_x:
        svg.text(x_of(t), bottom + 18, short(t), 11, INK2, 'middle')
    for x, y in pairs[:2000]:
        svg.add(f'<circle cx="{x_of(x):.1f}" cy="{y_of(y):.1f}" r="4" fill="{SERIES[0]}" fill-opacity=".62" stroke="{SURFACE}" stroke-width="1"><title>{x:,.6g}, {y:,.6g}</title></circle>')
    if xname:
        svg.text((left + right) / 2, height - 12, xname, 12, INK2, 'middle')
    if yname:
        svg.text(left, top - 10, yname, 12, INK2)
    return svg.done()


def histogram(values: list, title='', subtitle='', bins=12, width=720, height=340) -> str:
    data = [v for v in values if v is not None]
    if not data:
        return empty(title, width, height)
    lo, hi = min(data), max(data)
    if lo == hi:
        return bar([short(lo)], [len(data)], title, subtitle, width, height)
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in data:
        counts[min(bins - 1, int((v - lo) / step))] += 1
    return bar([short(round(lo + i * step, 4)) for i in range(bins)], counts, title, subtitle, width, height)


def empty(title: str, width: int, height: int) -> str:
    svg = Svg(width, height, title)
    svg.text(width / 2, height / 2, '没有数据', 14, INK2, 'middle')
    return svg.done()
