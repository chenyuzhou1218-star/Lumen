"""A palm on a beach, late morning."""
import c3d

c3d.sky(sun_height=42, sun_turn=-110, clouds=.35, seed=5)
c3d.beach(shore_y=10, colour='#ddcba4')
c3d.sea(shore_y=10, colour='#1f6a7c')
c3d.palm(at=(-3.6, 5, c3d.land_z(-3.6, 5)), height=8.5, lean=14)
c3d.palm(at=(-7.5, 3, c3d.land_z(-7.5, 3)), height=7, seed=4, lean=9)
c3d.camera(at=(1.6, -5, 1.5), look=(-.8, 12, 4.4), lens=22, blur=11, focus=(-3, 6, 2))
