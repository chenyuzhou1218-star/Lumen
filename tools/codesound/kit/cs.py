"""The language a song is written in. song.py does `import cs`, describes the music, and the runner renders it.

Time is in beats. Notes are named (D4) or numbered by the scale (1 2 3, b3, #4, 5' one octave up, 5, one octave down), so a tune
written in numbers cannot leave the key by accident. A bar line | is only a check: if a bar does not add up, you are told.
"""
from __future__ import annotations

import math
import random
import re
import sys

import synth
from synth import DRUMS, INSTRUMENTS, ROLE_LOUDNESS

NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SCALES = {'major': (0, 2, 4, 5, 7, 9, 11), 'minor': (0, 2, 3, 5, 7, 8, 10), 'dorian': (0, 2, 3, 5, 7, 9, 10), 'phrygian': (0, 1, 3, 5, 7, 8, 10),
          'lydian': (0, 2, 4, 6, 7, 9, 11), 'mixolydian': (0, 2, 4, 5, 7, 9, 10), 'harmonic_minor': (0, 2, 3, 5, 7, 8, 11),
          'pentatonic': (0, 2, 4, 7, 9), 'pentatonic_minor': (0, 3, 5, 7, 10), 'gong': (0, 2, 4, 7, 9), 'shang': (0, 2, 5, 7, 10), 'jue': (0, 3, 5, 8, 10),
          'zhi': (0, 2, 5, 7, 9), 'yu': (0, 3, 5, 7, 10), 'blues': (0, 3, 5, 6, 7, 10)}
CHORDS = {'': (0, 4, 7), 'm': (0, 3, 7), '7': (0, 4, 7, 10), 'maj7': (0, 4, 7, 11), 'm7': (0, 3, 7, 10), 'dim': (0, 3, 6), 'dim7': (0, 3, 6, 9), 'aug': (0, 4, 8),
          'sus2': (0, 2, 7), 'sus4': (0, 5, 7), '6': (0, 4, 7, 9), 'm6': (0, 3, 7, 9), '9': (0, 4, 7, 10, 14), 'add9': (0, 4, 7, 14), 'm9': (0, 3, 7, 10, 14),
          'maj9': (0, 4, 7, 11, 14), '5': (0, 7)}
CHORD_RE = re.compile(r'^([A-G][#b]?)(maj9|maj7|dim7|dim|aug|sus2|sus4|add9|m9|m7|m6|m|9|7|6|5|)(?:/([A-G][#b]?))?$')
TOKEN_RE = re.compile(r"\[[^\]]*\](?::[0-9./]+)?|\S+")
PATTERNS = {
    'rock': {'kick': 'x...x...x...x...', 'snare': '....x.......x...', 'hat': 'x.x.x.x.x.x.x.x.'},
    'four': {'kick': 'x...x...x...x...', 'clap': '....x.......x...', 'open_hat': '..x...x...x...x.', 'hat': 'x.x.x.x.x.x.x.x.'},
    'halftime': {'kick': 'x.....x.........', 'snare': '........x.......', 'hat': 'x.x.x.x.x.x.x.x.'},
    'trap': {'kick': 'x.....x...x.....', 'clap': '........x.......', 'hat': 'x.x.x.xxx.x.x.xx'},
    'ballad': {'kick': 'x.......x.......', 'rim': '....x.......x...', 'hat': 'x...x...x...x...'},
    'march': {'snare': 'x.xxx.xxx.xxx.xx', 'kick': 'x...............', 'timpani': '........x.......'},
    'war': {'war_drum': 'x.....x.x.......', 'taiko': '....x.......x.x.', 'wood_block': '..x...x...x...x.'},
    'ritual': {'taiko': 'x.......x.......', 'wood_block': '....x.......x...', 'shaker': '..x...x...x...x.'},
    'waltz': {'kick': 'x...........', 'rim': '....x...x...', 'hat': 'x...x...x...'},
}
SETTINGS: dict = {'sr': 44100, 'stems': False, 'seed': 7}  # the runner sets these


class SongError(Exception):
    """A mistake in song.py, in words."""


def pitch(name) -> int:
    """'C4' -> 60, a number stays a number."""
    if isinstance(name, (int, float)):
        return int(name)
    m = re.match(r'^([A-G])([#b]*)(-?\d)$', str(name).strip())
    if not m:
        raise SongError(f'不是音名：{name}（写成 C4、F#3、Bb2）')
    return 12 * (int(m.group(3)) + 1) + NOTE[m.group(1)] + m.group(2).count('#') - m.group(2).count('b')


def freq_of(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def chord_notes(symbol: str) -> tuple:
    """'Dm7/F' -> (root pitch class, intervals, bass pitch class)."""
    m = CHORD_RE.match(symbol)
    if not m:
        raise SongError(f'看不懂这个和弦：{symbol}（例如 Dm7、Bbmaj7、Csus4、F/A）')
    root = pitch(m.group(1) + '0') % 12
    return root, CHORDS[m.group(2)], pitch(m.group(3) + '0') % 12 if m.group(3) else root


class Song:
    def __init__(self):
        self.tempo = 100.0
        self.key_name = 'C major'
        self.tonic = 60
        self.scale = SCALES['major']
        self.beats_per_bar = 4
        self.swing = 0.0
        self.title = ''
        self.tracks: list = []
        self.saved: list = []  # (name, sound): single sound effects, out/sfx
        self.sections: list = []
        self.section_id = 0
        self.section_start = 0.0
        self.seen = []  # notes about how it was written
        self.reverb_size = .8
        self.end_beat = 0.0
        self.rnd = random.Random(SETTINGS['seed'])
        self.loop = False
        self.fade_in = self.fade_out = 0.0
        self.level = -16.0
        self.shift = 0
        self.tempo_changes: list = []

    def beat_to_s(self, beat: float) -> float:
        if not self.tempo_changes:
            return beat * 60.0 / self.tempo
        seconds, at, bpm = 0.0, 0.0, self.tempo
        for change, new in self.tempo_changes:
            if beat <= change:
                break
            seconds += (change - at) * 60.0 / bpm
            at, bpm = change, new
        return seconds + (beat - at) * 60.0 / bpm


S = Song()


def _fresh() -> None:
    global S
    S = Song()


def compose(style='古风', seconds=90, seed=1) -> dict:
    """A whole piece by rule, in a style: 古风 战斗 史诗 悬疑 轻音乐 田园 电子 合成器 摇滚 爵士 芯片 儿歌 冥想 菜单. Another seed is another piece."""
    import compose as writer

    return writer.compose(sys.modules[__name__], style, seconds, seed)


def fade(fade_in=0.0, out=0.0) -> None:
    """Seconds of fade at the start and the end of the whole song."""
    S.fade_in, S.fade_out = fade_in, out


def master(level='标准') -> None:
    """How loud the finished song is: 轻柔 (-20 dB, for reading), 标准 (-16), 响亮 (-13, for a video or a game)."""
    if level not in LEVELS:
        raise SongError(f'响度有：{"、".join(LEVELS)}')
    S.level = LEVELS[level]


def transpose(semitones: int) -> None:
    """Moves everything written after this up or down: a last chorus a step higher."""
    S.shift = semitones


def tempo_at(beat: float, bpm: float) -> None:
    """From this beat the tempo changes: a slower ending, a faster last run."""
    S.tempo_changes.append((beat, float(bpm)))
    S.tempo_changes.sort()


def midi_file(path: str, instrument='piano', vol=.8) -> 'Track':
    """Plays a .mid file on any instrument here: every channel's notes go to one track."""
    from midi_read import read

    data = read(path)
    if data['tempo']:
        S.tempo = data['tempo']
    t = track(instrument, vol=vol)
    for start, length, note, vel in data['notes']:
        t._add(start, length, note, vel / 127)
        S.end_beat = max(S.end_beat, start + length)
    return t


def song(tempo=100, key='C major', beats=4, swing=0.0, title='', reverb=.8, loop=False) -> None:
    """Start here. key: 'D minor', 'G dorian', 'C gong' (Chinese modes gong shang jue zhi yu), swing 0..0.6. loop=True: the tail wraps round to the start, for a game's music."""
    parts = key.split()
    if len(parts) != 2 or parts[1] not in SCALES:
        raise SongError(f'调要写成 "D minor"；调式可以是 {", ".join(SCALES)}')
    S.tempo, S.key_name, S.beats_per_bar, S.swing, S.title, S.reverb_size = float(tempo), key, beats, swing, title, reverb
    S.loop = loop
    S.tonic = pitch(parts[0] + '4')
    S.scale = SCALES[parts[1]]


class section:
    """with cs.section('verse', 8): every track starts this block at the same bar, whatever came before."""

    def __init__(self, name: str, bars: int):
        self.name, self.bars = name, bars

    def __enter__(self):
        S.section_id += 1
        S.sections.append({'name': self.name, 'start': S.section_start, 'bars': self.bars})
        return self

    def __exit__(self, kind, value, tb):
        if kind is None:
            S.section_start += self.bars * S.beats_per_bar
            S.end_beat = max(S.end_beat, S.section_start)
        return False


def fx() -> synth.Fx:
    """cs.fx().coin(): the sound effects (their names are in the guide)."""
    return synth.Fx(SETTINGS['sr'])


def save(name: str, sound: list) -> None:
    """Keep one sound as its own file: out/sfx/<name>.wav."""
    if not re.fullmatch(r'[\w\- ]{1,60}', name):
        raise SongError(f'声音的名字只用字母、数字、中文、下划线：{name}')
    S.saved.append((name, sound))


class Track:
    def __init__(self, instrument: str, vol=.8, pan=0.0, reverb=.15, delay=0.0, wide=0.0, low_cut=0.0, high_cut=0.0, duck=0.0, name='', human=.5, drive=0.0, chorus=0.0, tremolo=0.0, crush=0.0, sweep=None):
        if instrument != 'drums' and instrument != 'sounds' and instrument not in INSTRUMENTS:
            raise SongError(f'没有 {instrument} 这个乐器。有：{", ".join(sorted(INSTRUMENTS))}，以及 drums、sounds')
        self.instrument, self.vol, self.pan, self.reverb, self.delay = instrument, vol, pan, reverb, delay
        self.wide, self.low_cut, self.high_cut, self.duck, self.human = wide, low_cut, high_cut, duck, human
        self.drive, self.chorus, self.tremolo, self.crush, self.sweep = drive, chorus, tremolo, crush, sweep
        self.name = name or f'{instrument}{len(S.tracks) + 1}'
        self.notes: list = []   # {'b': beat, 'd': beats, 'm': midi or drum name, 'v': velocity}
        self.placed: list = []  # (beat, sound)
        self.pos = 0.0
        self.section = -1
        self.chord_memory = None

    # --- where we are ------------------------------------------------------------------------------------------------
    def _here(self) -> float:
        if self.section != S.section_id:
            self.section = S.section_id
            self.pos = S.section_start
        return self.pos

    def _moved(self, beat: float) -> None:
        self.pos = beat
        S.end_beat = max(S.end_beat, beat)

    def rest(self, beats: float) -> 'Track':
        self._moved(self._here() + beats)
        return self

    def _add(self, beat, dur, what, vel) -> None:
        if isinstance(what, int):
            what += S.shift
        self.notes.append({'b': round(beat, 4), 'd': round(dur, 4), 'm': what, 'v': round(max(.05, min(1.0, vel)), 3)})

    def hit_note(self, kit, step: int) -> None:
        import compose as writer

        writer.track_hit_note(self, kit, step)

    def roll(self, name: str, beats=1.0, vel=(.3, 1.0), per_beat=8) -> 'Track':
        """A drum roll that swells: the run into a chorus."""
        start = self._here()
        count = int(beats * per_beat)
        for i in range(count):
            self._add(start + i / per_beat, .1, name, _ramp(vel, i / max(1, count - 1)))
        self._moved(start + beats)
        return self

    def euclid(self, name: str, hits: int, steps=16, bars=1, vel=.8, rotate=0) -> 'Track':
        """Spreads hits as evenly as they go: 3 in 8 is the tresillo, 5 in 8 the cinquillo. Much of the world's rhythm is this rule."""
        start = self._here()
        step = S.beats_per_bar / steps
        for b in range(bars):
            for k in range(steps):
                if ((k + rotate) * hits) % steps < hits:
                    self._add(start + b * S.beats_per_bar + k * step, .2, name, vel)
        self._moved(start + bars * S.beats_per_bar)
        return self

    def humanize(self, amount=.5) -> 'Track':
        self.human = amount
        return self

    def tremolo_note(self, note: str, beats=4.0, per_beat=6, vel=.6, octave=4) -> 'Track':
        """One note repeated fast: the guzheng's and mandolin's long note."""
        start = self._here()
        midi = self.notes_of(note, octave)[0]
        for i in range(int(beats * per_beat)):
            self._add(start + i / per_beat, 1 / per_beat, midi, vel * (.85 + .15 * (i % 2)))
        self._moved(start + beats)
        return self

    def grace(self, note: str, to: str, beats=1.0, vel=.7, octave=4) -> 'Track':
        """A very short note leaning into the next one."""
        start = self._here()
        self._add(start, .1, self.notes_of(note, octave)[0], vel * .7)
        self._add(start + .08, beats - .08, self.notes_of(to, octave)[0], vel)
        self._moved(start + beats)
        return self

    def glide(self, frm: str, to: str, beats=1.0, vel=.7, octave=4) -> 'Track':
        """From one note up or down through those between, quickly: a harp's or a zither's run."""
        start = self._here()
        a, b = self.notes_of(frm, octave)[0], self.notes_of(to, octave)[0]
        scale = {(S.tonic + i) % 12 for i in S.scale}
        way = [n for n in (range(a, b + 1) if b >= a else range(a, b - 1, -1)) if n % 12 in scale] or [a, b]
        for i, n in enumerate(way):
            self._add(start + i * beats * .6 / len(way), beats * .5, n, vel)
        self._moved(start + beats)
        return self

    # --- tunes -----------------------------------------------------------------------------------------------------------
    def _scale_note(self, token: str, octave: int) -> int:
        m = re.fullmatch(r"([#b]?)(\d+)([',]*)", token)
        if not m:
            raise SongError(f'这个音写错了：{token}（写成 1 b3 #4 5\' 5,）')
        degree = int(m.group(2)) - 1
        scale = S.scale
        count = len(scale)
        midi = S.tonic % 12 + 12 * (octave + 1) + scale[degree % count] + 12 * (degree // count)
        midi += m.group(1).count('#') - m.group(1).count('b')
        return midi + 12 * (m.group(3).count("'") - m.group(3).count(','))

    def notes_of(self, token: str, octave: int) -> list:
        if re.match(r'^[A-G]', token):
            return [pitch(token)]
        return [self._scale_note(token, octave)]

    def tune(self, text: str, octave=4, length=1.0, vel=.75, legato=.95) -> 'Track':
        """'1 2 3:.5 5:.5 | 6:2 5:2 | r:1 [1 3 5]:3' numbers by the scale, or names like D4; :n is beats, r a rest, [ ] sounds
        together. vel may be (from, to) for a swell over the whole call."""
        if self.instrument in ('drums', 'sounds'):
            raise SongError('tune 是给乐器用的；鼓用 beat，音效用 place')
        tokens = []
        for bar_no, bar in enumerate(text.split('|')):
            sum_beats = 0.0
            for raw in TOKEN_RE.findall(bar):
                body, _, beats = raw.partition(':') if not raw.startswith('[') else (raw[1:raw.index(']')], '', raw[raw.index(']') + 2:])
                beats = _number(beats) if beats else length
                tokens.append((body, beats, raw.startswith('[')))
                sum_beats += beats
            if '|' in text and sum_beats and abs(sum_beats - S.beats_per_bar) > 1e-6 and bar_no < text.count('|'):
                S.seen.append(f'{self.name} 的第 {bar_no + 1} 小节有 {sum_beats:g} 拍，不是 {S.beats_per_bar} 拍：{bar.strip()}')
        whole = sum(t[1] for t in tokens) or 1.0
        start = beat = self._here()
        for body, beats, together in tokens:
            v = _ramp(vel, (beat - start) / whole)
            if body != 'r':
                accent = 1.08 if abs((beat - S.section_start) % S.beats_per_bar) < 1e-6 else 1.0
                for t in (body.split() if together else [body]):
                    for midi in self.notes_of(t, octave):
                        self._add(beat, beats * legato, midi, v * accent)
            beat += beats
        self._moved(beat)
        return self

    # --- harmony ---------------------------------------------------------------------------------------------------------
    def _voiced(self, symbol: str, octave: int) -> list:
        """The chord's notes in the inversion nearest the last chord, so that the hands barely move: that is what makes a
        progression sound played and not stamped."""
        root, intervals, _ = chord_notes(symbol)
        base = [12 * (octave + 1) + (root + i) % 12 for i in intervals]
        if self.chord_memory is None:
            voiced = sorted(12 * (octave + 1) + root + i for i in intervals)
        else:
            centre = sum(self.chord_memory) / len(self.chord_memory)
            voiced = []
            for n in base:
                while n - centre > 6:
                    n -= 12
                while centre - n > 6:
                    n += 12
                voiced.append(n)
            voiced.sort()
        self.chord_memory = voiced
        return voiced

    def chords(self, text: str, style='hold', octave=4, vel=.6, every=1.0) -> 'Track':
        """'Dm | Bb | F C | Am': one bar each, two in a bar share it. style: hold, pulse (a hit every `every` beats), arp_up, arp_down,
        arp_wave, broken (bass then the rest), strum, or a rhythm like 'x..x..x.' with eight steps a bar."""
        for bar in text.split('|'):
            names = bar.split()
            if not names:
                continue
            beats = S.beats_per_bar / len(names)
            for symbol in names:
                self._chord(symbol, style, octave, beats, vel, every)
        return self

    def _chord(self, symbol, style, octave, beats, vel, every) -> None:
        start = self._here()
        if symbol == 'r':
            self._moved(start + beats)
            return
        notes = self._voiced(symbol, octave)
        v = _ramp(vel, 0)
        if style == 'hold':
            for n in notes:
                self._add(start, beats * .98, n, v)
        elif style == 'strum':
            for k, n in enumerate(notes):
                self._add(start + k * .035, beats * .95 - k * .035, n, v * (1 - .04 * k))
        elif style == 'pulse':
            t = 0.0
            while t < beats - 1e-6:
                for n in notes:
                    self._add(start + t, every * .8, n, v * (1.0 if t == 0 else .86))
                t += every
        elif style in ('arp_up', 'arp_down', 'arp_wave'):
            order = {'arp_up': notes + [notes[0] + 12], 'arp_down': [notes[0] + 12] + notes[::-1], 'arp_wave': notes + [notes[0] + 12] + notes[:0:-1]}[style]
            t = 0.0
            k = 0
            while t < beats - 1e-6:
                self._add(start + t, every * 1.5, order[k % len(order)], v * (1.0 if k % 4 == 0 else .82))
                t += every
                k += 1
        elif style == 'broken':
            self._add(start, beats * .95, notes[0] - 12, v)
            t = every
            k = 0
            upper = notes + [notes[0] + 12]
            while t < beats - 1e-6:
                self._add(start + t, every * 1.5, upper[k % len(upper)], v * .78)
                t += every
                k += 1
        elif set(style) <= {'x', '.'} and style:
            step = beats / len(style)
            for k, c in enumerate(style):
                if c == 'x':
                    for n in notes:
                        self._add(start + k * step, step * 1.4, n, v)
        else:
            raise SongError(f'没有这种和弦写法：{style}')
        self._moved(start + beats)

    def bass(self, text: str, style='root', octave=2, vel=.75) -> 'Track':
        """The same chord text as chords(). style: root, pulse (eighths), octave, walk (leading into the next chord), or eight steps 'x..x..x.'."""
        names = []
        for bar in text.split('|'):
            items = bar.split()
            if items:
                names += [(sym, S.beats_per_bar / len(items)) for sym in items]
        for k, (symbol, beats) in enumerate(names):
            start = self._here()
            if symbol == 'r':
                self._moved(start + beats)
                continue
            _, _, low = chord_notes(symbol)
            n = 12 * (octave + 1) + low
            if style == 'root':
                self._add(start, beats * .96, n, vel)
            elif style == 'pulse':
                for i in range(int(beats * 2)):
                    self._add(start + i * .5, .46, n, vel * (1 if i % 2 == 0 else .82))
            elif style == 'octave':
                for i in range(int(beats * 2)):
                    self._add(start + i * .5, .44, n + (12 if i % 2 else 0), vel * (1 if i % 2 == 0 else .8))
            elif style == 'walk':
                for i in range(int(beats)):
                    self._add(start + i, .9, n + (0, 7, 5, 7)[i % 4] - (12 if (0, 7, 5, 7)[i % 4] > 5 else 0), vel * (1 if i == 0 else .85))
                if k + 1 < len(names) and names[k + 1][0] != 'r':
                    target = 12 * (octave + 1) + chord_notes(names[k + 1][0])[2]
                    self.notes[-1]['m'] = target + (-1 if target > n else 1)  # a half step into the next root
            elif set(style) <= {'x', '.'} and style:
                step = beats / len(style)
                for i, c in enumerate(style):
                    if c == 'x':
                        self._add(start + i * step, step * 1.3, n, vel)
            else:
                raise SongError(f'没有这种低音写法：{style}')
            self._moved(start + beats)
        return self

    # --- drums -----------------------------------------------------------------------------------------------------------
    def beat(self, pattern='rock', bars=1, vel=.8, fill=False, **parts) -> 'Track':
        """A named pattern (rock four halftime trap ballad march war ritual waltz), or your own: beat(kick='x...x...', snare='....x...').
        Each string is one bar, x hit, X accent, o ghost, . nothing. fill=True breaks the last half bar into a tom run."""
        if self.instrument != 'drums':
            raise SongError("beat 是给 cs.track('drums') 用的")
        grid = parts or PATTERNS.get(pattern)
        if grid is None:
            raise SongError(f'没有 {pattern} 这种节奏。有：{", ".join(PATTERNS)}，或者自己写 beat(kick=\'x...\')')
        for name in grid:
            if name not in DRUMS:
                raise SongError(f'没有 {name} 这个鼓。有：{", ".join(sorted(DRUMS))}')
        start = self._here()
        bar_beats = S.beats_per_bar
        for b in range(bars):
            at = start + b * bar_beats
            last = fill and b == bars - 1
            for name, line in grid.items():
                step = bar_beats / len(line)
                for k, c in enumerate(line):
                    if c == '.' or (last and k * step >= bar_beats / 2):
                        continue
                    self._add(at + k * step + (_swing(k, step)), .25, name, vel * {'X': 1.15, 'x': 1.0, 'o': .5}.get(c, 1.0))
            if last:
                run = ('snare', 'snare', 'tom_high', 'tom_high', 'tom_mid', 'tom_mid', 'tom_low', 'tom_low')
                step = bar_beats / 2 / len(run)
                for k, name in enumerate(run):
                    self._add(at + bar_beats / 2 + k * step, .25, name, vel * (.8 + .03 * k))
        self._moved(start + bars * bar_beats)
        return self

    def hit(self, name: str, vel=.9) -> 'Track':
        """One drum here, and move on by nothing: a crash on the first beat of a section."""
        if name not in DRUMS:
            raise SongError(f'没有 {name} 这个鼓')
        self._add(self._here(), .25, name, vel)
        S.end_beat = max(S.end_beat, self.pos + 1)
        return self

    def place(self, sound: list, beat=None) -> 'Track':
        """A ready sound (cs.fx().thunder()) at a beat in a cs.track('sounds')."""
        self.placed.append((self._here() if beat is None else beat, sound))
        return self


def track(instrument: str, **options) -> Track:
    t = Track(instrument, **options)
    S.tracks.append(t)
    return t


def _number(text: str) -> float:
    try:
        if '/' in text:
            a, b = text.split('/')
            return float(a) / float(b)
        return float(text)
    except ValueError as e:
        raise SongError(f'拍数写错了：{text}') from e


def _ramp(vel, where: float) -> float:
    if isinstance(vel, (tuple, list)):
        return vel[0] + (vel[1] - vel[0]) * min(1.0, where)
    return vel


def _swing(k: int, step: float) -> float:
    return S.swing * step if k % 2 else 0.0


# --- turning the score into sound ----------------------------------------------------------------------------------------

def _mix_in(bus: list, at: int, sound: list, gain: float) -> None:
    if at < 0:
        sound, at = sound[-at:], 0
    end = min(len(bus), at + len(sound))
    if end <= at:
        return
    bus[at:end] = [x + y * gain for x, y in zip(bus[at:end], sound)]


def _delay(buf: list, sr: int, beats: float, feedback=.35, level=.3) -> list:
    d = max(1, int(S.beat_to_s(beats) * sr))
    out = buf[:]
    for i in range(d, len(out)):
        out[i] += (out[i - d]) * feedback
    return [a + (b - a) * level for a, b in zip(buf, out)]


def _sweep_filter(buf: list, sr: int, start: float, end: float) -> list:
    """A low-pass that moves over the whole track."""
    out = [0.0] * len(buf)
    low = band = 0.0
    n = len(buf) or 1
    f = 0.0
    for i, x in enumerate(buf):
        if i % 256 == 0:
            fc = start * (end / start) ** (i / n)
            f = min(1.1, 2 * math.sin(math.pi * min(fc, sr * .22) / sr))
        low += f * band
        band += f * (x - low - .9 * band)
        out[i] = low
    return out


def _duck_curve(kicks: list, n: int, sr: int, amount: float) -> list:
    """Quieter for a moment after each kick: the pump that keeps a bass and a kick from fighting."""
    curve = [1.0] * n
    length = int(.22 * sr)
    for t in kicks:
        p = int(t * sr)
        for i in range(p, min(n, p + length)):
            curve[i] = min(curve[i], 1 - amount * (1 - (i - p) / length) ** 2)
    return curve


def render(sr: int, progress=None) -> dict:
    """{'left', 'right', 'stems': {name: (left, right)}} of the whole song, finished and at a sensible loudness."""
    if not S.tracks:
        return {'left': [], 'right': [], 'stems': {}}
    seconds = S.beat_to_s(S.end_beat) + 3.5
    n = int(seconds * sr)
    left, right = [0.0] * n, [0.0] * n
    send_l, send_r = [0.0] * n, [0.0] * n
    rnd = random.Random(SETTINGS['seed'])
    cache: dict = {}
    stems = {}
    kicks = [S.beat_to_s(e['b']) for t in S.tracks if t.instrument == 'drums' for e in t.notes if e['m'] in ('kick', 'war_drum', 'taiko')]
    for index, t in enumerate(S.tracks):
        if progress:
            progress(f'{t.name} ({index + 1}/{len(S.tracks)})')
        bus = [0.0] * n
        louder = ROLE_LOUDNESS.get(t.instrument, 1.0)
        for e in t.notes:
            drum = t.instrument == 'drums'
            late = (rnd.random() - .5) * .012 * t.human if not drum else (rnd.random() - .5) * .004 * t.human
            vel = max(.05, min(1.0, e['v'] * (1 + (rnd.random() - .5) * .14 * t.human)))
            q_vel = round(vel * 8) / 8  # the same note at near the same strength is the same sound: that cache is what makes Python fast enough
            secs = S.beat_to_s(e['d'])
            q_dur = round(secs * 12) / 12 or 1 / 12
            key = (t.instrument, e['m'], q_vel, 0 if drum else q_dur)
            sound = cache.get(key)
            if sound is None:
                sound = DRUMS[e['m']](q_vel, sr) if drum else INSTRUMENTS[t.instrument](freq_of(e['m']), q_dur, q_vel, sr)
                cache[key] = sound
            gain = (vel ** 1.3) * (1.0 if drum else louder * .34)
            _mix_in(bus, int((S.beat_to_s(e['b']) + max(late, -.004) + (.004 if not drum else 0)) * sr), sound, gain)
        for beat, sound in t.placed:
            _mix_in(bus, int(S.beat_to_s(beat) * sr), sound, 1.0)
        if t.low_cut:
            bus = synth.biquad(bus, 'high', t.low_cut, sr)
        if t.high_cut:
            bus = synth.biquad(bus, 'low', t.high_cut, sr)
        if t.delay:
            bus = _delay(bus, sr, .75, level=t.delay)
        if t.sweep:  # a filter opening over the song: (from Hz, to Hz)
            bus = _sweep_filter(bus, sr, *t.sweep)
        if t.drive:
            amount = 1 + t.drive * 8
            bus = [math.tanh(v * amount) / math.tanh(amount) * .7 for v in bus]
        if t.crush:
            keep = max(2, int(2 + (1 - t.crush) * 6))
            bits = 2 ** keep
            hold, value = max(1, int(t.crush * 12)), 0.0
            for i in range(len(bus)):
                if i % hold == 0:
                    value = round(bus[i] * bits) / bits
                bus[i] = value
        if t.chorus:
            lag = int(.018 * sr)
            w = math.tau * .6 / sr
            copy = bus[:]
            for i in range(lag * 2, n):
                bus[i] += copy[i - lag - int(lag * .6 * math.sin(w * i))] * t.chorus
        if t.tremolo:
            w = math.tau * (S.tempo / 60 * 2) / sr
            bus = [v * (1 - t.tremolo * (.5 + .5 * math.sin(w * i))) for i, v in enumerate(bus)]
        if t.duck and kicks:
            curve = _duck_curve(kicks, n, sr, t.duck)
            bus = [a * b for a, b in zip(bus, curve)]
        angle = (t.pan + 1) * math.pi / 4
        gain_l, gain_r = math.cos(angle) * t.vol * 1.41, math.sin(angle) * t.vol * 1.41
        lag = int(.012 * sr)
        if t.wide:  # the same thing a moment later on the other side: it stops sounding like one point in space
            l_part = [x * gain_l for x in bus]
            r_part = [x * gain_r * (1 - t.wide) + y * gain_r * t.wide for x, y in zip(bus, [0.0] * lag + bus[:-lag])]
        else:
            l_part = [x * gain_l for x in bus]
            r_part = [x * gain_r for x in bus]
        if SETTINGS['stems']:
            stems[t.name] = (l_part, r_part)
        left = [a + b for a, b in zip(left, l_part)]
        right = [a + b for a, b in zip(right, r_part)]
        if t.reverb:
            send_l = [a + b * t.reverb for a, b in zip(send_l, l_part)]
            send_r = [a + b * t.reverb for a, b in zip(send_r, r_part)]
    if progress:
        progress('混响')
    if any(send_l):
        wet_l, wet_r = synth.reverb(send_l, send_r, sr, S.reverb_size)
        for i in range(min(n, len(wet_l))):
            left[i] += wet_l[i]
            right[i] += wet_r[i]
    if progress:
        progress('母带')
    mastered = _master(left, right)
    end = _end_of(mastered['left'], mastered['right'], sr)
    l_out, r_out = mastered['left'], mastered['right']
    if S.loop:  # what rings on past the end falls over the start, so that a game's music has no seam
        end = int(S.beat_to_s(S.end_beat) * sr)
        tail_l, tail_r = l_out[end:], r_out[end:]
        l_out, r_out = l_out[:end], r_out[:end]
        for i in range(min(len(tail_l), end)):
            l_out[i] += tail_l[i]
            r_out[i] += tail_r[i]
    else:
        l_out, r_out = l_out[:end], r_out[:end]
    total = len(l_out)
    for start, seconds, up in ((0, S.fade_in, True), (total, S.fade_out, False)):
        count = min(total, int(seconds * sr))
        for i in range(count):
            g = (i / count) if up else i / count
            at = i if up else total - 1 - i
            l_out[at] *= g
            r_out[at] *= g
    return {'stems': {k: (a[:total], b[:total]) for k, (a, b) in stems.items()}, 'left': l_out, 'right': r_out}


def _end_of(left: list, right: list, sr: int) -> int:
    """Where the sound has really died away: three spare seconds of silence are no part of a song."""
    n = len(left)
    while n > 0 and abs(left[n - 1]) < .0006 and abs(right[n - 1]) < .0006:
        n -= 1
    return min(len(left), n + sr // 4)


LEVELS = {'轻柔': -20.0, '标准': -16.0, '响亮': -13.0}
CEILING = .93


def _master(left: list, right: list) -> dict:
    """A clean level: quiet songs up, loud ones down, and the few highest peaks rounded rather than clipped."""
    energy = sum(a * a + b * b for a, b in zip(left, right)) / max(1, 2 * len(left))
    rms = math.sqrt(energy)
    gain = 10 ** (S.level / 20) / rms if rms > 1e-9 else 1.0
    knee = .7
    room = CEILING - knee

    def soft(x: float) -> float:
        a = abs(x)
        if a <= knee:
            return x
        return math.copysign(knee + room * math.tanh((a - knee) / room), x)

    return {'left': [soft(x * gain) for x in left], 'right': [soft(x * gain) for x in right]}


def score() -> dict:
    """What was written, for the window and for the checks."""
    return {'title': S.title, 'tempo': S.tempo, 'key': S.key_name, 'beats_per_bar': S.beats_per_bar, 'end_beat': S.end_beat, 'seconds': round(S.beat_to_s(S.end_beat), 2),
            'sections': S.sections, 'written_notes': S.seen, 'scale': [(S.tonic + i) % 12 for i in S.scale],
            'tracks': [{'name': t.name, 'instrument': t.instrument, 'vol': t.vol, 'pan': t.pan, 'notes': t.notes} for t in S.tracks],
            'saved': [name for name, _ in S.saved]}
