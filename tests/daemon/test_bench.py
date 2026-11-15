"""The bench itself: it runs, it is deterministic, and its scoring says what the scenarios were
built to show. Scores that later work is meant to change (catch rate, unsafe recalls under the
current config) are deliberately not pinned here; bench/results/ records them."""

from __future__ import annotations

import json

import pytest

from codedoctor import cli
from codedoctor.bench import memory, reasoning
from codedoctor.bench import run as bench_run


@pytest.fixture(scope="module")
def mem():
    return memory.run()


@pytest.fixture(scope="module")
def rea():
    return reasoning.run()


def test_memory_history_is_set_up_as_described(mem):
    [sc] = mem["scenarios"]
    assert sc["claims"] == {"c1": "supported", "c2": "refuted", "c3": "supported", "c4": "superseded",
                            "c5": "supported", "c6": "needs_revalidation"}


def test_memory_scores_are_well_formed_and_private_notes_never_leak(mem):
    for cfg in mem["configs"]:
        s = mem["summary"][cfg["id"]]
        assert s["leaks"] == 0
        assert 0 <= s["recall_at_k"] <= 1 and 0 <= s["mrr"] <= 1


def test_memory_bench_sees_the_changes_it_was_built_to_measure(mem):
    before, current = mem["summary"]["before"], mem["summary"]["current"]
    assert current["recall_at_k"] >= before["recall_at_k"] and current["mrr"] > before["mrr"]
    probes = {p["id"]: p for p in mem["scenarios"][0]["configs"]["current"]["probes"]}
    assert probes["p1"]["top"][0]["note"] == "claim:c3"            # the verified finding, not the long summary
    assert any(t["note"] == "claim:c2" and t["warned"] for t in probes["p1"]["top"])  # refuted lead shown flagged
    assert mem["summary"]["before"]["unsafe"] >= 1                 # the metric does fire when nothing warns


def test_memory_bench_is_deterministic(mem):
    assert json.dumps(memory.run(), sort_keys=True) == json.dumps(mem, sort_keys=True)


def test_static_reasoning_finds_all_planted_defects(rea):
    [st] = rea["static"]
    assert st["summary"]["defects_detected"] == "7/7" and st["parse_errors"] == {}
    assert st["summary"]["impact_recall"] == 1.0


def test_agent_scoring_matches_each_policy(rea):
    """The user's rule: no read-only members, so in a cluster the worker is the hands and its guardian states the claim;
    nobody else re-verifies it, and the careful cluster scores like the careful basic agent (unsupported, root 0.5)."""
    runs = {(sc["id"], r["policy"]): r for sc in rea["agent"] for r in sc["runs"]}
    careful = runs[("reconnect-double-reward", "careful_cluster")]
    assert careful["outcome"] == "done" and careful["coverage"] == 1.0
    assert careful["defects"] == ["unsupported_conclusion"] and careful["root_cause"] == 0.5
    assert runs[("buy-does-nothing", "careful_basic")]["defects"] == ["unsupported_conclusion"]  # basic mode cannot verify
    jumps = runs[("reconnect-double-reward", "jumps_to_conclusion")]
    assert jumps["root_cause"] == 0.0 and "false_lead_asserted" in jumps["defects"]
    assert {"competing_open", "chain_gap", "false_lead_asserted"} <= set(runs[("buy-does-nothing", "competing_open")]["defects"])
    assert all(r["false_alarms"] == [] for r in runs.values())


def test_score_run_counts_only_flags_from_reasoning_checks():
    truth = {"symptom": ["ent:state:s:py/x"], "root_causes": ["ent:symbol:s:a.py#f"], "false_leads": [], "must_cover": []}
    claim = {"id": "clm_1", "claim_type": "hypothesis", "status": "proposed", "depends_on": [],
             "statement": {"subject": "ent:symbol:s:a.py#f", "relation": "causes", "object": "ent:state:s:py/x"}}
    out = reasoning.score_run(truth, "done", "", [claim], {"unsupported_conclusion", "chain_gap"})
    assert out["defects"] == ["unsupported_conclusion"] and out["caught"] == ["unsupported_conclusion"]
    assert out["false_alarms"] == ["chain_gap"] and out["root_cause"] == 0.5


def test_cli_writes_json_and_markdown(tmp_path, capsys):
    assert cli.main(["bench", "--suite", "memory", "--out", str(tmp_path), "--name", "t"]) == 0
    assert json.loads((tmp_path / "t.json").read_text(encoding="utf-8"))["memory"]["summary"]["current"]["leaks"] == 0
    md = (tmp_path / "t.md").read_text(encoding="utf-8")
    assert md.startswith("# 评测结果：t") and "## 记忆召回" in md and md in capsys.readouterr().out + "\n"
    assert set(bench_run.SUITES) == {"memory", "reasoning", "context"}


def test_m6_row_runs_only_with_the_users_embedding_model(mem, make_config):
    from codedoctor.models import scripted
    from test_memory_vectors import concept_embedder

    from conftest import unique_model

    assert [c["id"] for c in mem["not_run"]] == ["m6"] and "m6" not in mem["summary"]  # no model chosen: not run
    model = unique_model("emb")
    scripted.register_embedder(model, concept_embedder)  # stands in for the model the user would pick
    cfg = make_config(endpoints=[{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
                      memory={"embedding": {"endpoint": "fake", "model": model}})
    out = memory.run(embedding_from=cfg)
    [sc] = out["scenarios"]
    assert out["not_run"] == [] and sc["embedding"]["vectors"] > 0 and sc["embedding"]["error"] is None
    probes = {c: {p["id"]: p for p in sc["configs"][c]["probes"]} for c in ("current", "m6")}
    assert probes["m6"]["p9"]["rr"] > probes["current"]["p9"]["rr"]  # English question, Chinese notes


def test_context_suite_shows_what_m5_changes():
    from codedoctor.bench import context

    [sc] = context.run()["scenarios"]
    before, current = sc["policies"]["before"], sc["policies"]["current"]
    assert before["outcome"] == current["outcome"] == "done" and before["requests"] == current["requests"]
    assert current["over_budget"] == 0 and current["peak_share"] <= 1.0
    assert current["status_retained"] == 1.0 and current["evidence_recoverable"] == 1.0
    assert before["over_budget"] > 0  # before M5 a request could silently exceed the budget (tool descriptions uncounted)
