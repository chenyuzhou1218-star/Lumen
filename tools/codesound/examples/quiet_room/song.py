"""A small quiet piano piece, with strings that arrive late."""
import cs

cs.song(tempo=66, key='F major', title='After the Rain', reverb=.75)

left = cs.track('piano', vol=.7, pan=-.15, reverb=.3)
right = cs.track('piano', vol=.86, pan=.12, reverb=.3)
strings = cs.track('strings', vol=.3, pan=.26, reverb=.5, low_cut=220, wide=.5)
cello = cs.track('cello', vol=.42, pan=-.25, reverb=.4)

A = 'Fmaj7 | C/E | Dm7 | Bb'
B = 'Gm7 | C | Am7 | Dm7 | Gm7 | C | F | F'

with cs.section('alone', 4):
    left.chords(A, style='arp_up', every=.5, octave=3, vel=.42)

with cs.section('tune', 4):
    left.chords(A, style='arp_up', every=.5, octave=3, vel=.46)
    right.tune("5:1.5 6:.5 5:1 3:1 | 2:2 3:1 5:1 | 6:1.5 5:.5 3:2 | 4:1 3:1 2:2", octave=4, vel=.62)

with cs.section('tune again', 4):
    left.chords(A, style='arp_up', every=.5, octave=3, vel=.5)
    cello.bass(A, style='root', octave=3, vel=.5)
    right.tune("5:1.5 6:.5 5:1 3:1 | 2:2 3:1 5:1 | 6:1.5 5:.5 8:2 | 7:1 6:1 5:2", octave=4, vel=.66)

with cs.section('open', 8):
    left.chords(B, style='arp_wave', every=.5, octave=3, vel=.56)
    strings.chords(B, style='hold', octave=4, vel=.55)
    cello.bass(B, style='root', octave=3, vel=.55)
    right.tune("6:2 8:1 9:1 | 10:3 9:1 | 8:2 7:1 6:1 | 5:4 | 6:2 8:1 9:1 | 10:2 12:2 | 10:1 9:1 8:2 | 8:4", octave=4, vel=(.62, .72))

with cs.section('leave', 4):
    left.chords('Fmaj7 | Bb | Fmaj7 | r', style='arp_up', every=.5, octave=3, vel=.4)
    right.tune("r:2 5:1 3:1 | 2:2 1:2 | r:4 | r:4", octave=4, vel=.5)
    strings.chords('Fmaj7 | Bb | Fmaj7 | r', style='hold', octave=4, vel=.4)
