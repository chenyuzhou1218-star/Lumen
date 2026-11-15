"""An old market street late in the afternoon: stalls with lanterns, barrels, a well, banners, a stone wall behind."""
import random
import c3d

rng = random.Random(5)
c3d.sky(sun_height=14, sun_turn=235)
c3d.ground(size=400, mat='concrete')
c3d.mountains(y=600, height=200, snow=.3)
c3d.stone_wall([(-16, 11), (16, 11)], height=2.6, thick=.8)
for i, x in enumerate((-4.2, -1.2, 1.8, 4.8)):
    y = 4.4 + rng.uniform(-.3, .3)
    c3d.market_stall(at=(x, y, 0), turn=rng.uniform(-6, 6), colour=('#8a2a22', '#2f5f7a', '#b07a2a', '#5a4a7a')[i])
    c3d.point(at=(x, y - .3, 1.9), power=35, colour=c3d.kelvin(2400), radius=.12, name='lantern')
c3d.well(at=(-2.8, 1.2, 0))
for x, y in ((-5.4, 2.4), (-4.9, 2.9), (3.6, 2.2)):
    c3d.barrel(at=(x, y, 0), turn=rng.uniform(0, 90))
for x, y in ((4.4, 2.6), (4.9, 2.1)):
    c3d.crate(at=(x, y, 0), turn=rng.uniform(0, 40), size=.6)
for x in (-7.5, 7.5):
    c3d.banner(at=(x, 8.5, 0), colour='#8a2a22', height=5.2)
c3d.cottage(at=(-12, 15, 0), size=(7, 5, 3), roof='#3a3632')
c3d.cottage(at=(11, 16, 0), turn=-6, size=(6, 5, 3), roof='#3a3632')
c3d.camera(at=(1.2, -3.2, 1.6), look=(-.6, 5, 1.3), lens=28, blur=3, focus=(-1, 3.5, 1))
