"""Writes a tool's ai_panel.py from CodeDeck's (the page draws the panel now; this is only the work behind it), keeping
the tool's own TOOL, NAME, SUB and HINT and the module it imports as core, as they were in its last commit."""
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
tool = sys.argv[1]
old = subprocess.run(['git', '-C', str(TOOLS / tool), 'show', 'HEAD:ai_panel.py'], capture_output=True, text=True, encoding='utf-8').stdout
new = (TOOLS / 'codedeck' / 'ai_panel.py').read_text(encoding='utf-8')
for key in ('TOOL', 'NAME', 'SUB', 'HINT'):
    line = re.search(rf'^{key} = .*$', old, re.M).group(0)
    new = re.sub(rf'^{key} = .*$', lambda m: line, new, flags=re.M)
core = re.search(r'^import (\w+) as core$', old, re.M).group(1)
new = new.replace('import codedeck as core', f'import {core} as core')
name = re.search(r"^NAME = '(.*)'$", old, re.M).group(1)
new = new.replace('--with codedeck', f'--with {tool}').replace("with CodeDeck's own", f"with {name}'s own")
(TOOLS / tool / 'ai_panel.py').write_text(new, encoding='utf-8')
print(tool, core, name)
