"""A set of sound effects for a game: buttons, money, battle and weather. Several seeds where a game plays a sound many times."""
import cs

fx = cs.fx()

for name in ('click', 'hover', 'confirm', 'cancel', 'error', 'notify', 'coin', 'level_up', 'jump', 'land', 'powerup', 'door'):
    cs.save(name, getattr(fx, name)())

for seed in range(3):
    cs.save(f'sword_{seed + 1}', fx.sword(seed=seed))
    cs.save(f'hit_{seed + 1}', fx.hit(seed=seed))
    cs.save(f'arrow_{seed + 1}', fx.arrow(seed=seed))
    cs.save(f'step_stone_{seed + 1}', fx.footstep('stone', seed=seed))
    cs.save(f'step_grass_{seed + 1}', fx.footstep('grass', seed=seed))

cs.save('shield', fx.shield())
cs.save('horse', fx.horse())
cs.save('war_horn', fx.horn_call())
cs.save('explosion_small', fx.explosion(size=.4))
cs.save('explosion_big', fx.explosion(size=1.6))
cs.save('thunder', fx.thunder())

cs.save('rain_loop', fx.rain(seconds=10, heavy=.6))
cs.save('wind_loop', fx.wind(seconds=10))
cs.save('fire_loop', fx.fire(seconds=8))
cs.save('sea_loop', fx.waves(seconds=12))
cs.save('battle_loop', fx.battle_crowd(seconds=8))
