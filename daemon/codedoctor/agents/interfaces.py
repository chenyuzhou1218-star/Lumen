"""Keeping a project's functions as they are called (the user's rule, 2026-11-04). In a real run a model repaired refund()
correctly and changed what it takes, and 8 of 61 checks failed on code that worked: every caller was wrong now.

The system compares the project's Python with how it was when the team started on the task:
- breaks(): a public function or method removed, or its parameters changed so that existing calls no longer fit. Adding
  a parameter with a default fits. This is certain, so it goes straight back to the member.
- changes(): what else callers may notice - a changed return, the same parameters taken apart differently. A program
  cannot judge those, so they go to the one-off re-check, with the old and new text side by side.
Only Python is read; a file that does not parse is left to the tests.
"""

from __future__ import annotations

import ast
from pathlib import Path

SKIP = {".git", ".venv", "venv", "__pycache__", "node_modules", "tests", "test"}
MAX_FILES = 400
MAX_BYTES = 400_000


def _sources(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if SKIP & set(rel.parts) or rel.name.startswith("test_") or path.stat().st_size > MAX_BYTES:
            continue
        try:
            out[rel.as_posix()] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if len(out) >= MAX_FILES:
            break
    return out


def remember(services, root_task: str) -> None:
    """The project as the team found it, once per task."""
    bases = services.__dict__.setdefault("_interface_base", {})
    if root_task not in bases:
        bases[root_task] = _sources(Path(services.config.root))


def forget(services, root_task: str) -> None:
    services.__dict__.get("_interface_base", {}).pop(root_task, None)


def _public(text: str) -> dict[str, ast.AST]:
    """{name or Class.name: function} of what other code calls."""
    tree = ast.parse(text)
    found: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            found[node.name] = node
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and (not sub.name.startswith("_") or sub.name == "__init__"):
                    found[f"{node.name}.{sub.name}"] = sub
    return found


def _params(fn) -> tuple[list[str], int]:
    """(positional parameter names, how many are required)."""
    names = [a.arg for a in [*fn.args.posonlyargs, *fn.args.args]]
    return names, len(names) - len(fn.args.defaults)


def _fits(old, new) -> bool:
    """Do calls written for old still fit new?"""
    was, need = _params(old)
    now, need_now = _params(new)
    if now[:len(was)] != was or (len(now) < len(was) and new.args.vararg is None):
        return False  # a parameter renamed, moved or dropped
    if need_now > need:
        return False  # one that was optional, or a new one, is now required
    had = {a.arg for a in old.args.kwonlyargs}
    return all(a.arg in had for a, default in zip(new.args.kwonlyargs, new.args.kw_defaults) if default is None)


def _signature(name: str, fn) -> str:
    return f"{name}({ast.unparse(fn.args)})"


def _returns(fn) -> list[str]:
    """The function's own returns, not those of functions inside it."""
    out, todo = [], list(fn.body)
    while todo:
        node = todo.pop(0)
        if isinstance(node, ast.Return):
            out.append(ast.unparse(node.value) if node.value is not None else "None")
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            todo += list(ast.iter_child_nodes(node))
    return out


def _unpacked(fn) -> list[str]:
    """How the function takes its arguments apart: `for sku, qty in items`."""
    params = set(_params(fn)[0])
    return [ast.unparse(n.target) + " in " + ast.unparse(n.iter) for n in ast.walk(fn)
            if isinstance(n, ast.For) and isinstance(n.iter, ast.Name) and n.iter.id in params]


def _pairs(services, root_task: str):
    base = services.__dict__.get("_interface_base", {}).get(root_task)
    if base is None:
        return
    root = Path(services.config.root)
    for rel, text in base.items():
        path = root / rel
        if not path.is_file():
            yield rel, text, None
            continue
        try:
            now = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if now != text:
            yield rel, text, now


def breaks(services, root_task: str) -> list[str]:
    """What existing calls no longer fit: [one line each]."""
    out = []
    for rel, before, after in _pairs(services, root_task) or ():
        try:
            old = _public(before)
        except SyntaxError:  # the project did not parse when the team found it
            continue
        if after is None:
            out += [f"{rel}: {_signature(n, f)} is gone (the whole file was removed)" for n, f in old.items()]
            continue
        try:
            new = _public(after)
        except SyntaxError:
            continue
        for name, fn in old.items():
            if name not in new:
                out.append(f"{rel}: {_signature(name, fn)} is gone")
            elif not _fits(fn, new[name]):
                out.append(f"{rel}: was {_signature(name, fn)}, now {_signature(name, new[name])}")
    return out


def changes(services, root_task: str) -> list[str]:
    """What callers may notice although the call still fits: [one line each]."""
    out = []
    for rel, before, after in _pairs(services, root_task) or ():
        if after is None:
            continue
        try:
            old, new = _public(before), _public(after)
        except SyntaxError:
            continue
        for name, fn in old.items():
            if name not in new:
                continue
            was, now = _returns(fn), _returns(new[name])
            if was and was != now:
                out.append(f"{rel} {name}: returned {' / '.join(was)[:160]}; now returns {' / '.join(now)[:160]}")
            if _unpacked(fn) != _unpacked(new[name]):
                out.append(f"{rel} {name}: took apart its arguments as {_unpacked(fn)}; now as {_unpacked(new[name])}")
    return out


def told_to_change(words: str) -> bool:
    """The job itself is to change an interface."""
    words = words.lower()
    return any(w in words for w in ("change the interface", "change the signature", "改接口", "修改接口", "改函数签名", "接口改成"))
