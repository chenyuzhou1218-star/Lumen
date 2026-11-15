"""Is a conclusion still about the current system? (hard requirement 6)

Code version: one id for the whole working tree, so every piece of evidence
collected from the same state shares it. A clean git checkout is its HEAD
commit; anything else is 'wt-<sha256>' over HEAD plus the content of every
changed or untracked file (or, outside git, over file names, sizes and times).

Staleness is decided as precisely as the evidence allows: a claim that cites
code excerpts is stale only when one of those excerpts no longer appears in its
file (edits elsewhere, or the excerpt merely moving, do not invalidate it). A
claim with no code excerpts falls back to comparing whole versions.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".codedoctor", ".mypy_cache", ".pytest_cache"}
_CODE_ID = re.compile(r"^ev:code:(?P<ver>[^:]+):(?P<path>[^:#@]+)(#[^@]+)?@(?P<sha>[0-9a-f]{64})(:L\d+(-L\d+)?)?$")


# On Windows, a GUI process (pythonw.exe) spawning a child without this flag flashes a
# console window for each call. snapshot_version runs on every evidence add, so without it
# an investigation fills the screen with flickering windows and stalls on their creation.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30, creationflags=_NO_WINDOW)


def snapshot_version(root: Path) -> str:
    root = Path(root)
    try:
        if not (root / ".git").exists():
            raise FileNotFoundError  # not a git checkout: skip the two git calls and hash the tree directly
        head = _git(root, "rev-parse", "HEAD")
        status = _git(root, "status", "--porcelain", "-z", "--untracked-files=all")
        if head.returncode == 0 and status.returncode == 0:
            commit = head.stdout.decode().strip()
            if not status.stdout.strip(b"\0"):
                return commit
            h = hashlib.sha256(b"HEAD " + commit.encode())
            entries = [e for e in status.stdout.decode("utf-8", "replace").split("\0") if e]
            for path in sorted(e[3:] for e in entries if len(e) > 3):
                p = root / path
                h.update(b"\0" + path.encode())
                h.update(hashlib.sha256(p.read_bytes()).digest() if p.is_file() else b"<deleted>")
            return "wt-" + h.hexdigest()
    except (OSError, subprocess.SubprocessError):
        pass
    h = hashlib.sha256(b"nogit")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            try:
                st = p.stat()
            except OSError:
                continue
            h.update(f"\0{p.relative_to(root).as_posix()}\0{st.st_size}\0{st.st_mtime_ns}".encode())
    return "wt-" + h.hexdigest()


def parse_code_id(ev_id: str) -> dict | None:
    m = _CODE_ID.match(ev_id)
    if not m:
        return None
    return {"version": m["ver"], "path": unquote(m["path"]), "sha256": m["sha"]}


def code_excerpt_current(services, ev_id: str) -> str | None:
    """None if the cited excerpt is still present verbatim in its file, else the reason it is not."""
    parsed = parse_code_id(ev_id)
    if parsed is None or services.evidence.check(ev_id) != "ok":
        return None  # a missing or tampered excerpt is an integrity failure, reported by validation, not staleness
    try:
        excerpt = services.evidence.content(ev_id).decode("utf-8")
    except Exception:
        return f"cannot read stored excerpt {ev_id}"
    path = services.config.root / parsed["path"]
    if not path.is_file():
        return f"{parsed['path']} no longer exists"
    current = path.read_bytes().decode("utf-8", errors="replace")
    if excerpt and excerpt not in current:
        return f"{parsed['path']} changed: the cited lines are no longer present"
    return None


def claim_staleness(services, claim: dict, current: dict) -> tuple[str, str] | None:
    """(rule, detail) if the claim no longer describes the current system, else None.

    `current` holds the versions known right now: code_version always; config_version and
    db_schema_version when the project provides them."""
    scope = claim["scope"]
    for key in ("config_version", "db_schema_version"):
        if scope.get(key) and current.get(key) and scope[key] != current[key]:
            return "stale_version", f"{key} changed from {scope[key]} to {current[key]}"
    code_refs = [r["id"] for r in claim.get("evidence", []) if r["id"].startswith("ev:code:")]
    if code_refs:
        reasons = [r for r in (code_excerpt_current(services, ev) for ev in code_refs) if r]
        return ("stale_code", "; ".join(reasons)) if reasons else None
    if scope["code_version"] != current["code_version"]:
        return "stale_version", f"code changed from {scope['code_version']} to {current['code_version']} and the claim cites no code excerpt that could show it is unaffected"
    return None


def stale_notes(services, notes: list[dict]) -> dict[str, str]:
    """note id -> reason, for notes whose cited code excerpts changed."""
    out = {}
    for n in notes:
        reasons = [r for r in (code_excerpt_current(services, ev) for ev in n.get("evidence", []) if ev.startswith("ev:code:")) if r]
        if reasons:
            out[n["id"]] = "; ".join(reasons)
    return out
