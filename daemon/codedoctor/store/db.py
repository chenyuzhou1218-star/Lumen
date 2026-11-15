"""SQLite database (WAL mode). One file per project.

Every table keeps the full JSON document in `doc`; other columns are indexes.
Nothing here is ever summarized away: journal and messages are append-only.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 5

_DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    thread_id TEXT NOT NULL,
    reply_to TEXT,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    kind TEXT NOT NULL,
    task_id TEXT,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_inbox ON messages (recipient, delivered_at, seq);
CREATE INDEX IF NOT EXISTS messages_thread ON messages (thread_id, seq);
CREATE INDEX IF NOT EXISTS messages_task ON messages (task_id, seq);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    requester TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,          -- queued | running | finished
    outcome TEXT,                 -- report outcome when finished
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    usage TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,          -- idle | working | paused | stopped
    reason TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    agent TEXT NOT NULL,
    task_id TEXT,
    type TEXT NOT NULL,
    at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS journal_task ON journal (task_id, seq);
CREATE INDEX IF NOT EXISTS journal_agent ON journal (agent, seq);

CREATE TABLE IF NOT EXISTS notes (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,
    task_id TEXT,
    created_at TEXT NOT NULL,
    superseded_by TEXT,
    pinned INTEGER NOT NULL DEFAULT 0,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS notes_owner ON notes (owner, scope);
-- trigram: substring search that works for file paths, identifiers and Chinese text alike.
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5 (
    text, entities, refs, tokenize = 'trigram case_sensitive 0'
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    doc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    author TEXT NOT NULL,
    task_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS claims_task ON claims (task_id);
"""

# Added in schema version 2. Every statement is idempotent so it can run on new and old databases.
_DDL_V2 = """
CREATE TABLE IF NOT EXISTS effects (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    tool TEXT NOT NULL,
    state TEXT NOT NULL,          -- intent | done | failed | unknown
    intent_at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS effects_task ON effects (task_id, intent_at);

CREATE TABLE IF NOT EXISTS validations (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    overall TEXT NOT NULL,
    validated_at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS validations_claim ON validations (claim_id, validated_at);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    verdict TEXT NOT NULL,
    at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reviews_claim ON reviews (claim_id, at);

CREATE TABLE IF NOT EXISTS claim_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS claim_events_claim ON claim_events (claim_id, seq);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT NOT NULL,
    version INTEGER NOT NULL,
    doc TEXT NOT NULL,
    PRIMARY KEY (id, version)
);
"""

# Added in schema version 3: coupling graph, task tree, head objections.
_DDL_V3 = """
CREATE TABLE IF NOT EXISTS graph_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_edges (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    src TEXT NOT NULL,
    rel TEXT NOT NULL,
    dst TEXT NOT NULL,
    provenance TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS graph_edges_src ON graph_edges (src);
CREATE INDEX IF NOT EXISTS graph_edges_dst ON graph_edges (dst);
CREATE TABLE IF NOT EXISTS graph_risks (
    id TEXT PRIMARY KEY,
    severity TEXT NOT NULL,
    pattern TEXT NOT NULL,
    rank INTEGER NOT NULL,
    doc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS objections (
    id TEXT PRIMARY KEY,
    root_task_id TEXT NOT NULL,
    raised_by TEXT NOT NULL,
    status TEXT NOT NULL,          -- open | withdrawn | resolved_by_user
    at TEXT NOT NULL,
    doc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS objections_task ON objections (root_task_id, status);
"""

# Added in schema version 4: which entities each note is about, for coupling-aware recall (ADR 0006).
_DDL_V4 = """
CREATE TABLE IF NOT EXISTS note_entities (
    entity TEXT NOT NULL,
    note_rowid INTEGER NOT NULL,
    PRIMARY KEY (entity, note_rowid)
) WITHOUT ROWID;
"""

# Added in schema version 5: note embeddings for semantic recall (ADR 0007). Vectors of different
# models are never compared, so each row is keyed by "<endpoint>/<model>". dim 0 marks a note that
# may not be sent to that endpoint (data class); it is not retried.
_DDL_V5 = """
CREATE TABLE IF NOT EXISTS note_vectors (
    model TEXT NOT NULL,
    note_rowid INTEGER NOT NULL,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL,
    PRIMARY KEY (model, note_rowid)
) WITHOUT ROWID;
"""


class Database:
    """Thread-safe wrapper. The daemon is single-process; WAL lets the CLI read while it runs."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_DDL)
            row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            version = int(row["value"]) if row else SCHEMA_VERSION
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"{self.path}: database schema {version} is newer than supported {SCHEMA_VERSION}")
            self._conn.executescript(_DDL_V2)
            cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(tasks)")}
            if "body" not in cols:
                self._conn.execute("ALTER TABLE tasks ADD COLUMN body TEXT")
            self._conn.executescript(_DDL_V3)
            if "parent_task_id" not in cols:
                self._conn.execute("ALTER TABLE tasks ADD COLUMN parent_task_id TEXT")
            self._conn.execute("CREATE INDEX IF NOT EXISTS tasks_parent ON tasks (parent_task_id)")
            self._conn.executescript(_DDL_V4)
            if version < 4:
                self._backfill_note_entities()
            self._conn.executescript(_DDL_V5)
            self._conn.execute(
                "INSERT INTO meta VALUES ('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(SCHEMA_VERSION),),
            )

    def _backfill_note_entities(self) -> None:
        rows = self._conn.execute("SELECT rowid, doc FROM notes").fetchall()
        self._conn.executemany("INSERT OR IGNORE INTO note_entities (entity, note_rowid) VALUES (?,?)",
                               [(ent, r["rowid"]) for r in rows for ent in json.loads(r["doc"]).get("entities", [])])

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def dumps(doc: Any) -> str:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
