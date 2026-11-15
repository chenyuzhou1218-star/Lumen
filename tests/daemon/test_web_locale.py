"""The window drawn in React (web/src) in another language: every text it writes goes through t('…') and has an English
entry in desktop/locale/en.json, the catalog the Qt window uses too (web/src/i18n.js)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "web" / "src"
HAN = re.compile(r"[一-鿿]")
CALL = re.compile(r"""\bt\(\s*(['"`])((?:\\.|(?!\1).)*)\1""", re.S)


def _sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(SRC.glob("*.js*")) if p.name != "mock.js"}


def _without_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"\{/\*.*?\*/\}", "", code, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`])//.*$", r"\1", code)


def test_every_text_of_the_page_has_an_english_entry():
    cat = json.loads((ROOT / "daemon/codedoctor/desktop/locale/en.json").read_text(encoding="utf-8"))
    known = {**cat["exact"], **cat["templates"]}
    missing = []
    for name, code in _sources().items():
        for _, text in CALL.findall(code):
            if HAN.search(text) and not known.get(text):
                missing.append(f"{name}: {text}")
    assert not missing, f"{len(missing)} texts have no English entry (add them to desktop/locale/en.json): {missing[:12]}"


def test_no_chinese_reaches_the_page_without_t():
    """Chinese written straight into the page (JSX text, a title=…) would stay Chinese in English: it must go through t().
    Lists of [key, 中文, …] are read through t() where they are shown, so their strings are allowed."""
    bad = []
    for name, code in _sources().items():
        code = _without_comments(code)
        for line_no, line in enumerate(code.splitlines(), 1):
            if not HAN.search(line):
                continue
            rest = CALL.sub("", line)
            rest = re.sub(r"^\s*\[\s*'[a-z_]+'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*\],?\s*$", "", rest)  # APPROVALS-style rows
            if line.lstrip().startswith("const GREETINGS"):  # the greeting writes each language's own word: never translated
                continue
            if HAN.search(rest):
                bad.append(f"{name}:{line_no}: {line.strip()[:90]}")
    assert not bad, "Chinese shown without t():\n" + "\n".join(bad[:15])
