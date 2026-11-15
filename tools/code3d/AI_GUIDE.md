# Making 3D with Code3D

A project is a folder: `project.json` and `scene.py` (Python run inside Blender). Lengths are metres, Z is up.

## The way of working, always in this order

1. Read this and the kit below. Prefer the ready things: `mug`, `cup_and_saucer`, `plate`, `bowl`, `apple`, `orange`, `pear`, `bread`, `cloth`, `bottle`, `wine_glass`, `vase`, `book`, `potted_plant`, `laptop`,
   `table`, `coffee_table`, `chair`, `sofa`, `rug`, `bookshelf`, `floor_lamp`, `curtains`, `picture`, `desk_lamp`, `pendant_lamp`, `room`, `garden_outside`, `street_outside`, `rock`, `tree`, `pine`, `treeline`, `city_street`, `building`, `car`, `cottage`, `fence`, `snowfall`, `boat`, `tent`, `campfire`, `palm`, `barrel`, `crate`, `bench`, `lamp_post`, `well`, `stone_wall`, `banner`, `market_stall`, `land`, `track`, `fallen_leaves`, `meadow`, `hills`, `mountains`, `lake`, `sea`, `beach`, `mist`. Never write your own terrain, mountains or water: if these cannot do what you need, say so in your report. They already have the curves and details a box never will.
2. Write a first scene with the main things in place. Render `quality=check` at once (seconds). Do this before adding detail.
3. LOOK at the picture. Say to yourself what is wrong, as a photographer would. Fix the biggest thing. Render again. Repeat at least three times.
4. Read the notes that come with a render (too dark, orange, floating, out of frame): they are measured, take them seriously.
5. Check other sides with `views` before you call it done. Then `quality=draft`, then `quality=final` once, then export.

Never export or render final a scene you have not looked at: it is refused anyway. A scene is finished when the picture looks right, not when the code runs.

## What makes a picture look real

- **One idea.** One subject, placed off centre. Empty space is fine. A catalogue line-up of objects looks fake.
- **Light first.** One main light with a colour, one weak fill of the opposite colour. Warm room: `c3d.kelvin(3300)`, not orange; cold sky through the window: `c3d.dusk`, `room(daylight=...)`.
- **Never pure black or pure white.** Windows at dusk are blue, not black.
- **Lens.** Eye height, 35 to 60 mm. `camera(blur=2, focus=the subject)` with the background far away is the cheapest way to a photograph.
- **Real sizes.** A mug is 9 cm, a table top 75 cm from the floor, a door 2 m. Wrong sizes are what the eye catches first.
- **Things touch.** Cups stand on tables, nothing floats, nothing sinks.
- **Shadows come from light, never from paint.** Do not lay dark discs or slabs under things. If a shadow is weak, the lamp is too far, too weak or too flat: move it nearer the subject, to one side.
- **The subject is the brightest thing that is not a lamp.** To make a window look bluer, make the sky bluer. Do not dim the room: a dim table is the commonest fault.
- **Use the kit's own settings.** `street_outside(lamps=.4, windows=.5)`, `room(rain=1)`, `cup_and_saucer(size=.85)`, `book(colour=, worn=)`. Do not reach into parts with `bpy` or loops over `bpy.data`: if a thing cannot be changed, say so in your report.
- **Water on glass:** `room(rain=1)`. Spheres on a pane look like marbles.
- **Variation.** Materials from `c3d.preset`, not flat colours. A little disorder: things turned a few degrees, not lined up.

## Recipes

Evening room with a street outside:

```python
c3d.dusk(strength=1.3, top='#2c4f9a', horizon='#7f93b8')
c3d.room(size=(5, 3.6, 2.8), colour='#d9cdb9', sill=.88, window_size=(3.2, 1.6), rain=1)
c3d.street_outside(y=2.2, z=-.3, lamps=.5, windows=.7)
c3d.table(at=(0, 1.15, 0), size=(1.1, .62, .74))
c3d.pendant_lamp(at=(-.1, .95, 2.8), drop=1.0, power=70)
c3d.camera(at=(.5, -.3, 1.02), look=(.02, 1.35, .96), lens=42, blur=2.8, focus=(.02, 1.05, .78))
```

A room by day:

```python
c3d.sky(sun_height=28, sun_turn=-30, clouds=.3)
c3d.room(size=(4.5, 3.6, 2.7), colour='#ece6da', sill=.9, window_size=(2.6, 1.5), daylight=480)
c3d.garden_outside(y=2.6)
c3d.table(at=(0, .9, 0), size=(1.3, .8, .75))
c3d.camera(at=(.55, -.4, 1.25), look=(0, .9, .84), lens=40, blur=2.8, focus=(.05, .8, .78))
```

Furniture stands with its front towards -Y before it is turned: `turn=180` faces +Y, `turn=90` faces +X. Look at a `views` top picture to check a sofa faces the room.

Product on a plain background: `c3d.studio()`, a dark `c3d.ground`, camera a little above, 85 mm.

Outdoors, the things at the back do most of the work:

```python
c3d.sky(sun_height=16, sun_turn=125, clouds=.45)
c3d.ground(size=3000, mat='grass', z=-1.5)        # far below: only the very far plain
c3d.land(size=(700, 560), at=(0, 200, 0), lake=(60, 150, 360, 170))   # rolling ground with a real shore
c3d.lake(at=(60, 150, 0), size=(360, 170), ripple=.4)   # same place and size as in land
c3d.hills(y=520, height=70)                       # low wooded hills behind the water
c3d.mountains(y=800, height=320)                  # or a real range: rock, forest, snow
c3d.treeline(y=250)                               # dark forest on the far shore: hides the seam of water and hills
c3d.mist(y=260)                                   # morning: low soft banks over the water
c3d.meadow(size=(60, 60), at=(0, 12, 0), near=(0, -3))   # all of the foreground, never a patch
x, y = -6, 14
c3d.tree(at=(x, y, c3d.land_z(x, y)), height=11)
c3d.rock(at=(.8, 3, c3d.land_z(.8, 3)), size=.9)
c3d.camera(at=(0, -3, 1.5), look=(.5, 20, 2.4), lens=35, blur=11, focus=(.8, 12, 1))   # f/11: a landscape is sharp to the mountains
```

The seaside: `c3d.sky(sun_height=5, sun_turn=20, clouds=.4)`, `c3d.beach(shore_y=10)`, `c3d.sea(shore_y=10)`, rocks on `c3d.land_z`, camera low at `(0, -5, 1.6)`, 30 mm, `blur=11`.

A wood in autumn: `c3d.land(...)`, `c3d.track([(0, -6), (1, 8), (-2, 20), (3, 34)])`, `c3d.fallen_leaves(...)`, then a hundred `c3d.tree(at=(x, y, c3d.land_z(x, y)), seed=i, autumn=.8)` right to the back: six shapes are shared, so it stays light. With the sun behind the camera the leaves show their colour; against the sun they glow.

A city street: `c3d.sky(sun_height=38, sun_turn=-60, clouds=.3)`, `c3d.exposure(.8)`, `c3d.city_street(length=120)`, camera on the pavement at `(-3.2, -6, 1.6)` looking along +Y, 32 mm, `blur=8`. At night: `c3d.dusk(strength=.5, top='#16264a', horizon='#3f4c70')` and `night=True`. One at a time: `c3d.building`, `c3d.car`.

Winter at the blue hour: `c3d.dusk(strength=.9, top='#2a3f6e', horizon='#b9a7b5')`, `c3d.ground(size=3000, mat='snow', z=-1)`, `c3d.land(..., mat='snow')`, `c3d.cottage(at=..., lit=True, snow=.8)`, `c3d.pine(..., snow=.65)`, `c3d.snowfall()`, `c3d.exposure(.5)`.

A night outdoors: `c3d.night(moon=.6)` for stars and moonlight, `c3d.campfire(...)` for warm light, `c3d.exposure(1)`.

Use `c3d.lake` for water: its surface has no edge to catch a dark line, `ripple=0` is a mirror. Keep the sun itself out of the frame, or it is a hard white dot: light from it, do not show it.

## Limits

`scene.py` builds the scene and nothing else: no programs, no network, no native code, no files outside the project. `final` stops after `max_seconds` in project.json (300 by default): keep it at 1280 x 720 on this computer.
