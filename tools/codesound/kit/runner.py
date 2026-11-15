"""Runs song.py and renders it. A separate process, kept off the network and to its own folder (guard.py)."""
from __future__ import annotations

import array
import json
import os
from pathlib import Path
import runpy
import sys
import traceback
import wave

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))

import guard  # noqa: E402


def write_wav(path: Path, left: list, right: list, sr: int) -> None:
    data = array.array('h', bytes(4 * len(left)))
    scale = 32767
    for i in range(len(left)):
        a, b = left[i], right[i]
        data[2 * i] = int(scale * (1.0 if a > 1 else -1.0 if a < -1 else a))
        data[2 * i + 1] = int(scale * (1.0 if b > 1 else -1.0 if b < -1 else b))
    if sys.byteorder == 'big':
        data.byteswap()
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(data.tobytes())


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    folder = Path(job['folder'])
    script = folder / job['script']
    out = folder / 'out'
    out.mkdir(exist_ok=True)
    answer_at = Path(job['answer'])
    import cs
    import listen
    import synth
    import PIL
    from PIL import Image, ImageDraw, ImageFont, PngImagePlugin  # noqa: F401  (now: the guard keeps song.py from reading other folders)

    sr = job['sr']
    cs.SETTINGS.update(sr=sr, stems=job.get('stems', False), seed=job.get('seed', 7))
    cs.S.rnd.seed(cs.SETTINGS['seed'])
    guard.install(folder, [str(KIT), str(Path(os.__file__).parent), str(Path(sys.executable).parent), sys.base_prefix, str(Path(PIL.__file__).parent), os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')], str(script))
    try:
        os.chdir(folder)
        sys.path.insert(0, str(folder))
        runpy.run_path(str(script), run_name='__main__')
    except cs.SongError as e:
        answer_at.write_text(json.dumps({'ok': False, 'error': str(e), **_where(script)}, ensure_ascii=False), encoding='utf-8')
        return 1
    except Exception as e:
        answer_at.write_text(json.dumps({'ok': False, 'error': f'{type(e).__name__}: {e}', **_where(script), 'trace': traceback.format_exc()[-1500:]}, ensure_ascii=False), encoding='utf-8')
        return 1
    score = cs.score()
    (out / 'score.json').write_text(json.dumps(score, ensure_ascii=False), encoding='utf-8')
    if job['action'] == 'score':
        notes = listen.score_notes(score, synth.RANGES)
        answer_at.write_text(json.dumps({'ok': True, 'title': score['title'], 'seconds': score['seconds'], 'tracks': [{'name': t['name'], 'instrument': t['instrument'], 'notes': len(t['notes'])} for t in score['tracks']],
                                         'sections': score['sections'], 'warnings': notes}, ensure_ascii=False), encoding='utf-8')
        return 0

    def progress(what: str) -> None:
        print(json.dumps({'event': 'progress', 'at': what}, ensure_ascii=False), flush=True)

    files = []
    measured: dict = {}
    warnings = listen.score_notes(score, synth.RANGES)
    if cs.S.tracks:
        mix = cs.render(sr, progress)
        name = job['output']
        target = out / name
        write_wav(target, mix['left'], mix['right'], sr)
        files.append(target.relative_to(folder).as_posix())
        for stem, (a, b) in mix.get('stems', {}).items():
            (out / 'stems').mkdir(exist_ok=True)
            write_wav(out / 'stems' / f'{stem}.wav', a, b, sr)
            files.append(f'out/stems/{stem}.wav')
        progress('听一遍')
        measured = listen.measure(mix['left'], mix['right'], sr)
        warnings += listen.sound_notes(measured)
        listen.picture(out / 'latest.png', score, mix['left'], sr, measured)
    sounds = []
    if cs.S.saved:
        (out / 'sfx').mkdir(exist_ok=True)
        for sfx_name, sound in cs.S.saved:
            write_wav(out / 'sfx' / f'{sfx_name}.wav', sound, sound, sr)
            top = max((abs(v) for v in sound), default=0.0)
            sounds.append({'name': sfx_name, 'seconds': round(len(sound) / sr, 2), 'peak_db': round(listen.db(top), 1), 'file': f'out/sfx/{sfx_name}.wav'})
            files.append(f'out/sfx/{sfx_name}.wav')
    if not files:
        answer_at.write_text(json.dumps({'ok': False, 'error': 'song.py 没有写任何音乐，也没有 cs.save 任何声音。'}, ensure_ascii=False), encoding='utf-8')
        return 1
    curve = measured.pop('level_curve_db', [])
    per_beat = 60 / score['tempo']
    measured['level_by_section'] = [{'section': s['name'], 'db': _average(curve, s['start'] * per_beat, (s['start'] + s['bars'] * score['beats_per_bar']) * per_beat)} for s in score['sections']]
    answer_at.write_text(json.dumps({'ok': True, 'output': files[0], 'files': files[:60], 'sr': sr, 'measured': measured, 'sounds': sounds[:60], 'warnings': warnings,
                                     'picture': 'out/latest.png' if cs.S.tracks else ''}, ensure_ascii=False), encoding='utf-8')
    return 0


def _average(curve: list, start: float, end: float):
    part = curve[int(start * 2):max(int(start * 2) + 1, int(end * 2))]
    return round(sum(part) / len(part), 1) if part else None


def _where(script: Path) -> dict:
    """The line of song.py a mistake came from."""
    tb = sys.exc_info()[2]
    line = None
    while tb is not None:
        if Path(tb.tb_frame.f_code.co_filename) == script:
            line = tb.tb_lineno
        tb = tb.tb_next
    return {'line': line} if line else {}


if __name__ == '__main__':
    sys.exit(main())
