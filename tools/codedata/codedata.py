"""CodeData's command line: drop in a spreadsheet, get a report whose every number can be traced back.

    codedata init <folder>                 a new analysis: put data files in it
    codedata schema                        the guide
    codedata look <folder> [--file x]      what is in the data: columns, ranges, gaps, oddities, without any code
    codedata run <folder> [--pictures]     runs analysis.py and writes out/report.html, and a picture of it
    codedata recheck <folder>              runs it again and compares every number with the last run

Every command prints one JSON object as its last line.
"""
from __future__ import annotations

import right_python

right_python.use('playwright')

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
KIT = ROOT / 'kit'
sys.path.insert(0, str(KIT))

SETTINGS = {'name': '', 'script': 'analysis.py', 'max_seconds': 600}
DATA = ('.csv', '.tsv', '.txt', '.xlsx', '.json')
STARTER = '''"""Read `codedata look` first. Every sentence of the report rests on a table or a number computed here."""
import cd

t = cd.read('data.csv')
cd.title('报告的标题')
cd.say(f'一共 {len(t)} 行。', evidence=len(t))
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
    print(json.dumps(obj, ensure_ascii=False, default=str), flush=True)


def folder_of(text: str) -> Path:
    folder = Path(text).resolve()
    if not (folder / 'project.json').is_file():
        raise Stop(f'{folder} 不是 CodeData 项目：先运行 init')
    return folder


def load(folder: Path) -> dict:
    try:
        return {**SETTINGS, **json.loads((folder / 'project.json').read_text(encoding='utf-8-sig'))}
    except (OSError, ValueError) as e:
        raise Stop(f'读不了 project.json：{e}') from e


def cmd_init(a) -> dict:
    folder = Path(a.folder).resolve()
    if (folder / 'project.json').exists():
        raise Stop(f'{folder} 已经是项目了')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'project.json').write_text(json.dumps({**SETTINGS, 'name': folder.name}, ensure_ascii=False, indent=2), encoding='utf-8')
    if not (folder / 'analysis.py').exists():
        (folder / 'analysis.py').write_text(STARTER, encoding='utf-8')
    return {'ok': True, 'project': str(folder), 'script': 'analysis.py'}


def cmd_schema(_a) -> dict:
    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8')}


def cmd_look(a) -> dict:
    import tables

    folder = folder_of(a.folder)
    files = [folder / a.file] if a.file else sorted(f for f in folder.iterdir() if f.suffix.lower() in DATA and f.is_file() and f.name != 'project.json')
    if not files:
        raise Stop('文件夹里没有数据文件（csv、tsv、xlsx、json）')
    out = []
    try:
        for f in files[:12]:
            table = tables.read(f)
            info = {'file': f.name, **tables.profile(table), 'first_rows': [[str(c) for c in r] for r in table.rows[:4]]}
            if f.suffix.lower() == '.xlsx':
                info['sheets'] = tables.sheets_of(f)
            out.append(info)
    except tables.DataError as e:
        raise Stop(str(e)) from e
    return {'ok': True, 'files': out}


def _run(folder: Path, timeout: float = 0) -> dict:
    settings = load(folder)
    if not (folder / settings['script']).is_file():
        raise Stop(f'没有 {settings["script"]}')
    with tempfile.TemporaryDirectory(prefix='codedata-') as tmp:
        answer = Path(tmp) / 'answer.json'
        job = Path(tmp) / 'job.json'
        job.write_text(json.dumps({'folder': str(folder), 'script': settings['script'], 'answer': str(answer)}, ensure_ascii=False), encoding='utf-8')
        try:
            res = subprocess.run([sys.executable, str(KIT / 'runner.py'), str(job)], cwd=str(folder), capture_output=True, timeout=timeout or settings['max_seconds'],
                                 creationflags=NO_WINDOW | LOW_PRIORITY, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        except subprocess.TimeoutExpired as e:
            raise Stop('运行超时了') from e
        if not answer.is_file():
            raise Stop(res.stderr.decode('utf-8', 'replace').strip()[-1500:] or '没有结果')
        return json.loads(answer.read_text(encoding='utf-8'))


def _picture(folder: Path) -> tuple:
    from kit_shot import shots  # noqa: PLC0415

    res = shots(folder / 'out' / 'report.html', [(folder / 'out' / 'report.png', 900, 900)])
    return ['out/report.png'], res['errors']


def cmd_run(a) -> dict:
    folder = folder_of(a.folder)
    answer = _run(folder, a.timeout)
    if answer.get('ok') and a.pictures:
        try:
            answer['pictures'], problems = _picture(folder)
            if problems:
                answer['warnings'] = problems
        except Exception as e:  # noqa: BLE001 (the browser can fail in many ways; the page is made, only the pictures are missing)
            answer['warnings'] = [f'{type(e).__name__}: {e}']
    return answer


def cmd_recheck(a) -> dict:
    """The same data and code must give the same numbers. A difference means something in the analysis is not repeatable, or the data changed."""
    folder = folder_of(a.folder)
    path = folder / 'out' / 'facts.json'
    if not path.is_file():
        raise Stop('还没有运行过，没有东西可以比')
    before = json.loads(path.read_text(encoding='utf-8'))
    keep = folder / 'out' / 'facts_before.json'
    shutil.copyfile(path, keep)
    try:
        answer = _run(folder, a.timeout)
        if not answer.get('ok'):
            return answer
        after = json.loads(path.read_text(encoding='utf-8'))
    finally:
        keep.unlink(missing_ok=True)  # whatever happened, the copy does not stay behind
    left, right = before['facts'], after['facts']
    changed = [x['said'] for x, y in zip(left, right) if x != y]
    if len(left) != len(right):
        changed.append(f'事实数量不同：{len(left)} 和 {len(right)}')
    return {'ok': not changed, 'facts': len(right), **({'error': '这些数字变了：' + '；'.join(changed[:10])} if changed else {})}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codedata')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('schema').set_defaults(fn=cmd_schema)
    q = sub.add_parser('init')
    q.add_argument('folder')
    q.set_defaults(fn=cmd_init)
    q = sub.add_parser('look')
    q.add_argument('folder')
    q.add_argument('--file')
    q.set_defaults(fn=cmd_look)
    q = sub.add_parser('run')
    q.add_argument('folder')
    q.add_argument('--pictures', action='store_true')
    q.add_argument('--timeout', type=float, default=0)
    q.set_defaults(fn=cmd_run)
    q = sub.add_parser('recheck')
    q.add_argument('folder')
    q.add_argument('--timeout', type=float, default=0)
    q.set_defaults(fn=cmd_recheck)
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
