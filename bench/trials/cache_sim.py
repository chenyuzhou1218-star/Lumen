"""How much of each model request repeats the start of the agent's previous request in the same task - what a prefix
cache (DeepSeek's) can serve cheaply. The journal keeps request deltas; the full requests are rebuilt from them.
python cache_sim.py <bench dir name> [...]"""
import json
import sys

sys.path.insert(0, "D:/CodeDoctor/code-doctor/daemon")
from codedoctor import config  # noqa: E402
from codedoctor.agents.daemon import Daemon  # noqa: E402


def j(m) -> str:
    return json.dumps(m, ensure_ascii=False, sort_keys=True)


def common(a: list[str], b: list[str]) -> tuple[int, int]:
    """(chars of b that repeat a's start, index of the first differing message)."""
    n = 0
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            k = 0
            while k < min(len(x), len(y)) and x[k] == y[k]:
                k += 1
            return n + k, i
        n += len(x)
    return n, min(len(a), len(b))


for name in sys.argv[1:]:
    s = Daemon(config.load(f"D:/CodeDoctor/trials/{name}.toml")).s
    total = hit = 0
    why: dict[str, int] = {}
    lost: dict[str, int] = {}
    per_role: dict[str, list[int]] = {}
    for r in s.db.query("SELECT id, agent FROM tasks"):
        convo: list[dict] = []
        prev: list[str] | None = None
        for e in s.journal.read(task_id=r["id"], limit=100000):
            if e["type"] != "model_request":
                continue
            p = s.journal.original(e).get("payload") or {}
            for i, content in (p.get("rewritten") or {}).items():
                convo[int(i)] = {**convo[int(i)], "content": content}
            convo.extend(p.get("messages") or [])
            full = [j(m) for m in convo] + ([j({"role": "user", "content": p["working_memory"]})] if p.get("working_memory") else [])
            size = sum(len(m) for m in full)
            role = r["agent"].rsplit("-", 1)[0]
            pr = per_role.setdefault(role, [0, 0])
            total += size
            pr[0] += size
            if prev is not None:
                same, i = common(prev, full)
                hit += same
                pr[1] += same
                if i >= len(prev):
                    key = "only appended"
                elif prev[i].startswith('{"content"') and i == len(prev) - 1 and "working" not in key_hint if (key_hint := "") else False:
                    key = "x"
                elif i == len(prev) - 1 and p.get("working_memory") is not None:
                    key = "previous working memory at the end"
                elif p.get("rewritten"):
                    key = "older tool output elided"
                else:
                    key = f"other (message {i})"
                why[key] = why.get(key, 0) + 1
                lost[key] = lost.get(key, 0) + (size - same)
            prev = full
    print(f"{name}: requests {total:,} chars, repeated prefix {hit / max(total, 1):.0%}")
    print("   per role:", {k: f"{v[1] / max(v[0], 1):.0%} of {v[0]:,}" for k, v in per_role.items()})
    print("   where a request stopped matching the previous one:", why)
    print("   chars not repeated, by cause:", {k: f"{v:,}" for k, v in lost.items()})
