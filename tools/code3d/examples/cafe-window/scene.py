"""Rain-washed evening, a cafe window."""
import c3d

c3d.dusk(strength=1.3, top='#2c4f9a', horizon='#7f93b8')
c3d.room(size=(5, 3.6, 2.8), walls='plaster', colour='#d9cdb9', sill=.88, window_size=(3.2, 1.6), rain=1)
c3d.street_outside(y=2.2, z=-.3, lamps=.5, windows=.7)
y = 1.15
c3d.table(at=(0, y, 0), size=(1.1, .62, .74))
top = .74
c3d.cup_and_saucer(at=(.02, y - .1, top), turn=-30, size=.88)
c3d.book(at=(-.3, y + .02, top), turn=14, colour='#4a2f22')
c3d.potted_plant(at=(.36, y + .14, top), height=.3)
c3d.pendant_lamp(at=(-.1, y - .2, 2.8), drop=1.0, power=70)
c3d.camera(at=(.5, y - 1.45, 1.02), look=(.02, y + .2, .96), lens=42, blur=2.8, focus=(.02, y - .1, .78))
