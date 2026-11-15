"""What part.py imports: real parts with real dimensions, in millimetres. It runs inside Blender, whose exact boolean does the cutting.

    import cad
    plate = cad.box(60, 40, 4)
    plate = plate - cad.cylinder(5, 10).at(20, 10, 0)
    plate = plate.fillet(2)
    cad.part('bracket', plate, x=60, y=40, z=4)      # x y z: the sizes it must have, measured afterwards

A Shape is a mesh. + joins, - cuts, & keeps what overlaps. Shapes are centred on the origin unless told otherwise; Z is up.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

SEGMENTS = {'value': 96}
PARTS: list = []
EPS = 1e-6


class CadError(Exception):
    """A mistake in part.py, in words."""


def _mesh_from(build) -> bpy.types.Mesh:
    bm = bmesh.new()
    build(bm)
    me = bpy.data.meshes.new('shape')
    bm.to_mesh(me)
    bm.free()
    return me


class Shape:
    def __init__(self, mesh):
        self.mesh = mesh

    def _copy(self):
        return Shape(self.mesh.copy())

    def _with(self, matrix: Matrix) -> 'Shape':
        s = self._copy()
        s.mesh.transform(matrix)
        return s

    def at(self, x=0.0, y=0.0, z=0.0) -> 'Shape':
        """Moved by this much."""
        return self._with(Matrix.Translation((x, y, z)))

    def turn(self, x=0.0, y=0.0, z=0.0) -> 'Shape':
        """Turned around the origin, in degrees: x, then y, then z."""
        m = Matrix.Rotation(math.radians(z), 4, 'Z') @ Matrix.Rotation(math.radians(y), 4, 'Y') @ Matrix.Rotation(math.radians(x), 4, 'X')
        return self._with(m)

    def scaled(self, x=1.0, y=None, z=None) -> 'Shape':
        return self._with(Matrix.Diagonal((x, x if y is None else y, x if z is None else z, 1)))

    def mirror(self, axis='x') -> 'Shape':
        k = {'x': (-1, 1, 1, 1), 'y': (1, -1, 1, 1), 'z': (1, 1, -1, 1)}[axis]
        s = self._with(Matrix.Diagonal(k))
        s.mesh.flip_normals()
        return s

    def _boolean(self, other: 'Shape', op: str) -> 'Shape':
        a = bpy.data.objects.new('a', self.mesh.copy())
        b = bpy.data.objects.new('b', other.mesh)
        scene = bpy.context.scene.collection
        scene.objects.link(a)
        scene.objects.link(b)
        m = a.modifiers.new('cut', 'BOOLEAN')
        m.operation = op
        m.solver = 'EXACT'
        m.object = b
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        me = bpy.data.meshes.new_from_object(a.evaluated_get(depsgraph))
        scene.objects.unlink(a)
        scene.objects.unlink(b)
        return Shape(me)

    def __add__(self, other):
        return self._boolean(other, 'UNION')

    def __sub__(self, other):
        return self._boolean(other, 'DIFFERENCE')

    def __and__(self, other):
        return self._boolean(other, 'INTERSECT')

    def _edges(self, width: float, segments: int) -> 'Shape':
        o = bpy.data.objects.new('e', self.mesh.copy())
        scene = bpy.context.scene.collection
        scene.objects.link(o)
        m = o.modifiers.new('edge', 'BEVEL')
        m.width = width
        m.segments = segments
        m.limit_method = 'ANGLE'
        m.angle_limit = math.radians(30)
        m.harden_normals = False
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(depsgraph))
        scene.objects.unlink(o)
        return Shape(me)

    def fillet(self, radius: float) -> 'Shape':
        """Rounds every sharp edge."""
        return self._edges(radius, 6)

    def chamfer(self, size: float) -> 'Shape':
        """Cuts every sharp edge at 45 degrees."""
        return self._edges(size, 1)

    def on_bed(self) -> 'Shape':
        """Moved so that its lowest point is at z = 0."""
        low = min(v.co.z for v in self.mesh.vertices)
        return self.at(0, 0, -low)

    def repeat(self, count: int, x=0.0, y=0.0, z=0.0) -> 'Shape':
        """count copies, each moved by this much from the last, joined."""
        out = self
        for i in range(1, count):
            out = out + self.at(x * i, y * i, z * i)
        return out

    def around(self, count: int, radius: float = 0.0) -> 'Shape':
        """count copies evenly around Z. radius moves the shape out first."""
        first = self.at(radius, 0, 0)
        out = first
        for i in range(1, count):
            out = out + first.turn(z=360 * i / count)
        return out

    def bounds(self) -> tuple:
        co = [v.co for v in self.mesh.vertices]
        if not co:
            raise CadError('这个形状是空的：切掉的东西把它全切没了，或者两个形状根本没有碰到')
        lo = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
        hi = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
        return lo, hi


def segments(count: int) -> None:
    """How smooth round things are: 96 is good for printing."""
    SEGMENTS['value'] = int(count)


def box(x, y, z) -> Shape:
    def build(bm):
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((x, y, z, 1)))
    return Shape(_mesh_from(build))


def cylinder(d, h) -> Shape:
    """Standing on Z, centred."""
    return cone(d, d, h)


def cone(d1, d2, h) -> Shape:
    """d1 at the bottom, d2 at the top."""
    def build(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=SEGMENTS['value'], radius1=d1 / 2, radius2=d2 / 2, depth=h)
    return Shape(_mesh_from(build))


def sphere(d) -> Shape:
    def build(bm):
        bmesh.ops.create_uvsphere(bm, u_segments=SEGMENTS['value'], v_segments=SEGMENTS['value'] // 2, radius=d / 2)
    return Shape(_mesh_from(build))


def tube(outer, inner, h) -> Shape:
    if inner >= outer:
        raise CadError('管子的内径要小于外径')
    return cylinder(outer, h) - cylinder(inner, h + 2)


def prism(points, h) -> Shape:
    """A flat outline [(x, y), ...] raised h, from z = 0. Points go around once, in order."""
    def build(bm):
        verts = [bm.verts.new((x, y, 0)) for x, y in points]
        face = bm.faces.new(verts)
        bm.normal_update()
        if face.normal.z < 0:
            face.normal_flip()
        made = bmesh.ops.extrude_face_region(bm, geom=[face])
        moved = [v for v in made['geom'] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=moved, vec=(0, 0, h))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return Shape(_mesh_from(build))


def rounded_plate(x, y, z, radius) -> Shape:
    """A plate with rounded corners, centred, without rounding its top and bottom."""
    if radius * 2 > min(x, y):
        raise CadError('圆角半径太大')
    return (box(x - 2 * radius, y, z) + box(x, y - 2 * radius, z)
            + cylinder(2 * radius, z).at(x / 2 - radius, y / 2 - radius) + cylinder(2 * radius, z).at(radius - x / 2, y / 2 - radius)
            + cylinder(2 * radius, z).at(x / 2 - radius, radius - y / 2) + cylinder(2 * radius, z).at(radius - x / 2, radius - y / 2))


def hole(d, through=40.0, head=0.0, head_depth=0.0) -> Shape:
    """Something to cut away: a screw hole, with a wider head recess at the top when head is given. Its top is at z = 0."""
    s = cylinder(d, through).at(0, 0, -through / 2)
    if head:
        s = s + cylinder(head, head_depth + .01).at(0, 0, -head_depth / 2)
    return s


SCREWS = {'M2': (2.2, 3.8, 2), 'M2.5': (2.7, 4.5, 2.5), 'M3': (3.2, 5.5, 3), 'M4': (4.3, 7, 4), 'M5': (5.3, 8.5, 5), 'M6': (6.4, 10, 6)}


def screw_hole(size='M3', through=40.0) -> Shape:
    """A clearance hole and head recess for a socket-head screw. Its top is at z = 0."""
    if size not in SCREWS:
        raise CadError(f'没有 {size}。有：{", ".join(SCREWS)}')
    d, head, depth = SCREWS[size]
    return hole(d, through, head + .3, depth + .2)


def slot(length, d, h) -> Shape:
    """A long hole with round ends: a screw can slide in it. Centred."""
    middle = length - d
    return box(middle, d, h) + cylinder(d, h).at(middle / 2) + cylinder(d, h).at(-middle / 2)


def standoff(outer, hole, h) -> Shape:
    """A post for a circuit board: stands on z = 0."""
    return tube(outer, hole, h).at(0, 0, h / 2)


def gear(teeth=20, module=2.0, thick=6.0, hole=5.0) -> Shape:
    """A spur gear. Module is tooth size: two gears mesh when it is the same, their centres (teeth1 + teeth2) * module / 2 apart."""
    if teeth < 8:
        raise CadError('齿数太少')
    pitch = module * teeth / 2
    outer, root = pitch + module, pitch - 1.25 * module
    points = []
    for i in range(teeth):
        a = i / teeth * math.tau
        step = math.tau / teeth
        for frac, r in ((0, root), (.18, root), (.3, outer * .985), (.4, outer), (.6, outer), (.7, outer * .985), (.82, root)):
            t = a + frac * step
            points.append((r * math.cos(t), r * math.sin(t)))
    shape = prism(points, thick).at(0, 0, -thick / 2)
    return shape - cylinder(hole, thick + 2) if hole else shape


def enclosure(x, y, z, wall=2.0, radius=3.0) -> tuple:
    """An open box and a lid that fits inside it. Sizes are the outside. Returns (box, lid), each standing on z = 0, the lid with a lip and 0.2 mm of play."""
    outer = rounded_plate(x, y, z, radius).at(0, 0, z / 2)
    inner = rounded_plate(x - 2 * wall, y - 2 * wall, z, max(.5, radius - wall)).at(0, 0, z / 2 + wall)
    body = outer - inner
    plate = rounded_plate(x, y, wall, radius).at(0, 0, wall / 2)
    lip = rounded_plate(x - 2 * wall - .4, y - 2 * wall - .4, 3, max(.5, radius - wall)).at(0, 0, wall + 1.5)
    hollow = rounded_plate(x - 2 * wall - 3, y - 2 * wall - 3, 4, .5).at(0, 0, wall + 2.5)
    return body, (plate + lip) - hollow


def honeycomb(x, y, h, cell=8.0, wall=1.6) -> Shape:
    """A plate full of six-sided holes: strong, light, and air can pass."""
    plate = box(x, y, h)
    seg = SEGMENTS['value']
    SEGMENTS['value'] = 6
    hole = cylinder(cell, h + 2)
    SEGMENTS['value'] = seg
    dx, dy = (cell + wall) * .866, (cell + wall) * .75
    holes = None
    row = 0
    v = -y / 2 + cell
    while v < y / 2 - cell * .6:
        u = -x / 2 + cell + (dx / 2 if row % 2 else 0)
        while u < x / 2 - cell * .6:
            one = hole.at(u, v, 0)
            holes = one if holes is None else _gather(holes, one)
            u += dx
        v += dy
        row += 1
    if holes is None:
        raise CadError('板太小，放不下孔')
    return plate - holes


def _gather(a: Shape, b: Shape) -> Shape:
    """Two separate shapes as one mesh, with no boolean: many holes are then cut in one go."""
    bm = bmesh.new()
    bm.from_mesh(a.mesh)
    bm.from_mesh(b.mesh)
    me = bpy.data.meshes.new('many')
    bm.to_mesh(me)
    bm.free()
    return Shape(me)


def label(text: str, size=10.0, depth=1.0) -> Shape:
    """Raised letters, standing on z = 0: add them to a part, or subtract them to engrave."""
    curve = bpy.data.curves.new('text', 'FONT')
    curve.body = text
    curve.size = size
    curve.extrude = depth / 2
    curve.align_x, curve.align_y = 'CENTER', 'CENTER'
    for path in ('C:/Windows/Fonts/msyh.ttc', '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc'):  # Windows, then macOS
        try:
            curve.font = bpy.data.fonts.load(path)
            break
        except RuntimeError:
            continue
    o = bpy.data.objects.new('text', curve)
    scene = bpy.context.scene.collection
    scene.objects.link(o)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(depsgraph))
    scene.objects.unlink(o)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=.0005)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if not me.vertices:
        raise CadError(f'这些字画不出来：{text}')
    return Shape(me).at(0, 0, depth / 2)


def part(name: str, shape: Shape, material='PLA', x=None, y=None, z=None, tolerance=.05) -> None:
    """Keep a finished part: out/<name>.stl. x, y, z: the sizes it must measure, each checked after building."""
    PARTS.append({'name': name, 'shape': shape, 'material': material, 'want': {'x': x, 'y': y, 'z': z}, 'tolerance': tolerance})
