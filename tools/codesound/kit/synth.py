"""The sounds themselves: every instrument, drum and effect is computed here, sample by sample, from nothing.

No samples, no libraries. Everything returns a plain list of floats (mono, about -1..1). Python is slow per sample, so the
methods are the cheap ones that sound good: a damped resonator for each partial of a struck thing, Karplus-Strong for
plucked strings, band-limited saws through a state-variable filter for bowed and blown things.
"""
from __future__ import annotations

import math
import random

TAU = math.tau


def _seed(*parts) -> random.Random:
    return random.Random(repr(parts))


def apply_env(buf: list, sr: int, attack: float, release: float) -> list:
    """Soft start and end, so that no note clicks."""
    n = len(buf)
    a = min(n, max(1, int(attack * sr)))
    for i in range(a):
        buf[i] *= i / a
    r = min(n, max(1, int(release * sr)))
    for i in range(r):
        buf[n - 1 - i] *= i / r
    return buf


# --- struck and rung things: each partial is a damped resonator, which costs two multiplications a sample --------------

def _partial(out: list, freq: float, amp: float, decay: float, sr: int) -> None:
    """Adds amp * exp(-decay t) * sin(2 pi freq t) to out."""
    if freq <= 0 or freq >= sr * .46 or amp < 1e-5:
        return
    w = TAU * freq / sr
    g = math.exp(-decay / sr)
    a1, a2 = 2 * g * math.cos(w), -g * g
    y2, y1 = 0.0, amp * g * math.sin(w)
    if len(out) > 1:
        out[1] += y1
    for i in range(2, len(out)):
        y = a1 * y1 + a2 * y2
        out[i] += y
        y2, y1 = y1, y


def _struck(freq, dur, vel, sr, partials, release=.12, attack=.002, stretch=0.0) -> list:
    """partials: (ratio, amplitude, decay per second). stretch: stiff strings run sharp as they go up."""
    out = [0.0] * int((dur + release) * sr)
    for ratio, amp, decay in partials:
        real = ratio * math.sqrt(1 + stretch * ratio * ratio)
        bright = vel ** (.35 * math.log2(ratio + 1))  # hit softly, the top is what goes first
        _partial(out, freq * real, amp * bright, decay, sr)
    return apply_env(out, sr, attack, release)


def piano(freq, dur, vel, sr):
    top = min(12, max(4, int(sr * .45 / freq)))
    low = (freq / 220) ** .45
    partials = []
    for k in range(1, top + 1):
        amp = (1.0 if k == 1 else .78 if k == 2 else .5 / (k - 1) ** .9)
        decay = (.75 + .42 * k) * low
        partials.append((k, amp * .62, decay))
        if k <= 5:  # a note has two or three strings, never quite in tune: that slow beating is what makes it a piano
            partials.append((k * (1 + .00042), amp * .34, decay * 1.5))
    out = _struck(freq, max(dur, .25), vel, sr, partials, release=.16, stretch=.00022)
    rnd = _seed('hammer', round(freq, 1))
    hit = int(.012 * sr)  # the felt on the string, a very short thump
    prev = 0.0
    for i in range(min(hit, len(out))):
        prev += (.5) * ((rnd.random() * 2 - 1) - prev)
        out[i] += prev * .1 * vel * (1 - i / hit)
    return out


def electric_piano(freq, dur, vel, sr):
    return _struck(freq, max(dur, .3), vel, sr, [(1, 1, 1.4), (2, .25, 3), (4, .3 * vel, 9), (14, .12 * vel, 26)], release=.14)


def bell(freq, dur, vel, sr):
    """Bell ratios are not whole numbers; that is why it sounds like metal."""
    return _struck(freq, max(dur, 1.4), vel, sr, [(.5, .5, .55), (1, 1, .8), (1.19, .55, 1.0), (1.56, .38, 1.5), (2.0, .55, 1.7), (2.67, .3, 2.6),
                                                 (3.0, .22, 3.2), (4.07, .16, 5), (5.4, .1, 7)], release=.3)


def bronze_bell(freq, dur, vel, sr):
    """An old tuned temple bell: dark, long, with a slow beat between its two tones."""
    return _struck(freq, max(dur, 2.2), vel, sr, [(1, 1, .5), (1.004, .6, .55), (1.21, .4, .9), (2.0, .45, 1.2), (2.42, .3, 1.9), (3.01, .24, 2.8),
                                                 (4.3, .12, 5.5)], release=.5)


def celesta(freq, dur, vel, sr):
    return _struck(freq, max(dur, .5), vel, sr, [(1, 1, 2.5), (4, .3, 7), (10, .06, 20)], release=.2)


def marimba(freq, dur, vel, sr):
    return _struck(freq, max(dur, .2), vel, sr, [(1, 1, 7), (3.93, .35 * vel, 20), (9.2, .08 * vel, 45)], release=.05)


def glock(freq, dur, vel, sr):
    return _struck(freq, max(dur, .5), vel, sr, [(1, 1, 2), (2.76, .4, 5), (5.4, .2, 11)], release=.15)


# --- plucked strings: Karplus-Strong ---------------------------------------------------------------------------------

def _pluck(freq, dur, vel, sr, tone=.5, stretch_decay=.996, pick=.13, seed='') -> list:
    period = sr / freq
    size = int(period - .5)
    frac = period - .5 - size
    if size < 2:
        return [0.0] * int(dur * sr)
    rnd = _seed(seed, round(freq, 1))
    line = [0.0] * size
    prev = 0.0
    smooth = .25 + .7 * tone * vel
    for i in range(size):  # the shape of the pluck: dull for a finger, bright for a pick
        prev += smooth * ((rnd.random() * 2 - 1) - prev)
        line[i] = prev
    spot = max(1, int(size * pick))  # plucked away from the end, some harmonics are not there at all
    burst = [line[i] - line[i - spot] for i in range(size)]
    n = int((dur + .25) * sr)
    out = [0.0] * n
    damped_at = int(dur * sr)
    held = stretch_decay ** (440 / max(freq, 40) * .22)  # low strings ring longer
    damped = .94
    last = 0.0
    a, b = 1 - frac, frac
    i, pos = 0, 0
    for i in range(n):
        y = burst[pos]
        nxt = burst[pos + 1 if pos + 1 < size else 0]
        v = a * y + b * nxt
        new = .5 * (v + last)
        last = v
        out[i] = y
        burst[pos] = new * (held if i < damped_at else damped)
        pos = pos + 1 if pos + 1 < size else 0
    return apply_env(out, sr, .001, .06)


def guitar(freq, dur, vel, sr):
    return _pluck(freq, dur, vel, sr, tone=.55, pick=.14, seed='guitar')


def steel_guitar(freq, dur, vel, sr):
    return _pluck(freq, dur, vel, sr, tone=.9, pick=.09, seed='steel', stretch_decay=.9972)


def harp(freq, dur, vel, sr):
    return _pluck(freq, max(dur, .8), vel, sr, tone=.42, pick=.33, seed='harp', stretch_decay=.9972)


def bass_guitar(freq, dur, vel, sr):
    return _pluck(freq, dur, vel, sr, tone=.3, pick=.2, seed='bass', stretch_decay=.9978)


def guzheng(freq, dur, vel, sr):
    """A long zither: a clear pluck, and the left hand bends the string down and back."""
    base = _pluck(freq, max(dur, .9), vel, sr, tone=.8, pick=.11, seed='zheng', stretch_decay=.9974)
    return _vibrate(base, sr, rate=5.2, depth=.0016, delay=.28)


def pipa(freq, dur, vel, sr):
    return _pluck(freq, dur, vel, sr, tone=.95, pick=.08, seed='pipa', stretch_decay=.993)


def _vibrate(buf, sr, rate, depth, delay):
    """Pitch moved by reading the note at a wobbling speed, starting after delay."""
    n = len(buf)
    out = [0.0] * n
    w = TAU * rate / sr
    start = int(delay * sr)
    size = depth * sr / (TAU * rate) * TAU * .5
    for i in range(n):
        grow = min(1.0, max(0.0, (i - start) / (.3 * sr)))
        p = i - size * grow * (1 - math.cos(w * i))
        k = int(p)
        if 0 <= k < n - 1:
            f = p - k
            out[i] = buf[k] * (1 - f) + buf[k + 1] * f
    return out


# --- bowed, blown, sung: band-limited oscillators through a filter -----------------------------------------------------

def _sub(freq, dur, vel, sr, detune=(0.0,), cutoff=2000.0, env_amt=0.0, env_time=.3, res=.2, attack=.01, decay=.1, sustain=1.0, release=.15,
         vib_rate=0.0, vib_depth=0.0, vib_delay=.2, square=0.0, noise=0.0, seed='') -> list:
    """Saws (and a part of square) -> a low-pass that opens with vel and closes after the attack."""
    n = int((dur + release) * sr)
    out = [0.0] * n
    rnd = _seed(seed, round(freq, 1), round(vel, 2))
    voices = [(freq * 2 ** (c / 1200), rnd.random()) for c in detune]
    steps = [v[0] / sr for v in voices]
    phases = [v[1] for v in voices]
    count = len(voices)
    share = 1 / count ** .5
    low = band = 0.0
    q = 1.9 - 1.75 * min(res, .97)  # 0.15..1.9 damping of the state-variable filter
    f_top = .95 * (math.sqrt(q * q + 4) - q)  # this filter blows up above f*f + 2*f*q = 4, which a low sample rate reaches easily
    sus_at = int(dur * sr)
    att = max(1, int(attack * sr))
    dec = max(1, int(decay * sr))
    rel = max(1, n - sus_at)
    vib_w = TAU * vib_rate / sr
    vib_start = int(vib_delay * sr)
    vib_grow = max(1, int(.35 * sr))
    env_rate = 1 / max(1, env_time * sr)
    top = sr * .24
    for i in range(n):
        if i < att:
            amp = i / att
        elif i < att + dec:
            amp = 1 - (1 - sustain) * (i - att) / dec
        else:
            amp = sustain
        if i >= sus_at:
            amp *= 1 - (i - sus_at) / rel
        wobble = 1.0
        if vib_depth and i > vib_start:
            wobble += vib_depth * min(1.0, (i - vib_start) / vib_grow) * math.sin(vib_w * i)
        s = 0.0
        for v in range(count):
            step = steps[v] * wobble
            p = phases[v] + step
            if p >= 1.0:
                p -= 1.0
            phases[v] = p
            x = 2 * p - 1  # a saw, with polyBLEP at the jump so that the top of it does not fold back and sound like a fax
            if p < step:
                t = p / step
                x -= t + t - t * t - 1
            elif p > 1 - step:
                t = (p - 1) / step
                x -= t * t + t + t + 1
            if square:
                x = x * (1 - square) + square * (1 if p < .5 else -1)
            s += x
        s *= share
        if noise:
            s += noise * (rnd.random() * 2 - 1) * (.5 + .5 * amp)
        fc = cutoff * (1 + env_amt * max(0.0, 1 - i * env_rate))
        if fc > top:
            fc = top
        f = 2 * math.sin(math.pi * fc / sr)
        if f > f_top:
            f = f_top
        low += f * band
        high = s - low - q * band
        band += f * high
        out[i] = low * amp
    return out


def strings(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-7, 0, 6), cutoff=900 + 3200 * vel, env_amt=.4, env_time=.5, attack=.1 + .12 * (1 - vel), decay=.3, sustain=.9, release=.3,
                vib_rate=5.2, vib_depth=.0028, vib_delay=.35, seed='strings')


def staccato_strings(freq, dur, vel, sr):
    return _sub(freq, min(dur, .3), vel, sr, detune=(-6, 0, 5), cutoff=1200 + 3600 * vel, env_amt=.8, env_time=.08, attack=.006, decay=.1, sustain=.6, release=.09, seed='spic')


def cello(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-3, 3), cutoff=500 + 2100 * vel, env_amt=.5, env_time=.4, attack=.08, decay=.3, sustain=.92, release=.26,
                vib_rate=4.8, vib_depth=.0034, vib_delay=.4, seed='cello')


def erhu(freq, dur, vel, sr):
    """A two-string fiddle: one thin voice, wide vibrato, a nasal middle."""
    base = _sub(freq, dur, vel, sr, detune=(0,), cutoff=2400 + 2600 * vel, res=.35, attack=.05, decay=.2, sustain=.94, release=.14,
                vib_rate=5.8, vib_depth=.0075, vib_delay=.15, seed='erhu')
    return biquad(biquad(base, 'peak', 1250, sr, q=1.6, gain=7), 'high', 380, sr)


def brass(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-4, 4), cutoff=500 + 1800 * vel, env_amt=2.2 * vel, env_time=.13, res=.25, attack=.03, decay=.2, sustain=.85, release=.13,
                vib_rate=5, vib_depth=.0016, vib_delay=.5, seed='brass')


def horn(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-3, 3), cutoff=380 + 900 * vel, env_amt=1.2, env_time=.2, attack=.06, decay=.3, sustain=.9, release=.2, seed='horn')


def flute(freq, dur, vel, sr):
    n = int((dur + .1) * sr)
    out = [0.0] * n
    rnd = _seed('flute', round(freq, 1))
    w = TAU * freq / sr
    vib = TAU * 5.1 / sr
    att = max(1, int(.05 * sr))
    rel = int(dur * sr)
    breath = 0.0
    phase = 0.0
    second = .22 + .3 * vel
    for i in range(n):
        wob = 1 + .0026 * math.sin(vib * i) * min(1.0, i / (.4 * sr))
        phase += w * wob
        amp = min(1.0, i / att) * (1 if i < rel else max(0.0, 1 - (i - rel) / (.1 * sr)))
        breath += .22 * ((rnd.random() * 2 - 1) - breath)
        out[i] = amp * (math.sin(phase) + second * math.sin(2 * phase) + .09 * math.sin(3 * phase) + breath * .09)
    return out


def bamboo_flute(freq, dur, vel, sr):
    """Like the flute, with a buzzing membrane that adds an edge. Slides in from below."""
    base = flute(freq, dur, min(1.0, vel + .25), sr)
    buzz = biquad(base, 'peak', 2600, sr, q=1.2, gain=9)
    return _vibrate(buzz, sr, rate=5.8, depth=.0034, delay=.12)


def clarinet(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(0,), cutoff=1100 + 1500 * vel, square=.88, attack=.03, decay=.1, sustain=.92, release=.08, seed='clarinet')


def choir(freq, dur, vel, sr):
    """Voices on 'ah': three vocal-tract resonances over slightly different saws."""
    base = _sub(freq, dur, vel, sr, detune=(-9, -3, 4, 10), cutoff=5200, attack=.26, decay=.3, sustain=.9, release=.36, vib_rate=4.9, vib_depth=.002, vib_delay=.4, noise=.03, seed='choir')
    a = biquad(base, 'band', 730, sr, q=5)
    b = biquad(base, 'band', 1090, sr, q=6)
    c = biquad(base, 'band', 2440, sr, q=7)
    return [x + .66 * y + .32 * z for x, y, z in zip(a, b, c)]


def pad(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-11, -4, 5, 12), cutoff=420 + 800 * vel, env_amt=.8, env_time=1.2, res=.2, attack=.6, decay=.8, sustain=.9, release=.8, seed='pad')


def warm_pad(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-6, 6), cutoff=300 + 500 * vel, attack=.9, decay=.5, sustain=1, release=1.1, square=.2, seed='warm')


def organ(freq, dur, vel, sr):
    n = int((dur + .06) * sr)
    out = [0.0] * n
    for ratio, amp in ((1, 1), (2, .55), (3, .3), (4, .24), (6, .12), (8, .1)):
        _partial(out, freq * ratio, amp, .05, sr)
    return apply_env(out, sr, .012, .06)


def lead(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-5, 5), cutoff=1100 + 2600 * vel, env_amt=1.1, env_time=.16, res=.45, attack=.006, decay=.16, sustain=.78, release=.12,
                vib_rate=5.5, vib_depth=.0028, vib_delay=.3, square=.3, seed='lead')


def pluck_synth(freq, dur, vel, sr):
    return _sub(freq, min(dur, .4), vel, sr, detune=(-6, 6), cutoff=500 + 800 * vel, env_amt=6 * vel, env_time=.09, res=.4, attack=.002, decay=.2, sustain=.15, release=.18, seed='plucksyn')


def synth_bass(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-3, 3), cutoff=240 + 480 * vel, env_amt=2.2, env_time=.13, res=.4, attack=.004, decay=.2, sustain=.72, release=.06, square=.4, seed='sbass')


def sub_bass(freq, dur, vel, sr):
    n = int((dur + .06) * sr)
    out = [0.0] * n
    _partial(out, freq, 1, .1, sr)
    _partial(out, freq * 2, .22 * vel, 1.2, sr)
    return apply_env(out, sr, .006, .05)


def double_bass(freq, dur, vel, sr):
    return _pluck(freq, dur, vel, sr, tone=.22, pick=.22, seed='upright', stretch_decay=.996)


# --- drums --------------------------------------------------------------------------------------------------------------

def _noise(n, seed, a=1.0) -> list:
    rnd = _seed('noise', seed, n)
    r = rnd.random
    return [a * (r() * 2 - 1) for _ in range(n)]


def _sweep(sr, length, start, end, drop, amp_decay, click=0.0) -> list:
    """A sine whose pitch falls from start to end: a kick or a tom."""
    n = int(length * sr)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / sr
        phase += TAU * (end + (start - end) * math.exp(-t * drop)) / sr
        out[i] = math.sin(phase) * math.exp(-t * amp_decay)
    for i in range(min(n, int(.003 * sr))):
        out[i] += click * (1 - i / (.003 * sr)) * (1 if i % 2 else -1)
    return out


def _mix(*layers):
    n = max(len(a) for a, _ in layers)
    out = [0.0] * n
    for buf, amp in layers:
        for i, v in enumerate(buf):
            out[i] += v * amp
    return out


def _shaped(n, sr, decay):
    return [math.exp(-i / sr * decay) for i in range(n)]


def _noise_hit(sr, length, decay, seed, kind='high', freq=6000.0, q=.8) -> list:
    n = int(length * sr)
    buf = biquad(_noise(n, seed), kind, freq, sr, q=q)
    return [x * e for x, e in zip(buf, _shaped(n, sr, decay))]


def kick(vel, sr):
    return _sweep(sr, .36, 170, 46, 34, 9 - 2 * vel, click=.4 * vel)


def snare(vel, sr):
    tone = _sweep(sr, .2, 310, 180, 40, 22)
    return apply_env(_mix((tone, .55), (_noise_hit(sr, .26, 18, 'snare', 'high', 1400, .7), .75 * (.5 + .5 * vel))), sr, .0005, .02)


def clap(vel, sr):
    n = int(.24 * sr)
    noise = biquad(_noise(n, 'clap'), 'band', 1500, sr, q=1.4)
    out = [0.0] * n
    for k in range(n):
        t = k / sr
        env = math.exp(-t * 34)
        for start in (0.0, .011, .023):  # hands never meet in one instant
            if t >= start:
                env = max(env, math.exp(-(t - start) * 170))
        out[k] = noise[k] * env
    return out


def hat(vel, sr):
    return _noise_hit(sr, .09, 58, 'hat', 'high', 7800, .9)


def open_hat(vel, sr):
    return _noise_hit(sr, .42, 7.5, 'ohat', 'high', 7200, .9)


def shaker(vel, sr):
    n = int(.07 * sr)
    buf = biquad(_noise(n, 'shaker'), 'high', 5200, sr)
    return apply_env(buf, sr, .014, .04)


def rim(vel, sr):
    return _struck(1700, .05, vel, sr, [(1, 1, 80), (2.4, .4, 110)], release=.01, attack=.0005)


def tom_low(vel, sr):
    return _sweep(sr, .5, 150, 82, 16, 7, click=.14)


def tom_mid(vel, sr):
    return _sweep(sr, .42, 210, 120, 18, 9, click=.14)


def tom_high(vel, sr):
    return _sweep(sr, .36, 280, 170, 20, 11, click=.14)


def crash(vel, sr):
    return _mix((_noise_hit(sr, 1.9, 2.1, 'crash', 'high', 4000, .7), .7), (_noise_hit(sr, .3, 16, 'crash2', 'band', 900, .8), .3))


def ride(vel, sr):
    return _mix((_noise_hit(sr, .8, 5, 'ride', 'high', 6000, 1), .28), (_struck(5200, .6, vel, sr, [(1, .5, 7), (1.41, .3, 9)], release=.1, attack=.0005), .5))


def taiko(vel, sr):
    """A big barrel drum: a deep body, a slap of skin and the room shaking after."""
    return _mix((_sweep(sr, 1.2, 150, 58, 12, 3.8, click=.2), 1), (_noise_hit(sr, .14, 28, 'taiko', 'low', 900), .55))


def war_drum(vel, sr):
    return _mix((_sweep(sr, 1.6, 110, 44, 9, 2.6, click=.25), 1), (_noise_hit(sr, .22, 18, 'war', 'low', 520), .6))


def timpani(vel, sr):
    return _mix((_struck(98, .9, vel, sr, [(1, 1, 3.4), (1.5, .5, 5), (1.98, .3, 6.5), (2.44, .16, 8)], release=.2, attack=.002), 1), (_noise_hit(sr, .05, 70, 'timp', 'low', 800), .3))


def gong(vel, sr):
    out = _struck(92, 3.4, vel, sr, [(1, .8, .75), (1.46, .5, 1), (2.02, .6, 1.3), (2.76, .42, 1.3), (3.33, .4, 1.6), (4.1, .3, 2), (5.33, .22, 2.3), (6.9, .16, 2.8)],
                  release=.4, attack=.02)
    return _mix((out, 1), (_noise_hit(sr, 2.4, 2.4, 'gong', 'band', 3200, .9), .12))


def wood_block(vel, sr):
    return _struck(920, .07, vel, sr, [(1, 1, 55), (2.3, .3, 80)], release=.01, attack=.0005)


# --- more instruments and drums (2026-11-07) -----------------------------------------------------------------------------

def vibraphone(freq, dur, vel, sr):
    base = _struck(freq, max(dur, 1.0), vel, sr, [(1, 1, 1.1), (4, .28, 4), (10, .05, 10)], release=.3)
    w = TAU * 5.2 / sr
    return [v * (1 - .22 * (1 + math.sin(w * i)) / 2) for i, v in enumerate(base)]


def xylophone(freq, dur, vel, sr):
    return _struck(freq, max(dur, .15), vel, sr, [(1, 1, 16), (3, .5, 26), (6.2, .18, 50)], release=.03)


def kalimba(freq, dur, vel, sr):
    return _struck(freq, max(dur, .5), vel, sr, [(1, 1, 3.4), (5.4, .28, 18), (2.0, .12, 7)], release=.12)


def music_box(freq, dur, vel, sr):
    return _struck(freq * 2, max(dur, .8), vel, sr, [(1, 1, 3), (2.76, .5, 7), (5.4, .3, 12), (8.9, .12, 20)], release=.2)


def steel_drum(freq, dur, vel, sr):
    return _struck(freq, max(dur, .35), vel, sr, [(1, 1, 4), (2, .7, 5), (3, .3, 9), (.5, .15, 3)], release=.1)


def yangqin(freq, dur, vel, sr):
    """A struck zither: two strings a hair apart, a quick decay, and the hammer's tick."""
    return _struck(freq, max(dur, .4), vel, sr, [(1, 1, 3.4), (1.003, .7, 3.6), (2, .5, 6), (3, .3, 9), (4, .15, 12)], release=.1, attack=.0008)


def ukulele(freq, dur, vel, sr):
    return _pluck(freq, dur, vel, sr, tone=.6, pick=.2, seed='uke', stretch_decay=.988)


def mandolin(freq, dur, vel, sr):
    a = _pluck(freq, dur, vel, sr, tone=.9, pick=.1, seed='man1', stretch_decay=.992)
    b = _pluck(freq * 1.002, dur, vel, sr, tone=.9, pick=.1, seed='man2', stretch_decay=.992)
    return [x + y for x, y in zip(a, b)]


def koto(freq, dur, vel, sr):
    return _vibrate(_pluck(freq, max(dur, .7), vel, sr, tone=.72, pick=.16, seed='koto', stretch_decay=.9965), sr, rate=4.6, depth=.0022, delay=.2)


def violin(freq, dur, vel, sr):
    base = _sub(freq, dur, vel, sr, detune=(0,), cutoff=1500 + 3000 * vel, res=.3, attack=.05, decay=.2, sustain=.92, release=.16, vib_rate=5.6, vib_depth=.0048, vib_delay=.22, seed='violin')
    return biquad(biquad(base, 'peak', 2800, sr, q=1.2, gain=5), 'high', 300, sr)


def viola(freq, dur, vel, sr):
    return biquad(_sub(freq, dur, vel, sr, detune=(0,), cutoff=1000 + 2000 * vel, res=.3, attack=.06, decay=.2, sustain=.92, release=.18, vib_rate=5.2, vib_depth=.004, vib_delay=.25, seed='viola'), 'peak', 1200, sr, q=1, gain=4)


def trumpet(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(0,), cutoff=800 + 2600 * vel, env_amt=1.6, env_time=.08, res=.3, attack=.02, decay=.12, sustain=.85, release=.08, vib_rate=5.2, vib_depth=.0018, vib_delay=.4, square=.15, seed='trumpet')


def trombone(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(0,), cutoff=420 + 1500 * vel, env_amt=1.2, env_time=.14, attack=.05, decay=.15, sustain=.88, release=.12, seed='trombone')


def oboe(freq, dur, vel, sr):
    return biquad(_sub(freq, dur, vel, sr, detune=(0,), cutoff=2600, square=.45, attack=.04, decay=.1, sustain=.9, release=.08, vib_rate=5, vib_depth=.002, vib_delay=.3, seed='oboe'), 'peak', 1400, sr, q=2, gain=8)


def accordion(freq, dur, vel, sr):
    return biquad(_sub(freq, dur, vel, sr, detune=(-6, 0, 7), cutoff=2400, square=.7, attack=.04, decay=.1, sustain=.95, release=.08, seed='accordion'), 'peak', 900, sr, q=1, gain=4)


def suona(freq, dur, vel, sr):
    """A loud double-reed horn: bright, buzzing, always a little sharp at the front of a note."""
    base = _sub(freq, dur, vel, sr, detune=(0,), cutoff=4200, square=.55, res=.35, attack=.02, decay=.1, sustain=.95, release=.07, vib_rate=6.2, vib_depth=.006, vib_delay=.1, seed='suona')
    return [math.tanh(x * 2.2) * .6 for x in biquad(base, 'peak', 1800, sr, q=1.4, gain=9)]


def sheng(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-2, 2, 1199, 1202), cutoff=2100, square=.3, attack=.05, decay=.1, sustain=.95, release=.1, seed='sheng')


def supersaw(freq, dur, vel, sr):
    return _sub(freq, dur, vel, sr, detune=(-18, -9, -3, 3, 9, 18), cutoff=1200 + 3600 * vel, env_amt=.7, env_time=.3, attack=.01, decay=.3, sustain=.8, release=.3, seed='super')


def acid_bass(freq, dur, vel, sr):
    return _sub(freq, min(dur, .4), vel, sr, detune=(0,), cutoff=200, env_amt=11 * vel, env_time=.14, res=.85, attack=.002, decay=.12, sustain=.5, release=.05, seed='acid')


def chip_square(freq, dur, vel, sr):
    """An old game console: a square wave with no filter at all."""
    n = int((dur + .03) * sr)
    period = sr / freq
    out = [.34 if (i % period) < period / 2 else -.34 for i in range(n)]
    return apply_env(out, sr, .001, .02)


def chip_pulse(freq, dur, vel, sr):
    n = int((dur + .03) * sr)
    period = sr / freq
    out = [.3 if (i % period) < period / 4 else -.3 for i in range(n)]
    return apply_env(out, sr, .001, .02)


def chip_triangle(freq, dur, vel, sr):
    n = int((dur + .03) * sr)
    period = sr / freq
    out = [.6 * (1 - 4 * abs((i % period) / period - .5)) for i in range(n)]
    return apply_env(out, sr, .001, .02)


def glass_pad(freq, dur, vel, sr):
    base = _sub(freq, dur, vel, sr, detune=(-5, 5, 1200), cutoff=2600, attack=.5, decay=.6, sustain=.8, release=.9, seed='glass')
    return biquad(base, 'high', 500, sr)


def kick_808(vel, sr):
    return _sweep(sr, .9, 120, 42, 22, 3.6, click=.2)


def brush(vel, sr):
    return _noise_hit(sr, .24, 16, 'brush', 'band', 3000, .6)


def cowbell(vel, sr):
    return _struck(560, .16, vel, sr, [(1, 1, 18), (1.48, .8, 20)], release=.03, attack=.0005)


def tambourine(vel, sr):
    return _mix((_noise_hit(sr, .18, 22, 'tamb', 'high', 6500, .8), .9), (_struck(5200, .1, vel, sr, [(1, .3, 30), (1.3, .2, 34)], release=.02), .4))


def conga(vel, sr):
    return _sweep(sr, .28, 300, 190, 30, 14, click=.1)


def bongo(vel, sr):
    return _sweep(sr, .18, 470, 330, 40, 22, click=.1)


def triangle_hit(vel, sr):
    return _struck(4200, .7, vel, sr, [(1, 1, 5), (2.76, .5, 7), (5.4, .2, 9)], release=.1, attack=.0005)


def finger_snap(vel, sr):
    return _noise_hit(sr, .06, 110, 'snap', 'band', 2800, 1.2)


def cymbal_small(vel, sr):
    return _noise_hit(sr, .8, 6, 'small', 'high', 5200, .8)


DRUMS = {'kick': kick, 'snare': snare, 'clap': clap, 'hat': hat, 'open_hat': open_hat, 'shaker': shaker, 'rim': rim, 'tom_low': tom_low, 'tom_mid': tom_mid,
         'tom_high': tom_high, 'crash': crash, 'ride': ride, 'taiko': taiko, 'war_drum': war_drum, 'timpani': timpani, 'gong': gong, 'wood_block': wood_block, 'kick_808': kick_808, 'brush': brush, 'cowbell': cowbell, 'tambourine': tambourine,
         'conga': conga, 'bongo': bongo, 'triangle': triangle_hit, 'snap': finger_snap, 'small_cymbal': cymbal_small}

INSTRUMENTS = {'piano': piano, 'electric_piano': electric_piano, 'bell': bell, 'bronze_bell': bronze_bell, 'celesta': celesta, 'marimba': marimba, 'glock': glock,
               'guitar': guitar, 'steel_guitar': steel_guitar, 'harp': harp, 'bass_guitar': bass_guitar, 'guzheng': guzheng, 'pipa': pipa, 'strings': strings,
               'staccato_strings': staccato_strings, 'cello': cello, 'erhu': erhu, 'brass': brass, 'horn': horn, 'flute': flute, 'bamboo_flute': bamboo_flute,
               'clarinet': clarinet, 'choir': choir, 'pad': pad, 'warm_pad': warm_pad, 'organ': organ, 'lead': lead, 'pluck_synth': pluck_synth,
               'synth_bass': synth_bass, 'sub_bass': sub_bass, 'double_bass': double_bass, 'vibraphone': vibraphone, 'xylophone': xylophone, 'kalimba': kalimba, 'music_box': music_box,
               'steel_drum': steel_drum, 'yangqin': yangqin, 'ukulele': ukulele, 'mandolin': mandolin, 'koto': koto, 'violin': violin, 'viola': viola, 'trumpet': trumpet, 'trombone': trombone,
               'oboe': oboe, 'accordion': accordion, 'suona': suona, 'sheng': sheng, 'supersaw': supersaw, 'acid_bass': acid_bass, 'chip_square': chip_square, 'chip_pulse': chip_pulse,
               'chip_triangle': chip_triangle, 'glass_pad': glass_pad}

RANGES = {'piano': (21, 108), 'electric_piano': (28, 103), 'bell': (60, 96), 'bronze_bell': (36, 79), 'celesta': (60, 108), 'marimba': (45, 96), 'glock': (79, 108),
          'guitar': (40, 84), 'steel_guitar': (40, 84), 'harp': (24, 103), 'bass_guitar': (28, 67), 'guzheng': (38, 86), 'pipa': (45, 88), 'strings': (36, 100),
          'staccato_strings': (36, 96), 'cello': (36, 76), 'erhu': (62, 93), 'brass': (40, 84), 'horn': (41, 77), 'flute': (60, 96), 'bamboo_flute': (64, 96),
          'clarinet': (50, 91), 'choir': (43, 81), 'pad': (36, 88), 'warm_pad': (36, 84), 'organ': (36, 96), 'lead': (48, 96), 'pluck_synth': (40, 96),
          'synth_bass': (24, 60), 'sub_bass': (24, 55), 'double_bass': (28, 60), 'vibraphone': (53, 89), 'xylophone': (65, 108), 'kalimba': (55, 96), 'music_box': (48, 96), 'steel_drum': (50, 88),
          'yangqin': (41, 93), 'ukulele': (55, 84), 'mandolin': (55, 88), 'koto': (45, 86), 'violin': (55, 103), 'viola': (48, 88), 'trumpet': (52, 84), 'trombone': (40, 72), 'oboe': (58, 91),
          'accordion': (41, 93), 'suona': (55, 91), 'sheng': (55, 93), 'supersaw': (36, 96), 'acid_bass': (28, 60), 'chip_square': (36, 96), 'chip_pulse': (36, 96), 'chip_triangle': (24, 84), 'glass_pad': (48, 96)}

ROLE_LOUDNESS = {'piano': 1.2, 'guitar': 1.3, 'steel_guitar': 1.2, 'harp': 1.2, 'bell': .55, 'bronze_bell': .7, 'choir': 2.4, 'strings': .8, 'pad': .7, 'warm_pad': .9,
                 'organ': .32, 'flute': .55, 'bamboo_flute': .5, 'sub_bass': .8, 'lead': .55, 'brass': .7, 'horn': .85, 'cello': .9, 'erhu': .9, 'marimba': .9}


# --- filters ----------------------------------------------------------------------------------------------------------

def biquad(buf: list, kind: str, freq: float, sr: int, q: float = .707, gain: float = 0.0) -> list:
    """kind: low, high, band, peak, low_shelf, high_shelf (RBJ's cookbook)."""
    freq = min(freq, sr * .45)
    w = TAU * freq / sr
    cw, sw = math.cos(w), math.sin(w)
    alpha = sw / (2 * q)
    a_lin = 10 ** (gain / 40)
    if kind == 'low':
        b0, b1, b2, a0, a1, a2 = (1 - cw) / 2, 1 - cw, (1 - cw) / 2, 1 + alpha, -2 * cw, 1 - alpha
    elif kind == 'high':
        b0, b1, b2, a0, a1, a2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2, 1 + alpha, -2 * cw, 1 - alpha
    elif kind == 'band':
        b0, b1, b2, a0, a1, a2 = alpha, 0.0, -alpha, 1 + alpha, -2 * cw, 1 - alpha
    elif kind == 'peak':
        b0, b1, b2, a0, a1, a2 = 1 + alpha * a_lin, -2 * cw, 1 - alpha * a_lin, 1 + alpha / a_lin, -2 * cw, 1 - alpha / a_lin
    elif kind in ('low_shelf', 'high_shelf'):
        s = 2 * math.sqrt(a_lin) * alpha
        sign = 1 if kind == 'low_shelf' else -1
        b0 = a_lin * ((a_lin + 1) - sign * (a_lin - 1) * cw + s)
        b1 = sign * 2 * a_lin * ((a_lin - 1) - sign * (a_lin + 1) * cw)
        b2 = a_lin * ((a_lin + 1) - sign * (a_lin - 1) * cw - s)
        a0 = (a_lin + 1) + sign * (a_lin - 1) * cw + s
        a1 = -sign * 2 * ((a_lin - 1) + sign * (a_lin + 1) * cw)
        a2 = (a_lin + 1) + sign * (a_lin - 1) * cw - s
    else:
        raise ValueError(f'unknown filter {kind}')
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    x1 = x2 = y1 = y2 = 0.0
    out = [0.0] * len(buf)
    for i, x in enumerate(buf):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y
        x2, x1, y2, y1 = x1, x, y1, y
    return out


# --- effects for a game or a film ----------------------------------------------------------------------------------------

def _normal(buf: list, peak: float = .9) -> list:
    top = max((abs(v) for v in buf), default=0.0)
    if top < 1e-9:
        return buf
    g = peak / top
    return [v * g for v in buf]


def _rise(sr, length, start, end, wave='sine', vib=0.0, decay=6.0) -> list:
    """A tone gliding from start to end: most game sounds are this and a little else."""
    n = int(length * sr)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / n
        phase += TAU * (start * (end / start) ** t) * (1 + vib * math.sin(TAU * 30 * i / sr)) / sr
        x = math.sin(phase)
        if wave == 'square':
            x = 1.0 if x >= 0 else -1.0
        elif wave == 'triangle':
            x = 2 / math.pi * math.asin(x)
        out[i] = x * math.exp(-t * decay)
    return apply_env(out, sr, .001, .01)


class Fx:
    """Each returns a finished mono sound. seed gives another take of the same sound."""

    def __init__(self, sr: int):
        self.sr = sr

    # interface
    def click(self, seed=0):
        return _normal(_mix((_struck(1800, .03, 1, self.sr, [(1, 1, 180)], release=.005, attack=.0003), 1),
                            (_noise_hit(self.sr, .02, 200, f'click{seed}', 'high', 3000), .3)))

    def hover(self, seed=0):
        return _normal(_struck(2400, .04, .7, self.sr, [(1, 1, 110)], release=.01), .4)

    def confirm(self, seed=0):
        a = _struck(880, .1, 1, self.sr, [(1, 1, 18), (2, .2, 30)], release=.02)
        b = _struck(1320, .22, 1, self.sr, [(1, 1, 12), (2, .2, 22)], release=.05)
        return _normal(place(a, [(0, b)], int(.075 * self.sr)))

    def cancel(self, seed=0):
        a = _struck(660, .1, 1, self.sr, [(1, 1, 18)], release=.02)
        b = _struck(440, .2, 1, self.sr, [(1, 1, 12)], release=.05)
        return _normal(place(a, [(0, b)], int(.08 * self.sr)))

    def error(self, seed=0):
        tone = biquad(_rise(self.sr, .09, 190, 180, 'square', decay=.5), 'low', 1800, self.sr)
        return _normal(place(tone, [(0, tone)], int(.14 * self.sr)), .7)

    def notify(self, seed=0):
        a = bell(1046.5, .3, .8, self.sr)
        b = bell(1568, .5, .7, self.sr)
        return _normal(place(a, [(0, b)], int(.13 * self.sr)), .7)

    # game
    def coin(self, seed=0):
        a = _struck(1319, .07, 1, self.sr, [(1, 1, 16), (2.0, .3, 22)], release=.01)
        b = _struck(1976, .34, 1, self.sr, [(1, 1, 9), (2.0, .3, 16), (3.0, .1, 22)], release=.05)
        return _normal(place(a, [(0, b)], int(.07 * self.sr)))

    def jump(self, seed=0):
        return _normal(_rise(self.sr, .22, 180, 620, 'triangle', decay=2.5), .8)

    def land(self, seed=0):
        return _normal(_mix((_sweep(self.sr, .16, 130, 55, 40, 22), 1), (_noise_hit(self.sr, .09, 40, f'land{seed}', 'low', 1200), .5)))

    def powerup(self, seed=0):
        return _normal(_rise(self.sr, .7, 220, 1760, 'square', vib=.02, decay=1.8), .7)

    def level_up(self, seed=0):
        parts = []
        for k, f in enumerate((523.3, 659.3, 784, 1046.5)):
            parts.append((int(k * .095 * self.sr), bell(f, .5 if k == 3 else .2, .9, self.sr)))
        out = [0.0] * (max(p + len(b) for p, b in parts))
        for p, b in parts:
            for i, v in enumerate(b):
                out[p + i] += v
        return _normal(out)

    def laser(self, seed=0):
        return _normal(_rise(self.sr, .24, 1900, 170, 'square', decay=3.6), .7)

    def explosion(self, size=1.0, seed=0):
        """size 0.3 a grenade, 1 a shell, 2 a building."""
        n = int((.8 + 1.6 * size) * self.sr)
        rnd = _seed('boom', seed)
        out = [0.0] * n
        low = 0.0
        slow = 1.4 / size
        for i in range(n):
            t = i / self.sr
            low += (.018 + .28 * math.exp(-t * 7 * slow)) * ((rnd.random() * 2 - 1) - low)
            out[i] = low * math.exp(-t * 2.7 * slow)
        body = _sweep(self.sr, min(.9, .5 + .3 * size), 95, 28, 8, 4.4)
        crack = _noise_hit(self.sr, .07, 44, f'crack{seed}', 'band', 2300, .7)
        return _normal([math.tanh(v * 1.7) for v in _mix((out, 1.4), (body, 1), (crack, .3))])

    def hit(self, seed=0):
        return _normal(_mix((_sweep(self.sr, .13, 240, 80, 60, 26), 1), (_noise_hit(self.sr, .08, 56, f'hit{seed}', 'band', 1100, .7), .75)))

    def sword(self, seed=0):
        """A blade on a blade: a bright ring on inharmonic partials, after a scrape."""
        scrape = _noise_hit(self.sr, .05, 70, f'blade{seed}', 'high', 4200)
        ring = _struck(1720 + 90 * seed, .34, 1, self.sr, [(1, 1, 16), (1.48, .7, 18), (2.31, .6, 20), (3.17, .4, 26), (4.45, .25, 34)], release=.05, attack=.0006)
        return _normal(_mix((scrape, .6), (ring, .9)))

    def swoosh(self, seed=0):
        n = int(.3 * self.sr)
        noise = _noise(n, f'swoosh{seed}')
        out = [0.0] * n
        low = band = 0.0
        for i in range(n):
            t = i / n
            env = math.sin(math.pi * t) ** 2
            f = 2 * math.sin(math.pi * (500 + 3000 * math.sin(math.pi * t)) / self.sr)
            low += f * band
            band += f * (noise[i] - low - .7 * band)
            out[i] = band * env
        return _normal(out, .7)

    def arrow(self, seed=0):
        twang = _pluck(150, .1, .9, self.sr, tone=.8, seed='bow')
        return _normal(_mix((twang, .7), (self.swoosh(seed), .8)))

    def shield(self, seed=0):
        return _normal(_mix((_struck(410, .28, 1, self.sr, [(1, 1, 14), (1.59, .7, 19), (2.72, .5, 28), (3.9, .3, 40)], release=.04, attack=.0006), 1),
                            (_noise_hit(self.sr, .05, 60, f'sh{seed}', 'band', 2400), .4)))

    def footstep(self, surface='stone', seed=0):
        tone = {'stone': 1500, 'wood': 620, 'grass': 3400, 'snow': 2400, 'mud': 500}.get(surface, 1200)
        thud = _sweep(self.sr, .09, 130, 70, 40, 38)
        scuff = _noise_hit(self.sr, .1, 34, f'{surface}{seed}', 'band', tone, 1.0)
        return _normal(_mix((thud, .7), (scuff, 1 if surface in ('grass', 'snow', 'mud') else .55)), .7)

    def door(self, seed=0):
        thud = _sweep(self.sr, .24, 120, 60, 26, 15)
        wood = _struck(240, .16, 1, self.sr, [(1, 1, 30), (2.3, .6, 42), (3.7, .3, 60)], release=.03)
        return _normal(_mix((thud, 1), (wood, .7)))

    def horse(self, seed=0):
        """Four hooves on hard ground."""
        hoof = _mix((_sweep(self.sr, .07, 240, 110, 60, 48), 1), (_noise_hit(self.sr, .04, 90, f'hoof{seed}', 'band', 1800), .4))
        marks = [0, .075, .2, .29]
        out = [0.0] * int(.5 * self.sr)
        for k, at in enumerate(marks):
            p = int(at * self.sr)
            for i, v in enumerate(hoof):
                out[p + i] += v * (.7 + .1 * k)
        return _normal(out, .8)

    def horn_call(self, seed=0):
        """A war horn: one long low note that swells and breaks at the end."""
        tone = _sub(146.8, 1.8, .8, self.sr, detune=(-8, 0, 7), cutoff=700, env_amt=.9, env_time=.5, attack=.3, decay=.3, sustain=.95, release=.4, vib_rate=4, vib_depth=.002, seed=f'call{seed}')
        return _normal(tone, .85)

    def thunder(self, seed=0):
        n = int(5 * self.sr)
        rnd = _seed('thunder', seed)
        out = [0.0] * n
        low = 0.0
        strikes = [(rnd.uniform(.05, 3.4), rnd.uniform(.2, 1)) for _ in range(7)]
        gain = target = 0.0
        for i in range(n):
            if i % 64 == 0:
                t = i / self.sr
                target = sum(w * math.exp(-(t - s) * 3) for s, w in strikes if t >= s)
            gain += .002 * (target - gain)
            low += .05 * ((rnd.random() * 2 - 1) - low)
            out[i] = low * gain
        return _normal(apply_env(out, self.sr, .01, 1.2))

    # short pieces for a game's moments
    def _tune(self, kind, notes, gap, hold=.5):
        parts = [(int(i * gap * self.sr), kind(440 * 2 ** ((n - 69) / 12), hold, .9, self.sr)) for i, n in enumerate(notes)]
        out = [0.0] * max(p + len(b) for p, b in parts)
        for p, b in parts:
            for i, v in enumerate(b):
                out[p + i] += v
        return _normal(out)

    def victory(self, seed=0):
        return self._tune(brass, [60, 64, 67, 72, 67, 72, 76], .13, .4)

    def defeat(self, seed=0):
        return self._tune(strings, [64, 62, 60, 57, 55], .3, .7)

    def discover(self, seed=0):
        return self._tune(celesta, [72, 76, 79, 84, 88], .09, .5)

    def quest(self, seed=0):
        return self._tune(harp, [60, 67, 72, 76, 79, 84], .08, .6)

    def danger(self, seed=0):
        return self._tune(cello, [40, 41, 40, 41], .25, .4)

    def magic(self, seed=0):
        n = int(1.2 * self.sr)
        rnd = _seed('magic', seed)
        out = [0.0] * n
        for _ in range(40):
            at = rnd.randrange(0, int(.7 * self.sr))
            b = _struck(rnd.uniform(1400, 4800), .25, .8, self.sr, [(1, 1, 14), (2.76, .3, 22)], release=.05)
            for i, v in enumerate(b):
                if at + i < n:
                    out[at + i] += v * rnd.uniform(.2, .7)
        return _normal(out, .8)

    def heal(self, seed=0):
        return _normal(_rise(self.sr, .9, 330, 1320, 'sine', decay=2.2), .8)

    def typing(self, seed=0):
        rnd = _seed('type', seed)
        n = int(1.6 * self.sr)
        out = [0.0] * n
        at = 0
        while at < n - 2000:
            key = _noise_hit(self.sr, .02, 180, rnd.random(), 'band', 2400, 1.2)
            for i, v in enumerate(key):
                out[at + i] += v * rnd.uniform(.5, 1)
            at += int(rnd.uniform(.06, .17) * self.sr)
        return _normal(out, .7)

    def birds(self, seconds=8.0, seed=0):
        n = int((seconds + 1) * self.sr)
        rnd = _seed('birds', seed)
        out = [v * .05 for v in biquad(_noise(n, f'air{seed}'), 'band', 900, self.sr)]
        for _ in range(int(seconds * 1.6)):
            at = rnd.randrange(0, n - self.sr)
            base = rnd.uniform(2600, 4600)
            for k in range(rnd.randint(2, 5)):
                chirp = _rise(self.sr, .09, base, base * rnd.uniform(1.1, 1.5), 'sine', decay=2)
                p = at + k * int(.12 * self.sr)
                for i, v in enumerate(chirp):
                    if p + i < n:
                        out[p + i] += v * .35
        return _normal(self._loop(out, self.sr), .6)

    def night(self, seconds=8.0, seed=0):
        n = int((seconds + 1) * self.sr)
        rnd = _seed('crickets', seed)
        out = [v * .04 for v in biquad(_noise(n, f'night{seed}'), 'low', 500, self.sr)]
        pulse = [math.sin(TAU * 4300 * i / self.sr) * math.exp(-i / self.sr * 40) for i in range(int(.05 * self.sr))]
        for _ in range(int(seconds * 4)):
            at = rnd.randrange(0, n - self.sr)
            for k in range(3):
                for i, v in enumerate(pulse):
                    out[at + k * int(.06 * self.sr) + i] += v * .2
        return _normal(self._loop(out, self.sr), .6)

    def cave(self, seconds=8.0, seed=0):
        n = int((seconds + 1) * self.sr)
        rnd = _seed('drip', seed)
        out = [v * .3 for v in biquad(_noise(n, f'cave{seed}'), 'low', 160, self.sr)]
        for _ in range(int(seconds * 1.2)):
            at = rnd.randrange(0, n - self.sr // 2)
            drop = _rise(self.sr, .08, rnd.uniform(800, 1600), rnd.uniform(1600, 2800), 'sine', decay=4)
            for i, v in enumerate(drop):
                out[at + i] += v * .5
        return _normal(self._loop(out, self.sr), .6)

    def market(self, seconds=8.0, seed=0):
        """A crowd in the open: close to the battle's, softer, with a few sharper voices."""
        return _normal([v * .7 for v in self.battle_crowd(seconds, seed)], .5)

    # beds that loop: the end flows back into the start
    def _loop(self, buf, fade):
        n = len(buf) - fade
        out = buf[:n]
        for i in range(fade):
            a = i / fade
            out[i] = buf[n + i] * (1 - a) + buf[i] * a
        return out

    def rain(self, seconds=8.0, heavy=.5, seed=0):
        n = int((seconds + 1) * self.sr)
        hiss = biquad(_noise(n, f'rain{seed}'), 'high', 1400, self.sr)
        low = biquad(_noise(n, f'rain2{seed}'), 'low', 480, self.sr)
        rnd = _seed('drops', seed)
        out = [a * .5 + b * .5 * heavy for a, b in zip(hiss, low)]
        drop = _struck(1500, .02, 1, self.sr, [(1, 1, 170)], release=.004)
        for _ in range(int(seconds * (8 + 80 * heavy))):
            p = rnd.randrange(0, n - len(drop))
            g = rnd.random() * 1.4
            for i, v in enumerate(drop):
                out[p + i] += v * g
        return _normal(self._loop(out, self.sr), .6)

    def wind(self, seconds=8.0, seed=0):
        n = int((seconds + 1) * self.sr)
        noise = _noise(n, f'wind{seed}')
        rnd = _seed('gust', seed)
        phases = [rnd.random() * TAU for _ in range(3)]
        out = [0.0] * n
        low = band = 0.0
        for i in range(n):
            t = i / self.sr
            g = .5 + .25 * math.sin(.37 * t + phases[0]) + .17 * math.sin(.91 * t + phases[1]) + .08 * math.sin(2.1 * t + phases[2])
            f = 2 * math.sin(math.pi * (220 + 680 * g) / self.sr)
            low += f * band
            band += f * (noise[i] - low - .45 * band)
            out[i] = band * (.25 + g)
        return _normal(self._loop(out, self.sr), .55)

    def fire(self, seconds=6.0, seed=0):
        n = int((seconds + 1) * self.sr)
        rnd = _seed('crackle', seed)
        out = [v * .35 for v in biquad(_noise(n, f'fire{seed}'), 'low', 300, self.sr)]
        for _ in range(int(seconds * 11)):
            p = rnd.randrange(0, n - int(.02 * self.sr))
            pop = _noise_hit(self.sr, .012, 300, rnd.random(), 'high', 1400 + rnd.random() * 3600)
            g = .15 + rnd.random() ** 3 * 1.3
            for i, v in enumerate(pop):
                out[p + i] += v * g
        return _normal(self._loop(out, self.sr), .6)

    def waves(self, seconds=10.0, seed=0):
        n = int((seconds + 1) * self.sr)
        noise = biquad(_noise(n, f'sea{seed}'), 'low', 2200, self.sr)
        slow = TAU / 6.3
        out = [v * (.1 + .9 * max(0.0, math.sin(i / self.sr * slow)) ** 2) for i, v in enumerate(noise)]
        return _normal(self._loop(out, self.sr), .6)

    def battle_crowd(self, seconds=6.0, seed=0):
        """Many far-off shouts: filtered, swelling noise and low voices."""
        n = int((seconds + 1) * self.sr)
        noise = _noise(n, f'crowd{seed}')
        a = biquad(noise, 'band', 700, self.sr, q=1.2)
        b = biquad(noise, 'band', 1400, self.sr, q=2)
        rnd = _seed('swell', seed)
        p, q = rnd.random() * TAU, rnd.random() * TAU
        out = [(x + .5 * y) * (.55 + .25 * math.sin(i / self.sr * 1.7 + p) + .2 * math.sin(i / self.sr * 3.1 + q)) for i, (x, y) in enumerate(zip(a, b))]
        return _normal(self._loop(out, self.sr), .6)


def place(first: list, later: list, offset: int) -> list:
    """first at 0, each of later (extra offset, sound) at offset + its extra."""
    n = max([len(first)] + [offset + o + len(b) for o, b in later])
    out = [0.0] * n
    out[:len(first)] = first
    for o, b in later:
        for i, v in enumerate(b):
            out[offset + o + i] += v
    return out


def reverb(left_in: list, right_in: list, sr: int, size: float = .8, damp: float = .35) -> tuple:
    """A hall from eight combs and four all-pass filters (Schroeder, tuned as Freeverb is). It runs at half the rate: a tail
    has no real top end, and Python pays for every sample."""
    down_l = [(left_in[i] + left_in[i + 1]) * .5 for i in range(0, len(left_in) - 1, 2)]
    down_r = [(right_in[i] + right_in[i + 1]) * .5 for i in range(0, len(right_in) - 1, 2)]
    rate = sr / 2
    scale = rate / 44100
    fb = .72 + .26 * min(size, 1.0)
    keep = 1 - damp
    out = []
    for src, spread in ((down_l, 0), (down_r, 23)):
        total = [0.0] * len(src)
        for base in (1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617):
            size_of = max(8, int((base + spread) * scale * 1.5))
            line = [0.0] * size_of
            p = 0
            last = 0.0
            for i, x in enumerate(src):
                y = line[p]
                last = y * keep + last * damp
                line[p] = x + last * fb
                p = p + 1 if p + 1 < size_of else 0
                total[i] += y
        for base in (556, 441, 341, 225):
            size_of = max(8, int((base + spread) * scale))
            line = [0.0] * size_of
            p = 0
            for i, x in enumerate(total):
                y = line[p]
                line[p] = x + y * .5
                total[i] = y - x
                p = p + 1 if p + 1 < size_of else 0
        wet = [0.0] * (len(total) * 2)  # back up to the full rate
        for i, v in enumerate(total):
            nxt = total[i + 1] if i + 1 < len(total) else 0.0
            wet[2 * i] = v * .06
            wet[2 * i + 1] = (v + nxt) * .03
        out.append(wet)
    return out[0], out[1]
