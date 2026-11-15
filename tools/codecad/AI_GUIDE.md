# Making real parts with CodeCAD

A project is a folder: `project.json`, `part.py`. Lengths are millimetres, Z is up. This is for things that will exist: sizes are the point.

## The way of working

1. Write down the sizes that matter first, with what the part must fit: the phone is 8 mm thick, the screw is M3.
2. Put those in names at the top of `part.py`. Every other size follows from them. Never scatter numbers.
3. Give `cad.part` the sizes it must have (`x=`, `y=`, `z=`). They are measured after the build, not trusted.
4. `build`, then read every measured number and warning, and look at the picture. Fix and build again.

A part is done when it measures right, is one solid (`open_edges` 0, `separate_pieces` 1), and sits on the bed. Say in your report what was measured, and that nothing has been printed: only a real print proves fit.

## Designing for printing

- Parts that slide into each other need a gap: 0.2 to 0.3 mm per side. A 10 mm peg goes in a 10.5 mm hole.
- Walls at least 1.2 mm; 2 mm or more where it takes force.
- Lay it so that the flat side is on the bed and overhangs stay under 45 degrees. A hole across the print direction sags.
- Force along the layers is strong, across them weak: think which way it will break.
- Round inner corners with `fillet`: sharp ones crack first.
- Screw holes: `cad.screw_hole('M3')` already has the clearance.

## Writing

```python
import cad

PHONE = 9.0        # what must fit
GAP = .4
WALL = 3.0

base = cad.rounded_plate(80, 60, WALL, 6).at(0, 0, WALL / 2)
slot = cad.box(90, PHONE + GAP, 30).turn(x=-20).at(0, 5, 20)
part = (base + cad.box(70, 16, 22).at(0, 6, 12) - slot).on_bed()
cad.part('stand', part, material='PLA', x=80, y=60)
```

Ready parts: `cad.gear(teeth, module, thick, hole)`, `box_, lid = cad.enclosure(x, y, z, wall)`, `cad.honeycomb(x, y, h, cell)`, `cad.slot(length, d, h)`, `cad.standoff(outer, hole, h)`, `cad.label('文字', size, depth)`. The build also estimates print minutes, plastic and cost: they are estimates.

`+` joins, `-` cuts, `&` keeps the overlap. `.at()` moves, `.turn()` turns, `.fillet()` rounds edges, `.chamfer()` bevels, `.mirror()`, `.repeat()`, `.around()`, `.on_bed()`.

Things cut away must reach past the surface: a hole that ends exactly on a face leaves a skin.

`fillet` and `chamfer` take every sharp edge, so do them before cutting small holes, and keep the radius smaller than the shortest edge.

Each boolean takes time. Make all the holes first, join them into one, and cut once.

Materials for the weight: PLA PETG ABS TPU ALUMINIUM STEEL. `project.json` has the printer's size.
