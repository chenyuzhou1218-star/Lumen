# Making a game with CodeGame

A project is a folder: `project.json`, `game.js`, `assets/`. `game.js` is one JavaScript file that talks to the global `G`. It runs inside an async function, so `await` works at the top. There are no libraries and no build tools: `build` puts everything in one web page.

Games are original. Never remake an existing game, its characters, names or look.

## The way of working

1. One sentence: what does the player do, what is the goal, how can they lose? A small game that is finished beats a big one that is not.
2. First a player that moves on ground, and the camera. `play` it, look at the picture.
3. Add the goal, then the danger, then the ending. `play` after each one.
4. Look at every picture from `play`. Read `played`: did the player move, did the score change?
5. Only then make it beautiful: sky, colours, models from Code3D, sounds from CodeSound.

A game that loads proves nothing. It is done when `play` reaches the goal or the player was seen to lose. Write your own steps for that (below). Say in your report what the machine player did and did not reach. Whether it is fun is for the user.

## G

```js
G.sky({top, horizon, below, sunHeight, sunTurn, sun, sunPower, ambient, fog, fogAmount})
G.ground({size, cells, height: (x, z) => y, tint: (x, z, y, slope) => '#rrggbb', color})
G.heightAt(x, z)     G.noise(x, z, seed)    // smooth -1..1

G.box(o)  G.ball(o)  G.cylinder(o)  G.cone(o)
// o: at [x,y,z], size number or [x,y,z], turn degrees, rot [pitch,yaw,roll], color, emit, glow, rough, metal, opacity, unlit, solid true, tag 'name'
await G.model('house.glb', {at, size, turn, solid})   // from assets/; the result has .copy({at}) for more of the same
await G.texture('wood.png')    // then node.mat.map = texture; node.mat.tile = 4

node.at(x, y, z)  node.pos  node.rot  node.size  node.visible  node.mat  node.tag('x')  node.remove()  node.solid()

G.walker(node, {speed, jump, gravity, radius, height})   // WASD or arrows relative to the camera, Space to jump, ground and solid things. node.pos is at its feet
G.follow(node, {distance, height, pitch, yaw, lock})     // lock: true, the mouse turns the camera after a click
G.lookFrom(eye, at)                                      // a fixed camera
G.camera.fov

G.update((dt) => {...})        // every frame; stops when the game has ended
G.after(2, fn)  G.every(.5, fn)
G.chaser(node, target, {speed, sight, reach, onReach, lift})     // walks after a target over the ground
G.shoot(from, dir, {speed, size, color, life, tag, hit})         // hit(thing) when it touches something with that tag
G.burst(at, {count, color, speed, life, size})                   // small things flying apart
G.bar('health', value, max, color)   G.minimap({enemy: '#f55', goal: '#5df'}, range)
G.save('best', n)  G.load('best', 0)                             // stays between plays
G.key('KeyW')  G.pressed('Space')  G.mouse.x .y .dx .dy .down .clicked
G.near(a, b, distance)  G.all('tag')  G.ray(from, dir, far, tag)  G.random(lo, hi)
G.V: add sub mul dot cross len norm dist lerp

G.show('score', '分数 3')  G.message('text', seconds)  G.end('你赢了')    // R restarts after an end
G.watch('score', n)        // a number the machine player sees: watch everything that matters
await G.sound('hit.wav', {volume, loop})
G.quality = .75            // lower for weak graphics chips
G.shadowReach = 34         // how far around the camera shadows reach
```

Same numbers every run: `G.random` always gives the same sequence, so that a bug comes back.

## play

`play` builds the game, runs it in the browser on this computer and presses keys. Steps go in a JSON file:

```json
[{"keys": [], "seconds": 1, "look": "start"}, {"keys": ["KeyW"], "seconds": 3}, {"keys": ["KeyW", "Space"], "seconds": .5, "look": "jump"}]
```

Each step reports the player's position, the watched numbers, whether the game ended, and the frame rate. `look` takes a picture. The browser draws in software here, so the frame rate is lower than on a real graphics chip.

## What makes it feel good

- The camera follows softly, the player is never lost in the picture, and the goal can be seen or is marked.
- Show what happened: a message, a sound, a score that changes at once.
- Things stand on the ground: `G.heightAt`.
- Colour tells what matters: goals glow (`emit`), dangers are red or dark.
- The user's computer has a weak graphics chip. Keep it to a few hundred things and `cells` under 150. Make many copies of one model rather than many models.

Write everything the person will read (titles, slide and page text, narration, labels) in the language they wrote to you in; use 中文 only when they did. The examples and theme names in this guide being 中文 is not a reason to answer in 中文.
