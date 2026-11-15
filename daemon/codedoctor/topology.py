"""The four collaboration modes and the agent roster each one needs (ADR 0015).

Modes and sizes follow ChatGPT's studio build (single / dual / small squad / dual-head cluster); the roster rules
are this project's: agents the user already configured keep their id, model and settings (matched by role, in
order); new agents get NO model - the user picks every model. Single agents (role general) are kept in every mode
and are not part of the cluster count. ``draft`` edits a raw configuration only; nothing runs before it is saved.
"""

from __future__ import annotations

import copy

MODES = {
    "basic": ("单人助手", "1 个 Agent 直接调查，自己决策发现的异常。成本最低。"),
    "dual": ("双人互检", "1 个执行者 + 1 个独立监督者。执行者做完，监督者自动复查每条结论。"),
    "small": ("协作小队", "2 个首脑 + 执行者，每 2 个执行者共用 1 个监督者。适合中等规模的问题。"),
    "advanced": ("双首脑集群", "2 个首脑 + 执行者，每个执行者都有自己的监督者，按需并行唤醒。最多 40 个。"),
}
MAX_CLUSTER = 40


def sizes(mode: str) -> tuple[int, ...]:
    """Valid cluster sizes (heads, workers and guardians; single agents not counted)."""
    return {"basic": (0,), "dual": (2,), "small": tuple(range(5, MAX_CLUSTER + 1, 3)),
            "advanced": tuple(range(4, MAX_CLUSTER + 1, 2))}[mode]


def shape(mode: str, count: int) -> dict:
    """{'heads', 'workers', 'guardians'} for a mode and size."""
    if mode == "basic":
        return {"heads": 0, "workers": 0, "guardians": 0}
    if mode == "dual":
        return {"heads": 0, "workers": 1, "guardians": 1}
    groups = (count - 2) // (3 if mode == "small" else 2)
    return {"heads": 2, "workers": groups * (2 if mode == "small" else 1), "guardians": groups}


def describe(mode: str, count: int) -> str:
    s = shape(mode, count)
    if mode == "basic":
        return "1 个单 Agent 直接调查"
    if mode == "dual":
        return "1 个执行者 · 1 个监督者"
    per = "每 2 个执行者共用 1 个监督者" if mode == "small" else "每个执行者配 1 个监督者"
    return f"2 个首脑 · {s['workers']} 个执行者 · {s['guardians']} 个监督者（{per}）"


def current(raw: dict) -> tuple[str, int]:
    """The mode and cluster size a raw configuration has now."""
    cl = raw.get("cluster", {})
    members = [a for a in raw["agents"] if a["role"] != "general" and not a.get("team")]  # the Lumen team is apart
    mode = cl.get("mode") or ("advanced" if any(a["role"] == "head_dispatch" for a in members) else "basic")
    if mode == "collab":
        mode = "advanced"
    return mode, len(members)


def nearest(mode: str, count: int) -> int:
    options = sizes(mode)
    return min(options, key=lambda n: (abs(n - count), -n))


def draft(raw: dict, mode: str, count: int, *, parallel: bool = True, foresight: dict | None = None) -> dict:
    """A new raw configuration with the roster of ``mode`` at ``count`` agents."""
    if mode not in MODES or count not in sizes(mode):
        raise ValueError(f"{count} agents is not a size of {mode}: {sizes(mode)}")
    result = copy.deepcopy(raw)
    crew = [a for a in result["agents"] if a.get("team")]  # the Lumen team stays as it is (agents/team.py)
    old = [a for a in result["agents"] if not a.get("team")]
    singles = [a for a in old if a["role"] == "general"]
    pool = [a for a in old if a["role"] != "general"]
    taken: set[str] = set()
    all_ids = {a["id"] for a in old}
    template = {r: next((a for a in reversed(pool) if a["role"] == r and a.get("model")), None)
                for r in ("head_dispatch", "head_logic", "worker", "guardian")}

    def new_id(prefix: str, bare: bool) -> str:
        used = all_ids | taken
        if bare and prefix not in used:
            return prefix  # 'head-dispatch', 'head-logic'
        n = 1
        while f"{prefix}-{n}" in used:
            n += 1
        return f"{prefix}-{n}"

    def take(role: str, prefix: str) -> dict:
        found = next((a for a in pool if a["role"] == role and a["id"] not in taken), None)
        if found is not None:
            agent = copy.deepcopy(found)
        else:
            agent = {"id": new_id(prefix, bare=prefix.startswith("head-")), "role": role, "endpoint": "", "model": ""}
            src = template.get(role)
            for key in ("context_budget_tokens", "params", "memory"):  # settings that are not a model choice
                if src and key in src:
                    agent[key] = copy.deepcopy(src[key])
        agent.pop("supervises", None)
        agent.pop("supervises_workers", None)
        taken.add(agent["id"])
        return agent

    cluster: list[dict] = []
    s = shape(mode, count)
    if s["heads"]:
        cluster += [take("head_dispatch", "head-dispatch"), take("head_logic", "head-logic")]
    per = 2 if mode == "small" else 1
    for _ in range(s["guardians"]):
        workers = [take("worker", "worker") for _ in range(per)]
        guardian = take("guardian", "guardian")
        if mode == "small":
            guardian["supervises_workers"] = [w["id"] for w in workers]
        else:
            guardian["supervises"] = workers[0]["id"]
        cluster += [*workers, guardian]
    if not singles and mode == "basic":
        singles = [{"id": new_id("doctor", bare=True), "role": "general", "endpoint": "", "model": ""}]
    result["agents"] = singles + cluster + crew

    policy = {k: v for k, v in result.get("cluster", {}).items() if k == "foresight"}
    if mode in ("basic", "dual"):
        result["cluster"] = {"mode": mode}
    else:
        policy.update(enabled=True, mode=mode, max_agents=MAX_CLUSTER, parallel=parallel)
        if foresight is not None:
            policy["foresight"] = {**policy.get("foresight", {}), **foresight}
        result["cluster"] = policy
    return result
