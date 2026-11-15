"""c3d: the short way to write a 3D scene for Blender. It runs inside Blender, next to scene.py.

A scene can use bpy directly; this kit is what makes a few lines look real: physically based materials with variation
in them (nothing in the real world is one flat colour), a physical sky, bevels on hard edges, a real camera. Lengths
are metres, colours are '#rrggbb', angles are degrees.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Euler, Vector


# --- materials -------------------------------------------------------------------------------------------------------

def _rgba(colour) -> tuple:
    if isinstance(colour, str):
        h = colour.lstrip('#')
        if len(h) != 6:
            raise ValueError(f"colour must be '#rrggbb', not {colour!r}")
        srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in srgb]
        return (*linear, 1.0)
    return (*tuple(colour)[:3], 1.0)


def _socket(node, *names):
    """Blender renames sockets between versions: the first name it knows."""
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    raise KeyError(names[0])


def material(name: str = 'material', colour='#b0b0b0', metal: float = 0, rough: float = .5, glass: float = 0, ior: float = 1.45,
             glow=None, glow_strength: float = 1, vary: float = 0, bump: float = 0, scale: float = 6, coat: float = 0,
             soft: float = 0) -> bpy.types.Material:
    """A physically based material. metal 0..1, rough 0 (mirror)..1, glass 0..1 (see-through), glow a colour that gives
    light. vary 0..1 mottles colour and roughness, bump 0..1 adds a fine surface relief; scale is the size of both.
    coat 0..1 is a clear glaze over it (ceramic, varnish, car paint). soft 0..1 lets light into it (wax, skin, leaves, milk)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value = _rgba(colour)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    p.inputs['IOR'].default_value = ior
    _socket(p, 'Transmission Weight', 'Transmission').default_value = glass
    if coat:
        _socket(p, 'Coat Weight', 'Clearcoat').default_value = coat
    if soft:
        _socket(p, 'Subsurface Weight', 'Subsurface').default_value = soft
    if glow:
        _socket(p, 'Emission Color', 'Emission').default_value = _rgba(glow)
        _socket(p, 'Emission Strength').default_value = glow_strength
    if vary or bump:
        coord = nt.nodes.new('ShaderNodeTexCoord')
        noise = nt.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = scale
        noise.inputs['Detail'].default_value = 8
        nt.links.new(coord.outputs['Object'], noise.inputs['Vector'])
        if vary:
            ramp = nt.nodes.new('ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].position = .3
            ramp.color_ramp.elements[1].position = .7
            base = _rgba(colour)
            ramp.color_ramp.elements[0].color = (*[c * (1 - .5 * vary) for c in base[:3]], 1)
            ramp.color_ramp.elements[1].color = (*[min(1, c * (1 + .3 * vary)) for c in base[:3]], 1)
            nt.links.new(noise.outputs[0], ramp.inputs['Fac'])
            nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
            rmap = nt.nodes.new('ShaderNodeMapRange')
            rmap.inputs['To Min'].default_value = max(0, rough - .15 * vary)
            rmap.inputs['To Max'].default_value = min(1, rough + .15 * vary)
            nt.links.new(noise.outputs[0], rmap.inputs['Value'])
            nt.links.new(rmap.outputs[0], p.inputs['Roughness'])
        if bump:
            fine = nt.nodes.new('ShaderNodeTexNoise')
            fine.inputs['Scale'].default_value = scale * 12
            fine.inputs['Detail'].default_value = 10
            nt.links.new(coord.outputs['Object'], fine.inputs['Vector'])
            b = nt.nodes.new('ShaderNodeBump')
            b.inputs['Strength'].default_value = min(1, bump)
            b.inputs['Distance'].default_value = .02
            nt.links.new(fine.outputs[0], b.inputs['Height'])
            nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return mat


PRESETS = {
    'steel': dict(colour='#8f9296', metal=1, rough=.32, vary=.25, bump=.04, scale=30),
    'aluminium': dict(colour='#c9cbcf', metal=1, rough=.38, vary=.2, bump=.04, scale=40),
    'gold': dict(colour='#e6b84f', metal=1, rough=.22, vary=.2, scale=20),
    'copper': dict(colour='#c8754b', metal=1, rough=.28, vary=.3, scale=20),
    'iron': dict(colour='#3a3a3c', metal=1, rough=.6, vary=.6, bump=.25, scale=12),
    'plastic': dict(colour='#d4d4d4', rough=.38, vary=.08, bump=.02, scale=60),
    'rubber': dict(colour='#1c1c1e', rough=.82, vary=.2, bump=.1, scale=50),
    'paint': dict(colour='#b03030', rough=.28, vary=.06, scale=40),
    'glass': dict(colour='#ffffff', rough=.02, glass=1, ior=1.5),
    'water': dict(colour='#dfeff0', rough=.04, glass=1, ior=1.33, bump=.08, scale=3),
    'concrete': dict(colour='#8d8b86', rough=.78, vary=.22, bump=.12, scale=2),
    'stone': dict(colour='#77736c', rough=.85, vary=.9, bump=.9, scale=5),
    'marble': dict(colour='#e6e3dd', rough=.18, vary=.35, scale=3),
    'sand': dict(colour='#c2a878', rough=.95, vary=.5, bump=.9, scale=20),
    'soil': dict(colour='#4a3a2b', rough=.95, vary=.9, bump=1, scale=6),
    'fabric': dict(colour='#6d7480', rough=.92, vary=.3, bump=.6, scale=90),
    'leather': dict(colour='#5a3a26', rough=.5, vary=.4, bump=.5, scale=40),
    'skin': dict(colour='#d6a58c', rough=.45, vary=.2, bump=.1, scale=30),
    'porcelain': dict(colour='#f3efe7', rough=.16, coat=.8, soft=.15, vary=.04, scale=30),
    'ceramic': dict(colour='#c9b8a3', rough=.3, coat=.5, vary=.25, bump=.06, scale=25),
    'terracotta': dict(colour='#a95c38', rough=.82, vary=.22, bump=.3, scale=70),
    'brass': dict(colour='#b08a4a', metal=1, rough=.28, vary=.3, bump=.04, scale=25),
    'plaster': dict(colour='#e6dfd2', rough=.85, vary=.1, bump=.12, scale=5),
    'paper': dict(colour='#ece3cf', rough=.75, vary=.12, bump=.1, scale=60),
    'snow': dict(colour='#eef2f7', rough=.6, vary=.08, bump=.5, scale=3, soft=.5),
    'asphalt': dict(colour='#2b2d30', rough=.2, vary=.5, bump=.3, scale=6),
    'leaf': dict(colour='#3f6f2f', rough=.42, vary=.5, bump=.1, scale=12, soft=.3, coat=.25),
}


def preset(name: str, colour=None, **change) -> bpy.types.Material:
    """A ready material with the variation of the real thing: steel aluminium gold copper iron plastic rubber paint glass
    water concrete stone marble sand soil grass fabric leather skin wood. colour and any field of material() can change."""
    if name == 'wood':
        return wood(colour or '#80634a', **change)
    if name == 'grass':
        return field(colour or '#4c6a2c')
    if name not in PRESETS:
        raise ValueError(f"no preset {name!r}; there are: wood, {', '.join(PRESETS)}")
    args = {**PRESETS[name], **change}
    if colour:
        args['colour'] = colour
    return material(name, **args)


def wood(colour='#80634a', rough: float = .42, scale: float = 5) -> bpy.types.Material:
    """Wood: wandering grain lines along the object's X axis, fine pores over them, under a thin satin finish. scale: bigger
    is finer grain (3 for a table top, 10 for small things)."""
    mat = material('wood', colour, rough=rough, coat=.15)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')

    def squeezed(x, y):
        m = nt.nodes.new('ShaderNodeMapping')
        m.inputs['Scale'].default_value = (x, y, y)
        nt.links.new(coord.outputs['Object'], m.inputs['Vector'])
        return m.outputs[0]

    lines = nt.nodes.new('ShaderNodeTexWave')
    lines.wave_type, lines.bands_direction = 'BANDS', 'Y'
    lines.inputs['Scale'].default_value = scale * 1.1
    lines.inputs['Distortion'].default_value = 16
    lines.inputs['Detail'].default_value = 4
    lines.inputs['Detail Scale'].default_value = .9
    lines.inputs['Detail Roughness'].default_value = .62
    nt.links.new(squeezed(.16, 1), lines.inputs['Vector'])
    tone = nt.nodes.new('ShaderNodeTexNoise')  # boards are lighter and darker in long patches
    tone.inputs['Scale'].default_value = scale * .5
    tone.inputs['Detail'].default_value = 3
    nt.links.new(squeezed(.25, 1), tone.inputs['Vector'])
    pores = nt.nodes.new('ShaderNodeTexNoise')
    pores.inputs['Scale'].default_value = scale * 30
    pores.inputs['Detail'].default_value = 3
    nt.links.new(squeezed(.05, 1), pores.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = .1, .9
    base = _rgba(colour)
    ramp.color_ramp.elements[0].color = (*[c * .74 for c in base[:3]], 1)
    ramp.color_ramp.elements[1].color = (*[min(1, c * 1.14) for c in base[:3]], 1)
    nt.links.new(lines.outputs[0], ramp.inputs['Fac'])
    patch = nt.nodes.new('ShaderNodeMix')
    patch.data_type, patch.blend_type = 'RGBA', 'MULTIPLY'
    patch.inputs['Factor'].default_value = .5
    nt.links.new(ramp.outputs['Color'], patch.inputs['A'])
    nt.links.new(tone.outputs[0], patch.inputs['B'])
    fine = nt.nodes.new('ShaderNodeMix')
    fine.data_type, fine.blend_type = 'RGBA', 'MULTIPLY'
    fine.inputs['Factor'].default_value = .35
    nt.links.new(patch.outputs['Result'], fine.inputs['A'])
    nt.links.new(pores.outputs[0], fine.inputs['B'])
    nt.links.new(fine.outputs['Result'], p.inputs['Base Color'])
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = .12
    b.inputs['Distance'].default_value = .003
    nt.links.new(pores.outputs[0], b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return mat


def field(colour='#4c6a2c') -> bpy.types.Material:
    """Ground under grass, seen from far: broad patches of darker green and drier straw, never one flat colour."""
    mat = material('field', colour, rough=.9)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    base = _rgba(colour)
    last = None
    for scale, dark, light in ((.035, .62, 1.3), (.3, .78, 1.2), (3, .8, 1.15)):
        noise = nt.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = scale
        noise.inputs['Detail'].default_value = 6
        nt.links.new(coord.outputs['Object'], noise.inputs['Vector'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = .36, .64
        ramp.color_ramp.elements[0].color = (dark, dark, dark * .95, 1)
        ramp.color_ramp.elements[1].color = (light * 1.1, light, light * .75, 1)
        nt.links.new(noise.outputs[0], ramp.inputs['Fac'])
        mix = nt.nodes.new('ShaderNodeMixRGB')
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1
        if last is None:
            mix.inputs[1].default_value = base
        else:
            nt.links.new(last.outputs[0], mix.inputs[1])
        nt.links.new(ramp.outputs['Color'], mix.inputs[2])
        last = mix
    nt.links.new(last.outputs[0], p.inputs['Base Color'])
    fine = nt.nodes.new('ShaderNodeTexNoise')  # close up: short turf, not felt
    fine.inputs['Scale'].default_value = 140
    fine.inputs['Detail'].default_value = 8
    nt.links.new(coord.outputs['Object'], fine.inputs['Vector'])
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = 1
    b.inputs['Distance'].default_value = .05
    nt.links.new(fine.outputs[0], b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return mat


def boards(colour='#7a5230', width: float = .14, rough: float = .38) -> bpy.types.Material:
    """Floorboards: the wood above laid in staggered planks with thin dark gaps. Use it on a floor (the planks run along X)."""
    mat = wood(colour, rough=rough, scale=4)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    source = p.inputs['Base Color'].links[0].from_socket
    coord = nt.nodes.new('ShaderNodeTexCoord')
    brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.offset = .4
    brick.inputs['Color1'].default_value = (1, 1, 1, 1)
    brick.inputs['Color2'].default_value = (.72, .68, .62, 1)
    brick.inputs['Mortar'].default_value = (.02, .015, .01, 1)
    brick.inputs['Scale'].default_value = 1
    brick.inputs['Mortar Size'].default_value = .0018
    brick.inputs['Mortar Smooth'].default_value = .1
    brick.inputs['Brick Width'].default_value = 1.3
    brick.inputs['Row Height'].default_value = width
    nt.links.new(coord.outputs['Object'], brick.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type, mix.blend_type = 'RGBA', 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1
    nt.links.new(source, mix.inputs['A'])
    nt.links.new(brick.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], p.inputs['Base Color'])
    return mat


def apply(obj, mat) -> None:
    """Give an object a material, in place of what it had: a Material, or a preset's name."""
    if isinstance(mat, str):
        mat = preset(mat)
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# --- shapes ----------------------------------------------------------------------------------------------------------

def _finish(obj, name, at, rot, mat, smooth_it=False):
    if name:
        obj.name = name
    obj.location = at
    obj.rotation_euler = Euler([math.radians(a) for a in rot])
    if smooth_it:
        smooth(obj)
    if mat is not None:
        apply(obj, mat)
    return obj


def _new(mesh_maker, name: str) -> bpy.types.Object:
    """An object from bmesh, without bpy.ops: a scene of hundreds of parts builds in seconds, not half a minute."""
    bm = bmesh.new()
    mesh_maker(bm)
    mesh = bpy.data.meshes.new(name or 'shape')
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name or 'shape', mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _smooth_sides(obj) -> None:
    """Round sides, flat ends."""
    for poly in obj.data.polygons:
        poly.use_smooth = abs(poly.normal.z) < .5


def box(size=(1, 1, 1), at=(0, 0, 0), rot=(0, 0, 0), mat=None, bevel_width: float = .004, name: str = '') -> bpy.types.Object:
    """A box of size (x, y, z) metres, centred on `at`. Real edges are never razor sharp: it gets a small bevel."""
    if isinstance(size, (int, float)):
        size = (size, size, size)
    obj = _new(lambda bm: bmesh.ops.scale(bm, vec=size, verts=bmesh.ops.create_cube(bm, size=1)['verts']), name)
    if bevel_width:
        bevel(obj, bevel_width)
    return _finish(obj, name, at, rot, mat)


def sphere(radius: float = .5, at=(0, 0, 0), rot=(0, 0, 0), mat=None, name: str = '') -> bpy.types.Object:
    """A smooth sphere."""
    obj = _new(lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=radius), name)
    obj.data.polygons.foreach_set('use_smooth', [True] * len(obj.data.polygons))
    return _finish(obj, name, at, rot, mat)


def _cone(radius, top, height, sides, name):
    return _new(lambda bm: bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=radius, radius2=top, depth=height), name)


def cylinder(radius: float = .5, height: float = 1, at=(0, 0, 0), rot=(0, 0, 0), mat=None, bevel_width: float = .003,
             sides: int = 64, name: str = '') -> bpy.types.Object:
    """A cylinder along Z, centred on `at`."""
    obj = _cone(radius, radius, height, sides, name)
    _smooth_sides(obj)
    if bevel_width:
        bevel(obj, bevel_width)
    return _finish(obj, name, at, rot, mat)


def cone(radius: float = .5, height: float = 1, top: float = 0, at=(0, 0, 0), rot=(0, 0, 0), mat=None, name: str = '') -> bpy.types.Object:
    """A cone along Z; top > 0 makes it a truncated cone."""
    obj = _cone(radius, top, height, 64, name)
    _smooth_sides(obj)
    return _finish(obj, name, at, rot, mat)


def torus(radius: float = .5, thickness: float = .1, at=(0, 0, 0), rot=(0, 0, 0), mat=None, name: str = '') -> bpy.types.Object:
    """A ring lying flat. radius to the middle of the tube, thickness of the tube's radius."""
    major, minor = 96, 24

    def make(bm):
        rings = []
        for i in range(major):
            a = 2 * math.pi * i / major
            ring = []
            for j in range(minor):
                b = 2 * math.pi * j / minor
                r = radius + thickness * math.cos(b)
                ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), thickness * math.sin(b))))
            rings.append(ring)
        for i in range(major):
            for j in range(minor):
                k, l = (i + 1) % major, (j + 1) % minor
                bm.faces.new((rings[i][j], rings[k][j], rings[k][l], rings[i][l]))

    obj = _new(make, name)
    obj.data.polygons.foreach_set('use_smooth', [True] * len(obj.data.polygons))
    return _finish(obj, name, at, rot, mat)


def _curve(points, steps: int = 10) -> list:
    """A Catmull-Rom curve through the points; a doubled point stays a corner."""
    pts = [tuple(map(float, p)) for p in points]
    runs, run = [], [pts[0]]
    for p in pts[1:]:
        if p == run[-1]:
            runs.append(run)
            run = [p]
        else:
            run.append(p)
    runs.append(run)
    out = []
    for run in runs:
        if len(run) < 3:
            out += run
            continue
        ends = [run[0], *run, run[-1]]
        for i in range(1, len(ends) - 2):
            p0, p1, p2, p3 = ends[i - 1:i + 3]
            for k in range(steps):
                t = k / steps
                out.append(tuple(.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t ** 2 + (3 * b - a - 3 * c + d) * t ** 3)
                                 for a, b, c, d in zip(p0, p1, p2, p3)))
        out.append(run[-1])
    return [(max(0, r), z) for r, z in out]


def lathe(profile, at=(0, 0, 0), rot=(0, 0, 0), mat=None, segments: int = 96, name: str = 'lathe') -> bpy.types.Object:
    """A turned shape (vase, cup, column, wheel): profile is [(radius, height), ...] from bottom to top, spun around Z.
    The profile is drawn as one smooth curve through its points; give the same point twice for a sharp corner."""
    profile = _curve(profile)
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    rings = [[bm.verts.new((max(r, 1e-4) * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), z))
              for i in range(segments)] for r, z in profile]
    for a, b in zip(rings, rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    return _finish(obj, name, at, rot, mat, True)


def extrude(points, height: float = .1, at=(0, 0, 0), rot=(0, 0, 0), mat=None, bevel_width: float = .003, name: str = 'extrude') -> bpy.types.Object:
    """A flat outline [(x, y), ...] raised by height, sitting on z=0 of `at`: plates, walls with a shape, logos."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    face = bm.faces.new([bm.verts.new((x, y, 0)) for x, y in points])
    res = bmesh.ops.extrude_face_region(bm, geom=[face])
    bmesh.ops.translate(bm, vec=(0, 0, height), verts=[g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    if bevel_width:
        bevel(obj, bevel_width)
    return _finish(obj, name, at, rot, mat)


def tube(points, radius: float = .02, at=(0, 0, 0), mat=None, end: float | None = None, name: str = 'tube') -> bpy.types.Object:
    """A smooth tube through [(x, y, z), ...]: cables, pipes, handles, horns. end is its radius at the last point, for a taper."""
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = 6
    curve.use_fill_caps = True
    spline = curve.splines.new('NURBS')
    spline.points.add(len(points) - 1)
    for i, (p, xyz) in enumerate(zip(spline.points, points)):
        p.co = (*xyz, 1)
        if end is not None:
            p.radius = 1 + (end / radius - 1) * i / max(1, len(points) - 1)
    spline.use_endpoint_u = True
    spline.order_u = min(4, len(points))
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = at
    if mat is not None:
        obj.data.materials.append(preset(mat) if isinstance(mat, str) else mat)
    return obj


def text(words: str, size: float = .3, depth: float = .03, at=(0, 0, 0), rot=(90, 0, 0), mat=None, name: str = 'text') -> bpy.types.Object:
    """Standing 3D text (Latin letters, Blender's own font)."""
    curve = bpy.data.curves.new(name, 'FONT')
    curve.body, curve.size, curve.extrude, curve.bevel_depth = words, size, depth, depth * .1
    curve.align_x, curve.align_y = 'CENTER', 'CENTER'
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = at
    obj.rotation_euler = Euler([math.radians(a) for a in rot])
    if mat is not None:
        obj.data.materials.append(preset(mat) if isinstance(mat, str) else mat)
    return obj


# --- changing shapes -------------------------------------------------------------------------------------------------

def smooth(obj, angle: float = 40) -> None:
    """Smooth shading, keeping edges sharper than angle."""
    mesh = obj.data
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    limit = math.radians(angle)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for edge in bm.edges:
        if edge.is_manifold and edge.calc_face_angle(0) > limit:
            edge.smooth = False
    bm.to_mesh(mesh)
    bm.free()


def bevel(obj, width: float = .005, segments: int = 3) -> None:
    """Round the object's hard edges: the highlight along an edge is what makes a model look real."""
    m = obj.modifiers.new('bevel', 'BEVEL')
    m.width, m.segments, m.limit_method, m.harden_normals = width, segments, 'ANGLE', False


def subdivide(obj, levels: int = 2) -> None:
    """Smooth a rough mesh into organic curves."""
    m = obj.modifiers.new('subdivide', 'SUBSURF')
    m.levels, m.render_levels = levels, levels


def cut(obj, tool, keep_tool: bool = False) -> None:
    """Take `tool`'s shape out of obj (holes, slots). The tool disappears unless keep_tool."""
    _boolean(obj, tool, 'DIFFERENCE', keep_tool)


def join(obj, tool, keep_tool: bool = False) -> None:
    """Melt `tool` into obj as one solid."""
    _boolean(obj, tool, 'UNION', keep_tool)


def _boolean(obj, tool, op, keep):
    m = obj.modifiers.new(op.lower(), 'BOOLEAN')
    m.operation, m.object, m.solver = op, tool, 'EXACT'
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj], selected_editable_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=m.name)
    if not keep:
        bpy.data.objects.remove(tool, do_unlink=True)


def copy(obj, at=None, rot=None, scale=None, name: str = '') -> bpy.types.Object:
    """Another of obj, sharing its mesh (light even by the thousand)."""
    new = obj.copy()
    bpy.context.collection.objects.link(new)
    if at is not None:
        new.location = at
    if rot is not None:
        new.rotation_euler = Euler([math.radians(a) for a in rot])
    if scale is not None:
        new.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    if name:
        new.name = name
    return new


def scatter(obj, count: int, area=(10, 10), z: float = 0, seed: int = 1, scale=(.7, 1.3), turn: bool = True) -> list:
    """count copies of obj across area (x, y) around the origin, each its own size and turn: stones, trees, grass tufts."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        s = rng.uniform(*scale)
        out.append(copy(obj, at=(rng.uniform(-area[0] / 2, area[0] / 2), rng.uniform(-area[1] / 2, area[1] / 2), z),
                        rot=(0, 0, rng.uniform(0, 360) if turn else 0), scale=s))
    return out


def group(*objects, at=(0, 0, 0), rot=(0, 0, 0), name: str = 'group') -> bpy.types.Object:
    """Parent objects to one empty, so they move as one (and animate as one)."""
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = at
    root.rotation_euler = Euler([math.radians(a) for a in rot])
    for o in objects:
        o.parent = root
    return root


# --- light, camera, ground -------------------------------------------------------------------------------------------

def sky(sun_height: float = 35, sun_turn: float = 140, strength: float = .04, haze: float = 1, clouds: float = 0, seed: int = 1) -> None:
    """A physical sky with its sun, the whole lighting of an outdoor scene. sun_height 0 = sunset, 90 = noon.
    clouds 0..1: 0 is an empty sky, .4 scattered clouds, 1 overcast."""
    world = bpy.data.worlds.new('sky')
    world.use_nodes = True
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    node = nt.nodes.new('ShaderNodeTexSky')
    kinds = [i.identifier for i in node.bl_rna.properties['sky_type'].enum_items]
    node.sky_type = next((k for k in ('MULTIPLE_SCATTERING', 'NISHITA', 'SINGLE_SCATTERING') if k in kinds), kinds[0])
    node.sun_elevation = math.radians(sun_height)
    node.sun_rotation = math.radians(sun_turn)
    for prop, value in (('dust_density', haze), ('aerosol_density', haze), ('air_density', 1)):
        if hasattr(node, prop):
            setattr(node, prop, value)
    nt.links.new(node.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    if clouds:
        _clouds(nt, bg, clouds, seed, sun_height)
    bpy.context.scene.world = world


def _clouds(nt, clear, amount: float, seed: int, sun_height: float) -> None:
    """A layer of cloud over the sky: noise on a flat ceiling seen from below, thinning into the horizon."""
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Generated'], split.inputs[0])
    level = nt.nodes.new('ShaderNodeMath')
    level.operation = 'MAXIMUM'
    level.inputs[1].default_value = .03
    nt.links.new(split.outputs['Z'], level.inputs[0])
    flat = nt.nodes.new('ShaderNodeCombineXYZ')
    for axis in ('X', 'Y'):
        d = nt.nodes.new('ShaderNodeMath')
        d.operation = 'DIVIDE'
        nt.links.new(split.outputs[axis], d.inputs[0])
        nt.links.new(level.outputs[0], d.inputs[1])
        nt.links.new(d.outputs[0], flat.inputs[axis])
    flat.inputs['Z'].default_value = seed * 3.7
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = .9
    noise.inputs['Detail'].default_value = 12
    noise.inputs['Roughness'].default_value = .58
    nt.links.new(flat.outputs[0], noise.inputs['Vector'])
    edge = nt.nodes.new('ShaderNodeMapRange')
    edge.inputs['From Min'].default_value = .62 - .34 * amount
    edge.inputs['From Max'].default_value = .78 - .34 * amount
    nt.links.new(noise.outputs[0], edge.inputs['Value'])
    fade = nt.nodes.new('ShaderNodeMapRange')  # far clouds melt into the haze
    fade.inputs['From Min'].default_value, fade.inputs['From Max'].default_value = .02, .2
    nt.links.new(split.outputs['Z'], fade.inputs['Value'])
    both = nt.nodes.new('ShaderNodeMath')
    both.operation = 'MULTIPLY'
    nt.links.new(edge.outputs[0], both.inputs[0])
    nt.links.new(fade.outputs[0], both.inputs[1])
    tone = nt.nodes.new('ShaderNodeValToRGB')  # thick cloud is darker below, its thin edges take the light
    glow = min(1, .35 + sun_height / 40)
    warm = tuple(a + (b - a) * glow for a, b in zip((1, .62, .42), (1, .97, .92)))
    tone.color_ramp.elements[0].position, tone.color_ramp.elements[1].position = .42, .68
    tone.color_ramp.elements[0].color = (*warm, 1)
    tone.color_ramp.elements[1].color = (.5 * glow + .26, .54 * glow + .27, .6 * glow + .3, 1)
    nt.links.new(noise.outputs[0], tone.inputs['Fac'])
    white = nt.nodes.new('ShaderNodeBackground')
    white.inputs['Strength'].default_value = .35 + .75 * glow
    nt.links.new(tone.outputs['Color'], white.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(both.outputs[0], mix.inputs[0])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(white.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])


def studio(brightness: float = 1) -> None:
    """A photo studio for a product shot: soft grey surround, big key light, fill and rim."""
    world = bpy.data.worlds.new('studio')
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (.18, .185, .2, 1)
    bg.inputs['Strength'].default_value = .5 * brightness
    bpy.context.scene.world = world
    area((3, -3, 4), look=(0, 0, .5), size=3, power=280 * brightness, name='key')
    area((-4, -2, 2), look=(0, 0, .5), size=4, power=90 * brightness, colour='#dfe8ff', name='fill')
    area((0, 4, 3), look=(0, 0, .5), size=2, power=160 * brightness, name='rim')


def sun(height: float = 40, turn: float = 140, power: float = 4, colour='#fff1dd', softness: float = 1.5) -> bpy.types.Object:
    """A sun light, when the sky alone is not what you want."""
    data = bpy.data.lights.new('sun', 'SUN')
    data.energy, data.color, data.angle = power, _rgba(colour)[:3], math.radians(softness)
    obj = bpy.data.objects.new('sun', data)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler = Euler((math.radians(90 - height), 0, math.radians(turn)))
    return obj


def area(at=(2, -2, 3), look=(0, 0, 0), size: float = 1, power: float = 100, colour='#ffffff', name: str = 'light') -> bpy.types.Object:
    """A soft rectangular light aimed at `look`. power in watts."""
    data = bpy.data.lights.new(name, 'AREA')
    data.size, data.energy, data.color = size, power, _rgba(colour)[:3]
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    _aim(obj, at, look)
    return obj


def point(at=(0, 0, 2), power: float = 40, colour='#ffd9a8', radius: float = .05, name: str = 'lamp') -> bpy.types.Object:
    """A small warm bulb. power in watts."""
    data = bpy.data.lights.new(name, 'POINT')
    data.energy, data.color, data.shadow_soft_size = power, _rgba(colour)[:3], radius
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = at
    return obj


def _aim(obj, at, look) -> None:
    obj.location = at
    obj.rotation_euler = (Vector(look) - Vector(at)).to_track_quat('-Z', 'Y').to_euler()


def camera(at=(4, -5, 2), look=(0, 0, .6), lens: float = 50, blur: float = 0, focus=None, name: str = 'camera') -> bpy.types.Object:
    """The scene's camera at `at`, aimed at `look`. lens in mm: 24 wide, 50 natural, 85 portrait, 200 far. blur is the
    aperture's f-number for depth of field (e.g. 2.8), focused on the point `focus` (default: `look`); 0 = everything sharp.
    Aim a little off your subject and focus on it: a subject dead in the middle looks like a catalogue."""
    data = bpy.data.cameras.new(name)
    data.lens = lens
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    _aim(obj, at, look)
    if blur:
        data.dof.use_dof = True
        data.dof.aperture_fstop = blur
        data.dof.focus_distance = (Vector(focus if focus is not None else look) - Vector(at)).length
    bpy.context.scene.camera = obj
    return obj


def ground(size: float = 60, mat='concrete', z: float = 0, name: str = 'ground') -> bpy.types.Object:
    """A large floor; outdoors make it big, 1500, so that its end is never seen. It does not count when the views frame the model."""
    obj = _new(lambda bm: bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2), name)
    obj.location = (0, 0, z)
    obj['c3d_ground'] = True
    apply(obj, mat)
    return obj


# --- animation -------------------------------------------------------------------------------------------------------

def key(obj, frame: int, at=None, rot=None, scale=None) -> None:
    """Fix where obj is at this frame; Blender moves it smoothly from key to key."""
    if at is not None:
        obj.location = at
        obj.keyframe_insert('location', frame=frame)
    if rot is not None:
        obj.rotation_euler = Euler([math.radians(a) for a in rot])
        obj.keyframe_insert('rotation_euler', frame=frame)
    if scale is not None:
        obj.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
        obj.keyframe_insert('scale', frame=frame)


# --- light as a photographer thinks of it -------------------------------------------------------------------------------

def kelvin(k: float) -> str:
    """The colour of a light source: 1900 candle, 2700 warm bulb, 3200 halogen, 5000 noon, 6500 overcast, 9000 blue dusk.
    Warm rooms look real around 2800-3200; much lower turns the whole picture orange."""
    t = k / 100
    r = 255 if t <= 66 else 329.7 * (t - 60) ** -.1332
    g = 99.47 * math.log(t) - 161.1 if t <= 66 else 288.1 * (t - 60) ** -.0755
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5 * math.log(t - 10) - 305)
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(c))) for c in (r, g, b))


def dusk(strength: float = .6, top='#233a66', horizon='#b08a7a') -> None:
    """A sky after sunset or after rain, blue above and pale at the horizon, for scenes seen through a window. The physical
    sky() goes black once the sun is down; this one does not."""
    world = bpy.data.worlds.new('dusk')
    world.use_nodes = True
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = .02, .45
    ramp.color_ramp.elements[0].color = _rgba(horizon)
    ramp.color_ramp.elements[1].color = _rgba(top)
    nt.links.new(coord.outputs['Generated'], split.inputs[0])
    nt.links.new(split.outputs['Z'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    bpy.context.scene.world = world


def night(moon: float = .6, turn: float = 200, height: float = 40, milky: float = 1) -> None:
    """A clear night: deep blue sky, thousands of stars, the band of the Milky Way, and a moon's cold light from turn and height
    (0 is +Y, as for the sun). moon 0 is a moonless night."""
    world = bpy.data.worlds.new('night')
    world.use_nodes = True
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == 'BACKGROUND')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Generated'], split.inputs[0])
    up = nt.nodes.new('ShaderNodeMapRange')  # paler towards the horizon
    up.inputs['From Min'].default_value, up.inputs['From Max'].default_value = 0, .5
    nt.links.new(split.outputs['Z'], up.inputs['Value'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = _rgba('#1a2640')
    ramp.color_ramp.elements[1].color = _rgba('#04070f')
    nt.links.new(up.outputs[0], ramp.inputs['Fac'])
    stars = nt.nodes.new('ShaderNodeTexVoronoi')
    stars.inputs['Scale'].default_value = 170
    nt.links.new(coord.outputs['Generated'], stars.inputs['Vector'])
    bright = nt.nodes.new('ShaderNodeMapRange')
    bright.inputs['From Min'].default_value, bright.inputs['From Max'].default_value = .055, .012
    bright.inputs['To Max'].default_value = 3
    nt.links.new(stars.outputs['Distance'], bright.inputs['Value'])
    which = nt.nodes.new('ShaderNodeMapRange')  # only some cells hold a star, of all brightnesses
    which.inputs['From Min'].default_value, which.inputs['From Max'].default_value = .45, 1
    nt.links.new(stars.outputs['Color'], which.inputs['Value'])
    lit = nt.nodes.new('ShaderNodeMath')
    lit.operation = 'MULTIPLY'
    nt.links.new(bright.outputs[0], lit.inputs[0])
    nt.links.new(which.outputs[0], lit.inputs[1])
    tilt = nt.nodes.new('ShaderNodeMapping')  # the Milky Way, a slanting river of light
    tilt.inputs['Rotation'].default_value = (.5, 1.0, .4)
    nt.links.new(coord.outputs['Generated'], tilt.inputs['Vector'])
    side = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tilt.outputs[0], side.inputs[0])
    band = nt.nodes.new('ShaderNodeMath')
    band.operation = 'ABSOLUTE'
    nt.links.new(side.outputs['X'], band.inputs[0])
    mask = nt.nodes.new('ShaderNodeMapRange')
    mask.inputs['From Min'].default_value, mask.inputs['From Max'].default_value = .24, .02
    nt.links.new(band.outputs[0], mask.inputs['Value'])
    dust = nt.nodes.new('ShaderNodeTexNoise')
    dust.inputs['Scale'].default_value = 7
    dust.inputs['Detail'].default_value = 10
    nt.links.new(coord.outputs['Generated'], dust.inputs['Vector'])
    glow = nt.nodes.new('ShaderNodeMath')
    glow.operation = 'MULTIPLY'
    nt.links.new(mask.outputs[0], glow.inputs[0])
    nt.links.new(dust.outputs[0], glow.inputs[1])
    amount = nt.nodes.new('ShaderNodeMath')
    amount.operation = 'MULTIPLY'
    amount.inputs[1].default_value = .03 * milky
    nt.links.new(glow.outputs[0], amount.inputs[0])
    both = nt.nodes.new('ShaderNodeMath')
    nt.links.new(lit.outputs[0], both.inputs[0])
    nt.links.new(amount.outputs[0], both.inputs[1])
    tint = nt.nodes.new('ShaderNodeMixRGB')
    tint.blend_type = 'ADD'
    tint.inputs[0].default_value = 1
    nt.links.new(ramp.outputs['Color'], tint.inputs[1])
    nt.links.new(both.outputs[0], tint.inputs[2])
    above = nt.nodes.new('ShaderNodeMapRange')  # nothing under the horizon
    above.inputs['From Min'].default_value, above.inputs['From Max'].default_value = -.01, .02
    nt.links.new(split.outputs['Z'], above.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMixRGB')
    nt.links.new(above.outputs[0], mix.inputs[0])
    mix.inputs[1].default_value = _rgba('#0a0f1a')
    nt.links.new(tint.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1
    bpy.context.scene.world = world
    if moon:
        sun(height=height, turn=turn, power=.16 * moon, colour='#b8c8ea', softness=.6)


def exposure(stops: float = 0) -> None:
    """Brighter (+1) or darker (-1) as a whole, like the camera's exposure dial, without touching the lights."""
    bpy.context.scene.view_settings.exposure = stops


# --- things, ready to place ---------------------------------------------------------------------------------------------
# Each stands on the point `at` (z is what it stands on), turned by `turn` degrees, at its real size. Use them instead of
# building these from boxes: they already have the curves, thickness and small details that make a thing look real.

def _place(parts, at, turn, name):
    for part in parts:
        if part.name == name:  # the whole keeps the name the scene gave it
            part.name = f'{name} part'
    return group(*parts, at=at, rot=(0, 0, turn), name=name)


def mug(at=(0, 0, 0), turn: float = 0, colour='#f3efe7', drink: str = 'latte', name: str = 'mug') -> bpy.types.Object:
    """A ceramic mug, 9 cm tall, with a real wall thickness and handle. drink: latte, coffee, tea, water or None."""
    mat = preset('porcelain', colour=colour)
    body = lathe([(0, 0), (.03, 0), (.03, 0), (.036, .003), (.04, .02), (.041, .06), (.042, .086), (.0425, .0885), (.0415, .089), (.0395, .086),
                  (.039, .06), (.038, .02), (.03, .008), (0, .006)], mat=mat, name='cup')
    grip = tube([(.04, 0, .074), (.058, 0, .076), (.067, 0, .058), (.064, 0, .036), (.05, 0, .024), (.04, 0, .024)], .0055, mat=mat, name='handle')
    parts = [body, grip]
    if drink:
        parts.append(_drink(drink, .0388, .076))
    return _place(parts, at, turn, name)


def cup_and_saucer(at=(0, 0, 0), turn: float = 0, colour='#f3efe7', drink: str = 'latte', size: float = 1, name: str = 'coffee') -> bpy.types.Object:
    """A wide coffee cup on its saucer, with a spoon. The saucer is 16 cm wide, the cup 9.6 cm; size scales it all."""
    mat = preset('porcelain', colour=colour)
    plate = lathe([(0, 0), (.04, 0), (.04, 0), (.046, .002), (.072, .012), (.079, .0165), (.0795, .018), (.077, .018), (.07, .0145), (.048, .0065),
                   (.038, .0055), (0, .0055)], mat=mat, name='saucer')
    cup = lathe([(0, .006), (.025, .006), (.025, .006), (.029, .008), (.04, .024), (.046, .05), (.0475, .0635), (.0482, .066), (.0472, .0665),
                 (.0455, .062), (.044, .05), (.037, .027), (.026, .014), (0, .012)], mat=mat, name='cup')
    grip = tube([(.045, 0, .056), (.06, 0, .058), (.068, 0, .046), (.062, 0, .032), (.044, 0, .028), (.036, 0, .024)], .0042, mat=mat, name='handle')
    spoon_mat = preset('steel', rough=.2)
    spoon = tube([(.03, -.062, .0165), (.0, -.066, .0205), (-.05, -.057, .024), (-.078, -.05, .025)], .0015, mat=spoon_mat, name='spoon')
    bowl = sphere(.011, at=(.041, -.058, .0165), mat=spoon_mat, name='spoon bowl')
    bowl.scale = (1.3, .8, .25)
    whole = _place([plate, cup, grip, spoon, bowl, _drink(drink, .0448, .058)] if drink else [plate, cup, grip, spoon, bowl], at, turn, name)
    whole.scale = (size, size, size)
    return whole


def _drink(kind: str, radius: float, z: float):
    surface = cylinder(radius, .002, at=(0, 0, z), bevel_width=0, name=kind)
    if kind == 'latte':
        mat = material('latte', '#c79a68', rough=.3, soft=.4)
        nt = mat.node_tree
        p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        wave = nt.nodes.new('ShaderNodeTexWave')
        wave.wave_type, wave.rings_direction = 'RINGS', 'Z'
        wave.inputs['Scale'].default_value = 16
        wave.inputs['Distortion'].default_value = 7
        wave.inputs['Detail'].default_value = 2
        coord = nt.nodes.new('ShaderNodeTexCoord')
        nt.links.new(coord.outputs['Object'], wave.inputs['Vector'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = .35, .62
        ramp.color_ramp.elements[0].color = _rgba('#8a5a33')
        ramp.color_ramp.elements[1].color = _rgba('#f0dfc4')
        nt.links.new(wave.outputs[0], ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    else:
        look = {'coffee': ('#1d100a', .08), 'tea': ('#8a4a14', .06), 'water': ('#dfeff0', .02)}.get(kind, ('#1d100a', .08))
        mat = material(kind, look[0], rough=look[1], glass=1 if kind == 'water' else 0, ior=1.33)
    apply(surface, mat)
    return surface


def book(at=(0, 0, 0), turn: float = 0, size=(.15, .21, .028), colour='#5b3a24', worn: float = .5, name: str = 'book') -> bpy.types.Object:
    """A closed hardback lying flat: boards overhanging the page block, a rounded spine, a cream edge of pages."""
    w, h, t = size
    cover = material('cover', colour, rough=.55, vary=.1 + .3 * worn, bump=.25, scale=90, coat=.1)
    edge = material('page edge', '#e6dcc2', rough=.8)
    nt = edge.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    lines = nt.nodes.new('ShaderNodeTexWave')
    lines.bands_direction = 'Z'
    lines.inputs['Scale'].default_value = 900
    lines.inputs['Distortion'].default_value = .6
    coord = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(coord.outputs['Object'], lines.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = _rgba('#bfb296')
    ramp.color_ramp.elements[1].color = _rgba('#f1e8d2')
    nt.links.new(lines.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    board = .0025
    low = box((w, h, board), at=(0, 0, board / 2), mat=cover, bevel_width=.0009, name='back board')
    top = box((w, h, board), at=(0, 0, t - board / 2), mat=cover, bevel_width=.0009, name='front board')
    pages = box((w - .007, h - .006, t - 2 * board), at=(.0005, 0, t / 2), mat=edge, bevel_width=.0004, name='pages')
    spine = cylinder(t / 2 + .0002, h, at=(-w / 2 + .001, 0, t / 2), rot=(90, 0, 0), mat=cover, bevel_width=.0004, sides=32, name='spine')
    spine.scale = (.42, 1, 1)
    return _place([low, top, pages, spine], at, turn, name)


def _leaf_mesh(length: float, width: float, droop: float, twist: float, name: str):
    steps, across = 12, 4
    verts, faces = [], []
    for i in range(steps + 1):
        t = i / steps
        half = width * .5 * math.sin(math.pi * t ** .75) ** .8 + .0003
        along = length * t
        y = along * math.cos(droop * t)
        z = along * math.sin(droop * .15) - droop * length * .55 * t * t
        for j in range(across + 1):
            u = j / across * 2 - 1
            x = half * u
            fold = abs(u) * half * .35  # a leaf is a shallow V, not a flat sheet
            verts.append((x * math.cos(twist * t) , y, z + fold + x * math.sin(twist * t)))
    for i in range(steps):
        for j in range(across):
            a = i * (across + 1) + j
            faces.append((a, a + 1, a + across + 2, a + across + 1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def potted_plant(at=(0, 0, 0), turn: float = 0, height: float = .3, colour='#3f6f2f', pot='terracotta', seed: int = 3, leaves: int = 16,
                 name: str = 'plant') -> bpy.types.Object:
    """A small leafy house plant in a pot: curved leaves of different sizes and greens, soil, a rimmed pot. height is the
    whole thing. pot: a preset's name or a Material."""
    rng = random.Random(seed)
    k = height / .3
    pot_h, pot_r = .105 * k, .062 * k
    vessel = lathe([(0, 0), (pot_r * .72, 0), (pot_r * .72, 0), (pot_r * .92, pot_h * .75), (pot_r * .94, pot_h * .76), (pot_r * 1.06, pot_h * .78),
                    (pot_r * 1.08, pot_h), (pot_r * .98, pot_h * 1.01), (pot_r * .9, pot_h * .9), (0, pot_h * .9)], mat=pot, name='pot')
    soil = cylinder(pot_r * .9, .004, at=(0, 0, pot_h * .9), mat=preset('soil'), bevel_width=0, name='soil')
    parts = [vessel, soil]
    gold = 2.39996
    for i in range(leaves):
        t = i / max(1, leaves - 1)
        length = (height - pot_h) * rng.uniform(.75, 1.25) * (.6 + .6 * (1 - t) ** .5)
        leaf = _leaf_mesh(length, length * rng.uniform(.26, .36), rng.uniform(.5, 1.5) * (.5 + t), rng.uniform(-.5, .5), f'leaf {i}')
        hue = _rgba(colour)
        shade = rng.uniform(.75, 1.25)
        apply(leaf, material('leaf', tuple(c * shade * s for c, s in zip(hue[:3], (rng.uniform(.9, 1.1), 1, rng.uniform(.8, 1.05)))), rough=.42,
                             vary=.45, bump=.1, scale=14, soft=.3, coat=.25))
        a = i * gold + rng.uniform(-.2, .2)
        r = pot_r * .3 * (.3 + t)
        leaf.location = (r * math.cos(a), r * math.sin(a), pot_h * .9)
        leaf.rotation_euler = Euler((math.radians(rng.uniform(58, 80) - 45 * t), 0, a - math.pi / 2))
        parts.append(leaf)
    return _place(parts, at, turn, name)


def table(at=(0, 0, 0), turn: float = 0, size=(1.2, .7, .75), mat='wood', name: str = 'table') -> bpy.types.Object:
    """A wooden table on four tapered legs. size is (length, depth, height); its top is at height above `at`."""
    w, d, h = size
    wood_mat = wood(scale=3) if mat == 'wood' else preset(mat) if isinstance(mat, str) else mat
    top = box((w, d, .03), at=(0, 0, h - .015), mat=wood_mat, bevel_width=.003, name='table top')
    rail = wood_mat
    parts = [top]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(lathe([(0, 0), (.018, 0), (.018, 0), (.03, h - .03), (.03, h - .03), (0, h - .03)], at=(sx * (w / 2 - .06), sy * (d / 2 - .06), 0),
                               mat=rail, segments=32, name='leg'))
    parts.append(box((w - .16, .018, .06), at=(0, d / 2 - .06, h - .06), mat=rail, name='rail'))
    parts.append(box((w - .16, .018, .06), at=(0, -d / 2 + .06, h - .06), mat=rail, name='rail'))
    return _place(parts, at, turn, name)


def pendant_lamp(at=(0, 0, 2.6), drop: float = .7, colour='#2a2a2c', warm: float = 3300, power: float = 40, name: str = 'pendant') -> bpy.types.Object:
    """A lamp hanging from the ceiling point `at` by a cord of length drop: shade, glowing bulb, and the light it gives."""
    x, y, z = at
    shade_mat = preset('paint', colour=colour)
    cord = cylinder(.003, drop, at=(x, y, z - drop / 2), mat=material('cord', '#141414', rough=.6), bevel_width=0, name='cord')
    shade = lathe([(.02, .12), (.024, .118), (.04, .1), (.11, .03), (.15, 0), (.148, 0), (.108, .03), (.038, .095), (.02, .11)],
                  at=(x, y, z - drop - .12), mat=shade_mat, name='shade')
    bulb = sphere(.03, at=(x, y, z - drop - .08), mat=material('bulb', kelvin(warm), glow=kelvin(warm), glow_strength=12), name='bulb')
    light = point(at=(x, y, z - drop - .1), power=power, colour=kelvin(warm), radius=.04, name='lamp light')
    return group(cord, shade, bulb, light, name=name)


def room(size=(5, 4, 2.7), walls='plaster', floor=None, window: bool = True, sill: float = .85, window_size=(2.4, 1.5), colour=None, daylight: float = 90,
         rain: float = 0, name: str = 'room') -> bpy.types.Object:
    """A room standing on z=0, centred on x=0, with its back wall at y=+depth/2 and a big window in that wall looking out on
    +Y. Put the camera inside looking towards +Y. It has real walls, floorboards, a ceiling, a framed glazed window.
    daylight is the sky's light coming in: 90 at dusk, 900 by day. rain 0..2 puts drops of water on the glass, with the runs
    they leave: 1 is a shower that just ended. By day a sun on +Y (sky(sun_turn=-30, sun_height=30)) throws the window on the table."""
    w, d, h = size
    wall_mat = preset(walls, colour=colour) if isinstance(walls, str) else walls
    floor_mat = floor if floor is not None else boards()
    t = .15
    ww, wh = window_size
    parts = [box((w + 2 * t, d + 2 * t, .1), at=(0, 0, -.05), mat=floor_mat, bevel_width=0, name='floor'),
             box((w + 2 * t, d + 2 * t, .1), at=(0, 0, h + .05), mat=wall_mat, bevel_width=0, name='ceiling'),
             box((t, d, h), at=(-w / 2 - t / 2, 0, h / 2), mat=wall_mat, bevel_width=0, name='wall left'),
             box((t, d, h), at=(w / 2 + t / 2, 0, h / 2), mat=wall_mat, bevel_width=0, name='wall right'),
             box((w + 2 * t, t, h), at=(0, -d / 2 - t / 2, h / 2), mat=wall_mat, bevel_width=0, name='wall behind')]
    y = d / 2 + t / 2
    if not window:
        parts.append(box((w + 2 * t, t, h), at=(0, y, h / 2), mat=wall_mat, bevel_width=0, name='wall front'))
        return group(*parts, name=name)
    side = (w - ww) / 2
    parts += [box((side + t, t, h), at=(-w / 2 - t + (side + t) / 2, y, h / 2), mat=wall_mat, bevel_width=0, name='wall left of window'),
              box((side + t, t, h), at=(w / 2 + t - (side + t) / 2, y, h / 2), mat=wall_mat, bevel_width=0, name='wall right of window'),
              box((ww, t, sill), at=(0, y, sill / 2), mat=wall_mat, bevel_width=0, name='wall under window'),
              box((ww, t, h - sill - wh), at=(0, y, (h + sill + wh) / 2), mat=wall_mat, bevel_width=0, name='wall over window')]
    frame = preset('paint', colour='#e8e2d6')
    z = sill + wh / 2
    parts += [box((ww + .1, .28, .03), at=(0, y - .03, sill + .015), mat=wood(colour='#6b4628', scale=8), bevel_width=.003, name='window sill'),
              box((ww, .05, .05), at=(0, y, sill + wh - .025), mat=frame, name='frame'), box((ww, .05, .05), at=(0, y, sill + .055), mat=frame, name='frame'),
              box((.05, .05, wh), at=(-ww / 2 + .025, y, z), mat=frame, name='frame'), box((.05, .05, wh), at=(ww / 2 - .025, y, z), mat=frame, name='frame'),
              box((.04, .04, wh), at=(0, y, z), mat=frame, name='frame'), box((ww, .04, .035), at=(0, y, sill + wh * .68), mat=frame, name='frame')]
    pane = box((ww - .04, .006, wh - .04), at=(0, y, z), mat=_lets_light_through(preset('glass')), bevel_width=0, name='window glass')
    parts.append(pane)
    if rain:
        parts.append(rain_drops(size=(ww - .1, wh - .1), at=(0, y - .0035, z), amount=rain))
    # the sky's cool light coming in: what makes the warm lamp read as warm instead of turning everything orange
    sky_light = area(at=(0, y + .4, z), look=(0, 0, 1), size=max(ww, wh), power=daylight, colour=kelvin(8500), name='window light')
    sky_light.visible_camera = sky_light.visible_transmission = sky_light.visible_glossy = False  # the light, not a white sheet in the window
    parts.append(sky_light)
    return group(*parts, name=name)


def _lets_light_through(mat) -> bpy.types.Material:
    """To a renderer glass stops the light of lamps and of the sun: a room behind a window stayed dark at noon. Thin glass and
    water let shadow rays pass."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    shader = out.inputs['Surface'].links[0].from_socket
    path = nt.nodes.new('ShaderNodeLightPath')
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(path.outputs['Is Shadow Ray'], mix.inputs[0])
    nt.links.new(shader, mix.inputs[1])
    nt.links.new(clear.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def rain_drops(size=(2, 1.5), at=(0, 0, 0), amount: float = 1, seed: int = 11, name: str = 'rain drops') -> bpy.types.Object:
    """Drops of water on an upright pane in the XZ plane, centred on `at`, on its -Y face: thousands of real little lenses,
    most of them tiny, gathered in places, some with a run below them. room(rain=1) makes these by itself."""
    rng = random.Random(seed)
    w, h = size
    spots = [(rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2), rng.uniform(.15, .5)) for _ in range(12)]
    # one unit dome: flat against the glass, round towards the room
    ring, rise = 10, 3
    dome = [(math.cos(i / ring * 6.2832) * math.cos(j / rise * 1.5708), -math.sin(j / rise * 1.5708), math.sin(i / ring * 6.2832) * math.cos(j / rise * 1.5708))
            for j in range(rise) for i in range(ring)] + [(0, -1, 0)]
    cap = [(j * ring + i, j * ring + (i + 1) % ring, (j + 1) * ring + (i + 1) % ring, (j + 1) * ring + i) for j in range(rise - 1) for i in range(ring)]
    cap.append(tuple(range(ring - 1, -1, -1)))  # closed against the glass: a lens, not a shell
    last = len(dome) - 1
    cap += [((rise - 1) * ring + i, (rise - 1) * ring + (i + 1) % ring, last) for i in range(ring)]
    verts, faces = [], []

    def drop(x, z, r, tall=1.0):
        v = len(verts)
        verts.extend((x + dx * r, dy * r * .55, z + dz * r * tall - (r * .25 * tall if dz < 0 else 0)) for dx, dy, dz in dome)
        faces.extend(tuple(i + v for i in f) for f in cap)

    for _ in range(int(9000 * amount)):
        x, z = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
        crowd = max(math.exp(-((x - a) ** 2 + (z - b) ** 2) / (2 * c * c)) for a, b, c in spots)
        if rng.random() > .22 + .78 * crowd:
            continue
        drop(x, z, rng.uniform(.001, .003) if rng.random() < .88 else rng.uniform(.003, .0065))
    for _ in range(int(70 * amount)):  # a big drop that ran down: a thin trail of beads above it
        x, z = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2 + .1, h / 2)
        r = rng.uniform(.004, .008)
        drop(x, z, r, 1.5)
        trail = rng.uniform(.04, .3)
        dz, wander = r * 1.8, 0.0
        while dz < trail and z + dz < h / 2:
            wander += rng.uniform(-.0012, .0012)
            drop(x + wander, z + dz, r * rng.uniform(.18, .34) * (1 - dz / trail * .5))
            dz += rng.uniform(.002, .007)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    apply(obj, _lets_light_through(material('rain water', '#ffffff', rough=.02, glass=1, ior=1.33)))
    obj.location = at
    return obj


def street_outside(y: float = 3.5, z: float = -.4, wet: bool = True, seed: int = 5, lamps: float = 1, windows: float = 1, name: str = 'street') -> bpy.types.Object:
    """A street at dusk beyond a window on the +Y side: wet road, buildings across it with lit windows and shop signs, street
    lamps. Use it with dusk(), and with camera(blur=2, focus=something indoors) it melts into soft lights, as in a photograph.
    lamps and windows turn the street lights and the lit windows up or down: .4 is a street in blue dusk, 1 a warm evening."""
    rng = random.Random(seed)
    across = y + 22  # far enough for the sky to show over the roofs
    road = box((90, 24, .1), at=(0, y + 12, z - .05), mat=material('wet road', '#23262b', rough=.1 if wet else .6, vary=.5, bump=.2, scale=2), bevel_width=0, name='road')
    parts = [road, box((90, 2.2, .15), at=(0, y + 1, z + .02), mat=preset('concrete'), bevel_width=0, name='pavement')]
    bar = material('window bar', '#17181b', rough=.6)
    shades = [material('lit window', kelvin(k), glow=kelvin(k), glow_strength=g * windows) for k in (2800, 3000, 3300, 4200) for g in (.3, .5, .8)]
    bulbs = [material('window lamp', kelvin(k), glow=kelvin(k), glow_strength=38 * windows) for k in (2500, 3000)]
    x = -40.0
    while x < 40:
        wide = rng.uniform(7, 12)
        tall = rng.uniform(6.5, 11)
        shade = rng.choice(('#5b6880', '#646a7e', '#515e78', '#6a6578'))  # at dusk a building takes the blue of the sky
        parts.append(box((wide - .2, 8, tall), at=(x + wide / 2, across + 4, z + tall / 2), mat=material('facade', shade, rough=.85, vary=.3, scale=2), bevel_width=0, name='building'))
        for row in range(int(tall // 3.2)):
            for col in range(int(wide // 2.2)):
                if rng.random() >= (.75 if row == 0 else .32):
                    continue
                wx, wz = x + 1.3 + col * 2.2, z + 1.5 + row * 3.2
                pw, ph = (1.2, 1.5) if row == 0 else (.7, 1)
                parts.append(box((pw, .1, ph), at=(wx, across - .05, wz), mat=rng.choice(shades), bevel_width=0, name='lit window'))
                # a window is a frame with a room behind it: bars, a blind half down, a lamp inside
                parts.append(box((.05, .03, ph), at=(wx, across - .12, wz), mat=bar, bevel_width=0, name='window bar'))
                parts.append(box((pw, .03, .05), at=(wx, across - .12, wz + ph * .1), mat=bar, bevel_width=0, name='window bar'))
                if rng.random() < .4:
                    drop = ph * rng.uniform(.2, .6)
                    parts.append(box((pw, .03, drop), at=(wx, across - .11, wz + ph / 2 - drop / 2), mat=bar, bevel_width=0, name='blind'))
                if rng.random() < .55:
                    parts.append(sphere(.05, at=(wx + rng.uniform(-pw, pw) * .35, across - .2, wz + ph * .25), mat=rng.choice(bulbs), name='window lamp'))
        x += wide + rng.choice((0, 0, 0, 2.5, 5))  # side streets let the sky through
    for i in range(8):
        lx = -35 + i * 10 + rng.uniform(-1, 1)
        parts.append(cylinder(.07, 5.5, at=(lx, y + 2.4, z + 2.75), mat=preset('iron'), bevel_width=0, sides=12, name='lamp post'))
        parts.append(sphere(.16, at=(lx, y + 2.4, z + 5.6), mat=material('street lamp', '#ffe2b0', glow='#ffd9a0', glow_strength=14 * max(.3, lamps)), name='street lamp'))
        parts.append(point(at=(lx, y + 2.4, z + 5.4), power=1400 * lamps, colour=kelvin(3200), radius=.2, name='street light'))
    for i in range(60):  # small far lights are what turn into round soft discs behind a shallow focus
        hue = kelvin(rng.choice((2400, 2800, 3200))) if rng.random() < .7 else rng.choice(('#ff5a4c', '#ff3a30', '#7cc8ff'))
        parts.append(sphere(.09, at=(rng.uniform(-22, 22), y + rng.uniform(3, 14), z + rng.uniform(.5, 4.2)), mat=material('far light', hue, glow=hue, glow_strength=rng.uniform(25, 70) * max(.4, lamps)), name='far light'))
    for i in range(5):
        hue = rng.choice(('#ff6a5c', '#5cc8ff', '#ffb45c', '#ff78b0'))
        parts.append(box((rng.uniform(2, 3.5), .1, .5), at=(-20 + i * 9 + rng.uniform(-2, 2), across - .1, z + 3), mat=material('shop sign', hue, glow=hue, glow_strength=1.6 * windows), bevel_width=0, name='shop sign'))
    return group(*parts, name=name)


def garden_outside(y: float = 3, z: float = -.1, seed: int = 4, name: str = 'garden') -> bpy.types.Object:
    """A garden beyond a window on the +Y side, by day: lawn, a hedge, trees. With camera(blur=2.8, focus=something indoors) it
    goes soft, as it does behind a real window."""
    rng = random.Random(seed)
    lawn = ground(size=400, mat='grass', z=z, name='lawn')
    lawn.location.y = y + 200
    parts = []
    for i in range(30):
        parts.append(tree(at=(rng.uniform(-48, 48), y + rng.uniform(9, 60), z), height=rng.uniform(8, 14), seed=seed + i))
    return group(*parts, name=name)


class _Blocks:
    """Many plain blocks as one mesh, each with its tone: a facade of a thousand parts costs what one part costs."""

    def __init__(self):
        self.verts, self.faces, self.tones = [], [], []

    def add(self, low, high, tone):
        n = len(self.verts)
        (x0, y0, z0), (x1, y1, z1) = low, high
        self.verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for a, b, c, d in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.faces.append((n + a, n + b, n + c, n + d))
        self.tones += [tuple(tone[:3])] * 8

    def mesh(self, name, rough):
        return _coloured(name, self.verts, self.faces, self.tones, rough)


def building(at=(0, 0, 0), turn: float = 0, size=(14, 12, 18), colour='#b5a795', floors: int | None = None, shop: bool = True, lit: float = 0, seed: int = 1,
             name: str = 'building') -> bpy.types.Object:
    """A city building standing on `at`, its front facing -Y before it is turned: real window recesses, sills, a cornice, and a
    shop with a sign and an awning at street level. lit 0..1 is how many windows have a light on at night."""
    rng = random.Random(seed)
    w, d, h = size
    floors = floors or max(2, int(h // 3.3))
    tall = h / floors
    wall, deep = _rgba(colour), tuple(c * .62 for c in _rgba(colour)[:3])
    trim = tuple(min(1, c * 1.22) for c in _rgba(colour)[:3])
    b, pane, glow = _Blocks(), _Blocks(), _Blocks()
    bays = max(2, int(w // 3))
    bay = w / bays
    wid, high = bay * .52, tall * .56
    base = tall if shop else 0
    # the wall in strips, so that each window is a real hole with depth
    b.add((-w / 2, .4, 0), (w / 2, d, h), wall)
    b.add((-w / 2, 0, h - .5), (w / 2, .4, h), wall)
    b.add((-w / 2, 0, 0), (w / 2, .4, .45), deep)  # the plinth; over it a shop's front is open
    for f in range(1 if shop else 0, floors):
        z = f * tall
        sill, top = z + (tall - high) * .45, z + (tall - high) * .45 + high
        b.add((-w / 2, 0, z), (w / 2, .4, sill), wall)
        b.add((-w / 2, 0, top), (w / 2, .4, z + tall if f < floors - 1 else h), wall)
        for i in range(bays + 1):
            x = -w / 2 + i * bay
            b.add((x - (bay - wid) / 2 if i else x, 0, sill), (x + (bay - wid) / 2 if i < bays else x, .4, top), wall)
        for i in range(bays):
            x = -w / 2 + (i + .5) * bay
            b.add((x - wid / 2 - .06, -.1, sill - .08), (x + wid / 2 + .06, .08, sill), trim)  # a sill that catches the light
            frame = (.16, .15, .17)
            for u in (-1, 0, 1):
                b.add((x + u * wid / 2 - .025, .28, sill), (x + u * wid / 2 + .025, .34, top), frame)
            b.add((x - wid / 2, .28, sill + high * .62), (x + wid / 2, .34, sill + high * .62 + .05), frame)
            if lit and rng.random() < lit:
                warm = _rgba(kelvin(rng.choice((2800, 3000, 3400))))
                glow.add((x - wid / 2, .3, sill), (x + wid / 2, .32, top), tuple(c * rng.uniform(.5, 1.3) for c in warm[:3]))
            else:
                pane.add((x - wid / 2, .3, sill), (x + wid / 2, .32, top), (.09, .1, .12))
        b.add((-w / 2 - .08, -.08, z - .06), (w / 2 + .08, .05, z + .03), trim)
    b.add((-w / 2 - .22, -.28, h - .34), (w / 2 + .22, .1, h - .08), trim)  # cornice
    parts = []
    if shop:
        sign = _rgba(rng.choice(('#7a2e2a', '#22495c', '#2f4a36', '#4a3a6a', '#7a5a1e')))
        b.add((-w / 2, -.06, base - .85), (w / 2, .18, base), sign)
        for u in range(-1, 2):
            b.add((u * w / 3 - .18, 0, 0), (u * w / 3 + .18, .4, base - .85), deep)
        b.add((-w / 2, 0, 0), (-w / 2 + .3, .4, base - .85), deep)
        b.add((w / 2 - .3, 0, 0), (w / 2, .4, base - .85), deep)
        warm = _rgba(kelvin(3100))
        for u in range(3):  # three windows, each its own shop: shelves and goods against a dim glow, or closed for the night
            x0, x1 = -w / 2 + w * u / 3, -w / 2 + w * (u + 1) / 3
            if lit and rng.random() < .75:
                glow.add((x0, .38, .45), (x1, .4, base - .85), tuple(c * rng.uniform(.22, .5) for c in warm[:3]))
                for k in range(3):
                    z = .9 + k * (base - 1.9) / 3
                    b.add((x0, .3, z), (x1, .36, z + .05), (.05, .04, .04))
                    x = x0
                    while x < x1 - .3:  # the goods on a shelf, dark against the light
                        wide = rng.uniform(.12, .4)
                        b.add((x, .3, z + .05), (x + wide, .36, z + rng.uniform(.15, .42)), tuple(c * rng.uniform(.15, .7) for c in (rng.random(), rng.random(), rng.random())))
                        x += wide + rng.uniform(.03, .3)
                glow.add((x0 + .2, .3, base - 1.02), (x1 - .2, .34, base - .96), tuple(c * 2.4 for c in warm[:3]))
            else:
                pane.add((x0, .38, .45), (x1, .4, base - .85), (.09, .1, .12))
        for i in range(4):  # the awning, striped, sloping out over the pavement
            x0 = -w / 2 + w * i / 4
            b.add((x0, -1.1, base - 1.05), (x0 + w / 4, 0, base - .95), sign if i % 2 else trim)
    parts.append(b.mesh('walls', .82))
    if pane.verts:
        glass = _coloured('window glass', pane.verts, pane.faces, pane.tones, .06)
        parts.append(glass)
    if glow.verts:
        room = _coloured('lit windows', glow.verts, glow.faces, glow.tones, .5)
        nt = room.data.materials[0].node_tree
        pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        src = next(n for n in nt.nodes if n.type == 'VERTEX_COLOR')
        nt.links.new(src.outputs['Color'], _socket(pr, 'Emission Color', 'Emission'))
        _socket(pr, 'Emission Strength').default_value = .9
        parts.append(room)
    return _place(parts, at, turn, name)


def car(at=(0, 0, 0), turn: float = 0, colour='#20344f', lights: bool = False, name: str = 'car') -> bpy.types.Object:
    """A saloon car, 4.5 m long, nose towards +X before it is turned: curved body, glass, wheels, lamps. Stands well from 6 metres."""
    paint = material('car paint', colour, rough=.22, coat=1, metal=.3)
    glass = material('car glass', '#0d1114', rough=.06, coat=.5)
    # (x, half width, sill, height of the top): the body as sections from tail to nose
    sections = [(-2.25, .62, .42, .78), (-2.2, .78, .34, .92), (-1.9, .86, .3, .96), (-1.4, .9, .28, 1.0), (-.9, .9, .28, 1.32), (-.3, .9, .28, 1.4), (.3, .9, .28, 1.38), (.85, .9, .28, 1.02),
                (1.5, .9, .28, .92), (2.0, .84, .3, .8), (2.22, .68, .4, .66), (2.25, .5, .46, .56)]
    ring = 14
    verts, faces = [], []
    for x, w, low, top in sections:
        for i in range(ring):
            t = i / ring * 6.2832
            cz, hz = (low + top) / 2, (top - low) / 2
            c, s_ = math.cos(t), math.sin(t)
            # a rounded box: squarish, narrower towards the roof
            px = w * (abs(c) ** .45) * (1 if c > 0 else -1)
            pz = hz * (abs(s_) ** .55) * (1 if s_ > 0 else -1)
            if pz > hz * .2 and top > 1.05:
                px *= 1 - .24 * (pz - hz * .2) / (hz * .8)
            verts.append((x, px, cz + pz))
    for j in range(len(sections) - 1):
        for i in range(ring):
            faces.append((j * ring + i, j * ring + (i + 1) % ring, (j + 1) * ring + (i + 1) % ring, (j + 1) * ring + i))
    faces.append(tuple(range(ring - 1, -1, -1)))
    faces.append(tuple((len(sections) - 1) * ring + i for i in range(ring)))
    mesh = bpy.data.meshes.new('car body')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    body = bpy.data.objects.new('car body', mesh)
    bpy.context.collection.objects.link(body)
    apply(body, paint)
    m = body.modifiers.new('smooth', 'SUBSURF')
    m.levels = m.render_levels = 2
    parts = [body]
    for x0, x1, lean in ((-1.34, -.86, -1), (-.82, .78, 0), (.82, 1.3, 1)):  # the glass house
        if lean == 0:
            for side in (-1, 1):
                parts.append(box((x1 - x0, .02, .32), at=((x0 + x1) / 2, side * .775, 1.17), rot=(side * 12, 0, 0), mat=glass, bevel_width=0, name='side glass'))
        else:
            parts.append(box((.6, 1.4, .02), at=((x0 + x1) / 2, 0, 1.16), rot=(0, lean * 49, 0), mat=glass, bevel_width=0, name='screen'))
    rubber, rim = preset('rubber'), preset('aluminium')
    for x in (-1.4, 1.42):
        for side in (-1, 1):
            parts.append(cylinder(.33, .22, at=(x, side * .8, .33), rot=(90, 0, 0), mat=rubber, bevel_width=.03, sides=48, name='tyre'))
            parts.append(cylinder(.2, .01, at=(x, side * .915, .33), rot=(90, 0, 0), mat=rim, bevel_width=0, sides=32, name='wheel'))
    glow_on = 8 if lights else .05
    for side in (-1, 1):
        parts.append(box((.06, .3, .1), at=(2.21, side * .52, .72), mat=material('head lamp', '#fff4e0', glow='#fff4e0', glow_strength=glow_on), bevel_width=.01, name='lamp'))
        parts.append(box((.06, .34, .08), at=(-2.21, side * .55, .86), mat=material('tail lamp', '#7a0d0d', glow='#e01818', glow_strength=glow_on * .5), bevel_width=.01, name='lamp'))
    return _place(parts, at, turn, name)


def city_street(length: float = 120, road: float = 9, pavement: float = 3.5, night: bool = False, seed: int = 3, name: str = 'city street') -> bpy.types.Object:
    """A street running away along +Y from y=0: road with markings, kerbs, pavements, buildings down both sides, street trees and
    lamps, parked cars. Stand the camera on the pavement or the road at eye height, looking along +Y. night=True: lit windows and
    lamps, with c3d.dusk(); by day, c3d.sky()."""
    rng = random.Random(seed)
    half = road / 2
    asphalt = material('asphalt', '#2c2e31', rough=.55 if not night else .2, vary=.5, bump=.4, scale=9)
    slab = material('paving', '#8e8a84', rough=.8, vary=.4, bump=.25, scale=2)
    kerb = material('kerb', '#a7a39b', rough=.7, vary=.3, scale=8)
    paint = material('road paint', '#d8d6cc', rough=.6, vary=.3, scale=20)
    mid = length / 2
    parts = [box((road, length + 60, .1), at=(0, mid, -.05), mat=asphalt, bevel_width=0, name='road')]
    for side in (-1, 1):
        parts.append(box((pavement, length + 60, .16), at=(side * (half + pavement / 2), mid, .05), mat=slab, bevel_width=0, name='pavement'))
        parts.append(box((.16, length + 60, .17), at=(side * (half + .08), mid, .055), mat=kerb, bevel_width=.01, name='kerb'))
    y = 0
    while y < length + 30:
        parts.append(box((.14, 3, .004), at=(0, y, .002), mat=paint, bevel_width=0, name='road line'))
        y += 7
    for side in (-1, 1):
        y = -10.0
        i = 0
        while y < length + 40:
            wide = rng.uniform(11, 19)
            tall = rng.uniform(13, 27)
            colour = rng.choice(('#b5a795', '#a8634a', '#c9bfae', '#8d8478', '#b08b6a', '#d0c8ba'))
            parts.append(building(at=(side * (half + pavement), y + wide / 2, 0), turn=-side * 90, size=(wide - .06, 14, tall), colour=colour, lit=.55 if night else 0, seed=seed + i * 2 + side))
            y += wide
            i += 1
    for i in range(int(length / 16)):
        y = 6 + i * 16 + rng.uniform(-1, 1)
        for side in (-1, 1):
            x = side * (half + .9)
            if i % 2 == 0:
                parts.append(tree(at=(x, y + 8, .1), height=6.5, seed=i + (side > 0) * 3))
            parts.append(cylinder(.06, 6, at=(x, y, 3.1), mat=preset('iron'), bevel_width=0, sides=12, name='lamp post'))
            parts.append(sphere(.14, at=(x - side * .5, y, 6.05), mat=material('street lamp', '#ffe2b0', glow='#ffd9a0', glow_strength=16 if night else .2), name='street lamp'))
            parts.append(box((.5, .05, .05), at=(x - side * .25, y, 6.1), mat=preset('iron'), bevel_width=0, name='lamp arm'))
            if night:
                parts.append(point(at=(x - side * .5, y, 5.9), power=500, colour=kelvin(3000), radius=.15, name='street light'))
    for i in range(int(length / 11)):
        side = rng.choice((-1, 1))
        y = 8 + i * 11 + rng.uniform(-2, 2)
        parts.append(car(at=(side * (half - 1.15), y, 0), turn=90 if side > 0 else 90, colour=rng.choice(('#20344f', '#5a1414', '#b9bcc0', '#1c1d20', '#e4e3df', '#3a4a3a', '#6d6f72')), lights=False))
    return group(*parts, name=name)


def _cushion(size, at, mat, name='cushion'):
    """A soft block: puffed in the middle, rounded, slightly uneven, the way upholstery is."""
    from mathutils import noise

    w, d, h = size

    def make(bm):
        bmesh.ops.create_cube(bm, size=1)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=10, use_grid_fill=True)
        for v in bm.verts:
            x, y, z = v.co.x * 2, v.co.y * 2, v.co.z * 2
            round_ = 1 - .08 * (x * x * y * y + y * y * z * z + x * x * z * z)
            puff = 1 + .1 * (1 - x * x) * (1 - y * y)
            wob = 1 + noise.noise(Vector((x * 1.3 + at[0] * 7, y * 1.3, z * 1.3))) * .015
            v.co = Vector((x * w / 2 * round_ * wob, y * d / 2 * round_ * wob, z * h / 2 * (puff if z > 0 else 1) * round_))

    obj = _new(make, name)
    obj.data.polygons.foreach_set('use_smooth', [True] * len(obj.data.polygons))
    return _finish(obj, name, at, (0, 0, 0), preset(mat) if isinstance(mat, str) else mat, False)


def sofa(at=(0, 0, 0), turn: float = 0, width: float = 2.1, colour='#6d7480', name: str = 'sofa') -> bpy.types.Object:
    """A three-seat sofa, its seat facing -Y before it is turned: frame, arms, back, loose soft cushions, wooden feet."""
    cloth = preset('fabric', colour=colour)
    d = .92
    parts = [_cushion((width, d, .24), (0, 0, .28), cloth, 'frame'), _cushion((width, .24, .6), (0, d / 2 - .12, .6), cloth, 'back')]
    for side in (-1, 1):
        parts.append(_cushion((.22, d, .44), (side * (width / 2 - .11), 0, .52), cloth, 'arm'))
    seats = 3
    wide = (width - .44) / seats
    for i in range(seats):
        x = -width / 2 + .22 + wide * (i + .5)
        parts.append(_cushion((wide - .01, d - .3, .17), (x, -.1, .47), cloth, 'seat'))
        parts.append(_cushion((wide - .03, .2, .42), (x, d / 2 - .32, .76), cloth, 'back cushion'))
        parts[-1].rotation_euler.x = math.radians(-9)
    feet = preset('wood')
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cylinder(.025, .15, at=(sx * (width / 2 - .08), sy * (d / 2 - .08), .075), mat=feet, sides=16, name='foot'))
    return _place(parts, at, turn, name)


def rug(at=(0, 0, 0), turn: float = 0, size=(2.4, 1.6), colour='#8a4a3a', edge='#d8cdb8', name: str = 'rug') -> bpy.types.Object:
    """A woven rug on the floor: a bordered field with a soft worn pattern and real thickness."""
    w, d = size
    mat = material('rug', colour, rough=.95, bump=.9, scale=160)
    nt = mat.node_tree
    pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    bricks = nt.nodes.new('ShaderNodeTexChecker')
    bricks.inputs['Scale'].default_value = 6
    bricks.inputs['Color1'].default_value = _rgba(colour)
    bricks.inputs['Color2'].default_value = tuple(c * .72 for c in _rgba(colour)[:3]) + (1,)
    nt.links.new(coord.outputs['Object'], bricks.inputs['Vector'])
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], split.inputs[0])
    wear = nt.nodes.new('ShaderNodeTexNoise')
    wear.inputs['Scale'].default_value = 3
    nt.links.new(coord.outputs['Object'], wear.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = .5
    nt.links.new(bricks.outputs[0], mix.inputs[1])
    nt.links.new(wear.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], pr.inputs['Base Color'])
    border = material('rug border', edge, rough=.95, bump=.9, scale=160)
    body = box((w - .16, d - .16, .012), at=(0, 0, .006), mat=mat, bevel_width=.002, name='rug field')
    frame = box((w, d, .01), at=(0, 0, .005), mat=border, bevel_width=.002, name='rug border')
    return _place([frame, body], at, turn, name)


def coffee_table(at=(0, 0, 0), turn: float = 0, size=(1.1, .6, .42), mat='wood', name: str = 'coffee table') -> bpy.types.Object:
    """A low table, its top at 42 cm."""
    return table(at=at, turn=turn, size=size, mat=mat, name=name)


def bookshelf(at=(0, 0, 0), turn: float = 0, size=(1.2, .3, 2), colour='#5b3f28', seed: int = 2, name: str = 'bookshelf') -> bpy.types.Object:
    """A tall shelf against a wall, open towards -Y before it is turned, full of books of every size, some leaning, some gaps."""
    rng = random.Random(seed)
    w, d, h = size
    wood_mat = wood(colour=colour, scale=9)
    t = .022
    parts = [box((w, t, h), at=(0, d / 2 - t / 2, h / 2), mat=wood_mat, bevel_width=.002, name='back')]
    for side in (-1, 1):
        parts.append(box((t, d, h), at=(side * (w / 2 - t / 2), 0, h / 2), mat=wood_mat, bevel_width=.002, name='side'))
    levels = max(3, int(h / .34))
    spines = _Blocks()
    tints = ('#7a2e2a', '#22495c', '#2f4a36', '#c9b48a', '#3a3a44', '#8a6a2a', '#d8cdb8', '#4a2f22', '#5a2f4a')
    for i in range(levels + 1):
        z = i * (h - t) / levels + t / 2
        parts.append(box((w - 2 * t, d - t, t), at=(0, -t / 2, z), mat=wood_mat, bevel_width=.002, name='shelf'))
        if i == levels:
            break
        x = -w / 2 + t + .01
        room = (h - t) / levels - t
        while x < w / 2 - t - .04:
            if rng.random() < .1:
                x += rng.uniform(.06, .18)
                continue
            wide = rng.uniform(.018, .05)
            tall = room * rng.uniform(.62, .9)
            deep = d * rng.uniform(.6, .82)
            tone = tuple(c * rng.uniform(.75, 1.15) for c in _rgba(rng.choice(tints))[:3])
            spines.add((x, -d / 2 + (d - deep) * .3, z + t / 2), (x + wide, -d / 2 + (d - deep) * .3 + deep, z + t / 2 + tall), tone)
            x += wide + rng.uniform(0, .004)
    parts.append(spines.mesh('books', .55))
    return _place(parts, at, turn, name)


def floor_lamp(at=(0, 0, 0), turn: float = 0, warm: float = 3000, power: float = 30, name: str = 'floor lamp') -> bpy.types.Object:
    """A standing lamp, 1.6 m tall, with a cloth shade that glows."""
    metal = preset('brass')
    k = kelvin(warm)
    base = cylinder(.14, .025, at=(0, 0, .0125), mat=metal, sides=48, name='lamp foot')
    pole = cylinder(.011, 1.4, at=(0, 0, .72), mat=metal, bevel_width=0, sides=16, name='lamp pole')
    shade_mat = material('lamp shade', '#efe3cc', rough=.8, glow=k, glow_strength=2.2, soft=.3)
    shade = lathe([(.1, .28), (.102, .28), (.17, 0), (.168, 0), (.098, .28)], at=(0, 0, 1.32), mat=shade_mat, name='shade')
    return _place([base, pole, shade, point(at=(0, 0, 1.42), power=power, colour=k, radius=.06, name='lamp light')], at, turn, name)


def picture(at=(0, 0, 1.5), turn: float = 0, size=(.7, .5), mat=None, name: str = 'picture') -> bpy.types.Object:
    """A framed picture on a wall behind it (the wall on +Y before it is turned): a soft abstract in muted colours."""
    w, h = size
    canvas = material('canvas', '#b8a98c', rough=.6, vary=1, bump=.3, scale=3) if mat is None else mat
    return _place([box((w + .05, .025, h + .05), at=(0, 0, 0), mat=preset('paint', colour='#20201f'), bevel_width=.002, name='frame'),
                   box((w, .006, h), at=(0, -.012, 0), mat=preset('paper', colour='#ece3cf'), bevel_width=0, name='mount'),
                   box((w * .72, .004, h * .72), at=(0, -.016, 0), mat=canvas, bevel_width=0, name='canvas')], at, turn, name)


def curtains(at=(0, 0, 2.5), width: float = 3, height: float = 2.3, colour='#d8d0c0', gather: float = .28, name: str = 'curtains') -> bpy.types.Object:
    """Two drawn-back curtains hanging from `at` (the middle of the rail), their folds real, on either side of a window on +Y."""
    mat = preset('fabric', colour=colour, rough=.8, soft=.2)

    def panel(cx, wide):
        cols, rows = 90, 40
        verts, faces = [], []
        for j in range(rows + 1):
            t = j / rows
            for i in range(cols + 1):
                u = i / cols
                x = cx + (u - .5) * wide * (1 + t * .06)
                y = math.sin(u * 60 + t * 1.5) * .045 * (.7 + .5 * t) + math.sin(u * 23 + 1) * .02
                verts.append((x, y, -t * height))
        faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i) for j in range(rows) for i in range(cols)]
        mesh = bpy.data.meshes.new('curtain')
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
        obj = bpy.data.objects.new('curtain', mesh)
        bpy.context.collection.objects.link(obj)
        apply(obj, mat)
        return obj

    wide = width * gather
    rail = cylinder(.012, width + .3, at=(0, 0, .03), rot=(0, 90, 0), mat=preset('iron'), bevel_width=0, sides=12, name='rail')
    return _place([rail, panel(-width / 2 + wide / 2, wide), panel(width / 2 - wide / 2, wide)], at, 0, name)


def cottage(at=(0, 0, 0), turn: float = 0, size=(8, 6, 2.8), colour='#d8cdb8', roof='#5a4034', lit: bool = False, snow: float = 0, seed: int = 2, name: str = 'cottage') -> bpy.types.Object:
    """A small country house standing on `at`, its door on the -Y side before it is turned: thick walls, deep windows with shutters,
    a steep tiled roof with eaves, a chimney. lit=True: warm windows at night. snow 0..1 covers the roof."""
    rng = random.Random(seed)
    w, d, h = size
    wall, wood_tone = _rgba(colour), _rgba('#3f3026')
    stone = _rgba('#6b655c')
    b, glass, glow = _Blocks(), _Blocks(), _Blocks()
    b.add((-w / 2, 0, 0), (w / 2, d, .35), stone)
    bays = max(2, int(w // 2.4))
    bay = w / bays
    depth = .28
    top, sill = h - .55, 1.0
    door = bays // 2
    b.add((-w / 2 + .02, depth, .3), (w / 2 - .02, d, h), wall)
    b.add((-w / 2 + .02, .02, .3), (w / 2 - .02, depth, sill if False else .95), wall)
    b.add((-w / 2 + .02, .02, top), (w / 2 - .02, depth, h), wall)
    for i in range(bays + 1):  # piers between the openings
        x = -w / 2 + i * bay
        half = (bay - .9) / 2
        b.add((x - half if i else x, .02, .95), (x + half if i < bays else x, depth, top), wall)
    for i in range(bays):
        x = -w / 2 + (i + .5) * bay
        if i == door:
            b.add((x - .45, .02, .3), (x + .45, depth, 2.1), wall)
            b.add((x - .5, -.04, 0), (x + .5, .08, 2.18), wood_tone)
            b.add((x - .42, -.08, .05), (x + .42, .05, 2.1), _rgba('#4f2f22'))
            b.add((x + .3, -.11, .98), (x + .36, -.06, 1.04), (.7, .6, .3))
            continue
        (glow if lit else glass).add((x - .45, depth - .06, .95), (x + .45, depth - .03, top), _rgba(kelvin(3000)) if lit else (.08, .09, .1))
        for u in (-1, 0, 1):
            b.add((x + u * .45 - .025, depth - .1, .95), (x + u * .45 + .025, depth - .02, top), (.2, .16, .13))
        b.add((x - .45, depth - .1, (.95 + top) / 2), (x + .45, depth - .02, (.95 + top) / 2 + .05), (.2, .16, .13))
        b.add((x - .55, -.1, .87), (x + .55, .1, .95), stone)
        for side in (-1, 1):
            b.add((x + side * .5, -.04, .95), (x + side * .9, .03, top), _rgba('#46604e'))
    rise = d * .62
    over = .45
    ridge = h + rise
    ends = [(-w / 2 - over, 0), (w / 2 + over, 0)]
    verts = [(x, -over, h - over * rise / (d / 2)) for x, _ in ends] + [(x, d / 2, ridge) for x, _ in ends] + [(x, d + over, h - over * rise / (d / 2)) for x, _ in ends]
    verts += [(x, y, z + .12) for x, y, z in verts]
    faces = [(0, 1, 3, 2), (2, 3, 5, 4), (6, 8, 9, 7), (8, 10, 11, 9), (0, 6, 7, 1), (4, 5, 11, 10), (0, 2, 8, 6), (2, 4, 10, 8), (1, 7, 9, 3), (3, 9, 11, 5)]
    mesh = bpy.data.meshes.new('roof')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    roof_obj = bpy.data.objects.new('roof', mesh)
    bpy.context.collection.objects.link(roof_obj)
    apply(roof_obj, _tiles(roof, snow))
    gable = bpy.data.meshes.new('gable')  # the two triangles of wall under the roof
    gable.from_pydata([(-w / 2 + .02, .02, h), (-w / 2 + .02, d, h), (-w / 2 + .02, d / 2, ridge), (w / 2 - .02, .02, h), (w / 2 - .02, d, h), (w / 2 - .02, d / 2, ridge)], [],
                      [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (0, 2, 5, 3), (1, 4, 5, 2)])
    gable.update()
    end = bpy.data.objects.new('gable', gable)
    bpy.context.collection.objects.link(end)
    apply(end, material('gable wall', colour, rough=.85, vary=.15, bump=.2, scale=5))
    chim = box((.6, .6, 1.6), at=(w * .28, d * .68, ridge - .25), mat=material('chimney', '#6e4d40', rough=.85, vary=.5, bump=.6, scale=9), name='chimney')
    parts = [b.mesh('walls', .85), roof_obj, end, chim]
    if glass.verts:
        parts.append(_coloured('window glass', glass.verts, glass.faces, glass.tones, .06))
    if glow.verts:
        room = _coloured('lit windows', glow.verts, glow.faces, glow.tones, .5)
        nt = room.data.materials[0].node_tree
        pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        src = next(n for n in nt.nodes if n.type == 'VERTEX_COLOR')
        nt.links.new(src.outputs['Color'], _socket(pr, 'Emission Color', 'Emission'))
        _socket(pr, 'Emission Strength').default_value = 2.2
        parts.append(room)
        parts.append(point(at=(0, -1.6, 1.7), power=70, colour=kelvin(3000), radius=.3, name='light from the windows'))
    return _place(parts, at, turn, name)


def _tiles(colour, snow: float) -> bpy.types.Material:
    """Rows of roof tiles by colour and relief, in the roof's own coordinates; snow lies over them, thickest high up."""
    mat = material('roof tiles', colour, rough=.7)
    nt = mat.node_tree
    pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    bricks = nt.nodes.new('ShaderNodeTexBrick')
    base = _rgba(colour)
    bricks.inputs['Color1'].default_value = base
    bricks.inputs['Color2'].default_value = tuple(c * .78 for c in base[:3]) + (1,)
    bricks.inputs['Mortar'].default_value = tuple(c * .4 for c in base[:3]) + (1,)
    bricks.inputs['Scale'].default_value = 3.4
    bricks.inputs['Mortar Size'].default_value = .012
    swap = nt.nodes.new('ShaderNodeMapping')
    swap.inputs['Rotation'].default_value = (1.1, 0, 0)
    nt.links.new(coord.outputs['Object'], swap.inputs['Vector'])
    nt.links.new(swap.outputs[0], bricks.inputs['Vector'])
    relief = nt.nodes.new('ShaderNodeBump')
    relief.inputs['Strength'].default_value = .8
    relief.inputs['Distance'].default_value = .03
    nt.links.new(bricks.outputs['Fac'], relief.inputs['Height'])
    nt.links.new(relief.outputs['Normal'], pr.inputs['Normal'])
    if not snow:
        nt.links.new(bricks.outputs['Color'], pr.inputs['Base Color'])
        return mat
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = .9
    noise.inputs['Detail'].default_value = 6
    nt.links.new(coord.outputs['Object'], noise.inputs['Vector'])
    cover = nt.nodes.new('ShaderNodeMapRange')
    cover.inputs['From Min'].default_value, cover.inputs['From Max'].default_value = .66 - .52 * snow, .72 - .52 * snow
    nt.links.new(noise.outputs[0], cover.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMixRGB')
    nt.links.new(cover.outputs[0], mix.inputs[0])
    nt.links.new(bricks.outputs['Color'], mix.inputs[1])
    mix.inputs[2].default_value = _rgba('#eef2f7')
    nt.links.new(mix.outputs[0], pr.inputs['Base Color'])
    return mat


def fence(points, height: float = 1.1, gap: float = 2.2, colour='#5b4a3a', name: str = 'fence') -> bpy.types.Object:
    """A country fence along [(x, y), ...] on the land: posts and two rails, not quite straight."""
    rng = random.Random(3)
    b = _Blocks()
    base = _rgba(colour)
    for u, v in zip(points, points[1:]):
        length = math.hypot(v[0] - u[0], v[1] - u[1])
        n = max(1, int(length / gap))
        marks = [(u[0] + (v[0] - u[0]) * i / n, u[1] + (v[1] - u[1]) * i / n) for i in range(n + 1)]
        for p0 in marks:
            g = land_z(*p0)
            lean = rng.uniform(-.04, .04)
            tone = tuple(c * rng.uniform(.75, 1.15) for c in base[:3])
            b.add((p0[0] - .05 + lean, p0[1] - .05, g - .1), (p0[0] + .05 + lean, p0[1] + .05, g + height + rng.uniform(-.06, .06)), tone)
        for a, c in zip(marks, marks[1:]):
            for rail in (.45, .9):
                steps = 6
                for k in range(steps):
                    t0, t1 = k / steps, (k + 1) / steps
                    x0, y0 = a[0] + (c[0] - a[0]) * t0, a[1] + (c[1] - a[1]) * t0
                    x1, y1 = a[0] + (c[0] - a[0]) * t1, a[1] + (c[1] - a[1]) * t1
                    z = land_z(x0, y0) + height * rail
                    wide = .03
                    b.add((min(x0, x1) - wide, min(y0, y1) - wide, z), (max(x0, x1) + wide, max(y0, y1) + wide, z + .07), tuple(c2 * .9 for c2 in base[:3]))
    return b.mesh(name, .85)


def snowfall(at=(0, 8, 0), size=(30, 30, 10), count: int = 5000, seed: int = 4, name: str = 'snowfall') -> bpy.types.Object:
    """Flakes falling in the air in front of the camera: put `at` between the camera and the subject. They blur with depth of field."""
    rng = random.Random(seed)
    verts, faces, tones = [], [], []
    for _ in range(count):
        x, y, z = rng.uniform(-size[0] / 2, size[0] / 2), rng.uniform(-size[1] / 2, size[1] / 2), rng.uniform(0, size[2])
        r = rng.uniform(.006, .02)
        n = len(verts)
        verts += [(x - r, y, z), (x, y, z + r * rng.uniform(1, 2.6)), (x + r, y, z), (x, y, z - r * rng.uniform(1, 2.6))]
        faces.append((n, n + 1, n + 2, n + 3))
        tones += [(1, 1, 1)] * 4
    obj = _coloured(name, verts, faces, tones, .5)
    nt = obj.data.materials[0].node_tree  # flakes catch the light of the whole sky: white even against it
    pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    _socket(pr, 'Emission Color', 'Emission').default_value = (1, 1, 1, 1)
    _socket(pr, 'Emission Strength').default_value = .55
    obj.location = at
    obj.visible_shadow = False
    return obj


def boat(at=(0, 0, 0), turn: float = 0, length: float = 4.2, colour='#7d6650', stripe='#2f4d5c', tilt: float = 6, name: str = 'boat') -> bpy.types.Object:
    """A wooden rowing boat lying on the beach or afloat: an open hull of overlapping planks with a stem and a transom, ribs,
    three seats, a pair of oars. tilt leans it on one side, as a boat does when it is stranded. Its bow points to +X."""
    k = length / 4.2
    planks = 6
    stations = 34
    outer, inner = [], []

    def section(t):
        """Half width, depth below the rail, and sheer (rise of the rail) at t from -1 (stern) to 1 (bow)."""
        wide = .72 * (1 - abs(t) ** 2.4 if t > 0 else 1 - abs(t) ** 3.4 * .42) ** .9
        deep = .46 * (1 - abs(t) ** 3) + .06
        sheer = .1 + .26 * t ** 2 * (1.2 if t > 0 else .5)
        return max(.004, wide), deep, sheer

    verts, faces, tones = [], [], []
    tone_a, tone_b = _rgba(colour), _rgba(stripe)
    rng = random.Random(4)
    for skin, grow in ((0, .0), (1, -.028)):  # the outside, and a thin wall in from it
        start = len(verts)
        for i in range(stations + 1):
            t = i / stations * 2 - 1
            w, d, sh = section(t)
            w, d = max(.002, w + grow), d + grow
            x = t * 2.05
            for j in range(-planks, planks + 1):
                u = j / planks
                a = abs(u)
                # a round-bilged section, in steps: each plank overlaps the one below it
                y = w * max(0, math.sin(a * 1.5708)) ** .72 * (1 if u >= 0 else -1)
                z = sh - d * max(0, math.cos(a * 1.5708)) ** .78
                step = abs(round(a * planks) - a * planks)
                verts.append((x, y * (1 + step * .012), z))
                strake = round(a * planks)
                wet = strake >= planks - 1
                base = tone_b if wet else tone_a
                light = .82 + .3 * ((strake * 7 + i // 11) % 5) / 5
                tones.append(tuple(c * light * (.55 if skin else 1) * rng.uniform(.95, 1.05) for c in base[:3]))
        row = planks * 2 + 1
        for i in range(stations):
            for j in range(row - 1):
                a, b, c, d = start + i * row + j, start + i * row + j + 1, start + (i + 1) * row + j + 1, start + (i + 1) * row + j
                faces.append((a, b, c, d) if not skin else (a, d, c, b))
    row = planks * 2 + 1
    half = len(verts) // 2
    for i in range(stations):  # the top edge between the two skins
        for side in (0, row - 1):
            a, b = i * row + side, (i + 1) * row + side
            faces.append((a, b, half + b, half + a))
    for j in range(row - 1):  # the transom closes the stern
        faces.append((j, j + 1, half + j + 1, half + j))
    hull = _coloured('hull', verts, faces, tones, .6)
    hull.data.polygons.foreach_set('use_smooth', [False] * len(hull.data.polygons))
    wood_mat = wood(colour='#6b523c', scale=9)
    parts = [hull]
    for t, y0 in ((-.45, .62), (0, .68), (.42, .55)):
        w, d, sh = section(t)
        parts.append(box((.24, 2 * w * .9, .03), at=(t * 2.05, 0, sh - .14), mat=wood_mat, bevel_width=.004, name='seat'))
    for i in range(-5, 6):  # ribs
        t = i / 6.2
        w, d, sh = section(t)
        pts = [(t * 2.05, q * w * .92, sh - d * .92 * (1 - abs(q) ** 2.2)) for q in (-1, -.6, 0, .6, 1)]
        parts.append(tube(pts, .012, mat=wood_mat, name='rib'))
    oar = wood(colour='#a08a6a', scale=8)
    for side, lean in ((-1, 2), (1, -3)):
        parts.append(cylinder(.022, 2.3, at=(-.1, side * .22, .24), rot=(0, 90, lean), mat=oar, bevel_width=0, sides=12, name='oar'))
        parts.append(box((.5, .13, .012), at=(1.2, side * .24 + lean * .022, .24), rot=(0, 0, lean), mat=oar, bevel_width=.003, name='oar blade'))
    whole = group(*parts, at=(at[0], at[1], at[2] + .42 * k), rot=(tilt, 0, turn), name=name)
    whole.scale = (k, k, k)
    return whole


def campfire(at=(0, 0, 0), size: float = 1, power: float = 260, name: str = 'campfire') -> bpy.types.Object:
    """A small fire on the ground: a ring of stones, crossed logs, flames that glow, and the warm light they throw. Bright enough
    to light a tent and faces at night."""
    rng = random.Random(3)
    bark = material('charred', '#17120e', rough=.9, vary=.8, bump=1, scale=14)
    parts = []
    for i in range(10):
        a = i / 10 * 6.2832
        parts.append(rock(at=(math.cos(a) * .42, math.sin(a) * .42, 0), size=.17, seed=i + 1, name='ring stone'))
    for i in range(5):
        a = i / 5 * 6.2832 + .3
        lo = Vector((math.cos(a) * .36, math.sin(a) * .36, .03))
        parts.append(tube([tuple(lo), (math.cos(a) * .14, math.sin(a) * .14, .2), (0, 0, .34)], .036, end=.018, mat=bark, name='log'))
    flame = material('flame', '#ff8a2a', glow='#ff6a12', glow_strength=9, rough=.5)
    core = material('flame core', '#ffe08a', glow='#ffb040', glow_strength=20, rough=.5)
    for i in range(16):
        a = rng.uniform(0, 6.2832)
        r = rng.uniform(0, .13)
        h = rng.uniform(.28, .7)
        base = (math.cos(a) * r, math.sin(a) * r, .06)
        tip = (base[0] * .3 + rng.uniform(-.05, .05), base[1] * .3 + rng.uniform(-.05, .05), .06 + h)
        mid = ((base[0] + tip[0]) / 2 + rng.uniform(-.04, .04), (base[1] + tip[1]) / 2 + rng.uniform(-.04, .04), .06 + h * .45)
        parts.append(tube([base, mid, tip], .058, end=.002, mat=core if i % 3 == 0 else flame, name='flame'))
    parts.append(point(at=(0, 0, .55), power=power, colour=kelvin(1900), radius=.25, name='fire light'))
    whole = group(*parts, at=at, name=name)
    whole.scale = (size, size, size)
    return whole


def tent(at=(0, 0, 0), turn: float = 0, colour='#c98a3a', glow: float = 0, name: str = 'tent') -> bpy.types.Object:
    """A two-man ridge tent, its open door towards -Y before it is turned, with poles and guy lines. glow lights it from inside."""
    w, d, h = 1.7, 2.3, 1.15
    verts = [(-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (0, -d / 2 - .1, h), (-w / 2, d / 2, 0), (w / 2, d / 2, 0), (0, d / 2 + .1, h)]
    faces = [(0, 3, 5, 2), (1, 2, 5, 4), (3, 4, 5)]
    fine = []
    mesh = bpy.data.meshes.new('fly')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new('fly', mesh)
    bpy.context.collection.objects.link(obj)
    subdivide(obj, 3)
    obj.modifiers[-1].subdivision_type = 'SIMPLE'
    mat = preset('fabric', colour=colour, rough=.6, bump=.4, scale=120)
    if glow:
        pr = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        _socket(pr, 'Emission Color', 'Emission').default_value = _rgba(kelvin(2600))
        _socket(pr, 'Emission Strength').default_value = glow
    apply(obj, mat)
    inner = box((w - .1, .02, .02), at=(0, 0, .01), mat=preset('fabric', colour='#2a2622'), bevel_width=0, name='groundsheet')
    dark = bpy.data.meshes.new('door')  # the dark inside, seen through the door
    dark.from_pydata([(-w / 2 + .04, -d / 2 + .05, .01), (w / 2 - .04, -d / 2 + .05, .01), (0, -d / 2 - .04, h - .06)], [], [(0, 1, 2)])
    dark.update()
    door = bpy.data.objects.new('door', dark)
    bpy.context.collection.objects.link(door)
    apply(door, material('inside', '#0a0806', rough=.9, glow=kelvin(2600) if glow else None, glow_strength=glow * .4))
    parts = [obj, inner, door]
    for y, zlift in ((-d / 2 - .1, 0), (d / 2 + .1, 0)):
        parts.append(cylinder(.008, h + .02, at=(0, y, h / 2), mat=preset('aluminium'), bevel_width=0, sides=8, name='pole'))
    rope = material('guy line', '#b8b0a0', rough=.8)
    for x, y in ((-1.3, -1.5), (1.3, -1.5), (-1.3, 1.5), (1.3, 1.5)):
        parts.append(tube([(0, y * .84, h), (x, y, 0)], .003, mat=rope, name='guy line'))
    return _place(parts, at, turn, name)


def palm(at=(0, 0, 0), height: float = 8, seed: int = 2, lean: float = 10, name: str = 'palm') -> bpy.types.Object:
    """A coconut palm: a ringed curving trunk and long drooping fronds, each with hundreds of leaflets."""
    rng = random.Random(seed)
    a = rng.uniform(0, 6.2832)
    dx, dy = math.cos(a), math.sin(a)
    tip = lean / 45
    pts = [Vector((dx * height * tip * t ** 1.8, dy * height * tip * t ** 1.8, height * t)) for t in (0, .25, .5, .75, 1)]
    bark = material('palm bark', '#6b5a48', rough=.9, vary=.6, bump=1, scale=5)
    nt = bark.node_tree
    pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], split.inputs[0])
    rings = nt.nodes.new('ShaderNodeMath')
    rings.operation = 'SINE'
    times = nt.nodes.new('ShaderNodeMath')
    times.operation = 'MULTIPLY'
    times.inputs[1].default_value = 34
    nt.links.new(split.outputs['Z'], times.inputs[0])
    nt.links.new(times.outputs[0], rings.inputs[0])
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = .9
    b.inputs['Distance'].default_value = .03
    nt.links.new(rings.outputs[0], b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], pr.inputs['Normal'])
    trunk = tube([tuple(q) for q in pts], height * .028, end=height * .015, mat=bark, name='trunk')
    head = pts[-1]
    verts, faces, tones = [], [], []
    green = _rgba('#3d6a2c')
    fronds = 20
    for f in range(fronds):
        turn_a = f * 2.4 + rng.uniform(-.2, .2)
        rise = rng.uniform(-.2, .75)
        long = height * rng.uniform(.34, .46)
        out = Vector((math.cos(turn_a), math.sin(turn_a), 0))
        side = Vector((-out.y, out.x, 0))
        steps = 34
        for i in range(steps):
            t = i / steps
            spine = head + out * long * t + Vector((0, 0, long * (rise * t - .9 * t * t * t)))
            down = Vector((0, 0, -1))
            size = long * .24 * math.sin(math.pi * min(1, t * 1.02 + .08)) ** .7
            for s_ in (-1, 1):
                for k in range(3):
                    n = len(verts)
                    root = spine + out * (k * long / steps / 3)
                    far = root + side * s_ * size + down * size * .55 + out * size * .35
                    w_ = out * long * .007
                    verts += [tuple(root - w_), tuple(root + w_), tuple(far + w_ * .2), tuple(far - w_ * .2)]
                    faces.append((n, n + 1, n + 2, n + 3))
                    light = rng.uniform(.8, 1.25) * (.8 + .4 * max(0, 1 - t))
                    yellowed = rng.uniform(.95, 1.25)
                    tones += [(green[0] * light * yellowed, green[1] * light, green[2] * light)] * 4
    return _place([trunk, _coloured('fronds', verts, faces, tones, .42, 0, .3)], at, 0, name)


def wine_glass(at=(0, 0, 0), turn: float = 0, wine: str = 'red', name: str = 'wine glass') -> bpy.types.Object:
    """A stemmed wine glass, 21 cm tall. wine: red, white or None."""
    glass_mat = preset('glass')
    bowl = lathe([(0, 0), (.036, 0), (.036, .001), (.012, .004), (.0035, .012), (.0032, .08), (.0035, .1), (.02, .115), (.038, .145), (.04, .17), (.034, .21),
                  (.0335, .21), (.0385, .17), (.0365, .146), (.02, .118), (0, .106)], mat=glass_mat, name='glass')
    parts = [bowl]
    if wine:
        colour = '#9c1a2e' if wine == 'red' else '#e6d27a'
        liquid = lathe([(0, .108), (.02, .12), (.036, .147), (.0375, .155), (0, .155)], mat=material('wine', colour, rough=.03, glass=1, ior=1.34), name='wine')
        parts.append(liquid)
    return _place(parts, at, turn, name)


def _printed(colour) -> bpy.types.Material:
    """Paper with print: two ruled lines and a dark band where a name would be."""
    mat = preset('paper', colour=colour)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], split.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    ink = (.05, .04, .04, 1)
    paper = (1, 1, 1, 1)
    bands = ((.0, paper), (.16, ink), (.175, paper), (.42, ink), (.62, paper), (.84, ink), (.855, paper))
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = bands[0]
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = bands[1]
    for at, tone in bands[2:]:
        e = ramp.color_ramp.elements.new(at)
        e.color = tone
    height = nt.nodes.new('ShaderNodeMapRange')  # the label is .08 tall around its middle
    height.inputs['From Min'].default_value, height.inputs['From Max'].default_value = -.04, .04
    nt.links.new(split.outputs['Z'], height.inputs['Value'])
    nt.links.new(height.outputs[0], ramp.inputs['Fac'])
    tint = nt.nodes.new('ShaderNodeMixRGB')
    tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1
    was = p.inputs['Base Color'].links[0].from_socket if p.inputs['Base Color'].links else None
    if was is not None:
        nt.links.new(was, tint.inputs[1])
    else:
        tint.inputs[1].default_value = _rgba(colour)
    nt.links.new(ramp.outputs['Color'], tint.inputs[2])
    nt.links.new(tint.outputs[0], p.inputs['Base Color'])
    return mat


def bottle(at=(0, 0, 0), turn: float = 0, colour='#1f3a26', label='#e8e0cc', name: str = 'bottle') -> bpy.types.Object:
    """A wine bottle, 30 cm tall, dark glass with a paper label."""
    mat = material('bottle glass', colour, rough=.08, coat=.5, glass=.35, ior=1.5)
    body = lathe([(0, 0), (.036, 0), (.036, 0), (.0375, .006), (.0375, .006), (.0375, .19), (.034, .215), (.016, .24), (.0145, .29), (.0165, .292), (.0165, .3), (0, .3)], mat=mat, name='bottle')
    paper = cylinder(.038, .08, at=(0, 0, .1), mat=_printed(label), bevel_width=0, name='label')
    foil = cylinder(.0168, .055, at=(0, 0, .272), mat=preset('copper', colour='#7a2a2a'), bevel_width=0, name='foil')
    return _place([body, paper, foil], at, turn, name)


def vase(at=(0, 0, 0), turn: float = 0, height: float = .3, mat='ceramic', name: str = 'vase') -> bpy.types.Object:
    """A turned vase, hollow at the neck."""
    k = height / .3
    v = lathe([(0, 0), (.05 * k, 0), (.05 * k, 0), (.07 * k, .03 * k), (.095 * k, .11 * k), (.08 * k, .19 * k), (.04 * k, .25 * k), (.036 * k, .28 * k), (.048 * k, .3 * k),
               (.044 * k, .3 * k), (.032 * k, .28 * k), (0, .2 * k)], mat=mat, name='body')
    return _place([v], at, turn, name)


def plate(at=(0, 0, 0), turn: float = 0, radius: float = .13, colour='#f3efe7', name: str = 'plate') -> bpy.types.Object:
    """A dinner plate."""
    r = radius
    p = lathe([(0, 0), (r * .6, 0), (r * .6, 0), (r * .66, .003), (r * .95, .018), (r, .022), (r * .99, .024), (r * .93, .021), (r * .64, .007), (0, .006)], mat=preset('porcelain', colour=colour), name='plate')
    return _place([p], at, turn, name)


def _apple_skin(colour) -> bpy.types.Material:
    """Skin that runs in streaks along the fruit: polar coordinates, noise stretched from top to bottom."""
    mat = material('apple skin', colour, rough=.34, coat=.25, soft=.2)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], split.inputs[0])
    angle = nt.nodes.new('ShaderNodeMath')
    angle.operation = 'ARCTAN2'
    nt.links.new(split.outputs['Y'], angle.inputs[0])
    nt.links.new(split.outputs['X'], angle.inputs[1])
    polar = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(angle.outputs[0], polar.inputs['X'])
    high = nt.nodes.new('ShaderNodeMath')
    high.operation = 'MULTIPLY'
    high.inputs[1].default_value = 2.2
    nt.links.new(split.outputs['Z'], high.inputs[0])
    nt.links.new(high.outputs[0], polar.inputs['Y'])
    streaks = nt.nodes.new('ShaderNodeTexNoise')
    streaks.inputs['Scale'].default_value = 9
    streaks.inputs['Detail'].default_value = 6
    nt.links.new(polar.outputs[0], streaks.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    base = _rgba(colour)
    pale = tuple(min(1, a * .55 + b * .45) for a, b in zip(base[:3], (.78, .62, .2)))
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = .3, .5
    ramp.color_ramp.elements[0].color = (*pale, 1)
    ramp.color_ramp.elements[1].color = (*[c * .8 for c in base[:3]], 1)
    nt.links.new(streaks.outputs[0], ramp.inputs['Fac'])
    top = nt.nodes.new('ShaderNodeMapRange')  # the sun never reaches the dimple
    top.inputs['From Min'].default_value, top.inputs['From Max'].default_value = .05, .068
    nt.links.new(split.outputs['Z'], top.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMixRGB')
    nt.links.new(top.outputs[0], mix.inputs[0])
    nt.links.new(ramp.outputs['Color'], mix.inputs[1])
    mix.inputs[2].default_value = (*pale, 1)
    nt.links.new(mix.outputs[0], p.inputs['Base Color'])
    return mat


def apple(at=(0, 0, 0), turn: float = 0, colour='#a8261e', name: str = 'apple') -> bpy.types.Object:
    """An apple, not quite round, streaked from stem to base, paler round the dimple, with a stem."""
    mat = _apple_skin(colour)
    body = lathe([(0, .004), (.012, .002), (.03, .012), (.039, .032), (.038, .052), (.026, .068), (.011, .07), (.003, .06), (0, .058)], mat=mat, segments=48, name='apple')
    stem = tube([(0, 0, .058), (.001, .001, .07), (.005, .002, .082)], .0013, mat=material('stem', '#4a3220', rough=.7), name='stem')
    return _place([body, stem], at, turn, name)


def bowl(at=(0, 0, 0), radius: float = .13, mat='ceramic', name: str = 'bowl') -> bpy.types.Object:
    """A deep bowl with a foot; things can lie in it."""
    r, h = radius, radius * .62
    return _place([lathe([(0, 0), (r * .42, 0), (r * .44, 0), (r * .46, h * .1), (r * .8, h * .55), (r, h), (r * .985, h * 1.015), (r * .955, h), (r * .76, h * .58), (r * .42, h * .2), (0, h * .16)],
                         mat=mat, segments=96, name=name)], at, 0, f'{name} whole')


def orange(at=(0, 0, 0), radius: float = .04, colour='#e8872a', name: str = 'orange') -> bpy.types.Object:
    """A citrus fruit with pitted skin: an orange, or a lemon with colour='#e6c63a'."""
    mat = material('peel', colour, rough=.42, vary=.2, scale=30, coat=.15, soft=.3)
    nt = mat.node_tree
    pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    pits = nt.nodes.new('ShaderNodeTexVoronoi')
    pits.inputs['Scale'].default_value = 1.1 / radius
    nt.links.new(coord.outputs['Object'], pits.inputs['Vector'])
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = .5
    b.inputs['Distance'].default_value = radius * .03
    nt.links.new(pits.outputs['Distance'], b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], pr.inputs['Normal'])
    ball = lathe([(0, 0), (radius * .55, radius * .1), (radius * .92, radius * .62), (radius, radius), (radius * .9, radius * 1.42), (radius * .5, radius * 1.84), (radius * .1, radius * 1.93), (0, radius * 1.9)],
                 mat=mat, segments=64, name=name)
    return _place([ball, sphere(radius * .07, at=(0, 0, radius * 1.93), mat=material('stalk end', '#4a4a24', rough=.8), name='stalk end')], at, 0, f'{name} whole')


def pear(at=(0, 0, 0), turn: float = 0, colour='#b5a83f', lean: float = 12, name: str = 'pear') -> bpy.types.Object:
    """A ripe pear, freckled, leaning a little."""
    mat = _apple_skin(colour)
    body = lathe([(0, .004), (.018, .002), (.035, .018), (.038, .04), (.03, .06), (.021, .08), (.016, .1), (.011, .112), (.003, .116), (0, .112)], mat=mat, segments=48, name='pear')
    stem = tube([(0, 0, .112), (.002, .001, .125), (.007, .002, .136)], .0014, mat=material('stem', '#4a3220', rough=.7), name='stem')
    whole = group(body, stem, at=at, rot=(lean, 0, turn), name=name)
    return whole


def bread(at=(0, 0, 0), turn: float = 0, length: float = .3, name: str = 'bread') -> bpy.types.Object:
    """A country loaf with a dusty, deep-baked crust and cuts across the top."""
    from mathutils import noise

    w = length * .55
    h = length * .36
    crust = material('crust', '#a8682c', rough=.72, vary=.5, bump=.8, scale=24)
    nt = crust.node_tree
    pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    split = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], split.inputs[0])
    top = nt.nodes.new('ShaderNodeMapRange')  # darker where the oven reached, floury lower down
    top.inputs['From Min'].default_value, top.inputs['From Max'].default_value = h * .2, h * .95
    nt.links.new(split.outputs['Z'], top.inputs['Value'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = _rgba('#d9b98a')
    ramp.color_ramp.elements[1].color = _rgba('#6e3a17')
    nt.links.new(top.outputs[0], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], pr.inputs['Base Color'])

    def make(bm):
        bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1)
        for v in bm.verts:
            x, y, z = v.co
            z_ = max(z, -.45)
            lump = 1 + noise.noise(Vector((x * 1.6, y * 1.6, z * 1.6))) * .05
            cut = 0
            if z > .25:  # the slashes across the crust, opened by the heat
                for c in (-.5, 0, .5):
                    cut += .1 * math.exp(-(((x - c) - y * .35) / .08) ** 2)
            v.co = Vector((x * length / 2 * lump, y * w / 2 * lump, (z_ + .45) / 1.45 * h * (1 - cut)))

    obj = _new(make, name)
    obj.data.polygons.foreach_set('use_smooth', [True] * len(obj.data.polygons))
    return _finish(obj, name, at, (0, 0, turn), crust, False)


def cloth(at=(0, 0, 0), size=(1, .8), colour='#d9d2c4', folds: float = 1, seed: int = 3, name: str = 'cloth') -> bpy.types.Object:
    """Linen laid on a table, its surface in soft creases, its edge a little raised."""
    from mathutils import noise

    w, d = size
    cols, rows = int(w * 200), int(d * 200)
    verts = []
    for j in range(rows + 1):
        for i in range(cols + 1):
            x, y = (i / cols - .5) * w, (j / rows - .5) * d
            n = abs(noise.noise(Vector((x * 4, y * 7, seed)))) * .018 + noise.noise(Vector((x * 11, y * 15, seed + 1))) * .004
            edge = max(abs(x) / (w / 2), abs(y) / (d / 2))
            verts.append((x, y, .002 + n * folds * (.4 + .6 * min(1, (1 - edge) * 8))))
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i) for j in range(rows) for i in range(cols)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    apply(obj, preset('fabric', colour=colour, rough=.85, bump=.8, scale=300, vary=.15))
    obj.location = at
    return obj


def desk_lamp(at=(0, 0, 0), turn: float = 0, mat='brass', warm: float = 3200, power: float = 8, name: str = 'desk lamp') -> bpy.types.Object:
    """A desk lamp on a heavy round base, with a jointed arm and a glowing shade over the light."""
    metal = preset(mat) if isinstance(mat, str) else mat
    base = lathe([(0, 0), (.08, 0), (.08, 0), (.082, .006), (.078, .014), (.02, .022), (.012, .035), (0, .035)], mat=metal, name='base')
    arm = tube([(0, 0, .03), (.004, 0, .2), (-.01, 0, .3), (.07, 0, .4), (.15, 0, .43)], .0065, mat=metal, name='arm')
    shade = lathe([(.03, .1), (.034, .098), (.06, .06), (.09, 0), (.088, 0), (.058, .058), (.03, .092)], at=(.17, 0, .33), mat=preset('paint', colour='#2c3a33'), name='shade')
    bulb = sphere(.028, at=(.17, 0, .365), mat=material('bulb', kelvin(warm), glow=kelvin(warm), glow_strength=14), name='bulb')
    light = point(at=(.17, 0, .35), power=power, colour=kelvin(warm), radius=.03, name='lamp light')
    root = _place([base, arm, shade, bulb], at, turn, name)
    light.parent = root
    return root


def chair(at=(0, 0, 0), turn: float = 0, mat=None, name: str = 'chair') -> bpy.types.Object:
    """A plain wooden chair, seat 45 cm high, facing -Y."""
    m = mat if mat is not None else wood(colour='#6e4426', scale=8)
    seat = lathe([(0, 0), (.21, 0), (.21, 0), (.22, .012), (.21, .03), (.21, .03), (0, .03)], at=(0, 0, .43), mat=m, name='seat')
    seat.scale = (1, .98, 1)
    parts = [seat]
    for sx in (-1, 1):
        parts.append(tube([(sx * .17, -.16, 0), (sx * .15, -.14, .44)], .017, mat=m, name='front leg'))
        parts.append(tube([(sx * .17, .19, 0), (sx * .15, .16, .44), (sx * .15, .2, .84)], .016, mat=m, name='back leg'))
    parts.append(box((.34, .02, .1), at=(0, .2, .79), rot=(8, 0, 0), mat=m, bevel_width=.004, name='back rest'))
    for z in (.62, .55):
        parts.append(tube([(-.15, .185, z), (.15, .185, z)], .008, mat=m, name='rail'))
    return _place(parts, at, turn, name)


def laptop(at=(0, 0, 0), turn: float = 0, screen='#2a3a5a', name: str = 'laptop') -> bpy.types.Object:
    """An open laptop, its screen lit and facing -Y."""
    shell = preset('aluminium')
    base = box((.32, .22, .012), at=(0, 0, .006), mat=shell, bevel_width=.004, name='base')
    keys = box((.28, .11, .001), at=(0, .03, .0125), mat=preset('rubber'), bevel_width=0, name='keyboard')
    pad = box((.1, .065, .0006), at=(0, -.07, .0122), mat=material('trackpad', '#b8babf', rough=.3), bevel_width=0, name='trackpad')
    lid = box((.32, .007, .21), at=(0, .125, .105), rot=(-14, 0, 0), mat=shell, bevel_width=.003, name='lid')
    glow = box((.3, .001, .19), at=(0, .1205, .105), rot=(-14, 0, 0), mat=material('screen', screen, rough=.2, glow=screen, glow_strength=2.2), bevel_width=0, name='screen')
    return _place([base, keys, pad, lid, glow], at, turn, name)


def rock(at=(0, 0, 0), size: float = .5, seed: int = 1, mat='stone', name: str = 'rock') -> bpy.types.Object:
    """A rough boulder with cracks and facets, half sunk where it stands."""
    rng = random.Random(seed)

    def make(bm):
        bmesh.ops.create_icosphere(bm, subdivisions=5, radius=size / 2)
        lumps = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-.4, 1))).normalized(), rng.uniform(.05, .3)) for _ in range(14)]
        for v in bm.verts:
            n = v.co.normalized()
            push = sum(h * max(0, n.dot(d)) ** 4 for d, h in lumps)
            v.co = n * (size / 2) * (.72 + push) + Vector((0, 0, size * .2))
            v.co.z *= .75

    obj = _new(make, name)
    cracks = bpy.data.textures.new('cracks', 'VORONOI')
    cracks.noise_scale = size * .35
    m = obj.modifiers.new('cracks', 'DISPLACE')
    m.texture, m.strength, m.mid_level = cracks, size * .16, .5
    grain = bpy.data.textures.new('grain', 'CLOUDS')
    grain.noise_scale, grain.noise_depth = size * .12, 4
    m = obj.modifiers.new('grain', 'DISPLACE')
    m.texture, m.strength = grain, size * .05
    return _finish(obj, name, at, (0, 0, rng.uniform(0, 360)), preset(mat) if isinstance(mat, str) else mat, False)


def _coloured(name: str, verts, faces, colours, rough: float, soft: float = 0, thin: float = 0) -> bpy.types.Object:
    """One mesh of many small parts, each vertex with its colour: thousands of leaves or blades cost almost nothing."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    layer = mesh.color_attributes.new('tone', 'FLOAT_COLOR', 'POINT')
    flat = [c for rgb in colours for c in (*rgb, 1)]
    layer.data.foreach_set('color', flat)
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mat = material(name, '#ffffff', rough=rough, soft=soft)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    source = nt.nodes.new('ShaderNodeVertexColor')
    source.layer_name = 'tone'
    nt.links.new(source.outputs['Color'], p.inputs['Base Color'])
    if thin:  # a leaf is thin: the sun behind it lights it up, which is what makes a tree glow
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        through = nt.nodes.new('ShaderNodeBsdfTranslucent')
        nt.links.new(source.outputs['Color'], through.inputs['Color'])
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = thin
        nt.links.new(p.outputs[0], mix.inputs[1])
        nt.links.new(through.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
    apply(obj, mat)
    return obj


def _limbs(segments, name: str, mat) -> bpy.types.Object:
    """Many tapering limbs as one mesh: segments are (start, middle, end, start radius, end radius)."""
    verts, faces = [], []
    for start, mid, end, r0, r1 in segments:
        d = (end - start).normalized()
        u = d.orthogonal().normalized()
        v = d.cross(u)
        n = 8 if r0 > .03 else 5
        base = len(verts)
        for point, r in ((start, r0), (mid, (r0 + r1) / 2), (end, r1)):
            for i in range(n):
                t = i / n * 6.2832
                verts.append(tuple(point + (u * math.cos(t) + v * math.sin(t)) * r))
        for ring in range(2):
            for i in range(n):
                a, b = base + ring * n + i, base + ring * n + (i + 1) % n
                faces.append((a, b, b + n, a + n))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    apply(obj, mat)
    return obj


_grown: dict = {}


def tree(at=(0, 0, 0), height: float = 8, seed: int = 2, leaves='#44662c', autumn: float = 0, name: str = 'tree') -> bpy.types.Object:
    """A broad-leaved tree: a tapering trunk that forks five times and a full crown of leaves, brighter where the light reaches.
    Stands well from 5 metres away. autumn 0..1 turns its leaves to yellow and rust. Six shapes per colour are grown and shared,
    so a wood of many trees stays light: vary seed, height and where it stands."""
    key = (seed % 6, str(leaves), round(autumn * 4))
    if key not in _grown:
        _grown[key] = _grow_tree(10, key[0], leaves, key[2] / 4)
    parts = []
    for mesh in _grown[key]:
        part = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.collection.objects.link(part)
        parts.append(part)
    whole = _place(parts, at, random.Random(seed * 7 + 1).uniform(0, 360), name)
    whole.scale = (height / 10,) * 3
    return whole


def _grow_tree(height: float, seed: int, leaves, autumn: float) -> list:
    rng = random.Random(seed)
    bark = material('bark', '#2f261f', rough=.9, vary=.7, bump=1, scale=9)
    limbs, tips = [], []
    boughs = []

    def branch(start, direction, length, radius, depth, bough=None):
        if bough is None:
            bough = len(boughs)
            boughs.append([rng.uniform(.8, 1.2), []])
        d = direction.normalized()
        end = start + d * length
        mid = (start + end) / 2 + Vector((rng.uniform(-.1, .1), rng.uniform(-.1, .1), rng.uniform(-.04, .04))) * length
        thin = radius * .7
        limbs.append((start, mid, end, radius, thin))
        if depth < 3 and rng.random() < .9:  # leaves along the outer limbs, not only at their ends: a crown, not a mop on a stick
            tips.append((end, bough))
            boughs[bough][1].append(end)
        if depth == 0:
            return
        count = rng.choice((2, 3, 3))
        u = d.orthogonal().normalized()
        v = d.cross(u)
        for k in range(count):
            a = k / count * 6.2832 + rng.uniform(-.6, .6)
            side = u * math.cos(a) + v * math.sin(a)
            lift = Vector((0, 0, rng.uniform(.1, .34)))  # boughs reach up and out, the lowest furthest: a dome, not a parasol
            spread = rng.uniform(.4, .75)
            branch(end, d + side * spread + lift, length * rng.uniform(.78, .92) * (1.15 if k == 0 else 1), thin * rng.uniform(.76, .92), depth - 1, bough)

    # a trunk that goes on up through the crown, with boughs all the way: the crown is full from its skirt to its top
    at_h, lean, radius = Vector((0, 0, 0)), Vector((rng.uniform(-.05, .05), rng.uniform(-.05, .05), 1)), height * .027
    stages = 9
    for i in range(stages):
        step = height * .66 / stages
        end = at_h + lean.normalized() * step
        thin = radius * .84
        limbs.append((at_h, (at_h + end) / 2, end, radius, thin))
        at_h, radius = end, thin
        lean += Vector((rng.uniform(-.14, .14), rng.uniform(-.14, .14), 0))
        level = (i + 1) / stages
        if level < .24:
            continue
        for k in range(rng.choice((2, 3))):
            a = rng.uniform(0, 6.2832)
            shape = math.sin(math.pi * min(1, (level - .1) / .95) ** .75)  # the widest a little under the middle
            way = Vector((math.cos(a), math.sin(a), .25 + 1.1 * level + rng.uniform(-.15, .15)))
            branch(end, way, height * rng.uniform(.095, .14) * (.45 + shape), radius * .62, 3)
    middle = sum((t for t, _ in tips), Vector()) / len(tips)
    reach = max((t - middle).length for t, _ in tips)
    centres = [sum(b[1], Vector()) / max(1, len(b[1])) for b in boughs]
    sizes = [max(((t - c).length for t in b[1]), default=1) + height * .1 for b, c in zip(boughs, centres)]
    base = _rgba(leaves)
    turned = _rgba('#e39a22')
    verts, faces, tones = [], [], []
    leaf = height * .0105
    for tip, bough in tips:
        cluster = height * rng.uniform(.065, .105)
        for _ in range(90000 // len(tips)):
            d = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, .8))).normalized()
            spot = tip + d * cluster * rng.random() ** .5
            axis = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-.7, .2))).normalized() * leaf
            side = axis.cross(d).normalized() * leaf * .42
            n = len(verts)
            verts += [tuple(spot - axis * .5), tuple(spot - side), tuple(spot + axis * .5), tuple(spot + side)]
            faces.append((n, n + 1, n + 2, n + 3))
            mass = spot - centres[bough]  # each bough is a mass: dark in its depths and underneath, bright where it faces the sky
            out = min(1, mass.length / sizes[bough])
            light = rng.uniform(.8, 1.2) * boughs[bough][0] * (.5 + .75 * out ** 2 + .4 * max(-.5, mass.z / sizes[bough]) + .2 * max(0, (spot.z - middle.z) / reach))
            colour = [b + (t - b) * autumn * rng.random() ** .5 for b, t in zip(base[:3], turned[:3])]
            tones += [tuple(c * light * t for c, t in zip(colour, (rng.uniform(.9, 1.2), 1, rng.uniform(.75, 1))))] * 4
    made = [_limbs(limbs, 'limbs', bark), _coloured('foliage', verts, faces, tones, .5, 0, .42)]
    meshes = [o.data for o in made]
    for o in made:
        bpy.data.objects.remove(o)
    return meshes


def pine(at=(0, 0, 0), height: float = 14, seed: int = 3, colour='#2c4a2e', snow: float = 0, name: str = 'pine') -> bpy.types.Object:
    """A conifer: a straight tapering trunk and tiers of drooping boughs thick with needles. Stands well from 5 metres away.
    snow 0..1 lays white on its boughs."""
    rng = random.Random(seed)
    bark = material('bark', '#3d2e26', rough=.9, vary=.7, bump=1, scale=9)
    limbs = [(Vector((0, 0, 0)), Vector((0, 0, height * .5)), Vector((0, 0, height)), height * .017, height * .0015)]
    base = _rgba(colour)
    verts, faces, tones = [], [], []
    level = .1
    while level < .985:
        z = height * level
        reach = height * .24 * (1 - level) ** .78 * rng.uniform(.85, 1.15) + height * .015
        for k in range(rng.randint(5, 7)):
            a = rng.uniform(0, 6.2832)
            droop = rng.uniform(-.34, -.08) + level * .34
            way = Vector((math.cos(a), math.sin(a), droop)).normalized()
            start = Vector((0, 0, z))
            end = start + way * reach
            limbs.append((start, (start + end) / 2 + Vector((0, 0, -.06 * reach)), end, height * .0035, height * .0007))
            side = Vector((-way.y, way.x, 0))
            for _ in range(int(16 + reach * 12)):
                t = rng.random() ** .7
                at_on = start + way * reach * t + Vector((0, 0, -.06 * reach * 4 * t * (1 - t)))
                wide = reach * .38 * (1 - t * .75)
                spot = at_on + side * rng.uniform(-wide, wide) + Vector((0, 0, rng.uniform(-.05, .02) * reach))
                long = way * height * .022 + Vector((0, 0, -height * .012)) + side * rng.uniform(-.012, .012) * height
                cross = side * height * .0035 + Vector((0, 0, height * .004))
                n = len(verts)
                verts += [tuple(spot), tuple(spot + cross), tuple(spot + long + cross), tuple(spot + long)]
                faces.append((n, n + 1, n + 2, n + 3))
                light = rng.uniform(.7, 1.25) * (.42 + .6 * t + .5 * level)
                tone = tuple(c * light * m for c, m in zip(base[:3], (rng.uniform(.9, 1.1), 1, rng.uniform(.85, 1.05))))
                if rng.random() < snow * .8:
                    tone = (.82, .85, .9)
                tones += [tone] * 4
        level += rng.uniform(.028, .04) * (1 + level * .25)
    return _place([_limbs(limbs, 'limbs', bark), _coloured('needles', verts, faces, tones, .55, 0, .3)], at, rng.uniform(0, 360), name)


def treeline(y: float = 200, x=(-400, 400), depth: float = 40, height: float = 17, count: int = 2600, colour='#29442c', seed: int = 7, name: str = 'treeline') -> bpy.types.Object:
    """A band of far forest along a line at distance y: thousands of small dark spires. It is what hides the seam where a lake
    or field meets the hills. For trees further than 80 metres; closer, place c3d.pine or c3d.tree one by one."""
    rng = random.Random(seed)
    base = _rgba(colour)
    verts, faces, tones = [], [], []
    tiers, sides = 3, 6
    for _ in range(count):
        wx, wy = rng.uniform(*x), y + rng.uniform(0, depth)
        ground = land_z(wx, wy)
        if ground < .1 and _land:
            continue
        h = height * rng.uniform(.65, 1.35)
        r = h * rng.uniform(.12, .17)
        tint = rng.uniform(.65, 1.3)
        for tier in range(tiers):
            low, top = h * (.12 + tier * .24), h * (.5 + tier * .25)
            spread = r * (1 - tier * .28)
            n = len(verts)
            for i in range(sides):
                t = i / sides * 6.2832 + tier
                verts.append((wx + math.cos(t) * spread * rng.uniform(.8, 1.2), wy + math.sin(t) * spread * rng.uniform(.8, 1.2), ground + low))
            verts.append((wx, wy, ground + top))
            for i in range(sides):
                faces.append((n + i, n + (i + 1) % sides, n + sides))
            dark = tuple(c * tint * .55 for c in base[:3])
            bright = tuple(c * tint * (1 + .25 * tier) for c in base[:3])
            tones += [dark] * sides + [bright]
    obj = _coloured(name, verts, faces, tones, .8)
    obj['c3d_ground'] = True
    return obj


def fallen_leaves(size=(30, 40), at=(0, 12, 0), count: int = 40000, colours=('#a8561f', '#c98a2b', '#7d3a1c', '#8c6a2a', '#b23f1d'), seed: int = 5, name: str = 'fallen leaves') -> bpy.types.Object:
    """Dead leaves lying on the ground over an area, thickest in drifts, following c3d.land if there is one."""
    rng = random.Random(seed)
    tints = [_rgba(c) for c in colours]
    verts, faces, tones = [], [], []
    drift = [(rng.uniform(.2, .7), rng.uniform(.2, .7), rng.uniform(0, 6.3)) for _ in range(4)]
    for _ in range(count):
        x, y = rng.uniform(-size[0] / 2, size[0] / 2), rng.uniform(-size[1] / 2, size[1] / 2)
        if rng.random() > .55 + .45 * sum(math.sin(x * a + y * b + c) for a, b, c in drift) / 2:
            continue
        ground = land_z(x + at[0], y + at[1]) + rng.uniform(.004, .02)
        r = rng.uniform(.025, .05)
        t = rng.uniform(0, 6.2832)
        dx, dy = math.cos(t) * r, math.sin(t) * r
        n = len(verts)
        lift = rng.uniform(0, .012)
        verts += [(x - dx, y - dy, ground), (x - dy * .5, y + dx * .5, ground + lift), (x + dx, y + dy, ground), (x + dy * .5, y - dx * .5, ground + lift)]
        faces.append((n, n + 1, n + 2, n + 3))
        tint, light = rng.choice(tints), rng.uniform(.6, 1.2)
        tones += [tuple(c * light for c in tint[:3])] * 4
    obj = _coloured(name, verts, faces, tones, .6, .1)
    obj.location = at
    return obj


def track(points, width: float = 1.6, colour='#6b5238', seed: int = 2, name: str = 'track') -> bpy.types.Object:
    """A worn earth path along [(x, y), ...] on the land: uneven edges, two ruts, a touch above the ground so it is seen."""
    rng = random.Random(seed)
    pts = []
    for a, b in zip(points, points[1:]):
        steps = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / .5))
        pts += [(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps) for i in range(steps)]
    pts.append(tuple(points[-1]))
    for _ in range(40):  # rounds the corners
        pts = [pts[0], *[((u[0] + 2 * v[0] + w[0]) / 4, (u[1] + 2 * v[1] + w[1]) / 4) for u, v, w in zip(pts, pts[1:], pts[2:])], pts[-1]]
    across = 8
    verts, faces, tones = [], [], []
    base = _rgba(colour)
    for j, (x, y) in enumerate(pts):
        u, v = pts[max(0, j - 1)], pts[min(len(pts) - 1, j + 1)]
        dx, dy = v[0] - u[0], v[1] - u[1]
        size = math.hypot(dx, dy) or 1
        nx, ny = -dy / size, dx / size
        wide = width * (1 + .22 * math.sin(j * .19 + seed) + .1 * math.sin(j * .53))
        for i in range(across + 1):
            k = i / across * 2 - 1
            wx, wy = x + nx * k * wide / 2, y + ny * k * wide / 2
            edge = abs(k)
            verts.append((wx, wy, land_z(wx, wy) + .025 * (1 - edge * edge) + .004))
            rut = 1 - .32 * math.exp(-((edge - .45) / .12) ** 2)
            light = rng.uniform(.8, 1.15) * rut
            tones.append(tuple(c * light * (.75 + .25 * edge) for c in base[:3]))
    for j in range(len(pts) - 1):
        for i in range(across):
            n = j * (across + 1) + i
            faces.append((n, n + 1, n + across + 2, n + across + 1))
    return _coloured(name, verts, faces, tones, .9)


def meadow(size=(60, 60), at=(0, 12, 0), blades: int = 140000, height: float = .11, seed: int = 4, colour='#62743a', near=None, name: str = 'grass') -> bpy.types.Object:
    """Real grass blades over an area size (x, y) around `at`, on a ground(mat='grass'). near=(x, y), the point under the camera:
    most blades go where they are seen close, and they thicken with distance. Make it cover everything in front of the camera:
    a small patch on bare ground looks like a toupee."""
    rng = random.Random(seed)
    base = _rgba(colour)
    home = (near[0] - at[0], near[1] - at[1]) if near else None
    wide = max(size) * .22
    verts, faces, tones = [], [], []
    patch = [(rng.uniform(.25, 1.1), rng.uniform(.25, 1.1), rng.uniform(0, 6.3)) for _ in range(4)]
    for _ in range(blades):
        if home and rng.random() < .62:
            x, y = rng.gauss(home[0], wide), rng.gauss(home[1], wide)
        else:
            x, y = rng.uniform(-size[0] / 2, size[0] / 2), rng.uniform(-size[1] / 2, size[1] / 2)
        edge = max(abs(x) / size[0], abs(y) / size[1]) * 2  # thins out towards its rim: no hard line where it ends
        if edge > 1 or (edge > .6 and rng.random() < (edge - .6) / .4):
            continue
        soil = land_z(x + at[0], y + at[1])
        if soil < .05 and _land:
            continue
        far = math.hypot(x - home[0], y - home[1]) / 8 if home else 0
        tuft = sum(math.sin(x * a + y * b + c) for a, b, c in patch) / 4
        h = height * rng.uniform(.5, 1.5) * (1 + .5 * tuft)
        lean, turn_to = rng.uniform(.1, .7) * h, rng.uniform(0, 6.283)
        dx, dy = math.cos(turn_to), math.sin(turn_to)
        w = h * .03 * (1 + far)
        v = len(verts)
        verts += [(x - w * dy, y + w * dx, soil), (x + w * dy, y - w * dx, soil), (x - w * .7 * dy + lean * .3 * dx, y + w * .7 * dx + lean * .3 * dy, soil + h * .55),
                  (x + w * .7 * dy + lean * .3 * dx, y - w * .7 * dx + lean * .3 * dy, soil + h * .55), (x + lean * dx, y + lean * dy, soil + h)]
        faces += [(v, v + 1, v + 3, v + 2), (v + 2, v + 3, v + 4)]
        tint = rng.uniform(.75, 1.2) * (1 + .3 * tuft)
        dry = rng.random() < .1 + .12 * max(0, tuft)
        root = tuple(c * .4 * tint for c in base[:3])
        tip = tuple(c * tint * (1.5 if dry else 1.1) * t for c, t in zip(base[:3], (1.5 if dry else 1, 1, .7)))
        mid = tuple((a + b) / 2 for a, b in zip(root, tip))
        tones += [root, root, mid, mid, tip]
    obj = _coloured(name, verts, faces, tones, .55, 0, .35)
    obj.location = at
    return obj


def hills(y: float = 400, height: float = 70, width: float = 2400, colour='#4c6a52', haze='#a9bccb', layers: int = 3, seed: int = 8, name: str = 'hills') -> bpy.types.Object:
    """Ridges on the far +Y horizon, each paler and bluer than the one before it, the way distance looks. Keep y at 200 or more."""
    rng = random.Random(seed)
    near, air = _rgba(colour), _rgba(haze)
    parts = []
    for layer in range(layers):
        waves = [(rng.uniform(.8, 7) / width * 6.2832, rng.uniform(.3, 1), rng.uniform(0, 6.3)) for _ in range(9)]
        total = sum(w[1] for w in waves)
        top = height * (1 + layer * .7)
        far = y * (1 + layer * .75)
        mix = (layer + .4) / layers
        verts, faces, tones = [], [], []
        rows, cols = 22, 420
        for j in range(rows + 1):
            t = j / rows
            for i in range(cols + 1):
                x = -width / 2 * (1 + layer * .4) + width * (1 + layer * .4) * i / cols
                ridge = (sum(math.sin(x * f + c) * a for f, a, c in waves) / total + 1) / 2
                crag = sum((1 - abs(math.sin(x * f * 5 + t * (3 + n) + c))) * a for n, (f, a, c) in enumerate(waves[:5])) / total
                bump = sum(math.sin(x * f * 17 + t * 11 + c) * a for f, a, c in waves[:4]) / total * .05
                z = top * max(0, ridge * .78 + crag * .34 + bump - .08) * math.sin(t * 1.5708) ** .8 * (1 - t * .12)
                verts.append((x, far + t * height * 4, z))
                forest = (math.sin(x * waves[0][0] * 21 + t * 9) + math.sin(x * waves[1][0] * 33 - t * 13 + 1)) / 4 + .5  # dark woods and paler slopes
                shade = rng.uniform(.9, 1.1) * (.52 + .62 * forest * forest + .34 * z / top)
                tones.append(tuple((a * shade + (b - a * shade) * mix) for a, b in zip(near[:3], air[:3])))
        for j in range(rows):
            for i in range(cols):
                n = j * (cols + 1) + i
                faces.append((n, n + 1, n + cols + 2, n + cols + 1))
        parts.append(_coloured(f'ridge {layer}', verts, faces, tones, .9))
        parts[-1]['c3d_ground'] = True
    return group(*parts, name=name)


def mountains(y: float = 700, height: float = 320, width: float = 4200, snow: float = .62, forest='#2f4a38', rock='#6f6a66', haze='#a9bccb', layers: int = 2,
              seed: int = 8, name: str = 'mountains') -> bpy.types.Object:
    """A real range on the far +Y horizon: ridges cut by erosion, dark forest low down, bare rock above it, snow on the tops,
    and each range paler than the one before. snow is the height of the snow line, 0..1 of the peaks; 1 for none. Keep y at 400 or more."""
    from mathutils import noise

    parts = []
    woods, stone, air = _rgba(forest), _rgba(rock), _rgba(haze)
    white = _rgba('#f1f3f6')
    for layer in range(layers):
        cols, rows = 640, 120
        far = y * (1 + layer * .8)
        depth = height * 5
        span = width * (1 + layer * .5)
        scale = height * 2.1
        top = height * (1 + layer * .45)
        zs = []
        for j in range(rows + 1):
            t = j / rows
            ridge_of = math.sin(t * math.pi) ** .6
            for i in range(cols + 1):
                x = -span / 2 + span * i / cols
                q = Vector((x / scale + layer * 17.3, t * depth / scale, seed * 1.7))
                mass = .5 + .5 * noise.noise(q * .28)
                crags = noise.ridged_multi_fractal(q, 1.0, 2.05, 8, 1.0, 2.0) / 2.4
                zs.append(ridge_of * max(0, (.3 + mass * .7) * (.3 + crags) - .1))
        lift = top / (max(zs) or 1)
        zs = [v * lift for v in zs]
        peak = top
        verts, tones = [], []
        step_x, step_y = span / cols, depth / rows
        mix_air = (layer + .34) / (layers + .3)
        for j in range(rows + 1):
            for i in range(cols + 1):
                n = j * (cols + 1) + i
                z = zs[n]
                verts.append((-span / 2 + i * step_x, far + j * step_y, z))
                left, right = zs[n - 1 if i else n], zs[n + 1 if i < cols else n]
                back, front = zs[n - cols - 1 if j else n], zs[n + cols + 1 if j < rows else n]
                slope = math.hypot((right - left) / (2 * step_x), (front - back) / (2 * step_y))
                level = z / peak
                bare = min(1, max(0, (level - .24) / .2) + max(0, slope - .9))  # forest gives way to rock with height and steepness
                tone = [a + (b - a) * bare for a, b in zip(woods[:3], stone[:3])]
                if level > snow - .1 * math.sin(i * .37 + j * .61) and slope < 1.5:
                    cover = min(1, (level - snow + .1) / .08) * (1 - max(0, slope - 1) * 2)
                    tone = [a + (b - a) * max(0, cover) for a, b in zip(tone, white[:3])]
                tones.append(tuple(a + (b - a) * mix_air for a, b in zip(tone, air[:3])))
        faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i) for j in range(rows) for i in range(cols)]
        parts.append(_coloured(f'range {layer}', verts, faces, tones, .85))
        parts[-1]['c3d_ground'] = True  # the views frame what is near, not the horizon
    return group(*parts, name=name)


_land = None


def land_z(x: float, y: float) -> float:
    """How high the land is at (x, y), after c3d.land(); 0 without it. Stand things on it: at=(x, y, c3d.land_z(x, y))."""
    return _land(x, y) if _land else 0


def land(size=(500, 400), at=(0, 120, 0), height: float = 3, lake=None, mat='grass', seed: int = 5, name: str = 'land') -> bpy.types.Object:
    """Rolling ground instead of a flat plane, sinking into a lake when lake=(x, y, width, depth) names one: the shore is then
    where land meets water, as in nature, with no line along it. Follow it with c3d.lake(at=(x, y, 0), size=(width, depth)) for
    the water. meadow() grows on it by itself; stand everything else on c3d.land_z(x, y)."""
    from mathutils import noise

    global _land

    def wobble(a):
        return 1 + .1 * math.sin(a * 3 + seed) + .06 * math.sin(a * 5 + 1) + .03 * math.sin(a * 9 + 2)

    def z(wx, wy):
        rise = (.55 + .45 * max(-1, min(1, noise.fractal(Vector((wx / 70, wy / 70, seed)), 1.0, 2.0, 5)))) * height + .25  # never below the water, away from the lake
        if not lake:
            return rise
        d = math.hypot((wx - lake[0]) / (lake[2] / 2), (wy - lake[1]) / (lake[3] / 2))
        k = d / wobble(math.atan2(wy - lake[1], wx - lake[0]))
        if k >= 1.3:
            return rise
        bank = max(0, (k - .86) / .44)  # from the lake's bed up the bank, out to the plain land
        bank = bank * bank * (3 - 2 * bank)
        return -1.2 + (rise * bank + 1.2) * bank

    _land = z
    w, d = size
    cols, rows = int(w / 1.6), int(d / 1.6)
    verts = [(at[0] - w / 2 + w * i / cols, at[1] - d / 2 + d * j / rows, 0) for j in range(rows + 1) for i in range(cols + 1)]
    verts = [(a, b, z(a, b)) for a, b, _ in verts]
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i) for j in range(rows) for i in range(cols)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj['c3d_ground'] = True
    apply(obj, mat)
    return obj


def sea(shore_y: float = 10, size: float = 4000, colour='#1c4a5c', waves: float = 1, seed: int = 2, name: str = 'sea') -> bpy.types.Object:
    """The open sea from shore_y out to the horizon on +Y, with swell far out, ripples near, a sun path on it, and real rollers
    with foam where it reaches the beach. Goes with c3d.beach(shore_y) and a low sun. waves 0 is calm, 1 a light swell, 2 rough."""
    from mathutils import noise

    verts, tones = [], []
    cols, rows = 420, 300
    deep, shallow, foam = _rgba(colour), _rgba('#3f8a8c'), _rgba('#f2f1ea')

    def where(j):  # rows are close together near the beach
        return shore_y - 6 + (j / rows) ** 2.6 * size

    for j in range(rows + 1):
        wy = where(j)
        near = max(0, 1 - (wy - shore_y) / 60)
        for i in range(cols + 1):
            t = i / cols
            wx = (t - .5) * (160 + (wy - shore_y) * 1.6)
            q = Vector((wx / 9, wy / 22, seed))
            swell = noise.fractal(q, 1.0, 2.0, 4) * .28 * waves * (1 - near * .5)
            run = math.sin((wy - shore_y) * .34 + noise.noise(Vector((wx / 30, wy / 40, 1))) * 5)  # rollers coming in
            crest = max(0, run) ** 3 * .34 * waves * near
            z = swell + crest - max(0, shore_y - wy) * .14
            verts.append((wx, wy, z))
            edge = noise.noise(Vector((wx / 8, wy / 5, 3)))
            white = 0
            if wy < shore_y + 34:
                white = max(0, run - .55) * 2.2 * (.5 + edge) * near + max(0, (shore_y + 1.5 + edge * 2 - wy) / 2.5)
            tint = [a + (b - a) * min(1, near * 1.3) for a, b in zip(deep[:3], shallow[:3])]
            tones.append(tuple(a + (b - a) * min(1, white) for a, b in zip(tint, foam[:3])))
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i) for j in range(rows) for i in range(cols)]
    obj = _coloured(name, verts, faces, tones, .06)
    obj['c3d_ground'] = True
    nt = obj.data.materials[0].node_tree
    b = nt.nodes.new('ShaderNodeBump')
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = 2.2
    n.inputs['Detail'].default_value = 7
    coord = nt.nodes.new('ShaderNodeTexCoord')
    stretch = nt.nodes.new('ShaderNodeMapping')
    stretch.inputs['Scale'].default_value = (.6, 2, 1)
    nt.links.new(coord.outputs['Object'], stretch.inputs['Vector'])
    nt.links.new(stretch.outputs[0], n.inputs['Vector'])
    b.inputs['Strength'].default_value = .3
    b.inputs['Distance'].default_value = .08
    nt.links.new(n.outputs[0], b.inputs['Height'])
    p = next(x for x in nt.nodes if x.type == 'BSDF_PRINCIPLED')
    nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return obj


def beach(shore_y: float = 10, size=(400, 60), colour='#c4ad86', seed: int = 3, name: str = 'beach') -> bpy.types.Object:
    """Sand from behind the camera down into the sea at shore_y: rippled, dark and shining where the water has just left it."""
    from mathutils import noise

    global _land
    w, d = size

    def z(x, y):
        fall = (shore_y - y) * .045
        dunes = noise.fractal(Vector((x / 26, y / 16, seed)), 1.0, 2.0, 4) * .35 * min(1, max(0, (shore_y - y) / 16))
        return fall + dunes

    _land = z
    cols, rows = int(w / 2), int(d / .5)
    wet, dry = _rgba(colour), _rgba(colour)
    wet = tuple(c * .42 for c in wet[:3])
    verts, tones = [], []
    start = shore_y - d + 12
    for j in range(rows + 1):
        wy = start + d * j / rows
        for i in range(cols + 1):
            wx = -w / 2 + w * i / cols
            verts.append((wx, wy, z(wx, wy)))
            line = shore_y - 4 + noise.noise(Vector((wx / 11, 2, seed))) * 3
            k = min(1, max(0, (wy - line) / 2.5))
            speck = 1 + noise.noise(Vector((wx * 2, wy * 2, 7))) * .12
            tones.append(tuple((a + (b - a) * k) * speck for a, b in zip(dry[:3], wet)))
    faces = [(j * (cols + 1) + i, j * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i + 1, (j + 1) * (cols + 1) + i) for j in range(rows) for i in range(cols)]
    obj = _coloured(name, verts, faces, tones, .75)
    obj['c3d_ground'] = True
    nt = obj.data.materials[0].node_tree
    p = next(x for x in nt.nodes if x.type == 'BSDF_PRINCIPLED')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    grain = nt.nodes.new('ShaderNodeTexNoise')  # ripples the wind left, and grains
    grain.inputs['Scale'].default_value = 9
    grain.inputs['Detail'].default_value = 8
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.inputs['Scale'].default_value = .9
    wave.inputs['Distortion'].default_value = 9
    wave.inputs['Detail'].default_value = 4
    nt.links.new(coord.outputs['Object'], grain.inputs['Vector'])
    nt.links.new(coord.outputs['Object'], wave.inputs['Vector'])
    both = nt.nodes.new('ShaderNodeMath')
    nt.links.new(grain.outputs[0], both.inputs[0])
    nt.links.new(wave.outputs[0], both.inputs[1])
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = .35
    b.inputs['Distance'].default_value = .03
    nt.links.new(both.outputs[0], b.inputs['Height'])
    nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return obj


def mist(y: float = 120, height: float = 14, width: float = 900, amount: float = 1, colour='#dfe6ec', layers: int = 3, seed: int = 3, name: str = 'mist') -> bpy.types.Object:
    """Low mist lying across the view at distance y, thickest at the ground, torn at the top: over water, in a valley, between
    the trees and the hills. Cheap: it is soft sheets, not a volume. y is at least 40 metres from the camera."""
    rng = random.Random(seed)
    parts = []
    for i in range(layers):
        mat = bpy.data.materials.new('mist')
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        coord = nt.nodes.new('ShaderNodeTexCoord')
        split = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(coord.outputs['Object'], split.inputs[0])
        wide = nt.nodes.new('ShaderNodeMapping')  # banks of mist are long and low
        wide.inputs['Scale'].default_value = (.012, 1, .09)
        wide.inputs['Location'].default_value = (rng.uniform(0, 50), 0, rng.uniform(0, 50))
        nt.links.new(coord.outputs['Object'], wide.inputs['Vector'])
        noise = nt.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 3
        noise.inputs['Detail'].default_value = 7
        nt.links.new(wide.outputs[0], noise.inputs['Vector'])
        torn = nt.nodes.new('ShaderNodeMapRange')
        torn.inputs['From Min'].default_value, torn.inputs['From Max'].default_value = .3, .68
        nt.links.new(noise.outputs[0], torn.inputs['Value'])
        fall = nt.nodes.new('ShaderNodeMapRange')  # gone at the top of the sheet, fullest near the ground
        fall.inputs['From Min'].default_value, fall.inputs['From Max'].default_value = 0, height
        fall.inputs['To Min'].default_value, fall.inputs['To Max'].default_value = 1, 0
        nt.links.new(split.outputs['Z'], fall.inputs['Value'])
        side = nt.nodes.new('ShaderNodeMath')
        side.operation = 'MULTIPLY'
        nt.links.new(fall.outputs[0], side.inputs[0])
        nt.links.new(fall.outputs[0], side.inputs[1])
        both = nt.nodes.new('ShaderNodeMath')
        both.operation = 'MULTIPLY'
        nt.links.new(side.outputs[0], both.inputs[0])
        nt.links.new(torn.outputs[0], both.inputs[1])
        thin = nt.nodes.new('ShaderNodeMath')
        thin.operation = 'MULTIPLY'
        thin.inputs[1].default_value = min(1, .55 * amount)
        nt.links.new(both.outputs[0], thin.inputs[0])
        clear = nt.nodes.new('ShaderNodeBsdfTransparent')
        glow = nt.nodes.new('ShaderNodeEmission')  # lit from everywhere, as mist is
        glow.inputs['Color'].default_value = _rgba(colour)
        glow.inputs['Strength'].default_value = .85
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(thin.outputs[0], mix.inputs[0])
        nt.links.new(clear.outputs[0], mix.inputs[1])
        nt.links.new(glow.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        sheet = bpy.data.meshes.new(f'mist {i}')
        sheet.from_pydata([(-width / 2, 0, 0), (width / 2, 0, 0), (width / 2, 0, height), (-width / 2, 0, height)], [], [(0, 1, 2, 3)])
        sheet.update()
        obj = bpy.data.objects.new(f'mist {i}', sheet)
        bpy.context.collection.objects.link(obj)
        obj['c3d_ground'] = True  # air: nothing to frame, nothing that floats
        obj.location = (0, y * (1 + i * .35), 0)
        obj.visible_shadow = False
        apply(obj, mat)
        parts.append(obj)
    return group(*parts, name=name)


def lake(at=(0, 0, 0), size=(120, 80), colour='#22404a', ripple: float = 1, seed: int = 6, name: str = 'lake') -> bpy.types.Object:
    """Still water with an uneven shore, a hair above the ground at `at` (its middle). It mirrors what stands behind it,
    so look across it from low. ripple 0 is a mirror, 1 a light breeze."""
    rng = random.Random(seed)
    waves = [(rng.randint(2, 9), rng.uniform(.02, .09), rng.uniform(0, 6.3)) for _ in range(6)]
    if _land:  # the land has the shore: the water only has to reach past it
        size, waves = (size[0] * 1.5, size[1] * 1.5), []
    steps = 180
    verts = [(0, 0, 0)]
    for i in range(steps):
        t = i / steps * 6.2832
        k = 1 + sum(a * math.sin(n * t + c) for n, a, c in waves)
        verts.append((math.cos(t) * size[0] / 2 * k, math.sin(t) * size[1] / 2 * k, 0))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [(0, i + 1, (i + 1) % steps + 1) for i in range(steps)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj['c3d_ground'] = True
    mat = material('lake water', colour, rough=.04, ior=1.33, coat=0)
    nt = mat.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    if ripple:
        coord = nt.nodes.new('ShaderNodeTexCoord')
        stretch = nt.nodes.new('ShaderNodeMapping')  # ripples run across the view, long and low
        stretch.inputs['Scale'].default_value = (1, 5, 1)
        nt.links.new(coord.outputs['Object'], stretch.inputs['Vector'])
        noise = nt.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 1.6
        noise.inputs['Detail'].default_value = 8
        nt.links.new(stretch.outputs[0], noise.inputs['Vector'])
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = min(1, .12 * ripple)
        bump.inputs['Distance'].default_value = .05
        nt.links.new(noise.outputs[0], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
    apply(obj, mat)
    obj.location = (at[0], at[1], at[2] + (0 if _land else .012))
    return obj


# --- things for old towns and camps (2026-11-07) ----------------------------------------------------------------------

def barrel(at=(0, 0, 0), turn: float = 0, height: float = .9, name: str = 'barrel') -> bpy.types.Object:
    """A wooden barrel standing on `at`, its staves bulging, two iron hoops."""
    r = height * .33
    profile = [(r * .82, 0), (r * .92, height * .18), (r, height * .5), (r * .92, height * .82), (r * .82, height), (r * .76, height), (r * .76, height * .96), (0, height * .96)]
    body = lathe(profile, mat=wood(scale=2), segments=32, name='staves')
    parts = [body]
    for z in (.2, .8):
        parts.append(torus(r * (.93 if z != .5 else 1), .012, at=(0, 0, height * z), mat=preset('iron'), name='hoop'))
    return _place(parts, at, turn, name)


def crate(at=(0, 0, 0), turn: float = 0, size: float = .7, name: str = 'crate') -> bpy.types.Object:
    """A wooden crate: a plain box with battens along its edges."""
    w = wood(scale=3)
    s = size
    parts = [box((s * .94, s * .94, s * .94), at=(0, 0, s / 2), mat=w, name='box')]
    b = s * .1
    for x in (-1, 1):
        for y in (-1, 1):
            parts.append(box((b, b, s), at=(x * (s - b) / 2, y * (s - b) / 2, s / 2), mat=w, name='batten'))
    for z in (b / 2, s - b / 2):
        for x in (-1, 1):
            parts.append(box((b, s, b), at=(x * (s - b) / 2, 0, z), mat=w, name='batten'))
            parts.append(box((s, b, b), at=(0, x * (s - b) / 2, z), mat=w, name='batten'))
    return _place(parts, at, turn, name)


def bench(at=(0, 0, 0), turn: float = 0, width: float = 1.6, name: str = 'bench') -> bpy.types.Object:
    """A park bench of slats on iron sides, facing -Y before it is turned."""
    w = wood(scale=3)
    iron = preset('iron')
    parts = []
    for i in range(4):
        parts.append(box((width, .085, .03), at=(0, -.18 + i * .1, .44), mat=w, name='seat'))
    for i in range(3):
        parts.append(box((width, .03, .085), at=(0, .2, .56 + i * .11), rot=(-10, 0, 0), mat=w, name='back'))
    for x in (-width / 2 + .1, width / 2 - .1):
        parts.append(box((.05, .5, .05), at=(x, 0, .41), mat=iron, name='rail'))
        parts.append(box((.05, .05, .42), at=(x, -.2, .21), mat=iron, name='leg'))
        parts.append(box((.05, .05, .84), at=(x, .22, .42), rot=(-10, 0, 0), mat=iron, name='leg'))
    return _place(parts, at, turn, name)


def lamp_post(at=(0, 0, 0), height: float = 3.4, warm: float = 2700, power: float = 60, name: str = 'lamp post') -> bpy.types.Object:
    """An old street lamp on an iron post, lit."""
    iron = preset('iron')
    parts = [cylinder(.09, .4, at=(0, 0, .2), mat=iron, sides=24, name='foot'), cylinder(.045, height, at=(0, 0, height / 2), mat=iron, bevel_width=0, sides=24, name='post'),
             cone(.17, .16, .02, at=(0, 0, height + .36), mat=iron, name='cap')]
    glow = material('glow', '#ffcf8f')
    glow.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 8
    glow.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, .72, .36, 1)
    parts.append(cylinder(.1, .28, at=(0, 0, height + .14), mat=glow, bevel_width=0, sides=8, name='glass'))
    parts.append(point(at=(0, 0, height + .14), power=power, colour=kelvin(warm), radius=.08, name='lamp'))
    return _place(parts, at, 0, name)


def well(at=(0, 0, 0), name: str = 'well') -> bpy.types.Object:
    """A stone well with a little roof and a rope."""
    stone = preset('stone')
    w = wood(scale=3)
    parts = [lathe([(.72, 0), (.74, .02), (.74, .72), (.56, .72), (.56, .1), (0, .1)], mat=stone, segments=48, name='ring')]
    for x in (-.68, .68):
        parts.append(box((.1, .1, 1.7), at=(x, 0, 1.2), mat=w, name='post'))
    parts.append(cylinder(.05, 1.5, at=(0, 0, 1.75), rot=(0, 90, 0), mat=w, sides=16, name='axle'))
    parts.append(box((1.8, .7, .05), at=(0, -.3, 2.2), rot=(-32, 0, 0), mat=w, name='roof'))
    parts.append(box((1.8, .7, .05), at=(0, .3, 2.2), rot=(32, 0, 0), mat=w, name='roof'))
    parts.append(cylinder(.012, 1.2, at=(0, 0, 1.15), mat=preset('fabric') if 'fabric' in PRESETS else w, bevel_width=0, sides=8, name='rope'))
    return _place(parts, at, 0, name)


def stone_wall(points, height: float = 1.2, thick: float = .5, seed: int = 4, colour='#7d776c', name: str = 'stone wall') -> bpy.types.Object:
    """A dry-stone wall along [(x, y), ...] on the land: stones of many sizes, laid in rows."""
    rng = random.Random(seed)
    b = _Blocks()
    base = _rgba(colour)
    for u, v in zip(points, points[1:]):
        length = math.hypot(v[0] - u[0], v[1] - u[1])
        dx, dy = (v[0] - u[0]) / length, (v[1] - u[1]) / length
        along_x = abs(dx) >= abs(dy)
        row, z = 0, 0.0
        while z < height:
            h = rng.uniform(.14, .26)
            d = rng.uniform(0, .2) if row % 2 else 0
            while d < length:
                w = rng.uniform(.25, .6)
                p = (u[0] + dx * d, u[1] + dy * d)
                g = land_z(*p)
                inset = rng.uniform(0, .05)
                light = rng.uniform(.72, 1.2)
                tone = tuple(c * light for c in base[:3])
                if along_x:
                    low, high = (p[0], p[1] - thick / 2 + inset, g + z - .05), (p[0] + w * .96 * (1 if dx > 0 else -1), p[1] + thick / 2 - inset, g + z + h * .96)
                else:
                    low, high = (p[0] - thick / 2 + inset, p[1], g + z - .05), (p[0] + thick / 2 - inset, p[1] + w * .96 * (1 if dy > 0 else -1), g + z + h * .96)
                b.add(tuple(map(min, low, high)), tuple(map(max, low, high)), tone)
                d += w
            z += h
            row += 1
    return b.mesh(name, .9)


def banner(at=(0, 0, 0), turn: float = 0, height: float = 4.2, colour='#8a2a22', name: str = 'banner') -> bpy.types.Object:
    """A war banner on a pole: a long cloth hanging from a crossbar, a little in the wind."""
    w = wood(scale=3)
    parts = [cylinder(.04, height, at=(0, 0, height / 2), mat=w, bevel_width=0, sides=16, name='pole'), cylinder(.025, .8, at=(.4, 0, height - .1), rot=(0, 90, 0), mat=w, bevel_width=0, sides=12, name='bar')]
    verts, faces = [], []
    across, down = 8, 24
    length = height * .55
    for j in range(down + 1):
        for i in range(across + 1):
            s, t = i / across, j / down
            verts.append((.05 + s * .72, .05 * math.sin(s * 5 + t * 4) * (.4 + t), height - .12 - t * length))
    for j in range(down):
        for i in range(across):
            a = j * (across + 1) + i
            faces.append((a, a + 1, a + across + 2, a + across + 1))
    me = bpy.data.meshes.new('cloth')
    me.from_pydata(verts, [], faces)
    me.update()
    cloth_obj = bpy.data.objects.new('cloth', me)
    bpy.context.collection.objects.link(cloth_obj)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.materials.append(material('banner', colour, rough=.8))
    parts.append(cloth_obj)
    return _place(parts, at, turn, name)


def market_stall(at=(0, 0, 0), turn: float = 0, colour='#b5472f', name: str = 'market stall') -> bpy.types.Object:
    """A market stall: a table of planks under a striped cloth roof, facing -Y before it is turned."""
    w = wood(scale=3)
    pale = material('pale cloth', '#e9e0cc', rough=.85)
    strong = material('strong cloth', colour, rough=.85)
    parts = [box((2.4, 1, .05), at=(0, 0, .85), mat=w, name='top'), box((2.3, .05, .7), at=(0, .45, .48), mat=w, name='back')]
    for x in (-1.15, 1.15):
        for y in (-.45, .45):
            parts.append(box((.08, .08, 2.3 if y > 0 else 2.0), at=(x, y, 1.15 if y > 0 else 1), mat=w, name='post'))
    for i in range(8):
        parts.append(box((.32, 1.5, .02), at=(-1.12 + i * .32, -.1, 2.15), rot=(10, 0, 0), mat=strong if i % 2 else pale, name='awning'))
    return _place(parts, at, turn, name)
