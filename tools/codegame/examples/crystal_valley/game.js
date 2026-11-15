// Crystal Valley: collect every crystal before the night comes. Keep away from the stone wardens.
// Written in the same way any game here is written: one file that talks to G.

G.sky({ top: '#3a6fc0', horizon: '#f2d7b0', below: '#7d7464', sunHeight: 36, sunTurn: 40, sun: '#ffe6c4', sunPower: 3.2, ambient: '#90a7cf', fogAmount: .006 });

const hills = (x, z) => {
  const edge = Math.max(0, Math.hypot(x, z) - 60) * .35;   // the valley rises at its rim, so that nobody walks out of it
  return G.noise(x * .035, z * .035, 1.3) * 5 + G.noise(x * .12, z * .12, 4.2) * .9 + edge;
};
G.ground({
  size: 220, cells: 130, height: hills,
  tint: (x, z, y, slope) => (slope > .13 ? '#7c7468' : y > 5 ? '#8a9a58' : y < -2 ? '#4f7e45' : '#65914a'),
});

const place = (x, z, lift = 0) => [x, hills(x, z) + lift, z];

// trees: a trunk and two cones
for (let i = 0; i < 60; i++) {
  const x = G.random(-58, 58);
  const z = G.random(-58, 58);
  if (Math.hypot(x, z) < 8) continue;
  const tall = G.random(3.2, 5.6);
  G.cylinder({ at: place(x, z, tall * .2), size: [.42, tall * .45, .42], color: '#5b4231', solid: true });
  G.cone({ at: place(x, z, tall * .6), size: [tall * .62, tall * .62, tall * .62], color: '#2f5f3a' });
  G.cone({ at: place(x, z, tall * .92), size: [tall * .45, tall * .5, tall * .45], color: '#3a7044' });
}

// rocks
for (let i = 0; i < 26; i++) {
  const s = G.random(1, 2.8);
  G.box({ at: place(G.random(-55, 55), G.random(-55, 55), s * .3), size: [s, s * .8, s * 1.1], rot: [G.random(-14, 14), G.random(0, 360), G.random(-14, 14)], color: '#807a70', solid: true });
}

// the hero
const hero = G.box({ at: place(0, 0), size: [.01, .01, .01], color: '#000000' });
hero.visible = false;
const body = G.cylinder({ size: [.68, 1.1, .68], color: '#c44b3a', rough: .5 });
const head = G.ball({ size: .54, color: '#f0c7a4', rough: .6 });
const hood = G.cone({ size: [.72, .52, .72], color: '#8d2f25' });
const me = G.walker(hero, { speed: 7.5, jump: 8 });
G.follow(hero, { distance: 9, height: 1.3, pitch: 20, lock: true });

// crystals
const TOTAL = 12;
for (let i = 0; i < TOTAL; i++) {
  const a = i / TOTAL * Math.PI * 2 + G.random(-.2, .2);
  const r = G.random(16, 50);
  const x = Math.cos(a) * r;
  const z = Math.sin(a) * r;
  const c = G.cone({ at: place(x, z, 1.2), size: [.7, 1.5, .7], color: '#7fe6ff', emit: '#2aa8e0', glow: .7, rough: .15, tag: 'crystal' });
  c.base = c.pos[1];
}

// the wardens wander, and come for you when you are close
for (let i = 0; i < 5; i++) {
  const a = i / 5 * Math.PI * 2;
  const w = G.box({ at: place(Math.cos(a) * 34, Math.sin(a) * 34, 1), size: [1.5, 2, 1.5], color: '#4d4a55', rough: .85, tag: 'warden' });
  w.way = G.random(0, Math.PI * 2);
  G.ball({ at: w.pos, size: .34, color: '#ff5a2e', emit: '#ff5a2e', glow: 2, tag: 'eye' }).of = w;
}

let found = 0;
let daylight = 150;
G.show('crystals', `水晶 0 / ${TOTAL}`);

G.update((dt) => {
  const p = hero.pos;
  body.pos = [p[0], p[1] + .55, p[2]];
  head.pos = [p[0], p[1] + 1.32, p[2]];
  hood.pos = [p[0], p[1] + 1.7, p[2]];
  daylight -= dt;
  G.show('time', `天黑还有 ${Math.ceil(daylight)} 秒`);
  G.watch('crystals', found);
  G.watch('daylight', Math.round(daylight));

  for (const c of G.all('crystal')) {
    c.rot[1] += 70 * dt;
    c.pos[1] = c.base + Math.sin(G.time * 2) * .18;
    if (G.near(c, [p[0], p[1] + 1, p[2]], 1.6)) {
      c.remove();
      found += 1;
      G.show('crystals', `水晶 ${found} / ${TOTAL}`);
      G.message(`还差 ${TOTAL - found} 颗`, 1.2);
    }
  }
  for (const w of G.all('warden')) {
    const d = G.V.dist(w.pos, p);
    if (d < 16) {
      w.way = Math.atan2(p[0] - w.pos[0], p[2] - w.pos[2]);
    } else if (G.random() < .01) {
      w.way += G.random(-1.2, 1.2);
    }
    const speed = d < 16 ? 5.2 : 2;
    w.pos[0] += Math.sin(w.way) * speed * dt;
    w.pos[2] += Math.cos(w.way) * speed * dt;
    w.pos[1] = hills(w.pos[0], w.pos[2]) + 1;
    w.rot[1] = w.way * 180 / Math.PI;
    if (d < 1.7) G.end('被石卫士抓住了');
  }
  for (const e of G.all('eye')) e.pos = [e.of.pos[0], e.of.pos[1] + .55, e.of.pos[2]];

  if (found === TOTAL) G.end('你找到了所有水晶！');
  else if (daylight <= 0) G.end('天黑了');
});
