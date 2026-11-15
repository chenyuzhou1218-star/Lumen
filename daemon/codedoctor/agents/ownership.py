"""Who works on which file (ADR 0016). When a cluster changes code, the dispatch head hands out FILES: every code file
of the project gets exactly one worker, a worker changes only its own files (plus new tests), and the head cannot
finish while code files have no owner. Real run with 20 agents: the head left both web files unassigned and the two
bugs in them unfixed, while six of nine workers were never used."""

from __future__ import annotations

import os
import re
from pathlib import Path

from codedoctor.agents import orchestration as orch
from codedoctor.agents.tools import SKIP_DIRS

CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs", ".java", ".kt",
                 ".cs", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".swift", ".lua", ".gd", ".sql"}
ONE_WORKER_MAX = 30  # files: a coupled set larger than this is cut along directories
_TEST_DIRS = {"tests", "test", "__tests__", "spec"}


def is_test(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return bool(_TEST_DIRS & set(parts[:-1])) or name.startswith("test_") or ".test." in name or ".spec." in name


def code_files(root: Path, limit: int = 2000) -> list[str]:
    """Project code files a worker should own: not tests, not empty."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            rel = p.relative_to(root).as_posix()
            if p.suffix.lower() in CODE_SUFFIXES and not is_test(rel) and p.stat().st_size > 0:
                out.append(rel)
                if len(out) >= limit:
                    return out
    return out


def coupled_groups(services) -> list[list[str]]:
    """Code files joined by the coupling graph (calls, imports, events, shared state across files), largest first.
    Files in one group should go to one worker: split across workers, a changed interface in one file is not
    followed in the other (real run, 20 agents: orders.py called loyalty.redeem_value, which its owner never wrote)."""
    files = set(code_files(Path(services.config.root)))
    try:
        edges, nodes = services.graph._static().edges, services.graph._static().nodes
    except Exception:  # no graph: imports and shared URLs still join files
        edges, nodes = [], {}
    parent = {f: f for f in files}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def file_of(node_id):
        n = nodes.get(node_id)
        return n.path if n is not None and n.path in files else None

    for a, b in _imports(Path(services.config.root), files):  # the graph may not resolve `from pkg import mod`
        parent[find(a)] = find(b)
    for group in _shared_routes(Path(services.config.root), files).values():  # a page and the handler of its URL
        first, *rest = sorted(group)
        for f in rest:
            parent[find(f)] = find(first)
    holders: dict[str, set[str]] = {}  # an event / state / route / table: the files that touch it
    for e in edges:
        a, b = file_of(e.src), file_of(e.dst)
        if a and b and a != b:
            parent[find(a)] = find(b)
        elif a and not b:
            holders.setdefault(e.dst, set()).add(a)
        elif b and not a:
            holders.setdefault(e.src, set()).add(b)
    for group in holders.values():
        first, *rest = sorted(group)
        for f in rest:
            parent[find(f)] = find(first)
    comps: dict[str, list[str]] = {}
    for f in sorted(files):
        comps.setdefault(find(f), []).append(f)
    return sorted(comps.values(), key=lambda c: (-len(c), c))


_PY_FROM = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+([\w, ()]+)", re.M)
_PY_IMPORT = re.compile(r"^\s*import\s+([\w., ]+)", re.M)
_JS_IMPORT = re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(?|require\s*\()\s*['"](\.[^'"]+)['"]""")


def _imports(root: Path, files: set[str]):
    """(importing file, imported file) pairs inside the project, from the import statements themselves."""
    by_module = {}
    for f in files:
        if f.endswith(".py"):
            mod = f[:-3].replace("/", ".")
            by_module[mod.removesuffix(".__init__")] = f
    for f in files:
        try:
            text = (root / f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if f.endswith(".py"):
            for pkg, names in _PY_FROM.findall(text):
                for name in re.findall(r"\w+", names):
                    target = by_module.get(f"{pkg}.{name}") or by_module.get(pkg)
                    if target and target != f:
                        yield f, target
            for mods in _PY_IMPORT.findall(text):
                for mod in re.findall(r"[\w.]+", mods):
                    target = by_module.get(mod)
                    if target and target != f:
                        yield f, target
        else:
            for rel in _JS_IMPORT.findall(text):
                base = (Path(f).parent / rel).as_posix()
                for cand in (base, base + ".js", base + ".ts", base + ".jsx", base + ".tsx", base + "/index.js"):
                    norm = Path(cand).as_posix()
                    parts = []
                    for p in norm.split("/"):
                        if p == "..":
                            parts = parts[:-1]
                        elif p not in (".", ""):
                            parts.append(p)
                    target = "/".join(parts)
                    if target in files and target != f:
                        yield f, target
                        break


_ROUTE_LITERAL = re.compile(r"""(?:['"`]|\})(/[A-Za-z][\w-]*(?:/[\w{}:.$-]+)+)""")  # '}': `${API}/api/x`


def _shared_routes(root: Path, files: set[str]) -> dict[str, set[str]]:
    """URL paths ('/api/borrow') written in more than one file: the client that calls it and the server that handles
    it are coupled through the request's field names (real run: the page sent memberId, the API read member_id)."""
    by_route: dict[str, set[str]] = {}
    for f in files:
        try:
            text = (root / f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for route in set(_ROUTE_LITERAL.findall(text)):
            by_route.setdefault(route.split("?")[0].rstrip("/"), set()).add(f)
    return {r: fs for r, fs in by_route.items() if len(fs) > 1}


def plan(services, workers: int) -> list[dict]:
    """A file split for `workers` workers: coupled files stay together; a group too big for one worker is cut along
    directories (and its pieces are marked as coupled); small groups are packed by directory, so a big project is
    neither one giant job nor hundreds of single files (the user's game: 241 files, 225 groups without the graph)."""
    groups = coupled_groups(services)
    total = sum(len(g) for g in groups)
    if not total or workers <= 0:
        return []
    target = max(1, -(-total // workers))  # ceil
    units = []  # {"files", "dir", "coupled": group index or None}
    for gi, g in enumerate(groups):
        if len(g) <= max(target * 3 // 2, ONE_WORKER_MAX):  # coupled code stays whole unless one worker cannot cope
            units.append({"files": g, "dir": _top_dir(g), "coupled": gi if len(g) > 1 else None})
            continue
        by_dir: dict[str, list[str]] = {}
        for f in g:
            by_dir.setdefault(str(Path(f).parent), []).append(f)
        for d, fs in sorted(by_dir.items()):
            for i in range(0, len(fs), target):
                units.append({"files": fs[i:i + target], "dir": d, "coupled": gi})
    units.sort(key=lambda u: (u["dir"], -len(u["files"])))
    buckets = [{"files": [], "dirs": set(), "coupled": set()} for _ in range(min(workers, len(units)))]
    for u in units:
        same = [b for b in buckets if u["dir"] in b["dirs"] and len(b["files"]) + len(u["files"]) <= target]
        b = min(same or buckets, key=lambda b: len(b["files"]))
        b["files"] += u["files"]
        b["dirs"].add(u["dir"])
        if u["coupled"] is not None:
            b["coupled"].add(u["coupled"])
    return [b for b in buckets if b["files"]]


def _top_dir(files: list[str]) -> str:
    dirs = [str(Path(f).parent) for f in files]
    return max(set(dirs), key=dirs.count)


def describe_groups(services, workers: int = 0, limit_files: int = 400) -> str:
    groups = coupled_groups(services)
    if not groups:
        return ""
    multi = [g for g in groups if len(g) > 1]
    text = ("Coupled files (from imports, shared URLs and the coupling graph - they call each other or share "
            "events/state); keep each set with ONE worker where possible:\n"
            + ("\n".join(f"- {', '.join(g[:20])}" + (" ..." if len(g) > 20 else "") for g in multi[:20])
               or "- (no coupling found between files)"))
    if workers > 0:
        buckets = plan(services, workers)
        shown, lines = 0, []
        for i, b in enumerate(buckets):
            files = b["files"][: max(0, limit_files - shown)]
            shown += len(files)
            more = f" ... and {len(b['files']) - len(files)} more in {', '.join(sorted(b['dirs']))}" \
                if len(files) < len(b["files"]) else ""
            lines.append(f"- worker {i + 1} ({len(b['files'])} files): {', '.join(files)}{more}")
        cut = [gi for gi in range(len(groups)) if sum(gi in b["coupled"] for b in buckets) > 1]
        text += (f"\n\nSuggested split for your {workers} workers (delegate each line with files=[...]; adjust if you "
                 "know better):\n" + "\n".join(lines))
        if cut:
            text += ("\nSome coupled sets were too big for one worker and are split across several: tell those workers "
                     "which files of the others they call, so interfaces stay compatible.")
    return text


def normalize(root: Path, path: str) -> str:
    return (root / path).resolve().relative_to(root.resolve()).as_posix()


def files_of(task: dict) -> list[str]:
    return list(orch.body_of(task).get("files") or [])


def owners(services, root_task: str) -> dict[str, dict]:
    """file -> the most recent subtask that owns it (any state)."""
    out: dict[str, dict] = {}
    for child in orch.children(services, root_task):
        for f in files_of(child):
            out[f] = child
    return out


def conflicts(services, root_task: str, files: list[str]) -> dict[str, dict]:
    """Requested files already owned by an unfinished subtask of this investigation."""
    return {f: t for f, t in owners(services, root_task).items()
            if f in files and not orch.settled(services, t["id"])}


def unowned(services, root_task: str) -> list[str]:
    owned = set(owners(services, root_task))
    return [f for f in code_files(Path(services.config.root)) if f not in owned]


def foreign_note(services, task_id: str, rel: str) -> str:
    """A worker may change a file it does not own - an interface often has to change on both sides, and exact-match
    edits cannot clobber another worker's change. It is told whose file it is, so it keeps that worker's work."""
    row = orch.task_row(services, task_id) or {}
    files = files_of(row)
    if not files or rel in files or is_test(rel):
        return ""
    owner = owners(services, orch.root_of(services, task_id)).get(rel)
    if owner is None or owner["id"] == task_id:
        return ""
    return (f"\nNote: {rel} is {owner['agent']}'s file ({owner['id']}); keep its other changes intact and change only "
            "what your fix needs.")


_OUTLINE = re.compile(r"^(?:(?:async\s+)?def\s|class\s|    (?:async\s+)?def\s|[A-Z][A-Z0-9_]*\s*=|from\s|import\s|"
                      r"export\s|function\s|(?:const|let)\s+\w+\s*=\s*(?:async\s*)?(?:\(|function)|"
                      r"(?:app|router)\.(?:get|post|put|patch|delete)\()")


def outline(root: Path, files: list[str], max_chars: int = 12000, per_file: int = 40) -> str:
    """The shape of files without their bodies: imports, constants, classes, functions and routes, numbered."""
    out, used = [], 0
    for rel in files:
        try:
            lines = (Path(root) / rel).read_bytes().decode("utf-8", errors="replace").splitlines()
        except OSError:
            continue
        sig = [f"{n:>5}| {ln.rstrip()[:160]}" for n, ln in enumerate(lines, 1) if _OUTLINE.match(ln)][:per_file]
        block = f"--- {rel} ({len(lines)} lines)\n" + "\n".join(sig)
        if used + len(block) > max_chars:
            out.append(f"(more files not outlined: {', '.join(files[files.index(rel):][:40])})")
            break
        out.append(block)
        used += len(block)
    return "\n".join(out)


def by_relevance(root: Path, files: list[str], focus: str) -> list[str]:
    """Files the task names first (their path or file name), then files holding the identifiers it mentions
    (`backticked` words, snake_case names), then the rest - in a big project (a real run: qutebrowser, 200 files) the
    file a bug report is about must not be left out for files that came first in the alphabet."""
    import re

    if not focus:
        return list(files)
    text = focus.replace("\\", "/")
    words = {w for w in re.findall(r"`([A-Za-z_][\w.]{2,})`", text)} | {w for w in re.findall(r"\b[a-z]+_[a-z_]+\b", text) if len(w) > 4}
    def score(rel):
        name = rel.rsplit("/", 1)[-1]
        if rel in text or (len(name) > 6 and name in text):
            return 0
        if words:
            try:
                body = (Path(root) / rel).read_bytes().decode("utf-8", errors="replace")
            except OSError:
                return 2
            if any(w.split(".")[-1] in body for w in words):
                return 1
        return 2
    return sorted(files, key=score)


def briefing(root: Path, files: list[str], max_chars: int = 40000, focus: str = "") -> str:
    """A worker's own files as they are now (exact text, for edit_file) and an outline of the other code files.
    `focus`: the task's text - the files it is about come first."""
    own, used, left = [], 0, []
    files = by_relevance(root, files, focus)
    for rel in files:
        try:
            text = (Path(root) / rel).read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
        except OSError:
            continue
        if used + len(text) > max_chars:
            left.append(rel)
            continue
        own.append(f"=== {rel} ===\n{text.rstrip()}")
        used += len(text)
    others = [f for f in code_files(Path(root)) if f not in set(files)]
    parts = []
    if own:
        parts.append("YOUR FILES as they are now (exact text - copy from here for edit_file; do not read_file them "
                     "again unless an edit is refused):\n" + "\n\n".join(own))
    if left:
        more = f" ... and {len(left) - 25} more (list_dir shows them)" if len(left) > 25 else ""
        parts.append("Too large to include, read them with read_file: " + ", ".join(left[:25]) + more)
    if others:
        parts.append("THE OTHER CODE FILES, outline only (line numbers; read_file a range only when you need the "
                     "body of something you call or that calls you):\n" + outline(root, others))
    return "\n\n".join(parts)
