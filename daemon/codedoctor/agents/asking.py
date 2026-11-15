"""批准方式: before a tool changes files or runs a command, the user is asked when their choice for this chat says so.

    ask   (全部问我)  every action except talking: file changes, commands, mouse and keyboard, deleting
    auto  (帮我审查)  only deleting files, and mouse or keyboard (computer use); everything else just runs
    full  (完全放开)  nothing is asked

The supervisor's check stays in every choice; the choice only decides whether the user themselves is asked. What the project
allows at all (permissions, the allowlist) is checked by the tools as before: this never widens it.
"""

from __future__ import annotations

from codedoctor.computer import gate as gate_mod

ASKED = {"edit_file": "edit", "create_file": "create", "run_command": "command", "maker_run": "command"}


def classify(tool_name: str, args: dict, root=None) -> tuple[str, dict]:
    """(kind, what to show) of one tool call; a command that deletes is a deletion; a file outside root is "outside"."""
    kind = ASKED[tool_name]
    if kind == "command":
        command = str(args.get("command") or f"{args.get('tool', '')} {args.get('action', '')}".strip())
        if tool_name == "run_command" and gate_mod.is_delete_command(command):
            kind = "delete"
        return kind, {"command": command[:500]}
    path = str(args.get("path", ""))
    from pathlib import Path

    try:  # a place outside the project, absolute or "..\x" (tools._safe_path, codedoctor/outside.py)
        base = Path(root).resolve() if root is not None else None
        where = (base / path).resolve() if base is not None else Path(path)
        if (base is not None and where != base and base not in where.parents) or (base is None and Path(path).is_absolute()):
            kind = "outside"
    except OSError:
        kind = "outside"
    return kind, {"path": path[:300]}


async def ask_first(tool, ctx, args: dict) -> str | None:
    """None: go ahead. Else why not (the user said no, or did not answer in time)."""
    if tool.name not in ASKED:
        return None
    gate = getattr(ctx.services, "computer", None)
    if gate is None:
        return None
    from codedoctor.agents.tools import root_of

    kind, shown = classify(tool.name, args, root_of(ctx))
    if not gate_mod.asks_user(gate.tier_of(ctx.task_id), kind, shown):
        return None
    ok = await gate.ask_plain(ctx, kind, shown, intent=f"{ctx.agent_id} wants to use {tool.name}")
    return None if ok else "the user did not approve this action (or did not answer in time): it was not done"
