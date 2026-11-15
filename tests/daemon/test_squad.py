"""The big cluster's strategy for changing code (ADR 0016 item 14) end to end with scripted models: the system starts
the main pair, the dispatch head names scenarios, a scout's failing test goes to an idle backup pair at once, and the
backup fixes it in the project."""

from __future__ import annotations

import asyncio
import shlex
import sys
from pathlib import Path

from codedoctor import config as config_mod
from codedoctor.agents import orchestration as orch
from codedoctor.agents import squad
from codedoctor.agents.daemon import Daemon
from codedoctor.models import scripted

from conftest import unique_model


def project(root: Path) -> None:
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "calc.py").write_text("def total(items):\n    return sum(items) - 1\n", encoding="utf-8")
    (root / "README.md").write_text("# calc\nThe total of a basket is the sum of its items.\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_calc.py").write_text(
        "from app import calc\n\n\ndef test_total_is_a_number():\n    assert isinstance(calc.total([1]), int)\n",
        encoding="utf-8")


def config(tmp_path, m, squad_on=True, pairs=3):
    root = tmp_path / "shop"
    cmd = f"{shlex.quote(sys.executable.replace(chr(92), '/'))} -m pytest -q -p no:cacheprovider tests"
    agents = [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": m["dispatch"]},
              {"id": "head-logic", "role": "head_logic", "endpoint": "fake", "model": m["logic"]}]
    for i in range(1, pairs + 1):
        agents += [{"id": f"worker-{i}", "role": "worker", "endpoint": "fake", "model": m[f"w{i}"]},
                   {"id": f"guardian-{i}", "role": "guardian", "endpoint": "fake", "model": m[f"g{i}"],
                    "supervises_workers": [f"worker-{i}"]}]
    return root, config_mod.parse({
        "cd_schema": "cd.config.project/0",
        "project": {"name": "shop", "root": str(root), "data_dir": str(tmp_path / "data")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": agents, "cluster": {"enabled": True, "squad": squad_on},
        "permissions": {"run_command": "deny", "write_files": True, "test_command": cmd},
        "defaults": {"budget": {"max_steps": 12, "max_tokens": 1000000}, "stall_steps": 5},
    }, base_dir=tmp_path)


def test_the_layout_main_alternates_scouts():
    class A:
        def __init__(self, id, role, watched=()):
            self.id, self.role, self.watched = id, role, list(watched)

    class C:
        agents = {}

    cfg = C()
    cfg.agents = {"head-dispatch": A("head-dispatch", "head_dispatch"), "head-logic": A("head-logic", "head_logic")}
    for i in range(1, 10):
        cfg.agents[f"worker-{i}"] = A(f"worker-{i}", "worker")
        cfg.agents[f"guardian-{i}"] = A(f"guardian-{i}", "guardian", [f"worker-{i}"])
    lay = squad.layout(cfg)
    assert lay["main"] == ("worker-1", "guardian-1")
    assert [w for w, _ in lay["backups"]] == ["worker-2", "worker-3"]
    assert [w for w, _ in lay["scouts"]] == [f"worker-{i}" for i in range(4, 10)]  # 12 agents scout
    for i in range(3, 10):  # 6 agents: two pairs - the scout pair is also the backup pair
        del cfg.agents[f"worker-{i}"], cfg.agents[f"guardian-{i}"]
    small = squad.layout(cfg)
    assert small["scouts"] == small["backups"] == [("worker-2", "guardian-2")]
    assert squad.MAIN_SHARE + squad.BACKUPS_SHARE + squad.SCOUTS_SHARE + squad.HEAD_SHARE + squad.CONSULT_SHARE <= 1.0


def test_a_scout_finding_goes_to_a_backup_that_fixes_it_in_the_project(tmp_path):
    m = {k: unique_model(k) for k in ("dispatch", "logic", "w1", "g1", "w2", "g2", "w3", "g3")}
    root, cfg = config(tmp_path, m)
    project(root)
    seen = {}

    def head_first(msgs):
        seen["head"] = msgs[1].content
        seen["head_tools"] = True
        return {"tool_calls": [{"name": "scout", "arguments": {"scenarios": [
            {"title": "total is the sum", "check": "total([1, 2]) == 3"}]}}]}

    scripted.register(m["dispatch"], [head_first, {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 30}}]},
                                      *[{"text": "settled"}] * 3])
    # the main worker changes nothing; the scout writes a failing test; the backup gets it and fixes the code
    scripted.register(m["w1"], [lambda msgs: (seen.setdefault("main", msgs[1].content), {"text": "looked, changed nothing"})[1]])
    scripted.register(m["w2"], [
        lambda msgs: (seen.setdefault("backup", msgs[1].content), {"tool_calls": [{"name": "edit_file", "arguments": {
            "path": "app/calc.py", "old": "sum(items) - 1", "new": "sum(items)"}}]})[1],
        {"text": "fixed the total"}])  # the backup
    scripted.register(m["w3"], [
        {"tool_calls": [{"name": "edit_file", "arguments": {"path": "app/calc.py", "old": "- 1", "new": ""}}]},  # refused
        {"tool_calls": [{"name": "create_file", "arguments": {  # passes on the original code: reproduces nothing
            "path": "tests/test_scout_weak.py",
            "content": "from app import calc\n\n\ndef test_weak():\n    assert calc.total([]) <= 0\n"}}]},
        lambda msgs: (seen.setdefault("after_weak", msgs[-1].content), {"tool_calls": [{"name": "create_file", "arguments": {
            "path": "tests/test_scout_total.py",
            "content": "from app import calc\n\n\ndef test_total_is_the_sum():\n    assert calc.total([1, 2]) == 3\n"}}]})[1],
        {"text": "test_total_is_the_sum: fails"}])
    for g in ("g1", "g2", "g3"):
        scripted.register(m[g], [lambda msgs, g=g: (seen.setdefault(g, msgs[1].content), {"text": "checked"})[1]])
    scripted.register(m["logic"], [{"text": "ok"}])

    async def go():
        d = Daemon(cfg, poll_s=0.02)
        assert "scout" in d.agents["head-dispatch"].tools and "delegate" not in d.agents["head-dispatch"].tools
        await d.start()
        try:
            sub = d.submit_task("head-dispatch", "fix totals", "basket totals are one too small")
            for _ in range(800):
                tree = orch.tree(d.s, sub["task_id"])
                if len(tree) >= 6 and all((orch.task_row(d.s, t) or {}).get("state") == "finished" for t in tree):
                    break
                await asyncio.sleep(0.05)
        finally:
            await d.halt()
        return d, sub

    d, sub = asyncio.run(go())
    assert "THE SQUAD IS ALREADY AT WORK" in seen["head"] and "sum of its items" in seen["head"]  # README given
    assert "YOU ARE THE MAIN FIXER" in seen["main"] and "=== app/calc.py ===" in seen["main"]
    assert "BACKUP FIXER" in seen["backup"] and "test_total_is_the_sum" in seen["backup"]
    assert "g3" not in seen  # scout tests are checked by the system against the original code, not reviewed
    rows = [orch.task_row(d.s, t) for t in orch.tree(d.s, sub["task_id"])]
    bodies = {r["agent"]: orch.body_of(r) for r in rows if not orch.body_of(r).get("review_of")}
    assert bodies["worker-1"]["squad"] == "main" and bodies["worker-2"]["squad"] == "backup"
    assert bodies["worker-2"]["files"] == ["tests/test_scout_total.py"]
    assert bodies["worker-3"]["squad"] == "scout"
    # the scout could not change code; its test is in the project
    scout_results = [e["data"] for e in d.s.journal.read(task_id=next(r["id"] for r in rows if r["agent"] == "worker-3"))
                     if e["type"] == "tool_result"]
    assert not scout_results[0]["ok"]
    weak = [e["data"] for e in d.s.journal.read(task_id=next(r["id"] for r in rows if r["agent"] == "worker-3"))
            if e["type"] == "tool_result" and e["data"].get("tool") == "create_file"]
    assert weak[0]["ok"] and "passes even on the ORIGINAL code" in seen["after_weak"]
    assert (root / "tests" / "test_scout_total.py").exists()
    # the task page lists the finding: who found it, who fixed it, and that the last test run passes it
    from codedoctor.desktop.changes_view import collect

    found = collect(d.s, sub["task_id"])["found"]
    assert found["tests/test_scout_total.py"]["scout"] == "worker-3"
    assert found["tests/test_scout_total.py"]["backup"] == "worker-2"
    # the backup's fix is in the project
    assert (root / "app" / "calc.py").read_text(encoding="utf-8") == "def total(items):\n    return sum(items)\n"


def test_with_six_agents_the_scout_fixes_its_own_finding_as_the_backup(tmp_path):
    """Real 6-agent run: the scout pair is the backup pair, and the system skipped it as busy while its scout task was
    still finishing - the failing scout test stayed unfixed."""
    m = {k: unique_model(k) for k in ("dispatch", "logic", "w1", "g1", "w2", "g2")}
    root, cfg = config(tmp_path, m, pairs=2)
    project(root)
    scripted.register(m["dispatch"], [{"tool_calls": [{"name": "scout", "arguments": {"scenarios": [
        {"title": "total is the sum"}]}}]}, {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 30}}]},
        *[{"text": "settled"}] * 3])
    scripted.register(m["w1"], [{"text": "changed nothing"}])
    scripted.register(m["g1"], [{"text": "checked"}] * 2)
    scripted.register(m["w2"], [
        {"tool_calls": [{"name": "create_file", "arguments": {
            "path": "tests/test_scout_total.py",
            "content": "from app import calc\n\n\ndef test_total_is_the_sum():\n    assert calc.total([1, 2]) == 3\n"}}]},
        {"text": "test_total_is_the_sum: fails"},
        {"tool_calls": [{"name": "edit_file", "arguments": {"path": "app/calc.py", "old": "sum(items) - 1",
                                                             "new": "sum(items)"}}]},
        {"text": "fixed"}])
    scripted.register(m["g2"], [{"text": "checked"}] * 2)
    scripted.register(m["logic"], [{"text": "ok"}])

    async def go():
        d = Daemon(cfg, poll_s=0.02)
        await d.start()
        try:
            sub = d.submit_task("head-dispatch", "fix totals", "basket totals are one too small")
            for _ in range(800):
                tree = orch.tree(d.s, sub["task_id"])
                if len(tree) >= 6 and all((orch.task_row(d.s, t) or {}).get("state") == "finished" for t in tree):
                    break
                await asyncio.sleep(0.05)
        finally:
            await d.halt()
        return d, sub

    d, sub = asyncio.run(go())
    rows = [orch.task_row(d.s, t) for t in orch.tree(d.s, sub["task_id"])]
    backups = [r for r in rows if orch.body_of(r).get("squad") == "backup" and not orch.body_of(r).get("review_of")]
    assert [r["agent"] for r in backups] == ["worker-2"]
    assert (root / "app" / "calc.py").read_text(encoding="utf-8") == "def total(items):\n    return sum(items)\n"


def test_a_big_project_briefs_the_files_the_task_is_about_and_stays_in_the_message_limit(tmp_path):
    """A real run on qutebrowser (200 code files) failed before any model call: the main fixer's briefing went over
    the message limit, and the file the bug report named came late in the alphabet."""
    from codedoctor.agents import orchestration, ownership

    for i in range(120):
        (tmp_path / f"a{i:03d}.py").write_text("x = 1\n" * 400, encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "urlutils.py").write_text("def incdec_number(url):\n    return url\n", encoding="utf-8")
    files = ownership.code_files(tmp_path)
    task = "The utility `incdec_number` in `pkg/urlutils.py` fails on encoded URLs."
    assert ownership.by_relevance(tmp_path, files, task)[0] == "pkg/urlutils.py"
    brief = ownership.briefing(tmp_path, files, max_chars=20000, focus=task)
    assert "=== pkg/urlutils.py ===" in brief and len(brief) < orchestration.MAX_INSTRUCTIONS
    assert "more (list_dir shows them)" in brief
