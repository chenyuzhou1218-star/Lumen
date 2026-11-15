"""A war march of an old kingdom: drums first, then horns, then the whole army."""
import cs

cs.song(tempo=108, key='D yu', title='Banners at Dawn', reverb=.85)

drums = cs.track('drums', vol=.8, reverb=.3)
low = cs.track('cello', vol=.6, pan=-.1, reverb=.25, duck=.3)
bass = cs.track('double_bass', vol=.7, reverb=.05, duck=.4)
zheng = cs.track('guzheng', vol=.5, pan=-.32, reverb=.25, low_cut=220)
strings = cs.track('strings', vol=.42, pan=.3, reverb=.4, low_cut=200, wide=.5)
horns = cs.track('horn', vol=.6, pan=.14, reverb=.45)
brass = cs.track('brass', vol=.52, pan=-.14, reverb=.45, low_cut=160)
erhu = cs.track('erhu', vol=.6, pan=.05, reverb=.35)
choir = cs.track('choir', vol=.5, reverb=.6, low_cut=220, wide=.6)
sounds = cs.track('sounds', vol=.6, reverb=.5)

PLAIN = 'Dm | C | Dm | Am | Dm | C | Bb | Am'
LIFT = 'F | C | Dm | Am | Bb | F | Gm | Am'

with cs.section('far', 4):
    drums.beat('war', bars=4, vel=.55)
    sounds.place(cs.fx().horn_call(seed=1), beat=4)

with cs.section('gather', 8):
    drums.beat('war', bars=8, vel=.68, fill=True)
    bass.bass(PLAIN, style='pulse')
    low.bass(PLAIN, style='root', octave=3, vel=.5)
    zheng.chords(PLAIN, style='arp_up', every=.5, octave=4, vel=.5)

with cs.section('call', 8):
    drums.hit('gong', .9)
    drums.beat('war', bars=8, vel=.78, fill=True)
    bass.bass(PLAIN, style='pulse')
    low.bass(PLAIN, style='root', octave=3)
    zheng.chords(PLAIN, style='arp_up', every=.5, octave=4)
    strings.chords(PLAIN, style='hold', octave=4, vel=.5)
    erhu.tune("1':2 7:1 1':1 | 5:3 r:1 | 1':1 2':1 3':2 | 2':3 r:1 | 5':2 3':1 2':1 | 1':2 7:2 | 6:1 7:1 1':1 2':1 | 1':4", octave=4, vel=.75)

with cs.section('army', 8):
    drums.hit('crash', .9)
    drums.beat('war', bars=8, vel=.92, fill=True)
    bass.bass(LIFT, style='octave')
    low.bass(LIFT, style='pulse', octave=3)
    zheng.chords(LIFT, style='arp_wave', every=.25, octave=4, vel=.55)
    strings.chords(LIFT, style='pulse', every=.5, octave=4, vel=.6)
    choir.chords(LIFT, style='hold', octave=4, vel=.55)
    horns.tune("3':2 2':1 1':1 | 5:3 r:1 | 1':1 2':1 3':2 | 5:3 r:1", octave=3, vel=.8)
    horns.tune("6:2 1':1 2':1 | 3':3 5:1 | 4:2 2:2 | 5:4", octave=3, vel=.85)
    brass.tune("3':2 2':1 1':1 | 5:3 r:1 | 1':1 2':1 3':2 | 5:3 r:1 | 6:2 1':1 2':1 | 3':3 5:1 | 4:2 2:2 | 5:4", octave=4, vel=.8)

with cs.section('home', 4):
    drums.hit('gong', 1)
    drums.beat('war', bars=2, vel=.8)
    drums.beat(taiko='x...............', bars=1, vel=1)
    bass.bass('Dm | Dm | Dm | r', style='root')
    low.bass('Dm | Dm | Dm | r', style='root', octave=3)
    strings.chords('Dm | Dm | Dm | r', style='hold', octave=4, vel=.5)
    choir.chords('Dm | Dm | Dm | r', style='hold', octave=4, vel=.5)
