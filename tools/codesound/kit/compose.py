"""Writes a whole piece from a style: form, harmony, a tune built from one short idea, and who plays when.

Nothing here is a recording or a template to be filled in: the seed picks the idea and the rules develop it, so that every seed is a new piece.
The rules are the ordinary ones of the craft: the tune moves mostly by step and rests at phrase ends, the answer changes the end of the question, the
last section of a phrase leans on the dominant, the middle lifts by register and adds players, the end comes home.
cs.compose('古风', seconds=90, seed=3)
"""
from __future__ import annotations

import random

STYLES = {
    '古风': dict(tempo=(66, 80), key='D yu', beats=4, chords=['Dm C Dm Am', 'F C Dm Am', 'Dm F C Dm', 'Bb F C Dm'], lead='bamboo_flute', second='erhu', harmony='guzheng', style='arp_wave', pad='strings', bass='double_bass', drums='ritual', bells='bronze_bell'),
    '战斗': dict(tempo=(120, 140), key='E minor', beats=4, chords=['Em C G D', 'Em Am C B', 'Em D C B', 'Am Em B Em'], lead='brass', second='strings', harmony='staccato_strings', style='pulse', pad='choir', bass='cello', drums='war', bells='bell'),
    '史诗': dict(tempo=(84, 100), key='C minor', beats=4, chords=['Cm Ab Eb Bb', 'Cm Fm Ab G', 'Ab Bb Cm Cm', 'Fm Cm G Cm'], lead='horn', second='violin', harmony='strings', style='pulse', pad='choir', bass='double_bass', drums='war', bells='bronze_bell'),
    '悬疑': dict(tempo=(60, 76), key='A harmonic_minor', beats=4, chords=['Am Am F E', 'Am Dm E Am', 'Am F Dm E', 'Dm Am E E'], lead='clarinet', second='cello', harmony='glass_pad', style='hold', pad='warm_pad', bass='double_bass', drums=None, bells='celesta'),
    '轻音乐': dict(tempo=(72, 92), key='F major', beats=4, chords=['F C Dm Bb', 'F Am Bb C', 'Dm Bb F C', 'Bb C F F'], lead='piano', second='flute', harmony='piano', style='arp_up', pad='strings', bass='double_bass', drums=None, bells='celesta'),
    '田园': dict(tempo=(92, 112), key='G major', beats=3, chords=['G C D G', 'G Em C D', 'C G D G', 'Em C D G'], lead='flute', second='clarinet', harmony='harp', style='arp_up', pad='strings', bass='double_bass', drums=None, bells='glock'),
    '电子': dict(tempo=(118, 128), key='A minor', beats=4, chords=['Am F C G', 'Am F C E', 'F G Am Am', 'Dm Am G Am'], lead='lead', second='pluck_synth', harmony='supersaw', style='x..x..x.', pad='pad', bass='synth_bass', drums='four', bells='electric_piano'),
    '合成器': dict(tempo=(96, 112), key='E minor', beats=4, chords=['Em C G D', 'Am C Em D', 'C D Em Em', 'G D Em C'], lead='lead', second='glass_pad', harmony='pluck_synth', style='arp_up', pad='warm_pad', bass='acid_bass', drums='trap', bells='vibraphone'),
    '摇滚': dict(tempo=(112, 132), key='A minor', beats=4, chords=['Am F C G', 'Am G F E', 'C G Am F', 'F G Am Am'], lead='steel_guitar', second='lead', harmony='guitar', style='x.x.x.x.', pad='organ', bass='bass_guitar', drums='rock', bells='piano'),
    '爵士': dict(tempo=(100, 128), key='C major', beats=4, chords=['Cmaj7 Am7 Dm7 G7', 'Em7 A7 Dm7 G7', 'Fmaj7 Fm6 Em7 A7', 'Dm7 G7 Cmaj7 Cmaj7'], lead='clarinet', second='vibraphone', harmony='electric_piano', style='x..x....', pad=None, bass='double_bass', drums='ballad', bells='vibraphone', swing=.3, walk=True),
    '芯片': dict(tempo=(132, 156), key='C major', beats=4, chords=['C G Am F', 'C F G C', 'Am F C G', 'F G C C'], lead='chip_square', second='chip_pulse', harmony='chip_pulse', style='arp_up', pad=None, bass='chip_triangle', drums='rock', bells='chip_square'),
    '儿歌': dict(tempo=(100, 120), key='C major', beats=4, chords=['C F G C', 'C Am F G', 'F C G C', 'C G C C'], lead='music_box', second='kalimba', harmony='ukulele', style='pulse', pad=None, bass='bass_guitar', drums=None, bells='glock'),
    '冥想': dict(tempo=(54, 64), key='D gong', beats=4, chords=['D Bm G D', 'G D A D', 'Bm G D A', 'G A D D'], lead='flute', second='bronze_bell', harmony='warm_pad', style='hold', pad='glass_pad', bass=None, drums=None, bells='bronze_bell'),
    '菜单': dict(tempo=(84, 100), key='D major', beats=4, chords=['D A Bm G', 'D G A D', 'Bm G D A', 'G A D D'], lead='harp', second='flute', harmony='strings', style='hold', pad='pad', bass='double_bass', drums=None, bells='celesta', loop=True),
}


def _idea(rnd, beats: int, wide: int) -> list:
    """One bar: the seed of the whole tune. A list of (scale step, beats)."""
    shapes = ([1, 1, 2], [2, 1, 1], [1.5, .5, 2], [1, .5, .5, 2], [3, 1], [.5, .5, 1, 2]) if beats == 4 else ([1, 1, 1], [2, 1], [1.5, .5, 1])
    rhythm = list(rnd.choice(shapes))
    step = rnd.choice((0, 2, 4))
    out = []
    for length in rhythm:
        out.append((step, length))
        step += rnd.choice((1, -1, 1, -1, 2, -2))
        step = max(-1, min(wide, step))
    return out


def _bar_text(bar: list, shift: int, count: int) -> str:
    out = []
    for step, length in bar:
        v = step + shift
        degree = v % count + 1
        up = v // count
        out.append(f"{degree}{chr(39) * max(up, 0)}{',' * max(-up, 0)}:{length:g}")
    return ' '.join(out)


def _phrase(rnd, idea: list, count: int, shift: int, end: int, beats: int) -> str:
    """Four bars: the idea, its echo higher, a variation, and a held note to breathe on."""
    bars = [_bar_text(idea, shift, count), _bar_text(idea, shift + rnd.choice((1, 2)), count)]
    varied = [(s + rnd.choice((0, 1, -1)), n) for s, n in idea]
    bars.append(_bar_text(varied, shift + rnd.choice((0, 1)), count))
    bars.append(_bar_text([(end, beats)], shift, count))
    return ' | '.join(bars)


def compose(cs, style: str = '古风', seconds: float = 90, seed: int = 1) -> dict:
    if style not in STYLES:
        raise cs.SongError(f'没有 {style} 这种风格。有：{"、".join(STYLES)}')
    p = STYLES[style]
    rnd = random.Random(f'{style}{seed}')
    tempo = rnd.randint(*p['tempo'])
    beats = p['beats']
    cs.song(tempo=tempo, key=p['key'], beats=beats, swing=p.get('swing', 0), title=f'{style} {seed}', loop=p.get('loop', False))
    cs.fade(out=2.5 if not p.get('loop') else 0)
    scale_size = len(cs.SCALES[p['key'].split()[1]])
    bar_seconds = 60 / tempo * beats
    phrases = max(2, min(16, round(seconds / bar_seconds / 4)))
    # form: quiet, tune, answer, lift, ... , home
    plan = ['open'] + (['tune', 'answer'] * phrases)[:max(1, phrases - 2)]
    if len(plan) > 3:
        plan[len(plan) * 2 // 3] = 'lift'
        plan[len(plan) * 2 // 3 + (1 if len(plan) * 2 // 3 + 1 < len(plan) else 0)] = 'lift'
    plan.append('home')
    chords = {name: rnd.choice(p['chords']) for name in ('open', 'tune', 'answer', 'lift')}
    chords['answer'] = rnd.choice([c for c in p['chords'] if c != chords['tune']] or p['chords'])
    chord_text = {k: ' | '.join(v.split()) for k, v in chords.items()}
    idea = _idea(rnd, beats, scale_size + 2)

    lead = cs.track(p['lead'], vol=.8, pan=.05, reverb=.3, name='主旋律')
    second = cs.track(p['second'], vol=.46, pan=-.24, reverb=.35, low_cut=200, name='副旋律')
    harm = cs.track(p['harmony'], vol=.52, pan=.2, reverb=.28, low_cut=180, wide=.35, name='和声')
    pad = cs.track(p['pad'], vol=.3, pan=-.1, reverb=.5, low_cut=220, wide=.5, name='铺底') if p['pad'] else None
    bass = cs.track(p['bass'], vol=.72, reverb=.06, duck=.3 if p['drums'] else 0, name='低音') if p['bass'] else None
    drums = cs.track('drums', vol=.7, reverb=.16, name='鼓') if p['drums'] else None
    bell = cs.track(p['bells'], vol=.34, pan=.3, reverb=.5, name='点缀')
    root = 0
    for n, part in enumerate(plan):
        with cs.section(f'{part}{n + 1}', 4):
            text = chord_text.get(part, chord_text['tune'])
            big = part == 'lift'
            soft = part in ('open', 'home')
            style_now = p['style']
            every = .5 if style_now.startswith('arp') or style_now == 'pulse' else 1.0
            if part == 'home':
                last = text.split(' | ')[0]
                harm.chords(f'{last} | {last} | {last} | r', style='hold', octave=4, vel=.45)
                if pad:
                    pad.chords(f'{last} | {last} | {last} | r', octave=4, vel=.4)
                if bass:
                    bass.bass(f'{last} | {last} | {last} | r', style='root')
                lead.tune(_bar_text([(0, beats)], root + 7 if scale_size == 7 else root + 5, scale_size) + ' | r:' + str(beats) + ' | r:' + str(beats) + ' | r:' + str(beats), octave=4, vel=.5)
                bell.hit_note(cs, 0)
                continue
            harm.chords(text, style=style_now, every=every, octave=3 if every < 1 else 4, vel=.42 if soft else .6 if big else .52)
            if pad and not soft:
                pad.chords(text, octave=4, vel=.5 if big else .38)
            if bass and part != 'open':
                walk = p.get('walk')
                bass.bass(text, style='walk' if walk else ('pulse' if drums and big else 'root'), vel=.72)
            if drums and part != 'open':
                drums.beat(p['drums'], bars=4, vel=.92 if big else .74, fill=True)
                if big:
                    drums.hit('crash', .8)
            if part != 'open':
                shift = (scale_size if big else 0) + root + (2 if part == 'answer' else 0)
                end = 0 if part != 'tune' else (4 if scale_size == 7 else 3)
                lead.tune(_phrase(rnd, idea, scale_size, shift, end, beats), octave=4, vel=.82 if big else .72)
                if part in ('answer', 'lift'):
                    second.rest(beats * 2)
                    second.tune(_phrase(rnd, idea, scale_size, shift - scale_size, 0, beats).rsplit(' | ', 2)[0], octave=4, vel=.5)
            else:
                bell.hit_note(cs, scale_size + 4)
    _into_range(cs)
    return {'style': style, 'seed': seed, 'tempo': tempo, 'key': p['key'], 'sections': len(plan), 'instruments': [p['lead'], p['second'], p['harmony']]}


def _into_range(cs) -> None:
    """A note an instrument cannot play goes up or down by octaves until it can: the tune stays the tune."""
    import synth

    for t in cs.S.tracks:
        lo, hi = synth.RANGES.get(t.instrument, (0, 127))
        for e in t.notes:
            while isinstance(e['m'], int) and e['m'] < lo:
                e['m'] += 12
            while isinstance(e['m'], int) and e['m'] > hi:
                e['m'] -= 12


def track_hit_note(self, cs, step: int) -> None:
    """One note on the first beat of a section: a bell over a change."""
    v = self._here()
    midi = self.notes_of(f'{step % len(cs.S.scale) + 1}' + "'" * (step // len(cs.S.scale)), 4)[0]
    self._add(v, 3.5, midi, .5)
