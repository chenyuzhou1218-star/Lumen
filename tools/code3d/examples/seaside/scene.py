"""Evening on a beach."""
import c3d

c3d.sky(sun_height=5, sun_turn=20, haze=1.4, clouds=.4, seed=3)
c3d.beach(shore_y=10)
c3d.sea(shore_y=10)
c3d.boat(at=(-.6, 3.2, c3d.land_z(-.6, 3.2)), turn=28)
for i, (x, y, s) in enumerate(((-5, 5, 1.3), (-3.6, 7, .6), (3.2, 7.5, .8))):
    c3d.rock(at=(x, y, c3d.land_z(x, y) - s * .1), size=s, seed=i + 1)
c3d.camera(at=(1.6, -4, 1.5), look=(-.2, 12, 1.2), lens=32, blur=8, focus=(-.6, 3, .4))
