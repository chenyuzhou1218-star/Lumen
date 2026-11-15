#!/usr/bin/env python3
"""CodeCut: a small, JSON-first video editor for terminals and agents."""
from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from urllib.parse import urlparse, quote

ROOT = Path(__file__).resolve().parent
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


class CutError(Exception):
    pass


def emit(data):
    print(json.dumps(data, ensure_ascii=False, allow_nan=False), flush=True)


def progress(stage, **fields):
    print(json.dumps(dict(event=stage, **fields), ensure_ascii=False), file=sys.stderr, flush=True)


def run(args, timeout=600, cwd=None):
    try:
        result = subprocess.run([str(a) for a in args], capture_output=True,
                                creationflags=CREATE_NO_WINDOW, timeout=timeout, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CutError(str(e)) from e
    if result.returncode:
        raise CutError(result.stderr.decode('utf-8', errors='replace')[-5000:])
    return result


def tool(name):
    env = os.environ.get('CODECUT_' + name.upper())
    candidates = ([env] if env else []) + [str(ROOT / 'tools' / (name + '.exe')), str(ROOT / 'tools' / name), shutil.which(name)]
    if name == 'ffmpeg':
        candidates += [str(p) for p in (ROOT / 'tools').glob('ffmpeg*.exe')]
    for p in candidates:
        if p and Path(p).is_file():
            try:
                run([p, '-version'], timeout=10)
                return str(Path(p).resolve())
            except CutError:
                continue
    raise CutError(f'{name} unavailable. Set CODECUT_{name.upper()} to its executable path.')


def media_info(path):
    ff = tool('ffmpeg')
    try:
        result = subprocess.run([ff, '-hide_banner', '-i', str(path)], capture_output=True,
                                creationflags=CREATE_NO_WINDOW, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CutError(str(e)) from e
    text = result.stderr.decode('utf-8', errors='replace')
    match = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', text)
    duration = sum(float(v) * f for v, f in zip(match.groups(), [3600, 60, 1])) if match else None
    if 'Video:' not in text and 'Audio:' not in text:
        raise CutError(f'Cannot read media: {path}\n{text[-1800:]}')
    return dict(duration=duration, video='Video:' in text, audio='Audio:' in text)


def save(path, project):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        json.dump(project, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        raise CutError(f'Cannot read project: {e}') from e
    if not isinstance(data, dict) or data.get('version') != 1:
        raise CutError('Project must be an object with version: 1.')
    return data


def number(value, name, low=0, high=86400, inclusive=True):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise CutError(f'{name} must be a finite number.')
    if value < low or value > high or (not inclusive and value == low):
        raise CutError(f'{name} must be {">" if not inclusive else ">="} {low} and <= {high}.')
    return value


def local_source(item, project_path):
    source = item.get('source', '')
    if not isinstance(source, str) or not source:
        raise CutError('source must be a non-empty string.')
    if source.startswith(('http://', 'https://')):
        if item['kind'] != 'code':
            raise CutError('Only code sources accept HTTP URLs; download media to a local file first.')
        if not urlparse(source).hostname:
            raise CutError('Invalid source URL.')
        return source
    p = Path(source)
    p = (project_path.parent / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_file():
        raise CutError(f'Source not found: {p}')
    if item['kind'] == 'code' and p.suffix.lower() not in ('.html', '.htm'):
        raise CutError('Code source must be an HTML entry file or a running HTTP URL.')
    return p


def validate(project, path, require_scenes=True):
    if not isinstance(project.get('scenes'), list) or not isinstance(project.get('audio'), list):
        raise CutError('scenes and audio must be arrays.')
    for field, low, high in [('width', 64, 3840), ('height', 64, 2160), ('fps', 1, 60)]:
        n = number(project.get(field), field, low, high)
        if not isinstance(n, int) or (field != 'fps' and n % 2):
            raise CutError(f'{field} must be an integer' + (' divisible by 2.' if field != 'fps' else '.'))
    if require_scenes and not project['scenes']:
        raise CutError('Add at least one visual scene.')
    ids = set()
    def check(item, overlay=False, audio=False):
        if not isinstance(item, dict):
            raise CutError('Every clip must be an object.')
        ident = item.get('id')
        if not isinstance(ident, str) or not ident or ident in ids:
            raise CutError('Every clip needs a unique non-empty string id.')
        ids.add(ident)
        if item.get('kind') not in (['audio'] if audio else ['code', 'video', 'image']):
            raise CutError(f'Unsupported clip kind: {item.get("kind")}')
        number(item.get('duration'), 'duration', 0, 86400, inclusive=False)
        if item['duration'] * project['fps'] < 1:
            raise CutError('Clip duration must be at least one frame.')
        number(item.get('trim', 0), 'trim')
        number(item.get('volume', 1), 'volume', 0, 4)
        number(item.get('speed', 1), 'speed', .25, 4)
        for f in ['fade_in', 'fade_out']:
            number(item.get(f, 0), f, 0, item['duration'])
        if not audio:
            number(item.get('brightness', 0), 'brightness', -1, 1)
            number(item.get('contrast', 1), 'contrast', 0, 3)
            number(item.get('saturation', 1), 'saturation', 0, 3)
            if item.get('rotate', 0) not in [0, 90, 180, 270]:
                raise CutError('rotate must be 0, 90, 180 or 270.')
            crop = item.get('crop', [0, 0, 0, 0])
            if not isinstance(crop, list) or len(crop) != 4:
                raise CutError('crop must be [left, top, right, bottom].')
            for v in crop:
                number(v, 'crop', 0, .95)
            if crop[0]+crop[2] >= .98 or crop[1]+crop[3] >= .98:
                raise CutError('Crop must leave at least 2% of the image.')
        number(item.get('wait', 0.3), 'wait', 0, 60)
        local_source(item, path)
        if overlay:
            number(item.get('start', 0), 'start')
            for f in ['x', 'y']:
                number(item.get(f, 0), f, 0, project['width'] if f == 'x' else project['height'])
            for f, limit in [('width', project['width']), ('height', project['height'])]:
                n = number(item.get(f), f, 2, limit)
                if n != int(n) or n % 2:
                    raise CutError('Overlay dimensions must be even integers.')
            if item.get('x', 0) + item['width'] > project['width'] or item.get('y', 0) + item['height'] > project['height']:
                raise CutError('Overlay rectangle must fit inside the canvas.')
        if audio:
            number(item.get('start', 0), 'start')
        layers = item.get('overlays', [])
        if not isinstance(layers, list) or ((audio or overlay) and layers):
            raise CutError('Only scenes may have overlays, and overlays must be an array.')
        for layer in layers:
            check(layer, overlay=True)
    for scene in project['scenes']:
        check(scene)
    for audio in project['audio']:
        check(audio, audio=True)
    if not isinstance(project.get('texts', []), list):
        raise CutError('texts must be an array.')
    for title in project.get('texts', []):
        if not isinstance(title, dict) or not isinstance(title.get('id'), str) or title['id'] in ids:
            raise CutError('Text needs a unique string id.')
        ids.add(title['id'])
        if not isinstance(title.get('text'), str) or not title['text'].strip() or len(title['text']) > 2000:
            raise CutError('Text must contain 1..2000 characters.')
        number(title.get('start', 0), 'text start')
        number(title.get('duration'), 'text duration', 0, 86400, inclusive=False)
        number(title.get('font_size', 48), 'font_size', 8, 500)
        number(title.get('x', project['width']/2), 'text x', 0, project['width'])
        number(title.get('y', project['height']*.8), 'text y', 0, project['height'])
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', title.get('color', '#ffffff')):
            raise CutError('Text color must be #RRGGBB.')
    return project


def duration(item, fps):
    return round(item['duration'] * fps) / fps


@contextlib.contextmanager
def serve(folder):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(folder)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)



def launch_browser(pw):
    """Playwright's own Chromium, else the installed Edge or Chrome (Playwright's download goes missing whenever
    the package is updated; the system browser keeps rendering working)."""
    errors = []
    for channel in (None, 'msedge', 'chrome'):
        try:
            return pw.chromium.launch(headless=True, **({'channel': channel} if channel else {}))
        except Exception as e:
            errors.append(f"{channel or 'chromium'}: {str(e).splitlines()[0]}")
    raise CutError('No browser for code scenes. Install Microsoft Edge or Chrome, or run: '
                   'python -m playwright install chromium (' + '; '.join(errors) + ')')


@contextlib.contextmanager
def code_page(item, project_path, width, height):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise CutError('Install dependencies: python -m pip install -r requirements.txt; python -m playwright install chromium') from e
    source = local_source(item, project_path)
    root = item.get('root')
    folder = (project_path.parent / root).resolve() if root else (source.parent if isinstance(source, Path) else None)
    with contextlib.ExitStack() as stack:
        if isinstance(source, Path):
            if not folder.is_dir() or not source.is_relative_to(folder):
                raise CutError('Code entry must be inside root.')
            base = stack.enter_context(serve(folder))
            url = base + '/' + quote(source.relative_to(folder).as_posix())
        else:
            url = source
        pw = stack.enter_context(sync_playwright())
        browser = launch_browser(pw)
        stack.callback(browser.close)
        page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        response = page.goto(url, wait_until='load', timeout=30000)
        if response is not None and response.status >= 400:
            raise CutError(f'Code entry returned HTTP {response.status}.')
        page.wait_for_timeout(int(item.get('wait', 0.3) * 1000))
        page.evaluate('() => document.fonts.ready')
        page.evaluate('''() => {
          window.__codecutTimeout = window.setTimeout.bind(window);
          window.__codecutClearTimeout = window.clearTimeout.bind(window);
        }''')
        hook = page.evaluate("() => typeof window.renderFrame === 'function'")
        if not hook:
            # Freeze JS clocks; then advance timers/requestAnimationFrame one frame at a time.
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            page.clock.install(time=now)
            page.clock.pause_at(now)
        yield page, hook, errors


def seek_page(page, hook, seconds, width, height, delta_ms):
    if not hook and delta_ms > 0:
        page.clock.run_for(delta_ms)
    page.evaluate('''async ({t,w,h,hook}) => {
      const later=window.__codecutTimeout, cancel=window.__codecutClearTimeout;
      if (hook) {
        let id;
        try {
          await Promise.race([
            Promise.resolve().then(()=>window.renderFrame(t,{width:w,height:h})),
            new Promise((_,reject)=>{id=later(()=>reject(new Error('renderFrame timed out after 30 seconds')),30000);})
          ]);
        } finally {cancel(id);}
      }
      for (const a of document.getAnimations()) { a.pause(); a.currentTime = t*1000; }
      for (const v of document.querySelectorAll('video')) {
        v.pause();
        if (Number.isFinite(v.duration) && v.duration > 0) {
          const target=Math.min(t,Math.max(0,v.duration-0.001));
          if(Math.abs(v.currentTime-target)>0.001) {
            await new Promise((resolve,reject)=>{
              const timer=later(()=>reject(new Error('Embedded video seek timed out')),5000);
              v.addEventListener('seeked',()=>{cancel(timer);resolve();},{once:true});
              v.currentTime=target;
            });
          }
        }
      }
    }''', dict(t=seconds, w=width, h=height, hook=hook))


def encode_code(item, project, path, dest, width, height):
    ff = tool('ffmpeg')
    fps = project['fps']
    frames = round(item['duration'] * fps)
    args = [ff, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', fps,
            '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
            '-pix_fmt', 'yuv420p', '-r', fps, '-frames:v', frames, str(dest)]
    with code_page(item, path, width, height) as (page, hook, errors), tempfile.TemporaryFile() as log:
        progress('code', id=item['id'], mode='renderFrame' if hook else 'browser-clock', frames=frames)
        proc = subprocess.Popen([str(a) for a in args], stdin=subprocess.PIPE, stderr=log,
                                stdout=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        try:
            for n in range(frames):
                t = item.get('trim', 0) + n / fps * item.get('speed', 1)
                delta = round(t*1000) if n == 0 else round(t*1000)-round((t-item.get('speed',1)/fps)*1000)
                seek_page(page, hook, t, width, height, delta)
                if errors:
                    raise CutError(f'Code scene {item["id"]}: {errors[0]}')
                proc.stdin.write(page.screenshot(type='png', timeout=30000))
                if n % max(fps, 1) == 0:
                    progress('frames', id=item['id'], done=n+1, total=frames)
            proc.stdin.close()
            proc.wait(timeout=120)
            if proc.returncode:
                log.seek(0)
                raise CutError(log.read().decode('utf-8', errors='replace')[-3000:])
        except BrokenPipeError as e:  # ffmpeg quit while pictures were still going in: its own log says why
            proc.wait(timeout=30)
            log.seek(0)
            raise CutError('ffmpeg stopped early: ' + log.read().decode('utf-8', errors='replace')[-3000:]) from e
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if proc.stdin is not None and not proc.stdin.closed:
                with contextlib.suppress(BrokenPipeError, OSError):
                    proc.stdin.close()


def audio_filter(item, d):
    speed = item.get('speed', 1)
    parts = ['asetpts=PTS-STARTPTS', 'aresample=48000']
    while speed > 2:
        parts.append('atempo=2')
        speed /= 2
    while speed < .5:
        parts.append('atempo=0.5')
        speed *= 2
    parts += [f'atempo={speed}', f'atrim=duration={d}', f'volume={item.get("volume",1)}']
    for key, mode, start in [('fade_in','in',0), ('fade_out','out',max(0,d-item.get('fade_out',0)))]:
        if item.get(key, 0):
            parts.append(f'afade=t={mode}:st={start}:d={item[key]}')
    return ','.join(parts)


def encode_visual(item, project, path, dest, scratch, width=None, height=None):
    ff = tool('ffmpeg')
    w, h = width or project['width'], height or project['height']
    fps = project['fps']
    d = duration(item, fps)
    kind = item['kind']
    trim = item.get('trim', 0)
    source = local_source(item, path)
    audio = False
    if kind == 'code':
        source = scratch / f'code-{uuid.uuid4().hex}.mp4'
        encode_code(item, project, path, source, w, h)
        inputs = ['-i', source]
    elif kind == 'image':
        inputs = ['-loop', '1', '-framerate', fps, '-i', source]
    else:
        info = media_info(source)
        if not info['video']:
            raise CutError(f'No video stream: {source}')
        if info['duration'] is not None and trim + d * item.get('speed', 1) > info['duration'] + 0.05:
            raise CutError(f'Clip {item["id"]} extends beyond source duration {info["duration"]}.')
        audio = info['audio']
        inputs = ['-ss', trim, '-i', source]
    if not audio:
        inputs += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    filters = []
    if kind == 'video':
        filters.append(f'setpts=(PTS-STARTPTS)/{item.get("speed",1)}')
    l,t,r,b = item.get('crop', [0,0,0,0])
    if any([l,t,r,b]):
        filters.append(f'crop=iw*{1-l-r}:ih*{1-t-b}:iw*{l}:ih*{t}')
    rotation = item.get('rotate', 0)
    if rotation in [90, 270]:
        filters.append('transpose=' + ('1' if rotation == 90 else '2'))
    elif rotation == 180:
        filters.extend(['hflip', 'vflip'])
    if item.get('mirror', False):
        filters.append('hflip')
    filters += [f'scale={w}:{h}:force_original_aspect_ratio=decrease', f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2',
                'setsar=1', f'fps={fps}', f'tpad=stop_mode=clone:stop_duration={d}',
                f'eq=brightness={item.get("brightness",0)}:contrast={item.get("contrast",1)}:saturation={item.get("saturation",1)}']
    if item.get('fade_in', 0):
        filters.append(f'fade=t=in:st=0:d={item["fade_in"]}')
    if item.get('fade_out', 0):
        filters.append(f'fade=t=out:st={max(0,d-item["fade_out"])}:d={item["fade_out"]}')
    vf = ','.join(filters)
    af = audio_filter(item if audio else {'volume':0}, d) + ',apad'
    run([ff, '-hide_banner', '-loglevel', 'error', '-y', *inputs, '-map', '0:v:0', '-map', '0:a:0' if audio else '1:a:0',
         '-vf', vf, '-af', af, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-t', d, '-video_track_timescale', '90000', dest])


def render(project, path, output, force=False, single=None):
    validate(project, path)
    scenes = project['scenes']
    if single:
        scenes = [s for s in scenes if s['id'] == single]
        if not scenes:
            raise CutError(f'Scene not found: {single}')
    output = output.resolve()
    if output.suffix.lower() != '.mp4':
        raise CutError('Output must end in .mp4.')
    sources = [path.resolve()]
    for s in project['scenes'] + project['audio']:
        for item in [s] + s.get('overlays', []):
            src = local_source(item, path)
            if isinstance(src, Path):
                sources.append(src)
    if output in sources:
        raise CutError('Output may not overwrite a project or source file.')
    if output.exists() and not force:
        raise CutError('Output already exists. Use --force to replace it.')
    output.parent.mkdir(parents=True, exist_ok=True)
    ff = tool('ffmpeg')
    with tempfile.TemporaryDirectory(prefix='codecut-') as temp:
        scratch = Path(temp)
        final_scenes = []
        for i, scene in enumerate(scenes):
            progress('scene', id=scene['id'], index=i+1, total=len(scenes))
            base = scratch / f'scene-{i}.mp4'
            encode_visual(scene, project, path, base, scratch)
            for j, layer in enumerate(scene.get('overlays', [])):
                overlay = scratch / f'layer-{i}-{j}.mp4'
                encode_visual(layer, project, path, overlay, scratch, layer['width'], layer['height'])
                combined = scratch / f'mix-{i}-{j}.mp4'
                # Overlay audio is intentionally muted; add sound on the audio track explicitly.
                start = layer.get('start', 0)
                graph = f'[1:v]setpts=PTS-STARTPTS+{start}/TB[layer];[0:v][layer]overlay=x={layer.get("x",0)}:y={layer.get("y",0)}:eof_action=pass:repeatlast=0:enable=\'gte(t,{start})\'[v]'
                run([ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', base, '-i', overlay,
                     '-filter_complex', graph, '-map', '[v]', '-map', '0:a:0', '-c:v', 'libx264',
                     '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                     '-r', project['fps'], '-video_track_timescale', '90000',
                     '-t', duration(scene, project['fps']), combined])
                base = combined
            final_scenes.append(base)
        listing = scratch / 'concat.txt'
        listing.write_text(''.join(f"file '{p.name}'\n" for p in final_scenes), encoding='utf-8')
        joined = scratch / 'joined.mp4'
        # Re-encode audio once across joins to avoid per-segment AAC priming gaps.
        run([ff, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', listing,
             '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-ac', '2', joined], cwd=scratch)
        total = sum(duration(s, project['fps']) for s in scenes)
        fd, pending_name = tempfile.mkstemp(prefix='.codecut-', suffix='.mp4', dir=output.parent)
        os.close(fd)
        pending = Path(pending_name)
        try:
            audio_tracks = [] if single else project['audio']
            inputs = ['-i', joined]
            filters = ['[0:a]apad[baseaudio]']
            labels = ['[baseaudio]']
            for i, a in enumerate(audio_tracks, 1):
                src = local_source(a, path)
                info = media_info(src)
                if not info['audio']:
                    raise CutError(f'No audio stream: {src}')
                if info['duration'] is not None and a.get('trim', 0) + a['duration'] * a.get('speed',1) > info['duration'] + .05:
                    raise CutError(f'Audio clip {a["id"]} extends beyond source duration.')
                if a.get('start', 0) >= total:
                    raise CutError(f'Audio clip {a["id"]} starts after the visual timeline ends.')
                inputs += ['-ss', a.get('trim', 0), '-i', src]
                delay = round(a.get('start', 0) * 1000)
                filters.append(f'[{i}:a]{audio_filter(a, a["duration"])},adelay={delay}:all=1[a{i}]')
                labels.append(f'[a{i}]')
            filters.append(''.join(labels) + f'amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95:latency=1[a]')
            titles = [] if single else project.get('texts', [])
            vmap, vcodec = '0:v:0', ['-c:v', 'copy']
            for n, title in enumerate(titles):
                png = scratch / f'title-{n}.png'
                make_title(title, project['width'], project['height'], png)
                idx = 1 + len(audio_tracks) + n
                inputs += ['-loop', '1', '-framerate', project['fps'], '-i', png]
                start = title.get('start', 0)
                end = start + title['duration']
                filters.append(f'[{"0:v" if n == 0 else "title"+str(n-1)}][{idx}:v]overlay=enable=\'gte(t,{start})*lt(t,{end})\':shortest=1[title{n}]')
                vmap = f'[title{n}]'
                vcodec = ['-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r',project['fps']]
            run([ff, '-hide_banner', '-loglevel', 'error', '-y', *inputs, '-filter_complex', ';'.join(filters),
                 '-map', vmap, '-map', '[a]', *vcodec, '-c:a', 'aac', '-ar', '48000', '-ac', '2',
                 '-t', total, '-movflags', '+faststart', pending])
            # Decode the actual result before publishing it.
            decoded = run([ff, '-v', 'error', '-xerror', '-i', pending, '-progress', 'pipe:1', '-f', 'null', '-'])
            counts = re.findall(rb'(?m)^frame=(\d+)', decoded.stdout)
            expected_frames = sum(round(s['duration'] * project['fps']) for s in scenes)
            if not counts or int(counts[-1]) != expected_frames:
                raise CutError('Rendered frame count does not match the timeline.')
            info = media_info(pending)
            if info['duration'] is None or abs(info['duration'] - total) > 1/project['fps'] + .04:
                raise CutError('Rendered duration does not match the timeline.')
            if force:
                os.replace(pending, output)
            else:
                if output.exists():
                    raise CutError('Output appeared during render; it was not overwritten.')
                pending.rename(output)
        finally:
            pending.unlink(missing_ok=True)
    return dict(ok=True, output=str(output), duration=total, scenes=len(scenes),
                width=project['width'], height=project['height'], fps=project['fps'])


def make_title(title, width, height, output):
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for candidate in [r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\arial.ttf', '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/Library/Fonts/Arial Unicode.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(candidate).is_file():
            font = ImageFont.truetype(candidate, int(title.get('font_size',48)))
            break
    font = font or ImageFont.load_default()
    image = Image.new('RGBA', (width,height))
    draw = ImageDraw.Draw(image)
    text = title['text']
    box = draw.multiline_textbbox((0,0), text, font=font, spacing=8, stroke_width=1)
    tw, th = box[2]-box[0], box[3]-box[1]
    x = title.get('x',width/2)-tw/2-box[0]
    y = title.get('y',height*.8)-th/2-box[1]
    if title.get('box',True):
        draw.rounded_rectangle((x+box[0]-14,y+box[1]-8,x+box[2]+14,y+box[3]+8),radius=8,fill=(0,0,0,155))
    draw.multiline_text((x,y), text, fill=title.get('color','#ffffff'), font=font,spacing=8,align='center',stroke_width=1,stroke_fill=(0,0,0,190))
    image.save(output)


def find_item(project, ident):
    for group in [project['scenes'], project['audio'], project.get('texts',[])] + [s.get('overlays', []) for s in project['scenes']]:
        for item in group:
            if item['id'] == ident:
                return group, item
    raise CutError(f'Clip not found: {ident}')


FIXED_FIELDS = {'id', 'kind', 'overlays'}


def add_subtitles(project, path, args):
    """Each cue of an .srt becomes a title at its own time. The file is read as it comes from CodeTools or anywhere else."""
    from editor_model import EditorModel

    if not args.file.is_file():
        raise CutError(f'No such file: {args.file}')
    raw = args.file.read_bytes()
    try:
        words = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        words = raw.decode('gb18030', 'replace')
    stamp = re.compile(r'(\d+):(\d\d):(\d\d)[,.](\d{3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{3})')
    project.setdefault('texts', [])
    project.setdefault('assets', [])
    model = EditorModel()
    model.path, model.data = path, project
    added = 0
    for block in re.split(r'\n\s*\n', words.replace('\r\n', '\n').strip()):
        m = stamp.search(block)
        line = block[m.end():].strip() if m else ''
        if not m or not line:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000 + args.shift
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000 + args.shift
        ident = model.add_text(max(0, start), line)
        model.update(ident, {'start': model.quantize(max(0, start)), 'duration': max(.2, end - start), 'font_size': args.size, 'color': '#ffffff', 'box': True,
                             'x': project['width'] / 2, 'y': project['height'] * .88})
        added += 1
    if not added:
        raise CutError('No subtitles in that file.')
    validate(project, path, require_scenes=False)
    save(path, project)
    return {'ok': True, 'added': added}


def edit(project, path, args):
    """The editor's own operations (editor_model.EditorModel) on the project file, so the terminal and the window
    edit the same way. Source paths stay as they are in the file."""
    sys.path.insert(0, str(ROOT))
    from editor_model import EditorModel
    project.setdefault('texts', [])
    project.setdefault('assets', [])
    model = EditorModel()
    model.path, model.data = path, project
    if args.command != 'text':
        find_item(project, args.id)  # 'Clip not found: ...' rather than the window's hint
    if args.command == 'split':
        try:
            right = model.split(args.id, args.time)
        except Exception as e:
            if type(e).__name__ != 'CutError':
                raise
            raise CutError('time must be inside the clip, at least one frame from either end '
                           '(global timeline seconds; see list).') from e
        result = {'ok': True, 'left': args.id, 'right': right}
    elif args.command == 'text':
        if args.id and any(i.get('id') == args.id for i in model.all_items(project)):
            raise CutError(f'id already used: {args.id}')
        start = args.start
        ident = model.add_text(start, args.text)
        fields = {'start': model.quantize(max(0, start)), 'duration': args.duration, 'font_size': args.size,
                  'color': args.color, 'box': not args.no_box,
                  'x': args.x if args.x is not None else project['width'] / 2,
                  'y': args.y if args.y is not None else project['height'] * .8}
        model.update(ident, fields)
        if args.id:
            model.locate(ident)[1]['id'] = ident = args.id
        result = {'ok': True, 'id': ident}
    elif args.command == 'update':
        try:
            fields = json.loads(args.fields)
        except ValueError as e:
            raise CutError(f'fields must be a JSON object: {e}') from e
        if not isinstance(fields, dict) or not fields:
            raise CutError('fields must be a non-empty JSON object.')
        if FIXED_FIELDS & fields.keys():
            raise CutError('id, kind and overlays cannot be changed this way.')
        model.update(args.id, fields)
        result = {'ok': True, 'id': args.id, 'clip': model.locate(args.id)[1]}
    else:
        before = {i['id'] for i in model.all_items(project)}
        model.duplicate(args.id)
        result = {'ok': True, 'id': next(i['id'] for i in model.all_items(project) if i['id'] not in before)}
    validate(project, path, require_scenes=False)
    save(path, project)
    return result


def schema():
    return {
        'version': 1, 'units': 'seconds; pixels; volume 0..4',
        'project': {'version': 1, 'width': 1280, 'height': 720, 'fps': 30, 'scenes': [], 'audio': [], 'texts': []},
        'scene': {'id': 's1', 'kind': 'code|video|image', 'source': 'path or HTTP URL (code only)',
                  'duration': 5, 'trim': 0, 'volume': 1, 'overlays': []},
        'overlay': {'id': 'o1', 'kind': 'code|video|image', 'source': 'path', 'duration': 5,
                    'x': 20, 'y': 20, 'width': 320, 'height': 180},
        'audio': {'id': 'a1', 'kind': 'audio', 'source': 'music.mp3', 'duration': 5, 'start': 0, 'trim': 0, 'volume': 0.5},
        'text': {'id':'t1','kind':'text','text':'Title','start':0,'duration':3,'font_size':48,'color':'#ffffff','x':640,'y':576,'box':True},
        'clip_options': {'speed':1,'fade_in':0,'fade_out':0,'rotate':0,'mirror':False,'crop':[0,0,0,0],'brightness':0,'contrast':1,'saturation':1},
        'code_hook': 'Optional: window.renderFrame = async (seconds, {width,height}) => { draw(seconds); };',
        'code_options': {'wait': 0.3, 'root': 'folder served over HTTP, relative to project.json (default: the entry\'s folder)'},
        'overlay_options': {'start': 0},
        'editor_fields': {'name': 'label shown in the window', 'assets': 'the window\'s media library',
                          '_thumbnail': 'cached preview', '_waveform': 'cached preview', '_source_duration': 'media length'},
        'rules': ['Scene order is playback order.', 'Paths in JSON are relative to project.json.',
                  'code_options: wait = seconds a page settles before its first frame (0..60); add sets it on code clips.',
                  'Every field listed here is valid; the desktop editor\'s own fields (editor_fields) are kept as they are.',
                  'Overlay start is relative to its scene; overlay audio is muted.',
                  'duration is output time; trim and duration*speed select the source range. Text start is global time.',
                  'Browser audio is not captured; add an audio clip.',
                  'No npm install, repository scripts or arbitrary shell commands are executed.',
                  'Built projects: provide an HTML entry; development servers: provide their running URL.']}


def parser():
    p = argparse.ArgumentParser(description='CodeCut — code + video + audio -> MP4. stdout JSON; stderr progress.')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Check FFmpeg and Chromium by actually launching them')
    sub.add_parser('schema', help='Print the configuration contract for AI')
    init = sub.add_parser('init', help='Create an empty project')
    init.add_argument('project', type=Path)
    init.add_argument('--width', type=int, default=1280)
    init.add_argument('--height', type=int, default=720)
    init.add_argument('--fps', type=int, default=30)
    for name in ['list', 'check', 'remove', 'move', 'add', 'render', 'preview', 'set']:
        s = sub.add_parser(name)
        s.add_argument('project', type=Path)
        if name in ['remove', 'move', 'set']:
            s.add_argument('id')
        if name == 'move':
            s.add_argument('position', type=int, help='1-based position within its track')
        if name == 'set':
            s.add_argument('field', choices=['duration', 'trim', 'volume', 'start', 'x', 'y', 'width', 'height', 'wait'])
            s.add_argument('value', type=float)
        if name == 'add':
            s.add_argument('kind', choices=['code', 'video', 'audio', 'image'])
            s.add_argument('source')
            s.add_argument('--id')
            s.add_argument('--duration', type=float)
            s.add_argument('--trim', type=float, default=0)
            s.add_argument('--volume', type=float, default=1)
            s.add_argument('--start', type=float, default=0, help='Audio start on the global timeline')
            s.add_argument('--entry', help='HTML path relative to a selected repository/directory')
            s.add_argument('--root', help='Local HTTP server root for code assets')
            s.add_argument('--wait', type=float, default=.3, help='Page load settling time in seconds')
            s.add_argument('--over', help='Parent scene id for an overlay')
            for f, default in [('x', 20), ('y', 20), ('width', 320), ('height', 180)]:
                s.add_argument('--' + f, type=int, default=default)
        if name in ['render', 'preview']:
            s.add_argument('-o', '--output', type=Path)
            s.add_argument('--force', action='store_true')
        if name == 'preview':
            s.add_argument('--scene', help='Render only this scene, without global soundtracks')
            s.add_argument('--open', action='store_true', help='Open the resulting MP4 in the system player')
    split = sub.add_parser('split', help='Split a clip at a time on the global timeline (the editor\'s Ctrl+B)')
    split.add_argument('project', type=Path)
    split.add_argument('id')
    split.add_argument('time', type=float, help='Seconds on the global timeline, inside the clip')
    subs = sub.add_parser('subtitles', help='Add every line of an .srt file as a title')
    subs.add_argument('project', type=Path)
    subs.add_argument('file', type=Path)
    subs.add_argument('--size', type=int, default=36)
    subs.add_argument('--shift', type=float, default=0, help='Seconds to move them all by')
    text = sub.add_parser('text', help='Add a title burned into the video')
    text.add_argument('project', type=Path)
    text.add_argument('text')
    text.add_argument('--id')
    text.add_argument('--start', type=float, default=0, help='Global timeline time')
    text.add_argument('--duration', type=float, default=3)
    text.add_argument('--size', type=int, default=48)
    text.add_argument('--color', default='#ffffff')
    text.add_argument('--x', type=float, help='Centre x in canvas pixels (default: middle)')
    text.add_argument('--y', type=float, help='Centre y in canvas pixels (default: lower fifth)')
    text.add_argument('--no-box', action='store_true', help='No dark box behind the text')
    update = sub.add_parser('update', help='Change any fields of a clip, given as a JSON object')
    update.add_argument('project', type=Path)
    update.add_argument('id')
    update.add_argument('fields', help='e.g. {"speed": 2, "fade_in": 0.5, "saturation": 1.2}')
    dup = sub.add_parser('duplicate', help='Copy a clip right after itself')
    dup.add_argument('project', type=Path)
    dup.add_argument('id')
    info = sub.add_parser('info', help='Duration and streams of a media file')
    info.add_argument('media', type=Path)
    repo = sub.add_parser('repo', help='Clone a Git repository; never runs its scripts')
    repo.add_argument('url')
    repo.add_argument('directory', type=Path)
    demo = sub.add_parser('demo', help='Create a runnable project with animation, video, MP3, and overlay')
    demo.add_argument('directory', type=Path)
    return p


def demo(folder):
    if folder.exists() and any(folder.iterdir()):
        raise CutError('Demo directory must be empty or absent.')
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / 'examples' / 'animation.html', folder / 'animation.html')
    ff = tool('ffmpeg')
    run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=24:duration=2',
         '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', folder / 'video.mp4'])
    run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:sample_rate=48000:duration=4',
         '-c:a', 'libmp3lame', folder / 'music.mp3'])
    project = {'version': 1, 'width': 640, 'height': 360, 'fps': 24,
        'scenes': [
            {'id': 'intro', 'kind': 'code', 'source': 'animation.html', 'duration': 2},
            {'id': 'video', 'kind': 'video', 'source': 'video.mp4', 'duration': 2, 'volume': .4,
             'overlays': [{'id': 'picture', 'kind': 'code', 'source': 'animation.html', 'duration': 2,
                           'x': 360, 'y': 190, 'width': 256, 'height': 144}]}],
        'audio': [{'id': 'music', 'kind': 'audio', 'source': 'music.mp3', 'duration': 3.5, 'start': .5, 'volume': .2}]}
    save(folder / 'project.json', project)
    return {'ok': True, 'project': str((folder / 'project.json').resolve()), 'next': 'render project.json -o result.mp4'}


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == 'schema':
        return schema()
    if args.command == 'doctor':
        checks = {}
        try:
            ff = tool('ffmpeg')
            run([ff, '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:d=0.1', '-c:v', 'libx264', '-f', 'null', '-'])
            checks['ffmpeg'] = {'ok': True, 'path': ff}
        except CutError as e:
            checks['ffmpeg'] = {'ok': False, 'error': str(e)}
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = launch_browser(pw)
                page = browser.new_page()
                page.set_content('<h1>CodeCut</h1>')
                assert page.locator('h1').inner_text() == 'CodeCut'
                assert len(page.screenshot()) > 100
                browser.close()
            checks['chromium'] = {'ok': True}
        except Exception as e:
            checks['chromium'] = {'ok': False, 'error': str(e)}
        return {'ok': all(v['ok'] for v in checks.values()), 'checks': checks}
    if args.command == 'repo':
        if args.url.startswith('-') or any(c in args.url for c in '\r\n'):
            raise CutError('Invalid Git URL.')
        if args.directory.exists():
            raise CutError('Clone destination must not already exist.')
        git = shutil.which('git')
        if not git:
            raise CutError('Git is not installed.')
        run([git, '-c', 'core.hooksPath=', 'clone', '--depth', '1', '--', args.url, args.directory.resolve()], timeout=300)
        entries = [str(p.relative_to(args.directory)) for p in args.directory.rglob('*.html') if '.git' not in p.parts][:100]
        return {'ok': True, 'directory': str(args.directory.resolve()), 'html_entries': entries}
    if args.command == 'demo':
        return demo(args.directory.resolve())
    if args.command == 'info':
        return {'ok': True, 'media': str(args.media.resolve()), **media_info(args.media.resolve())}
    path = args.project.resolve()
    if args.command == 'init':
        if path.exists():
            raise CutError('Project already exists.')
        project = dict(version=1, width=args.width, height=args.height, fps=args.fps, scenes=[], audio=[])
        validate(project, path, require_scenes=False)
        save(path, project)
        return {'ok': True, 'project': str(path)}
    project = load(path)
    validate(project, path, require_scenes=False)
    if args.command == 'add':
        source = args.source
        root = args.root
        if not source.startswith(('http://', 'https://')):
            src = Path(source).resolve()
            if src.is_dir():
                if args.kind != 'code':
                    raise CutError('Directories may only be used as code sources.')
                root = str(src)
                entry = Path(args.entry or 'index.html')
                src = (src / entry).resolve()
                if not src.is_relative_to(Path(root)):
                    raise CutError('Entry must be inside the selected directory.')
            source = Path(os.path.relpath(src, path.parent)).as_posix()  # the same file on every system
        item = dict(id=args.id or uuid.uuid4().hex[:8], kind=args.kind, source=source,
                    duration=args.duration, trim=args.trim, volume=args.volume)
        if args.kind == 'code':
            item['wait'] = args.wait
            if root:
                item['root'] = Path(os.path.relpath(Path(root).resolve(), path.parent)).as_posix()
        src = local_source(item, path)
        if item['duration'] is None:
            if args.kind in ['video', 'audio']:
                info = media_info(src)
                if info['duration'] is None:
                    raise CutError('Cannot infer duration; provide --duration.')
                # Round down inferred durations to avoid reading past the last frame.
                item['duration'] = math.floor((info['duration']-args.trim)*project['fps'])/project['fps']
            else:
                item['duration'] = 5
        if args.over:
            if args.kind == 'audio':
                raise CutError('Use --start for audio; --over accepts visual clips only.')
            parent = next((s for s in project['scenes'] if s['id'] == args.over), None)
            if parent is None:
                raise CutError('Overlay parent scene not found.')
            item.update(x=args.x, y=args.y, width=args.width, height=args.height)
            parent.setdefault('overlays', []).append(item)
        elif args.kind == 'audio':
            item['start'] = args.start
            project['audio'].append(item)
        else:
            project['scenes'].append(item)
        validate(project, path, require_scenes=False)
        save(path, project)
        return {'ok': True, 'clip': item}
    if args.command == 'subtitles':
        return add_subtitles(project, path, args)
    if args.command in ['split', 'text', 'update', 'duplicate']:
        return edit(project, path, args)
    if args.command == 'list':
        return {'ok': True, 'project': project, 'duration': sum(duration(s, project['fps']) for s in project['scenes'])}
    if args.command == 'check':
        validate(project, path)
        return {'ok': True, 'scenes': len(project['scenes']), 'audio': len(project['audio'])}
    if args.command in ['remove', 'move', 'set']:
        group, item = find_item(project, args.id)
        if args.command == 'remove':
            group.remove(item)
        elif args.command == 'move':
            if not 1 <= args.position <= len(group):
                raise CutError(f'position must be 1..{len(group)}.')
            group.remove(item)
            group.insert(args.position-1, item)
        else:
            if args.field == 'start' and item['kind'] != 'audio':
                raise CutError('start is supported only on audio clips.')
            if args.field in ['x', 'y', 'width', 'height'] and 'width' not in item:
                raise CutError('Rectangle fields are supported only on overlays.')
            value = args.value
            if args.field in ['x', 'y', 'width', 'height']:
                if not value.is_integer():
                    raise CutError('Rectangle fields must be integers.')
                value = int(value)
            item[args.field] = value
        validate(project, path, require_scenes=False)
        save(path, project)
        return {'ok': True, 'id': args.id}
    if args.command in ['render', 'preview']:
        dest = args.output or path.with_name('preview.mp4' if args.command == 'preview' else 'result.mp4')
        result = render(project, path, dest, args.force, getattr(args, 'scene', None))
        if getattr(args, 'open', False):
            if os.name == 'nt':
                os.startfile(result['output'])
            else:  # the export worked; only opening it is left to the person
                result = {**result, 'warnings': [*(result.get('warnings') or []), 'Automatic playback is available on Windows only; the MP4 was exported.']}
        return result
    raise CutError('Unknown command.')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        result = main()
        emit(result)
        sys.exit(0 if result.get('ok', True) else 1)
    except KeyboardInterrupt:
        emit({'ok': False, 'error': 'Cancelled.'})
        sys.exit(130)
    except Exception as e:
        emit({'ok': False, 'error': str(e) or type(e).__name__})
        sys.exit(1)
