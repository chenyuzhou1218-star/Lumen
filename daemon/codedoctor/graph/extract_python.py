"""Python source -> FileFacts, using the standard library ast (exact parse)."""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

from codedoctor.graph.facts import IDEM_MARKER, RETRY_LOOP_HEADER, TX_MARKER, FileFacts, SymbolFacts, normalize_route, sql_tables

ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}
MUTATORS = {"append", "extend", "add", "insert", "remove", "pop", "update", "clear", "setdefault", "discard", "popitem"}


def module_name(path: str) -> str:
    p = PurePosixPath(path)
    parts = list(p.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def extract(path: str, source: str, modules: dict[str, str]) -> FileFacts:
    """`modules` maps dotted module names of the project to repo paths (for import resolution)."""
    ff = FileFacts(path, "python")
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as e:
        ff.error = f"{type(e).__name__}: {e}"
        return ff
    pkg = module_name(path).rsplit(".", 1)[0] if "." in module_name(path) else ""

    def resolve_module(name: str, level: int = 0) -> str | None:
        if level:
            base = module_name(path).split(".")
            base = base[: len(base) - level] if not path.endswith("__init__.py") else base[: len(base) - level + 1]
            name = ".".join([*base, name] if name else base)
        return modules.get(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                target = resolve_module(a.name)
                if target:
                    ff.imports.append((target, node.lineno))
                    ff.bindings[(a.asname or a.name).split(".")[0] if not a.asname else a.asname] = (target, None)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_module(node.module or "", node.level)
            for a in node.names:
                sub = resolve_module(f"{node.module}.{a.name}" if node.module else a.name, node.level)
                if sub:  # "from pkg import module"
                    ff.imports.append((sub, node.lineno))
                    ff.bindings[a.asname or a.name] = (sub, None)
                elif base:
                    ff.imports.append((base, node.lineno))
                    ff.bindings[a.asname or a.name] = (base, a.name)

    module_sym = SymbolFacts("<module>", path, 1, "module", "python")
    ff.symbols.append(module_sym)

    def visit_body(body: list, qual_prefix: str, class_name: str | None, sym: SymbolFacts) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{qual_prefix}{stmt.name}"
                fsym = SymbolFacts(qual, path, stmt.lineno, "method" if class_name else "function", "python", class_name)
                ff.symbols.append(fsym)
                for dec in stmt.decorator_list:
                    route = _route_from_decorator(dec)
                    if route:
                        ff.routes.append((route[0], route[1], qual, dec.lineno))
                scan_function(stmt, fsym)
                visit_body(stmt.body, f"{qual}.", None, fsym)
            elif isinstance(stmt, ast.ClassDef):
                qual = f"{qual_prefix}{stmt.name}"
                ff.symbols.append(SymbolFacts(qual, path, stmt.lineno, "class", "python", stmt.name))
                visit_body(stmt.body, f"{qual}.", stmt.name, sym)
            elif sym is module_sym:
                scan_statements([stmt], module_sym)

    def scan_function(fn, sym: SymbolFacts) -> None:
        scan_statements(fn.body, sym)
        names = " ".join([fn.name, *(a.arg for a in fn.args.args + fn.args.kwonlyargs)])
        if IDEM_MARKER.search(names):
            sym.has_idem = True

    def scan_statements(stmts: list, sym: SymbolFacts) -> None:
        for stmt in stmts:
            for node in _walk_no_defs(stmt):
                _scan_node(node, sym)
            _scan_control(stmt, sym)

    visit_body(tree.body, "", None, module_sym)
    return ff


def _walk_no_defs(node):
    """ast.walk that does not descend into nested function / class bodies (they are separate symbols)."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        for child in ast.iter_child_nodes(n):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                stack.append(child)


def _scan_control(stmt, sym: SymbolFacts) -> None:
    """Early returns inside conditionals, retry loops, transaction blocks."""
    for node in _walk_no_defs(stmt):
        if isinstance(node, ast.If):
            for inner in node.body:
                if isinstance(inner, ast.Return) and (inner.value is None or
                                                      (isinstance(inner.value, ast.Constant) and inner.value.value in (None, False))):
                    sym.early_returns.append(inner.lineno)
        elif isinstance(node, (ast.For, ast.While)):
            header = ast.unparse(node.test) if isinstance(node, ast.While) else f"{ast.unparse(node.target)} {ast.unparse(node.iter)}"
            if RETRY_LOOP_HEADER.search(header) and any(isinstance(n, ast.Try) for n in _walk_no_defs(node)):
                sym.retry_loop = True
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if TX_MARKER.search(ast.unparse(item.context_expr)):
                    sym.has_tx = True


def _scan_node(node, sym: SymbolFacts) -> None:
    if isinstance(node, ast.Call):
        name, receiver = _callee(node.func)
        if name:
            sym.calls.append((name, receiver, node.lineno))
            if TX_MARKER.search(name):
                sym.has_tx = True
            if isinstance(node.func, ast.Attribute) and name in MUTATORS:
                target = _attr_name(node.func.value)
                if target:
                    sym.writes_attr.append((target, node.lineno))
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                for kind, table in sql_tables(arg.value):
                    sym.sql.append((kind, table, node.lineno))
    elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            for tt in (t.elts if isinstance(t, (ast.Tuple, ast.List)) else [t]):
                if isinstance(tt, ast.Attribute):
                    sym.writes_attr.append((tt.attr, node.lineno))
                elif isinstance(tt, ast.Subscript) and _attr_name(tt.value):
                    sym.writes_attr.append((_attr_name(tt.value), node.lineno))
    elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
        sym.reads_attr.append((node.attr, node.lineno))
    elif isinstance(node, ast.Name) and IDEM_MARKER.search(node.id):
        sym.has_idem = True
    elif isinstance(node, ast.Constant) and isinstance(node.value, str) and IDEM_MARKER.search(node.value):
        sym.has_idem = True


def _attr_name(node) -> str | None:
    return node.attr if isinstance(node, ast.Attribute) else None


def _callee(func) -> tuple[str | None, str | None]:
    if isinstance(func, ast.Name):
        return func.id, None
    if isinstance(func, ast.Attribute):
        v = func.value
        if isinstance(v, ast.Name):
            return func.attr, v.id
        return func.attr, "?"
    return None, None


def _route_from_decorator(dec) -> tuple[str, str] | None:
    """@app.post('/x'), @router.get('/x'), @app.route('/x', methods=['POST']), @app.api_route(...)"""
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute) or not dec.args:
        return None
    first = dec.args[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return None
    norm = normalize_route(first.value)
    if not norm:
        return None
    attr = dec.func.attr.lower()
    if attr in ROUTE_METHODS:
        return attr.upper(), norm[1]
    if attr in ("route", "api_route"):
        for kw in dec.keywords:
            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)) and kw.value.elts:
                el = kw.value.elts[0]
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    return el.value.upper(), norm[1]
        return "GET", norm[1]
    return None
