"""The window in React (2026-11-10): the sidebar, the new chat, the conversation and the pages around them, drawn by
web/ (built into web_dist/) in one web view.

The user asked for Lumen to look and feel like the AI apps people know; those draw their chats with web technology,
which is what this is. Python stays the program: the page talks to it over QWebChannel inside the window (nothing on a
port: approvals never go over HTTP), and the message box's choices are kept by the same Composer the Qt window used
(models, levels, @ tools, attachments, approval), hidden, so what is sent is exactly what was sent before.

What stays Qt - an @ tool's own window, and the pages not drawn in React yet - lies over the page where the page leaves
room for it: the page reports that rectangle (Bridge.slot) and the widget is put there (WebChat.place).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtWidgets import QWidget

from codedoctor.agents import orchestration as orch
from codedoctor.ui_text import describe_tool_call, duration, parse_ts, task_status

DIST = Path(__file__).resolve().parent / "web_dist"
ASSETS = Path(__file__).resolve().parent / "assets" / "team"
# What Lumen adds behind the user's words for the AI (the tool on the right, its project): never shown in the chat (the user,
# 2026-11-14: "必须写到明面上啊！...直接放到背后的提示词").
HIDDEN = "\n\n<<lumen:context>>\n"


def shown(question: str) -> str:
    """The user's own words of a question, without what Lumen added behind them."""
    return str(question or "").split(HIDDEN.strip())[0].rstrip()


def _t(text):
    from codedoctor.desktop import locale

    return locale.t(text)


def _avatar(agent: str) -> str:
    from codedoctor.agents import team

    m = team.member(agent)
    path = ASSETS / f"{m.id if m else 'lumen'}.png"
    return QUrl.fromLocalFile(str(path)).toString() if path.is_file() else ""


def _without_system_block(text: str) -> str:
    from codedoctor.desktop.task_view import _without_system_block as cut

    return cut(text or "")


def _report(daemon, row: dict) -> dict | None:
    reports = [m for m in daemon.s.bus.list(thread_id=row["thread_id"]) if m["kind"] == "report" and m["body"].get("task_id") == row["id"]]
    return reports[-1]["body"] if reports else None


def _steps(daemon, task_id: str, limit: int = 400) -> list[dict]:
    """What the agent did, as the old window listed it: one line per tool call (with whether it worked), its thoughts
    between calls, the system's test runs, errors and stops."""
    out, by_call = [], {}
    for e in daemon.s.journal.read(task_id=task_id, after_seq=0, limit=limit):
        t, d = e["type"], e["data"]
        if e["agent"] == "system" and t != "test_run":
            continue
        if d.get("truncated") and "tool" not in d and t in ("tool_call", "tool_result"):
            d = (daemon.s.journal.original(e) or {}).get("data") or d
        if t == "tool_call":
            step = {"kind": "tool", "tool": d["tool"], "text": _t(describe_tool_call(d["tool"], d.get("arguments", {}))), "ok": None, "at": e["at"]}
            by_call[d.get("call_id")] = step
            out.append(step)
        elif t == "tool_result" and d.get("call_id") in by_call and not d.get("truncated"):
            by_call[d["call_id"]]["ok"] = d.get("ok")
        elif t == "model_response" and d.get("tool_calls") and d.get("total_ms") is None:
            payload = (daemon.s.journal.original(e) or {}).get("payload") or {}
            text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
            if text:
                out.append({"kind": "thought", "text": text[:400], "at": e["at"]})
        elif t == "test_run":
            reg, opn = d.get("regressions") or [], d.get("open") or []
            out.append({"kind": "test", "text": _t(f"系统自动跑测试：{d.get('summary', '')}"), "ok": not reg and not opn, "at": e["at"]})
        elif t == "model_error":
            busy = d.get("status") == 429 and d.get("retryable")
            out.append({"kind": "note" if busy else "error", "text": _t("模型服务正忙，自动等一会儿再试") if busy else _t("模型出错：") + str(d.get('error', ''))[:200], "at": e["at"]})
        elif t in ("budget_stop", "stall_stop"):
            out.append({"kind": "error", "text": _t("预算用完，停止" if t == "budget_stop" else "连续几步没有新进展，停止"), "at": e["at"]})
        elif t == "state_change" and d.get("state") == "remembering":  # a new conversation waits for the memory (memory/digest.py)
            out.append({"kind": "note", "text": _t("正在回顾以前的对话……"), "at": e["at"]})
        elif t == "state_change" and d.get("state") == "remembered":
            out.append({"kind": "note", "text": _t("记忆还在整理，先用已有的开始" if d.get("late") else "已经回顾了以前的对话"), "at": e["at"]})
    return out


def _who(daemon, row: dict) -> str:
    from codedoctor.desktop.task_view import engines_label

    body = orch.body_of(row)
    if body.get("engine"):
        from codedoctor import engines

        label = engines.label(body)
        effort = engines.effort_name(body["engine"], body.get("engine_effort"))
        # Claude Code's levels have Chinese names (中等 ...): in the window's language, the model's own name left as it is
        # (the English window showed "Claude Code · Haiku 5.5 · 中等", 2026-11-16)
        return label[: -len(effort)] + _t(effort) if effort and label.endswith(effort) else label
    if body.get("model"):
        return body["model"]["model"]
    agent = daemon.s.config.agents.get(row["agent"])
    if agent is None:
        return ""
    return engines_label(daemon.s.config.endpoints.get(agent.primary.endpoint), agent.primary.model)


def _member(daemon, row: dict) -> dict:
    from codedoctor.agents import team

    body = orch.body_of(row)
    m = team.member(row["agent"])
    sender = team.member(row.get("requester") or "lumen")
    rep = _report(daemon, row)
    return {"id": row["id"], "agent": row["agent"], "name": m.name if m else row["agent"], "cn": m.cn if m else "",
            "job": _t(m.job) if m else "", "colour": m.colour if m else "#888888", "avatar": _avatar(row["agent"]),
            "from": sender.name if sender else "Lumen", "ask": str(body.get("instructions", row["title"]))[:1500],
            "review": bool(body.get("review_of")), "state": row["state"], "outcome": row.get("outcome"),
            "status": _t(task_status(row)), "answer": _without_system_block(rep.get("summary", "")) if rep else "",
            "steps": _steps(daemon, row["id"], 120)}


def chat_json(daemon, task_id: str) -> dict:
    """One conversation: every turn's question, who answered, its steps, the team's messages and the answer."""
    from codedoctor.desktop import chat_tools

    task = daemon.task(task_id)
    if task is None:
        return {"missing": True}
    body = orch.body_of(task)
    chat_id = body.get("chat_of") or task_id
    rows = daemon.chat_turns(chat_id) or [task]
    titles = chat_tools.names_of(str(daemon.s.config.source or ""))["titles"]
    from codedoctor.desktop import prefs as ui_prefs

    folds = ui_prefs.load().get("fold_turns") or {}
    turns = []
    for row in rows:
        b = orch.body_of(row) or {"instructions": row["title"]}
        rep = _report(daemon, row)
        usage = json.loads(row["usage"]) if isinstance(row.get("usage"), str) and row["usage"] else (row.get("usage") or {})
        elapsed = time.time() - parse_ts(row["created_at"]) if row["state"] != "finished" else (usage.get("wall_ms") or 0) / 1000
        whole = orch.tree_tokens(daemon.s, row["id"]) or (usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
        cached = orch.tree_cached(daemon.s, row["id"]) or usage.get("cached_tokens", 0)
        msgs = daemon.s.bus.list(thread_id=row["thread_id"])
        over = [e["data"] for e in daemon.s.journal.read(task_id=row["id"], after_seq=0, limit=2000) if e["type"] == "spend_stop"]
        turns.append({
            "id": row["id"], "fold": folds.get(row["id"]), "question": shown(b.get("instructions", row["title"])), "at": row["created_at"], "who": _who(daemon, row),
            "tools": orch.called_tools(b), "chat": bool(b.get("chat")), "state": row["state"], "outcome": row.get("outcome"),
            "status": _t(task_status(row)), "answer": _without_system_block(rep.get("summary", "")) if rep else "",
            "steps": _steps(daemon, row["id"]), "members": [_member(daemon, c) for c in orch.children(daemon.s, row["id"])],
            "elapsed": _t(duration(elapsed)), "tokens": max(0, whole - cached), "over": over[-1] if over else None,
            "needs": [m["body"].get("reason", "") for m in msgs if m["kind"] == "escalation" and m["body"].get("task_id") == row["id"]],
        })
    last = rows[-1]
    return {"chat_id": chat_id, "task_id": last["id"], "title": titles.get(chat_id) or rows[0]["title"], "turns": turns,
            "running": last["state"] != "finished", "resumable": last["state"] == "finished" and last.get("outcome") in ("interrupted", "budget", "stalled")}


def side_json(win) -> dict:
    """The sidebar: this folder's chats (by the names given to them, without those put away), which are pinned and which
    is open, the other folders, the services without a key, and which page of the panel on the right is open. The list
    itself is kept by the Qt Sidebar (pins, names, the selection), which the window no longer shows."""
    from codedoctor.desktop import projects
    from codedoctor.desktop.sidebar import RUNNING

    sb = win.sidebar
    here = sb.config_path or ""
    known = projects.load()
    item = next((p for p in known if here and projects._same(p["config"], here)), {})
    folders = [{"name": item.get("label") or sb.project, "config": here, "root": sb.root, "here": True}]
    folders += [{"name": p.get("label") or p.get("name") or p["config"], "config": p["config"], "root": str(p.get("root") or ""), "here": False}
                for p in known if p.get("config") and Path(p["config"]).exists() and not (here and projects._same(p["config"], here))][:19]
    return {"chats": [{"id": c["id"], "title": c["title"], "open": c["open"], "running": task_status(c) in RUNNING} for c in sb.listed()],
            "pins": list(sb.pins), "selected": sb._selected if win._in_chat() else None, "folders": folders,
            "keys_missing": list(getattr(sb, "key_problems", [])),
            "docks": list(getattr(win.dock, "open", [win.dock.current] if win.dock.isVisible() else []))}


def asks_json(win) -> dict:
    """What waits for the user now: actions to approve (the gate's records) and questions in the panel (agents/ask_user.py)."""
    from codedoctor.agents import ask_user
    from codedoctor.desktop.computer_view import describe_cn

    s = win.d.s
    from codedoctor.agents import team

    approvals = []
    gate = getattr(s, "computer", None)
    if gate is not None:
        for rec in reversed(gate.actions(statuses=("pending_user",))):  # oldest first
            m = team.member(rec["agent"])
            approvals.append({"id": rec["id"], "who": rec["agent"], "name": m.name if m else rec["agent"],
                              "text": _t(describe_cn(rec))[:160], "why": _t(rec.get("user_reason") or "")})

    def named(q: dict) -> dict:  # "lumen" -> "Lumen": the member's own name in the panel's title
        m = team.member(q.get("agent", ""))
        return {**q, "agent": m.name if m else q.get("agent", "")}

    return {"approvals": approvals, "questions": [named(q) for q in ask_user.pending(s)]}


def boot_json(win) -> dict:
    """What the page needs once: the interface language and its texts, and the appearance preferences."""
    from codedoctor.desktop import i18n

    lang = i18n.language()
    catalog = {}
    if lang == "zh-TW":  # the Chinese texts, converted on the page the same way (zh_hant.py)
        from codedoctor.desktop import zh_hant

        catalog = zh_hant.catalog()
    elif lang != "zh":  # English, with the language's own texts over it (locale.py: fr.json; missing texts stay English)
        from codedoctor.desktop import locale as desktop_locale

        catalog = desktop_locale.catalog(lang)
    return {"lang": lang, "catalog": catalog, "prefs": prefs_json(win.ui), "project": win.cfg.name,
            "welcome": {k: i18n.tr(k) for k in ("tagline", "skip", "enter")}}


def prefs_json(ui: dict) -> dict:
    """The appearance preferences the page itself applies (prefs.py)."""
    from codedoctor.desktop.theme import ACCENTS

    keys = ("font_size", "chat_width", "send_key", "show_times", "expand_steps", "auto_fold", "show_tokens", "reduced_motion", "accent",
            "mode", "term_font", "figure_motion", "spend_limit")
    out = {k: ui.get(k) for k in keys}
    out["accent_colours"] = list(ACCENTS.get(ui.get("accent"), ACCENTS["amber"]))
    return out


def plugins_json(found: list | None, done: bool) -> dict:
    """插件: the big tools, then CodeTools' small plugins by group (listed by CodeTools itself, plugins_view._read), each
    with the line drawing its own window uses."""
    from codedoctor.desktop import i18n
    from codedoctor.desktop.plugins_view import BIG, GLYPHS, GROUP_KEY

    groups: dict[str, list] = {}
    for p in found or []:
        groups.setdefault(p["group"], []).append({"id": p["id"], "name": p["name"], "about": p.get("blurb", "")})
    return {"big": [{"key": k, "name": n, "about": i18n.tr(f"{k}_sub")} for k, n in BIG],
            "groups": [{"name": _t(g), "glyph": GROUP_KEY.get(g.strip().lower(), "创作"), "items": [{**i, "name": _t(i["name"]), "about": _t(i["about"])} for i in items]} for g, items in groups.items()],
            "done": done, "glyphs": GLYPHS}


class Bridge(QObject):
    """What the page may ask. Every slot answers JSON text."""
    show = Signal(str)       # {"page": "home"} or {"page": "chat", "task_id": ...}: what to draw
    heard = Signal(str)      # the voice input's text (or {"error": ...})
    changed = Signal(str)    # the message box's state changed on this side (a mention typed, files picked)
    put = Signal(str)        # words to add to the box in front of the user (from the browser or the terminal)
    side = Signal(str)       # the sidebar's lists changed (side_json)
    tool = Signal(str)       # {"on": bool, "name": ...}: an @ tool's own window above the chat
    prefs = Signal(str)      # the appearance preferences changed (prefs_json)
    command = Signal(str)    # {"do": "toggle_side" | "find"}: a shortcut pressed in the window
    found = Signal(str)      # {"count", "at"}: what the find bar found
    plugins_ready = Signal(str)  # plugins_json, once CodeTools has listed its plugins
    probed = Signal(str)     # {"token", ...}: a settings test that took a while (web_settings.probe)
    term = Signal(str)       # the terminal: {"out": text} | {"exit": true} | {"ran": {who, command}} (web_dock.py)
    asks = Signal(str)       # what waits for the user: {"approvals": [...], "questions": [...]} (asks_json)
    asks_poke = Signal()     # from any thread: something waiting for the user changed
    browser = Signal(str)    # the browser's tabs, address, star and Ray's panel (BrowserPage.as_json)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.recorder = None

    # --- what to draw ------------------------------------------------------------------------------------------------

    @Slot(result=str)
    def boot(self) -> str:
        return json.dumps(boot_json(self.win), ensure_ascii=False)

    @Slot(result=str)
    def sidebar(self) -> str:
        return json.dumps(side_json(self.win), ensure_ascii=False)

    @Slot(result=str)
    def home(self) -> str:
        from codedoctor.desktop.composer import MENTIONS, mentionable

        win, c = self.win, self.win.home.composer
        warnings = [{"text": _t(w), "act": ""} if isinstance(w, str) else {"text": _t(w[0]), "act": _t(w[1][0]) if len(w) > 1 and w[1] else ""}
                    for w in (win.home._warnings or [])]
        draft = None
        if not getattr(self, "_draft_given", False):  # what was being written when the window last closed, once
            self._draft_given = True
            draft = c.edit.toPlainText()
        return json.dumps({"project": win.cfg.name, "tools": [{"key": k, "name": MENTIONS[k]} for k in mentionable()],
                           "box": self._box(c), "warnings": warnings, "lumen": _avatar("lumen"), "draft": draft}, ensure_ascii=False)

    @Slot(int)
    def warning_action(self, index: int) -> None:
        """The button of a warning on the new chat (改成内部代码)."""
        w = self.win.home._warnings or []
        if 0 <= index < len(w) and not isinstance(w[index], str) and len(w[index]) > 1 and w[index][1]:
            w[index][1][1]()

    @Slot(str)
    def keep_draft(self, text: str) -> None:
        """The new chat's words as they are typed, kept for the next time the window opens."""
        self.win.web_draft = text

    @Slot(str, result=str)
    def chat(self, task_id: str) -> str:
        try:
            out = chat_json(self.win.d, task_id)
        except Exception as e:  # shown on the page; the window stays usable
            out = {"error": f"{type(e).__name__}: {e}"}
        out["box"] = self._box(self.win.task_view.composer)
        out["box"]["running"] = bool(out.get("running"))
        out["lumen"] = _avatar("lumen")
        try:
            self._ask_when_blocked(out)
        except Exception:  # a question that could not be raised never stops the page
            pass
        return json.dumps(out, ensure_ascii=False)

    def _ask_when_blocked(self, out: dict) -> None:
        """A turn seen running here that ended 被拦下 saying what it needs: the question panel asks for it (the user,
        2026-11-14: it should ask, not stop). Once per turn, and only for turns that ended while this window watched."""
        turns = out.get("turns") or []
        if not turns:
            return
        last = turns[-1]
        seen = self.__dict__.setdefault("_seen_running", set())
        if last.get("state") != "finished":
            seen.add(last["id"])
            return
        asked = self.__dict__.setdefault("_asked_blocked", set())
        if last.get("outcome") != "blocked" or last["id"] not in seen or last["id"] in asked:
            return
        asked.add(last["id"])
        from codedoctor.agents import ask_user

        need = (last.get("answer") or "").strip()
        # The AI program itself could not start (not signed in, not installed): the answer already says what to do, and
        # "按你的判断接着做" would mean nothing (the flow check, 2026-11-14: an expired Claude Code sign-in became a question)
        if any(w in need for w in ("没有登录", "登录已过期", "Failed to authenticate", "not logged in", "没有找到 Codex",
                                   "没有找到 Claude Code", "codex login", "claude login")):
            return
        head = "没做完：它需要你给一样东西（权限、文件或回答），见下。"  # engines.py's opening line: the panel asks the rest
        for opening in (head, _t(head)):
            if need.startswith(opening):
                need = need[len(opening):].strip()
        need = need or _t("它需要你给一样东西才能接着做。")
        ask_user.follow_up(self.win.d.s, last["id"], "Lumen", need,
                           [_t("按你的判断接着做"), _t("先不做了")])  # no permission choice: the user's 批准方式 decides that (2026-11-14)
        self.win.web.push_asks()

    def _box(self, c) -> dict:
        """The message box's choices as the Composer holds them: the model, its levels, the approval, the @ tools, files."""
        from codedoctor import engines
        from codedoctor.desktop.composer import MENTIONS

        keys, name = c._levels()
        models = []
        for e in engines.NAMES:
            if not engines.get(e).executable():
                continue
            for m in engines.models(e):
                models.append({"group": engines.TITLES[e], "label": m["name"], "pick": {"engine": e, "id": m["id"], "model": f"{engines.TITLES[e]} · {m['name']}"}})
        for title, endpoint, model in c.choices:
            models.append({"group": title.split(" · ")[0], "label": model, "pick": {"endpoint": endpoint, "model": model}})
        return {"model": (c.model_choice or {}).get("model", ""), "pick": c.model_choice, "models": models,
                "levels": [{"key": k, "name": _t(name(k))} for k in keys], "level": c.level,
                "approval": c.approval, "mentions": [{"key": k, "name": MENTIONS.get(k, k)} for k in c.mentions],
                "files": [n for n, _ in c.attached], "running": False,
                "tool": bool(self.win.tool_view.isVisible())}  # an @ tool's window is above: the new chat folds away

    # --- the message box -------------------------------------------------------------------------------------------

    def _composer(self, where: str):
        return self.win.home.composer if where == "home" else self.win.task_view.composer

    LIMIT = 48000  # the service takes 50,000 characters of instructions (schemas/agent/message.schema.json)

    def _open_project(self, key: str) -> str:
        """The project file the tool on the right shows (tools/<tool>/state/current.json, written by the tool), when it is in
        this project's folder; else ""."""
        from codedoctor.desktop import tool_view

        try:
            home = tool_view.home(key)
            if home is None:
                return ""
            cur = json.loads((home / "state" / "current.json").read_text(encoding="utf-8"))
            path, folder = Path(cur.get("project") or ""), Path(cur.get("folder") or "")
            root = Path(self.win.d.s.config.root).resolve()
            if path.is_file() and folder and folder.resolve() == root:
                return str(path)
        except (OSError, ValueError):
            pass
        return ""

    def _tool_on_now(self) -> bool:
        web = getattr(self.win, "web", None)
        return bool(web is not None and getattr(web, "_tool_on", False) and getattr(web, "_tool_key", ""))

    @property
    def _tool_key(self) -> str:
        web = getattr(self.win, "web", None)
        return getattr(web, "_tool_key", "") if web is not None else ""

    @Slot(str, str, result=str)  # the page calls this one: the slot mark must stay right above it (moved off it, sending died)
    def send(self, where: str, text: str) -> str:
        """{"ok": true} once the task exists; else why, with the box's files kept (the page keeps the words)."""
        c = self._composer(where)
        if not c.model_choice:  # nothing is chosen for the user (their rule): they choose before it goes
            return json.dumps({"ok": False, "why": _t("先在输入框右下角选一个模型。")}, ensure_ascii=False)
        size = len(text) + sum(len(body) + 20 for _, body in c.attached)
        if size > self.LIMIT:
            return json.dumps({"ok": False, "why": _t("太长了：连同文件一共 {0} 个字，一次最多 {1} 个。拿掉一个文件，或者只贴要紧的部分。").replace("{0}", f"{size:,}").replace("{1}", f"{self.LIMIT:,}")},
                              ensure_ascii=False)
        files, mentions = list(c.attached), list(c.mentions)
        # The tool open on the right is what the user is working in (2026-11-14: a video was in CodeCut, the user asked to keep
        # its first 30 s, and Lumen searched the folder for an .mp4 and asked for an upload): it goes with the message as if
        # called with @, unless they called other tools themselves.
        open_tool = self._tool_key if self._tool_on_now() else ""
        added = bool(open_tool) and not c.mentions and open_tool not in c.mentions
        if added:
            c.add_mention(open_tool)
        if open_tool:  # the AI works on exactly what is on the right; said behind the user's words, never shown in the chat
            where_open = self._open_project(open_tool)
            name = __import__("codedoctor.desktop.composer", fromlist=["MENTIONS"]).MENTIONS.get(open_tool, open_tool)
            text += (f"{HIDDEN}The {name} window is open on the right side of Lumen"
                     + (f" with this project: {where_open}. Work on this project directly with the tool" if where_open else "")
                     + f"; the window shows each change at once. The computer-use member may also click and type in that window "
                     f"directly: it is listed as '{name} (Lumen)', nobody is asked, and the user watches it work. The user does "
                     "not need to upload anything.")
        c.edit.setPlainText(text)
        self.win.last_submit_ok = False
        c._send()  # the same path as the old box: @ tools named, files fenced as data, then MainWindow.submit
        if not getattr(self.win, "last_submit_ok", False):
            c.edit.clear()  # the words are kept by the page itself (give_back put them in this box too)
            c.attached = files  # _send emptied the box; nothing was sent, so it all goes back
            c._show_attached()
            for k in mentions:
                c.add_mention(k)
            return json.dumps({"ok": False, "box": self._box(c)}, ensure_ascii=False)
        return json.dumps({"ok": True}, ensure_ascii=False)

    @Slot(str, result=str)
    def estimate(self, where: str) -> str:
        """Before a message goes: what questions like it used here before, and the user's limit."""
        try:
            out = self.win.estimate(self._composer(where))
        except Exception:  # no estimate: the message still goes, the limit still holds
            out = {"typical": 0, "count": 0, "limit": 0}
        return json.dumps(out)

    @Slot(str, str, result=str)
    def set_model(self, where: str, pick: str) -> str:
        c = self._composer(where)
        c._set_model(json.loads(pick), "")
        self.win.remember_pick(c)  # kept: the chat it opens, the next new chat and the next start show it
        return json.dumps(self._box(c), ensure_ascii=False)

    @Slot(str, str, result=str)
    def set_level(self, where: str, key: str) -> str:
        c = self._composer(where)
        c._set_level(key or None, "")
        self.win.remember_pick(c)
        return json.dumps(self._box(c), ensure_ascii=False)

    @Slot(str, str, bool, result=str)
    def set_approval(self, where: str, key: str, confirmed: bool = False) -> str:
        c = self._composer(where)
        if key == "full" and not confirmed and c.approval != "full":
            pass  # 完全放开 only after the page's own confirmation (it passes confirmed): never from a stray call
        elif key in ("ask", "auto", "full"):
            c.approval = key
        return json.dumps(self._box(c), ensure_ascii=False)

    @Slot(str, str, bool, result=str)
    def mention(self, where: str, key: str, on: bool) -> str:
        c = self._composer(where)
        if on:
            c.add_mention(key)
        else:
            c.remove_mention(key)
        return json.dumps(self._box(c), ensure_ascii=False)

    @Slot(str, result=str)
    def pick_files(self, where: str) -> str:
        from PySide6.QtWidgets import QFileDialog

        c = self._composer(where)
        paths, _ = QFileDialog.getOpenFileNames(self.win, _t("加文件"), "", "*.*")
        c.add_files(paths)
        return json.dumps(self._box(c), ensure_ascii=False)

    @Slot(str, int, result=str)
    def drop_file(self, where: str, index: int) -> str:
        c = self._composer(where)
        if 0 <= index < len(c.attached):
            del c.attached[index]
            c._show_attached()
        return json.dumps(self._box(c), ensure_ascii=False)

    @Slot()
    def stop(self) -> None:
        self.win.control("cancel_task", confirm=False)

    @Slot()
    def resume(self) -> None:
        self.win.control("resume_task")

    # --- 详细 (web_details.py) -------------------------------------------------------------------------------------------

    @Slot(str, result=str)
    def details_json(self, task_id: str) -> str:
        from codedoctor.desktop import web_details

        try:
            out = web_details.details_json(self.win, task_id)
        except Exception as e:  # shown where the details would be; the chat stays usable
            out = {"error": f"{type(e).__name__}: {e}"}
        return json.dumps(out, ensure_ascii=False)

    @Slot(str, str, result=str)
    def ws_rows(self, task_id: str, tab: str) -> str:
        from codedoctor.desktop import web_details

        try:
            out = web_details.workspace_rows(self.win, task_id, tab)
        except Exception as e:
            out = {"note": f"{type(e).__name__}: {e}", "rows": []}
        return json.dumps(out, ensure_ascii=False)

    @Slot(str, str, int, result=str)
    def ws_detail(self, task_id: str, tab: str, index: int) -> str:
        from codedoctor.desktop import web_details

        return json.dumps(web_details.workspace_detail(self.win, task_id, tab, index), ensure_ascii=False)

    @Slot(str, result=str)
    def ws_undo(self, task_id: str) -> str:
        from codedoctor.desktop import web_details

        return json.dumps(web_details.workspace_undo(self.win, task_id), ensure_ascii=False)

    @Slot(str, str, result=str)
    def remember(self, task_id: str, text: str) -> str:
        from codedoctor.desktop import web_details

        return json.dumps(web_details.remember(self.win, task_id, text), ensure_ascii=False)

    # --- the sidebar ---------------------------------------------------------------------------------------------------

    @Slot(str)
    def go(self, key: str) -> None:
        """home, plugins, settings (or one of its pages), browser, terminal."""
        self.win.navigate(key)

    @Slot(str)
    def open_task(self, task_id: str) -> None:
        self.win.open_task(task_id)

    @Slot(str, str)
    def open_project(self, config: str, task_id: str) -> None:
        """Another folder (on one of its chats): this window closes and opens there, asking first if tasks are running."""
        self.win.switch_project(config, task_id or None)

    @Slot()
    def open_folder(self) -> None:
        self.win.open_folder()

    @Slot(str, result=str)
    def folder_chats(self, config: str) -> str:
        """Another folder's recent chats, read from its database, each once."""
        from codedoctor.desktop.sidebar import RUNNING, other_project_tasks

        return json.dumps([{"id": c["id"], "title": c["title"], "open": c["open"], "running": task_status(c) in RUNNING}
                           for c in other_project_tasks(config, 30)], ensure_ascii=False)

    @Slot(str)
    def pin(self, chat_id: str) -> None:
        self.win.sidebar._toggle_pin(chat_id)
        self.win.web.push_side(force=True)

    @Slot(str, str)
    def rename(self, chat_id: str, name: str) -> None:
        from codedoctor.desktop import chat_tools

        sb = self.win.sidebar
        chat_tools.rename(sb.config_path or "", chat_id, name)
        sb.reload_names()
        self.win.web.push_side(force=True)

    @Slot(str)
    def hide_chat(self, chat_id: str) -> None:
        """从列表里收起: off the list, nothing deleted (Ctrl+K → 放回收起的聊天 shows it again)."""
        self.win.sidebar._put_away(chat_id)
        self.win.web.push_side(force=True)

    @Slot(str)
    def export_chat(self, chat_id: str) -> None:
        self.win.export_chat(chat_id)

    @Slot(str, result=str)
    def search(self, needle: str) -> str:
        """Chats that say this anywhere, in a question or an answer."""
        from codedoctor.desktop import chat_tools

        needle = needle.strip()
        if len(needle) < 2:
            return "[]"
        try:
            found = chat_tools.search_chats(self.win.d, needle)
        except Exception:  # the list's own filter still works
            found = []
        return json.dumps(found, ensure_ascii=False)

    @Slot()
    def palette(self) -> None:
        self.win.open_palette()

    # --- 插件 ----------------------------------------------------------------------------------------------------------

    @Slot(result=str)
    def plugins(self) -> str:
        """What is known now; CodeTools lists its plugins in a moment (Python has to start), then plugins_ready."""
        page = self.win.plugins_page
        if not getattr(self, "_plugins_hooked", False):
            self._plugins_hooked = True
            self._plugins_done = False

            def ready(found):
                self._plugins_done = True
                self.plugins_ready.emit(json.dumps(plugins_json(found, True), ensure_ascii=False))
            page.ready.connect(ready)
        from codedoctor.desktop import i18n

        if page.plugins is None or getattr(page, "lang", None) != i18n.language():
            self._plugins_done = False
            page.load()  # not read yet, or read in another language
        return json.dumps(plugins_json(page.plugins, self._plugins_done), ensure_ascii=False)

    @Slot(str, str)
    def open_plugin(self, tool: str, plugin: str) -> None:
        """A big tool's own window, or one of CodeTools' small plugins in CodeTools."""
        from codedoctor import makers

        makers.open_app(tool, plugin)

    # --- 设置 (web_settings.py) -------------------------------------------------------------------------------------------

    @Slot(result=str)
    def settings(self) -> str:
        from codedoctor.desktop import web_settings

        return json.dumps(web_settings.state(self.win), ensure_ascii=False)

    @Slot(str, result=str)
    def settings_form(self, endpoint_id: str) -> str:
        from codedoctor.desktop import web_settings

        return json.dumps(web_settings.form(self.win, endpoint_id), ensure_ascii=False)

    @Slot(str, str, result=str)
    def settings_act(self, action: str, data: str) -> str:
        """One change; a key typed for a service arrives here and stays in this process (never sent back, never logged)."""
        from codedoctor.desktop import web_settings

        return json.dumps(web_settings.act(self.win, action, json.loads(data or "{}")), ensure_ascii=False)

    @Slot(result=str)
    def settings_save(self) -> str:
        from codedoctor.desktop import web_settings

        return json.dumps(web_settings.save(self.win), ensure_ascii=False)

    @Slot(result=str)
    def settings_revert(self) -> str:
        from codedoctor.desktop import web_settings

        return json.dumps(web_settings.revert(self.win), ensure_ascii=False)

    @Slot(str, str, str)
    def settings_probe(self, what: str, data: str, token: str) -> None:
        from codedoctor.desktop import web_settings

        def done(result: dict) -> None:
            try:
                self.probed.emit(json.dumps({"token": token, **result}, ensure_ascii=False))
            except RuntimeError:  # the window closed meanwhile
                pass
        web_settings.probe(self.win, what, json.loads(data or "{}"), done)

    @Slot(str, str, result=str)
    def knowledge(self, tab: str, needle: str) -> str:
        from codedoctor.desktop import web_settings

        return json.dumps(web_settings.knowledge(self.win, tab, needle), ensure_ascii=False)

    @Slot(str, result=str)
    def book(self, lang: str) -> str:
        from codedoctor.desktop import web_settings

        return json.dumps(web_settings.book(lang), ensure_ascii=False)

    @Slot(str)
    def settings_section(self, key: str) -> None:
        """The section shown, remembered for the next 设置."""
        self.win.web.last = {**self.win.web.last, "section": key}
        self.win.settings_section = key

    @Slot()
    def restart(self) -> None:
        self.win.restart()

    @Slot()
    def replay_welcome(self) -> None:
        self.win._show_welcome()

    # --- the browser on the right: its frame is the page's, its pages Chromium's ----------------------------------------------

    @Slot(result=str)
    def browser_state(self) -> str:
        self.win.browser.ensure()
        return json.dumps(self.win.browser.as_json(), ensure_ascii=False)

    @Slot(str)
    def browser_go(self, text: str) -> None:
        if text.strip():
            self.win.browser.go(text)

    @Slot(str)
    def browser_act(self, what: str) -> None:
        """back, forward, reload, stop, new, reopen, star, to_chat, ray_close, ray_chat."""
        b = self.win.browser
        if what in ("back", "forward", "reload", "stop"):
            b._act(what)
        elif what == "new":
            b.add_tab()
        elif what == "reopen":
            b.reopen_tab()
        elif what == "star":
            b._toggle_star()
        elif what == "to_chat":
            b._to_chat()
        elif what == "ray_close":
            b.panel._close()
        elif what == "ray_chat" and b.panel.task:
            self.win.open_task(b.panel.task)

    @Slot(int)
    def browser_tab(self, index: int) -> None:
        self.win.browser.select_tab(index)

    @Slot(int)
    def browser_close(self, index: int) -> None:
        b = self.win.browser
        if 0 <= index < len(b.views):
            b.close_tab(index)

    @Slot(result=str)
    def browser_marks(self) -> str:
        from codedoctor.desktop import chat_tools

        return json.dumps(chat_tools.bookmarks()[:60], ensure_ascii=False)

    # --- the terminal on the right (web_dock.py) --------------------------------------------------------------------------

    @Slot(result=str)
    def term_state(self) -> str:
        return json.dumps(self.win.dock.term_state(), ensure_ascii=False)

    @Slot(str)
    def term_input(self, data: str) -> None:
        self.win.dock.type(data)

    @Slot(int, int)
    def term_resize(self, cols: int, rows: int) -> None:
        self.win.dock.resize(cols, rows)

    @Slot()
    def term_interrupt(self) -> None:
        self.win.dock.interrupt()

    @Slot(str)
    def term_to_chat(self, text: str) -> None:
        """Right click in the terminal: what was selected, or the last screenful, into the message box."""
        self.win.put_in_box(f"```\n{text}\n```")

    # --- room for what stays Qt ----------------------------------------------------------------------------------------

    @Slot(str, float, float, float, float)
    def slot(self, name: str, x: float, y: float, w: float, h: float) -> None:
        """Where the page left room for a Qt part ("page" or "tool"); zero size: it is not shown."""
        self.win.web.place(name, (x, y, w, h))

    @Slot()
    def close_tool(self) -> None:
        self.win.close_tool()

    @Slot(str)
    def pick_tool(self, key: str) -> None:
        self.win.pick_tool(key)

    @Slot(result=str)
    def asks_now(self) -> str:
        return json.dumps(asks_json(self.win), ensure_ascii=False)

    @Slot(str, bool)
    def decide_ask(self, action_id: str, approve: bool) -> None:
        """The long approve / refuse button: one action waiting for the user (the gate's record), decided here and nowhere else."""
        try:
            self.win.d.s.computer.user_decides(action_id, bool(approve), "decided in the Lumen window")
        except PermissionError:
            pass  # already decided, timed out or stopped meanwhile
        self.win.web.push_asks()

    @Slot(str, str)
    def answer_ask(self, qid: str, answers: str) -> None:
        """The question panel's answers go straight back to the agent that asked."""
        from codedoctor.agents import ask_user

        given = json.loads(answers or "[]")
        ask_user.answer(self.win.d.s, qid, given)
        q = ask_user.take_follow_up(self.win.d.s, qid)
        self.win.web.push_asks()
        if q is None:
            return
        # a turn that ended 被拦下 (_ask_when_blocked): the answer is the user's next message in that chat, unless they said stop
        a = given[0] if given else {}
        words = [str(c) for c in (a.get("choices") or [])] + ([str(a.get("other")).strip()] if str(a.get("other") or "").strip() else [])
        if not words or a.get("skipped") or words == [_t("先不做了")]:
            return
        self.send("chat", "；".join(words))

    @Slot(str, bool)
    def fold_turn(self, turn_id: str, folded: bool) -> None:
        """省略 / 展开过程 on one turn: kept for good, so it is the same after another chat or a restart."""
        from codedoctor.desktop import prefs as ui_prefs

        ui = ui_prefs.load()
        folds = dict(ui.get("fold_turns") or {})
        folds.pop(turn_id, None)
        folds[turn_id] = bool(folded)
        ui["fold_turns"] = dict(list(folds.items())[-2000:])
        ui_prefs.save(ui)

    @Slot(str, bool)
    def find(self, text: str, back: bool) -> None:
        self.win.web.find(text, back)

    @Slot()
    def back(self) -> None:
        """返回 above a Qt page (详细): to the chat it belongs to, else the new chat."""
        tid = self.win.task_view.task_id
        if tid and self.win.web.last.get("key") == "details":
            self.win.open_task(tid)
        else:
            self.win.navigate("home")

    # --- elsewhere in the window -------------------------------------------------------------------------------------

    @Slot(str)
    def details(self, task_id: str) -> None:
        """The full investigation view (claims, anomalies, changes, computer actions): the Qt page, as before."""
        self.win.open_details(task_id)

    @Slot(str)
    def open_link(self, url: str) -> None:
        self.win.open_link(url)

    @Slot(str)
    def copy(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)

    # --- voice -------------------------------------------------------------------------------------------------------

    @Slot(result=bool)
    def voice_start(self) -> bool:
        from codedoctor.desktop import voice

        if not voice.available():
            return False
        old, self.recorder = self.recorder, None
        if old is not None:  # one still recording would keep the microphone
            old.stop()
        rec = self.recorder = voice.Recorder()
        rec.failed.connect(lambda why: self.heard.emit(json.dumps(
            {"error": _t("没有找到麦克风，或者它被别的程序占用了。") if why == "no_mic" else str(why)}, ensure_ascii=False)))
        rec.start()
        voice.warm()
        return True

    @Slot(str)
    def voice_stop(self, language: str) -> None:
        from codedoctor.desktop import voice

        rec, self.recorder = self.recorder, None
        if rec is None:
            return
        pcm = rec.stop()

        def work():
            try:
                text = voice.transcribe(pcm, language or "zh")
                self.heard.emit(json.dumps({"text": text}, ensure_ascii=False))
            except Exception as e:
                self.heard.emit(json.dumps({"error": str(e)}, ensure_ascii=False))
        threading.Thread(target=work, daemon=True, name="voice-text").start()

    @Slot()
    def voice_cancel(self) -> None:
        rec, self.recorder = self.recorder, None
        if rec is not None:
            rec.stop()


class WebChat(QWidget):
    """The page and its bridge. show / show_home / show_chat tell the page what to draw; the Qt parts that stay lie over it
    (adopt, place)."""

    def __init__(self, win):
        super().__init__()
        from PySide6.QtWebChannel import QWebChannel
        from PySide6.QtWebEngineCore import QWebEngineSettings
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.win = win
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.view = QWebEngineView(self)
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.bridge = Bridge(win)
        self.channel = QWebChannel(self)
        self.channel.registerObject("lumen", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.page().setBackgroundColor(paper(win.ui))  # nothing white flashes before the page draws in the dark mode
        self.view.setContextMenuPolicy(Qt.NoContextMenu)  # the page has its own menus; 重新加载/查看源代码 are not for users
        self.view.load(QUrl.fromLocalFile(str(DIST / "index.html")))
        self.last: dict = {"page": "home"}
        self.view.loadFinished.connect(lambda _ok: self.bridge.show.emit(json.dumps(self.last)))
        # A white flash with everything gone, then back (the user, 2026-11-14): the page's renderer process dying is that. It
        # is written to flash.log and the page loaded again at once, instead of staying white; a page that starts loading
        # again by itself is written down too.
        self.view.page().renderProcessTerminated.connect(self._renderer_died)
        self.view.loadStarted.connect(lambda: flash_log("page", "loadStarted", (0, 0, 0, 0), (0, 0, 0, 0)))
        self.parts: dict[str, QWidget] = {}
        self.rects: dict[str, tuple] = {}
        self._side = ""
        self._tool_on = False
        self.bridge.asks_poke.connect(self.push_asks)  # emitted from the thread that asks, handled on this one
        self._tools: list = []
        self._tool_key = ""

    # --- the Qt parts over the page ----------------------------------------------------------------------------------

    def adopt(self, page: QWidget, tool: QWidget, browser: QWidget | None = None) -> None:
        """The stack of Qt pages (shown where the page leaves room for it), the @ tool's window (above the chat) and the
        browser's pages (in the panel on the right)."""
        self.parts = {"page": page, "tool": tool}
        tool.frameless = True  # its row, its word while it starts and any error are the page's (Chat.jsx ToolArea)
        tool.changed.connect(self._tool_changed)
        if browser is not None:
            self.parts["browser"] = browser
            browser.go_frameless()
            browser.changed.connect(self._browser_changed)
        for w in self.parts.values():
            w.setParent(self)
            w.setAttribute(Qt.WA_NativeWindow, True)  # native from the start: a native child made later remakes its parents' windows
            w.setAutoFillBackground(True)  # opaque: nothing of the page under it shows through
            pal = w.palette()
            pal.setColor(w.backgroundRole(), paper(self.win.ui))
            w.setPalette(pal)
            w.hide()

    def place(self, name: str, rect: tuple) -> None:
        self.rects[name] = rect
        self._apply(name)

    def _wanted(self, name: str) -> bool:
        if name == "browser":  # while the panel shows the browser its native view stays: the start page is drawn by it too
            return "browser" in getattr(self.win.dock, "open", []) and self.win.browser.current() is not None
        if name == "tool":
            return self._tool_on and self.win.tool_view.ready()
        return self.last.get("page") == "native" if name == "page" else self._tool_on

    def _apply(self, name: str) -> None:
        w = self.parts.get(name)
        if w is None:
            return
        x, y, width, height = self.rects.get(name, (0, 0, 0, 0))
        if not self._wanted(name) or width < 2 or height < 2:
            if w.isVisible():
                self._hide_later(name, w)  # a hide that a show follows at once is not done (each one repaints the window)
            return
        self._cancel_hide(name)
        # Only what changed is touched. These parts are native windows lying over the page's own: moving, showing or raising one
        # that is already there repaints the whole window, which was the flashing white screen (the panel's rect is asked
        # again every 0.8 s by push_side).
        geo = (round(x), round(y), round(width), round(height))
        before = (w.x(), w.y(), w.width(), w.height())
        if before != geo:
            flash_log(name, "setGeometry", before, geo)
            w.setGeometry(*geo)
        if not w.isVisible():
            flash_log(name, "show", before, geo)
            w.show()
            w.raise_()

    def _hide_later(self, name: str, w) -> None:
        from PySide6.QtCore import QTimer

        timers = self.__dict__.setdefault("_hiding", {})
        if name in timers:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)

        def hide() -> None:
            if timers.get(name) is timer:  # a newer timer of this part is not removed by an older one
                timers.pop(name, None)
            if w.isVisible() and not self._wanted(name):
                why = f"hide rect={tuple(round(v) for v in self.rects.get(name, (0, 0, 0, 0)))}"
                if name == "tool":  # why the tool's window went: the pane closed, its program ended, or the page gave no room
                    tv = self.win.tool_view
                    why += f" pane={self._tool_on} state={tv.info.get('state')} current={tv.current}"
                flash_log(name, why, (w.x(), w.y(), w.width(), w.height()), (0, 0, 0, 0))
                w.hide()
        timer.timeout.connect(hide)
        timers[name] = timer
        timer.start(250)

    def _cancel_hide(self, name: str) -> None:
        timer = self.__dict__.get("_hiding", {}).pop(name, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.view.setGeometry(self.rect())

    def _renderer_died(self, status, code) -> None:
        """The page's renderer process ended (it is a separate Chromium process): written down, and the page comes back."""
        flash_log("page", f"renderer-ended status={int(getattr(status, 'value', status))} code={code}", (0, 0, 0, 0), (0, 0, 0, 0))
        QTimer.singleShot(300, lambda: self.view.load(QUrl.fromLocalFile(str(DIST / "index.html"))))

    def changeEvent(self, e):
        super().changeEvent(e)
        from PySide6.QtCore import QEvent

        if e.type() in (QEvent.WindowStateChange, QEvent.ActivationChange):  # with the page's own events, a flash can be placed
            flash_log("window", "state" if e.type() == QEvent.WindowStateChange else "activation", (0, 0, 0, 0), (0, 0, 0, 0))

    # --- what the page draws -----------------------------------------------------------------------------------------

    def show_view(self, view: dict) -> None:
        self.last = view
        self._apply("page")
        self.bridge.show.emit(json.dumps(view, ensure_ascii=False))
        self.push_side()

    def show_home(self) -> None:
        self.show_view({"page": "home"})

    def show_chat(self, task_id: str) -> None:
        chat = self.win.task_view.chat_id
        if getattr(self, "_box_chat", None) not in (None, chat):  # another conversation: its box starts empty
            self.win.task_view.composer.drop_draft()
        self._box_chat = chat
        self.show_view({"page": "chat", "task_id": task_id})

    def show_native(self, key: str, **more) -> None:
        """A page still drawn by Qt, beside the sidebar."""
        self.show_view({"page": "native", "key": key, **more})

    def set_tool(self, on: bool, name: str = "", tools: list | None = None, current: str = "") -> None:
        self._tool_on = on
        self._tools, self._tool_key = tools or [], current
        self._apply("tool")
        info = self.win.tool_view.info if on else {}
        self.bridge.tool.emit(json.dumps({"on": on, "name": name, "tools": tools or [], "current": current, "ask": _t(info.get("ask", "")), "state": info.get("state", ""),
                                          "why": _t(info.get("why", ""))}, ensure_ascii=False))

    def push_asks(self) -> None:
        text = json.dumps(asks_json(self.win), ensure_ascii=False)
        if text != getattr(self, "_asks_last", ""):
            self._asks_last = text
            self.bridge.asks.emit(text)

    def _browser_changed(self) -> None:
        self._apply("browser")
        text = json.dumps(self.win.browser.as_json(), ensure_ascii=False)
        if text != getattr(self, "_browser_last", ""):
            self._browser_last = text
            self.bridge.browser.emit(text)

    def _tool_changed(self) -> None:
        if self._tool_on:
            self.set_tool(True, self.win.tool_view.info.get("name", ""), self._tools, self._tool_key)

    def push_side(self, force: bool = False) -> None:
        """The sidebar again, when anything in it changed (the window refreshes every 0.8 s); the panel on the right with it."""
        self._apply("browser")
        try:
            text = json.dumps(side_json(self.win), ensure_ascii=False)
        except Exception:  # never stops the refresh; the list stays as it was
            return
        if force or text != self._side:
            self._side = text
            self.bridge.side.emit(text)

    def push_prefs(self) -> None:
        self.view.page().setBackgroundColor(paper(self.win.ui))
        for part in self.parts.values():
            pal = part.palette()
            pal.setColor(part.backgroundRole(), paper(self.win.ui))
            part.setPalette(pal)
        self.bridge.prefs.emit(json.dumps(prefs_json(self.win.ui), ensure_ascii=False))

    def command(self, do: str) -> None:
        self.bridge.command.emit(json.dumps({"do": do}))

    def find(self, text: str, back: bool) -> None:
        from PySide6.QtWebEngineCore import QWebEnginePage

        def done(result):
            self.bridge.found.emit(json.dumps({"count": result.numberOfMatches(), "at": result.activeMatch()}))
        flags = QWebEnginePage.FindFlag.FindBackward if back else QWebEnginePage.FindFlag(0)
        self.view.page().findText(text, flags, done)


_flash_lines = 0


def flash_log(part: str, action: str, old: tuple, new: tuple) -> None:
    """One line in flash.log (next to the user's settings, CODEDOCTOR_HOME) for every time a native part over the page is shown,
    hidden or moved, and who asked - so a flash can be traced to its cause. At most about 2000 lines are kept."""
    global _flash_lines
    import traceback
    from datetime import datetime

    from codedoctor.desktop import prefs

    try:
        path = prefs._path().with_name("flash.log")
        who = " < ".join(f"{f.name}:{f.lineno}" for f in reversed(traceback.extract_stack(limit=5)[:-2][-2:]))
        line = f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {part} {action} {tuple(old)} -> {tuple(new)} by {who}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
        _flash_lines += 1
        if _flash_lines % 200 == 1:  # also the first write of a run: the file of an earlier run is cut too
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            if len(lines) > 2000:
                path.write_text("".join(lines[-1500:]), encoding="utf-8")
    except OSError:
        pass  # a log must never be the reason for a problem


def Qt_white():
    from PySide6.QtGui import QColor

    return QColor("#ffffff")


def paper(ui: dict):
    """The page's own white, or its dark (styles.css --paper)."""
    from PySide6.QtGui import QColor

    return QColor("#1c1c1f" if ui.get("mode") == "dark" else "#ffffff")


def available() -> bool:
    return (DIST / "index.html").is_file()


def enabled(ui: dict) -> bool:
    """The React window, whenever it is built (npm run build in web/). There is no other window any more."""
    return available()
