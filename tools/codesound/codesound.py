"""CodeSound's command line: music and sound effects written as code, rendered from nothing on this computer.

Every command prints one JSON object as its last line. A project is a folder: project.json, song.py, out/. No samples, no
downloads, no model: the sound is computed by kit/synth.py, in a low-priority process so that it can work behind a game.

    codesound init <folder>          a new project
    codesound schema                 the guide and the kit
    codesound check <folder>         is it written correctly (does not run it)
    codesound score <folder>         runs song.py without making sound: tracks, length, notes about the writing
    codesound render <folder>        --quality check (22 kHz, seconds) or final (44.1 kHz)   --stems
    codesound midi <folder>          the notes as a MIDI file
    codesound new <folder> --style 战斗 --seconds 90 --seed 3     a whole piece by rule
    codesound export <folder> --format mp3                       MP3, OGG or M4A
    codesound measure <file.wav>     any WAV: loudness, bands, faults
"""
from __future__ import annotations

import right_python

right_python.use('PIL')

import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
KIT = ROOT / 'kit'
SETTINGS = {'name': '', 'script': 'song.py', 'seed': 7, 'max_seconds': 1800}
STARTER = '''"""A song is a small Python file. The numbers are the scale: 1 is the key's first note, 5' one octave up. Beats after the colon."""
import cs

cs.song(tempo=84, key='D minor', title='First song')

piano = cs.track('piano', vol=.8, pan=-.12, reverb=.25)
strings = cs.track('strings', vol=.42, pan=.2, reverb=.4, low_cut=180, wide=.4)
flute = cs.track('flute', vol=.62, pan=.08, reverb=.35)
bass = cs.track('double_bass', vol=.8, reverb=.05)

with cs.section('quiet', 4):
    piano.chords('Dm | Bb | F | C', style='arp_up', every=.5, octave=3, vel=.55)
    bass.bass('Dm | Bb | F | C')

with cs.section('tune', 8):
    piano.chords('Dm | Bb | F | C | Dm | Bb | Gm | A', style='arp_up', every=.5, octave=3, vel=.6)
    strings.chords('Dm | Bb | F | C | Dm | Bb | Gm | A', vel=.45, octave=4)
    bass.bass('Dm | Bb | F | C | Dm | Bb | Gm | A')
    flute.tune("5:1.5 6:.5 8:2 | 7:1 6:1 5:2 | 3:1.5 5:.5 6:2 | 5:4 | 5:1.5 6:.5 8:2 | 7:1 6:1 8:2 | 9:2 8:1 7:1 | #7:4", octave=4)
'''
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
LOW_PRIORITY = 0x00004000 if os.name == 'nt' else 0


class Stop(Exception):
    """An answer with ok:false."""


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def load(folder: Path) -> dict:
    try:
        data = json.loads((folder / 'project.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        raise Stop(f'{folder} 不是 CodeSound 项目（没有可读的 project.json）') from e
    return {**SETTINGS, **data}


def folder_of(text: str) -> Path:
    folder = Path(text).resolve()
    if not (folder / 'project.json').is_file():
        raise Stop(f'{folder} 不是 CodeSound 项目：先运行 init')
    return folder


def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'project.json').exists():
        raise Stop(f'{folder} 已经是项目了')
    folder.mkdir(parents=True, exist_ok=True)
    settings = {**SETTINGS, 'name': folder.name}
    (folder / 'project.json').write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    if not (folder / 'song.py').exists():
        (folder / 'song.py').write_text(STARTER, encoding='utf-8')
    return {'ok': True, 'project': str(folder), 'script': 'song.py'}


def cmd_schema(_a) -> dict:
    tree = ast.parse((KIT / 'cs.py').read_text(encoding='utf-8'))
    calls = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_') and node.name not in ('render', 'score', 'freq_of'):
            calls.append({'call': f'cs.{node.name}({ast.unparse(node.args)})', 'doc': ast.get_docstring(node) or ''})
        if isinstance(node, ast.ClassDef) and node.name == 'Track':
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith('_') and item.name != 'notes_of':
                    calls.append({'call': f'track.{item.name}({ast.unparse(item.args).removeprefix("self, ").removeprefix("self")})', 'doc': ast.get_docstring(item) or ''})
    synth_tree = ast.parse((KIT / 'synth.py').read_text(encoding='utf-8'))
    effects = []
    for node in synth_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Fx':
            effects = [f'{i.name}({ast.unparse(i.args).removeprefix("self, ").removeprefix("self")})' for i in node.body if isinstance(i, ast.FunctionDef) and not i.name.startswith('_')]
    calls.insert(1, {'call': "with cs.section(name, bars):", 'doc': 'A block of the song. Every track starts it at the same bar.'})
    sys.path.insert(0, str(KIT))
    import cs as kit

    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8'), 'cs': calls, 'instruments': sorted(kit.INSTRUMENTS), 'drums': sorted(kit.DRUMS),
            'drum_patterns': sorted(kit.PATTERNS), 'scales': sorted(kit.SCALES), 'effects': effects}


def cmd_check(a) -> dict:
    folder = folder_of(a.folder)
    settings = load(folder)
    path = folder / settings['script']
    if not path.is_file():
        raise Stop(f'没有 {settings["script"]}')
    source = path.read_text(encoding='utf-8-sig')
    try:
        tree = compile(source, str(path), 'exec', ast.PyCF_ONLY_AST)
    except SyntaxError as e:
        return {'ok': False, 'error': f'第 {e.lineno} 行语法错误：{e.msg}', 'line': e.lineno}
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name) and n.func.value.id == 'cs'}
    known = {'song', 'section', 'track', 'fx', 'save', 'pitch', 'compose', 'fade', 'master', 'transpose', 'tempo_at', 'midi_file'}
    unknown = sorted(called - known)
    if unknown:
        return {'ok': False, 'error': f'cs 里没有这些：{", ".join(unknown)}（schema 里有全部）'}
    return {'ok': True, 'project': settings, 'lines': len(source.splitlines())}


def _run(folder: Path, action: str, a) -> dict:
    settings = load(folder)
    quality = getattr(a, 'quality', 'check')
    with tempfile.TemporaryDirectory(prefix='codesound-') as tmp:
        answer = Path(tmp) / 'answer.json'
        job = {'folder': str(folder), 'script': settings['script'], 'action': action, 'sr': 44100 if quality == 'final' else 22050, 'answer': str(answer),
               'stems': bool(getattr(a, 'stems', False)), 'seed': settings['seed'], 'output': 'final.wav' if quality == 'final' else 'latest.wav'}
        path = Path(tmp) / 'job.json'
        path.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
        try:
            proc = subprocess.Popen([sys.executable, str(KIT / 'runner.py'), str(path)], cwd=str(folder), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=NO_WINDOW | LOW_PRIORITY, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        except OSError as e:
            raise Stop(f'启动不了：{e}') from e
        limit = float(getattr(a, 'timeout', 0) or settings['max_seconds'])
        try:
            _, err = proc.communicate(timeout=limit)
        except subprocess.TimeoutExpired as e:
            proc.kill()
            proc.wait()
            raise Stop(f'{limit:.0f} 秒内没有做完：把歌写短一点，或者先用 quality=check') from e
        if not answer.is_file():
            raise Stop((err.decode('utf-8', 'replace').strip()[-1500:]) or f'退出代码 {proc.returncode}，没有结果')
        return json.loads(answer.read_text(encoding='utf-8'))


def cmd_score(a) -> dict:
    return _run(folder_of(a.folder), 'score', a)


def cmd_render(a) -> dict:
    return _run(folder_of(a.folder), 'render', a)


def cmd_new(a) -> dict:
    """A new project whose song.py asks for a style: the fastest way from nothing to music."""
    answer = cmd_init(a)
    (Path(a.folder).resolve() / 'song.py').write_text(f"import cs\n\ncs.compose({a.style!r}, seconds={a.seconds:g}, seed={a.seed})\n", encoding='utf-8')
    return answer


def cmd_measure(a) -> dict:
    """Any WAV file, from anywhere: the same measurements a render gets."""
    import array
    import wave

    sys.path.insert(0, str(KIT))
    import listen

    path = Path(a.file)
    try:
        with wave.open(str(path), 'rb') as f:
            channels, width, rate, count = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
            raw = f.readframes(count)
    except (OSError, wave.Error) as e:
        raise Stop(f'读不了：{e}') from e
    if width != 2:
        raise Stop('只读 16 位 WAV')
    data = array.array('h')
    data.frombytes(raw)
    left = [v / 32768 for v in data[0::channels]]
    right = [v / 32768 for v in data[(channels - 1)::channels]]
    m = listen.measure(left, right, rate)
    notes = listen.sound_notes(m)
    m.pop('level_curve_db', None)
    return {'ok': True, 'measured': m, 'warnings': notes, 'channels': channels, 'rate': rate}


def cmd_export(a) -> dict:
    """MP3 or OGG, with the FFmpeg CodeCut has: a WAV is large for a phone, a web page or a game."""
    folder = folder_of(a.folder)
    source = next((folder / 'out' / n for n in ('final.wav', 'latest.wav') if (folder / 'out' / n).is_file()), None)
    if source is None:
        raise Stop('先合成一次')
    ffmpeg = next(iter(sorted((ROOT.parent / 'codecut' / 'tools').glob('ffmpeg*.exe'))), None) or shutil.which('ffmpeg')
    if not ffmpeg:
        raise Stop('没有找到 FFmpeg（CodeCut 带的那个）')
    target = folder / 'out' / f'{source.stem}.{a.format}'
    codec = {'mp3': ['-codec:a', 'libmp3lame', '-q:a', '2'], 'ogg': ['-codec:a', 'libvorbis', '-q:a', '6'], 'm4a': ['-codec:a', 'aac', '-b:a', '192k']}[a.format]
    res = subprocess.run([str(ffmpeg), '-y', '-loglevel', 'error', '-i', str(source), *codec, str(target)], capture_output=True, creationflags=NO_WINDOW)
    if res.returncode or not target.is_file():
        raise Stop('转换失败：' + res.stderr.decode('utf-8', 'replace')[-300:])
    return {'ok': True, 'output': f'out/{target.name}', 'size_kb': target.stat().st_size // 1024}


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


DRUM_NOTES = {'kick': 36, 'snare': 38, 'clap': 39, 'rim': 37, 'hat': 42, 'open_hat': 46, 'shaker': 70, 'tom_low': 45, 'tom_mid': 47, 'tom_high': 50, 'crash': 49, 'ride': 51,
              'taiko': 35, 'war_drum': 41, 'timpani': 43, 'gong': 52, 'wood_block': 76}


def cmd_midi(a) -> dict:
    """Notes as a standard file, for any notation or music program."""
    folder = folder_of(a.folder)
    if not (folder / 'out' / 'score.json').is_file():
        _run(folder, 'score', a)
    score = json.loads((folder / 'out' / 'score.json').read_text(encoding='utf-8'))
    ticks = 480
    chunks = []
    meta = _vlq(0) + b'\xff\x51\x03' + int(60_000_000 / score['tempo']).to_bytes(3, 'big') + _vlq(0) + b'\xff\x2f\x00'
    chunks.append(b'MTrk' + struct.pack('>I', len(meta)) + meta)
    used = 0
    for index, t in enumerate(score['tracks']):
        drum = t['instrument'] == 'drums'
        channel = 9 if drum else min(index, 8)
        events = []
        for e in t['notes']:
            note = DRUM_NOTES.get(e['m'], 38) if drum else e['m']
            start = int(e['b'] * ticks)
            events.append((start, 1, note, int(e['v'] * 127)))
            events.append((start + max(1, int(e['d'] * ticks)), 0, note, 0))
        events.sort()
        now = 0
        body = bytearray()
        for when, on, note, vel in events:
            body += _vlq(when - now) + bytes([(0x90 if on else 0x80) | channel, max(0, min(127, note)), max(1, min(127, vel)) if on else 0])
            now = when
        body += _vlq(0) + b'\xff\x2f\x00'
        chunks.append(b'MTrk' + struct.pack('>I', len(body)) + bytes(body))
        used += 1
    path = folder / 'out' / 'song.mid'
    path.write_bytes(b'MThd' + struct.pack('>IHHH', 6, 1, len(chunks), ticks) + b''.join(chunks))
    return {'ok': True, 'output': 'out/song.mid', 'tracks': used}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codesound')
    sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('init')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_init)
    sub.add_parser('schema').set_defaults(fn=cmd_schema)
    for name, fn in (('check', cmd_check), ('score', cmd_score), ('midi', cmd_midi)):
        q = sub.add_parser(name)
        q.add_argument('folder')
        q.set_defaults(fn=fn)
    q = sub.add_parser('new')
    q.add_argument('folder')
    q.add_argument('--style', default='古风')
    q.add_argument('--seconds', type=float, default=90)
    q.add_argument('--seed', type=int, default=1)
    q.set_defaults(fn=cmd_new)
    q = sub.add_parser('measure')
    q.add_argument('file')
    q.set_defaults(fn=cmd_measure)
    q = sub.add_parser('export')
    q.add_argument('folder')
    q.add_argument('--format', choices=('mp3', 'ogg', 'm4a'), default='mp3')
    q.set_defaults(fn=cmd_export)
    q = sub.add_parser('render')
    q.add_argument('folder')
    q.add_argument('--quality', choices=('check', 'final'), default='check')
    q.add_argument('--stems', action='store_true')
    q.add_argument('--timeout', type=float, default=0)
    q.set_defaults(fn=cmd_render)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parser().parse_args(argv)
    try:
        answer = args.fn(args)
    except Stop as e:
        answer = {'ok': False, 'error': str(e)}
    except Exception as e:  # noqa: BLE001 (whatever else goes wrong still answers in JSON, so the window can say it)
        answer = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    say(answer)
    return 0 if answer.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())

