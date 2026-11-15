"""Morning at a mountain lake."""
import c3d

c3d.sky(sun_height=9, sun_turn=95, haze=1.5, clouds=.45, seed=7)
c3d.ground(size=3000, mat='grass', z=-1.5)
c3d.land(size=(700, 560), at=(0, 200, 0), lake=(60, 170, 420, 190))
c3d.lake(at=(60, 170, 0), size=(420, 190), ripple=.3)
c3d.mountains(y=620, height=340)
c3d.treeline(y=268, depth=60)
c3d.mist(y=240, amount=.7)
c3d.meadow(size=(80, 70), at=(0, 22, 0), near=(0, -3))
for x, y, h, seed in ((-9, 18, 15, 2), (-15, 24, 18, 5), (-22, 22, 13, 3), (24, 44, 16, 4)):
    c3d.pine(at=(x, y, c3d.land_z(x, y)), height=h, seed=seed)
for i, (x, y, s) in enumerate(((.8, 3, .9), (-1.4, 5.5, .6), (3, 7, .7))):
    c3d.rock(at=(x, y, c3d.land_z(x, y)), size=s, seed=i + 1)
c3d.exposure(.2)
c3d.camera(at=(0, -3, c3d.land_z(0, -3) + 1.5), look=(.5, 30, 6), lens=28, blur=11, focus=(.8, 12, 1))
