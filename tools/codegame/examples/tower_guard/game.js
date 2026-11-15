// Tower Guard: enemies come in waves for the tower. Space fires forward. Keep the tower's bar above zero.

G.sky({ top: '#27406f', horizon: '#e6a97c', below: '#6a5b4e', sunHeight: 18, sunTurn: 70, sun: '#ffc48c', sunPower: 3, ambient: '#7f8fb5', fogAmount: .009 });
const land = (x, z) => G.noise(x * .05, z * .05, 2.2) * 1.4;
G.ground({ size: 160, cells: 80, height: land, tint: (x, z, y, s) => (s > .1 ? '#6a6250' : y > .4 ? '#7d8a4e' : '#5d7d42') });

const tower = G.cylinder({ at: [0, land(0, 0) + 4, 0], size: [5, 8, 5], color: '#8d8a84', rough: .8, solid: true, tag: 'tower' });
G.cone({ at: [0, land(0, 0) + 10, 0], size: [7, 4, 7], color: '#7a3a2c' });
const hero = G.box({ at: [0, land(0, 8), 8], size: .01 });
hero.visible = false;
const body = G.cylinder({ size: [.7, 1.2, .7], color: '#3f6fd0', rough: .4 });
G.walker(hero, { speed: 9, jump: 8 });
G.follow(hero, { distance: 10, height: 1.5, pitch: 24, lock: true });
G.minimap({ enemy: '#ff6a55', tower: '#ffd27a' }, 60);

let health = 100, score = 0, wave = 0, facing = [0, 0, -1];
const best = G.load('best', 0);
G.show('score', `击退 0   最高 ${best}`);

function spawn() {
  wave += 1;
  G.message(`第 ${wave} 波`, 1.2);
  for (let i = 0; i < 2 + wave; i++) {
    const a = G.random(0, Math.PI * 2);
    const x = Math.cos(a) * 44;
    const z = Math.sin(a) * 44;
    const e = G.box({ at: [x, land(x, z) + 1, z], size: [1.3, 1.9, 1.3], color: '#55303a', rough: .7, tag: 'enemy' });
    G.chaser(e, tower, { speed: 2.4 + wave * .25, sight: 200, reach: 4.2, onReach: (n) => { n.remove(); health -= 10; G.burst(n.pos, { color: '#d05040' }); } });
  }
}
spawn();
G.every(11, spawn);

G.update((dt) => {
  const p = hero.pos;
  body.pos = [p[0], p[1] + .6, p[2]];
  const r = hero.rot[1] * Math.PI / 180;
  facing = [Math.sin(r), 0, Math.cos(r)];
  if (G.pressed('Space') || G.mouse.clicked) {
    G.shoot(G.V.add(p, [0, 1.2, 0]), facing, { tag: 'enemy', hit: (t) => { t.remove(); score += 1; G.burst(t.pos); G.show('score', `击退 ${score}   最高 ${Math.max(best, score)}`); } });
  }
  G.bar('tower', health, 100);
  G.watch('health', health);
  G.watch('score', score);
  G.watch('wave', wave);
  if (health <= 0) {
    G.save('best', Math.max(best, score));
    G.end(`塔倒了，击退 ${score} 个敌人`);
  }
});
