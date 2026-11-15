"""A still life by a north window: fruit, bread, wine on linen."""
import c3d

c3d.room(size=(4, 3.4, 2.7), colour='#55504a', sill=.9, window_size=(1.2, 1.3), daylight=380)
c3d.sky(sun_height=40, sun_turn=120, clouds=.8)
y = 1.0
c3d.table(at=(0, y, 0), size=(1.5, .9, .78))
top = .78
c3d.cloth(at=(-.05, y - .05, top), size=(1.15, .72))
t = top + .004
c3d.bread(at=(-.34, y - .12, t), turn=24)
c3d.bowl(at=(.12, y + .04, t), radius=.15)
c3d.apple(at=(.05, y + .06, t + .03), turn=30)
c3d.orange(at=(.16, y + .0, t + .03), radius=.042)
c3d.pear(at=(.2, y + .1, t + .04), turn=100, lean=30)
c3d.orange(at=(.36, y - .18, t), radius=.036, colour='#e6c63a')
c3d.bottle(at=(-.06, y + .22, t), turn=20)
c3d.wine_glass(at=(.34, y + .08, t))
c3d.camera(at=(.12, y - 1.25, 1.05), look=(0, y, .88), lens=50, blur=4, focus=(0, y - .05, .85))
