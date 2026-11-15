"""CodeLab's command line: keeps watch over model training. It reads logs and tells what is going on, in numbers.

    codelab watch <log> [--name x]     reads a training log: losses, speed, how far along, what looks wrong
    codelab list                       the runs it has been told about
    codelab start <folder> -- <cmd>    starts a NEW run in the background, with its output in a log it can read
    codelab stop <name>                stops a run CodeLab itself started; never anything else
    codelab compare <a> <b>...         best values of several runs, side by side
    codelab picture <log>              the curves as a picture

Reading never touches a run that is going. It finds its way through any text log: `loss: 0.31`, `epoch 3/10`, `{"loss": 0.31}`, CSV.
Runs live in ~/.codelab. Every command prints one JSON object as its last line.
"""
from __future__ import annotations

import right_python

right_python.use('PIL')

import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

HOME = Path(os.environ.get('CODELAB_HOME') or Path.home() / '.codelab')
LOGS = HOME / 'logs'
RUNS = HOME / 'runs.json'
SPOT = re.compile(r'''(?<![\w.])(?P<name>(?:train[_ /-]|val(?:id(?:ation)?)?[_ /-]|test[_ /-]|eval[_ /-])?(?:loss|acc(?:uracy)?|lr|learning[_ ]rate|error|bleu|f1|auc|map|reward|grad[_ ]?norm|perplexity))['"]?(?:\s*[:=]\s*|\s+)['"]?(?P<value>[-+]?(?:\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+|nan|inf))''', re.I)
STEP = re.compile(r'''(?<![\w.])(?P<word>global[_ ]step|step|iter(?:ation)?|batch|epoch)['"]?\s*[:= ]\s*['"]?\[?(?P<now>\d+)(?:\s*/\s*(?P<end>\d+))?''', re.I)
BAR = re.compile(r'(?P<percent>\d{1,3})%\|')
TIME_LEFT = re.compile(r'<\s*(?P<left>\d+:\d\d(?::\d\d)?)')
BAD = re.compile(r'(cuda out of memory|out of memory|traceback \(most recent call last\)|runtimeerror|killed|nan loss|segmentation fault|exploding)', re.I)
HIGHER_BETTER = ('acc', 'accuracy', 'bleu', 'f1', 'auc', 'map', 'reward')
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
LOW_PRIORITY = 0x00004000 if os.name == 'nt' else 0
TAIL_BYTES = 60_000_000


class Stop(Exception):
    """An answer with ok:false."""


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def runs() -> dict:
    try:
        return json.loads(RUNS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def keep_runs(data: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    RUNS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def read_tail(path: Path) -> str:
    """Opened for reading and shared: the job writing it goes on as if nothing happened."""
    size = path.stat().st_size
    with open(path, 'rb') as f:
        if size > TAIL_BYTES:
            f.seek(size - TAIL_BYTES)
        raw = f.read()
    for enc in ('utf-8', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def norm(name: str) -> str:
    n = re.sub(r'[ /-]', '_', name.lower())
    n = n.replace('validation_', 'val_').replace('valid_', 'val_').replace('accuracy', 'acc').replace('learning_rate', 'lr').replace('gradnorm', 'grad_norm')
    return n


def parse(text: str) -> dict:
    """{'series': {name: [(step, value)]}, 'progress', 'errors', ...}"""
    series: dict = {}
    errors: list = []
    step = 0
    seen = 0
    total = None
    percent = None
    left = None
    epoch = None
    for line in text.replace('\r', '\n').split('\n'):
        if not line.strip():
            continue
        if BAD.search(line):
            errors.append(line.strip()[:200])
        best = None
        for m in STEP.finditer(line):
            word = m.group('word').lower()
            if word == 'epoch':
                epoch = int(m.group('now'))
                if m.group('end'):
                    best = best or m
                    percent = 100 * epoch / max(1, int(m.group('end')))
            else:
                best = m
        found = list(SPOT.finditer(line))
        if best is not None and best.group('now'):
            value = int(best.group('now'))
            step = value
            if best.group('end') and best.group('word').lower() != 'epoch':
                total = int(best.group('end'))
                percent = 100 * value / max(1, total)
        bar = BAR.search(line)
        if bar:
            percent = float(bar.group('percent'))
        when = TIME_LEFT.search(line)
        if when:
            left = when.group('left')
        if found:
            if best is None:
                seen += 1
            at = step if best is not None else seen
            for m in found:
                try:
                    v = float(m.group('value'))
                except ValueError:
                    continue
                series.setdefault(norm(m.group('name')), []).append((at, v))
    return {'series': series, 'errors': errors[-5:], 'percent': round(percent, 1) if percent is not None else None, 'time_left': left, 'step': step, 'total': total, 'epoch': epoch}


def parse_csv(text: str) -> dict:
    series: dict = {}
    reader = csv.DictReader(text.splitlines())
    for i, row in enumerate(reader):
        at = i
        for key in ('step', 'global_step', 'iter', 'epoch'):
            if row.get(key) not in (None, ''):
                try:
                    at = int(float(row[key]))
                    break
                except ValueError:
                    pass
        for k, v in row.items():
            if k is None or k in ('step', 'global_step', 'iter', 'epoch', 'time', 'timestamp'):
                continue
            try:
                series.setdefault(norm(k), []).append((at, float(v)))
            except (TypeError, ValueError):
                pass
    return {'series': series, 'errors': [], 'percent': None, 'time_left': None, 'step': 0, 'total': None, 'epoch': None}


def read_log(path: Path) -> dict:
    if not path.is_file():
        raise Stop(f'没有这个文件：{path}')
    text = read_tail(path)
    return parse_csv(text) if path.suffix.lower() == '.csv' else parse(text)


def bad_number(v: float) -> bool:
    return math.isnan(v) or math.isinf(v)


def summary(name: str, points: list) -> dict:
    values = [v for _, v in points if not bad_number(v)]
    if not values:
        return {'name': name, 'points': len(points), 'all_bad': True}
    high = any(h in name for h in HIGHER_BETTER)
    best = max(values) if high else min(values)
    at = next(s for s, v in points if v == best)
    return {'name': name, 'points': len(points), 'first': round(values[0], 5), 'last': round(values[-1], 5), 'best': round(best, 5), 'best_at': at, 'better_is': 'higher' if high else 'lower'}


def trouble(data: dict) -> list:
    """What a person watching the curve would notice."""
    out = list(dict.fromkeys(f'日志里有错误：{e}' for e in data['errors']))
    for name, points in data['series'].items():
        values = [v for _, v in points]
        if not values or name in ('lr', 'grad_norm'):
            continue
        if any(bad_number(v) for v in values[-20:]):
            out.append(f'{name} 变成了 NaN 或无穷大：训练已经坏了，再跑下去没有意义。常见原因是学习率太大。')
            continue
        good = [v for v in values if not bad_number(v)]
        if len(good) < 30:
            continue
        high = any(h in name for h in HIGHER_BETTER)
        part = len(good) // 5
        early, late = statistics.fmean(good[-2 * part:-part]), statistics.fmean(good[-part:])
        change = (late - early) * (1 if high else -1)
        scale = abs(statistics.fmean(good[:part])) or 1
        if abs(change) / scale < .002:
            out.append(f'{name} 最近几乎不动了（{early:.4g} 到 {late:.4g}）：可能到头了，或者学习率该变了。')
        elif change < 0 and abs(change) / scale > .02:
            out.append(f'{name} 最近在变差（{early:.4g} 到 {late:.4g}）。')
    train = data['series'].get('train_loss') or data['series'].get('loss')
    val = data['series'].get('val_loss') or data['series'].get('eval_loss')
    if train and val and len(val) >= 6 and len(train) >= 6:
        t = [v for _, v in train if not bad_number(v)]
        w = [v for _, v in val if not bad_number(v)]
        if len(t) >= 6 and len(w) >= 6 and statistics.fmean(t[-3:]) < statistics.fmean(t[:3]) and min(w) < statistics.fmean(w[-2:]) * .95:
            out.append(f'训练损失还在降，验证损失却回升了（最低 {min(w):.4g}，现在 {w[-1]:.4g}）：过拟合了，早点存下最好的那一版。')
    return out


def cmd_watch(a) -> dict:
    target = a.log
    name = a.name
    known = runs()
    if target in known:
        name, target = target, known[target]['log']
    path = Path(target).resolve()
    data = read_log(path)
    found = sorted(data['series'])
    stale = time.time() - path.stat().st_mtime
    answer = {'ok': True, 'log': str(path), 'updated_seconds_ago': round(stale), 'progress_percent': data['percent'], 'step': data['step'] or None, 'total_steps': data['total'], 'epoch': data['epoch'], 'time_left': data['time_left'],
              'metrics': [summary(k, data['series'][k]) for k in found[:16]], 'warnings': trouble(data)}
    if stale > 1800 and (data['percent'] or 0) < 99:
        answer['warnings'].append(f'日志已经 {stale / 60:.0f} 分钟没有更新：可能停了，也可能在做一次很长的验证。')
    if not found:
        answer['warnings'].append('在日志里没有认出任何指标。把它的一小段给我看，或者让训练打印 loss: 0.31 这样的行。')
    answer['eta_minutes'] = eta(path, data)
    answer['summary'] = plain_words(answer)
    if name:
        known[name] = {**known.get(name, {}), 'log': str(path)}
        keep_runs(known)
    return answer


def plain_words(answer: dict) -> str:
    """The state of a run as one sentence, for a person who has been away."""
    bits = []
    if answer.get('progress_percent') is not None:
        bits.append(f"进度 {answer['progress_percent']:.0f}%")
    if answer.get('time_left'):
        bits.append(f"还要 {answer['time_left']}")
    elif answer.get('eta_minutes') is not None:
        bits.append(f"按现在的速度还要约 {answer['eta_minutes']:.0f} 分钟")
    loss = next((m for m in answer.get('metrics', []) if m['name'] in ('val_loss', 'loss', 'train_loss') and 'last' in m), None)
    if loss:
        bits.append(f"{loss['name']} 现在 {loss['last']}，最好 {loss['best']}")
    bits.append('有问题要看' if answer.get('warnings') else '看起来正常')
    return '，'.join(bits) + '。'


def eta(path: Path, data: dict) -> float | None:
    """Minutes left, from how far it got since the file was created."""
    if not data['percent'] or data['percent'] >= 100:
        return None
    spent = path.stat().st_mtime - path.stat().st_ctime
    if spent < 30:
        return None
    return spent / 60 * (100 - data['percent']) / data['percent']


def cmd_system(_a) -> dict:
    """How the machine is doing: graphics memory if there is an NVIDIA card, disk space where the runs write. Reads only."""
    out: dict = {'ok': True}
    try:
        res = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, timeout=15, creationflags=NO_WINDOW)
        rows = [[c.strip() for c in line.split(',')] for line in res.stdout.decode('utf-8', 'replace').splitlines() if line.strip()]
        out['gpus'] = [{'name': r[0], 'memory_mb': f'{r[1]} / {r[2]}', 'busy_percent': r[3], 'temperature_c': r[4]} for r in rows]
    except (OSError, subprocess.SubprocessError, IndexError):
        out['gpus'] = []
    usage = shutil.disk_usage(HOME.anchor if HOME.anchor else '.')
    out['disk_free_gb'] = round(usage.free / 1e9, 1)
    out['warnings'] = ['硬盘只剩不到 20 GB：检查点可能写不下'] if usage.free < 20e9 else []
    return out


def cmd_checkpoints(a) -> dict:
    """Checkpoints in a folder, newest first, with their sizes: which to keep is the user's to say."""
    folder = Path(a.folder)
    if not folder.is_dir():
        raise Stop(f'没有这个文件夹：{folder}')
    found = []
    for p in folder.rglob('*'):
        if p.is_file() and p.suffix.lower() in ('.pt', '.pth', '.ckpt', '.safetensors', '.bin', '.h5'):
            s = p.stat()
            found.append((s.st_mtime, s.st_size, p))
    found.sort(reverse=True)
    return {'ok': True, 'count': len(found), 'total_gb': round(sum(f[1] for f in found) / 1e9, 2),
            'latest': [{'file': str(f[2].relative_to(folder)), 'mb': round(f[1] / 1e6, 1), 'time': time.strftime('%m-%d %H:%M', time.localtime(f[0]))} for f in found[:20]]}


def alive(pid: int) -> bool:
    if os.name != 'nt':  # macOS and Linux: signal 0 only asks whether the process is there
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    res = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, creationflags=NO_WINDOW)
    return str(pid).encode() in res.stdout


def cmd_list(_a) -> dict:
    out = []
    for name, r in runs().items():
        out.append({'name': name, **r, 'running': alive(r['pid']) if r.get('pid') and r.get('started_here') else None})
    return {'ok': True, 'runs': out}


def cmd_start(a) -> dict:
    """A new run, in its own low-priority process, its output going to a log. It keeps running if CodeLab exits."""
    if not a.command:
        raise Stop('要写命令：codelab start 文件夹 -- python train.py')
    folder = Path(a.folder).resolve()
    if not folder.is_dir():
        raise Stop(f'没有这个文件夹：{folder}')
    command = a.command
    known = runs()
    name = a.name or f'run{len(known) + 1}'
    if name in known:
        raise Stop(f'已经有 {name} 了')
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f'{name}.log'
    try:
        with open(log, 'ab') as f:
            proc = subprocess.Popen(command, cwd=str(folder), stdout=f, stderr=subprocess.STDOUT, creationflags=NO_WINDOW | LOW_PRIORITY, env={**os.environ, 'PYTHONUNBUFFERED': '1'})
    except OSError as e:
        raise Stop(f'启动不了 {command[0]}：{e}') from e
    known[name] = {'log': str(log), 'pid': proc.pid, 'started_here': True, 'folder': str(folder), 'command': command, 'started': time.strftime('%Y-%m-%d %H:%M')}
    keep_runs(known)
    return {'ok': True, 'name': name, 'pid': proc.pid, 'log': str(log)}


def cmd_stop(a) -> dict:
    """Only runs started with `codelab start`: a training job started by hand is never stopped from here."""
    r = runs().get(a.name)
    if r is None:
        raise Stop(f'没有 {a.name} 这个任务')
    if not r.get('started_here'):
        raise Stop(f'{a.name} 不是 CodeLab 启动的，它不会去停别人的任务')
    if not alive(r['pid']):
        return {'ok': True, 'note': '已经结束了'}
    res = subprocess.run(['taskkill', '/PID', str(r['pid']), '/T', '/F'] if os.name == 'nt' else ['kill', str(r['pid'])], capture_output=True, creationflags=NO_WINDOW)
    return {'ok': res.returncode == 0, **({} if res.returncode == 0 else {'error': res.stderr.decode('gbk', 'replace')[:300]})}


def cmd_compare(a) -> dict:
    known = runs()
    out = {}
    names: set = set()
    for item in a.logs:
        path = Path(known[item]['log'] if item in known else item)
        data = read_log(path)
        out[item] = {k: summary(k, v) for k, v in data['series'].items()}
        names |= set(out[item])
    rows = []
    for metric in sorted(names):
        row = {'metric': metric}
        for item in a.logs:
            s = out[item].get(metric)
            row[item] = s.get('best') if s else None
        rows.append(row)
    return {'ok': True, 'best_values': rows}


COLOURS = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#6250d6', '#e34948')


def cmd_picture(a) -> dict:
    """One small chart per kind of number: scales differ too much to share an axis."""
    from PIL import Image, ImageDraw, ImageFont

    known = runs()
    path = Path(known[a.log]['log'] if a.log in known else a.log)
    data = read_log(path)
    groups: dict = {}
    for name, points in data['series'].items():
        key = 'loss' if 'loss' in name or name == 'error' else 'accuracy etc' if any(h in name for h in HIGHER_BETTER) else name
        groups.setdefault(key, {})[name] = points
    if not groups:
        raise Stop('日志里没有可以画的数字')
    cols = 2
    rows = math.ceil(len(groups) / cols)
    w, h = 620, 320
    img = Image.new('RGB', (w * cols, h * rows), '#fcfcfb')
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for path in ('C:/Windows/Fonts/msyh.ttc', '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/Library/Fonts/Arial Unicode.ttf'):  # Windows, then macOS
        try:
            font = ImageFont.truetype(path, 13)
            break
        except OSError:
            continue
    for index, (group, members) in enumerate(sorted(groups.items())):
        ox, oy = (index % cols) * w, (index // cols) * h
        left, right, top, bottom = ox + 58, ox + w - 16, oy + 44, oy + h - 28
        every = [(s, v) for pts in members.values() for s, v in pts if not bad_number(v)]
        if not every:
            continue
        lo_s, hi_s = min(s for s, _ in every), max(s for s, _ in every)
        lo_v, hi_v = min(v for _, v in every), max(v for _, v in every)
        d.text((ox + 12, oy + 8), group, fill='#0b0b0b', font=font)
        for k in range(5):
            y = top + (bottom - top) * k / 4
            d.line((left, y, right, y), fill='#e5e4df')
            d.text((ox + 6, y - 8), f'{hi_v - (hi_v - lo_v) * k / 4:.3g}', fill='#52514e', font=font)
        x_at = 90
        for c, (name, points) in enumerate(sorted(members.items())):
            colour = COLOURS[c % len(COLOURS)]
            step = max(1, len(points) // 600)
            line = [(left + (s - lo_s) / ((hi_s - lo_s) or 1) * (right - left), bottom - (v - lo_v) / ((hi_v - lo_v) or 1) * (bottom - top)) for s, v in points[::step] if not bad_number(v)]
            if len(line) > 1:
                d.line(line, fill=colour, width=2)
            d.rectangle((ox + x_at, oy + 12, ox + x_at + 10, oy + 22), fill=colour)
            d.text((ox + x_at + 14, oy + 8), name, fill='#52514e', font=font)
            x_at += 26 + int(d.textlength(name, font=font))
    target = Path(a.output) if a.output else HOME / 'latest.png'
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target)
    return {'ok': True, 'output': str(target), 'pictures': [str(target)]}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codelab')
    sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('watch')
    q.add_argument('log')
    q.add_argument('--name')
    q.set_defaults(fn=cmd_watch)
    sub.add_parser('list').set_defaults(fn=cmd_list)
    sub.add_parser('system').set_defaults(fn=cmd_system)
    q = sub.add_parser('checkpoints')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_checkpoints)
    q = sub.add_parser('start')
    q.add_argument('folder')
    q.add_argument('--name')
    q.set_defaults(fn=cmd_start)
    q = sub.add_parser('stop')
    q.add_argument('name')
    q.set_defaults(fn=cmd_stop)
    q = sub.add_parser('compare')
    q.add_argument('logs', nargs='+')
    q.set_defaults(fn=cmd_compare)
    q = sub.add_parser('picture')
    q.add_argument('log')
    q.add_argument('-o', '--output')
    q.set_defaults(fn=cmd_picture)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    argv = sys.argv[1:] if argv is None else list(argv)
    command = []
    if '--' in argv:  # what follows -- belongs to the run, whatever it looks like
        at = argv.index('--')
        argv, command = argv[:at], argv[at + 1:]
    args = parser().parse_args(argv)
    args.command = command
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
