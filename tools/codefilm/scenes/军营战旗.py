"""An army's camp at dawn: tents in rows, banners, a fire still burning, mountains behind."""
import random
import c3d

rng = random.Random(7)
c3d.sky(sun_height=6, sun_turn=100)
c3d.ground(size=3000, mat='grass', z=-1)
c3d.land(size=(420, 420), at=(0, 150, 0), height=1.4, mat=c3d.field('#55603e'))
c3d.mountains(y=520, height=260, snow=.45)
c3d.mist(y=140, height=18, amount=.8)
for row in range(3):
    for col in range(5):
        x, y = -10 + col * 5 + rng.uniform(-.5, .5), 8 + row * 6 + rng.uniform(-.5, .5)
        c3d.tent(at=(x, y, c3d.land_z(x, y)), turn=rng.uniform(-10, 10), colour=('#c9b48a', '#a8956a')[row % 2])
for x in (-12, -4, 4, 12):
    c3d.banner(at=(x, 5, c3d.land_z(x, 5)), height=5.5, colour='#7a1f1a')
c3d.campfire(at=(1, 3, c3d.land_z(1, 3)), power=180)
for i in range(16):
    px, py = rng.choice((-1, 1)) * rng.uniform(18, 70), rng.uniform(20, 90)
    c3d.pine(at=(px, py, c3d.land_z(px, py)), height=rng.uniform(10, 16), seed=i % 5)
c3d.camera(at=(2, -6, c3d.land_z(2, -6) + 1.7), look=(0, 25, 5), lens=26, blur=4, focus=(0, 8, 1))
