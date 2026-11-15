"""The big cluster's strategy for changing code (the user's design, 2026-10-31; ADR 0016 item 14).

Real Flash runs: 20 agents splitting coupled code by files fixed 19/37 bugs where one pair (双人互检) fixed 36/37. More
agents only help if they cannot make the pair worse. So, with 2 heads and N worker/guardian pairs:
- the MAIN pair fixes the whole coupled chain in the project, with about the budget a pair alone would have - by
  itself it is a 双人互检 run, the floor;
- most other pairs are SCOUTS: the worker writes one test per business scenario the dispatch head names (no business
  code). The system runs each new scout test against the ORIGINAL code too: a test that passes there does not
  reproduce anything and the scout is told so once. A failing scout test is a bug found;
- two BACKUP pairs fix what the scouts found: the system hands each failing scout test to an idle backup pair, which
  fixes it in the project next to the main pair (exact-match edits cannot clobber each other). The main pair is told
  too, and who is on it.
The heads only name scenarios and pass on what they see across findings; together they spend at most 10%.
Measured before the backups (2026-10-31): two alternate pairs fixing their own copies lost every comparison to the main
version and spent 28% of the budget, while four bugs the scouts had found in one run stayed unfixed.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

from codedoctor.agents import orchestration as orch

MAIN_SHARE = 0.51        # of the investigation budget, for the main pair (a 双人互检 run of the same budget gets ~0.5)
BACKUPS_SHARE = 0.25     # for every backup task together
SCOUTS_SHARE = 0.14      # split between the scout workers (their tests are checked by the system, not reviewed)
HEAD_SHARE = 0.07        # the dispatch head; a logic-head consult gets CONSULT_SHARE (together at most 10%)
CONSULT_SHARE = 0.03
REVIEW_PART = 0.3        # of a task's share, for its guardian's review
MAX_BACKUPS = 2
FILES_PER_BACKUP_TASK = 2

_dispatch_lock = threading.Lock()


def _pairs(config) -> list[tuple[str, str]]:
    """(worker, guardian) in the user's configuration order."""
    out = []
    for a in config.agents.values():
        if a.role == "worker":
            g = orch.guardian_for(config, a.id)
            if g:
                out.append((a.id, g))
    return out


def applies(config) -> bool:
    heads = any(a.role == "head_dispatch" for a in config.agents.values())
    return (config.cluster.enabled and config.cluster.squad and heads and config.permissions.write_files
            and bool(config.permissions.test_command) and len(_pairs(config)) >= 2)


def layout(config) -> dict:
    """With few pairs (6 agents: two) there is no pair to spare for backups: the scouts become the backups once their
    tests are written (a backup task waits until its worker is free)."""
    pairs = _pairs(config)
    n_backup = min(MAX_BACKUPS, max(0, len(pairs) - 2))
    scouts = pairs[1 + n_backup:]
    return {"main": pairs[0], "backups": pairs[1:1 + n_backup] or scouts[:MAX_BACKUPS], "scouts": scouts}


def original_dir(services, root_task: str) -> Path:
    return Path(services.config.data_dir) / "squad" / root_task / "original"


def _copy_project(src: Path, dest: Path) -> None:
    from codedoctor.agents.tools import SKIP_DIRS

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest, ignore=lambda d, names: [n for n in names if n in SKIP_DIRS or n.startswith(".")
                                                       or n.endswith((".pyc", ".cd-tmp"))])


def start(services, head_task: dict, head_id: str) -> str:
    """Start the main pair at once (no head tokens), keep a copy of the code as it was, and tell the head its jobs."""
    from codedoctor.agents import ownership, prompts

    cfg = services.config
    lay = layout(cfg)
    root = Path(cfg.root)
    task_id = head_task["task_id"]
    if not original_dir(services, task_id).exists():
        _copy_project(root, original_dir(services, task_id))
    files = ownership.code_files(root)[:200]
    if not any(orch.body_of(c).get("squad") == "main" for c in orch.children(services, task_id)):
        # what is left of the message limit after the task and the rules (the outline takes up to 12000 more)
        room = orch.MAX_INSTRUCTIONS - len(head_task["instructions"]) - len(prompts.SQUAD_MAIN) - 16000
        brief = ownership.briefing(root, files, max_chars=max(4000, min(40000, room)), focus=head_task["instructions"])
        orch.create_subtask(services, sender=head_id, recipient=lay["main"][0], title=head_task["title"][:200],
                            instructions=head_task["instructions"] + "\n\n" + prompts.SQUAD_MAIN
                            + ("\n\n" + prompts.wrap_untrusted("project files", brief) if brief else ""),
                            parent_task_id=task_id, data_class=cfg.code_data_class,
                            extra={"files": files or ["."], "squad": "main", "share": MAIN_SHARE})
    text = prompts.squad_head(main=lay["main"][0], backups=[w for w, _ in lay["backups"]], scouts=len(lay["scouts"]))
    readme = next((p for p in sorted(root.glob("README*")) if p.is_file()), None)
    if readme is not None:
        text += "\n\nThe project's README (its business rules):\n" + prompts.wrap_untrusted(
            readme.name, readme.read_bytes().decode("utf-8", errors="replace")[:8000])
    return text


def scout_tasks(services, head_task_id: str, head_id: str, scenarios: list[dict], spec: str) -> list[dict]:
    """One task per scout worker, the scenarios dealt out in turn."""
    from codedoctor.agents import ownership, prompts

    cfg = services.config
    scouts = [w for w, _ in layout(cfg)["scouts"]]
    if not scouts:
        return []
    deals: dict[str, list[dict]] = {w: [] for w in scouts}
    for i, sc in enumerate(scenarios):
        deals[scouts[i % len(scouts)]].append(sc)
    outline = ownership.outline(Path(cfg.root), ownership.code_files(Path(cfg.root)), max_chars=10000)
    made = []
    for w, mine in deals.items():
        if not mine:
            continue
        lines = [f"{n}. {sc['title']}: {sc.get('check', '')}".rstrip(": ") for n, sc in enumerate(mine, 1)]
        sub = orch.create_subtask(services, sender=head_id, recipient=w, title=mine[0]["title"][:200],
                                  instructions=prompts.SQUAD_SCOUT + "\n\nYour scenarios:\n" + "\n".join(lines)
                                  + "\n\nThe task as the user gave it (the spec, with the README):\n"
                                  + prompts.wrap_untrusted("task", spec[:6000])
                                  + "\n\n" + prompts.wrap_untrusted("project outline", outline),
                                  parent_task_id=head_task_id, data_class=cfg.code_data_class,
                                  extra={"squad": "scout", "share": SCOUTS_SHARE / len(scouts)})
        made.append({"task_id": sub["task_id"], "agent": w, "scenarios": [sc["title"] for sc in mine]})
    return made


# --- live notes: what reaches a running task between its steps ----------------------------------------------------------

def post_note(services, task_id: str, text: str) -> None:
    services.__dict__.setdefault("_live_notes", {}).setdefault(task_id, []).append(text)


def take_notes(services, task_id: str) -> list[str]:
    return services.__dict__.setdefault("_live_notes", {}).pop(task_id, [])


def fixers(services, root_task: str) -> list[dict]:
    """The main and backup tasks of this investigation and their guardians' reviews, not finished yet."""
    out = []
    for t in orch.tree(services, root_task):
        row = orch.task_row(services, t)
        if not row or row["state"] == "finished":
            continue
        if orch.body_of(row).get("squad") in ("main", "backup"):
            out.append({"id": t, "agent": row["agent"]})
    return out


def _state(services, root_task: str) -> dict:
    """Per investigation: scout test files, which backup task has which file, and the backup share handed out."""
    return services.__dict__.setdefault("_squad", {}).setdefault(root_task, {"scout_tests": set(), "assigned": {},
                                                                            "share_used": 0.0})


def scout_tests(services, root_task: str) -> set[str]:
    return set(_state(services, root_task)["scout_tests"])


def assigned(services, root_task: str) -> dict[str, str]:
    """scout test file -> the backup task fixing it."""
    return dict(_state(services, root_task)["assigned"])


def scout_found(services, root_task: str, scout_task: str, test_file: str, failing: set[str], why: str) -> int:
    """A scout's test fails: an idle backup pair gets it now, and the main pair is told who is on it."""
    _state(services, root_task)["scout_tests"].add(test_file)
    dispatch_backups(services, root_task)
    owner = assigned(services, root_task).get(test_file)
    owner = owner if owner and not owner.startswith("done:") else None
    scout_row = orch.task_row(services, scout_task) or {}
    services.journal.append("system", "state_change", {
        "state": "scout_found", "test_file": test_file, "failing": sorted(failing)[:20], "scout": scout_row.get("agent"),
        "backup_task": owner, "backup": (orch.task_row(services, owner) or {}).get("agent") if owner else None},
        task_id=root_task)
    who = (f"Backup {orch.task_row(services, owner)['agent']} ({owner}) is fixing it in parallel: leave it unless your "
           "own fix covers it." if owner else "Fix the defect behind it.")
    told = 0
    for f in fixers(services, root_task):
        if f["id"] == owner:
            continue
        post_note(services, f["id"], (
            f"[Code Doctor] A scout ({scout_task}) wrote {test_file} and it FAILS - a bug the scenario describes:\n- "
            + "\n- ".join(sorted(failing)[:10]) + f"\n{why}\n{who} If the test itself contradicts the README or the task, "
            "do not change your code for it - say so in one line."))
        told += 1
    return told


def still_failing(services, root_task: str) -> dict[str, set[str]]:
    """Scout test files that fail in the last test run of the project -> their failing tests."""
    from codedoctor.agents import testrun

    last = testrun.last(services)
    files = scout_tests(services, root_task)
    out: dict[str, set[str]] = {}
    for f in (last.failed if last else set()):
        path = f.split("::", 1)[0]
        if path in files:
            out.setdefault(path, set()).add(f)
    return out


def dispatch_backups(services, root_task: str, finishing: str | None = None) -> list[str]:
    """Give scout test files that still fail and nobody fixes to idle backup workers, while the backups' share lasts.
    `finishing`: the agent whose task is finishing right now - free, though its task is not marked finished yet (with
    6 agents the scout is the backup: real run, it was skipped as busy and nothing was dispatched). Returns task ids."""
    from codedoctor.agents import ownership, prompts

    cfg = services.config
    backups = [w for w, _ in layout(cfg)["backups"]]
    if not backups:
        return []
    with _dispatch_lock:
        st = _state(services, root_task)
        per_task = BACKUPS_SHARE / (len(backups) * 2)
        failing = still_failing(services, root_task)
        open_files = [f for f in sorted(failing) if f not in st["assigned"]]
        made = []
        for w in backups:
            if not open_files or st["share_used"] + per_task > BACKUPS_SHARE + 1e-9:
                break
            if orch.load(services, w) > (1 if w == finishing else 0):
                continue
            mine, open_files = open_files[:FILES_PER_BACKUP_TASK], open_files[FILES_PER_BACKUP_TASK:]
            tests = []
            for f in mine:
                try:
                    tests.append(f"=== {f} ===\n" + (Path(cfg.root) / f).read_bytes().decode("utf-8", errors="replace"))
                except OSError:
                    pass
            fails = sorted(t for f in mine for t in failing[f])
            outline = ownership.outline(Path(cfg.root), ownership.code_files(Path(cfg.root)), max_chars=8000)
            sub = orch.create_subtask(
                services, sender="system", recipient=w, title=("侦察发现：" + "、".join(f.rsplit("/", 1)[-1].removesuffix(".py").removeprefix("test_scout_")
                                                              for f in mine))[:200],
                instructions=prompts.SQUAD_BACKUP + "\n\nFailing scout tests:\n- " + "\n- ".join(fails[:20])
                + "\n\n" + prompts.wrap_untrusted("scout tests", "\n\n".join(tests)[:12000])
                + "\n\n" + prompts.wrap_untrusted("project outline", outline),
                parent_task_id=root_task, data_class=cfg.code_data_class,
                extra={"squad": "backup", "share": per_task, "files": mine})
            for f in mine:
                st["assigned"][f] = sub["task_id"]
            st["share_used"] += per_task
            made.append(sub["task_id"])
        if made:
            services.journal.append("system", "state_change", {"state": "backup_dispatch", "tasks": made,
                                                               "files": sorted(st["assigned"])[:50]}, task_id=root_task)
        return made


def release(services, root_task: str, task_id: str, finishing: str | None = None) -> None:
    """A backup task finished: what it was given and still fails may go to the next idle backup."""
    from codedoctor.agents import testrun

    st = _state(services, root_task)
    last = testrun.last(services)
    failing = {f.split("::", 1)[0] for f in (last.failed if last else set())}
    for f, owner in list(st["assigned"].items()):
        if owner == task_id and f in failing:
            st["assigned"][f] = f"done:{task_id}"  # tried once; not handed out again (it may be a wrong test)
    dispatch_backups(services, root_task, finishing)


def passes_on_original(services, root_task: str, test_file: str) -> bool | None:
    """Run a scout's test file against the code as it was before anyone changed it. True: it passes there too (it
    reproduces nothing); None: it could not be checked. No model tokens."""
    from codedoctor.agents import testrun

    orig = original_dir(services, root_task)
    src = Path(services.config.root) / test_file
    if not orig.exists() or not src.is_file():
        return None
    dest = orig / test_file
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    res = testrun.run(services, "system", root=orig)
    mine = [t for t in res.failed | res.passed if t.split("::", 1)[0] == test_file]
    if not mine:
        return None
    return not any(t.split("::", 1)[0] == test_file for t in res.failed)
