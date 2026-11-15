"""40 agents with scripted models on a 19-module project: every worker fixes its own module at the same time and the
system runs the tests after every change. Checks that the whole tree finishes, nothing is lost, and how long the
serialized test runs take. python stress_scripted.py [N] [timeout] [squad]: with "squad" the system's strategy runs
instead (ADR 0016 item 14): the main worker fixes all modules, 16 scouts write a test each, two backups
take the scout tests that fail."""
import asyncio
import os
import shlex
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "D:/CodeDoctor/code-doctor/tests/daemon")
os.environ["CODEDOCTOR_HOME"] = tempfile.mkdtemp()
from codedoctor import config as config_mod  # noqa: E402
from codedoctor.agents import orchestration as orch  # noqa: E402
from codedoctor.agents.daemon import Daemon  # noqa: E402
from codedoctor.models import scripted  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 19
SQUAD = len(sys.argv) > 3 and sys.argv[3] == "squad"
tmp = Path(tempfile.mkdtemp())
root = tmp / "proj"
(root / "pkg").mkdir(parents=True)
(root / "tests").mkdir()
(root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
for i in range(N):
    (root / "pkg" / f"m{i}.py").write_text(f"def value():\n    return {i} - 1\n", encoding="utf-8")
    (root / "tests" / f"test_m{i}.py").write_text(f"from pkg import m{i}\n\n\ndef test_value():\n    assert m{i}.value() == {i}\n",
                                                  encoding="utf-8")

models = {}


def reg(name, turns):
    models[name] = f"stress-{name}-{time.time_ns()}"
    scripted.register(models[name], turns)


FIX_ALL = {"tool_calls": [{"name": "edit_file", "arguments": {"path": f"pkg/m{i}.py", "old": f"{i} - 1", "new": f"{i}"}}
                          for i in range(N)]}
reg("dispatch", [
    {"tool_calls": [{"name": "scout", "arguments": {"scenarios": [{"title": f"m{i} value", "check": f"m{i}.value() == {i}"}
                                                                  for i in range(N)]}}]} if SQUAD else
    {"tool_calls": [{"name": "delegate", "arguments": {"agent": f"worker-{i + 1}", "title": f"fix m{i}",
                                                        "instructions": "value() is off by one", "files": [f"pkg/m{i}.py"]}}
                    for i in range(N)]},
    {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 300}}]},
    {"tool_calls": [{"name": "wait_for", "arguments": {"timeout_s": 300}}]},
    *[{"text": "all fixed"}] * 3])
reg("logic", [{"text": "ok"}])
for i in range(N):
    if SQUAD and i < 3:  # main (and backups, when they get a scout finding) fix everything
        reg(f"w{i}", [FIX_ALL, {"text": "done"}])
        reg(f"g{i}", [{"text": "checked"}])
        continue
    if SQUAD:  # scouts: one test file per scenario they get (scenarios are dealt in turn)
        mine = [k for k in range(N) if k % (N - 3) == i - 3]
        reg(f"w{i}", [{"tool_calls": [{"name": "create_file", "arguments": {
            "path": f"tests/test_scout_m{k}.py",
            "content": f"from pkg import m{k}\n\n\ndef test_scout_value():\n    assert m{k}.value() == {k}\n"}} for k in mine]},
            {"text": "done"}])
        reg(f"g{i}", [{"text": "checked"}])
        continue
    reg(f"w{i}", [{"tool_calls": [{"name": "edit_file", "arguments": {"path": f"pkg/m{i}.py", "old": f"{i} - 1", "new": f"{i}"}}]},
                  {"text": "done"}])
    reg(f"g{i}", [{"text": "checked"}])
agents = [{"id": "head-dispatch", "role": "head_dispatch", "endpoint": "fake", "model": models["dispatch"]},
          {"id": "head-logic", "role": "head_logic", "endpoint": "fake", "model": models["logic"]}]
for i in range(N):
    agents += [{"id": f"worker-{i + 1}", "role": "worker", "endpoint": "fake", "model": models[f"w{i}"]},
               {"id": f"guardian-{i + 1}", "role": "guardian", "endpoint": "fake", "model": models[f"g{i}"],
                "supervises_workers": [f"worker-{i + 1}"]}]
cmd = f"{shlex.quote(sys.executable.replace(chr(92), '/'))} -m pytest -q -p no:cacheprovider tests"
cfg = config_mod.parse({
    "cd_schema": "cd.config.project/0",
    "project": {"name": "stress", "root": str(root), "data_dir": str(tmp / "data")},
    "endpoints": [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
    "agents": agents, "cluster": {"enabled": True, "max_agents": 40, "squad": SQUAD},
    "permissions": {"run_command": "deny", "write_files": True, "test_command": cmd},
    "defaults": {"budget": {"max_steps": 12, "max_tokens": 5000000}, "stall_steps": 5},
}, base_dir=tmp)


async def go():
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    t0 = time.time()
    try:
        sub = d.submit_task("head-dispatch", "fix all", "every value is off by one")
        try:
            report = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), float(sys.argv[2]) if len(sys.argv) > 2 else 900)
        except Exception:
            report = {"body": {"outcome": "TIMEOUT"}}
            for t in orch.tree(d.s, sub["task_id"]):
                r = orch.task_row(d.s, t)
                print("TASK", r["agent"], r["state"], r["outcome"], flush=True)
            for e in d.s.journal.read(task_id=sub["task_id"])[-12:]:
                print("  J", e["agent"], e["type"], str(e["data"])[:150], flush=True)
        for _ in range(2000):
            if all(orch.task_row(d.s, t)["state"] == "finished" for t in orch.tree(d.s, sub["task_id"])):
                break
            await asyncio.sleep(0.1)
    finally:
        await d.halt()
    tree = orch.tree(d.s, sub["task_id"])
    runs = [e["data"] for t in tree for e in d.s.journal.read(task_id=t) if e["type"] == "test_run"]
    fixed = sum((root / "pkg" / f"m{i}.py").read_text().strip().endswith(f"return {i}") for i in range(N))
    outcomes = {}
    for t in tree:
        r = orch.task_row(d.s, t)
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    print(f"agents {len(agents)} | tasks {len(tree)} {outcomes} | fixed {fixed}/{N} | test runs {len(runs)} | "
          f"last: {runs[-1]['summary'] if runs else '-'} | answer: {report['body']['outcome']} | {time.time() - t0:.0f}s", flush=True)


asyncio.run(go())
os._exit(0)
