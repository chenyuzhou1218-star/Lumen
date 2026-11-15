"""One benchmark run: python bench.py <repo> <agents> <budget> [label]
repo: chainshop | library | gym-booking2. agents: 2 (双人互检) or 2 heads + pairs (6, 10, 20, 40).
Clones a fresh copy, writes a config, runs Code Doctor headless with DeepSeek, grades it, appends to results.jsonl."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = "D:/CodeDoctor/code-doctor/.venv/Scripts/python.exe"
GRADERS = {"chainshop": "grade_chainshop.py", "library": "grade_library.py", "gym-booking2": "grade_gym2.py"}
PROMPTS = {"chainshop": "chain-prompt.txt", "library": "race-prompt.txt", "gym-booking2": "gym2-prompt.txt"}

repo, n, budget = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
MODEL = __import__("os").environ.get("BENCH_MODEL", "deepseek-chat")  # the user chooses the model
THINKING = __import__("os").environ.get("BENCH_THINKING", "")  # 思考强度 (off/low/medium/high); empty: the provider's default
label = sys.argv[4] if len(sys.argv) > 4 else ""
stamp = time.strftime("%H%M%S")
SHISHAN = Path("D:/史山")  # the bug bank: repo "王者/market" = a puzzle there (set up with its own tool, its grader)
TIERS = {"白银": "silver", "黄金": "gold", "钻石": "diamond", "王者": "king", "外部Pro": "pro"}
# External puzzles run their tests with the project's own environment (an old Qt app: off-screen, results printed as
# they happen by the cdreport plugin, the proxy auto-config tests that crash on Windows left out).
QBPY = "D:/史山/外部/swe-bench-pro/work/qb-env/Scripts/python.exe"
EXTERNAL = {"外部Pro/qb-urlutils": {"python": QBPY, "tests": f'"{QBPY}" -m pytest -q -p no:cacheprovider -p cdreport -o addopts= '
                                                         f'-k "not pac" tests/unit/utils/test_urlutils.py',
                                   "env": {"QT_QPA_PLATFORM": "offscreen"}}}
puzzle = "/" in repo
safe = (TIERS.get(repo.split("/")[0], "x") + "-" + repo.split("/")[1]) if puzzle else repo
name = f"b-{safe}-{n}-{stamp}"
work, data = HERE / name, HERE / f"data-{name}"
if puzzle:
    subprocess.run([sys.executable, str(SHISHAN / "工具" / "开局.py"), repo, str(work)], check=True, capture_output=True)
else:
    subprocess.run(["git", "clone", "-q", str(HERE / repo), str(work)], check=True)


def agent(i, role, **kw):
    return {"id": i, "role": role, "endpoint": "deepseek", "model": MODEL, "context_budget_tokens": 60000,
            "params": {"temperature": 0.2, **({"reasoning": THINKING} if THINKING else {})}, **kw}


if n == 2:
    agents, mode, entry = [agent("worker-1", "worker"), agent("guardian-1", "guardian", supervises_workers=["worker-1"])], "dual", "worker-1"
else:
    pairs = (n - 2) // 2
    agents = [agent("head-dispatch", "head_dispatch"), agent("head-logic", "head_logic")]
    for k in range(1, pairs + 1):
        agents += [agent(f"worker-{k}", "worker"), agent(f"guardian-{k}", "guardian", supervises_workers=[f"worker-{k}"])]
    mode, entry = "advanced", "head-dispatch"
raw = {
    "cd_schema": "cd.config.project/0",
    "project": {"name": name.lower()[:60], "root": str(work).replace("\\", "/"), "data_dir": str(data).replace("\\", "/"),
                "code_data_class": "internal"},
    "permissions": {"run_command": "allowlist", "write_files": True,
                    "command_allowlist": ["python -m pytest", "python -c", f"{VENV} -m pytest", f"{VENV} -c"]
                    + ([f"{EXTERNAL[repo]['python']} -m pytest"] if repo in EXTERNAL else []),
                    "test_command": EXTERNAL[repo]["tests"] if repo in EXTERNAL else f"{VENV} -m pytest -q -p no:cacheprovider tests"},
    "defaults": {"budget": {"max_steps": 40, "max_tokens": budget}, "stall_steps": 6},
    "cluster": {"enabled": mode != "dual", "mode": mode, "max_agents": 40, "parallel": True, "foresight": {"enabled": False}},
    "endpoints": [{"id": "deepseek", "name": "DeepSeek", "kind": "openai_compatible", "provider": "deepseek",
                   "base_url": "https://api.deepseek.com/v1", "api_key_env": "DEEPSEEK_API_KEY", "api_key_keyring": True,
                   "local": False, "max_data_class": "internal", "max_concurrency": 4,
                   "models": ["deepseek-chat", "deepseek-reasoner"]}],
    "agents": agents,
}
sys.path.insert(0, "D:/CodeDoctor/code-doctor/daemon")
from codedoctor import config  # noqa: E402

cfg_path = HERE / f"{name}.toml"
config.save_raw(raw, cfg_path)
prompt = ((SHISHAN / "题目" / repo / "任务.txt") if puzzle else (HERE / PROMPTS[repo])).read_text(encoding="utf-8").strip()
t0 = time.time()
out = subprocess.run([VENV, "-m", "codedoctor", "run", "--config", str(cfg_path), "--agent", entry, "--title", "全面检查并修复",
                      "--timeout", "2700", prompt], capture_output=True, text=True, encoding="utf-8", errors="replace",
                     env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", **EXTERNAL.get(repo, {}).get("env", {})})
seconds = int(time.time() - t0)
(HERE / f"{name}.out").write_text(out.stdout + "\n--- stderr ---\n" + out.stderr, encoding="utf-8")
judge = SHISHAN / "裁判" / f"{repo.replace('/', '-')}.py" if puzzle else HERE / GRADERS[repo]
grade = subprocess.run([VENV, str(judge), str(work)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}).stdout
m = re.search(r"(\d+)/(\d+) 个 bug 修对；仓库自带测试：(.*)", grade)
probe = subprocess.run([VENV, "-c", f"""
import json, sys
from codedoctor import config
from codedoctor.agents.daemon import Daemon
s = Daemon(config.load({str(cfg_path)!r})).s
per = {{}}
for r in s.db.query("SELECT id, agent FROM tasks"):
    for e in s.journal.read(task_id=r["id"]):
        if e["type"] == "model_response":
            d = e["data"]; per[r["agent"]] = per.get(r["agent"], 0) + (d.get("input_tokens") or 0) + (d.get("output_tokens") or 0)
            per["_cached"] = per.get("_cached", 0) + (d.get("cached_tokens") or 0)
            per["_output"] = per.get("_output", 0) + (d.get("output_tokens") or 0)
print(json.dumps(per))
"""], capture_output=True, text=True, cwd="D:/CodeDoctor/code-doctor/daemon")
per = json.loads(probe.stdout.strip() or "{}")
cached, output = per.pop("_cached", 0), per.pop("_output", 0)
row = {"time": time.strftime("%m-%d %H:%M"), "label": label, "repo": repo, "agents": n, "budget": budget, "model": MODEL, "thinking": THINKING or "default",
       "score": f"{m.group(1)}/{m.group(2)}" if m else "?", "tests": m.group(3) if m else "?", "seconds": seconds,
       "tokens": sum(per.values()), "cached_input": cached, "output": output, "active": len(per), "dir": name}
with open(HERE / "results.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(grade)
print(json.dumps(row, ensure_ascii=False))
