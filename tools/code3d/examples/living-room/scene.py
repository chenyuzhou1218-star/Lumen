"""A living room in the afternoon."""
import c3d

c3d.sky(sun_height=24, sun_turn=-40, clouds=.3)
c3d.room(size=(5.4, 4.4, 2.7), colour='#e6dfd2', sill=.5, window_size=(3, 1.9), daylight=620)
c3d.garden_outside(y=3.1)
c3d.curtains(at=(0, 2.05, 2.55), width=3.3, height=2.3)
c3d.rug(at=(0, .3, 0), turn=2, size=(2.7, 1.9))
c3d.sofa(at=(-1.45, .35, 0), turn=-98 + 180)
c3d.coffee_table(at=(.1, .35, 0), turn=5, size=(1.1, .6, .42))
c3d.book(at=(.05, .3, .42), turn=20, colour='#22495c')
c3d.cup_and_saucer(at=(.32, .42, .42), turn=-30, drink='coffee', size=.9)
c3d.floor_lamp(at=(-2.1, 1.6, 0), power=9)
c3d.bookshelf(at=(2.3, 1.2, 0), turn=-90)
c3d.potted_plant(at=(1.75, 1.75, 0), height=1, leaves=30)
c3d.camera(at=(1.3, -1.9, 1.3), look=(-.35, .9, .7), lens=30, blur=5.6, focus=(.1, .35, .5))
