"""What a person does with a chat other than reading it: name it, put it away, take it out as a file, keep phrases to reuse.

Everything here is the user's own convenience, stored next to ui.json and never required: a chat keeps its data in the
project whatever happens to these files.

    chat_names.json   {configuration path: {"titles": {chat id: name}, "hidden": [chat id]}}
    phrases.json      ["a phrase", ...]
    bookmarks.json    [{"title": ..., "url": ...}, ...]
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time

from codedoctor.agents import orchestration as orch

MOST_PHRASES = 60
MOST_BOOKMARKS = 200


def _home() -> Path:
    return Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor")


def _read(name: str, empty):
    try:
        data = json.loads((_home() / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    return data if isinstance(data, type(empty)) else empty


def _write(name: str, data) -> None:
    path = _home() / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # a convenience that cannot be saved lasts this session only


# --- a chat's name, and chats put away ------------------------------------------------------------------------------

def names_of(config: str) -> dict:
    """{"titles": {...}, "hidden": [...]} of one project."""
    entry = _read("chat_names.json", {}).get(config or "", {})
    if not isinstance(entry, dict):
        entry = {}
    titles = entry.get("titles") if isinstance(entry.get("titles"), dict) else {}
    hidden = entry.get("hidden") if isinstance(entry.get("hidden"), list) else []
    return {"titles": {k: v for k, v in titles.items() if isinstance(v, str)}, "hidden": [c for c in hidden if isinstance(c, str)]}


def _save_names(config: str, entry: dict) -> None:
    data = _read("chat_names.json", {})
    data[config or ""] = entry
    _write("chat_names.json", data)


def rename(config: str, chat_id: str, title: str) -> None:
    entry = names_of(config)
    title = " ".join(title.split())[:120]
    if title:
        entry["titles"][chat_id] = title
    else:  # an empty name: back to its first message
        entry["titles"].pop(chat_id, None)
    _save_names(config, entry)


def hide(config: str, chat_id: str) -> None:
    """Off the list; nothing is deleted, and bring_back shows it again."""
    entry = names_of(config)
    if chat_id not in entry["hidden"]:
        entry["hidden"].append(chat_id)
    _save_names(config, entry)


def bring_back(config: str) -> int:
    entry = names_of(config)
    count = len(entry["hidden"])
    entry["hidden"] = []
    _save_names(config, entry)
    return count


# --- a chat as a file -------------------------------------------------------------------------------------------------

def _answer_of(daemon, row: dict) -> str:
    reports = [m for m in daemon.s.bus.list(thread_id=row["thread_id"]) if m["kind"] == "report" and m["body"].get("task_id") == row["id"]]
    return reports[-1]["body"].get("summary", "") if reports else ""


def as_markdown(daemon, chat_id: str, title: str | None = None) -> str:
    """The whole conversation as Markdown: the questions as asked, the answers as given, with their times."""
    turns = daemon.chat_turns(chat_id)
    if not turns:
        return ""
    lines = [f"# {title or turns[0]['title']}", "", f"> {daemon.s.config.name} · 导出于 {time.strftime('%Y-%m-%d %H:%M')}", ""]
    for row in turns:
        body = orch.body_of(row) or {}
        when = str(row.get("created_at") or "")[:16].replace("T", " ")
        lines += [f"## 问 · {when}", "", body.get("instructions", row["title"]).strip(), ""]
        answer = _answer_of(daemon, row).strip()
        lines += ["## 答", "", answer or "（这一轮没有回答）", ""]
    return "\n".join(lines).rstrip() + "\n"


def export_all(daemon, config: str, folder: Path) -> int:
    """Every chat of this project as a file in folder (a new one is made under it); returns how many."""
    rows = daemon.s.db.query("SELECT id, title, json_extract(body, '$.chat_of') AS chat_of FROM tasks WHERE parent_task_id IS NULL ORDER BY created_at")
    names = names_of(config)["titles"]
    target = folder / f"{daemon.s.config.name} 聊天 {time.strftime('%Y%m%d-%H%M')}"
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for r in rows:
        if r["chat_of"]:  # a later turn of a chat: it goes with the chat
            continue
        title = names.get(r["id"], r["title"])
        text = as_markdown(daemon, r["id"], title)
        if text:
            count += 1
            (target / f"{count:03d} {file_name(title)}").write_text(text, encoding="utf-8")
    return count


def file_name(title: str) -> str:
    """A name Windows accepts, from a chat's title."""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", title).strip(" .")[:60]
    return f"{name or 'chat'}.md"


# --- searching what was said ------------------------------------------------------------------------------------------

def _snippet(text: str, needle: str, width: int = 26) -> str:
    at = text.lower().find(needle.lower())
    if at < 0:
        return ""
    start = max(0, at - width // 2)
    return " ".join(text[start:start + width + len(needle)].split())


def search_chats(daemon, needle: str, most: int = 12) -> list[dict]:
    """Chats that say this, in a question or an answer, newest first: {"task", "title", "snippet"}. The list on the left only
    looks at first messages."""
    like = "%" + needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    found: dict[str, dict] = {}
    for r in daemon.s.db.query("SELECT id, title, body, json_extract(body, '$.chat_of') AS chat_of FROM tasks WHERE parent_task_id IS NULL "
                               "AND body LIKE ? ESCAPE '\\' ORDER BY created_at DESC LIMIT ?", (like, most)):
        text = (json.loads(r["body"]).get("instructions") or "") if r["body"] else ""
        if needle.lower() in text.lower():
            found[r["id"]] = {"task": r["id"], "title": r["title"], "snippet": _snippet(text, needle)}
    for r in daemon.s.db.query("SELECT m.task_id AS task_id, m.doc AS doc, t.title AS title FROM messages m JOIN tasks t ON t.id = m.task_id "
                               "WHERE m.kind = 'report' AND t.parent_task_id IS NULL AND m.doc LIKE ? ESCAPE '\\' ORDER BY m.seq DESC LIMIT ?", (like, most)):
        text = (json.loads(r["doc"]).get("body") or {}).get("summary") or ""
        if needle.lower() in text.lower() and r["task_id"] not in found:
            found[r["task_id"]] = {"task": r["task_id"], "title": r["title"], "snippet": _snippet(text, needle)}
    return list(found.values())[:most]


# --- what was being written when the window closed --------------------------------------------------------------------

def draft(config: str) -> str:
    value = _read("drafts.json", {}).get(config or "", "")
    return value if isinstance(value, str) else ""


def keep_draft(config: str, text: str) -> None:
    data = _read("drafts.json", {})
    if text.strip() not in ("", "/", "、"):
        data[config or ""] = text[:20000]
    else:
        data.pop(config or "", None)
    _write("drafts.json", data)


# --- where the window was ---------------------------------------------------------------------------------------------

def window_place() -> dict:
    return _read("window.json", {})


def keep_window_place(x: int, y: int, width: int, height: int, maximized: bool) -> None:
    _write("window.json", {"x": x, "y": y, "width": width, "height": height, "maximized": maximized})


# --- phrases to reuse -------------------------------------------------------------------------------------------------

def phrases() -> list[str]:
    return [p for p in _read("phrases.json", []) if isinstance(p, str)]


def add_phrase(text: str) -> None:
    text = text.strip()
    if text:
        _write("phrases.json", ([text] + [p for p in phrases() if p != text])[:MOST_PHRASES])


def remove_phrase(text: str) -> None:
    _write("phrases.json", [p for p in phrases() if p != text])


# --- bookmarks of the browser ----------------------------------------------------------------------------------------

def bookmarks() -> list[dict]:
    return [b for b in _read("bookmarks.json", []) if isinstance(b, dict) and isinstance(b.get("url"), str)]


def is_bookmarked(url: str) -> bool:
    return any(b["url"] == url for b in bookmarks())


def toggle_bookmark(url: str, title: str) -> bool:
    """True if it is now kept."""
    kept = bookmarks()
    if any(b["url"] == url for b in kept):
        _write("bookmarks.json", [b for b in kept if b["url"] != url])
        return False
    _write("bookmarks.json", ([{"title": (title or url)[:120], "url": url}] + kept)[:MOST_BOOKMARKS])
    return True


# --- how much was used ------------------------------------------------------------------------------------------------

def usage_rows(daemon) -> list[dict]:
    """One row per model answer in this project: {"day", "who", "fresh", "cached", "cost"}. fresh is what was really new; cached
    is what an engine read back again, which costs about a tenth (a chat's header says the same)."""
    out = []
    for r in daemon.s.db.query("SELECT doc, at, agent FROM journal WHERE type = 'model_response'"):
        data = (json.loads(r["doc"]).get("data") or {})
        cached = int(data.get("cached_tokens") or 0)
        whole = int(data.get("input_tokens") or 0) + int(data.get("output_tokens") or 0)
        out.append({"day": str(r["at"])[:10], "who": str(data.get("engine") or data.get("model") or r["agent"]), "fresh": max(0, whole - cached), "cached": cached,
                    "cost": float(data.get("cost_usd") or 0)})
    return out


def usage_summary(rows: list[dict], today: str, days: list[str]) -> dict:
    """{"today", "week", "all": {"fresh", "cached", "cost", "answers"}, "by_day": [(day, fresh)], "by_who": [(who, fresh, cost, answers)]}"""
    def total(items):
        return {"fresh": sum(r["fresh"] for r in items), "cached": sum(r["cached"] for r in items), "cost": sum(r["cost"] for r in items), "answers": len(items)}

    week = set(days[-7:])
    per_day = {d: 0 for d in days}
    who: dict[str, list] = {}
    for r in rows:
        if r["day"] in per_day:
            per_day[r["day"]] += r["fresh"]
        entry = who.setdefault(r["who"], [0, 0.0, 0])
        entry[0] += r["fresh"]
        entry[1] += r["cost"]
        entry[2] += 1
    return {"today": total([r for r in rows if r["day"] == today]), "week": total([r for r in rows if r["day"] in week]), "all": total(rows),
            "by_day": list(per_day.items()), "by_who": sorted(((k, *v) for k, v in who.items()), key=lambda x: -x[1])}
