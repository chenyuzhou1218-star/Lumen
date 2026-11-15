"""A city street at night."""
import c3d

c3d.dusk(strength=.5, top='#16264a', horizon='#3f4c70')
c3d.city_street(length=120, night=True)
c3d.camera(at=(-3.2, -6, 1.6), look=(1, 40, 3), lens=32, blur=4, focus=(0, 14, 1))
