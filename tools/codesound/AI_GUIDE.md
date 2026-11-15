# Making music and sound with CodeSound

A project is a folder: `project.json` and `song.py`. You cannot hear. So you work from what can be measured, and you say so.

## The way of working, always in this order

1. Decide the piece in words first: what it is for, the mood, the tempo, the key, the form (for example quiet 4 bars, tune 8, big 8, tune 8, end 4).
2. Write the chords and the tune first, nothing else. `score` tells you whether it is written properly. Then add the rest.
3. Render `quality=check`, read the numbers and the notes, and look at the picture: notes on top, spectrum in the middle, loudness below.
4. Fix the biggest thing and render again, at least three rounds. Then `quality=final` once.
5. In your report, say what you measured and changed. Never claim a piece sounds beautiful: you did not hear it. The user's ear decides.

## What makes it sound like music

- **A tune people could sing.** Mostly steps, one leap at the high point, and rests to breathe. Repeat a short idea, then change its end.
- **Sections differ by who plays, not by volume.** Start with few instruments, add them, take most away before the biggest moment.
- **Keep to one job per register.** Bass low, chords in the middle, tune above. Cut the low end of everything that is not bass (`low_cut=180`).
- **Tune loudest.** Chords and pads sit under it: `vol` about half of the tune's.
- **Space.** Reverb on things far away, little on bass and kick. Spread chords with `pan` and `wide`; bass, kick and tune stay in the middle.
- **A minor song ends strong on the dominant with `#7`** (`A` chord in D minor). Numbers keep you in the scale; write `#7` when you want out of it.
- **Bass with kick:** give the bass `duck=.4` and it steps aside on each kick.
- **An ending.** Hold the last chord long, or stop on a hit. Do not just run out.

## Writing

```python
import cs
cs.song(tempo=72, key='A yu', title='Old City')       # yu, gong, shang, jue, zhi are the Chinese modes
zheng = cs.track('guzheng', vol=.8, pan=-.2, reverb=.3)
flute = cs.track('bamboo_flute', vol=.6, reverb=.4)
drums = cs.track('drums', vol=.6, reverb=.25)
with cs.section('open', 4):
    zheng.chords('Am | G | Am | Em', style='arp_wave', every=.5, octave=3, vel=.55)
with cs.section('tune', 8):
    zheng.chords('Am | G | C | Am | F | G | Am | Am', style='broken', every=.5, octave=3)
    flute.tune("1:2 2:1 3:1 | 5:3 3:1 | 2:2 1:2 | 6,:4 | 1:2 2:1 3:1 | 5:2 6:2 | 5:1 3:1 2:2 | 1:4")
    drums.beat('ritual', bars=8)
```

- Numbers are by the scale, in `tune`: `3:.5` half a beat, `5'` up an octave, `5,` down, `b3`, `#4`, `r:1` a rest, `[1 3 5]:2` together. Names work too: `D4:1`.
- `vel=(.3,.9)` swells over a whole `tune` call. Every track of a `section` starts at the same bar.
- A `|` in a tune is checked: a bar that does not add up is reported.
- Python is all here: loops, functions, `for` over sections.

## A whole piece at once

`cs.compose('战斗', seconds=90, seed=3)` writes form, harmony, tune and arrangement by rule. Styles: 古风 战斗 史诗 悬疑 轻音乐 田园 电子 合成器 摇滚 爵士 芯片 儿歌 冥想 菜单. It is a good start; add tracks after it, or write your own when the user wants something particular. Another seed is another piece. 菜单 loops without a seam.

## More to write with

- `cs.song(loop=True)` for a game: the tail wraps round to the start. `cs.fade(fade_in=1, out=3)`, `cs.master('响亮')`, `cs.transpose(2)` for a last chorus, `cs.tempo_at(beat, bpm)` for a slower ending.
- On a track: `drive=` warmth or distortion, `chorus=`, `tremolo=`, `crush=` an old console, `sweep=(300, 4000)` a filter opening over the song.
- `t.roll('snare', 2)`, `t.euclid('kick', 3, 8)`, `t.grace('C4', 'D4')`, `t.glide('C4', 'C5')`, `t.tremolo_note('E4', 2)`.
- `cs.midi_file('tune.mid', 'guzheng')` plays a MIDI file on any instrument.
- Export: `export --format mp3`. `measure file.wav` measures any recording the same way.

## Sound effects

```python
fx = cs.fx()
cs.save('coin', fx.coin())
cs.save('sword_1', fx.sword(seed=1))
cs.save('rain_loop', fx.rain(seconds=10, heavy=.7))   # rain, wind, fire, waves and battle_crowd loop without a seam
```

Also `victory defeat discover quest danger magic heal typing`, and beds `birds night cave market`. Each lands in `out/sfx/`. Different `seed`s give different takes: a game needs three footsteps, not one. To put a sound in a song: `cs.track('sounds').place(fx.thunder(), beat=32)`.

## Using the results

`out/final.wav` goes into CodeCut as audio, or into a game. `--stems` gives every track on its own in `out/stems/`, `midi` the notes for other programs.
