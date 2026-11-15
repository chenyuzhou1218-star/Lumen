"""A cottage in the snow, at the blue hour."""
import random
import c3d

rng = random.Random(3)
c3d.dusk(strength=.9, top='#2a3f6e', horizon='#b9a7b5')
c3d.ground(size=3000, mat='snow', z=-1)
c3d.land(size=(500, 460), at=(0, 170, 0), height=1.6, mat='snow')
c3d.mountains(y=620, height=260, snow=.25, forest='#3a4a58', rock='#7a7f8c')
x, y = -2, 16
c3d.cottage(at=(x, y, c3d.land_z(x, y)), turn=-8, lit=True, snow=.8)
c3d.fence([(-14, 7), (-4, 8), (6, 7), (14, 9)])
for i in range(46):
    side = rng.choice((-1, 1))
    px, py = side * rng.uniform(9, 70), rng.uniform(14, 90)
    c3d.pine(at=(px, py, c3d.land_z(px, py)), height=rng.uniform(9, 17), seed=i % 5, snow=.65)
c3d.treeline(y=110, depth=60, colour='#27323c', x=(-300, 300))
c3d.snowfall(at=(0, 8, 0), size=(26, 26, 9))
c3d.exposure(.5)
c3d.camera(at=(1, -5, c3d.land_z(1, -5) + 1.5), look=(-1, 20, 3), lens=35, blur=6, focus=(-2, 15, 2))
