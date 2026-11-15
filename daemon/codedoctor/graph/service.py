"""Coupling graph of the configured project: build, persist, refresh, and merge in the
relations agents have claimed (inferred) or proven (verified)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from codedoctor import ids
from codedoctor.currency import snapshot_version
from codedoctor.graph import risks as risk_mod
from codedoctor.graph.build import build
from codedoctor.graph.model import Edge, Graph, Node
from codedoctor.store.db import dumps

CLAIM_RELS = {"calls", "handles", "reads", "writes", "emits", "consumes", "triggers", "renders", "depends_on",
              "shares_state_with", "precedes", "causes", "may_cause", "affects", "violates"}
LIVE_CLAIM_STATUS = {"proposed": "inferred", "supported": "verified"}


def edge_doc(e: Edge, code_version: str) -> dict:
    doc = {"cd_schema": "cd.graph.edge/0", "src": e.src, "rel": e.rel, "dst": e.dst, "provenance": e.provenance,
           "code_version": code_version}
    if e.resolution:
        doc["resolution"] = e.resolution
    if e.path:
        doc["location"] = {"path": e.path, "line": e.line or 1}
    if e.claim:
        doc["claim"] = e.claim
    return doc


class GraphService:
    def __init__(self, services):
        self.s = services
        self._lock = threading.Lock()
        self._cache: tuple[str, Graph] | None = None  # (build id, static graph)

    # --- build ----------------------------------------------------------------------------

    def meta(self) -> dict:
        return {r["key"]: json.loads(r["value"]) for r in self.s.db.query("SELECT key, value FROM graph_meta")}

    def build(self) -> dict:
        """Parse the whole project again. Takes seconds for a few hundred files."""
        with self._lock:
            root = Path(self.s.config.root)
            version = snapshot_version(root)
            g, info = build(root, self.s.config.name)
            found = risk_mod.detect(g, version)
            build_id = ids.new_id("bld")
            with self.s.db.tx() as c:
                c.execute("DELETE FROM graph_nodes")
                c.execute("DELETE FROM graph_edges")
                c.execute("DELETE FROM graph_risks")
                c.executemany("INSERT INTO graph_nodes (id, type, doc) VALUES (?,?,?)",
                              [(n.id, n.type, dumps({"name": n.name, "path": n.path, "line": n.line, "attrs": n.attrs}))
                               for n in g.nodes.values()])
                c.executemany("INSERT INTO graph_edges (src, rel, dst, provenance, doc) VALUES (?,?,?,?,?)",
                              [(e.src, e.rel, e.dst, e.provenance, dumps(edge_doc(e, version))) for e in g.edges])
                c.executemany("INSERT INTO graph_risks (id, severity, pattern, rank, doc) VALUES (?,?,?,?,?)",
                              [(r["id"], r["severity"], r["pattern"], i, dumps(r)) for i, r in enumerate(found)])
                summary = {"build_id": build_id, "code_version": version, "built_at": ids.now(), **info,
                           "stats": g.stats(), "risks": len(found)}
                for k, v in summary.items():
                    c.execute("INSERT INTO graph_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                              (k, json.dumps(v, ensure_ascii=False)))
            self._cache = (build_id, g)
            return summary

    def ensure_built(self, rebuild_if_changed: bool = True) -> dict:
        meta = self.meta()
        if not meta:
            return self.build()
        if rebuild_if_changed and meta.get("code_version") != snapshot_version(Path(self.s.config.root)):
            return self.build()
        return meta

    # --- read -----------------------------------------------------------------------------

    def _static(self) -> Graph:
        meta = self.ensure_built(rebuild_if_changed=False)
        if self._cache and self._cache[0] == meta["build_id"]:
            return self._cache[1]
        g = Graph()
        for r in self.s.db.query("SELECT id, type, doc FROM graph_nodes"):
            d = json.loads(r["doc"])
            g.add_node(Node(r["id"], r["type"], d["name"], d["path"], d["line"], d["attrs"]))
        for r in self.s.db.query("SELECT doc FROM graph_edges ORDER BY seq"):
            d = json.loads(r["doc"])
            loc = d.get("location") or {}
            g.add_edge(Edge(d["src"], d["rel"], d["dst"], d["provenance"], d.get("resolution"), loc.get("path"), loc.get("line"),
                            d.get("claim")))
        self._cache = (meta["build_id"], g)
        return g

    def graph(self) -> Graph:
        """Static graph plus edges from live claims (proposed -> inferred, supported -> verified)."""
        static = self._static()
        claim_edges = []
        for r in self.s.db.query("SELECT doc FROM claims WHERE status IN ('proposed', 'supported')"):
            c = json.loads(r["doc"])
            st = c["statement"]
            if st["relation"] in CLAIM_RELS and isinstance(st["object"], str):
                claim_edges.append(Edge(st["subject"], st["relation"], st["object"], LIVE_CLAIM_STATUS[c["status"]], claim=c["id"]))
        if not claim_edges:
            return static
        g = Graph(dict(static.nodes), list(static.edges))
        for e in claim_edges:
            g.add_edge(e)
        return g

    def risks(self, limit: int = 30, pattern: str | None = None, min_severity: str = "low") -> list[dict]:
        self.ensure_built(rebuild_if_changed=False)
        order = {"high": 0, "medium": 1, "low": 2}
        allowed = [k for k, v in order.items() if v <= order[min_severity]]
        sql = f"SELECT doc FROM graph_risks WHERE severity IN ({','.join('?' * len(allowed))})"
        params: list = list(allowed)
        if pattern:
            sql += " AND pattern = ?"
            params.append(pattern)
        return [json.loads(r["doc"]) for r in self.s.db.query(sql + " ORDER BY rank LIMIT ?", (*params, limit))]

    def risk_counts(self) -> dict:
        rows = self.s.db.query("SELECT pattern, severity, COUNT(*) AS n FROM graph_risks GROUP BY pattern, severity")
        return {f"{r['pattern']}/{r['severity']}": r["n"] for r in rows}
