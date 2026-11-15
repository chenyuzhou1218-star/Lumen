"""Builds every tool's en.json from webkit/i18n/: common.json (+ web4.json for the four that share its words) + the tool's own file.
    python webkit/merge_en.py
The kit's own words (ui/kit/en.json, from webkit/kit/en.json) are copied by build.mjs with the kit."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
SOURCES = HERE / 'i18n'
WEB4 = ('codedata', 'codegame', 'codecad', 'codelab')
EXTRA = {'codepage': ('common',), 'codesound': (), 'code3d': (), 'codecut': (), 'codetools': ()}


def load(name: str) -> dict:
    path = SOURCES / f'{name}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


for tool in ('code3d', 'codecad', 'codecut', 'codedata', 'codedeck', 'codefilm', 'codegame', 'codelab', 'codepage', 'codesound', 'codetools'):
    table = {}
    for part in ('common',) + (('web4',) if tool in WEB4 else ()) + (tool,) + (('codetools2',) if tool == 'codetools' else ('codepage2',) if tool == 'codepage' else ()):
        table.update(load(part))
    (TOOLS / tool / 'en.json').write_text(json.dumps(table, ensure_ascii=False, indent=0) + '\n', encoding='utf-8')
    print(tool, len(table))
