"""Runs inside Blender (--background): builds part.py, measures each part, writes its STL and a picture of it.

The job comes as a JSON file after `--`; the answer goes to the file the job names.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import struct
import sys
import traceback

import bmesh
import bpy
from mathutils import Vector

job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
KIT = Path(job['kit'])
PROJECT = Path(job['project'])
OUT = PROJECT / 'out'
sys.path.insert(0, str(KIT))
DENSITY = {'PLA': 1.24, 'PETG': 1.27, 'ABS': 1.04, 'TPU': 1.21, 'ALUMINIUM': 2.7, 'STEEL': 7.85}  # g per cubic centimetre


def finish(answer: dict) -> None:
    Path(job['result']).write_text(json.dumps(answer, ensure_ascii=False), encoding='utf-8')


def measure(item: dict) -> dict:
    me = item['shape'].mesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.normal_update()
    if not bm.verts:
        bm.free()
        return {'empty': True}
    lo = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
    hi = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
    open_edges = sum(1 for e in bm.edges if not e.is_manifold)
    volume = abs(bm.calc_volume(signed=False))
    area = sum(f.calc_area() for f in bm.faces)
    steep = 0.0
    bed = lo.z + .05
    for f in bm.faces:
        if f.normal.z < -.71 and min(v.co.z for v in f.verts) > bed:  # faces more than 45 degrees over nothing
            steep += f.calc_area()
    parts = _pieces(bm)
    tris = [[tuple(l.vert.co) for l in f.loops] + [tuple(f.normal)] for f in bm.faces]
    bm.free()
    density = DENSITY.get(str(item['material']).upper(), 1.24)
    grams = volume / 1000 * density
    infill = .2 * volume + .8 * min(volume, area * 1.2)  # walls are solid, the inside is 20 %
    plastic = infill / 1000 * density
    print_ = {'print_minutes': round(infill / 9 / 60 + (hi.z - lo.z) / .2 * .06), 'plastic_g': round(plastic, 1), 'plastic_yuan': round(plastic * .08, 2)}
    return {**print_, 'size_mm': [round(hi[i] - lo[i], 3) for i in range(3)], 'lowest_z': round(lo.z, 3), 'volume_cm3': round(volume / 1000, 3), 'area_cm2': round(area / 100, 2), 'weight_g': round(grams, 1),
            'triangles': len(tris), 'open_edges': open_edges, 'separate_pieces': parts, 'overhang_cm2': round(steep / 100, 2), '_tris': tris, 'material': item['material']}


def _pieces(bm) -> int:
    seen = set()
    count = 0
    for start in bm.verts:
        if start.index in seen:
            continue
        count += 1
        stack = [start]
        seen.add(start.index)
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
    return count


def write_stl(path: Path, tris: list) -> None:
    with open(path, 'wb') as f:
        f.write(b'CodeCAD'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        pack = struct.Struct('<12fH').pack
        for a, b, c, n in tris:
            f.write(pack(*n, *a, *b, *c, 0))


def notes(item: dict, m: dict) -> list:
    out = []
    name = item['name']
    if m.get('empty'):
        return [f'{name} 是空的。']
    if m['open_edges']:
        out.append(f'{name} 有 {m["open_edges"]} 条边没有封好，不是实体，切片软件可能出错。')
    if m['separate_pieces'] > 1:
        out.append(f'{name} 是 {m["separate_pieces"]} 块互不相连的东西。')
    if m['lowest_z'] > .01 or m['lowest_z'] < -.01:
        out.append(f'{name} 的最低点在 z={m["lowest_z"]}：打印前要放到平台上（.on_bed()）。')
    if m['overhang_cm2'] > .5:
        out.append(f'{name} 有 {m["overhang_cm2"]} cm² 的悬空面超过 45 度，打印要加支撑，或者换个摆放方向。')
    for axis, k in (('x', 0), ('y', 1), ('z', 2)):
        want = item['want'].get(axis)
        if want is not None and abs(m['size_mm'][k] - want) > item['tolerance']:
            out.append(f'{name} 的 {axis} 方向要 {want} mm，实际量出来 {m["size_mm"][k]} mm。')
    bed = job.get('printer')
    if bed and any(m['size_mm'][k] > bed[k] for k in range(3)):
        out.append(f'{name} 比打印机的 {bed} mm 还大。')
    return out


def picture(items: list, path: Path) -> None:
    """All the parts in one look: a simple solid view from above and to the side, which draws in a moment."""
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'SINGLE'
    scene.display.shading.single_color = (.62, .68, .78)
    scene.display.shading.show_cavity = True
    scene.display.shading.show_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    scene.render.film_transparent = False
    world = bpy.data.worlds.new('w')
    world.color = (.9, .9, .92)
    scene.world = world
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    offset = 0.0
    for it in items:
        o = bpy.data.objects.new(it['name'], it['shape'].mesh)
        scene.collection.objects.link(o)
        a, b = it['shape'].bounds()
        o.location.x = offset - a.x
        for i in range(3):
            lo[i] = min(lo[i], a[i] + (o.location.x if i == 0 else 0))
            hi[i] = max(hi[i], b[i] + (o.location.x if i == 0 else 0))
        offset += (b.x - a.x) + max(10.0, (b.x - a.x) * .2)
    middle = (lo + hi) / 2
    reach = max((hi - lo).length, 1.0)
    cam = bpy.data.cameras.new('c')
    cam.lens = 60
    cam.clip_end = reach * 40
    cam.clip_start = reach / 200
    co = bpy.data.objects.new('c', cam)
    scene.collection.objects.link(co)
    scene.camera = co
    direction = Vector((.62, -.62, .48)).normalized()
    co.location = middle + direction * reach * 2.6
    co.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)


def main() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import cad
    import guard

    script = PROJECT / job['script']
    appdata = os.environ.get('APPDATA')
    guard.install(PROJECT, [str(KIT), str(Path(bpy.app.binary_path).parent), os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')] + ([appdata] if appdata else []), str(script))
    os.chdir(PROJECT)
    source = script.read_text(encoding='utf-8-sig')
    try:
        exec(compile(source, str(script), 'exec'), {'__name__': '__main__', '__file__': str(script)})  # noqa: S102 (its own scene script)
    except Exception as e:  # noqa: BLE001 (reported to whoever wrote it, with the line)
        line = getattr(e, 'lineno', None) if isinstance(e, SyntaxError) else None
        for frame in traceback.extract_tb(e.__traceback__):
            if frame.filename.lower() == str(script).lower():
                line = frame.lineno
        finish({'ok': False, 'error': str(e) if isinstance(e, cad.CadError) else f'{type(e).__name__}: {e}', **({'line': line} if line else {})})
        return
    if not cad.PARTS:
        finish({'ok': False, 'error': "part.py 里没有 cad.part('名字', 形状)，什么也没留下。"})
        return
    OUT.mkdir(exist_ok=True)
    parts, warnings = [], []
    for item in cad.PARTS:
        if not re.fullmatch(r'[\w\- ]{1,60}', item['name']):
            finish({'ok': False, 'error': f'零件名字只用字母、数字、中文、下划线：{item["name"]}'})
            return
        m = measure(item)
        warnings += notes(item, m)
        tris = m.pop('_tris', [])
        if tris:
            write_stl(OUT / f'{item["name"]}.stl', tris)
        parts.append({'name': item['name'], 'file': f'out/{item["name"]}.stl', **m})
    answer = {'ok': True, 'parts': parts, 'warnings': warnings, 'unit': 'mm'}
    if job.get('picture', True):
        try:
            picture(cad.PARTS, OUT / 'latest.png')
            answer['pictures'] = ['out/latest.png']
        except Exception as e:  # noqa: BLE001 (the measured part is still good)
            answer['warnings'] = warnings + [f'图没有画出来：{e}']
    finish(answer)


main()
