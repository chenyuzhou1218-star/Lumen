"""Memory recall bench (bench/scenarios/memory/*.json). Deterministic: no model is called.

A scenario replays a history into a fresh project copy - claims with real code evidence,
reviews, task ends (written by the same code the runtime uses), notes, code edits - and then
asks each probe question. Every probe runs under cumulative configurations, from the recall of
ADR 0003 to the current one, so the effect of each change is visible:

  before    ADR 0003: text match; claim status ignored; no per-claim notes
  m1        + claim status read live (warning flags, claim weights)
  m1_m3     + per-claim notes; summaries rank lower
  current   + coupling-graph expansion (M2)
  m6        + meaning (semantic recall, ADR 0007) - only with --embedding-config, which names the
            user's own configuration and so the embedding model they chose; otherwise not run

Per probe: recall@k (share of relevant groups with a note in the top k), reciprocal rank of
the first relevant note, unsafe (untrusted notes shown without a warning), trap_above
(untrusted notes ranked above the first relevant one) and leaks (forbidden notes shown).
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncio

from codedoctor import claim_rules, ids
from codedoctor.bench.common import BenchError, load, project_copy, scripted_config
from codedoctor.currency import snapshot_version, stale_notes
from codedoctor.memory import related, task_memory
from codedoctor.memory.notes import DEFAULT_WEIGHTS, Recalled, RecallWeights
from codedoctor.services import Services

K = 8  # the default recall_k: what an agent gets at the start of a task
WARNINGS = ("REFUTED", "STALE", "WITHDRAWN")


@dataclass(frozen=True)
class Config:
    id: str
    label: str
    weights: RecallWeights
    flags: bool        # M1: claim status shown
    claim_notes: bool  # M3: per-claim notes exist
    coupling: bool     # M2
    semantic: bool = False  # M6


CONFIGS = (
    Config("before", "ADR 0003（本批之前）", RecallWeights(claim={}, entity={}, summary_penalty=0.0), False, False, False),
    Config("m1", "+M1 主张状态", RecallWeights(entity={}, summary_penalty=0.0), True, False, False),
    Config("m1_m3", "+M3 按主张拆分", RecallWeights(entity={}), True, True, False),
    Config("current", "+M2 耦合回忆（当前）", DEFAULT_WEIGHTS, True, True, True),
)
M6 = Config("m6", "+M6 按意思回忆", DEFAULT_WEIGHTS, True, True, True, semantic=True)


class _History:
    def __init__(self, s: Services, root):
        self.s, self.root = s, root
        self.claims: dict[str, str] = {}
        self.notes: dict[str, str] = {}
        self.tasks: dict[str, str] = {}
        self.evidence: dict[str, str] = {}

    def task(self, alias: str) -> str:
        return self.tasks.setdefault(alias, ids.new_id("task"))

    def source(self, agent: str, task_alias: str | None = None) -> str:
        return self.s.journal.append(agent, "state_change", {"state": "idle"},
                                     task_id=self.task(task_alias) if task_alias else None)["id"]

    def apply(self, op: dict) -> None:
        getattr(self, "_" + op["op"])(op)

    def _build_graph(self, op: dict) -> None:
        self.s.graph.build()

    def _claim(self, op: dict) -> None:
        cite = op["cite"]
        ev_id, _ = self.s.evidence.add_code_excerpt(self.root, cite["path"], cite["lines"][0], cite["lines"][1], agent_id=op["author"])
        ref: dict = {"id": ev_id, "role": "supports", "shows": op["text"][:200]}
        if cite.get("contains"):
            ref["assert"] = [{"op": "text_contains", "text": cite["contains"]}]
        draft: dict = {
            "claim_type": op["type"], "evidence_level": op["level"],
            "statement": {"text": op["text"], "subject": op["subject"], "relation": op["relation"], "object": op["object"]},
            "scope": {"code_version": snapshot_version(self.root)}, "evidence": [ref],
            "falsification": {"method": "test", "intervention": True, "description": op["falsification"]},
        }
        if op.get("supersedes"):
            draft["supersedes"] = self.claims[op["supersedes"]]
        author = {"kind": "agent", "id": op["author"], "role": op.get("role", "worker"),
                  "model": {"provider": "scripted", "model": "bench"}, "task_id": self.task(op["task"])}
        self.claims[op["as"]] = self.s.claims.submit(draft, author=author)["id"]
        self.evidence[op["as"]] = ev_id

    def _review(self, op: dict) -> None:
        cid = self.claims[op["claim"]]
        if op["verdict"] == "reverified":
            evidence, expect = [self.evidence[op["claim"]]], "supported"
        else:
            evidence = [self.s.evidence.add_blob(op["proof"].encode("utf-8"), "text/plain", source="tool",
                                                 collected_by="bench/0", agent_id=op["by"])]
            expect = "refuted"
        self.s.claims.add_review(cid, reviewer=op["by"], verdict=op["verdict"], notes=op.get("proof", "re-checked"), evidence=evidence)
        got = claim_rules.evaluate(self.s, cid)["status"]
        if got != expect:
            raise BenchError(f"review of {op['claim']} should make it {expect}, it is {got}")

    def _task_end(self, op: dict) -> None:
        tid = self.task(op["as"])
        claims = [self.claims[c] for c in op["claims"]]
        task_memory.write(self.s, owner=op["owner"], task_id=tid, title=op["title"], outcome=op.get("outcome", "done"),
                          summary=op["summary"], evidence=[self.evidence[c] for c in op["claims"]], claims=claims,
                          source=self.source(op["owner"], op["as"]))

    def _note(self, op: dict) -> None:
        self.notes[op["as"]] = self.s.notes.write(
            owner=op["owner"], scope=op.get("scope", "project"), kind=op["kind"], text=op["text"],
            entities=op.get("entities"), pinned=op.get("pinned", False), sources=[self.source(op["owner"])],
            # what `remember` produces: the note cites the evidence, it cannot cite the claim
            evidence=[self.evidence[op["evidence_of"]]] if op.get("evidence_of") else None)["id"]

    def _edit(self, op: dict) -> None:
        path = self.root / op["path"]
        text = path.read_bytes().decode("utf-8")  # bytes, not text mode: Windows would rewrite every line ending
        if text.count(op["old"]) != 1:
            raise BenchError(f"edit of {op['path']}: {op['old']!r} must occur exactly once")
        path.write_bytes(text.replace(op["old"], op["new"]).encode("utf-8"))
        claim_rules.refresh_all(self.s)

    # --- reading results back -----------------------------------------------------------------

    def matches(self, selector: str, note: dict) -> bool:
        kind, alias = selector.split(":", 1)
        if kind == "note":
            return note["id"] == self.notes[alias]
        if kind == "claim":
            return note["kind"] == "claim" and note.get("claims") == [self.claims[alias]]
        if kind == "summary":
            return note["kind"] == "summary" and note.get("task_id") == self.tasks[alias]
        raise BenchError(f"unknown selector {selector!r}")

    def label(self, note: dict) -> str:
        for alias, nid in self.notes.items():
            if note["id"] == nid:
                return f"note:{alias}"
        for alias in self.claims:
            if self.matches(f"claim:{alias}", note):
                return f"claim:{alias}"
        for alias, tid in self.tasks.items():
            if note["kind"] == "summary" and note.get("task_id") == tid:
                return f"summary:{alias}"
        return note["id"]

    def aliased(self, text: str) -> str:
        """Claim ids replaced by their scenario aliases, so results do not change from run to run."""
        for alias, cid in self.claims.items():
            text = text.replace(cid, alias)
        return text


def _probe(s: Services, h: _History, probe: dict, cfg: Config) -> dict:
    k = probe.get("k", K)
    reader = probe.get("reader", "doctor")
    if cfg.semantic:
        found: list[Recalled] = asyncio.run(related.recall_async(s, probe["query"], reader=reader, k=k, weights=cfg.weights,
                                                                 data_class=s.config.code_data_class))
    else:
        found = related.recall(s, probe["query"], reader=reader, k=k if cfg.claim_notes else k * 4,
                               follow_coupling=cfg.coupling, weights=cfg.weights)
    if not cfg.claim_notes:  # before M3 these notes did not exist
        found = [r for r in found if r.note["kind"] != "claim"]
    found = found[:k]
    stale = stale_notes(s, [r.note for r in found])  # code-excerpt staleness existed before this batch

    def warned(r: Recalled) -> bool:
        return r.note["id"] in stale or (cfg.flags and any(f.startswith(WARNINGS) for f in r.flags))

    def is_any(selectors: list[str], r: Recalled) -> bool:
        return any(h.matches(sel, r.note) for sel in selectors)

    groups = probe.get("relevant", [])
    first = next((i + 1 for i, r in enumerate(found) if any(is_any(g, r) for g in groups)), None)
    untrusted = [i for i, r in enumerate(found) if is_any(probe.get("untrusted", []), r)]
    return {
        "id": probe["id"], "lang": probe.get("lang"), "query": probe["query"],
        "recall": sum(any(is_any(g, r) for r in found) for g in groups) / len(groups) if groups else None,
        "rr": (1 / first if first else 0.0) if groups else None,
        "unsafe": sum(1 for i in untrusted if not warned(found[i])),
        "trap_above": sum(1 for i in untrusted if first is None or i + 1 < first),
        "leaks": sum(1 for r in found if is_any(probe.get("forbidden", []), r)),
        "top": [{"rank": i + 1, "note": h.label(r.note), "score": r.score, "warned": warned(r),
                 **({"flags": [h.aliased(f) for f in r.flags]} if cfg.flags and r.flags else {}),
                 **({"via": r.via} if cfg.coupling and r.via else {}),
                 **({"meaning": r.meaning} if cfg.semantic and r.meaning else {})}
                for i, r in enumerate(found)],
    }


def summarize(probes: list[dict]) -> dict:
    scored = [p for p in probes if p["recall"] is not None]
    return {
        "probes": len(probes),
        "recall_at_k": round(sum(p["recall"] for p in scored) / len(scored), 3) if scored else None,
        "mrr": round(sum(p["rr"] for p in scored) / len(scored), 3) if scored else None,
        "unsafe": sum(p["unsafe"] for p in probes),
        "trap_above": sum(p["trap_above"] for p in probes),
        "leaks": sum(p["leaks"] for p in probes),
        "perfect": sum(1 for p in probes if p["recall"] in (None, 1.0) and p["rr"] in (None, 1.0)
                       and not p["unsafe"] and not p["leaks"]),
    }


def run_scenario(scenario: dict, configs: tuple[Config, ...] = CONFIGS, embedding_from=None) -> dict:
    with project_copy(scenario) as (root, data):
        cfg = scripted_config(root, data, scenario["name"], [{"id": "doctor", "role": "general", "endpoint": "bench", "model": "bench"}],
                              embedding_from)
        s = Services.open(cfg)
        try:
            h = _History(s, root)
            for op in scenario["history"]:
                h.apply(op)
            out = {"id": scenario["id"], "claims": {a: s.claims.get(c)["status"] for a, c in h.claims.items()}, "configs": {}}
            if embedding_from is not None:
                asyncio.run(_index_all(s))
                out["embedding"] = {"model": s.vectors.key, **s.vectors.count(), "error": s.vectors.last_error}
            for c in configs:
                probes = [_probe(s, h, p, c) for p in scenario["probes"]]
                out["configs"][c.id] = {"summary": summarize(probes), "probes": probes}
            return out
        finally:
            s.db.close()


async def _index_all(s: Services) -> None:
    while await s.vectors.index_pending():
        pass


def run(scenarios_dir=None, embedding_from=None) -> dict:
    """`embedding_from`: the user's configuration with memory.embedding set; adds the M6 configuration."""
    configs = CONFIGS + ((M6,) if embedding_from is not None else ())
    scenarios = [run_scenario(sc, configs, embedding_from) for sc in load("memory", scenarios_dir)]
    return {
        "configs": [{"id": c.id, "label": c.label} for c in configs],
        "not_run": [] if embedding_from is not None else [{"id": M6.id, "label": M6.label,
                                                           "why": "没有指定嵌入模型（用 --embedding-config 指向你的配置文件）"}],
        "scenarios": scenarios,
        "summary": {c.id: summarize([p for sc in scenarios for p in sc["configs"][c.id]["probes"]]) for c in configs},
    }
