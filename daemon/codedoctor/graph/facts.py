"""Language-neutral facts extracted from one source file, before cross-file resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

RETRYISH_NAME = re.compile(r"retry|reconnect|resend|replay|redeliver|resubmit", re.I)
RETRY_LOOP_HEADER = re.compile(r"attempt|retr|tries|backoff", re.I)
TX_MARKER = re.compile(r"transaction|atomic|begin_tx|\bbegin\b|commit|rollback|savepoint", re.I)
IDEM_MARKER = re.compile(r"idempot|request_?id|requestid|dedup|nonce|once_key|operation_?id", re.I)
SQL_WRITE = re.compile(r"\b(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO|UPSERT\s+INTO)\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)", re.I)
SQL_READ = re.compile(r"\b(?:FROM|JOIN)\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)", re.I)
ROUTE_PARAM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)|<(?:[A-Za-z_]+:)?([A-Za-z_][A-Za-z0-9_]*)>|\$\{[^}]*\}")


SQL_SHAPE = re.compile(
    r"^\s*(?:SELECT\b[\s\S]*\bFROM\b|INSERT\s+(?:OR\s+\w+\s+)?INTO\b|UPDATE\s+[`\"\[]?\w+[`\"\]]?\s+SET\b|"
    r"DELETE\s+FROM\b|REPLACE\s+INTO\b|UPSERT\s+INTO\b|WITH\s+\w+\s+AS\s*\()", re.I)


def sql_tables(text: str) -> list[tuple[str, str]]:
    """[('writes'|'reads', table)] from a string that really is SQL (not an English sentence containing 'update')."""
    if not SQL_SHAPE.search(text):
        return []
    out = [("writes", t) for t in SQL_WRITE.findall(text)]
    written = {t for _, t in out}
    out += [("reads", t) for t in SQL_READ.findall(text) if t not in written or text.lstrip().upper().startswith("SELECT")]
    return out


def normalize_route(raw: str) -> tuple[str | None, str] | None:
    """('host' or None, '/templated/{param}/path') for a URL or path literal, else None."""
    raw = raw.strip()
    host = None
    m = re.match(r"^[a-z]+://([^/]+)(/.*)?$", raw, re.I)
    if m:
        host, raw = m.group(1).lower(), m.group(2) or "/"
    if not raw.startswith("/"):
        return None
    raw = raw.split("?", 1)[0].split("#", 1)[0]
    path = ROUTE_PARAM.sub(lambda m: "{" + (m.group(1) or m.group(2) or "p") + "}", raw)
    if re.search(r"\s|:", path) or len(path) > 1000:
        return None
    return host, path


@dataclass
class SymbolFacts:
    qualname: str
    path: str
    line: int
    kind: str                     # function | method | class | module | listener
    language: str
    class_name: str | None = None
    calls: list[tuple[str, str | None, int]] = field(default_factory=list)      # (name, receiver, line)
    writes_attr: list[tuple[str, int]] = field(default_factory=list)
    reads_attr: list[tuple[str, int]] = field(default_factory=list)
    emits: list[tuple[str, str, int]] = field(default_factory=list)            # ('event'|'ws_msg', name, line)
    consumes_msg: list[tuple[str, int]] = field(default_factory=list)          # ws message types handled inside
    http: list[tuple[str, str, int, str | None]] = field(default_factory=list) # (METHOD, path, line, host)
    sql: list[tuple[str, str, int]] = field(default_factory=list)              # ('reads'|'writes', table, line)
    early_returns: list[int] = field(default_factory=list)
    has_tx: bool = False
    has_idem: bool = False
    retry_loop: bool = False

    @property
    def retryish(self) -> bool:
        return self.retry_loop or bool(RETRYISH_NAME.search(self.qualname.rsplit(".", 1)[-1]))


@dataclass
class FileFacts:
    path: str
    language: str
    symbols: list[SymbolFacts] = field(default_factory=list)
    imports: list[tuple[str, int]] = field(default_factory=list)                # resolved repo paths
    bindings: dict[str, tuple[str, str | None]] = field(default_factory=dict)  # local name -> (repo path, name or None for module)
    routes: list[tuple[str, str, str, int]] = field(default_factory=list)      # (METHOD, path, handler qualname, line)
    listeners: list[tuple[str, str, str, int]] = field(default_factory=list)   # ('event'|'ws_msg', name, handler qualname, line)
    error: str | None = None
