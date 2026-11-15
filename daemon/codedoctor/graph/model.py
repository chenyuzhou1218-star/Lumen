"""In-memory coupling graph and the queries the agents use.

Nodes are canonical entity ids (schemas/claim/entity-ref). Edges carry their
provenance (static / runtime / inferred / verified) and, for static edges, the
exact source location. Queries never hide provenance: every path they return
lists the edges it walked.
"""

from __future__ import annotations

import heapq
import re
from collections import defaultdict
from dataclasses import dataclass, field

_KEEP = re.compile(r"[A-Za-z0-9_$.<>~-]")

# Direction in which effects flow along each relation, for "what does X affect".
FORWARD = {"calls", "handles", "writes", "emits", "consumes", "triggers", "renders", "causes", "may_cause", "affects"}
# 'reads' flows from state to reader: a change to the state affects whoever reads it.
STATE_TO_READER = {"reads"}


def encode_name(text: str) -> str:
    """Percent-encode everything outside the entity-id name alphabet (keeps ids schema-valid for any language)."""
    return "".join(ch if _KEEP.fullmatch(ch) else "".join(f"%{b:02X}" for b in ch.encode("utf-8")) for ch in text)


def encode_path(path: str) -> str:
    return "".join(ch if not (ch.isspace() or ch in ":#@\\%") else "".join(f"%{b:02X}" for b in ch.encode("utf-8")) for ch in path)


def encode_free(text: str) -> str:
    """For event / message / state names: only whitespace and ':' are reserved."""
    return "".join(ch if not (ch.isspace() or ch in ":%") else "".join(f"%{b:02X}" for b in ch.encode("utf-8")) for ch in text)


class Ids:
    def __init__(self, service: str):
        self.svc = service

    def file(self, path: str) -> str:
        return f"ent:file:{self.svc}:{encode_path(path)}"

    def symbol(self, path: str, qualname: str) -> str:
        return f"ent:symbol:{self.svc}:{encode_path(path)}#{encode_name(qualname)}"

    def route(self, method: str, path: str) -> str:
        return f"ent:route:{self.svc}:{method.upper()}:{path}"

    def event(self, name: str) -> str:
        return f"ent:event:{self.svc}:{encode_free(name)[:256]}"

    def ws_msg(self, name: str) -> str:
        return f"ent:ws_msg:{self.svc}:{encode_free(name)[:256]}"

    def state(self, attr: str, language: str) -> str:
        """In-memory state is scoped by language: a Python server and a JS client never share memory,
        even when both have a field called `gold`. Database tables are shared and are not scoped."""
        store = {"python": "py", "javascript": "js"}.get(language, language)
        return f"ent:state:{self.svc}:{store}/{encode_free(attr)[:512]}"

    def table(self, name: str) -> str:
        return f"ent:table:main:{name}"


@dataclass
class Node:
    id: str
    type: str
    name: str
    path: str | None = None
    line: int | None = None
    attrs: dict = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    rel: str
    dst: str
    provenance: str = "static"
    resolution: str | None = None
    path: str | None = None
    line: int | None = None
    claim: str | None = None

    def key(self) -> tuple:
        return (self.src, self.rel, self.dst, self.provenance)

    def describe(self) -> str:
        loc = f" @ {self.path}:{self.line}" if self.path else ""
        how = f", {self.resolution}" if self.resolution else ""
        via = f", claim {self.claim}" if self.claim else ""
        return f"{self.src} -[{self.rel}]-> {self.dst}  ({self.provenance}{how}{via}){loc}"


def node_type(entity: str) -> str:
    return entity.split(":", 2)[1]


class Graph:
    def __init__(self, nodes: dict[str, Node] | None = None, edges: list[Edge] | None = None):
        self.nodes: dict[str, Node] = nodes or {}
        self.edges: list[Edge] = []
        self._seen: set[tuple] = set()
        self.out: dict[str, list[Edge]] = defaultdict(list)
        self.inc: dict[str, list[Edge]] = defaultdict(list)
        for e in edges or []:
            self.add_edge(e)

    def add_node(self, node: Node) -> None:
        cur = self.nodes.get(node.id)
        if cur is None:
            self.nodes[node.id] = node
            return
        # The node may have been created as a bare edge endpoint before its definition was seen.
        if cur.path is None and node.path is not None:
            cur.path, cur.line, cur.name = node.path, node.line, node.name
        for k, v in node.attrs.items():
            cur.attrs.setdefault(k, v)

    def ensure(self, entity: str, name: str | None = None) -> None:
        if entity not in self.nodes:
            self.nodes[entity] = Node(entity, node_type(entity), name or entity.rsplit(":", 1)[-1])

    def add_edge(self, e: Edge) -> None:
        if e.key() in self._seen:
            return
        self._seen.add(e.key())
        self.ensure(e.src)
        self.ensure(e.dst)
        self.edges.append(e)
        self.out[e.src].append(e)
        self.inc[e.dst].append(e)

    # --- lookup -------------------------------------------------------------------------

    def find(self, text: str, limit: int = 30) -> list[Node]:
        t = text.lower()
        hits = [n for n in self.nodes.values() if t in n.id.lower() or t in n.name.lower() or (n.path and t in n.path.lower())]
        hits.sort(key=lambda n: (n.type not in ("symbol", "route", "state", "event"), len(n.id)))
        return hits[:limit]

    def resolve(self, text: str) -> Node | None:
        if text in self.nodes:
            return self.nodes[text]
        hits = self.find(text, 1)
        return hits[0] if hits else None

    # --- traversal --------------------------------------------------------------------

    def _steps(self, entity: str, direction: str) -> list[tuple[str, Edge]]:
        """Neighbours along which an effect propagates. direction: 'down' = what this affects, 'up' = what affects this.
        Ambiguous name matches are not followed: they would spread effects to unrelated same-named functions."""
        steps = []
        if direction == "down":
            for e in self.out.get(entity, []):
                if e.rel in FORWARD and e.resolution != "ambiguous":
                    steps.append((e.dst, e))
            for e in self.inc.get(entity, []):  # state -> its readers
                if e.rel in STATE_TO_READER:
                    steps.append((e.src, e))
        else:
            for e in self.inc.get(entity, []):
                if e.rel in FORWARD and e.resolution != "ambiguous":
                    steps.append((e.src, e))
            for e in self.out.get(entity, []):
                if e.rel in STATE_TO_READER:
                    steps.append((e.dst, e))
        return steps

    def reach(self, entity: str, direction: str, max_depth: int = 6) -> dict[str, tuple[int, list[Edge]]]:
        """Shortest path (by hops) to every reachable entity: {entity: (distance, edges on the path)}."""
        best: dict[str, tuple[int, list[Edge]]] = {entity: (0, [])}
        heap = [(0, entity)]
        while heap:
            d, cur = heapq.heappop(heap)
            if d > best[cur][0] or d >= max_depth:
                continue
            for nxt, e in self._steps(cur, direction):
                if nxt not in best or d + 1 < best[nxt][0]:
                    best[nxt] = (d + 1, best[cur][1] + [e])
                    heapq.heappush(heap, (d + 1, nxt))
        return best

    def impact(self, entity: str, max_depth: int = 4) -> dict:
        return {"affects": self.reach(entity, "down", max_depth), "affected_by": self.reach(entity, "up", max_depth)}

    def common_cause(self, symptoms: list[str], max_depth: int = 6) -> list[dict]:
        """Entities that every (or most) symptom depends on (downstream) or that feed into them (upstream).
        Ranked by how many symptoms they explain, then by total distance; shared state and tables first on ties."""
        per: list[tuple[str, dict]] = []
        for s in symptoms:
            down = self.reach(s, "down", max_depth)
            up = self.reach(s, "up", max_depth)
            merged = {**up, **down}
            for k in set(up) & set(down):
                merged[k] = min(up[k], down[k], key=lambda x: x[0])
            per.append((s, merged))
        counts: dict[str, list[tuple[str, int, list[Edge]]]] = defaultdict(list)
        for s, reached in per:
            for ent, (d, path) in reached.items():
                if ent not in symptoms:
                    counts[ent].append((s, d, path))
        prio = {"state": 0, "table": 0, "column": 0, "symbol": 1, "ws_msg": 2, "event": 2, "route": 3, "file": 9}
        ranked = []
        for ent, hits in counts.items():
            if len(hits) < 2 and len(symptoms) > 1:
                continue
            t = node_type(ent)
            if t == "file":
                continue
            ranked.append({
                "entity": ent,
                "explains": len(hits),
                "of": len(symptoms),
                "total_distance": sum(h[1] for h in hits),
                "paths": {h[0]: [e.describe() for e in h[2]] for h in hits},
                "_order": (-len(hits), prio.get(t, 5), sum(h[1] for h in hits)),
            })
        ranked.sort(key=lambda r: r["_order"])
        for r in ranked:
            r.pop("_order")
        return ranked

    def entry_points(self) -> list[str]:
        """Where work starts: route handlers, event / message consumers, module top levels."""
        entries = set()
        for e in self.edges:
            if e.rel in ("handles", "consumes"):
                entries.add(e.dst)
        return sorted(entries)

    def stats(self) -> dict:
        by_type: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            by_type[n.type] += 1
        by_prov: dict[str, int] = defaultdict(int)
        for e in self.edges:
            by_prov[e.provenance] += 1
        return {"nodes": len(self.nodes), "edges": len(self.edges), "node_types": dict(by_type), "edge_provenance": dict(by_prov)}
