"""CodeFilm: one sentence to a finished short film. It puts the other tools to work:

    Code3D     renders each shot from a scene (a ready one, or scene code the AI writes)
    CodeSound  writes and renders the music, as long as the film
    a voice    reads the narration (Windows' own voices: offline, free)
    FFmpeg     moves the camera over each picture, cuts between shots, lays the subtitles and mixes the sound (the copy CodeCut has)

    codefilm init <folder>                               a new film
    codefilm plan <folder> --idea "一句话" [--seconds 60]  a storyboard by rule: style, shots, music; narration only from what was given
    codefilm schema                                      the guide, the ready scenes, the styles
    codefilm check <folder>                              is film.json right
    codefilm build <folder> [--quality draft|final]      out/film.mp4, out/film.srt, a sheet of the shots

Every command prints one JSON object as its last line. Rendered shots, voices and music are kept in work/ and reused while they are unchanged.
"""
from __future__ import annotations

import right_python

right_python.use('PIL')

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import wave  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT.parent
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
LOW = 0x00004000 if os.name == 'nt' else 0
FPS = 25
FADE = .8
MOVES = ('推近', '拉远', '左移', '右移', '静止')
QUALITY = {'draft': {'width': 1280, 'height': 720, 'samples': 16}, 'final': {'width': 1920, 'height': 1080, 'samples': 64}}
STYLES = {  # words that suggest a style -> (ready scenes in order, music style)
    '古风': (('古风', '古代', '武侠', '江湖', '王朝', '列国', '战国', '三国', '古镇', '仙侠', '侠', '宫廷', '水墨'), ['山水晨雾', '古镇集市', '军营战旗', '营地星空', '秋林', '雪中小屋'], '古风'),
    '战争': (('战争', '战斗', '出征', '军队', '将军', '征战', '战场', '史诗', '帝国'), ['军营战旗', '山水晨雾', '营地星空', '古镇集市', '雪中小屋'], '史诗'),
    '城市': (('城市', '科技', '产品', '公司', '咖啡', '都市', '办公', '创业', '软件', 'app', 'App'), ['夜晚街道', '雨夜咖啡馆', '午后客厅', '书桌', '静物'], '轻音乐'),
    '自然': (('旅行', '海', '自然', '风景', '山', '森林', '季节', '秋天', '冬天', '夏天', '假期'), ['海边黄昏', '热带海滩', '山水晨雾', '秋林', '雪中小屋', '营地星空'], '田园'),
}
EXAMPLES = {'山水晨雾': 'meadow', '营地星空': 'camp', '秋林': 'autumn', '雪中小屋': 'winter', '夜晚街道': 'city', '雨夜咖啡馆': 'cafe-window', '午后客厅': 'living-room', '书桌': 'desk', '静物': 'still-life',
            '海边黄昏': 'seaside', '热带海滩': 'tropic'}


class Stop(Exception):
    """An answer with ok:false."""


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False, default=str), flush=True)


def ready_scenes() -> dict:
    """Name -> scene file: CodeFilm's own, then Code3D's examples."""
    out = {p.stem: p for p in sorted((ROOT / 'scenes').glob('*.py'))}
    for name, folder in EXAMPLES.items():
        p = TOOLS / 'code3d' / 'examples' / folder / 'scene.py'
        if p.is_file():
            out[name] = p
    return out


def load(folder: Path) -> dict:
    try:
        return json.loads((folder / 'film.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        raise Stop(f'读不了 film.json：{e}') from e


def problems(film: dict, folder: Path) -> list:
    out = []
    scenes = ready_scenes()
    shots = film.get('shots')
    if not isinstance(shots, list) or not shots:
        return ['shots 是空的：至少要一个镜头']
    for i, s in enumerate(shots, 1):
        scene = s.get('scene')
        if not scene:
            out.append(f'第 {i} 个镜头没有 scene')
        elif scene not in scenes and not (folder / str(scene)).is_file():
            out.append(f'第 {i} 个镜头的 scene “{scene}” 既不是现成场景，也不是项目里的文件。现成的有：{"、".join(scenes)}')
        if s.get('move', '推近') not in MOVES:
            out.append(f'第 {i} 个镜头的 move 只能是：{"、".join(MOVES)}')
        if not isinstance(s.get('seconds', 5), (int, float)) or not 1.5 <= s.get('seconds', 5) <= 60:
            out.append(f'第 {i} 个镜头的 seconds 要在 1.5 到 60 之间')
    music = film.get('music') or {}
    if music.get('file') and not (folder / music['file']).is_file():
        out.append(f'没有音乐文件 {music["file"]}')
    return out


# --- plan --------------------------------------------------------------------------------------------------------------

def style_of(idea: str) -> str:
    scores = {k: sum(w in idea for w in words) for k, (words, _, _) in STYLES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else '自然'


def title_of(idea: str) -> str:
    quoted = re.search(r'[《“"「]([^》”"」]{1,24})[》”"」]', idea)
    if quoted:
        return quoted.group(1)
    text = re.sub(r'^(请|帮我|给我)?(做|拍|剪|生成|制作)(一个|一部|一支|个|部|支)?', '', idea.strip())
    text = re.sub(r'(的)?(宣传片|短片|视频|片子|影片|预告片|动画)$', '', text)
    text = re.sub(r'^[\d一二三四五六七八九十两]+(分钟|秒)(的)?', '', text).strip(' ，,。的')
    return text[:18] or '短片'


def _chinese_number(text: str) -> int:
    """一 .. 九十九, also 两 and the short forms: 十 = 10, 十五 = 15, 二十 = 20, 二十五 = 25."""
    digit = {c: i for i, c in enumerate('零一二三四五六七八九')} | {'两': 2}
    if '十' in text:
        left, _, right = text.partition('十')
        return (digit.get(left[-1:], 1) if left else 1) * 10 + (digit.get(right[:1], 0) if right else 0)
    return digit.get(text[-1:], 1) if text else 1


def cmd_plan(a) -> dict:
    """A storyboard from one sentence, by rule. It writes no narration of its own: words for a voice come from the person (or from the
    AI when it is asked through Lumen), never invented here."""
    folder = Path(a.folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    idea = a.idea.strip()
    if not idea:
        raise Stop('要写一句话：想做一个什么样的片子')
    m = re.search(r'(\d+|[一二两三四五六七八九十]+)\s*分钟', idea)
    seconds = a.seconds
    if m and not a.seconds_given:
        n = m.group(1)
        seconds = 60 * (int(n) if n.isdigit() else _chinese_number(n))
    m = re.search(r'(\d+)\s*秒', idea)
    if m and not a.seconds_given:
        seconds = int(m.group(1))
    seconds = max(12, min(600, seconds or 60))
    style = style_of(idea)
    _, scenes, music = STYLES[style]
    have = ready_scenes()
    scenes = [s for s in scenes if s in have]
    night = ('夜晚街道', '雨夜咖啡馆', '营地星空', '军营战旗')
    if any(w in idea for w in ('夜', '晚上', '星空', '深夜')):  # a night film opens on the night scenes
        scenes = [s for s in scenes if s in night] + [s for s in scenes if s not in night]
    lines =[x.strip() for x in (a.lines or '').splitlines() if x.strip()]
    count = max(len(lines), min(12, max(3, round((seconds - 8) / 6))))
    rnd = random.Random(idea)
    moves = ['推近', '左移', '拉远', '右移']
    shots = []
    for i in range(count):
        each = (seconds - 6.5 + FADE * (count + 1)) / count  # the title, the end card and the cross-fades are inside the length asked for
        shots.append({'scene': scenes[i % len(scenes)], 'seconds': round(each, 1), 'move': moves[(i + rnd.randrange(4)) % 4], 'say': lines[i] if i < len(lines) else ''})
    film = {'title': title_of(idea), 'subtitle': '', 'idea': idea, 'style': style, 'music': {'style': music, 'seed': rnd.randrange(1, 999)}, 'voice': {'on': bool(lines), 'name': '', 'rate': 0},
            'shots': shots, 'end': '谢谢观看'}
    (folder / 'film.json').write_text(json.dumps(film, ensure_ascii=False, indent=1), encoding='utf-8')
    notes = [] if lines else ['没有旁白：分镜是按规则排的，不会自己编台词。要配音，就在 say 里写每个镜头的话，或者让 Lumen 的 AI 来写。']
    return {'ok': True, 'project': str(folder), 'style': style, 'shots': count, 'seconds': seconds, 'warnings': notes}


# --- building ------------------------------------------------------------------------------------------------------------

def _digest(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode('utf-8'))
    return h.hexdigest()[:16]


def _json_of(raw: bytes) -> dict:
    for line in reversed(raw.decode('utf-8', 'replace').splitlines()):
        try:
            v = json.loads(line)
        except ValueError:
            continue
        if isinstance(v, dict) and 'event' not in v:
            return v
    return {}


def _tool(name: str, *args, timeout=1800) -> dict:
    exe = TOOLS / name / f'{name}.py'
    if not exe.is_file():
        raise Stop(f'没有找到 {name}')
    res = subprocess.run([sys.executable, str(exe), *map(str, args)], capture_output=True, timeout=timeout, creationflags=NO_WINDOW | LOW, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    answer = _json_of(res.stdout)
    if not answer:
        raise Stop(f'{name} 没有结果：' + res.stderr.decode('utf-8', 'replace')[-400:])
    return answer


def render_shot(scene_file: Path, work: Path, quality: str, log) -> Path:
    q = QUALITY[quality]
    source = scene_file.read_bytes()
    key = _digest(source, quality)
    folder = work / 'shots' / f'{scene_file.stem}_{key}'
    picture = folder / 'out' / 'final.png'
    if picture.is_file():
        return picture
    if not (folder / 'project.json').is_file():
        res = _tool('code3d', 'init', folder)
        if not res.get('ok'):
            raise Stop(f'Code3D 建不了项目：{res.get("error")}')
    settings = json.loads((folder / 'project.json').read_text(encoding='utf-8'))
    settings.update(width=q['width'], height=q['height'], samples=q['samples'], max_seconds=1200)
    (folder / 'project.json').write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'scene.py').write_bytes(source)
    log(f'渲染 {scene_file.stem}')
    res = _tool('code3d', 'render', folder, '--quality', 'final', '--force', timeout=1500)
    if not res.get('ok') or not picture.is_file():
        raise Stop(f'{scene_file.stem} 渲染失败：{res.get("error")}' + (f'（第 {res["line"]} 行）' if res.get('line') else ''))
    return picture


def voice(text: str, name: str, rate: int, work: Path) -> Path:
    key = _digest(text, name, rate)
    target = work / 'voice' / f'{key}.wav'
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    source = target.with_suffix('.txt')
    source.write_text(text, encoding='utf-8-sig')
    if sys.platform == 'darwin':  # macOS: the system's `say`, written straight to a wav
        cmd = ['say', *(['-v', name] if name else []), '-r', str(175 + int(rate) * 15), '--file-format=WAVE', '--data-format=LEI16@22050', '-o', str(target), '-f', str(source)]
        res = subprocess.run(cmd, capture_output=True, timeout=300)
        if res.returncode or not target.is_file():
            raise Stop('配音失败：' + res.stderr.decode('utf-8', 'replace')[-300:])
        return target
    # the paths and the voice go in through the environment: a quote or a $ in a folder name must not become part of the script
    pick = "if($env:LUMEN_VOICE){$s.SelectVoice($env:LUMEN_VOICE)};"
    script = (f"Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;{pick}$s.Rate={int(rate)};"
              "$s.SetOutputToWaveFile($env:LUMEN_OUT);$s.Speak([IO.File]::ReadAllText($env:LUMEN_IN));$s.Dispose()")
    res = subprocess.run(['powershell', '-NoProfile', '-Command', script], capture_output=True, timeout=300, creationflags=NO_WINDOW,
                         env={**os.environ, 'LUMEN_VOICE': name or '', 'LUMEN_OUT': str(target), 'LUMEN_IN': str(source)})
    if res.returncode or not target.is_file():
        raise Stop('配音失败：' + res.stderr.decode('gbk', 'replace')[-300:])
    return target


def level(wav: Path, how: str, work: Path) -> Path:
    """An evened-out copy, made once: speech brought up to a clear level, music to a steady bed under it."""
    chain = {'voice': 'highpass=f=80,acompressor=threshold=0.1:ratio=3:makeup=2,loudnorm=I=-15:TP=-2:LRA=7,aresample=48000',
             'music': 'dynaudnorm=f=400:g=31:m=8,loudnorm=I=-19:TP=-2:LRA=9,aresample=48000'}[how]
    target = work / 'level' / f'{_digest(str(wav), how)}.wav'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.stat().st_mtime < wav.stat().st_mtime:
        _run_ffmpeg(['-i', str(wav), '-af', chain, '-c:a', 'pcm_s16le', str(target)], target.parent)
    return target


def seconds_of(wav: Path) -> float:
    with wave.open(str(wav), 'rb') as f:
        return f.getnframes() / f.getframerate()


def music(film: dict, seconds: float, work: Path, folder: Path, log) -> Path | None:
    m = film.get('music') or {}
    if m.get('file'):
        return (folder / m['file']).resolve()
    if not m.get('style'):
        return None
    key = _digest(m['style'], m.get('seed', 1), round(seconds))
    project = work / 'music' / key
    target = project / 'out' / 'final.wav'
    if target.is_file():
        return target
    if not (project / 'project.json').is_file():
        res = _tool('codesound', 'init', project)
        if not res.get('ok'):
            raise Stop(f'CodeSound 建不了项目：{res.get("error")}')
    (project / 'song.py').write_text(f"import cs\n\ncs.compose({m['style']!r}, seconds={seconds:.0f}, seed={int(m.get('seed', 1))})\ncs.fade(out=3)\n", encoding='utf-8')
    log('作曲和合成音乐')
    asked, before = seconds, None
    for _ in range(3):  # the tune is written in whole phrases; if it came out longer than the film, write it again shorter so the ending is heard
        res = _tool('codesound', 'render', project, '--quality', 'final', timeout=3600)
        if not res.get('ok'):
            raise Stop(f'音乐没有做成：{res.get("error")}')
        made = seconds_of(target)
        if made <= seconds + 4 or made == before:  # the shortest tune is three sections; then the film keeps its start
            break
        before = made
        asked = max(8.0, asked * seconds / made)
        (project / 'song.py').write_text(f"import cs\n\ncs.compose({m['style']!r}, seconds={asked:.1f}, seed={int(m.get('seed', 1))})\ncs.fade(out=3)\n", encoding='utf-8')
    return target


def _font(size: int, bold=True):
    wide = ('C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/msyh.ttc') if bold else ('C:/Windows/Fonts/msyh.ttc',)
    for path in (*wide, '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/Library/Fonts/Arial Unicode.ttf'):  # Windows, then macOS
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def card(text: str, sub: str, size: tuple, path: Path, palette=('#101420', '#2a3448')) -> Path:
    """A title or an end card: big words on a dark gradient."""
    w, h = size
    im = Image.new('RGB', (w, h))
    top, low = [int(palette[0][i:i + 2], 16) for i in (1, 3, 5)], [int(palette[1][i:i + 2], 16) for i in (1, 3, 5)]
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line((0, y, w, y), fill=tuple(int(top[k] + (low[k] - top[k]) * t) for k in range(3)))
    f = _font(int(h * .1))
    tw = d.textlength(text, font=f)
    d.text(((w - tw) / 2, h * .4), text, font=f, fill='#f3efe6')
    if sub:
        f2 = _font(int(h * .038), False)
        sw = d.textlength(sub, font=f2)
        d.text(((w - sw) / 2, h * .4 + h * .14), sub, font=f2, fill='#c9c3b6')
    d.line(((w - 120) / 2, h * .37, (w + 120) / 2, h * .37), fill='#c8a24a', width=3)
    im.save(path)
    return path


def ffmpeg() -> str:
    found = sorted((TOOLS / 'codecut' / 'tools').glob('ffmpeg*.exe'))
    exe = str(found[0]) if found else shutil.which('ffmpeg')
    if not exe:
        raise Stop('没有找到 FFmpeg（CodeCut 带的那个）')
    return exe


def _run_ffmpeg(args: list, cwd: Path) -> None:
    res = subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', *args], cwd=str(cwd), capture_output=True, creationflags=NO_WINDOW | LOW, timeout=3600)
    if res.returncode:
        raise Stop('FFmpeg 失败：' + res.stderr.decode('utf-8', 'replace')[-700:])


def clip(picture: Path, seconds: float, move: str, size: tuple, target: Path) -> None:
    """The camera moves slowly over a still: in, out, or across. 'Ken Burns', by FFmpeg's zoompan."""
    w, h = size
    frames = max(2, int(seconds * FPS))
    zoom = {'推近': f"1+0.12*on/{frames}", '拉远': f"1.12-0.12*on/{frames}", '左移': '1.1', '右移': '1.1', '静止': '1'}[move]
    x = {'左移': f"(iw-iw/zoom)*(1-on/{frames})", '右移': f"(iw-iw/zoom)*on/{frames}"}.get(move, "iw/2-(iw/zoom/2)")
    y = "ih/2-(ih/zoom/2)"
    vf = f"scale={w * 2}:{h * 2},zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={FPS},format=yuv420p"
    _run_ffmpeg(['-loop', '1', '-i', str(picture), '-vf', vf, '-t', f'{seconds:.3f}', '-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', str(target)], target.parent)


def _stamp(t: float) -> str:
    ms = round(max(0.0, t) * 1000)
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def cmd_build(a) -> dict:
    folder = Path(a.folder).resolve()
    film = load(folder)
    found = problems(film, folder)
    if found:
        raise Stop('；'.join(found[:8]))
    quality = a.quality
    q = QUALITY[quality]
    size = (1280, 720) if quality == 'draft' else (1920, 1080)
    work, out = folder / 'work', folder / 'out'
    for p in (work, out, work / 'clips'):
        p.mkdir(parents=True, exist_ok=True)

    def log(text: str) -> None:
        print(json.dumps({'event': 'progress', 'at': text}, ensure_ascii=False), flush=True)

    scenes = ready_scenes()
    v = film.get('voice') or {}
    plan = []  # (picture, seconds, move, words to show, voice file or None)
    if film.get('title'):
        plan.append((card(film['title'], film.get('subtitle', ''), size, work / 'title.png'), 3.5, '推近', '', None))
    for i, s in enumerate(film['shots'], 1):
        scene_file = scenes.get(s['scene']) or (folder / s['scene'])
        log(f'镜头 {i} / {len(film["shots"])}')
        picture = render_shot(scene_file, work, quality, log)
        words = (s.get('say') or '').strip()
        spoken = level(voice(words, v.get('name', ''), v.get('rate', 0), work), 'voice', work) if words and v.get('on', True) else None
        seconds = float(s.get('seconds', 5))
        if spoken:
            seconds = max(seconds, seconds_of(spoken) + 1.2)
        plan.append((picture, seconds, s.get('move', '推近'), s.get('text', words), spoken))
    if film.get('end'):
        plan.append((card(film['end'], '', size, work / 'end.png'), 3.0, '静止', '', None))
    total = sum(p[1] for p in plan) - FADE * (len(plan) - 1)

    log('镜头运动')
    clips = []
    for i, (picture, seconds, move, _, _) in enumerate(plan):
        target = work / 'clips' / f'{i:03d}_{_digest(picture.read_bytes(), seconds, move, size)}.mp4'
        if not target.is_file():
            clip(picture, seconds, move, size, target)
        clips.append(target)

    srt, starts, at = [], [], 0.0
    for i, (_, seconds, _, words, _) in enumerate(plan):
        starts.append(at)
        if words:
            srt.append(f'{len(srt) + 1}\n{_stamp(at + .3)} --> {_stamp(at + seconds - FADE - .1)}\n{words}\n')
        at += seconds - FADE
    (out / 'film.srt').write_text('\n'.join(srt), encoding='utf-8')
    (work / 'film.srt').write_text('\n'.join(srt), encoding='utf-8')

    song = music(film, total + 2, work, folder, log)
    song = level(song, 'music', work) if song else None
    log('剪辑和混音')
    inputs, graph = [], []
    for c in clips:
        inputs += ['-i', str(c)]
    last, offset = '0:v', 0.0
    for i in range(1, len(clips)):
        offset += plan[i - 1][1] - FADE
        name = f'v{i}'
        graph.append(f'[{last}][{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[{name}]')
        last = name
    if srt:
        size_pt = 26
        graph.append(f"[{last}]subtitles=film.srt:force_style='FontName=Microsoft YaHei,FontSize={size_pt},PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=1.4,Shadow=0,MarginV=36'[vout]")
        last = 'vout'
    audio = []
    n = len(clips)
    voices = [(starts[i] + .4, p[4]) for i, p in enumerate(plan) if p[4]]
    for k, (when, path) in enumerate(voices):
        inputs += ['-i', str(path)]
        ms = int(when * 1000)
        graph.append(f'[{n + k}:a]adelay={ms}|{ms},apad[va{k}]')
        audio.append(f'[va{k}]')
    voice_mix = None
    if audio:
        graph.append(f"{''.join(audio)}amix=inputs={len(audio)}:normalize=0,atrim=0:{total:.3f}[voice]")
        voice_mix = 'voice'
    if song:
        inputs += ['-i', str(song)]
        m = n + len(voices)
        graph.append(f'[{m}:a]atrim=0:{total:.3f},afade=t=in:d=1.5,afade=t=out:st={max(0, total - 3):.3f}:d=3,apad[music]')
        if voice_mix:
            graph.append('[voice]asplit=2[side][speak]')
            graph.append('[music][side]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[ducked]')
            graph.append('[ducked][speak]amix=inputs=2:normalize=0,alimiter=limit=0.9[aout]')
        else:
            graph.append('[music]anull[aout]')
    elif voice_mix:
        graph.append('[voice]anull[aout]')
    target = out / 'film.mp4'
    args = [*inputs, '-filter_complex', ';'.join(graph) if graph else 'null', '-map', f'[{last}]' if graph and last != '0:v' else '0:v']
    if song or voice_mix:
        args += ['-map', '[aout]', '-c:a', 'aac', '-b:a', '192k']
    args += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-t', f'{total:.3f}', str(target)]
    if not graph:
        args = [*inputs, '-c', 'copy', str(target)]
    _run_ffmpeg(args, work)

    sheet = out / 'shots.png'
    pictures = [p[0] for p in plan]
    cell = (384, 216)
    cols = 4
    board = Image.new('RGB', (cols * cell[0], ((len(pictures) + cols - 1) // cols) * cell[1]), '#111')
    for i, p in enumerate(pictures):
        board.paste(Image.open(p).convert('RGB').resize(cell), ((i % cols) * cell[0], (i // cols) * cell[1]))
    board.save(sheet)
    still = out / 'poster.png'
    Image.open(pictures[min(1, len(pictures) - 1)]).convert('RGB').save(still)
    return {'ok': True, 'output': 'out/film.mp4', 'seconds': round(total, 1), 'shots': len(film['shots']), 'size': f'{size[0]}x{size[1]}', 'narration_lines': len(voices),
            'music': bool(song), 'files': ['out/film.mp4', 'out/film.srt', 'out/shots.png'], 'pictures': ['out/shots.png'],
            'warnings': [] if voices else ['没有旁白：片子里只有画面、字幕标题和音乐。']}


def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'film.json').exists():
        raise Stop(f'{folder} 已经有 film.json 了')
    a.idea = a.idea or '一部关于山水和古镇的古风短片'
    a.seconds, a.seconds_given, a.lines = 45, False, ''
    return cmd_plan(a)


def cmd_schema(_a) -> dict:
    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8'), 'ready_scenes': list(ready_scenes()), 'moves': list(MOVES), 'music_styles': _music_styles()}


def _music_styles() -> list:
    sys.path.insert(0, str(TOOLS / 'codesound' / 'kit'))
    try:
        import compose

        return list(compose.STYLES)
    except ImportError:
        return []


def cmd_check(a) -> dict:
    folder = Path(a.folder).resolve()
    film = load(folder)
    found = problems(film, folder)
    return {'ok': not found, 'shots': len(film.get('shots') or []), **({'error': '；'.join(found)} if found else {})}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codefilm')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('schema').set_defaults(fn=cmd_schema)
    q = sub.add_parser('init')
    q.add_argument('folder')
    q.add_argument('--idea', default='')
    q.set_defaults(fn=cmd_init)
    q = sub.add_parser('plan')
    q.add_argument('folder')
    q.add_argument('--idea', required=True)
    q.add_argument('--seconds', type=float, default=0)
    q.add_argument('--lines', default='', help='narration, one line per shot')
    q.set_defaults(fn=cmd_plan)
    q = sub.add_parser('check')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_check)
    q = sub.add_parser('build')
    q.add_argument('folder')
    q.add_argument('--quality', choices=tuple(QUALITY), default='draft')
    q.set_defaults(fn=cmd_build)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parser().parse_args(argv)
    if args.cmd == 'plan':
        args.seconds_given = bool(args.seconds)
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
