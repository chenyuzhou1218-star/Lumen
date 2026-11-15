"""The Lumen team as little 3D figures, each its own glowing element. Rendered once with Blender and kept as pictures:

    blender --background --factory-startup --python make_team.py -- <folder> [member ...]

An original design: a soft bean of light with a big head, huge eyes, stubby arms and feet, and the top of the head made of
whatever the member is. Everything is built here from code, with Code3D's kit.
"""
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[5] / "tools" / "code3d" / "kit"))
import c3d

args = sys.argv[sys.argv.index("--") + 1:]
OUT = Path(args[0])
ONLY = args[1:]
SIZE = 512

BODY = [(.0, -.02), (.25, -.02), (.37, .06), (.44, .2), (.45, .33), (.48, .43), (.62, .58), (.71, .8), (.72, .98), (.65, 1.2), (.46, 1.42), (.22, 1.53), (.0, 1.55)]  # a big head on a small round body
TEAM = {
    "lumen": dict(low="#ff8a00", high="#ffd94a", glow=.42, top="rays", cheek="#ff5a2e"),
    "spark": dict(low="#e8380f", high="#ff9a2e", glow=.45, top="flame", cheek="#c41f00"),
    "prism": dict(low="#6a3df0", high="#c79bff", glow=.35, top="crystal", cheek="#ff6fd0"),
    "torch": dict(low="#c9182b", high="#ff6a4c", glow=.4, top="torch", cheek="#8f0012"),
    "ray": dict(low="#0b7be0", high="#66d4ff", glow=.4, top="streak", cheek="#4c6dff"),
    "lantern": dict(low="#0c9c8c", high="#62e6c4", glow=.4, top="lantern", cheek="#ffb36b"),
    "beacon": dict(low="#3a3ad6", high="#8f9dff", glow=.35, top="beacon", cheek="#ff7a7a"),
    "iris": dict(low="#2e6cf0", high="#6fd8ff", glow=.4, top="rainbow", cheek="#ff7ac8"),
}


def light_stuff(name, low, high, glow, axis_from=-.1, axis_to=1.5):
    """Lit from inside: the colour climbs from deep to pale, and the edge glows brighter than the middle."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs[0])
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value, rng.inputs["From Max"].default_value = axis_from, axis_to
    nt.links.new(sep.outputs["Z"], rng.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = c3d._rgba(low)
    ramp.color_ramp.elements[1].color = c3d._rgba(high)
    nt.links.new(rng.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    nt.links.new(ramp.outputs[0], c3d._socket(p, "Emission Color", "Emission"))
    p.inputs["Roughness"].default_value = .55
    c3d._socket(p, "Coat Weight", "Clearcoat").default_value = .15
    fres = nt.nodes.new("ShaderNodeFresnel")
    fres.inputs["IOR"].default_value = 1.25
    amount = nt.nodes.new("ShaderNodeMapRange")
    amount.inputs["To Min"].default_value, amount.inputs["To Max"].default_value = glow, glow * 2.2
    nt.links.new(fres.outputs[0], amount.inputs["Value"])
    nt.links.new(amount.outputs[0], c3d._socket(p, "Emission Strength"))
    return m


def flat(colour, glow=0, rough=.25):
    return c3d.material("flat", colour, rough=rough, glow=colour if glow else None, glow_strength=glow)


FLAME = [(0, 0), (.09, .01), (.15, .1), (.14, .22), (.09, .36), (.04, .5), (0, .62)]


def tongue(mat, at, tilt, turn, size):
    o = c3d.lathe(FLAME, at=at, rot=(tilt, 0, turn), mat=mat, segments=48, name="flame")
    o.scale = (size, size, size)
    return o


def build_top(kind, stuff, s):
    z = 1.45
    if kind == "rays":
        for i in range(7):
            a = -78 + i * 26
            r = math.radians(a)
            tongue(stuff, (math.sin(r) * .6, 0, .96 + math.cos(r) * .5), 0, 0, .8 + .22 * (i % 2 == 0)).rotation_euler = (0, r, 0)
    elif kind == "flame":
        for x, h, t, size in ((0, z, 0, 1.6), (-.26, z - .1, -22, 1.15), (.28, z - .12, 24, 1.2), (-.46, z - .34, -40, .8), (.48, z - .36, 42, .85), (.04, z - .04, 8, .9)):
            o = tongue(stuff, (x, .03, h), 0, 0, size)
            o.rotation_euler = (0, math.radians(t), 0)
    elif kind == "crystal":
        for x, h, t, size in ((0, z - .05, 0, 1.2), (-.22, z - .1, -24, .8), (.24, z - .12, 26, .85)):
            bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=.15 * size, radius2=0, depth=.55 * size, location=(x, 0, h + .2 * size), rotation=(0, math.radians(t), .3))
            c3d.apply(bpy.context.object, c3d.material("gem", "#d9b8ff", rough=.08, glow="#a06bff", glow_strength=1.6))
    elif kind == "torch":
        for x, h, t, size in ((0, z, 0, 1.15), (-.15, z - .05, -18, .8), (.16, z - .06, 20, .8)):
            o = tongue(light_stuff("fire", "#ff5a1f", "#ffe9a0", 1.6, 0, .9), (x, 0, h), 0, 0, size)
            o.rotation_euler = (0, math.radians(t), 0)
        c3d.torus(.3, .055, at=(0, 0, 1.47), mat=c3d.preset("copper"))
    elif kind == "streak":
        for i, (t, size) in enumerate(((-70, 1.25), (-48, 1.45), (-26, 1.3), (-6, 1.0))):
            o = tongue(stuff, (.1 + .08 * i, .02, 1.2 + .06 * i), 0, 0, size)
            o.rotation_euler = (0, math.radians(t), 0)
    elif kind == "lantern":
        c3d.cylinder(.42, .08, at=(0, 0, 1.46), mat=c3d.preset("copper"), bevel_width=.02)
        c3d.cone(.46, .2, .18, at=(0, 0, 1.6), mat=c3d.preset("copper"))
        c3d.torus(.15, .03, at=(0, 0, 1.86), rot=(90, 0, 0), mat=c3d.preset("copper"))
    elif kind == "beacon":
        c3d.cylinder(.24, .18, at=(0, 0, 1.6), mat=flat("#fff3c4", 3))
        c3d.cone(.34, .24, 0, at=(0, 0, 1.8), mat=flat("#e8393f"))
        for side in (-1, 1):
            o = c3d.cone(.02, .9, .2, at=(side * .68, 0, 1.6), rot=(0, side * 90, 0), mat=c3d.material("beam", "#fff6c9", glass=1, rough=.2, glow="#fff1a8", glow_strength=.7))
            o.visible_shadow = False
    elif kind == "rainbow":
        for i, colour in enumerate(("#ff5a5a", "#ffb03a", "#ffe45c", "#58d68d", "#4cb4ff", "#a56bff")):
            c3d.torus(.86 - i * .06, .033, at=(0, .05, 1.0), rot=(90, 0, 0), mat=flat(colour, 1.1))


def face(cheek):
    black = c3d.material("eye", "#14131a", rough=.12)
    white = flat("#ffffff", 2.2)
    for side in (-1, 1):
        e = c3d.sphere(.135, at=(side * .24, -.635, .94), mat=black)
        e.scale = (.92, .42, 1.3)
        c3d.sphere(.044, at=(side * .24 - .04, -.69, 1.03), mat=white)
        c3d.sphere(.019, at=(side * .24 + .04, -.69, .88), mat=white)
        c = c3d.sphere(.1, at=(side * .46, -.53, .74), mat=c3d.material("cheek", cheek, rough=.5, glow=cheek, glow_strength=.5))
        c.scale = (1.1, .25, .62)
    c3d.tube([(-.09, -.685, .72), (-.045, -.705, .675), (0, -.712, .662), (.045, -.705, .675), (.09, -.685, .72)], .015, mat=black)


def limbs(stuff, kind):
    wave = kind == "rainbow"
    for side in (-1, 1):
        lift = 1 if side == 1 else -.1
        c3d.tube([(side * .4, -.02, .32), (side * .58, -.05, .33 + .08 * lift), (side * .7, -.06, .36 + .22 * lift)], .07, mat=stuff)
        c3d.sphere(.105, at=(side * .71, -.06, .38 + .24 * lift), mat=stuff)
        foot = c3d.sphere(.15, at=(side * .22, -.1, -.03), mat=stuff)
        foot.scale = (1, 1.35, .62)
    if wave:  # Iris works the computer: a little pointer in its hand
        arrow = c3d.extrude([(0, 0), (0, -.26), (.07, -.19), (.12, -.3), (.17, -.27), (.12, -.17), (.2, -.17)], .05, at=(.78, -.24, .86), rot=(90, 0, -18),
                            mat=c3d.material("pointer", "#23232b", rough=.3), bevel_width=.01)
        arrow.scale = (1.5, 1.5, 1.5)
        arrow.name = "pointer"


def render(name, spec):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    stuff = light_stuff("body", spec["low"], spec["high"], spec["glow"])
    c3d.lathe(BODY, mat=stuff, name="body", segments=96)
    build_top(spec["top"], stuff, spec)
    limbs(stuff, spec["top"])
    face(spec["cheek"])
    if spec["top"] == "beacon":
        for z, r in ((.14, .42), (.32, .45)):
            c3d.torus(r, .04, at=(0, 0, z), mat=flat("#f3f3f8", .4))
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = .32
    scene = bpy.context.scene
    scene.world = world
    c3d.area((2, -3, 3), look=(0, 0, .8), size=4, power=70, name="key")
    c3d.area((-3, -2, 1.5), look=(0, 0, .8), size=3, power=50, colour="#dfe8ff", name="fill")
    c3d.camera(at=(0, -7.6, 1.2), look=(0, 0, .92), lens=75)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 3
    scene.render.resolution_x = scene.render.resolution_y = SIZE
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.render.filepath = str(OUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("done", name, flush=True)


for name, spec in TEAM.items():
    if not ONLY or name in ONLY:
        render(name, spec)
