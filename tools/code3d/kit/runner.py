"""Runs inside Blender (--background): builds the project's scene from scene.py, then does one job with it.

The job comes as a JSON file after `--`; the answer goes to the file the job names. A line "C3D {json}" on stdout is progress.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

import bpy
from mathutils import Vector

job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
KIT = Path(job['kit'])
PROJECT = Path(job['project'])
OUT = PROJECT / 'out'
warnings: list[str] = []
sys.path.insert(0, str(KIT))


def say(**event) -> None:
    print('C3D ' + json.dumps(event), flush=True)


def finish(answer: dict) -> None:
    Path(job['result']).write_text(json.dumps(answer, ensure_ascii=False), encoding='utf-8')
    sys.stdout.flush()


def scene_error(e: BaseException) -> dict:
    """Where in scene.py it went wrong: the line a person (or a model) has to fix, not Blender's stack."""
    script = str(PROJECT / job['script']).lower()
    line = None
    for frame in traceback.extract_tb(e.__traceback__):
        if frame.filename.lower() == script or frame.filename == 'scene.py':
            line = frame.lineno
    if isinstance(e, SyntaxError) and e.lineno:
        line = e.lineno
    return {'ok': False, 'error': f'{type(e).__name__}: {e}', 'line': line}


def build() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import guard

    guard.install(PROJECT, [KIT, Path(bpy.app.binary_path).parent, *job.get('read', [])], str(PROJECT / job['script']))
    import c3d

    scene = bpy.context.scene
    s = job['settings']
    scene.render.resolution_x, scene.render.resolution_y = int(s['width']), int(s['height'])
    scene.render.fps = int(s['fps'])
    scene.frame_start, scene.frame_end = int(s['frame_start']), int(s['frame_end'])
    scene.frame_set(int(s['frame_start']))
    path = PROJECT / job['script']
    source = path.read_text(encoding='utf-8')
    os.chdir(PROJECT)
    exec(compile(source, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path), 'bpy': bpy, 'c3d': c3d})
    bpy.context.view_layer.update()
    lights = any(o.type == 'LIGHT' for o in scene.objects)
    glows = any(n.type == 'EMISSION' or (n.type == 'BSDF_PRINCIPLED' and n.inputs['Emission Strength'].default_value > 0)
                for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes)
    if scene.world is None and not lights and not glows:
        c3d.sky()
        warnings.append('场景没有灯光：这次用了默认天空。写 c3d.sky() 或 c3d.studio() 定下光线。')


def meshes():
    return [o for o in bpy.context.scene.objects if o.type in ('MESH', 'CURVE', 'FONT', 'SURFACE') and not o.hide_render]


def corners(o, dg) -> list:
    """Where an object is in the world. A curve's bound_box is a default two-metre cube, so a curve is measured by its mesh."""
    e = o.evaluated_get(dg)
    if o.type == 'MESH':
        return [e.matrix_world @ Vector(c) for c in e.bound_box]
    mesh = e.to_mesh()
    pts = [e.matrix_world @ v.co for v in mesh.vertices] if mesh else [e.matrix_world.translation.copy()]
    e.to_mesh_clear()
    return pts or [e.matrix_world.translation.copy()]


def bounds() -> tuple[Vector, float]:
    """The middle of the model and its size, without the ground."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in meshes():
        if o.get('c3d_ground'):
            continue
        pts += corners(o, dg)
    if not pts:
        return Vector((0, 0, 0)), 1.0
    low = Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    return (low + high) / 2, max((high - low).length / 2, .01)


DIRECTIONS = {'front': (0, -1, .06), 'back': (0, 1, .06), 'left': (-1, 0, .06), 'right': (1, 0, .06), 'top': (0, -.001, 1), 'iso': (1, -1, .75)}
_viewer = None


def view_camera(direction) -> None:
    """A camera of its own, framing the whole model from one side: the scene's camera stays as written."""
    global _viewer
    scene = bpy.context.scene
    if _viewer is None:
        _viewer = bpy.data.objects.new('c3d-view', bpy.data.cameras.new('c3d-view'))
        scene.collection.objects.link(_viewer)
        _viewer.data.lens = 60
    mid, radius = bounds()
    aspect = scene.render.resolution_x / scene.render.resolution_y
    half = math.atan(18 / _viewer.data.lens) * (1 if aspect >= 1 else aspect)
    half = min(half, math.atan(math.tan(math.atan(18 / _viewer.data.lens)) / aspect))
    distance = radius / math.sin(half) * 1.08
    d = Vector(direction).normalized()
    _viewer.location = mid + d * distance
    _viewer.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    _viewer.data.clip_end = max(1000, distance * 10)
    scene.camera = _viewer


QUALITY = {'check': (360, 8, .15, 15, 3), 'draft': (640, 16, .08, 45, 4)}  # width, samples, noise, seconds, bounces


def use_engine(quality: str) -> dict:
    scene = bpy.context.scene
    s = job['settings']
    draft = quality != 'final'
    width, samples, noise, seconds, bounces = QUALITY.get(quality) or (None, int(s['samples']), .02, int(s['max_seconds']), 10)
    scene.render.resolution_percentage = 100
    if draft:  # a look, not the picture
        scale = min(1, job.get('draft_width', width) / scene.render.resolution_x)
        scene.render.resolution_percentage = max(1, int(scale * 100))
    if s['engine'] == 'eevee':
        kinds = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
        scene.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in kinds else 'BLENDER_EEVEE_NEXT'
        scene.eevee.taa_render_samples = 16 if draft else min(int(s['samples']), 128)
        if hasattr(scene.eevee, 'use_raytracing'):
            scene.eevee.use_raytracing = True
    else:
        scene.render.engine = 'CYCLES'
        c = scene.cycles
        c.device = 'CPU'  # the game in front keeps the graphics card; the render stays out of its way
        c.samples = job.get('samples') or samples
        c.use_adaptive_sampling = True
        c.adaptive_threshold = noise
        c.time_limit = seconds  # this computer is small: a clock, not a hope. The denoiser cleans up what is left.
        c.use_denoising = True
        c.denoiser = 'OPENIMAGEDENOISE'
        c.max_bounces = bounces
        c.caustics_reflective = c.caustics_refractive = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = max(1, (os.cpu_count() or 2) - 1)  # one core stays free for whatever else is running
    scene.view_settings.view_transform = 'AgX'
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    scene.render.film_transparent = False
    return {'width': scene.render.resolution_x * scene.render.resolution_percentage // 100,
            'height': scene.render.resolution_y * scene.render.resolution_percentage // 100,
            'engine': s['engine']}


def shoot(path: Path) -> float:
    scene = bpy.context.scene
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(path)
    began = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - began


def aim(view: str) -> None:
    scene = bpy.context.scene
    if view == 'camera' and scene.camera is None:
        warnings.append('场景没有相机：这次从斜上方看。写 c3d.camera(...) 定下成片的角度。')
        view = 'iso'
    if view != 'camera':
        view_camera(DIRECTIONS[view])


def do_render() -> dict:
    size = use_engine(job['quality'])
    scene = bpy.context.scene
    if job.get('frame') is not None:
        scene.frame_set(int(job['frame']))
    aim(job['view'])
    path = Path(job['output'])
    seconds = shoot(path)
    scene_now = {k: v for k, v in do_objects().items() if k != 'ok'}  # the window and the agent see what they are looking at
    return {'ok': True, 'output': str(path), 'seconds': round(seconds, 1), 'view': job['view'], 'quality': job['quality'], 'scene': scene_now,
            'notes': critique(path, job['view']), **size}


DARK = .16  # the median of a lit subject stays above this


def critique(path: Path, view: str) -> list[str]:
    """What a photographer would say first: measured from the picture and the geometry, so that it holds on any model."""
    notes = []
    try:
        import numpy as np

        image = bpy.data.images.load(str(path))
        w, h = image.size
        data = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[::2, ::2, :3]
        bpy.data.images.remove(image)
        luma = data @ np.array([.2126, .7152, .0722], dtype=np.float32)
        mean, low, high = float(luma.mean()), float(np.percentile(luma, 5)), float(np.percentile(luma, 95))
        r, g, b = (float(data[..., i].mean()) for i in range(3))
        if mean < .16:
            notes.append(f'画面太暗（平均亮度 {mean:.2f}，照片一般 0.25 到 0.5）：加灯，或 c3d.exposure(1)。')
        below = float(np.median(luma[:luma.shape[0] // 2]))  # the first row of the array is the bottom of the picture
        above = float(np.median(luma[luma.shape[0] // 2:]))
        if view == 'camera' and above > below * 2 and below < DARK:
            notes.append(f'下半张压在暗处（亮度 {below:.2f}，上半张 {above:.2f}）：主体在那里就要提高主灯或把灯移近主体，不要靠压暗别处；'
                         '阴影看不清也是这个原因，不要画假阴影。')
        if mean > .72:
            notes.append(f'画面太亮（平均亮度 {mean:.2f}）：减灯，或 c3d.exposure(-1)。')
        if float((luma > .97).mean()) > .08:
            notes.append(f'{float((luma > .97).mean()):.0%} 的画面过曝成纯白：降低那里的灯或发光强度。')
        if float((luma < .02).mean()) > .3:
            notes.append(f'{float((luma < .02).mean()):.0%} 的画面是死黑：那里什么也看不见，加补光，窗外要有天光（c3d.dusk）。')
        if high - low < .25:
            notes.append(f'画面发灰，明暗差太小（{high - low:.2f}）：让主光更集中，留出暗部。')
        if b > 0 and r / max(b, .001) > 2.2:
            notes.append(f'整张偏橙（红蓝比 {r / max(b, .001):.1f}）：灯太黄了，用 c3d.kelvin(3300) 左右，再加一点冷的环境光形成对比。')
        if r > 0 and b / max(r, .001) > 2.0:
            notes.append(f'整张偏蓝（蓝红比 {b / max(r, .001):.1f}）：加一盏暖灯。')
    except Exception as e:  # the picture stands without its notes
        notes.append(f'（没有量到画面：{type(e).__name__}）')
    return notes + geometry_notes(view)


def things(dg) -> dict:
    """Each whole thing in the scene, its parts together: {name: (low corner, high corner, parts)}."""
    boxes = {}
    for o in meshes():
        if o.get('c3d_ground'):
            continue
        pts = corners(o, dg)
        root = o
        while root.parent is not None:
            root = root.parent
        low = Vector(tuple(min(p[i] for p in pts) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in pts) for i in range(3)))
        parts = 1
        if root.name in boxes:
            a, b, n = boxes[root.name]
            low = Vector(tuple(min(low[i], a[i]) for i in range(3)))
            high = Vector(tuple(max(high[i], b[i]) for i in range(3)))
            parts += n
        boxes[root.name] = (low, high, parts)
    return boxes


def geometry_notes(view: str) -> list[str]:
    from bpy_extras.object_utils import world_to_camera_view

    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    boxes = {k: v[:2] for k, v in things(dg).items()}
    notes, grounds = [], [o for o in meshes() if o.get('c3d_ground')]
    floor = max((o.matrix_world.translation.z for o in grounds), default=None)
    for name, (low, high) in boxes.items():
        size = high - low
        if size.length > 8 or name.startswith(('pendant', 'street', 'room', 'lamp')):
            continue
        gap = None
        for other, (a, b) in boxes.items():
            if other != name and a.x < high.x and b.x > low.x and a.y < high.y and b.y > low.y and b.z <= low.z + .02:
                gap = min(gap, low.z - b.z) if gap is not None else low.z - b.z
        here = sys.modules['c3d'].land_z((low.x + high.x) / 2, (low.y + high.y) / 2) if 'c3d' in sys.modules else 0  # rolling land is not at z=0
        level = floor + here if floor is not None else None
        if level is not None and low.z >= level - .02:
            gap = min(gap, low.z - level) if gap is not None else low.z - level
        if gap is not None and gap > .012:
            notes.append(f'{name} 悬空 {gap * 100:.1f} 厘米：东西要落在东西上。')
    camera = scene.camera
    if view == 'camera' and camera is not None:
        for name, (low, high) in boxes.items():
            marks = [Vector((x, y, z)) for x in (low.x, high.x) for y in (low.y, high.y) for z in (low.z, high.z)] + [(low + high) / 2]
            seen = [world_to_camera_view(scene, camera, c) for c in marks]
            if not any(0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0 for v in seen) and (high - low).length < 3:
                notes.append(f'{name} 不在画面里。')
    return notes[:8]


def do_views() -> dict:
    size = use_engine('check')
    pictures = []
    for i, view in enumerate(job['views']):
        say(event='progress', done=i, total=len(job['views']), what=view)
        aim(view)
        path = OUT / f'view-{view}.png'
        shoot(path)
        pictures.append(str(path))
    return {'ok': True, 'pictures': pictures, **size}


def do_turntable() -> dict:
    job['samples'] = job.get('samples') or 6
    job['draft_width'] = job.get('draft_width') or 480
    size = use_engine('check')
    count = int(job['count'])
    pictures = []
    for i in range(count):
        say(event='progress', done=i, total=count, what='turn')
        a = 2 * math.pi * i / count - math.pi / 4
        view_camera((math.cos(a), math.sin(a), .55))
        path = OUT / 'turn' / f'{i:02d}.png'
        shoot(path)
        pictures.append(str(path))
    return {'ok': True, 'pictures': pictures, **size}


def do_objects() -> dict:
    dg = bpy.context.evaluated_depsgraph_get()
    rows, faces = [], 0
    for o in meshes():
        e = o.evaluated_get(dg)
        mesh = e.to_mesh() if o.type != 'MESH' else e.data
        count = len(mesh.polygons) if mesh else 0
        faces += count
        names = [m.name for m in o.data.materials if m] if hasattr(o.data, 'materials') else []
        if not names and count:
            warnings.append(f'{o.name} 没有材质，渲染出来是灰的。')
        rows.append({'name': o.name, 'type': o.type.lower(), 'faces': count, 'materials': names,
                     'location': [round(v, 3) for v in o.matrix_world.translation], 'size': [round(v, 3) for v in o.dimensions]})
        if o.type != 'MESH':
            e.to_mesh_clear()
    mid, radius = bounds()
    scene = bpy.context.scene
    whole = [{'name': k, 'parts': n, 'from': [round(v, 3) for v in low], 'to': [round(v, 3) for v in high]} for k, (low, high, n) in things(dg).items()]
    return {'ok': True, 'objects': rows[:200], 'things': whole[:60], 'count': len(rows), 'faces': faces, 'centre': [round(v, 3) for v in mid],
            'size': round(radius * 2, 3), 'camera': bool(scene.camera), 'frames': [scene.frame_start, scene.frame_end]}


def do_animate() -> dict:
    size = use_engine(job['quality'])
    scene = bpy.context.scene
    aim('camera')
    folder = OUT / 'frames'
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob('*.png'):
        old.unlink()
    total = scene.frame_end - scene.frame_start + 1
    began = time.time()
    for i, f in enumerate(range(scene.frame_start, scene.frame_end + 1)):
        say(event='progress', done=i, total=total, what='frame')
        scene.frame_set(f)
        shoot(folder / f'{i:05d}.png')
    return {'ok': True, 'frames': str(folder), 'count': total, 'fps': scene.render.fps, 'seconds': round(time.time() - began, 1), **size}


def do_export() -> dict:
    fmt, path = job['format'], Path(job['output'])
    path.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    if fmt == 'glb':
        bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', export_apply=True)
    elif fmt == 'fbx':
        bpy.ops.export_scene.fbx(filepath=str(path), use_mesh_modifiers=True, bake_anim=scene.frame_end > scene.frame_start)
    elif fmt == 'obj':
        bpy.ops.wm.obj_export(filepath=str(path), export_materials=True)
    elif fmt == 'stl':
        bpy.ops.wm.stl_export(filepath=str(path))
    elif fmt == 'usd':
        bpy.ops.wm.usd_export(filepath=str(path))
    elif fmt == 'blend':
        bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
    return {'ok': True, 'output': str(path), 'format': fmt, 'bytes': path.stat().st_size if path.is_file() else 0}


ACTIONS = {'render': do_render, 'views': do_views, 'turntable': do_turntable, 'objects': do_objects, 'animate': do_animate,
           'export': do_export}

try:
    say(event='stage', what='build')
    build()
except BaseException as e:  # the script's own mistakes, of any kind, come back as an answer
    finish(scene_error(e))
    raise SystemExit(0)
try:
    say(event='stage', what=job['action'])
    answer = ACTIONS[job['action']]()
    answer['warnings'] = list(dict.fromkeys(warnings))
    finish(answer)
except BaseException as e:
    finish({'ok': False, 'error': f'{type(e).__name__}: {e}', 'line': None, 'warnings': warnings})
