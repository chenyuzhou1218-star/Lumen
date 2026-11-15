"""How an AI that cannot hear gets to know what it made: measure the sound, read the score, and draw both.

Everything here is a number or a picture, and every note it gives is a measurement. It says what is too loud, muddy, empty or
out of key. It cannot say a tune is beautiful, and the report says so: that is the user's ear.
"""
from __future__ import annotations

import cmath
import math
from pathlib import Path

BANDS = (('超低', 20, 60), ('低音', 60, 250), ('低中', 250, 800), ('中频', 800, 2500), ('高中', 2500, 6000), ('高频', 6000, 16000))
# a usual share of the energy per band, in dB relative to the whole, for a mixed piece of music
USUAL = {'超低': (-16, -5), '低音': (-9, -2), '低中': (-12, -3), '中频': (-17, -6), '高中': (-26, -11), '高频': (-36, -16)}
NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')


def db(x: float) -> float:
    return 20 * math.log10(x) if x > 1e-9 else -180.0


def fft(values: list) -> list:
    """Radix 2; len(values) is a power of two."""
    n = len(values)
    if n == 1:
        return [complex(values[0])]
    even, odd = fft(values[0::2]), fft(values[1::2])
    out = [0j] * n
    for k in range(n // 2):
        t = cmath.exp(-2j * math.pi * k / n) * odd[k]
        out[k], out[k + n // 2] = even[k] + t, even[k] - t
    return out


def spectrum_frames(mono: list, sr: int, size: int = 1024, most: int = 180) -> list:
    """Magnitudes of about `most` evenly spread windows."""
    if len(mono) < size:
        return []
    hop = max(size, (len(mono) - size) // most)
    window = [.5 - .5 * math.cos(2 * math.pi * i / (size - 1)) for i in range(size)]
    frames = []
    for start in range(0, len(mono) - size, hop):
        part = [a * b for a, b in zip(mono[start:start + size], window)]
        frames.append([abs(c) for c in fft(part)[:size // 2]])
    return frames


def measure(left: list, right: list, sr: int) -> dict:
    n = len(left)
    if not n:
        return {}
    peak = max(max(abs(a), abs(b)) for a, b in zip(left, right))
    clipped = sum(1 for a in left if abs(a) >= .999) + sum(1 for a in right if abs(a) >= .999)
    mono = [(a + b) * .5 for a, b in zip(left, right)]
    rms = math.sqrt(sum(a * a for a in mono) / n)
    side = math.sqrt(sum(((a - b) * .5) ** 2 for a, b in zip(left, right)) / n)
    frames = spectrum_frames(mono, sr)
    size = 1024
    energy = {name: 0.0 for name, _, _ in BANDS}
    whole = 1e-12
    for frame in frames:
        for k, mag in enumerate(frame):
            hz = k * sr / size
            power = mag * mag
            for name, lo, hi in BANDS:
                if lo <= hz < hi:
                    energy[name] += power
                    whole += power
                    break
    bands = {name: round(10 * math.log10(max(energy[name], 1e-12) / whole), 1) for name in energy}
    second = max(1, sr // 2)
    curve = []
    for start in range(0, n, second):
        part = mono[start:start + second]
        curve.append(round(db(math.sqrt(sum(a * a for a in part) / max(1, len(part)))), 1))
    silent = longest = 0
    for level in curve:
        silent = silent + 1 if level < -50 else 0
        longest = max(longest, silent)
    played = [c for c in curve if c > -50]
    return {'seconds': round(n / sr, 2), 'peak_db': round(db(peak), 1), 'rms_db': round(db(rms), 1), 'crest_db': round(db(peak) - db(rms), 1), 'clipped_samples': clipped,
            'stereo_width': round(side / max(rms, 1e-9), 2), 'bands_db': bands, 'level_curve_db': curve, 'dynamic_range_db': round(max(played) - min(played), 1) if played else 0.0,
            'longest_silence_s': longest * .5}


def sound_notes(m: dict) -> list:
    """Measured faults, in words."""
    out = []
    if not m:
        return ['没有声音：这首歌是空的。']
    if m['clipped_samples']:
        out.append(f"有 {m['clipped_samples']} 个采样削波，会听到破音：把音轨的 vol 调低。")
    if m['rms_db'] < -24:
        out.append(f"整体太小声（{m['rms_db']} dB）。")
    if m['crest_db'] < 6:
        out.append(f"压得太死，只有 {m['crest_db']} dB 的动态：鼓或低音太满。")
    if m['stereo_width'] < .08:
        out.append('声场几乎是单声道：把和弦和垫音 pan 开，或者加 wide。')
    if m['stereo_width'] > 1.1:
        out.append('左右相差太大，在手机这种单声道设备上会变薄。')
    if m['dynamic_range_db'] < 3 and m['seconds'] > 30:
        out.append('从头到尾一样响：一首曲子要有起伏，试试让主歌薄、副歌厚，加减乐器而不是调音量。')
    if m['longest_silence_s'] > 2.5 and m['seconds'] > 8:
        out.append(f"中间有 {m['longest_silence_s']} 秒几乎没有声音。")
    words = {'超低': ('超低频太多，小音箱上只剩轰鸣：kick、sub_bass 减一点，或给别的轨加 low_cut。', ''),
             '低音': ('低音太重，盖住了别的：减低音轨 vol，或打开 duck。', '低音太薄，曲子会发飘：加 bass 或把低音轨调高。'),
             '低中': ('低中频太多，声音发闷、糊：给和弦、垫音、弦乐加 low_cut=200。', '低中频太少，声音发空。'),
             '中频': ('中频太多，声音发硬、顶耳朵。', '中频太少，主旋律站不出来：主旋律的 vol 加一点。'),
             '高中': ('高中频太多，刺耳：high_cut=6000 或减小镲。', '高中频太少，声音发闷，像隔着墙：加镲、拨弦，或减少 high_cut。'),
             '高频': ('高频太多，发嘶。', '')}
    for name, (lo, hi) in USUAL.items():
        value = m['bands_db'].get(name)
        if value is None:
            continue
        if value > hi:
            out.append(f'{name} {value} dB，偏高（常见 {lo} 到 {hi}）。' + words[name][0])
        elif value < lo and words[name][1]:  # a piano piece has no sub bass, and that is no fault
            out.append(f'{name} {value} dB，偏低（常见 {lo} 到 {hi}）。' + words[name][1])
    return out


def score_notes(score: dict, ranges: dict) -> list:
    """What can be known about the music from the notes alone. Rules of thumb: a note here can be right on purpose."""
    out = list(score.get('written_notes') or [])
    beats = score.get('beats_per_bar') or 4
    scale = set(score.get('scale') or [])
    pitched = []
    for t in score.get('tracks', []):
        notes = [e for e in t['notes'] if isinstance(e['m'], int)]
        pitched.append((t, notes))
        lo, hi = ranges.get(t['instrument'], (0, 127))
        wrong = [e for e in notes if not lo <= e['m'] <= hi]
        if wrong:
            out.append(f"{t['name']}：{len(wrong)} 个音超出 {t['instrument']} 的音域（{_name(lo)} 到 {_name(hi)}），会失真或不像这件乐器。")
    every = [e for _, notes in pitched for e in notes]
    if every and scale:
        strange = [e for e in every if e['m'] % 12 not in scale]
        share = len(strange) / len(every)
        if share > .22:
            out.append(f'{share:.0%} 的音不在 {score.get("key")} 里，听起来可能走调；如果是有意转调就不用管。')
    clashes = _clashes(pitched, beats)
    if clashes:
        out.append(f'有 {len(clashes)} 处两个声部在强拍上差半音（例如第 {clashes[0][0]} 小节 {clashes[0][1]}），容易刺耳。')
    bars = int(score.get('end_beat', 0) // beats)
    tracks_of_bar = [0] * max(bars, 1)
    for t, notes in pitched + [(t, t['notes']) for t in score.get('tracks', []) if t['instrument'] == 'drums']:
        for b in {int(e['b'] // beats) for e in notes}:
            if b < len(tracks_of_bar):
                tracks_of_bar[b] += 1
    if bars >= 16 and len(set(tracks_of_bar)) == 1:
        out.append('每小节的乐器数量都一样：没有层次。开头少、后面多，结尾再收。')
    if bars >= 8 and all(c == 0 for c in tracks_of_bar[-2:]):
        out.append('最后两小节是空的。')
    melody = _melody(pitched)
    if melody:
        same = _sameness(melody, beats)
        if same > .8 and bars >= 16:
            out.append(f'主旋律 {same:.0%} 的小节是重复的：后半段要变，升高八度、换节奏或者换和声。')
        widest = max(e['m'] for e in melody) - min(e['m'] for e in melody)
        if widest < 5 and len(melody) > 24:
            out.append(f'主旋律只在 {widest} 个半音里打转，不够有起伏。')
    if not any(t['instrument'] == 'drums' for t in score.get('tracks', [])) and score.get('tempo', 0) > 120 and bars >= 16:
        out.append('这么快的曲子没有鼓：要的就是这样吗？')
    return out


def _name(midi: int) -> str:
    return f'{NAMES[midi % 12]}{midi // 12 - 1}'


def _clashes(pitched: list, beats: int) -> list:
    found = []
    strong = {}
    for t, notes in pitched:
        for e in notes:
            if abs(e['b'] % 1) < 1e-6 and e['b'] % beats in (0, beats // 2):
                strong.setdefault(e['b'], []).append((t['name'], e))
    for at, items in sorted(strong.items()):
        for i, (na, a) in enumerate(items):
            for nb, b in items[i + 1:]:
                if na != nb and abs(a['m'] - b['m']) in (1, 13) and min(a['d'], b['d']) >= .9:
                    found.append((int(at // beats) + 1, f'{na} 的 {_name(a["m"])} 和 {nb} 的 {_name(b["m"])}'))
    return found


def _melody(pitched: list) -> list:
    """The track with the highest notes among those that move: the one the ear follows."""
    best, top = None, -1.0
    for _, notes in pitched:
        if len(notes) < 8:
            continue
        mean = sum(e['m'] for e in notes) / len(notes)
        if mean > top:
            best, top = notes, mean
    return best or []


def _sameness(notes: list, beats: int) -> float:
    bars: dict = {}
    for e in notes:
        bars.setdefault(int(e['b'] // beats), []).append((round(e['b'] % beats, 2), e['m']))
    shapes = [tuple(sorted(v)) for v in bars.values()]
    if len(shapes) < 2:
        return 0.0
    return 1 - len(set(shapes)) / len(shapes)


# --- pictures ---------------------------------------------------------------------------------------------------------

TRACK_COLOURS = ('#ff9f5a', '#6cc6ff', '#a4e57c', '#f27fb0', '#c4a0ff', '#ffe066', '#66e0c8', '#ff7b6b', '#9ab0ff', '#d8d8d8')


def picture(path: Path, score: dict, left: list, sr: int, measured: dict) -> None:
    """Three strips over one time axis: the notes, the spectrum, the loudness. The song as an eye can check it."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1280, 720
    font = None  # no Chinese font: the labels stay in plain letters
    for path in ('C:/Windows/Fonts/msyh.ttc', '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/Library/Fonts/Arial Unicode.ttf'):  # Windows, then macOS
        try:
            font = ImageFont.truetype(path, 13)
            break
        except OSError:
            continue

    def label(at, text):
        d.text(at, text if font else text.encode('ascii', 'replace').decode(), fill='#b8bac6', font=font)

    img = Image.new('RGB', (width, height), '#14151a')
    d = ImageDraw.Draw(img)
    seconds = max(measured.get('seconds') or 1, 1)
    per_beat = 60 / max(score.get('tempo') or 100, 1)

    def x_of(sec):
        return 30 + (width - 60) * sec / seconds

    roll = (20, 340)
    notes = [(i, e) for i, t in enumerate(score.get('tracks', [])) for e in t['notes'] if isinstance(e['m'], int)]
    if notes:
        low, high = min(e['m'] for _, e in notes), max(e['m'] for _, e in notes)
        span = max(high - low, 12)
        for i, e in notes:
            y = roll[1] - (e['m'] - low) / span * (roll[1] - roll[0] - 6)
            x0, x1 = x_of(e['b'] * per_beat), x_of((e['b'] + e['d']) * per_beat)
            d.rectangle((x0, y - 2, max(x1, x0 + 2), y + 1), fill=TRACK_COLOURS[i % len(TRACK_COLOURS)])
    for s in score.get('sections', []):
        x = x_of(s['start'] * per_beat)
        d.line((x, roll[0], x, 700), fill='#40424e')
        label((x + 4, 2), str(s['name']))
    for i, t in enumerate(score.get('tracks', [])[:12]):
        drum_hits = [e for e in t['notes'] if not isinstance(e['m'], int)]
        for e in drum_hits:
            x = x_of(e['b'] * per_beat)
            d.line((x, 342 + i * 3, x, 344 + i * 3), fill=TRACK_COLOURS[i % len(TRACK_COLOURS)])
    frames = spectrum_frames(left, sr, 1024, 300)
    top, bottom = 390, 610
    if frames:
        peak = max(max(f) for f in frames) or 1.0
        rows = bottom - top
        size = len(frames[0])
        for col, frame in enumerate(frames):
            x0 = 30 + (width - 60) * col / len(frames)
            x1 = 30 + (width - 60) * (col + 1) / len(frames)
            for row in range(rows):
                hz = 30 * (16000 / 30) ** (row / rows)  # log frequency, as ears hear it
                k = min(size - 1, int(hz * 2 * size / sr))
                v = max(0.0, 1 + db(frame[k] / peak) / 70)
                r, g, b = int(255 * min(1, v * 1.4)), int(255 * v * v), int(120 * v ** 3 + 40 * v)
                if r + g + b > 24:
                    d.line((x0, bottom - row, x1, bottom - row), fill=(r, g, b))
    curve = measured.get('level_curve_db') or []
    if curve:
        points = [(30 + (width - 60) * i / max(1, len(curve) - 1), 700 - max(0.0, 60 + c) / 60 * 80) for i, c in enumerate(curve)]
        d.line(points, fill='#7fd4ff', width=2)
    label((30, 372), '频谱（低到高）')
    label((30, 616), f"响度：峰值 {measured.get('peak_db')} dB，平均 {measured.get('rms_db')} dB")
    img.save(path)
