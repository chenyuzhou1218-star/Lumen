"""CodeTools: many small tools in one place. Each is one file in plugins/.

    codetools list                       every plugin
    codetools schema [id]                what a plugin asks for
    codetools run <id> <action> --args '{"text": "hi"}' [--out folder]
    codetools check [id]                 runs every action on its own sample, for real

Every command prints one JSON object as its last line.
"""
from __future__ import annotations

import right_python

right_python.use('PIL', 'PySide6.QtPdf')

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import importlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import traceback  # noqa: E402

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import kit  # noqa: E402

RESULTS = Path.home() / 'CodeTools'


def say(obj: dict) -> None:
    try:  # in Lumen's language when LUMEN_LANG is not 中文 (i18n.py + en.json)
        import i18n
        obj = i18n.localize(obj)
    except ImportError:
        pass
    print(json.dumps(obj, ensure_ascii=False, default=str), flush=True)


BROKEN: dict = {}   # plugin file -> why it did not load: one bad plugin must not take the others down with it


def load_all() -> dict:
    found = {}
    BROKEN.clear()
    for path in sorted((ROOT / 'plugins').glob('*.py')):
        if path.name.startswith('_'):
            continue
        try:
            module = importlib.import_module(f'plugins.{path.stem}')
            plugins = getattr(module, 'PLUGINS', [module.PLUGIN] if hasattr(module, 'PLUGIN') else [])
        except Exception as e:  # noqa: BLE001 (a missing library, a typo: say which file and why)
            BROKEN[path.name] = f'{type(e).__name__}: {e}'
            continue
        for plugin in plugins:
            found[plugin.id] = plugin
    return found


def load_one(pid: str) -> dict:
    """Just the file a plugin lives in. `run` used to import all of them (38 plugins, PIL, sqlite...) to run one action, which is what made 运行 slow."""
    import re
    for path in sorted((ROOT / 'plugins').glob('*.py')):
        if path.name.startswith('_'):
            continue
        if re.search(r"Plugin\(\s*['\"]" + re.escape(pid) + r"['\"]", path.read_text(encoding='utf-8')):
            try:
                module = importlib.import_module(f'plugins.{path.stem}')
            except Exception as e:  # noqa: BLE001
                raise kit.Stop(f'{path.name} 没有载入：{type(e).__name__}: {e}') from e
            found = {p.id: p for p in getattr(module, 'PLUGINS', [module.PLUGIN] if hasattr(module, 'PLUGIN') else [])}
            if pid in found:
                return found
    return {}


def plain(p) -> dict:
    return {'id': p.id, 'name': p.name, 'group': p.group, 'blurb': p.blurb,
            'actions': [{'key': a.key, 'label': a.label, 'changes': a.changes, 'fields': [dataclasses.asdict(f) for f in a.fields]} for a in p.actions]}


def action_of(all_plugins: dict, pid: str, key: str):
    if pid not in all_plugins:
        raise kit.Stop(f'没有 {pid} 这个插件')
    for a in all_plugins[pid].actions:
        if a.key == key:
            return a
    raise kit.Stop(f'{pid} 没有 {key}：有 {", ".join(a.key for a in all_plugins[pid].actions)}')


def run_one(action, args: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    values = {f.key: f.value for f in action.fields}
    values.update(args)
    return action.run(values, out)


def cmd_list(_a) -> dict:
    return {'ok': True, 'plugins': [{k: v for k, v in plain(p).items() if k != 'actions'} | {'actions': [x.label for x in p.actions]} for p in load_all().values()]}


def cmd_schema(a) -> dict:
    found = load_all()
    if a.id:
        if a.id not in found:
            raise kit.Stop(f'没有 {a.id} 这个插件')
        return {'ok': True, 'plugin': plain(found[a.id])}
    return {'ok': True, 'guide': (ROOT / 'AI_GUIDE.md').read_text(encoding='utf-8'),
            'plugins': [f'{p.id}: {p.name} ({p.group}) {p.blurb}. actions: {", ".join(x.key for x in p.actions)}' for p in found.values()]}


def cmd_run(a) -> dict:
    try:
        args = json.loads(a.args or '{}')
    except ValueError as e:
        raise kit.Stop(f'--args 不是 JSON：{e}') from e
    action = action_of(load_one(a.id), a.id, a.action)
    return run_one(action, args, Path(a.out) if a.out else RESULTS / a.id)


def cmd_check(a) -> dict:
    found = load_all()
    ids = [a.id] if a.id else list(found)
    results, bad = [], []
    base = Path(tempfile.mkdtemp(prefix='codetools-check-'))
    for pid in ids:
        for action in found[pid].actions:
            try:
                sample = dict(action.sample)
                setup = sample.pop('_setup', None)
                out = base / pid / action.key
                out.mkdir(parents=True, exist_ok=True)
                if setup:
                    sample.update(setup(out))
                res = run_one(action, sample, out)
                missing = [f for f in [*res.get('files', []), *res.get('pictures', [])] if not Path(f).exists()]
                ok = res.get('ok') and not missing
                results.append({'plugin': pid, 'action': action.key, 'ok': bool(ok), 'said': (res.get('lines') or [''])[0][:90]})
                if not ok:
                    bad.append(f'{pid}.{action.key}: {res.get("error")} {missing}')
            except Exception as e:  # noqa: BLE001 (a check reports everything that goes wrong)
                results.append({'plugin': pid, 'action': action.key, 'ok': False, 'said': repr(e)[:160]})
                bad.append(f'{pid}.{action.key}: {traceback.format_exc()[-500:]}')
    if not a.keep:
        shutil.rmtree(base, ignore_errors=True)
    return {'ok': not bad, 'plugins': len(ids), 'actions': len(results), 'results': results, 'folder': str(base) if a.keep else '', **({'error': '\n'.join(bad)} if bad else {})}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='codetools')
    p.add_argument('--lang', help='the language of names and notes: zh, or anything else for English (LUMEN_LANG does the same)')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list').set_defaults(fn=cmd_list)
    q = sub.add_parser('schema')
    q.add_argument('id', nargs='?')
    q.set_defaults(fn=cmd_schema)
    q = sub.add_parser('run')
    q.add_argument('id')
    q.add_argument('action')
    q.add_argument('--args', default='{}')
    q.add_argument('--args-file')
    q.add_argument('--out')
    q.set_defaults(fn=cmd_run)
    q = sub.add_parser('check')
    q.add_argument('id', nargs='?')
    q.add_argument('--keep', action='store_true')
    q.set_defaults(fn=cmd_check)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parser().parse_args(argv)
    if getattr(args, 'args_file', None):
        args.args = Path(args.args_file).read_text(encoding='utf-8')
    try:
        answer = args.fn(args)
    except kit.Stop as e:
        answer = {'ok': False, 'error': str(e)}
    except Exception as e:  # noqa: BLE001 (whatever else goes wrong still answers in JSON, so the window can say it)
        answer = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    say(answer)
    return 0 if answer.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
