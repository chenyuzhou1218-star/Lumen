"""Every ready thing on one table, to see them."""
import c3d

c3d.studio(brightness=1)
c3d.ground(mat=c3d.material('floor', '#3a3836', rough=.5, vary=.2, scale=2))
y = 0
c3d.table(at=(0, 0, 0), size=(1.8, .9, .74))
t = .74
c3d.bottle(at=(-.7, .2, t), turn=20)
c3d.wine_glass(at=(-.55, -.05, t))
c3d.plate(at=(-.28, -.15, t))
c3d.apple(at=(-.27, -.15, t + .02))
c3d.vase(at=(-.1, .25, t), height=.26)
c3d.mug(at=(.08, -.18, t), turn=200, drink='coffee', colour='#2f4b5a')
c3d.laptop(at=(.42, .12, t), turn=-12)
c3d.desk_lamp(at=(.76, .22, t), turn=200)
c3d.chair(at=(-.3, -.75, 0), turn=175)
c3d.rock(at=(1.5, -.6, 0), size=.6, seed=3)
c3d.tree(at=(-2.4, 3.2, 0), height=3.2)
c3d.camera(at=(.2, -2.6, 1.5), look=(0, 0, .75), lens=40)
