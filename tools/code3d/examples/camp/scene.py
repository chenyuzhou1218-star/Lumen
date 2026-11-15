"""A camp under the stars."""
import random
import c3d

rng = random.Random(2)
c3d.night(moon=.7, turn=-60, height=35)
c3d.ground(size=3000, mat='grass', z=-1)
c3d.land(size=(420, 420), at=(0, 150, 0), height=1.6, mat=c3d.field('#3a4a30'))
c3d.mountains(y=560, height=240, snow=.5)
c3d.meadow(size=(44, 36), at=(0, 8, 0), near=(0, -3), blades=60000, height=.09)
x, y = -1.6, 6
c3d.tent(at=(x, y, c3d.land_z(x, y)), turn=20, glow=.9)
c3d.campfire(at=(1.3, 4, c3d.land_z(1.3, 4)), power=240)
for i in range(40):
    side = rng.choice((-1, 1))
    px, py = side * rng.uniform(7, 80), rng.uniform(9, 80)
    c3d.pine(at=(px, py, c3d.land_z(px, py)), height=rng.uniform(10, 18), seed=i % 5)
c3d.exposure(1.3)
c3d.camera(at=(1.5, -3.5, c3d.land_z(1.5, -3.5) + 1.3), look=(0, 20, 6), lens=24, blur=5.6, focus=(0, 5, .5))
