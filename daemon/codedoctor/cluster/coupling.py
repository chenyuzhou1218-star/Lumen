"""Typed influence paths. A shared dependency is a lead, never causal proof."""
from __future__ import annotations

from collections import defaultdict, deque

from codedoctor.cluster.contracts import BusinessError


def influence(edge):
    if edge.resolution == "ambiguous" or edge.provenance == "inferred" or edge.rel in {"causes", "may_cause"}:
        return None
    if edge.rel in {"calls", "depends_on", "handles", "reads"}:
        return edge.dst, edge.src
    if edge.rel in {"writes", "emits", "consumes", "triggers", "renders"}:
        return edge.src, edge.dst
    return None


def blast_radius(graph, origin: str, *, max_nodes=10000, depth=10000):
    """A linear-space influence tree, with explicit coverage limits, not all paths."""
    if origin not in graph.nodes or type(max_nodes) is not int or type(depth) is not int or not 1 <= max_nodes <= 50000 or not 1 <= depth <= 50000:
        raise BusinessError("exact origin and bounded integer traversal limits required")
    outgoing = defaultdict(list)
    excluded = 0
    for edge in graph.edges:
        direction = influence(edge)
        if direction is None:
            excluded += 1
            continue
        source, target = direction
        if source in graph.nodes and target in graph.nodes:
            outgoing[source].append((target, edge))
    queue, seen, tree, truncated = deque([(origin, 0)]), {origin}, [], False
    while queue:
        current, distance = queue.popleft()
        for target, edge in outgoing[current]:
            if target in seen:
                continue
            if distance >= depth or len(seen) >= max_nodes:
                truncated = True
                continue
            seen.add(target)
            tree.append({"entity": target, "via": current, "distance": distance + 1, "relation": edge.rel,
                         "provenance": edge.provenance, "path": edge.path, "line": edge.line})
            queue.append((target, distance + 1))
    return {"origin": origin, "affected": tree, "affected_count": len(tree), "truncated": truncated,
            "excluded_edges": excluded, "scope": "typed_structural_influence_tree_not_all_execution_paths",
            "causality_proven": False}


def candidates(graph, symptoms: list[str], *, depth: int = 8, max_nodes: int = 5000) -> dict:
    if not 1 <= depth <= 16 or not 1 <= max_nodes <= 50000 or not 1 <= len(symptoms) <= 32:
        raise BusinessError("invalid coupling traversal budget")
    if len(set(symptoms)) != len(symptoms) or any(s not in graph.nodes for s in symptoms):
        raise BusinessError("symptoms must be distinct exact graph entity ids; ambiguous names are not resolved")
    incoming = defaultdict(list)
    skipped = []
    for edge in graph.edges:
        direction = influence(edge)
        if direction is None:
            skipped.append(edge.describe())
            continue
        source, target = direction
        incoming[target].append((source, {"from": source, "to": target, "relation": edge.rel,
                                         "provenance": edge.provenance, "path": edge.path, "line": edge.line}))
    per, truncated = {}, False
    for symptom in symptoms:
        seen, queue = {symptom: []}, deque([symptom])
        while queue:
            current = queue.popleft()
            path = seen[current]
            for parent, hop in incoming[current]:
                if parent in seen:
                    continue
                if len(path) >= depth or len(seen) >= max_nodes:
                    truncated = True
                    continue
                seen[parent] = [hop, *path]
                queue.append(parent)
        per[symptom] = seen
    ranked = []
    for entity in set().union(*(set(v) for v in per.values())) - set(symptoms):
        paths = {s: reached[entity] for s, reached in per.items() if entity in reached}
        if len(paths) < min(2, len(symptoms)):
            continue
        ranked.append({"entity": entity, "coverage": len(paths), "of": len(symptoms), "paths": paths,
                       "distance": sum(len(p) for p in paths.values()), "classification": "structural_candidate"})
    ranked.sort(key=lambda row: (-row["coverage"], row["distance"], row["entity"]))
    return {"candidates": ranked, "truncated": truncated, "excluded_uncertain_edges": skipped,
            "causality_proven": False}
