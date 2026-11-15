"""Build the static coupling graph of a project: parse every supported file, then resolve
names across files. Each edge records how it was resolved (exact / name_match / heuristic)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from pathlib import Path

from codedoctor.graph import extract_js, extract_python
from codedoctor.graph.facts import FileFacts, SymbolFacts
from codedoctor.graph.model import Edge, Graph, Ids, Node

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".codedoctor", ".mypy_cache",
             ".pytest_cache", "lib", "libs", "vendor", "third_party", ".next", "coverage", ".uv-cache"}
PY_EXT = (".py",)
JS_EXT = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts")
MAX_FILE_BYTES = 2_000_000
# Method names too generic to resolve by name alone.
STOP_CALLS = {
    "get", "set", "add", "append", "extend", "update", "items", "keys", "values", "pop", "push", "json", "format", "join",
    "split", "strip", "replace", "map", "filter", "forEach", "reduce", "then", "catch", "finally", "toString", "call",
    "apply", "bind", "log", "warn", "error", "info", "debug", "on", "off", "once", "emit", "send", "remove", "delete",
    "has", "clear", "init", "start", "stop", "update", "render", "dispose", "destroy", "reset", "show", "hide", "open",
    "close", "copy", "clone", "equals", "length", "slice", "splice", "indexOf", "includes", "find", "some", "every",
    "sort", "concat", "trim", "lower", "upper", "encode", "decode", "read", "write", "load", "save", "run", "next",
    "execute", "request", "fetch", "resolve", "reject", "create", "parse", "stringify", "max", "min", "floor", "abs",
    "random", "now", "assign", "freeze", "isArray", "isFinite", "setTimeout", "clearTimeout", "setInterval",
    "requestAnimationFrame", "addEventListener", "removeEventListener", "querySelector", "getElementById",
    "constructor", "__init__", "super", "print", "len", "range", "str", "int", "float", "list", "dict", "isinstance",
}
# Attribute names too generic to treat as shared business state.
STOP_ATTRS = {
    "length", "x", "y", "z", "w", "id", "name", "type", "value", "data", "state", "visible", "style", "width", "height",
    "position", "rotation", "scale", "children", "parent", "position", "options", "config", "status", "body", "result",
    "text", "innerHTML", "textContent", "className", "classList", "src", "href", "disabled", "checked", "display",
    "opacity", "color", "material", "geometry", "mesh", "object", "target", "current", "prototype", "handlers",
    "listeners", "events", "_events", "time", "delta", "elapsed", "count", "index", "i", "j", "k", "key", "keys", "map",
    "args", "kwargs", "self", "this", "message", "error", "err", "e", "event", "ready", "enabled", "active", "dirty",
    "needsUpdate", "matrix", "matrixWorld", "uuid", "version", "timer", "timeout", "interval", "queue", "cache",
}


def project_files(root: Path) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not _skip_dir(d))
        for fn in sorted(filenames):
            if fn.endswith(PY_EXT + JS_EXT) and not _skip_file(fn):
                p = Path(dirpath) / fn
                try:
                    if p.stat().st_size <= MAX_FILE_BYTES:
                        out.append(p.relative_to(root).as_posix())
                except OSError:
                    pass
    return out


def _skip_dir(name: str) -> bool:
    """Dependencies and generated code are not the project's own coupling."""
    low = name.lower()
    return (name in SKIP_DIRS or name.startswith(".") or low.startswith(("lib", "vendor", "third", "external", "deps"))
            or "第三方" in name or "third_party" in low or "thirdparty" in low)


def _skip_file(name: str) -> bool:
    low = name.lower()
    return low.endswith((".min.js", ".d.ts")) or ".bundle." in low or ".min." in low


def build(root: Path, service: str) -> tuple[Graph, dict]:
    t0 = time.monotonic()
    root = Path(root)
    files = project_files(root)
    fileset = set(files)
    modules = {extract_python.module_name(f): f for f in files if f.endswith(PY_EXT)}
    facts: list[FileFacts] = []
    errors = {}
    for f in files:
        try:
            source = (root / f).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            errors[f] = str(e)
            continue
        ff = extract_python.extract(f, source, modules) if f.endswith(PY_EXT) else extract_js.extract(f, source, fileset)
        if ff.error:
            errors[f] = ff.error
        facts.append(ff)
    g = _assemble(facts, Ids(service))
    info = {"files": len(files), "parse_errors": errors, "seconds": round(time.monotonic() - t0, 2),
            "languages": {"python": sum(f.endswith(PY_EXT) for f in files), "javascript": sum(f.endswith(JS_EXT) for f in files)}}
    return g, info


def _assemble(facts: list[FileFacts], ids: Ids) -> Graph:
    g = Graph()
    by_key: dict[tuple[str, str], SymbolFacts] = {}
    funcs_by_name: dict[str, list[SymbolFacts]] = defaultdict(list)
    methods_by_name: dict[str, list[SymbolFacts]] = defaultdict(list)
    classes_by_name: dict[str, list[SymbolFacts]] = defaultdict(list)
    for ff in facts:
        g.add_node(Node(ids.file(ff.path), "file", ff.path, ff.path, 1, {"language": ff.language}))
        for s in ff.symbols:
            by_key[(ff.path, s.qualname)] = s
            simple = s.qualname.rsplit(".", 1)[-1]
            if s.kind == "class":
                classes_by_name[simple].append(s)
            elif s.kind in ("method", "listener") or "." in s.qualname:
                methods_by_name[simple].append(s)
            elif s.kind == "function":
                funcs_by_name[simple].append(s)

    def sid(s: SymbolFacts) -> str:
        return ids.symbol(s.path, s.qualname)

    def edge(src, rel, dst, s: SymbolFacts | None, line, resolution):
        g.add_edge(Edge(src, rel, dst, "static", resolution, s.path if s else None, line))

    def resolve(ff: FileFacts, s: SymbolFacts, name: str, receiver: str | None) -> list[tuple[SymbolFacts, str]]:
        if receiver is None:
            local = by_key.get((ff.path, name))
            if local:
                return [(local, "exact")]
            if name in ff.bindings:
                target, tname = ff.bindings[name]
                hit = by_key.get((target, tname or name))
                if hit:
                    return [(hit, "exact")]
            if name in STOP_CALLS:
                return []
            cands = funcs_by_name.get(name, []) + classes_by_name.get(name, [])
            return _by_name(cands)
        if receiver in ("self", "this") and s.class_name:
            hit = by_key.get((s.path, f"{s.class_name}.{name}"))
            if hit:
                return [(hit, "exact")]
        if receiver in ff.bindings and ff.bindings[receiver][1] is None:  # module alias: db.execute()
            hit = by_key.get((ff.bindings[receiver][0], name))
            return [(hit, "exact")] if hit else []
        if name in STOP_CALLS:
            return []
        cands = methods_by_name.get(name, []) + funcs_by_name.get(name, [])
        return _by_name([c for c in cands if c is not s])

    writers_by_attr: dict[tuple[str, str], list[tuple[SymbolFacts, int]]] = defaultdict(list)
    for ff in facts:
        fid = ids.file(ff.path)
        for target, line in ff.imports:
            g.add_edge(Edge(fid, "imports", ids.file(target), "static", "exact", ff.path, line))
        for s in ff.symbols:
            if s.kind != "module":
                g.add_node(Node(sid(s), "symbol", s.qualname, s.path, s.line, {
                    "kind": s.kind, "language": s.language, "early_returns": sorted(set(s.early_returns)),
                    "has_tx": s.has_tx, "has_idem": s.has_idem, "retryish": s.retryish,
                    "writes": sorted({a for a, _ in s.writes_attr} | {t for k, t, _ in s.sql if k == "writes"}),
                    "write_lines": sorted({ln for _, ln in s.writes_attr} | {ln for k, _, ln in s.sql if k == "writes"}),
                }))
                g.add_edge(Edge(fid, "contains", sid(s), "static", "exact", s.path, s.line))
            else:
                g.add_node(Node(sid(s), "symbol", f"{s.path} (module)", s.path, 1, {"kind": "module", "language": s.language,
                                                                               "early_returns": [], "has_tx": s.has_tx,
                                                                               "has_idem": s.has_idem, "retryish": False,
                                                                               "writes": [], "write_lines": []}))
            src = sid(s)
            for name, receiver, line in s.calls:
                for target, how in resolve(ff, s, name, receiver):
                    if target is not s:
                        edge(src, "calls", sid(target), s, line, how)
            for attr, line in s.writes_attr:
                if attr not in STOP_ATTRS and not attr.isupper() and s.kind != "module" \
                        and not s.qualname.endswith(("__init__", "constructor")):
                    edge(src, "writes", ids.state(attr, s.language), s, line, "heuristic")
                    writers_by_attr[(s.language, attr)].append((s, line))
            for kind, table, line in s.sql:
                edge(src, kind, ids.table(table), s, line, "heuristic")
            for kind, name, line in s.emits:
                edge(src, "emits", ids.event(name) if kind == "event" else ids.ws_msg(name), s, line, "exact")
            for msg, line in s.consumes_msg:
                edge(ids.ws_msg(msg), "consumes", src, s, line, "exact")
            for method, path, line, host in s.http:
                edge(src, "calls", ids.route(method, path), s, line, "exact")
        for method, path, handler, line in ff.routes:
            targets = _handler_targets(ff, handler, by_key, resolve)
            for target, how in targets:
                g.add_edge(Edge(ids.route(method, path), "handles", sid(target), "static", how, ff.path, line))
            if not targets:
                g.ensure(ids.route(method, path))
            g.nodes[ids.route(method, path)].attrs["server"] = True
        for kind, name, handler, line in ff.listeners:
            ent = ids.event(name) if kind == "event" else ids.ws_msg(name)
            for target, how in _handler_targets(ff, handler, by_key, resolve):
                g.add_edge(Edge(ent, "consumes", sid(target), "static", how, ff.path, line))
            g.ensure(ent)

    # Reads only for attributes something writes, so the graph keeps business state, not every property access.
    for ff in facts:
        for s in ff.symbols:
            seen = set()
            for attr, line in s.reads_attr:
                if (s.language, attr) in writers_by_attr and attr not in STOP_ATTRS and attr not in seen:
                    seen.add(attr)
                    edge(sid(s), "reads", ids.state(attr, s.language), s, line, "heuristic")
    return g


def _by_name(cands: list) -> list:
    """One candidate: a usable name match. Two or three: recorded as ambiguous. More: too vague to record."""
    if len(cands) == 1:
        return [(cands[0], "name_match")]
    if 2 <= len(cands) <= 3:
        return [(c, "ambiguous") for c in cands]
    return []


def _handler_targets(ff: FileFacts, handler: str, by_key, resolve) -> list[tuple[SymbolFacts, str]]:
    if handler.startswith("ref:"):
        name = handler[4:]
        owner = next(iter(s for s in ff.symbols if s.kind == "module"))
        return resolve(ff, owner, name, None) or resolve(ff, owner, name, "?")
    hit = by_key.get((ff.path, handler))
    return [(hit, "exact")] if hit else []
