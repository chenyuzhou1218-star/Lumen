"""Semantic recall (ADR 0007, M6): note embeddings from the embedding model the user chose.

Trigram text search finds notes that share words with the question; it cannot see that
"match reward paid twice" and "比赛奖励到账两次" mean the same thing. An embedding model can.

- Only when the user configured memory.embedding; nothing here picks or switches a model.
- Notes are embedded in the background (Daemon) and, a bounded batch, right before a search,
  so a note written a moment ago can already be found. Newest notes first.
- Vectors are stored unit length (float32) under "<endpoint>/<model>"; vectors of different
  models are never compared. A search is a dot product over the notes the reader may see.
- Data classes: a note's text is sent only if its class is allowed at the embedding endpoint
  (endpoint max_data_class). A note that is not gets a marker row (dim 0) and is never found by
  meaning; text and coupling recall still find it. The query is held to the same rule.
- A failing endpoint never breaks recall: search raises VectorUnavailable, the caller falls
  back to text and coupling, and the reason is kept in `last_error`.
"""

from __future__ import annotations

import json
import math
from array import array

from codedoctor.evidence.registry import data_class_rank
from codedoctor.memory.notes import note_data_class
from codedoctor.models.base import ModelError

BATCH = 32         # notes per embedding request
MAX_CHARS = 2000   # of each note sent for embedding
_sumprod = getattr(math, "sumprod", None) or (lambda a, b: sum(x * y for x, y in zip(a, b)))


class VectorUnavailable(Exception):
    pass


def _unit(v: list[float]) -> array:
    norm = math.sqrt(_sumprod(v, v)) or 1.0
    return array("f", (x / norm for x in v))


class VectorIndex:
    def __init__(self, services):
        self.s = services
        self.cfg = services.config.embedding
        self.key = f"{self.cfg.endpoint}/{self.cfg.model}" if self.cfg else None
        self.last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self.cfg is not None

    def allowed(self, data_class: str) -> bool:
        ep = self.s.config.endpoints[self.cfg.endpoint]
        return data_class_rank(data_class) <= data_class_rank(ep.max_data_class)

    def note_class(self, note: dict) -> str:
        return note_data_class(note, self.s.config.code_data_class)

    async def _embed(self, texts: list[str]) -> list[array]:
        try:
            async with self.s.models.limit(self.cfg.endpoint):
                vectors = await self.s.models.client(self.cfg.endpoint).embed(self.cfg.model, texts)
        except ModelError as e:
            self.last_error = f"{self.key}: {e}"
            raise VectorUnavailable(self.last_error) from e
        self.last_error = None
        return [_unit(v) for v in vectors]

    def pending(self, limit: int) -> list[tuple[int, dict]]:
        rows = self.s.db.query(
            """SELECT n.rowid AS rowid, n.doc FROM notes n
               LEFT JOIN note_vectors v ON v.note_rowid = n.rowid AND v.model = ?
               WHERE v.note_rowid IS NULL AND n.superseded_by IS NULL ORDER BY n.rowid DESC LIMIT ?""",
            (self.key, limit))
        return [(r["rowid"], json.loads(r["doc"])) for r in rows]

    async def index_pending(self, limit: int = BATCH) -> int:
        """Embed up to `limit` notes that have no vector for this model yet. Returns how many were handled."""
        if not self.enabled:
            return 0
        rows = self.pending(limit)
        send = [(rowid, doc) for rowid, doc in rows if self.allowed(self.note_class(doc))]
        vectors = await self._embed([doc["text"][:MAX_CHARS] for _, doc in send]) if send else []
        sent = {rowid for rowid, _ in send}
        with self.s.db.tx() as c:
            c.executemany("INSERT OR REPLACE INTO note_vectors (model, note_rowid, dim, vec) VALUES (?,?,?,?)",
                          [(self.key, rowid, len(v), v.tobytes()) for (rowid, _), v in zip(send, vectors)]
                          + [(self.key, rowid, 0, b"") for rowid, _ in rows if rowid not in sent])
        return len(rows)

    def _drop_other_dims(self, dim: int) -> int:
        """Forget this model's vectors of another length (the same model name can answer with a different one). Returns
        how many were forgotten, so they are embedded again."""
        with self.s.db.tx() as c:
            cur = c.execute("DELETE FROM note_vectors WHERE model = ? AND dim <> ?", (self.key, dim))
            return cur.rowcount

    def count(self) -> dict:
        row = self.s.db.one("SELECT SUM(dim > 0) AS vectors, SUM(dim = 0) AS withheld FROM note_vectors WHERE model = ?", (self.key,))
        return {"vectors": row["vectors"] or 0, "withheld": row["withheld"] or 0, "pending": len(self.pending(1_000_000))}

    async def search(self, query: str, *, reader: str, include_shared: bool, data_class: str, top: int = 50) -> dict[str, float]:
        """note id -> how close in meaning, 0..1 (cosine similarity rescaled above min_similarity).
        Empty when the query itself may not be sent to the embedding endpoint."""
        if not self.enabled or not self.allowed(data_class):
            return {}
        await self.index_pending()
        [q] = await self._embed([query[:MAX_CHARS]])
        if self._drop_other_dims(len(q)):  # the model answers with another length now: those vectors cannot be compared
            while await self.index_pending() >= BATCH:  # Haiku check item 19: re-embed them, or they vanish from meaning search
                pass
        vis_sql, vis_params = self.s.notes._visible(reader, include_shared)
        rows = self.s.db.query(
            f"""SELECT n.id, v.vec FROM note_vectors v JOIN notes n ON n.rowid = v.note_rowid
                WHERE v.model = ? AND v.dim = ? AND n.superseded_by IS NULL AND {vis_sql}""",
            (self.key, len(q), *vis_params))
        floor = self.cfg.min_similarity
        scored = []
        for r in rows:
            vec = array("f")
            vec.frombytes(r["vec"])
            sim = _sumprod(q, vec)
            if sim > floor:
                scored.append((r["id"], round((sim - floor) / (1 - floor), 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return dict(scored[:top])
