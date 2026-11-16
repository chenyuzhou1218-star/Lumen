"""Tools an agent can call. Each tool validates its arguments, stays inside the
project root and the user's permissions, and turns what it read into registered
evidence so the agent can cite it."""

from __future__ import annotations

import asyncio
import inspect
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from codedoctor.evidence.registry import EvidenceError
from codedoctor.claims import ClaimRejected
from codedoctor.currency import stale_notes
from codedoctor.memory import related as related_memory
from codedoctor.memory.notes import MemoryError_, Recalled, allowed_notes
from codedoctor.models.base import ToolSpec

MAX_READ_LINES = 400
MAX_OUTPUT_CHARS = 12000
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".codedoctor", ".mypy_cache", ".pytest_cache"}
# Shell operators: run_command has no shell, so outside quotes they would only confuse the program it runs.
_SHELL_OPERATORS = {"|", "||", "&", "&&", ";", ">", ">>", "<", "2>", "2>&1", "`"}


@dataclass
class ToolResult:
    ok: bool
    content: str
    external: bool = False  # content came from outside Code Doctor -> shown to the model as untrusted data
    evidence: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    data_class: str = "public"
    progress: bool | None = None  # explicit progress signal (e.g. wait_for got new results); None = judge by novelty
    images: list[str] = field(default_factory=list)  # image evidence ids shown to the model after the tool results


@dataclass
class ToolContext:
    services: "Services"  # noqa: F821
    agent_id: str
    role: str
    task_id: str
    model: dict
    call_entry_id: str  # journal entry of this tool call; used as the source of memory notes
    thread_id: str
    known_agents: set[str]
    data_class: str = "internal"  # strictest data in the task's context so far; notes and queries derived from it are as sensitive
    max_output_chars: int | None = None  # set from the agent's context budget (ADR 0008); None: MAX_OUTPUT_CHARS, read_file by lines only
    root: Any = None  # the task's work folder when it is not the project (an alternate pair's copy, ADR 0016 item 14)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[ToolContext, dict], ToolResult]
    effect_class: str | None = None  # None = read-only; "internal" / "external" calls go through the side-effect ledger
    retry_safe: bool = True
    check_args: bool = True  # False: the handler reshapes and validates the arguments itself (submit_claim)

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters)


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def root_of(ctx: ToolContext) -> Path:
    return Path(ctx.root) if ctx.root else ctx.services.config.root


def _safe_path(ctx: ToolContext, rel: str) -> tuple[Path, str]:
    root = root_of(ctx).resolve() if ctx.root else ctx.services.config.root
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        from codedoctor import outside  # the user's folders and other drives (asked first: asking.classify "outside")

        if outside.allowed(p):  # "C:\Users\me\Desktop\x" or "..\x": the user's folders and other drives
            return p, str(p)
        raise PermissionError(f"path {rel!r} is outside the project root, and not a place agents may use")
    return p, p.relative_to(root).as_posix() if p != root else "."


def _limit(ctx: ToolContext) -> int:
    return ctx.max_output_chars or MAX_OUTPUT_CHARS


def _err(msg: str) -> ToolResult:
    return ToolResult(ok=False, content=f"ERROR: {msg}")


# --- file tools ----------------------------------------------------------------

def list_dir(ctx: ToolContext, args: dict) -> ToolResult:
    p, rel = _safe_path(ctx, args.get("path", "."))
    if not p.is_dir():
        return _err(f"{rel} is not a directory")
    entries = []
    for child in sorted(p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
        if child.name in SKIP_DIRS:
            continue
        entries.append(child.name + ("/" if child.is_dir() else f"  ({child.stat().st_size} bytes)"))
    return ToolResult(ok=True, content=f"{rel}/\n" + "\n".join(entries[:500]), external=True, data_class=_code_class(ctx))


def _code_class(ctx: ToolContext) -> str:
    return ctx.services.config.code_data_class


def read_file(ctx: ToolContext, args: dict) -> ToolResult:
    p, rel = _safe_path(ctx, args["path"])
    if not p.is_file():
        return _err(f"{rel} is not a file")
    total = len(p.read_bytes().decode("utf-8", errors="replace").splitlines())
    start = max(1, args.get("start_line", 1))
    end = min(total, args.get("end_line", start + MAX_READ_LINES - 1), start + MAX_READ_LINES - 1)
    if total == 0:
        return ToolResult(ok=True, content=f"{rel} is empty", external=True)
    if start > total:
        return _err(f"{rel} has only {total} lines")
    if end < start:
        return _err("end_line is before start_line")
    if ctx.max_output_chars:
        lines = p.read_bytes().decode("utf-8", errors="replace").splitlines()
        used, last = 0, start
        for n in range(start, end + 1):
            used += len(lines[n - 1]) + 8  # line number prefix
            if used > ctx.max_output_chars and n > start:
                break
            last = n
        end = last
    ev_id, excerpt = ctx.services.evidence.add_code_excerpt(
        root_of(ctx), rel, start, end, agent_id=ctx.agent_id, data_class=_code_class(ctx)
    )
    numbered = "\n".join(f"{n:>5}| {line}" for n, line in enumerate(excerpt.splitlines(), start))
    more = f"\n... ({total - end} more lines; call read_file with start_line={end + 1})" if end < total else ""
    return ToolResult(
        ok=True,
        content=f"evidence: {ev_id}\nfile: {rel} lines {start}-{end} of {total}\n{numbered}{more}",
        external=True,
        evidence=[ev_id],
        data_class=_code_class(ctx),
    )


def search_text(ctx: ToolContext, args: dict) -> ToolResult:
    base, rel_base = _safe_path(ctx, args.get("path", "."))
    query = args["query"]
    try:
        pattern = re.compile(query if args.get("regex") else re.escape(query), re.IGNORECASE)
    except re.error as e:
        return _err(f"bad regex: {e}")
    glob = args.get("glob")
    limit = min(args.get("max_results", 50), 200)
    hits: list[str] = []
    root = root_of(ctx)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            fp = Path(dirpath) / fn
            if glob and not fp.match(glob):
                continue
            try:
                data = fp.read_bytes()
            except OSError:
                continue
            if len(data) > 2_000_000 or b"\0" in data[:8192]:
                continue
            for n, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{fp.relative_to(root).as_posix()}:{n}: {line.strip()[:200]}")
                    if len(hits) >= limit:
                        break
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break
    body = "\n".join(hits) if hits else "(no matches)"
    if len(body) > _limit(ctx):
        body = body[:_limit(ctx)] + f"\n...(truncated to fit the context budget; narrow the search with path or glob)"
    note = "\n(search results are pointers; use read_file to get citable evidence)"
    return ToolResult(ok=True, content=f"search {query!r} in {rel_base}: {len(hits)} hits\n{body}{note}", external=True,
                      data_class=_code_class(ctx))


def run_command(ctx: ToolContext, args: dict) -> ToolResult:
    command = args["command"].strip()
    # Any command (the user, 2026-11-14: "删掉任何的权限"): no allowlist and no switch. Whether the user is asked first is
    # their 批准方式 (agents/asking.py): 全部问我 asks every one, 帮我审查 the ones that delete, 完全放开 none.
    # No shell (real run: 38 of 47 commands were multi-line `python -c` scripts refused for their newlines). The
    # command is split into arguments and run directly, so quoted newlines and semicolons are just text; shell
    # operators outside quotes are refused because nothing would interpret them.
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as e:
        return _err(f"cannot parse the command: {e}")
    if not argv:
        return _err("empty command")
    if any(a in _SHELL_OPERATORS or a.startswith(("|", ">", "<")) for a in argv):
        # pipes, chaining, redirection: a real shell runs it (PowerShell on Windows), never refused (the user, 2026-11-14)
        argv = (["powershell", "-NoProfile", "-NonInteractive", "-Command", command] if os.name == "nt"
                else ["/bin/sh", "-c", command])
    try:
        proc = subprocess.run(argv, shell=False, cwd=root_of(ctx), capture_output=True,
                              timeout=args.get("timeout_s", 120),
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError as e:  # not a program: a shell command (dir, del, Get-ChildItem ...), so the shell runs it
        try:
            proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command] if os.name == "nt"
                                  else ["/bin/sh", "-c", command], shell=False, cwd=root_of(ctx), capture_output=True,
                                  timeout=args.get("timeout_s", 120), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            return _err("command timed out")
        except OSError:
            return _err(f"cannot run it: {e}")
    except subprocess.TimeoutExpired:
        return _err("command timed out")
    out = (proc.stdout + b"\n--- stderr ---\n" + proc.stderr).decode("utf-8", errors="replace")
    code = proc.returncode
    if code != 0 and os.name == "nt" and _needs_admin(out):
        # Windows itself refused (C:\Windows\Temp, Program Files ...): run it again as administrator. Windows shows its own
        # "允许此应用对你的设备进行更改吗？" and the user decides there (the user, 2026-11-14: 加上).
        code, out = run_as_admin(command, str(root_of(ctx)), args.get("timeout_s", 300))
    # a run against the code as it is now: test evidence, so a claim can be 'reproduced' or a fix verified
    ev_id = ctx.services.evidence.add_test_run(root_of(ctx), command, code, out,
                                               agent_id=ctx.agent_id, data_class=_code_class(ctx))
    shown = out if len(out) <= _limit(ctx) else "...(truncated, full output in evidence)...\n" + out[-_limit(ctx):]
    return ToolResult(ok=True, content=f"evidence: {ev_id}\nexit code: {code}\n{shown}", external=True,
                      evidence=[ev_id], data_class=_code_class(ctx))


_ADMIN_WORDS = ("access is denied", "access to the path", "unauthorizedaccess", "permissiondenied", "拒绝访问", "访问被拒绝",
                "requires elevation", "需要提升", "administrator")


def _needs_admin(output: str) -> bool:
    text = output.casefold()
    return any(w in text for w in _ADMIN_WORDS)


def run_as_admin(command: str, cwd: str, timeout: float = 300) -> tuple[int, str]:
    """The command again in an administrator PowerShell: Windows asks the user first (UAC). (exit code, output)."""
    import shutil
    import tempfile
    import uuid

    # A folder that takes the temp folder's own permissions (the user may read what is in it), not mkdtemp's: its folder
    # is for its owner only, and the log the administrator's PowerShell wrote there is owned by Administrators - the user's
    # Lumen could not read what the command printed (the user's UAC test, 2026-11-15: "ran as administrator", and nothing).
    work = Path(tempfile.gettempdir()) / f"lumen-admin-{uuid.uuid4().hex[:10]}"
    work.mkdir()
    script, log = work / "run.ps1", work / "out.txt"
    body = (f"Set-Location -LiteralPath '{cwd.replace(chr(39), chr(39) * 2)}'\n"
            f"$code = 0\ntry {{ & {{ {command} }} *>&1 | Out-File -LiteralPath '{log}' -Encoding utf8; $code = $LASTEXITCODE }}\n"
            f"catch {{ $_ | Out-File -LiteralPath '{log}' -Encoding utf8 -Append; $code = 1 }}\nif ($null -eq $code) {{ $code = 0 }}\nexit $code\n")
    script.write_text(body, encoding="utf-8-sig")
    launch = ("try { $p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
              f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','\"{script}\"'; exit $p.ExitCode }} "
              "catch { Write-Output 'the user did not allow administrator rights (UAC)'; exit 1223 }")
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", launch], capture_output=True,
                              timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return 1, "ran as administrator, but it did not finish in time"
    said = proc.stdout.decode("utf-8", errors="replace")
    try:
        said = log.read_text(encoding="utf-8-sig", errors="replace") + said
    except FileNotFoundError:
        pass
    except OSError as e:  # never silently: a run whose output cannot be read is said to be so
        said = f"(what the command printed could not be read: {e})\n" + said
    shutil.rmtree(work, ignore_errors=True)
    if proc.returncode == 1223:
        return 1223, "Windows asked for administrator rights and the user said no. " + said
    return proc.returncode, "(ran as administrator)\n" + said


# --- evidence, memory, claims, messages -------------------------------------------

def read_evidence(ctx: ToolContext, args: dict) -> ToolResult:
    ev = ctx.services.evidence
    rec = ev.get(args["id"])
    if rec is None:
        return _err(f"unknown evidence id {args['id']}")
    if ev.check(args["id"]) != "ok":
        return _err(f"evidence {args['id']} failed its integrity check")
    text = ev.content(args["id"]).decode("utf-8", errors="replace")
    limit = args.get("max_chars", _limit(ctx))
    shown = text if len(text) <= limit else text[:limit] + "\n...(truncated)"
    return ToolResult(ok=True, content=f"evidence: {args['id']} ({rec['kind']}, {rec['content']['size_bytes']} bytes)\n{shown}",
                      external=rec["content_trust"] == "untrusted", data_class=rec["data_class"])


def remember(ctx: ToolContext, args: dict) -> ToolResult:
    for ev_id in args.get("evidence", []):
        if ctx.services.evidence.check(ev_id) != "ok":
            return _err(f"evidence {ev_id} is not registered or not intact")
    try:
        note = ctx.services.notes.write(
            owner=ctx.agent_id,
            scope=args.get("scope", "agent"),
            kind=args.get("kind", "fact"),
            text=args["text"],
            entities=args.get("entities"),
            evidence=args.get("evidence"),
            sources=[ctx.call_entry_id],
            task_id=ctx.task_id,
            pinned=args.get("pinned", False),
            data_class=ctx.data_class,
        )
    except MemoryError_ as e:
        return _err(str(e))
    return ToolResult(ok=True, content=f"remembered as {note['id']}", notes=[note["id"]])


async def recall(ctx: ToolContext, args: dict) -> ToolResult:
    agent_cfg = ctx.services.config.agents.get(ctx.agent_id)
    shared = agent_cfg.shared_read if agent_cfg else True
    found = await related_memory.recall_async(ctx.services, args["query"], reader=ctx.agent_id, data_class=ctx.data_class,
                                              k=min(args.get("k", 8), 50), include_shared=shared,
                                              follow_coupling=args.get("follow_coupling", True))
    conf = ctx.services.config
    ceiling = conf.endpoints[agent_cfg.primary.endpoint].max_data_class if agent_cfg else conf.code_data_class
    found, withheld, noted = allowed_notes(found, conf.code_data_class, ceiling)
    note = (f"\n({len(withheld)} matching notes left out: their data class is above what your model endpoint may "
            f"receive ('{ceiling}').)") if withheld else ""
    if not found:
        return ToolResult(ok=True, content="(no matching memory)" + note)
    return ToolResult(ok=True, content=format_recalled(ctx.services, found) + note, external=True, data_class=noted)


def format_recalled(services, found: list[Recalled], max_chars: int | None = None) -> str:
    """One entry per note: id, kind, date, the live state of the claims behind it, staleness of its code
    evidence, the text, and - for notes reached through the coupling graph - the coupling that reached it.
    With `max_chars` (ADR 0008) long notes are shortened (read_note shows them in full) and notes that do
    not fit are left out, best first."""
    stale = stale_notes(services, [r.note for r in found])
    note_chars = min(2000, max(300, max_chars // 4)) if max_chars else None
    lines, used = [], 0
    for k, r in enumerate(found):
        n = r.note
        flags = "".join(f" [{f}]" for f in r.flags)
        if n["id"] in stale:
            flags += f" [POSSIBLY OUTDATED: {stale[n['id']]}]"
        refs = ", ".join(n.get("evidence", [])[:8]) + (f" and {len(n['evidence']) - 8} more" if len(n.get("evidence", [])) > 8 else "")
        text = n["text"]
        if note_chars and len(text) > note_chars:
            text = text[:note_chars] + f"...(shortened from {len(n['text'])} chars; read_note {n['id']} for all of it)"
        line = f"- [{n['id']} {n['kind']} {n['created_at'][:10]}]{flags} {text}" + (f"  (evidence: {refs})" if refs else "")
        if r.via:
            line += f"\n  (recalled through coupling: {r.via})"
        if r.meaning:
            line += f"\n  (close in meaning to the query: {r.meaning:.2f})"
        if max_chars and lines and used + len(line) > max_chars:
            lines.append(f"({len(found) - k} more matching notes not shown, to fit the context budget; use recall to search)")
            break
        used += len(line) + 1
        lines.append(line)
    return "\n".join(lines)


def read_note(ctx: ToolContext, args: dict) -> ToolResult:
    note = ctx.services.notes.get(args["id"])
    agent_cfg = ctx.services.config.agents.get(ctx.agent_id)
    shared = agent_cfg.shared_read if agent_cfg else True
    if note is None or not (note["owner"] == ctx.agent_id or (shared and note["scope"] == "project")):
        return _err(f"no note {args['id']} that you may read")
    [r] = [Recalled(note, 0.0, _note_flags(ctx.services, note))]
    meta = [f"sources: {', '.join(note['sources'])}"]
    if note.get("entities"):
        meta.append(f"entities: {', '.join(note['entities'])}")
    if note.get("superseded_by"):
        meta.append(f"superseded by {note['superseded_by']}")
    return ToolResult(ok=True, content=format_recalled(ctx.services, [r]) + "\n" + "\n".join(meta), external=True,
                      data_class=note.get("data_class", ctx.services.config.code_data_class))


def _note_flags(services, note: dict) -> list[str]:
    from codedoctor.memory.notes import _flags

    return _flags(note.get("claims", []), services.notes.claim_states(note.get("claims", [])))


def submit_claim(ctx: ToolContext, args: dict) -> ToolResult:
    from codedoctor.agents import claim_input

    author = {"kind": "agent", "id": ctx.agent_id, "role": ctx.role, "model": ctx.model, "task_id": ctx.task_id}
    try:
        draft = claim_input.parse(claim_input.unwrap(args))
    except ValueError as e:
        return _err(f"claim is not a JSON object: {e}")
    try:
        nodes = ctx.services.graph._static().nodes
    except Exception:  # no graph yet: shorthand for files still works, suggestions are empty
        nodes = {}
    draft, reshaped = claim_input.normalize(draft, ctx.services.config.name, nodes, ctx.services.config.root)
    try:
        claim = ctx.services.claims.submit(draft, author=author)
    except ClaimRejected as e:
        return _err("claim rejected:\n- " + "\n- ".join(claim_input.explain(e.problems, draft, nodes)))
    text = f"claim accepted as {claim['id']} (status proposed)"
    if reshaped:
        text += "\nreshaped before validation:\n- " + "\n- ".join(reshaped)
    return ToolResult(ok=True, content=text, claims=[claim["id"]])


def _claim_status_text(result: dict) -> str:
    text = f"{result['claim_id']}: {result['before']} -> {result['status']}" if result["changed"] else f"{result['claim_id']}: {result['status']}"
    if result["missing"]:
        text += "\nnot (yet) supported because:\n- " + "\n- ".join(result["missing"])
    return text


def review_claim(ctx: ToolContext, args: dict) -> ToolResult:
    from codedoctor import claim_rules

    own = ctx.services.claims.get(args["claim_id"])
    if own and own["author"]["id"] == ctx.agent_id:
        # not an error to report: a real guardian re-reviewed its own finding, was refused, and filed that as an anomaly
        return ToolResult(ok=True, content=f"{args['claim_id']} is your own claim: it needs no review from you (someone else "
                                           "reviews it, or its evidence and the system's checks stand for it). Nothing to "
                                           "do or report here - continue with the rest of your work.")
    try:
        review = ctx.services.claims.add_review(args["claim_id"], reviewer=ctx.agent_id, verdict=args["verdict"],
                                                notes=args["notes"], evidence=args.get("evidence"))
    except ClaimRejected as e:
        return _err("review rejected:\n- " + "\n- ".join(e.problems))
    result = claim_rules.evaluate(ctx.services, args["claim_id"])
    return ToolResult(ok=True, content=f"review {review['review_id']} recorded.\n" + _claim_status_text(result))


def check_claim(ctx: ToolContext, args: dict) -> ToolResult:
    from codedoctor import claim_rules

    try:
        result = claim_rules.evaluate(ctx.services, args["claim_id"])
    except KeyError:
        return _err(f"unknown claim {args['claim_id']}")
    return ToolResult(ok=True, content=_claim_status_text(result))


def withdraw_claim(ctx: ToolContext, args: dict) -> ToolResult:
    try:
        ctx.services.claims.withdraw(args["claim_id"], ctx.agent_id, args["reason"])
    except ClaimRejected as e:
        return _err("; ".join(e.problems))
    return ToolResult(ok=True, content=f"{args['claim_id']} withdrawn")


def send_message(ctx: ToolContext, args: dict) -> ToolResult:
    to = args["to"]
    if to != "user" and to not in ctx.known_agents:
        return _err(f"unknown recipient {to!r}; known: user, {', '.join(sorted(ctx.known_agents))}")
    msg = ctx.services.bus.post(sender=ctx.agent_id, recipient=to, kind="question", body={"text": args["text"]},
                                thread_id=ctx.thread_id, data_class=ctx.data_class)  # as sensitive as what the sender saw
    return ToolResult(ok=True, content=f"sent {msg['id']} to {to}")


_EV_ITEMS = {"type": "array", "items": {"type": "string"}, "maxItems": 32}


def _claim_parameters() -> dict:
    from codedoctor.agents.claim_input import PARAMETERS

    return PARAMETERS

TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("list_dir", "List a directory of the project.", _obj({"path": {"type": "string"}}, []), list_dir),
    Tool("read_file", f"Read up to {MAX_READ_LINES} lines of a project file. Registers the excerpt as citable evidence and returns its evidence id.",
         _obj({"path": {"type": "string"}, "start_line": {"type": "integer", "minimum": 1},
               "end_line": {"type": "integer", "minimum": 1}}, ["path"]), read_file),
    Tool("search_text", "Search project files for text (case-insensitive) or a regex. Returns path:line hits.",
         _obj({"query": {"type": "string", "minLength": 1}, "path": {"type": "string"}, "glob": {"type": "string"},
               "regex": {"type": "boolean"}, "max_results": {"type": "integer", "minimum": 1, "maximum": 200}}, ["query"]),
         search_text),
    Tool("run_command", "Run a command in the project root. Output is stored as evidence.",
         _obj({"command": {"type": "string", "minLength": 1}, "timeout_s": {"type": "integer", "minimum": 1, "maximum": 600}}, ["command"]),
         run_command, effect_class="external", retry_safe=False),
    Tool("read_evidence", "Read the stored content of an evidence id (exact original).",
         _obj({"id": {"type": "string"}, "max_chars": {"type": "integer", "minimum": 100, "maximum": 100000}}, ["id"]), read_evidence),
    Tool("remember", "Save a durable note to long-term memory (survives this task). Use for facts, decisions, open questions. "
                     "Include file paths, line numbers and evidence ids exactly.",
         _obj({"text": {"type": "string", "minLength": 1, "maxLength": 20000},
               "kind": {"enum": ["fact", "decision", "observation", "todo", "summary"]},
               "scope": {"enum": ["agent", "project"]},
               "entities": {"type": "array", "items": {"type": "string"}, "maxItems": 32},
               "evidence": _EV_ITEMS, "pinned": {"type": "boolean"}}, ["text"]), remember,
         effect_class="internal", retry_safe=False),
    Tool("recall", "Search long-term memory (yours and the project's shared notes). Also finds notes about modules coupled "
                   "(in the coupling graph) to the files, functions or entities the query names, and shows whether the "
                   "claims behind each note are now VERIFIED, UNVERIFIED, STALE or REFUTED.",
         _obj({"query": {"type": "string", "minLength": 1}, "k": {"type": "integer", "minimum": 1, "maximum": 50},
               "follow_coupling": {"type": "boolean"}}, ["query"]), recall),
    Tool("read_note", "Read one long-term memory note in full (recall and the task's memory section may shorten long notes).",
         _obj({"id": {"type": "string", "pattern": "^mem_"}}, ["id"]), read_note),
    Tool("submit_claim", "Record one structured claim. Only cite evidence ids returned by tools. Status starts as 'proposed'; "
                         "it becomes 'supported' only through validation plus an independent review. To raise the evidence "
                         "level, submit a new claim with 'supersedes'.",
         _obj({"claim": _claim_parameters()}, ["claim"]), submit_claim, effect_class="internal", retry_safe=False,
         check_args=False),
    Tool("review_claim", "Independently review someone else's claim. verdict: 'counterexample' (cite evidence that it is wrong), "
                         "'reverified' (cite evidence you produced by re-checking it yourself), or 'insufficient_evidence' (say what is missing). "
                         "You cannot review your own claims.",
         _obj({"claim_id": {"type": "string"}, "verdict": {"enum": ["counterexample", "reverified", "insufficient_evidence"]},
               "notes": {"type": "string", "minLength": 1, "maxLength": 20000}, "evidence": _EV_ITEMS}, ["claim_id", "verdict", "notes"]),
         review_claim, effect_class="internal", retry_safe=False),
    Tool("check_claim", "Show a claim's status and exactly what is still missing before it can count as supported.",
         _obj({"claim_id": {"type": "string"}}, ["claim_id"]), check_claim, effect_class="internal", retry_safe=True),
    Tool("withdraw_claim", "Withdraw one of your own claims.",
         _obj({"claim_id": {"type": "string"}, "reason": {"type": "string", "minLength": 1, "maxLength": 4000}}, ["claim_id", "reason"]),
         withdraw_claim, effect_class="internal", retry_safe=True),
    Tool("send_message", "Send a question to the user or another agent. Does not wait for an answer.",
         _obj({"to": {"type": "string"}, "text": {"type": "string", "minLength": 1, "maxLength": 20000}}, ["to", "text"]), send_message,
         effect_class="internal", retry_safe=False),
]}

GRAPH_READ = ["graph_overview", "graph_find", "graph_neighbors", "graph_impact", "graph_common_cause", "graph_risks"]
DEFAULT_TOOLS = {
    "general": ["list_dir", "read_file", "search_text", "run_command", "read_evidence", "remember", "recall", "read_note",
                "submit_claim", "check_claim", "withdraw_claim", "review_claim", "send_message", *GRAPH_READ, "graph_rebuild"],
    "head_dispatch": ["delegate", "scout", "tell_fixers", "wait_for", "consult", "task_status", "check_claim", "read_evidence", "recall", "read_note", "remember",
                      "graph_overview", "graph_find", "graph_risks"],
    "head_logic": [*GRAPH_READ, "graph_rebuild", "list_dir", "read_file", "search_text", "read_evidence", "recall", "read_note", "remember",
                   "submit_claim", "check_claim", "withdraw_claim", "raise_objection", "withdraw_objection"],
    "worker": ["list_dir", "read_file", "search_text", "run_command", "read_evidence", "remember", "recall", "read_note", "submit_claim",
               "check_claim", "withdraw_claim", "graph_find", "graph_neighbors", "graph_impact", "send_message"],
    "investigator": ["list_dir", "read_file", "search_text", "run_command", "read_evidence", "remember", "recall", "read_note",
                     "submit_claim", "check_claim", "withdraw_claim", "graph_find", "graph_neighbors", "graph_impact"],
    "guardian": ["list_dir", "read_file", "search_text", "read_evidence", "recall", "read_note", "remember", "review_claim", "check_claim",
                 "graph_find", "graph_neighbors", "graph_impact"],
}


COMPUTER_ACTIONS = ("mouse_move", "mouse_click", "type_text", "press_keys", "look_around", "aim_at", "hold_keys", "hold_mouse",
                    "launch_app", "close_app", "terminal")
COMPUTER_ACTOR = ("screenshot", "wait_and_look", "list_windows", *COMPUTER_ACTIONS)  # offered only when switched on (computer/tools.offered)
for _role in ("general", "worker", "investigator"):
    DEFAULT_TOOLS[_role] = [*DEFAULT_TOOLS[_role], *COMPUTER_ACTOR]
DEFAULT_TOOLS["guardian"] = [*DEFAULT_TOOLS["guardian"], "screenshot", "list_windows", "decide_action"]
VIDEO = ("video_project", "video_edit", "video_render")  # CodeCut (codedoctor/video.py): installed, and the task called @CodeCut
for _role in ("general", "worker", "investigator"):
    DEFAULT_TOOLS[_role] = [*DEFAULT_TOOLS[_role], *VIDEO]
DEFAULT_TOOLS["guardian"] = [*DEFAULT_TOOLS["guardian"], "video_project"]
MODEL3D = ("code3d_project", "code3d_run")  # Code3D (codedoctor/model3d.py): installed, and the task called @Code3D
for _role in ("general", "worker", "investigator"):
    DEFAULT_TOOLS[_role] = [*DEFAULT_TOOLS[_role], *MODEL3D]
DEFAULT_TOOLS["guardian"] = [*DEFAULT_TOOLS["guardian"], "code3d_project"]
MAKERS = ("maker_read", "maker_run")  # the other making tools (codedoctor/makers.py): installed, and the task called one in
for _role in ("general", "worker", "investigator"):
    DEFAULT_TOOLS[_role] = [*DEFAULT_TOOLS[_role], *MAKERS]
DEFAULT_TOOLS["guardian"] = [*DEFAULT_TOOLS["guardian"], "maker_read"]


NEEDS_INVESTIGATION = ("cluster_open", "cluster_dispatch", "cluster_run", "cluster_status")  # opened by a head


# ADR 0016 (user's design): when the project allows changing files a worker is a pair of hands - it reads, changes
# code and runs tests, nothing else. Its supervisor (the guardian) checks every change and does all the reporting.
HANDS_TOOLS = {"list_dir", "read_file", "search_text", "read_evidence", "graph_find", "graph_neighbors", "graph_impact",
               "edit_file", "create_file", "run_command", *VIDEO, *MODEL3D, *MAKERS, *COMPUTER_ACTOR}  # the hands also drive the screen (computer use is offered only when on)


SUPERVISOR_SPARE = {"cluster_candidates", "cluster_impact", "cluster_run", "cluster_status", "remember", "recall",
                    "read_note"}
HEAD_PAPERWORK = {"submit_claim", "withdraw_claim", "report_anomaly", "remember", "checklist_update", "resolve_anomaly",
                  "cluster_open", "cluster_dispatch"}


def usable(name: str, config, role: str | None = None, team: bool = False) -> bool:
    """Offer only tools that can work in this project: every description costs tokens on every request, and in the
    first real run a model spent five calls on a denied run_command and on business-investigation tools without heads.
    team: a Lumen team member - only what the project allows counts, not the cluster roles' divisions of labour."""
    if name in MODEL3D:
        from codedoctor import model3d

        return model3d.allowed(name, config)
    if name in MAKERS:
        from codedoctor import makers

        return makers.allowed(name, config)
    if team:
        if name in VIDEO:
            from codedoctor import video

            return video.home() is not None and (name == "video_project" or config.permissions.write_files)
        if name == "run_command":
            return config.permissions.run_command != "deny"
        if name in ("edit_file", "create_file"):
            return config.permissions.write_files
        return True
    heads = any(a.role in ("head_dispatch", "head_logic") for a in config.agents.values())
    if name in ("scout", "tell_fixers", "delegate") and role == "head_dispatch":
        from codedoctor.agents import squad

        return squad.applies(config) != (name == "delegate")  # the squad's head names scenarios instead of handing out files
    if name in VIDEO:
        from codedoctor import video

        return video.home() is not None and (name == "video_project" or config.permissions.write_files)
    if name == "run_command":
        return config.permissions.run_command != "deny"
    if name in ("edit_file", "create_file"):
        return config.permissions.write_files
    if name in NEEDS_INVESTIGATION:
        return heads
    if role == "worker" and config.permissions.write_files:
        return name in HANDS_TOOLS
    if role in ("head_dispatch", "head_logic") and config.permissions.write_files and name in HEAD_PAPERWORK:
        return False  # real run: the heads filed 11 claims and 10 anomalies and spent 670k tokens; supervisors report  # the hands: no reports, claims or anomalies; the supervisor reports for them
    if name == "decide_anomaly" and role in ("worker", "investigator"):
        return not heads  # with heads the logic head decides; a worker decides only when it answers the user itself
    if name == "submit_claim" and role == "guardian":
        return config.permissions.write_files  # the supervisor states what the hands changed
    if role == "guardian" and config.permissions.write_files and name in SUPERVISOR_SPARE:
        return False  # reviewing code changes: business experiments and long-term memory are not needed
    return True


def tools_for(role: str, configured: tuple[str, ...] | None) -> list[Tool]:
    names = configured if configured is not None else DEFAULT_TOOLS.get(role, DEFAULT_TOOLS["general"])
    unknown = [n for n in names if n not in TOOLS]
    if unknown:
        raise ValueError(f"unknown tools in config: {unknown}")
    if role in {"head_dispatch", "head_logic"} and set(names) & {"run_command", "cluster_run", *COMPUTER_ACTIONS}:
        raise ValueError("heads decide and schedule; they cannot execute terminal commands, computer actions or business experiments")
    return [TOOLS[n] for n in names]


async def execute_async(tool: Tool, ctx: ToolContext, args: dict) -> ToolResult:
    """Async tools (waiting for other agents) run on the event loop; everything else in a worker thread."""
    if tool.name in ("edit_file", "create_file", "run_command", "maker_run"):  # 批准方式: the user is asked when their choice says so
        from codedoctor.agents import asking

        refused = await asking.ask_first(tool, ctx, args)
        if refused:
            return _err(refused)
    if inspect.iscoroutinefunction(tool.handler):
        errors = list(Draft202012Validator(tool.parameters).iter_errors(args)) if tool.check_args else []
        if errors:
            return _err(f"bad arguments for {tool.name}: {errors[0].message}")
        return await tool.handler(ctx, args)
    return await asyncio.to_thread(execute, tool, ctx, args)


def execute(tool: Tool, ctx: ToolContext, args: dict) -> ToolResult:
    errors = list(Draft202012Validator(tool.parameters).iter_errors(args)) if tool.check_args else []
    if errors:
        return _err(f"bad arguments for {tool.name}: {errors[0].message}")
    try:
        return tool.handler(ctx, args)
    except PermissionError as e:
        return _err(str(e))
    except (OSError, EvidenceError, UnicodeError) as e:
        return _err(f"{type(e).__name__}: {e}")


def _asked_of_lumen(ctx, args):
    return _err("approve_permission is answered by the running Lumen (agents/team_link.py), not here")


# Claude Code's own Edit, Write and Bash are not pre-approved when a run has the link: each one asks this tool first, and the
# answer follows the user's 批准方式 for the chat (agents/asking.py). It is only ever forwarded to the service.
TOOLS["approve_permission"] = Tool(
    "approve_permission", "Lumen decides whether Claude Code may use one of its own tools (Edit, Write, Bash).",
    _obj({"tool_name": {"type": "string"}, "input": {"type": "object"}}, ["tool_name", "input"]), _asked_of_lumen)

# Graph and cluster tools register themselves into TOOLS.
from codedoctor.agents import tools_cluster  # noqa: E402,F401
from codedoctor.agents import tools_anomaly  # noqa: E402,F401
from codedoctor.agents import tools_edit  # noqa: E402,F401
from codedoctor.cluster import tools as business_tools  # noqa: E402,F401
from codedoctor import makers, model3d, video  # noqa: E402,F401
from codedoctor.agents import team as _team  # noqa: E402,F401
from codedoctor.agents import tools_browser as _browser  # noqa: E402,F401
from codedoctor.agents import ask_user as _ask_user  # noqa: E402,F401 (the question panel's tool)
