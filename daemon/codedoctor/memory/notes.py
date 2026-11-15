"""Memory notes: the compact, searchable layer of long-term memory.

Each note (schemas/memory/note) is a fact, decision, observation, todo or
summary, tied to the entities, evidence, claims, code version and journal
entries it came from. Notes are never deleted; a correction supersedes the old
note, which then drops out of recall but stays readable.

Search uses SQLite FTS5 with the trigram tokenizer so exact identifiers, file
paths and line numbers ("shop.py:47", "inventory_version") and Chinese text
match as substrings. Two-character terms (common in Chinese) are matched with
LIKE because trigrams need three characters.

Recall also (docs/adr/0006):
- reads the CURRENT status of every claim a note cites, so a note whose claim
  was later refuted, withdrawn or made stale is flagged and ranked down instead
  of being recalled as if it were still true (a superseded claim is followed
  to the claim that replaced it);
- takes optional `related` entities (from the coupling graph, see
  memory/related.py) and recalls notes about them even when the query text
  never mentions them, saying through which coupling each one was reached.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from codedoctor import ids
from codedoctor.evidence.registry import data_class_rank, stricter
from codedoctor.protocol.registry import validator
from codedoctor.store.db import Database, dumps

SCHEMA = "memory/note.schema.json"

_CJK = r"㐀-鿿豈-﫿"
_TOKEN = re.compile(rf"[{_CJK}]+|[A-Za-z0-9_./#:@\-]+")


class MemoryError_(ValueError):
    pass


@dataclass(frozen=True)
class RecallWeights:
    """How recall ranks notes. The bench (codedoctor.bench) runs the same queries under other weights to measure them."""
    # added per cited claim, by its current status; a note citing several claims gets the mean
    claim: dict = field(default_factory=lambda: {"supported": 0.2, "proposed": 0.0, "needs_revalidation": -0.15,
                                                 "refuted": -0.3, "withdrawn": -0.3})
    # for a note about an entity this many coupling hops from one the query is about
    entity: dict = field(default_factory=lambda: {0: 0.6, 1: 0.4, 2: 0.25})
    summary_penalty: float = 0.1  # a long task summary matches many terms by sheer length; prefer the specific notes
    pinned: float = 0.25
    semantic: float = 0.6  # times how close in meaning (0..1) the note is to the query, when semantic recall is on


DEFAULT_WEIGHTS = RecallWeights()
_FLAG = {
    "supported": "VERIFIED",
    "proposed": "UNVERIFIED",
    "needs_revalidation": "STALE (code changed since; re-check before relying on it)",
    "refuted": "REFUTED (disproven; do not rely on it)",
    "withdrawn": "WITHDRAWN by its author",
}

# entity -> (coupling hops from an entity the query is about, how it was reached)
Related = dict[str, tuple[int, str]]


@dataclass
class Recalled:
    note: dict
    score: float
    flags: list[str] = field(default_factory=list)  # live state of the claims the note cites
    via: str | None = None                          # the coupling through which it was recalled
    meaning: float | None = None                    # how close in meaning (0..1), when semantic recall found it


def _terms(query: str) -> tuple[list[str], list[str]]:
    """Split a query into (fts terms of >=3 chars, short terms matched with LIKE)."""
    fts, short = [], []
    for tok in _TOKEN.findall(query.lower()):
        tok = tok.strip(".:#-")
        if not tok:
            continue
        if re.fullmatch(rf"[{_CJK}]+", tok) and len(tok) > 3:
            fts.extend(tok[i : i + 3] for i in range(len(tok) - 2))
        elif len(tok) >= 3:
            fts.append(tok)
        else:
            short.append(tok)
    return list(dict.fromkeys(fts)), list(dict.fromkeys(short))


class NoteStore:
    def __init__(self, db: Database):
        self.db = db

    def write(
        self,
        *,
        owner: str,
        scope: str,
        kind: str,
        text: str,
        sources: list[str],
        entities: list[str] | None = None,
        evidence: list[str] | None = None,
        claims: list[str] | None = None,
        code_version: str | None = None,
        task_id: str | None = None,
        pinned: bool = False,
        data_class: str | None = None,
    ) -> dict:
        note: dict = {
            "cd_schema": "cd.memory.note/0",
            "id": ids.new_id("mem"),
            "scope": scope,
            "owner": owner,
            "kind": kind,
            "text": text,
            "created_at": ids.now(),
            "sources": sources,
        }
        for key, value in (("entities", entities), ("evidence", evidence), ("claims", claims)):
            if value:
                note[key] = list(dict.fromkeys(value))
        if code_version:
            note["code_version"] = code_version
        if task_id:
            note["task_id"] = task_id
        if pinned:
            note["pinned"] = True
        if data_class:
            note["data_class"] = data_class
        errors = list(validator(SCHEMA).iter_errors(note))
        if errors:
            e = errors[0]
            raise MemoryError_(f"invalid note {'/'.join(map(str, e.absolute_path))}: {e.message}")
        inherited = self._check_sources(owner, sources)
        if inherited != "public" and data_class_rank(inherited) > data_class_rank(note.get("data_class", "public")):
            note["data_class"] = inherited  # a note is at least as sensitive as what it was derived from
        refs = " ".join(note.get("evidence", []) + note.get("claims", []) + sources)
        with self.db.tx() as c:
            cur = c.execute(
                "INSERT INTO notes (id, scope, owner, kind, task_id, created_at, pinned, doc) VALUES (?,?,?,?,?,?,?,?)",
                (note["id"], scope, owner, kind, task_id, note["created_at"], int(pinned), dumps(note)),
            )
            c.execute(
                "INSERT INTO notes_fts (rowid, text, entities, refs) VALUES (?,?,?,?)",
                (cur.lastrowid, text, " ".join(note.get("entities", [])), refs),
            )
            c.executemany("INSERT INTO note_entities (entity, note_rowid) VALUES (?,?)",
                          [(ent, cur.lastrowid) for ent in note.get("entities", [])])
        return note

    def _check_sources(self, owner: str, sources: list[str]) -> str:
        """Every source must exist, and a note source must be readable by the owner (its own or project-scoped), so a
        note can always be traced to its originals (ChatGPT review R6). Returns the strictest data class among them."""
        strictest = "public"
        for src in sources:
            if src.startswith("jrn_"):
                row = self.db.one("SELECT doc FROM journal WHERE id = ?", (src,))
                if row is None:
                    raise MemoryError_(f"source {src} is not in the journal")
                strictest = stricter(strictest, json.loads(row["doc"]).get("data", {}).get("data_class", "public"))
            else:
                src_note = self.get(src)
                if src_note is None:
                    raise MemoryError_(f"source {src} is not a stored note")
                if src_note["owner"] != owner and src_note["scope"] != "project":
                    raise MemoryError_(f"source {src} is another agent's private note")
                strictest = stricter(strictest, src_note.get("data_class", "public"))
        return strictest

    def get(self, note_id: str) -> dict | None:
        row = self.db.one("SELECT doc FROM notes WHERE id = ?", (note_id,))
        return json.loads(row["doc"]) if row else None

    def supersede(self, old_id: str, new_id: str) -> None:
        old = self.get(old_id)
        if old is None or self.get(new_id) is None:
            raise MemoryError_("both notes must exist")
        old["superseded_by"] = new_id
        with self.db.tx() as c:
            c.execute("UPDATE notes SET superseded_by = ?, doc = ? WHERE id = ?", (new_id, dumps(old), old_id))

    def _visible(self, reader: str, include_shared: bool) -> tuple[str, list]:
        if include_shared:
            return "(n.owner = ? OR n.scope = 'project')", [reader]
        return "n.owner = ?", [reader]

    def recall(self, query: str, *, reader: str, k: int = 8, include_shared: bool = True,
               related: Related | None = None, semantic: dict[str, float] | None = None,
               weights: RecallWeights = DEFAULT_WEIGHTS) -> list[Recalled]:
        """Notes visible to `reader` that best match `query`, are about a `related` entity, or are close
        in meaning (`semantic`: note id -> 0..1, from memory/vectors.py). Superseded notes are excluded.

        score = share of query terms the note contains + entity score (by coupling distance)
                + semantic score + claim score (by the cited claims' current status) + pinned bonus - summary penalty
        """
        fts_terms, short_terms = _terms(query)
        related = related or {}
        semantic = semantic or {}
        if not fts_terms and not short_terms and not related and not semantic:
            return []
        vis_sql, vis_params = self._visible(reader, include_shared)
        candidates: dict[str, dict] = {}
        limit = max(k * 8, 40)

        if fts_terms:
            match = " OR ".join('"' + t.replace('"', '""') + '"' for t in fts_terms)
            rows = self.db.query(
                f"""SELECT n.doc FROM notes_fts f JOIN notes n ON n.rowid = f.rowid
                    WHERE notes_fts MATCH ? AND n.superseded_by IS NULL AND {vis_sql}
                    ORDER BY bm25(notes_fts) LIMIT ?""",
                (match, *vis_params, limit),
            )
            for r in rows:
                doc = json.loads(r["doc"])
                candidates[doc["id"]] = doc
        for term in short_terms:
            like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            rows = self.db.query(
                f"""SELECT n.doc FROM notes n JOIN notes_fts f ON n.rowid = f.rowid
                    WHERE (f.text LIKE ? ESCAPE '\\' OR f.entities LIKE ? ESCAPE '\\')
                      AND n.superseded_by IS NULL AND {vis_sql}
                    ORDER BY n.rowid DESC LIMIT ?""",
                (like, like, *vis_params, limit),
            )
            for r in rows:
                doc = json.loads(r["doc"])
                candidates[doc["id"]] = doc

        ents = list(related)
        for i in range(0, len(ents), 500):  # stay under SQLite's bound-parameter limit
            chunk = ents[i : i + 500]
            rows = self.db.query(
                f"""SELECT DISTINCT n.rowid, n.doc FROM note_entities e JOIN notes n ON n.rowid = e.note_rowid
                    WHERE e.entity IN ({','.join('?' * len(chunk))}) AND n.superseded_by IS NULL AND {vis_sql}
                    ORDER BY n.rowid DESC LIMIT ?""",
                (*chunk, *vis_params, limit),
            )
            for r in rows:
                doc = json.loads(r["doc"])
                candidates[doc["id"]] = doc

        sem_ids = [i for i in semantic if i not in candidates]
        for i in range(0, len(sem_ids), 500):
            chunk = sem_ids[i : i + 500]
            rows = self.db.query(
                f"""SELECT n.doc FROM notes n WHERE n.id IN ({','.join('?' * len(chunk))})
                    AND n.superseded_by IS NULL AND {vis_sql}""", (*chunk, *vis_params))
            for r in rows:
                doc = json.loads(r["doc"])
                candidates[doc["id"]] = doc

        all_terms = fts_terms + short_terms
        states = self.claim_states([c for doc in candidates.values() for c in doc.get("claims", [])])
        scored = []
        for doc in candidates.values():
            # the claims it cites count too: a search for a conclusion's id finds the notes about it (Haiku check item 20)
            hay = (doc["text"] + " " + " ".join(doc.get("entities", [])) + " " + " ".join(doc.get("evidence", []))
                   + " " + " ".join(doc.get("claims", []))).lower()
            hits = sum(1 for t in all_terms if t in hay)
            near = [(related[e][0], e) for e in doc.get("entities", []) if e in related]
            meaning = semantic.get(doc["id"])
            if hits == 0 and not near and not meaning:
                continue
            score = hits / len(all_terms) if all_terms else 0.0
            via = None
            if near:
                dist, ent = min(near)
                score += weights.entity.get(dist, 0.1)
                if dist > 0:
                    via = related[ent][1]
            if meaning:
                score += weights.semantic * meaning
            cited = [states[c][0] for c in doc.get("claims", []) if c in states]
            if cited:
                score += sum(weights.claim.get(st, 0.0) for st in cited) / len(cited)
            score += (weights.pinned if doc.get("pinned") else 0.0) - (weights.summary_penalty if doc["kind"] == "summary" else 0.0)
            scored.append(Recalled(doc, round(score, 4), _flags(doc.get("claims", []), states), via, meaning))
        # equal scores: newest first; ids are monotonic ULIDs, so this holds within one millisecond too
        scored.sort(key=lambda r: (r.score, r.note["created_at"], r.note["id"]), reverse=True)
        return scored[:k]

    def claim_states(self, claim_ids: list[str]) -> dict[str, tuple[str, str]]:
        """claim id -> (current status, id of the claim that status belongs to).
        A superseded claim is followed to the claim that replaced it: that one's status is what counts now."""
        out: dict[str, tuple[str, str]] = {}
        for cid in dict.fromkeys(claim_ids):
            cur, seen = cid, set()
            while cur not in seen:
                seen.add(cur)
                row = self.db.one("SELECT status FROM claims WHERE id = ?", (cur,))
                if row is None:
                    break
                if row["status"] != "superseded":
                    out[cid] = (row["status"], cur)
                    break
                nxt = self.db.one("SELECT id FROM claims WHERE json_extract(doc, '$.supersedes') = ? "
                                  "ORDER BY created_at DESC LIMIT 1", (cur,))
                if nxt is None:
                    out[cid] = ("superseded", cur)
                    break
                cur = nxt["id"]
        return out

    def by_task(self, task_id: str) -> list[dict]:
        return [json.loads(r["doc"]) for r in self.db.query("SELECT doc FROM notes WHERE task_id = ? ORDER BY rowid", (task_id,))]

    def count(self) -> int:
        return self.db.one("SELECT COUNT(*) AS n FROM notes")["n"]


def note_data_class(note: dict, code_data_class: str) -> str:
    """A note is at least as sensitive as the project's code (its text is derived from it); notes written before
    data classes were recorded are not treated as public."""
    return stricter(note.get("data_class", "public"), code_data_class)


def allowed_notes(found: list, code_data_class: str, max_data_class: str) -> tuple[list, list, str]:
    """(notes that may go to an endpoint allowing max_data_class, notes withheld, strictest class of those kept)."""
    keep, withheld, strictest = [], [], "public"
    for r in found:
        dc = note_data_class(r.note, code_data_class)
        if data_class_rank(dc) > data_class_rank(max_data_class):
            withheld.append(r)
        else:
            keep.append(r)
            strictest = stricter(strictest, dc)
    return keep, withheld, strictest


def _flags(claim_ids: list[str], states: dict[str, tuple[str, str]]) -> list[str]:
    """One flag per status, e.g. 'REFUTED (disproven; do not rely on it): clm_1'. Claims that cannot be found are flagged too."""
    groups: dict[str, list[str]] = {}
    for cid in claim_ids:
        if cid not in states:
            groups.setdefault("CLAIM NOT FOUND", []).append(cid)
            continue
        status, final = states[cid]
        label = _FLAG.get(status, status.upper())
        groups.setdefault(label, []).append(cid if final == cid else f"{cid} (superseded by {final})")
    return [f"{label}: {', '.join(found[:8])}" + (f" and {len(found) - 8} more" if len(found) > 8 else "")
            for label, found in groups.items()]
