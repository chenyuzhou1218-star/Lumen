"""JavaScript / TypeScript source -> FileFacts, using tree-sitter (exact syntax tree)."""

from __future__ import annotations

import posixpath
import re
from functools import lru_cache

from codedoctor.graph.facts import IDEM_MARKER, RETRY_LOOP_HEADER, TX_MARKER, FileFacts, SymbolFacts, normalize_route, sql_tables

FUNCS = {"function_declaration", "generator_function_declaration", "function_expression", "function", "arrow_function",
         "generator_function", "method_definition"}
EMIT_FNS = {"emit", "_emit", "trigger", "dispatch", "publish", "fire", "emitEvent", "broadcast", "notify"}
LISTEN_FNS = {"on", "once", "addListener", "addEventListener", "subscribe", "listen", "onMessage", "prependListener"}
SEND_FNS = {"send", "sendMessage", "sendJSON", "sendJson", "request", "sendRequest", "rpc", "invoke", "post", "call"}
HTTP_OBJECTS = {"axios", "http", "https", "api", "$http", "request", "superagent", "ky"}
SERVER_OBJECTS = {"app", "router", "server", "api", "fastify", "routes"}
ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "all"}
MUTATORS = {"push", "pop", "shift", "unshift", "splice", "set", "delete", "add", "clear", "sort", "reverse", "fill"}
TYPE_KEYS = {"type", "action", "op", "cmd", "command", "event", "msgType", "messageType", "kind"}
FALSY_RETURN = {"null", "undefined", "false"}


@lru_cache(maxsize=4)
def _parser(lang: str):
    import tree_sitter as ts

    if lang == "typescript":
        import tree_sitter_typescript as tst
        language = ts.Language(tst.language_typescript())
    elif lang == "tsx":
        import tree_sitter_typescript as tst
        language = ts.Language(tst.language_tsx())
    else:
        import tree_sitter_javascript as tsj
        language = ts.Language(tsj.language())
    return ts.Parser(language)


def _lang_for(path: str) -> str:
    if path.endswith(".tsx"):
        return "tsx"
    if path.endswith((".ts", ".mts", ".cts")):
        return "typescript"
    return "javascript"


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _string_value(node, src: bytes) -> str | None:
    if node is None:
        return None
    if node.type == "string":
        return "".join(_text(c, src) for c in node.children if c.type == "string_fragment")
    if node.type == "template_string":
        # keep literal parts, turn ${...} into a parameter placeholder
        out = []
        for c in node.children:
            if c.type == "string_fragment":
                out.append(_text(c, src))
            elif c.type == "template_substitution":
                out.append("${p}")
        return "".join(out)
    return None


def _args(call) -> list:
    a = call.child_by_field_name("arguments")
    return [c for c in a.named_children] if a is not None else []


def _line(node) -> int:
    return node.start_point[0] + 1


def resolve_import(from_path: str, spec: str, files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = posixpath.normpath(posixpath.join(posixpath.dirname(from_path), spec))
    for cand in (base, base + ".js", base + ".ts", base + ".mjs", base + ".jsx", base + ".tsx",
                 base + "/index.js", base + "/index.ts"):
        if cand in files:
            return cand
    return None


def extract(path: str, source: str, files: set[str]) -> FileFacts:
    ff = FileFacts(path, "javascript")
    src = source.encode("utf-8")
    try:
        tree = _parser(_lang_for(path)).parse(src)
    except Exception as e:  # parser unavailable or crashed
        ff.error = f"{type(e).__name__}: {e}"
        return ff
    module = SymbolFacts("<module>", path, 1, "module", "javascript")
    ff.symbols.append(module)
    _Walker(ff, src, files).visit(tree.root_node, module, None, [])
    return ff


class _Walker:
    def __init__(self, ff: FileFacts, src: bytes, files: set[str]):
        self.ff, self.src, self.files = ff, src, files

    def t(self, node) -> str:
        return _text(node, self.src)

    # --- symbols ------------------------------------------------------------------------

    def new_symbol(self, qual: str, node, kind: str, cls: str | None) -> SymbolFacts:
        sym = SymbolFacts(qual, self.ff.path, _line(node), kind, "javascript", cls)
        self.ff.symbols.append(sym)
        params = node.child_by_field_name("parameters")
        if params is not None and IDEM_MARKER.search(self.t(params)):
            sym.has_idem = True
        return sym

    def function_name(self, node, cls: str | None, names: list[str]) -> str | None:
        if node.type in ("function_declaration", "generator_function_declaration"):
            n = node.child_by_field_name("name")
            return self.t(n) if n else None
        if node.type == "method_definition":
            n = node.child_by_field_name("name")
            owner = cls or (names[-1] if names else None)
            return f"{owner}.{self.t(n)}" if owner and n else (self.t(n) if n else None)
        parent = node.parent
        if parent is None:
            return None
        if parent.type == "variable_declarator":
            n = parent.child_by_field_name("name")
            return self.t(n) if n and n.type == "identifier" else None
        if parent.type == "assignment_expression":
            left = parent.child_by_field_name("left")
            if left is not None:
                text = self.t(left)
                parts = [p for p in re.split(r"\.|\[|\]", text) if p and p not in ("prototype", "this", "window", "global", "globalThis", "exports", "module")]
                return ".".join(parts[-2:]) if parts else None
        if parent.type == "pair":
            key = parent.child_by_field_name("key")
            if key is not None:
                k = _string_value(key, self.src) or self.t(key)
                return f"{names[-1]}.{k}" if names else k
        return None

    # --- walk -----------------------------------------------------------------------------

    def visit(self, node, sym: SymbolFacts, cls: str | None, names: list[str]) -> None:
        t = node.type
        if t in ("class_declaration", "class"):
            n = node.child_by_field_name("name")
            cname = self.t(n) if n is not None else (self.function_name(node, cls, names) if node.parent is not None else None)
            if cname:
                self.ff.symbols.append(SymbolFacts(cname, self.ff.path, _line(node), "class", "javascript", cname))
            for c in node.named_children:
                self.visit(c, sym, cname or cls, names + ([cname] if cname else []))
            return
        if t in FUNCS:
            name = self.function_name(node, cls, names)
            if name:
                kind = "method" if t == "method_definition" or "." in name else "function"
                fsym = self.new_symbol(name, node, kind, cls)
                self.scan_function(node, fsym)
                body = node.child_by_field_name("body")
                if body is not None:
                    for c in body.named_children if body.type == "statement_block" else [body]:
                        self.visit(c, fsym, cls, names)
                return
            # anonymous function: its effects belong to the enclosing symbol
            body = node.child_by_field_name("body")
            if body is not None:
                self.scan_control(body, sym)
                self.visit(body, sym, cls, names)
            return
        if t == "variable_declarator":
            n = node.child_by_field_name("name")
            v = node.child_by_field_name("value")
            if n is not None and v is not None and v.type == "object":
                for c in node.named_children:
                    self.visit(c, sym, cls, names + [self.t(n)])
                return
            if n is not None and v is not None and v.type == "call_expression":
                fn = v.child_by_field_name("function")
                if fn is not None and self.t(fn) == "require":
                    a = _args(v)
                    spec = _string_value(a[0], self.src) if a else None
                    target = resolve_import(self.ff.path, spec, self.files) if spec else None
                    if target:
                        self.ff.imports.append((target, _line(node)))
                        self.ff.bindings[self.t(n)] = (target, None)
        if t == "import_statement":
            self.import_stmt(node)
            return
        if t == "call_expression":
            if self.call(node, sym, cls, names):
                return
        elif t == "new_expression":
            ctor = node.child_by_field_name("constructor")
            if ctor is not None:
                sym.calls.append((self.t(ctor).split(".")[-1], None, _line(node)))
        elif t in ("assignment_expression", "augmented_assignment_expression"):
            left = node.child_by_field_name("left")
            if left is not None and left.type in ("member_expression", "subscript_expression"):
                attr = self.member_attr(left)
                if attr:
                    sym.writes_attr.append((attr, _line(node)))
        elif t == "update_expression":
            arg = node.child_by_field_name("argument")
            if arg is not None and arg.type == "member_expression":
                attr = self.member_attr(arg)
                if attr:
                    sym.writes_attr.append((attr, _line(node)))
        elif t == "member_expression":
            prop = node.child_by_field_name("property")
            if prop is not None:
                sym.reads_attr.append((self.t(prop), _line(node)))
        elif t == "switch_statement":
            value = node.child_by_field_name("value")
            if value is not None and any(k in self.t(value) for k in TYPE_KEYS):
                for case in node.named_children[-1].named_children if node.named_children else []:
                    if case.type == "switch_case":
                        v = case.child_by_field_name("value")
                        s = _string_value(v, self.src)
                        if s:
                            sym.consumes_msg.append((s, _line(case)))
        elif t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op is not None and self.t(op) in ("===", "=="):
                left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
                for a, b in ((left, right), (right, left)):
                    if a is not None and a.type == "member_expression" and b is not None:
                        prop = a.child_by_field_name("property")
                        s = _string_value(b, self.src)
                        if prop is not None and self.t(prop) in TYPE_KEYS and s:
                            sym.consumes_msg.append((s, _line(node)))
        elif t in ("identifier", "property_identifier", "shorthand_property_identifier"):
            text = self.t(node)
            if IDEM_MARKER.search(text):
                sym.has_idem = True
            if TX_MARKER.search(text):
                sym.has_tx = True
        elif t == "string":
            s = _string_value(node, self.src) or ""
            for kind, table in sql_tables(s):
                sym.sql.append((kind, table, _line(node)))
        for c in node.named_children:
            self.visit(c, sym, cls, names)

    def member_attr(self, node) -> str | None:
        if node.type == "member_expression":
            prop = node.child_by_field_name("property")
            return self.t(prop) if prop is not None else None
        if node.type == "subscript_expression":
            obj = node.child_by_field_name("object")
            return self.member_attr(obj) if obj is not None else None
        return None

    def import_stmt(self, node) -> None:
        source = node.child_by_field_name("source")
        spec = _string_value(source, self.src) if source is not None else None
        target = resolve_import(self.ff.path, spec, self.files) if spec else None
        if not target:
            return
        self.ff.imports.append((target, _line(node)))
        for clause in node.named_children:
            if clause.type != "import_clause":
                continue
            for c in clause.named_children:
                if c.type == "identifier":
                    self.ff.bindings[self.t(c)] = (target, "default")
                elif c.type == "namespace_import":
                    ids = [x for x in c.named_children if x.type == "identifier"]
                    if ids:
                        self.ff.bindings[self.t(ids[0])] = (target, None)
                elif c.type == "named_imports":
                    for spec_node in c.named_children:
                        if spec_node.type == "import_specifier":
                            name = spec_node.child_by_field_name("name")
                            alias = spec_node.child_by_field_name("alias")
                            if name is not None:
                                self.ff.bindings[self.t(alias or name)] = (target, self.t(name))

    # --- calls ----------------------------------------------------------------------------

    def call(self, node, sym: SymbolFacts, cls: str | None, names: list[str]) -> bool:
        """Record what a call means. Returns True if it fully handled the node's children."""
        fn = node.child_by_field_name("function")
        if fn is None:
            return False
        args = _args(node)
        line = _line(node)
        if fn.type == "identifier":
            name, receiver, obj_text = self.t(fn), None, None
        elif fn.type == "member_expression":
            prop = fn.child_by_field_name("property")
            obj = fn.child_by_field_name("object")
            name = self.t(prop) if prop is not None else None
            obj_text = self.t(obj) if obj is not None else ""
            receiver = "this" if obj_text == "this" else (obj_text if obj is not None and obj.type == "identifier" else "?")
        else:
            return False
        if not name:
            return False
        first = _string_value(args[0], self.src) if args else None

        # HTTP client
        if name == "fetch" and first is not None:
            route = normalize_route(first)
            if route:
                method = "GET"
                if len(args) > 1 and args[1].type == "object":
                    m = self.object_value(args[1], {"method"})
                    if m:
                        method = m.upper()
                sym.http.append((method, route[1], line, route[0]))
        elif receiver in HTTP_OBJECTS and name.lower() in ROUTE_METHODS and first is not None:
            route = normalize_route(first)
            if route:
                sym.http.append((name.upper(), route[1], line, route[0]))
        elif name == "open" and len(args) >= 2 and first and first.upper() in {m.upper() for m in ROUTE_METHODS}:
            route = normalize_route(_string_value(args[1], self.src) or "")
            if route:
                sym.http.append((first.upper(), route[1], line, route[0]))
        elif first is not None and normalize_route(first) and (
                re.search(r"fetch|request|http|ajax|api|call", name, re.I)
                or (len(args) > 1 and args[1].type == "object" and self.object_value(args[1], {"method"}))):
            # project-specific wrapper around fetch: retryFetch("/api/x", {method: "POST"})
            route = normalize_route(first)
            method = (self.object_value(args[1], {"method"}) if len(args) > 1 and args[1].type == "object" else None) or "GET"
            sym.http.append((method.upper(), route[1], line, route[0]))

        # server routes (express-style)
        if receiver in SERVER_OBJECTS and name.lower() in ROUTE_METHODS and first is not None and normalize_route(first):
            handler = next((a for a in args[1:][::-1] if a.type in FUNCS or a.type in ("identifier", "member_expression")), None)
            route_path = normalize_route(first)[1]
            method = "ANY" if name == "all" else name.upper()
            if handler is not None and handler.type in FUNCS:
                qual = f"route_{method}_{route_path}"
                hsym = self.new_symbol(qual, handler, "listener", cls)
                self.scan_function(handler, hsym)
                self.ff.routes.append((method, route_path, qual, line))
                body = handler.child_by_field_name("body")
                if body is not None:
                    self.visit(body, hsym, cls, names)
                return True
            if handler is not None:
                self.ff.routes.append((method, route_path, "ref:" + self.t(handler).split(".")[-1], line))

        # event bus
        if name in EMIT_FNS and first is not None:
            sym.emits.append(("event", first, line))
        if name == "dispatchEvent" and args and args[0].type == "new_expression":
            inner = _args(args[0])
            ev = _string_value(inner[0], self.src) if inner else None
            if ev:
                sym.emits.append(("event", ev, line))
        if name in LISTEN_FNS and first is not None and len(args) >= 2:
            handler = args[1]
            kind = "ws_msg" if receiver and re.search(r"sock|ws|conn|channel|io", receiver or "", re.I) and first not in ("message", "open", "close", "error") else "event"
            if handler.type in FUNCS:
                owner = sym.qualname if sym.qualname != "<module>" else ""
                qual = f"{owner}.on_{first}" if owner else f"on_{first}"
                hsym = self.new_symbol(qual, handler, "listener", cls)
                self.scan_function(handler, hsym)
                self.ff.listeners.append((kind, first, qual, line))
                body = handler.child_by_field_name("body")
                if body is not None:
                    self.visit(body, hsym, cls, names)
                fn_obj = fn.child_by_field_name("object") if fn.type == "member_expression" else None
                if fn_obj is not None:
                    self.visit(fn_obj, sym, cls, names)
                return True
            if handler.type in ("identifier", "member_expression"):
                self.ff.listeners.append((kind, first, "ref:" + self.t(handler).split(".")[-1], line))

        # messages to a server / peer
        if name in SEND_FNS and receiver not in HTTP_OBJECTS:
            msg = first if first and not normalize_route(first) else self.find_type_key(args)
            if msg:
                sym.emits.append(("ws_msg", msg, line))

        # mutating method on a member: this.items.push(x)
        if name in MUTATORS and fn.type == "member_expression":
            obj = fn.child_by_field_name("object")
            if obj is not None and obj.type == "member_expression":
                attr = self.member_attr(obj)
                if attr:
                    sym.writes_attr.append((attr, line))
        if TX_MARKER.search(name):
            sym.has_tx = True
        sym.calls.append((name, receiver, line))
        return False

    def object_value(self, obj, keys: set[str]) -> str | None:
        for pair in obj.named_children:
            if pair.type == "pair":
                k = pair.child_by_field_name("key")
                v = pair.child_by_field_name("value")
                if k is not None and (self.t(k).strip("'\"") in keys):
                    s = _string_value(v, self.src)
                    if s:
                        return s
        return None

    def find_type_key(self, nodes, depth: int = 0) -> str | None:
        if depth > 3:
            return None
        for n in nodes:
            if n.type == "object":
                v = self.object_value(n, TYPE_KEYS)
                if v:
                    return v
            found = self.find_type_key(n.named_children, depth + 1)
            if found:
                return found
        return None

    # --- control flow ---------------------------------------------------------------------

    def scan_function(self, fn, sym: SymbolFacts) -> None:
        body = fn.child_by_field_name("body")
        if body is not None:
            self.scan_control(body, sym)

    def scan_control(self, node, sym: SymbolFacts) -> None:
        stack = [node]
        while stack:
            n = stack.pop()
            if n.type in FUNCS and n is not node:
                continue
            if n.type == "if_statement":
                cons = n.child_by_field_name("consequence")
                stmts = cons.named_children if cons is not None and cons.type == "statement_block" else ([cons] if cons is not None else [])
                for s in stmts:
                    if s.type == "return_statement":
                        val = s.named_children[0] if s.named_children else None
                        if val is None or self.t(val) in FALSY_RETURN:
                            sym.early_returns.append(_line(s))
            elif n.type in ("for_statement", "for_in_statement", "while_statement", "do_statement"):
                body = n.child_by_field_name("body")
                header = self.t(n)[: (body.start_byte - n.start_byte) if body is not None else 200]
                if n.type == "do_statement":
                    cond = n.child_by_field_name("condition")
                    header = self.t(cond) if cond is not None else ""
                if RETRY_LOOP_HEADER.search(header) and self.contains(n, "try_statement"):
                    sym.retry_loop = True
            stack.extend(n.named_children)

    @staticmethod
    def contains(node, type_name: str) -> bool:
        stack = list(node.named_children)
        while stack:
            n = stack.pop()
            if n.type == type_name:
                return True
            if n.type not in FUNCS:
                stack.extend(n.named_children)
        return False
