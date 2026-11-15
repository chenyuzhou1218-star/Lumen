"""Recover tool calls that a model wrote into its text instead of the tool_calls field.

Many open models (llama 3.x, some Qwen/GLM builds, older vLLM/llama.cpp chat templates)
answer a tool request with JSON in the message body. Accepted shapes, only for tools
that were actually offered in this request:

    {"name": "read_file", "arguments": {...}}          ("parameters" / "args" / "input" too)
    {"function": {"name": "read_file", "arguments": "..."}}
    <tool_call>{...}</tool_call>          <function=read_file>{...}</function>
    a JSON list of the above, optionally inside a ```json fence

To avoid executing JSON the model merely quoted (from a log or a file it read), calls are
recovered only when they make up the message: whatever prose is left around them must be
short. Recovered calls then go through the same permission and side-effect checks as
native ones.
"""

from __future__ import annotations

import json
import re

from codedoctor.models.base import ToolCall

MAX_LEFTOVER_CHARS = 240
_ARG_KEYS = ("arguments", "parameters", "args", "input")
_FUNC_TAG = re.compile(r"<function=([A-Za-z0-9_.-]+)>\s*(\{.*?\})\s*</function>", re.S)
_WRAPPERS = re.compile(r"</?tool_call>|<\|python_tag\|>|<\|eom_id\|>|<\|eot_id\|>|```(?:json|tool_call)?", re.I)


def _as_call(obj, names: set[str]):
    if not isinstance(obj, dict):
        return None
    if isinstance(obj.get("function"), dict):
        obj = obj["function"]
    name = obj.get("name") or obj.get("tool") or obj.get("tool_name")
    if not isinstance(name, str) or name not in names:
        return None
    args = next((obj[k] for k in _ARG_KEYS if k in obj), {})
    parse_error = None
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError as e:
            args, parse_error = {}, f"arguments are not valid JSON: {e}"
    if not isinstance(args, dict):
        args, parse_error = {}, "arguments must be a JSON object"
    return name, args, parse_error


def extract(text: str | None, tool_names) -> tuple[list[ToolCall], str | None]:
    """Return (calls, remaining_text). No calls → ([], text unchanged)."""
    if not text or not tool_names:
        return [], text
    names = set(tool_names)
    found: list[tuple[str, dict, str | None]] = []
    spans: list[tuple[int, int]] = []

    for m in _FUNC_TAG.finditer(text):
        if m.group(1) in names:
            got = _as_call({"name": m.group(1), "arguments": m.group(2)}, names)
            if got:
                found.append(got)
                spans.append(m.span())

    dec = json.JSONDecoder()
    i = 0
    while True:
        starts = [p for p in (text.find("{", i), text.find("[", i)) if p >= 0]
        if not starts:
            break
        start = min(starts)
        if any(a <= start < b for a, b in spans):
            i = start + 1
            continue
        try:
            obj, end = dec.raw_decode(text, start)
        except json.JSONDecodeError:
            i = start + 1
            continue
        items = obj if isinstance(obj, list) else [obj]
        got = [_as_call(o, names) for o in items]
        if items and all(got):
            found.extend(got)
            spans.append((start, end))
        i = end

    if not found:
        return [], text
    leftover, last = [], 0
    for a, b in sorted(spans):
        leftover.append(text[last:a])
        last = b
    leftover.append(text[last:])
    rest = _WRAPPERS.sub("", "".join(leftover)).strip()
    if len(rest) > MAX_LEFTOVER_CHARS:
        return [], text  # JSON embedded in a real answer: leave it as text
    calls = [ToolCall(id=f"text_call_{n}", name=name, arguments=args, parse_error=err)
             for n, (name, args, err) in enumerate(found)]
    return calls, rest or None
