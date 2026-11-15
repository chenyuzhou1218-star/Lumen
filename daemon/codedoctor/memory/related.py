"""Coupling-aware recall (docs/adr/0006, M2).

A task rarely names every module it touches: memory about the wallet matters to
a question about the shop when the shop calls the wallet. So before recall, the
identifiers and paths the query mentions are mapped onto coupling-graph entities
(seeds), and the graph is walked a short way in both directions. Notes about any
entity reached are recalled, each with the edges that reached it.

Only a graph that already exists is used; recall never starts a build. A name
matching more than MAX_PER_TOKEN entities is skipped as ambiguous, so a common
word does not pull in half the project.
"""

from __future__ import annotations

import re

from codedoctor.graph.model import Edge, Graph
from codedoctor.memory.notes import DEFAULT_WEIGHTS, Recalled, RecallWeights, Related
from codedoctor.memory.vectors import VectorUnavailable

DEPTH = 2              # coupling hops followed from each seed, in each direction
MAX_PER_TOKEN = 4      # a name matching more entities than this is ambiguous and skipped
MAX_FILE_SYMBOLS = 30  # a file is coupled through what it defines; at most this many of its symbols become seeds
MAX_RELATED = 200
MAX_TOKENS = 400       # distinct words of a query looked up in the graph (a foresight brief has thousands)

_TOKEN = re.compile(r"ent:[a-z_]+:[^\s,;()'\"<>，。；：（）、]+|[A-Za-z0-9_$][A-Za-z0-9_$-]*(?:[./#\\][A-Za-z0-9_$-]+)*")
_PATHLIKE = re.compile(r"/|\.(py|pyi|js|jsx|ts|tsx|mjs|cjs|vue)$", re.I)


def _short(entity: str) -> str:
    return entity.rsplit("#", 1)[-1] if "#" in entity else entity.rsplit(":", 1)[-1]


def _describe(path: list[Edge]) -> str:
    return ", ".join(f"{_short(e.src)} -{e.rel}-> {_short(e.dst)}" + ("" if e.provenance == "static" else f" ({e.provenance})")
                     for e in path)


class _Index:
    """Lookups for _resolve, built once per graph. Scanning every node for every word of a long query (foresight
    passes several kilobytes) took seconds on a large project and, holding the GIL, froze the desktop window."""

    def __init__(self, g: Graph):
        self.by_name: dict[str, list[str]] = {}    # 'buy', 'shop.buy', 'pkg.shop.buy' -> non-file entities
        self.files: dict[str, list[str]] = {}      # 'shop.py', 'server/shop.py' -> file entities
        self.symbols: dict[str, list] = {}         # exact lower path -> symbol nodes defined there
        for n in g.nodes.values():
            if n.type == "file":
                parts = (n.path or "").lower().split("/")
                for i in range(len(parts)):
                    self.files.setdefault("/".join(parts[i:]), []).append(n.id)
                continue
            parts = n.name.lower().split(".")
            for i in range(len(parts)):
                self.by_name.setdefault(".".join(parts[i:]), []).append(n.id)
            if n.type == "symbol":
                self.symbols.setdefault((n.path or "").lower(), []).append(n)


_CACHE: dict = {"first": None, "size": -1, "index": None}


def _index(g: Graph) -> _Index:
    # graph() returns a new Graph when live claims add edges, but over the same node objects: key on those
    # (the node itself is kept, so its identity cannot be reused by a later graph)
    first = next(iter(g.nodes.values()), None)
    if _CACHE["first"] is not first or _CACHE["size"] != len(g.nodes) or _CACHE["index"] is None:
        _CACHE.update(first=first, size=len(g.nodes), index=_Index(g))
    return _CACHE["index"]


def _resolve(g: Graph, token: str) -> list[str]:
    if token in g.nodes:
        return [token]
    idx = _index(g)
    low = token.lower().replace("\\", "/")
    name = None
    if "#" in low:
        low, name = low.split("#", 1)
    if name is None and not _PATHLIKE.search(low):
        hits = idx.by_name.get(low, [])
        return list(hits) if len(hits) <= MAX_PER_TOKEN else []
    files = idx.files.get(low, [])  # the path is the file's path, or ends with '/' + it
    if name is not None:
        hits = [n.id for f in files for n in idx.symbols.get((g.nodes[f].path or "").lower(), [])
                if n.name.lower() == name or n.name.lower().endswith("." + name)]
        return hits if len(hits) <= MAX_PER_TOKEN else []
    if len(files) > MAX_PER_TOKEN:
        return []
    out = list(files)
    for f in files:
        out += [n.id for n in idx.symbols.get((g.nodes[f].path or "").lower(), [])][:MAX_FILE_SYMBOLS]
    return out


def seeds(g: Graph, text: str) -> dict[str, str]:
    """Entities the text names: {entity: the word that named it}."""
    out: dict[str, str] = {}
    tokens = list(dict.fromkeys(m.group(0).rstrip(".-") for m in _TOKEN.finditer(text)))[:MAX_TOKENS]
    for token in tokens:
        if len(token) < 3 or token.replace(".", "").isdigit():
            continue
        for ent in _resolve(g, token):
            out.setdefault(ent, token)
    return out


def expand(g: Graph, seed_map: dict[str, str], depth: int = DEPTH) -> Related:
    """Every entity within `depth` coupling hops of a seed, upstream or downstream, with the shortest path to it."""
    out: Related = {}

    def keep(ent: str, dist: int, why: str) -> None:
        if ent not in out or dist < out[ent][0]:
            out[ent] = (dist, why)

    for seed, token in seed_map.items():
        keep(seed, 0, f"named in the query as '{token}'")
        for direction in ("down", "up"):
            for ent, (dist, path) in g.reach(seed, direction, depth).items():
                if dist:
                    keep(ent, dist, f"{'affected by' if direction == 'down' else 'affects'} '{token}': {_describe(path)}")
    if len(out) > MAX_RELATED:
        out = dict(sorted(out.items(), key=lambda kv: kv[1][0])[:MAX_RELATED])
    return out


def coupled(services, text: str) -> Related:
    """Related entities for `text`, or {} when there is no graph yet or it cannot be read."""
    try:
        if not services.graph.meta():
            return {}
        g = services.graph.graph()
    except Exception:  # recall must keep working on text alone if the graph is unusable
        return {}
    return expand(g, seeds(g, text))


def recall(services, query: str, *, reader: str, k: int = 8, include_shared: bool = True,
           follow_coupling: bool = True, weights: RecallWeights = DEFAULT_WEIGHTS) -> list[Recalled]:
    """Text and coupling recall (no model call)."""
    related = coupled(services, query) if follow_coupling else None
    return services.notes.recall(query, reader=reader, k=k, include_shared=include_shared, related=related, weights=weights)


async def recall_async(services, query: str, *, reader: str, data_class: str, k: int = 8, include_shared: bool = True,
                       follow_coupling: bool = True, weights: RecallWeights = DEFAULT_WEIGHTS) -> list[Recalled]:
    """Text, coupling and - when the user configured an embedding model - meaning (ADR 0007).
    `data_class` is the sensitivity of the query: it is sent for embedding only where that is allowed.
    If the embedding endpoint fails, recall carries on with text and coupling (services.vectors.last_error says why)."""
    try:  # Haiku check item 15: a conclusion whose code changed is stale before it is shown as verified, not only at start-up
        from codedoctor import claim_rules

        claim_rules.refresh_all(services)
    except Exception:  # recall itself must not fail because the staleness check did
        pass
    semantic = None
    if services.vectors.enabled:
        try:
            semantic = await services.vectors.search(query, reader=reader, include_shared=include_shared, data_class=data_class)
        except VectorUnavailable:
            semantic = None
    related = coupled(services, query) if follow_coupling else None
    return services.notes.recall(query, reader=reader, k=k, include_shared=include_shared, related=related,
                                 semantic=semantic, weights=weights)
