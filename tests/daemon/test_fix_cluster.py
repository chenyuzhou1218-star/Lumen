"""A code-changing cluster end to end with scripted models (ADR 0016): the dispatch head sees the coupled file
groups, hands them out by files, the worker fixes, the system runs the tests, and the guardian reviews the diff."""

from __future__ import annotations

import asyncio
import shlex
import sys
from pathlib import Path

from codedoctor import config as config_mod
from codedoctor.agents import orchestration as orch
from codedoctor.agents.daemon import Daemon
from codedoctor.models import scripted

from conftest import unique_model


def project(root: Path) -> None:
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "prices.py").write_text("def cents(yuan):\n    return yuan * 10\n", encoding="utf-8")
    (root / "app" / "orders.py").write_text("from app import prices\n\n\ndef total(items):\n"
                                            "    return sum(prices.cents(p) for p in items)\n", encoding="utf-8")
    (root / "app" / "banner.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_orders.py").write_text(
        "from app import orders\n\n\ndef test_total():\n    assert orders.total([1, 2]) == 300\n", encoding="utf-8")


def test_dispatch_hands_out_coupled_groups_and_the_system_tests_every_change(tmp_path):
    root = tmp_path / "shop"
    project(root)
    m = {k: unique_model(k) for k in ("dispatch", "worker", "guardian", "logic")}
    seen = {}

    def first_turn(msgs):
        seen["task"] = msgs[1].content
        return {"tool_calls": [{"name": "delegate", "arguments": {
            "agent": "worker-1", "title": "fix prices", "instructions": "totals are 10x too small",
            "files": ["app/orders.py", "app/prices.py"]}},
            {"name": "delegate", "arguments": {"agent": "worker-2", "title": "banner", "instructions": "check it",
                                               "files": ["app/banner.py"]}}]}

    scripted.register(m["dispatch"], [first_turn, {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 20}}]},
                                      *[{"text": "fixed: prices.cents multiplied by 10 instead of 100"}] * 3])
    scripted.register(m["worker"], [
        {"tool_calls": [{"name": "edit_file", "arguments": {"path": "app/prices.py", "old": "yuan * 10", "new": "yuan * 100"}}]},
        {"text": "done"}])
    scripted.register(m["guardian"], [lambda msgs: (seen.setdefault("review", msgs[1].content), {"text": "checked"})[1]])
    scripted.register(m["logic"], [{"text": "no couplings beyond orders -> prices"}])
    cmd = f"{shlex.quote(sys.executable.replace(chr(92), '/'))} -m pytest -q -p no:cacheprovider tests"
    agents = [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": m["dispatch"]},
              {"id": "head-logic", "role": "head_logic", "endpoint": "fake", "model": m["logic"]}]
    for i in (1, 2):
        agents += [{"id": f"worker-{i}", "role": "worker", "endpoint": "fake", "model": m["worker"] if i == 1 else m["logic"]},
                   {"id": f"guardian-{i}", "role": "guardian", "endpoint": "fake", "model": m["guardian"] if i == 1 else m["logic"],
                    "supervises_workers": [f"worker-{i}"]}]
    cfg = config_mod.parse({
        "cd_schema": "cd.config.project/0",
        "project": {"name": "shop", "root": str(root), "data_dir": str(tmp_path / "data")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": agents, "cluster": {"enabled": True, "squad": False},  # the file-split strategy
        "permissions": {"run_command": "deny", "write_files": True, "test_command": cmd},
        "defaults": {"budget": {"max_steps": 12, "max_tokens": 400000}, "stall_steps": 5},
    }, base_dir=tmp_path)

    async def go():
        d = Daemon(cfg, poll_s=0.02)
        await d.start()
        try:
            sub = d.submit_task("head-dispatch", "fix totals", "order totals are wrong")
            report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 60)
            for _ in range(300):
                if all(orch.task_row(d.s, t)["state"] == "finished" for t in orch.tree(d.s, sub["task_id"])):
                    break
                await asyncio.sleep(0.05)
        finally:
            await d.halt()
        return d, sub, report

    d, sub, report = asyncio.run(go())
    # the system grouped the coupled files (orders imports prices) and told the dispatch head
    assert "Coupled files" in seen["task"] and "app/orders.py, app/prices.py" in seen["task"]
    assert "app/banner.py" in seen["task"]
    # the fix landed, the tests pass, and the guardian got the diff and the system's test runs
    assert "yuan * 100" in (root / "app" / "prices.py").read_text(encoding="utf-8")
    runs = [e["data"] for t in orch.tree(d.s, sub["task_id"]) for e in d.s.journal.read(task_id=t) if e["type"] == "test_run"]
    assert runs and runs[-1]["summary"].startswith("1 passed") and not runs[-1]["regressions"]
    assert "+    return yuan * 100" in seen["review"] and "Test runs the system made" in seen["review"]
    assert report["body"]["outcome"] == "done"


def test_coupled_groups_follow_imports_and_shared_urls(tmp_path):
    from types import SimpleNamespace

    from codedoctor.agents import ownership

    root = tmp_path / "p"
    (root / "srv").mkdir(parents=True)
    (root / "web").mkdir()
    (root / "srv" / "__init__.py").write_text("", encoding="utf-8")
    (root / "srv" / "api.py").write_text("from srv import store\nROUTES = {('POST', '/api/buy'): store.buy}\n", encoding="utf-8")
    (root / "srv" / "store.py").write_text("def buy(b):\n    return b\n", encoding="utf-8")
    (root / "srv" / "alone.py").write_text("X = 1\n", encoding="utf-8")
    (root / "web" / "page.js").write_text("import { show } from './view';\nfetch(`${API}/api/buy`)\n", encoding="utf-8")
    (root / "web" / "view.js").write_text("export function show() {}\n", encoding="utf-8")
    services = SimpleNamespace(config=SimpleNamespace(root=root),
                               graph=SimpleNamespace(_static=lambda: (_ for _ in ()).throw(RuntimeError("no graph"))))
    groups = ownership.coupled_groups(services)
    big = next(g for g in groups if "srv/api.py" in g)
    assert {"srv/api.py", "srv/store.py", "web/page.js", "web/view.js"} <= set(big)
    assert ["srv/alone.py"] in groups


def test_the_split_keeps_coupled_code_whole_and_packs_loose_files(tmp_path):
    """Real runs: splitting 12 tightly coupled files across 6 workers fixed 7/13; one worker fixed 13/13.
    And a project of loose script files must not become hundreds of one-file jobs."""
    from types import SimpleNamespace

    from codedoctor.agents import ownership

    def services(root):
        return SimpleNamespace(config=SimpleNamespace(root=root),
                               graph=SimpleNamespace(_static=lambda: (_ for _ in ()).throw(RuntimeError())))

    tight = tmp_path / "tight" / "shop"
    tight.mkdir(parents=True)
    names = [f"m{i}" for i in range(12)]
    for i, n in enumerate(names):
        (tight / f"{n}.py").write_text(f"from shop import {names[(i + 1) % 12]}\n", encoding="utf-8")
    assert [len(b["files"]) for b in ownership.plan(services(tmp_path / "tight"), 9)] == [12]

    loose = tmp_path / "loose"
    for d in ("ui", "net", "game"):
        (loose / d).mkdir(parents=True)
        for i in range(20):
            (loose / d / f"f{i}.js").write_text("var x = 1;\n", encoding="utf-8")
    buckets = ownership.plan(services(loose), 4)
    assert len(buckets) == 4 and sum(len(b["files"]) for b in buckets) == 60 and max(len(b["files"]) for b in buckets) <= 23
    text = ownership.describe_groups(services(loose), 4)
    assert "Suggested split for your 4 workers" in text and "worker 4" in text


def test_the_guardian_fixes_what_its_review_finds_while_the_worker_moves_on(tmp_path):
    """The user's pair design: the worker fixes and moves on; its guardian supervises, fixes what it finds itself,
    and the system re-tests the guardian's change too."""
    root = tmp_path / "shop"
    project(root)
    (root / "app" / "prices.py").write_text("def cents(yuan):\n    return yuan * 10\n\n\ndef tax(c):\n    return c // 100\n",
                                            encoding="utf-8")
    (root / "tests" / "test_tax.py").write_text("from app import prices\n\n\ndef test_tax():\n    assert prices.tax(1000) == 100\n",
                                                encoding="utf-8")
    m = {k: unique_model(k) for k in ("dispatch", "worker", "guardian", "logic")}
    seen = {}
    scripted.register(m["dispatch"], [
        {"tool_calls": [{"name": "delegate", "arguments": {"agent": "worker-1", "title": "fix prices", "instructions": "totals and tax are wrong",
                                                           "files": ["app/orders.py", "app/prices.py"]}}]},
        {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 30}}]},
        *[{"text": "done"}] * 3])
    scripted.register(m["worker"], [  # fixes the totals, misses the tax, and moves on
        {"tool_calls": [{"name": "edit_file", "arguments": {"path": "app/prices.py", "old": "yuan * 10", "new": "yuan * 100"}}]},
        {"text": "done"}, {"text": "done"}, {"text": "done"}])

    def review(msgs):
        seen["review"] = msgs[1].content
        return {"tool_calls": [{"name": "edit_file", "arguments": {"path": "app/prices.py", "old": "c // 100", "new": "c // 10"}}]}

    scripted.register(m["guardian"], [review, {"text": "fixed the tax the worker missed; all tests pass"}])
    scripted.register(m["logic"], [{"text": "ok"}])
    cmd = f"{shlex.quote(sys.executable.replace(chr(92), '/'))} -m pytest -q -p no:cacheprovider tests"
    cfg = config_mod.parse({
        "cd_schema": "cd.config.project/0",
        "project": {"name": "shop", "root": str(root), "data_dir": str(tmp_path / "data")},
        "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
        "agents": [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": m["dispatch"]},
                   {"id": "head-logic", "role": "head_logic", "endpoint": "fake", "model": m["logic"]},
                   {"id": "worker-1", "role": "worker", "endpoint": "fake", "model": m["worker"]},
                   {"id": "guardian-1", "role": "guardian", "endpoint": "fake", "model": m["guardian"],
                    "supervises_workers": ["worker-1"]}],
        "cluster": {"enabled": True},
        "permissions": {"run_command": "deny", "write_files": True, "test_command": cmd},
        "defaults": {"budget": {"max_steps": 12, "max_tokens": 400000}, "stall_steps": 5},
    }, base_dir=tmp_path)

    async def go():
        d = Daemon(cfg, poll_s=0.02)
        assert "edit_file" in d.agents["guardian-1"].tools
        await d.start()
        try:
            sub = d.submit_task("head-dispatch", "fix", "totals and tax are wrong")
            await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 60)
            for _ in range(300):
                if all(orch.task_row(d.s, t)["state"] == "finished" for t in orch.tree(d.s, sub["task_id"])):
                    break
                await asyncio.sleep(0.05)
        finally:
            await d.halt()
        return d, sub

    d, sub = asyncio.run(go())
    text = (root / "app" / "prices.py").read_text(encoding="utf-8")
    assert "yuan * 100" in text and "c // 10" in text  # the worker's fix and the guardian's fix
    [rev] = [t for t in orch.children(d.s, sub["task_id"]) if orch.body_of(t).get("review_of")]
    assert orch.body_of(rev)["files"] == ["app/orders.py", "app/prices.py"]
    runs = [e["data"] for e in d.s.journal.read(task_id=rev["id"]) if e["type"] == "test_run"]
    assert runs and runs[-1]["summary"].startswith("2 passed")  # the system re-tested the guardian's change
