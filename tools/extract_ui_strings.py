"""List every Chinese string the desktop shows, for the translation catalogs (desktop/locale/<lang>.json).

Plain constants are kept as they are; an f-string becomes a template with {0}, {1}, ... where its values go.
Docstrings and comments are skipped. Usage: python tools/extract_ui_strings.py > strings.json
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

HAN = re.compile(r"[一-鿿]")
ROOT = pathlib.Path(__file__).resolve().parents[1] / "daemon" / "codedoctor"
# the window's code, and the modules whose words it shows (statuses, phases, ways of working, test verdicts)
FILES = sorted((ROOT / "desktop").glob("*.py")) + [ROOT / "ui_text.py", ROOT / "topology.py", ROOT / "changes.py",
                                                   ROOT / "agents" / "anomalies.py"]
SKIP = {"i18n.py"}


def docstrings(tree) -> set[int]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                out.add(id(first.value))
    return out


def template(node: ast.JoinedStr) -> str:
    parts, i = [], 0
    for v in node.values:
        if isinstance(v, ast.Constant):
            parts.append(str(v.value).replace("{", "{{").replace("}", "}}"))
        else:
            parts.append("{%d}" % i)
            i += 1
    return "".join(parts)


def main() -> None:
    exact: dict[str, list[str]] = {}
    templates: dict[str, list[str]] = {}
    for f in FILES:
        if f.name in SKIP:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        skip = docstrings(tree)
        inside_f = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                for v in node.values:
                    inside_f.add(id(v))
                t = template(node)
                if HAN.search(t):
                    templates.setdefault(t, []).append(f"{f.name}:{node.lineno}")
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and HAN.search(node.value)
                    and id(node) not in skip and id(node) not in inside_f
                    and not re.fullmatch(r"\[[^\]]*\]", node.value)):  # a regex character class, not a text
                exact.setdefault(node.value, []).append(f"{f.name}:{node.lineno}")
    json.dump({"exact": exact, "templates": templates}, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
