"""An autumn wood, low sun through the trees."""
import random
import c3d

rng = random.Random(4)
c3d.sky(sun_height=22, sun_turn=-150, haze=1.5, clouds=.3)
c3d.ground(size=3000, mat=c3d.field('#5a5430'), z=-1)
c3d.land(size=(500, 500), at=(0, 200, 0), height=2, mat=c3d.field('#5a5430'))
c3d.track([(0, -6), (1, 8), (-2, 20), (3, 34), (0, 55)], width=1.8)
c3d.fallen_leaves(size=(34, 60), at=(0, 22, 0), count=70000)
c3d.meadow(size=(50, 70), at=(0, 26, 0), near=(0, -3), blades=50000, colour='#7a6d3a')
for i in range(110):
    side = rng.choice((-1, 1))
    x, y = side * rng.uniform(3.5, 70), rng.uniform(3, 170)
    c3d.tree(at=(x, y, c3d.land_z(x, y)), height=rng.uniform(11, 17), seed=i, autumn=rng.uniform(.5, 1))
c3d.exposure(.8)
c3d.camera(at=(.2, -5, c3d.land_z(.2, -5) + 1.55), look=(.3, 30, 3.4), lens=30, blur=8, focus=(.5, 10, 1))
