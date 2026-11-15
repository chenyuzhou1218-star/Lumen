"""What can honestly be said about a relation between numbers, with how sure it is."""
from __future__ import annotations

import statistics


def pairs(xs: list, ys: list) -> list:
    return [(x, y) for x, y in zip(xs, ys) if isinstance(x, (int, float)) and isinstance(y, (int, float))]


def correlate(xs: list, ys: list) -> dict:
    """Pearson's r. It says how straight the line is, not why."""
    data = pairs(xs, ys)
    if len(data) < 3:
        return {'r': None, 'n': len(data), 'says': '数据太少，说不出关系'}
    r = statistics.correlation([a for a, _ in data], [b for _, b in data])
    size = abs(r)
    word = '几乎没有' if size < .2 else '较弱的' if size < .4 else '中等的' if size < .7 else '很强的'
    way = '同向' if r > 0 else '反向'
    return {'r': round(r, 3), 'n': len(data), 'says': f'{word}{way}关系（r={r:.2f}，{len(data)} 个点）。这不能说明谁导致了谁。'}


def trend(values: list) -> dict:
    """A straight line through a series: the slope per step, and how much of the movement it explains."""
    ys = [v for v in values if isinstance(v, (int, float))]
    if len(ys) < 3:
        return {'slope': None, 'says': '数据太少，看不出趋势'}
    xs = list(range(len(ys)))
    slope, start = statistics.linear_regression(xs, ys)
    fit = statistics.correlation(xs, ys) ** 2 if len(set(ys)) > 1 else 0
    word = '上升' if slope > 0 else '下降'
    return {'slope': round(slope, 4), 'start': round(start, 4), 'fit': round(fit, 3), 'says': f'平均每步{word} {abs(slope):,.2f}，直线能解释 {fit:.0%} 的变化。'}


def forecast(values: list, steps: int = 3) -> dict:
    """The same line carried forward. It holds only if nothing changes: the wider the band, the less to trust it."""
    t = trend(values)
    if t['slope'] is None:
        return {'next': [], 'says': t['says']}
    ys = [v for v in values if isinstance(v, (int, float))]
    n = len(ys)
    residual = [y - (t['start'] + t['slope'] * i) for i, y in enumerate(ys)]
    spread = statistics.stdev(residual) if n > 2 else 0.0
    next_ = [round(t['start'] + t['slope'] * (n + i), 2) for i in range(steps)]
    return {'next': next_, 'plus_minus': round(2 * spread, 2), 'says': f'照这条线往后 {steps} 步：{next_}，前后约差 {2 * spread:,.2f}。只在情况不变时成立。'}


def share(values: list) -> list:
    total = sum(v for v in values if isinstance(v, (int, float))) or 1
    return [round(v / total, 4) if isinstance(v, (int, float)) else None for v in values]


def rank_outliers(values: list) -> list:
    data = sorted(v for v in values if isinstance(v, (int, float)))
    if len(data) < 8:
        return []
    q = statistics.quantiles(data, n=4)
    spread = q[2] - q[0]
    return [v for v in data if v < q[0] - 3 * spread or v > q[2] + 3 * spread]

