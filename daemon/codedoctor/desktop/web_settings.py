"""设置 in React (web/src/Settings.jsx): what the page shows and what each of its controls does.

The settings stay where they were: the project's configuration as ModelsPage holds it (its raw copy, the keys typed and not
yet saved, whether anything changed), the user's own preferences in prefs.py, keys in Windows Credential Manager. The page
asks for the state (state), sends one change at a time (act) and gets the new state back; 保存 writes it all as the Qt
page did (save). A key typed into the page comes here once, to be kept with the unsaved changes; it is never sent back to
the page, never written into the configuration, never logged.

Sections the page draws: services, agent_models, memory, appearance, usage, code, computer (web_cfgpages.py: they edit the
configuration like the rest).
"""

from __future__ import annotations

import copy
import os
import re
import time
from datetime import date, timedelta

from codedoctor import config as config_mod
from codedoctor import providers, secrets
from codedoctor.desktop import locale, web_cfgpages
from codedoctor.desktop.settings_view import (_NOTHING, DATA_CLASS_CN, TOOL_CN, agents_summary, endpoint_of, fallbacks_text,
                                              key_status, parse_fallbacks, watched_ids)

SECTIONS = ("services", "agent_models", "memory", "appearance", "usage", "knowledge", "book",
            "code", "computer")
KEY_TEXT = {"keyring": "密钥已保存", "env": "密钥来自环境变量", "missing": "缺少密钥", "not_needed": "无需密钥"}
APPEARANCE = {  # preference -> its choices (prefs.py)
    "accent": (("amber", "光的琥珀"), ("blue", "天蓝"), ("violet", "紫"), ("green", "绿"), ("rose", "玫瑰"), ("ink", "墨")),
    "font_size": (("small", "小"), ("normal", "中"), ("large", "大")),
    "chat_width": (("narrow", "窄"), ("normal", "中"), ("wide", "宽")),
    "send_key": (("enter", "Enter 发送，Shift+Enter 换行"), ("ctrl_enter", "Ctrl+Enter 发送，Enter 换行")),
    "search_engine": (("google", "Google"), ("bing", "必应")),
    "mode": (("light", "浅色"), ("dark", "深色")),
    "spend_limit": ((0, "不限"), (50_000, "5 万"), (100_000, "10 万"), (300_000, "30 万"), (1_000_000, "100 万"), (3_000_000, "300 万")),
    "term_font": ((11, "11"), (12, "12"), (13, "13"), (14, "14"), (15, "15"), (16, "16"), (18, "18")),
}
SWITCHES = ("reduced_motion", "figure_motion", "show_times", "expand_steps", "auto_fold", "notify_done", "show_tokens")
t = locale.t
NOTE_KIND_CN = {"fact": "事实", "decision": "决定", "observation": "观察", "todo": "待办", "summary": "任务总结", "claim": "结论"}
SHOWN = 150  # records of the knowledge page shown at most


def _choices(pairs) -> list[dict]:
    return [{"value": v, "label": t(text)} for v, text in pairs]


# --- what the page shows -----------------------------------------------------------------------------------------------

def _used_by(raw: dict, eid: str) -> list[str]:
    return [a["id"] for a in raw["agents"] if a["endpoint"] == eid or any(f["endpoint"] == eid for f in a.get("fallbacks", []))]


def _endpoint(raw: dict, e: dict, pending) -> dict:
    status = key_status(e)
    kind = {"anthropic": "Anthropic 接口", "scripted": "测试脚本"}.get(e["kind"], "OpenAI 兼容接口")
    if e["kind"] == "engine":  # Claude Code or Codex on the user's own plan
        from codedoctor import engines

        kind = engines.TITLES.get(e.get("base_url", "").split(":", 1)[-1], e["kind"])
    used = _used_by(raw, e["id"])
    out = {"id": e["id"], "name": t(e.get("name") or e["id"]), "kind": e["kind"], "kind_text": t(kind), "base_url": e.get("base_url", ""),
           "local": bool(e.get("local")), "status": status, "status_text": t(KEY_TEXT.get(status, status)),
           "pending": "typed" if isinstance(pending, str) else "drop" if pending is None else "",
           "data_class": t(dict(DATA_CLASS_CN).get(e.get("max_data_class", "local_only" if e.get("local") else "internal"), "")),
           "used_by": used, "used_text": t(agents_summary(used)), "keyring": bool(e.get("api_key_keyring")), "key_env": e.get("api_key_env") or "",
           "models": list(e.get("models", [])), "editable": e["kind"] in ("openai_compatible", "anthropic")}
    return out


def _form(e: dict | None, page) -> dict:
    """An endpoint as the add / edit form shows it (never its key)."""
    if e is None:
        return {}
    pending = page.pending_keys.get(e["id"], _NOTHING)
    saved = secrets.key_status(endpoint_of({**e, "api_key_env": None, "api_key_keyring": True})) == "keyring"
    return {"id": e["id"], "name": e.get("name", e["id"]), "provider": e.get("provider") or ("custom-anthropic" if e["kind"] == "anthropic" else "custom"),
            "kind": e["kind"], "base_url": e.get("base_url", ""), "local": bool(e.get("local")),
            "key_mode": "keyring" if e.get("api_key_keyring") else "env" if e.get("api_key_env") else "none",
            "key_env": e.get("api_key_env", ""), "data_class": e.get("max_data_class", "local_only" if e.get("local") else "internal"),
            "text_calls": e.get("text_tool_calls", True), "models": "\n".join(e.get("models", [])),
            "key_saved": saved, "key_pending": "typed" if isinstance(pending, str) else "drop" if pending is None else ""}


def _agent(a: dict, mode: str, workers: set[str]) -> dict:
    from codedoctor.agents import team
    from codedoctor.desktop.web_chat import _avatar
    from codedoctor.ui_text import ROLE_CN

    m = team.BY_ID.get(a["id"]) if a.get("team") else None
    watched = watched_ids(a)
    removable = not a.get("team") and mode == "advanced" and a["role"] in ("worker", "investigator", "guardian") and \
        (a["role"] == "guardian" or len(workers) > 1)
    return {"id": a["id"], "team": bool(m), "name": m.name if m else ("Lumen" if a["id"] == "doctor" else a["id"]), "cn": m.cn if m else "", "colour": m.colour if m else "",
            "job": t(m.job) if m else t(ROLE_CN.get(a["role"], a["role"])) + (t(" · 监督 ") + "、".join(watched) if watched else ""),
            "meaning": t(m.meaning) if m else "", "avatar": _avatar(a["id"]) if m else "", "role": a["role"],
            "endpoint": a["endpoint"], "model": a.get("model", ""), "think": (a.get("params") or {}).get("reasoning") or "medium",
            "fallbacks": fallbacks_text(a), "removable": removable}


def _usage(win) -> dict:
    from codedoctor.desktop import chat_tools
    from codedoctor.desktop.usage_view import DAYS, short

    rows = chat_tools.usage_rows(win.d)
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(DAYS - 1, -1, -1)]
    s = chat_tools.usage_summary(rows, today.isoformat(), days)
    tiles = [{"key": k, "title": t(title), "value": short(s[k]["fresh"]), "cached": short(s[k]["cached"]), "answers": s[k]["answers"],
              "cost": round(s[k]["cost"], 2) if s[k]["cost"] else 0} for k, title in (("today", "今天"), ("week", "最近 7 天"), ("all", "全部"))]
    return {"tiles": tiles, "days": [{"day": d, "value": v, "short": short(v)} for d, v in s["by_day"]],
            "who": [{"who": w, "fresh": short(f), "cost": round(c, 2) if c else 0, "answers": n} for w, f, c, n in s["by_who"][:12]]}


def state(win) -> dict:
    from codedoctor import topology
    from codedoctor.desktop import i18n
    from codedoctor.desktop import prefs as ui_prefs
    from codedoctor.models.reasoning import LEVEL_CN, LEVELS

    page = win.models_page
    raw = page.raw
    ui = ui_prefs.load()
    out = {"editable": raw is not None, "dirty": page.dirty, "path": str(page.path or ""),
           "appearance": {"values": {k: ui[k] for k in (*APPEARANCE, *SWITCHES, "wallpaper", "language")},
                          "choices": {**{k: _choices(v) for k, v in APPEARANCE.items()}, "wallpaper": _choices(ui_prefs.WALLPAPERS),
                                      "language": [{"value": v, "label": text} for v, text in i18n.LANGS]}},
           "usage": _usage(win), "known": _known(win)}
    if raw is None:
        return out
    mode = topology.current(raw)[0]
    workers = {a["id"] for a in raw["agents"] if a["role"] in ("worker", "investigator")}
    first = next(iter(raw["agents"]), {})
    emb = (raw.get("memory") or {}).get("embedding") or {}
    out.update({
        "endpoints": [_endpoint(raw, e, page.pending_keys.get(e["id"], _NOTHING)) for e in raw["endpoints"]],
        "agents": [_agent(a, mode, workers) for a in raw["agents"]],
        "mode": mode, "levels": [{"value": k, "label": t(LEVEL_CN[k])} for k in LEVELS],
        "memory": {"recall": any(int((a.get("memory") or {}).get("recall_k", 8)) > 0 for a in raw["agents"]),
                   "embedding": {"endpoint": emb.get("endpoint") or "", "model": emb.get("model", ""),
                                 "endpoints": [{"value": e["id"], "label": e.get("name") or e["id"], "models": list(e.get("models", []))}
                                               for e in raw["endpoints"] if e["kind"] == "openai_compatible"]}},
        "presets": [{"id": p.id, "name": t(p.name), "kind": p.kind, "base_url": p.base_url, "key_env": p.key_env or "", "local": p.local,
                     "note": t(p.note)} for p in providers.PRESETS],
        "data_classes": _choices(DATA_CLASS_CN),
        "code": web_cfgpages.code(raw), "computer": web_cfgpages.computer(raw, DATA_CLASS_CN),
    })
    return out


def form(win, eid: str) -> dict:
    """The add / edit form of one service ({} for a new one)."""
    page = win.models_page
    e = next((x for x in (page.raw or {}).get("endpoints", []) if x["id"] == eid), None)
    return _form(e, page)


# --- what the page changes ---------------------------------------------------------------------------------------------

class Refused(ValueError):
    """Not done, and why (shown on the page)."""


AT_ONCE = ("code", "code_detect", "computer", "memory")  # these take effect as soon as they change
SAVE_FAILED = "这次的修改没能写进配置文件，但在这次运行里照样有效。"


def apply_now(win, saved) -> None:
    """The running window and its agents take the saved rules: no restart. (The configuration objects are frozen: replaced in place.)"""
    for conf in {id(c): c for c in (win.cfg, win.d.s.config)}.values():
        object.__setattr__(conf, "permissions", saved.permissions)
        object.__setattr__(conf, "computer", saved.computer)
    gate = getattr(win.d.s, "computer", None)
    if gate is not None:
        gate.policy = saved.computer
        if gate.desktop is None and saved.computer.enabled:
            from codedoctor.computer.desktop import default_desktop

            gate.desktop = default_desktop()
    for aid, agent in win.d.s.config.agents.items():  # the long-term memory switch
        if aid in saved.agents:
            object.__setattr__(agent, "recall_k", saved.agents[aid].recall_k)


def at_once(win) -> str:
    """Take what changed (permissions, computer use, memory) into the running window now, and write it to the file. "" when all went
    well, else one sentence in words (never the schema's). Nothing else the page changed is touched: those wait for 保存."""
    page = win.models_page
    if page.pending_keys or any(not a.get("model") for a in page.raw["agents"]):
        return ""  # a service or an AI is half done: 保存 handles it, with its own words
    try:
        saved = config_mod.parse(copy.deepcopy(page.raw), base_dir=page.path.parent if page.path else None, source=page.path)
    except Exception:
        return t(SAVE_FAILED)
    apply_now(win, saved)
    try:
        config_mod.save_raw(page.raw, page.path)
    except Exception:
        return t(SAVE_FAILED)
    page.dirty = False
    page.saved_agents = len(saved.agents)
    return ""


def _changed(page) -> None:
    page.dirty = True
    page._web_stale = True  # the Qt page rebuilds from raw before it is next shown (MainWindow.navigate)


def _endpoint_value(page, data: dict, existing: dict | None) -> dict:
    """The service as it will be written to the configuration (no key in it), checked as the Qt dialog checked it."""
    taken = {e["id"] for e in page.raw["endpoints"]} - ({existing["id"]} if existing else set())
    e = dict(existing or {})
    local = bool(data.get("local"))
    eid = (existing or {}).get("id") or str(data.get("id", "")).strip()
    e.update(id=eid, name=str(data.get("name", "")).strip() or eid, provider=data.get("provider") or "custom",
             kind=data.get("kind") or "openai_compatible", base_url=str(data.get("base_url", "")).strip().rstrip("/"), local=local,
             max_data_class=data.get("data_class") or ("local_only" if local else "internal"))
    for k in ("api_key_env", "api_key_keyring"):
        e.pop(k, None)
    mode = data.get("key_mode")
    if mode == "keyring":
        e["api_key_keyring"] = True
        if (existing or {}).get("api_key_env"):  # an environment variable, when set, still wins
            e["api_key_env"] = existing["api_key_env"]
    elif mode == "env":
        e["api_key_env"] = str(data.get("key_env", "")).strip()
    if e["kind"] == "openai_compatible" and data.get("text_calls") is False:
        e["text_tool_calls"] = False
    else:
        e.pop("text_tool_calls", None)
    models = list(dict.fromkeys(m.strip() for m in str(data.get("models", "")).splitlines() if m.strip()))
    if models:
        e["models"] = models
    else:
        e.pop("models", None)
    problems = []
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", e["id"]):
        problems.append(t("服务 ID 只能用小写字母、数字、- 和 _，并以字母或数字开头。"))
    elif e["id"] in taken:
        problems.append(t("已经有这个 ID 的服务：") + e["id"])
    if not re.match(r"https?://", e["base_url"]):
        problems.append(t("地址要以 http:// 或 https:// 开头。"))
    if e.get("api_key_env") is not None and not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", e["api_key_env"]):
        problems.append(t("环境变量名只能用大写字母、数字和下划线。"))
    if not e["local"] and e["max_data_class"] == "local_only":
        problems.append(t("远程服务不能接收“仅本机”的数据。"))
    if problems:
        raise Refused("\n".join(problems))
    return e


def _agent_of(page, aid: str) -> dict:
    a = next((x for x in page.raw["agents"] if x["id"] == aid), None)
    if a is None:
        raise Refused(t("没有这个 Agent：") + aid)
    return a


def _known(win) -> dict:
    """What the AI remembers of the user, for 设置 → 长期记忆: about them (every project) and this project."""
    from codedoctor.memory import digest

    def read(path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    try:
        project = read(digest.project_file(win.d.s))
    except Exception:  # no project open
        project = ""
    return {"about": read(digest.user_file()), "project": project, "about_max": digest.USER_MAX, "project_max": digest.PROJECT_MAX}


def act(win, action: str, data: dict) -> dict:
    """One change from the page. Returns the new state, or {"error": why} with nothing changed."""
    from codedoctor.desktop import prefs as ui_prefs

    page = win.models_page
    try:
        if action == "appearance":  # the user's own preferences: applied at once, nothing to save
            key, value = data["key"], data["value"]
            if key not in ui_prefs.DEFAULTS or type(value) is not type(ui_prefs.DEFAULTS[key]):
                raise Refused(t("没有这个设置：") + str(key))
            if key in APPEARANCE and value not in dict(APPEARANCE[key]):
                raise Refused(t("没有这个选项：") + str(value))
            win.apply_appearance({key: value})
            if key == "language":
                from PySide6.QtCore import QTimer

                from codedoctor.desktop import i18n

                i18n.set_language(value)
                if getattr(win, "web", None) is not None:  # the page takes the new language at once: loaded again, same page
                    QTimer.singleShot(150, win.web.view.reload)
            return state(win)
        if action in ("known_text", "known_clear"):  # the AI's memory of the user (memory/digest.py): theirs to read, change and clear
            from codedoctor.memory import digest

            files = {"about": digest.user_file(), "project": digest.project_file(win.d.s)}
            if action == "known_clear":
                for f in files.values():
                    f.unlink(missing_ok=True)
                digest.forget_pending(win.d.s)
            else:
                part, text = data.get("part"), str(data.get("text", ""))
                if part not in files:
                    raise Refused(t("没有这个选项：") + str(part))
                limit = digest.USER_MAX if part == "about" else digest.PROJECT_MAX
                if len(text) > limit:
                    raise Refused(t("太长了：最多 {0} 个字。").replace("{0}", str(limit)))
                if text.strip():
                    digest.write_text(files[part], text)
                else:
                    files[part].unlink(missing_ok=True)
            return state(win)
        if page.raw is None:
            raise Refused(t("这个窗口没有从配置文件启动，不能在这里修改。"))
        raw = page.raw
        if action == "endpoint":  # add (no "existing") or edit a service; a typed key waits for 保存
            existing = next((e for e in raw["endpoints"] if e["id"] == data.get("existing")), None)
            if data.get("existing") and existing is None:
                raise Refused(t("这个服务已经不在了。"))
            value = _endpoint_value(page, data, existing)
            if existing:
                raw["endpoints"][raw["endpoints"].index(existing)] = value
            else:
                raw["endpoints"].append(value)
            typed = str(data.get("key") or "").strip()
            if value.get("api_key_keyring") and typed:
                page.pending_keys[value["id"]] = typed
            elif (existing or {}).get("api_key_keyring") and not value.get("api_key_keyring"):
                page.pending_keys[value["id"]] = None  # it stopped using the credential store
        elif action == "drop_key":
            page.pending_keys[data["id"]] = None
        elif action == "remove_endpoint":
            users = _used_by(raw, data["id"])
            if users:
                raise Refused(t("还有 {0} 在用它。先在“AI 模型”里把它们改到别的服务，再删除。").replace("{0}", agents_summary(users)))
            raw["endpoints"] = [e for e in raw["endpoints"] if e["id"] != data["id"]]
            page.pending_keys[data["id"]] = None
        elif action == "agent":  # one field of one agent: endpoint, model, think, fallbacks
            a = _agent_of(page, data["id"])
            field, value = data["field"], data["value"]
            if field == "endpoint":
                ep = next((e for e in raw["endpoints"] if e["id"] == value), None)
                if ep is None:
                    raise Refused(t("没有这个服务：") + str(value))
                a["endpoint"] = value
                if ep.get("models") and a.get("model") not in ep["models"]:
                    a["model"] = ""  # the old model name belongs to another service: the user chooses
            elif field == "model":
                a["model"] = str(value).strip()
            elif field == "think":
                from codedoctor.models.reasoning import LEVELS

                if value not in LEVELS:
                    raise Refused(t("没有这个选项：") + str(value))
                a.setdefault("params", {})["reasoning"] = value
            elif field == "fallbacks":
                fbs = parse_fallbacks(str(value), {e["id"] for e in raw["endpoints"]})
                if fbs:
                    a["fallbacks"] = fbs
                else:
                    a.pop("fallbacks", None)
            else:
                raise Refused(t("没有这个设置：") + str(field))
        elif action == "add_pair":
            agents = raw["agents"]
            ids = {a["id"] for a in agents}
            n = 1
            while f"worker-{n}" in ids or f"guardian-{n}" in ids:
                n += 1
            tmpl_w = next((a for a in reversed(agents) if a["role"] == "worker"), agents[0])
            tmpl_g = next((a for a in reversed(agents) if a["role"] == "guardian"), tmpl_w)
            w = {"id": f"worker-{n}", "role": "worker", "endpoint": tmpl_w["endpoint"], "model": tmpl_w["model"]}
            g = {"id": f"guardian-{n}", "role": "guardian", "endpoint": tmpl_g["endpoint"], "model": tmpl_g["model"], "supervises": f"worker-{n}"}
            for src, dst in ((tmpl_w, w), (tmpl_g, g)):
                for k in ("params", "memory", "context_budget_tokens", "fallbacks"):
                    if k in src:
                        dst[k] = copy.deepcopy(src[k])
            agents += [w, g]
        elif action == "remove_agent":
            guards = [a["id"] for a in raw["agents"] if data["id"] in watched_ids(a)]
            drop = {data["id"], *guards}
            raw["agents"] = [a for a in raw["agents"] if a["id"] not in drop]
        elif action == "memory":
            if "recall" in data:  # one switch: 回忆以前的记忆 (how many it recalls is the system's own choice)
                for a in raw["agents"]:
                    mem = a.setdefault("memory", {})
                    cur = int(mem.get("recall_k", 8))
                    mem["recall_k"] = (cur if cur > 0 else 8) if data["recall"] else 0
        elif action in ("code", "code_detect"):
            web_cfgpages.act_code(raw, action, data)
        elif action == "computer":
            web_cfgpages.act_computer(raw, data, DATA_CLASS_CN)
        elif action == "embedding":
            eid, model = data.get("endpoint") or "", str(data.get("model", "")).strip()
            mem = raw.get("memory", {})
            if eid:
                old = mem.get("embedding", {})
                emb = {"endpoint": eid, "model": model}
                if "min_similarity" in old and old.get("endpoint") == eid and old.get("model") == model:
                    emb["min_similarity"] = old["min_similarity"]  # tuned for that model only
                raw["memory"] = {**mem, "embedding": emb}
            elif "embedding" in mem:
                rest = {k: v for k, v in mem.items() if k != "embedding"}
                if rest:
                    raw["memory"] = rest
                else:
                    raw.pop("memory")
        else:
            raise Refused(t("没有这个设置：") + action)
    except Refused as e:
        return {"error": str(e)}
    except ValueError as e:  # a fallback written wrong (parse_fallbacks)
        return {"error": str(e)}
    _changed(page)
    if action in AT_ONCE:
        note = at_once(win)
        out = state(win)
        if note:
            out["note"] = note
        return out
    return state(win)


def revert(win) -> dict:
    page = win.models_page
    page.pending_keys.clear()  # typed keys are dropped with everything else
    if page.path:
        page.raw = config_mod.load_raw(page.path)
    page.dirty = False
    page._web_stale = True
    return state(win)


def save(win) -> dict:
    """保存, as the Qt page saved: every agent has a model, the configuration written (the old one kept as .bak), then the
    keys written to or removed from Windows Credential Manager. {"ok", "warnings", "problems"} or {"ok": false, "error"}."""
    page = win.models_page
    if page.raw is None:
        return {"ok": False, "error": t("这个窗口没有从配置文件启动，不能在这里修改。")}
    empty = [a["id"] for a in page.raw["agents"] if not a.get("model")]
    if empty:
        return {"ok": False, "error": t("有 {0} 个 Agent 还没有选模型，所以没有保存。在“AI 模型”里给它们选好，再点保存。").replace("{0}", str(len(empty))),
                "agents": empty}
    if page.computer is not None:  # the Qt 电脑操作 page, if it was opened: what it holds goes in too
        try:
            page.computer._launch_list()
        except ValueError as e:
            return {"ok": False, "error": t("允许启动的程序写法有误：") + str(e)}
        page.computer._apply()
    emb = page.raw.get("memory", {}).get("embedding")
    if emb and not emb.get("model"):
        return {"ok": False, "error": t("已选择用于“按意思回忆”的服务，但还没有填写嵌入模型名。不想用可以选“不使用”。")}
    try:
        saved = config_mod.save_raw(page.raw, page.path)
    except Exception:
        return {"ok": False, "error": t(SAVE_FAILED)}
    apply_now(win, saved)
    problems = []
    for eid, key in page.pending_keys.items():  # keys follow the configuration: written only now
        try:
            if key:
                secrets.set_key(eid, key)
            else:
                secrets.delete_key(eid)
        except Exception as e:
            problems.append(f"{eid}: {e}")
    page.pending_keys.clear()
    page.dirty = False
    page.saved_agents = len(saved.agents)
    page._web_stale = True
    page.keys_changed.emit()
    warnings = config_mod.independence_warnings(saved)
    page.last_warnings = warnings
    return {"ok": True, "warnings": [t(w) for w in warnings], "problems": problems}


# --- tests that take a while (answered later through Bridge.probed) ----------------------------------------------------

def probe(win, what: str, data: dict, done) -> None:
    """A service answers or not (what="endpoint": a saved service by id, or the form's values), or an embedding model
    works (what="embedding"). Nothing of the project is sent. done(result dict) runs on the window's thread."""
    from codedoctor.desktop.settings_view import run_async

    page = win.models_page
    raw = page.raw or {"endpoints": []}
    began = time.perf_counter()
    if what == "engine":
        from codedoctor import engines

        name = data["name"]

        async def ask():
            import asyncio

            return await asyncio.to_thread(engines.status, name)

        def answered(res):
            if isinstance(res, Exception):
                done({"ok": False, "text": f"{type(res).__name__}: {res}"})
                return
            words = {"ready": t("已登录，{0} 个模型").replace("{0}", str(len(engines.models(name)))), "login": t("还没有登录"), "missing": t("没有安装")}
            done({"ok": res == "ready", "text": f"{engines.TITLES[name]}: {words.get(res, res)}"})
        run_async(ask(), answered)
        return
    if what == "embedding":
        e = next((x for x in raw["endpoints"] if x["id"] == data.get("endpoint")), None)
        model = str(data.get("model", "")).strip()
        if e is None or not model:
            done({"ok": False, "text": t("请先选择或填写嵌入模型名。")})
            return
        key = secrets.get_key(endpoint_of(e)) if e.get("api_key_env") or e.get("api_key_keyring") else None

        def emb_done(res):
            if isinstance(res, Exception):
                done({"ok": False, "text": t("测试出错：") + f"{type(res).__name__}: {res}"})
            elif res.error:
                done({"ok": False, "text": t("不能用：") + str(res.error)})
            else:
                done({"ok": True, "text": t("可用：向量维度 {0}，用时 {1} ms。").replace("{0}", str(res.dimensions)).replace("{1}", str(res.latency_ms))})
        run_async(providers.probe_embedding(e["kind"], e["base_url"], key, model, timeout_s=90.0), emb_done)
        return
    # a service: the saved one ("id"), or what the form says now ("form")
    if data.get("id"):
        e = next((x for x in raw["endpoints"] if x["id"] == data["id"]), None)
        if e is None:
            done({"ok": False, "text": t("这个服务已经不在了。")})
            return
        if e["kind"] == "engine":
            probe(win, "engine", {"name": e["base_url"].split(":", 1)[1]}, done)
            return
        if e["kind"] == "scripted":
            done({"ok": True, "text": t("这是测试脚本，没有可连接的服务")})
            return
        pending = page.pending_keys.get(e["id"], _NOTHING)
        key = pending if isinstance(pending, str) else secrets.get_key(endpoint_of(e))
        kind, url, model = e["kind"], e.get("base_url", ""), None
    else:
        f = data.get("form") or {}
        kind, url = f.get("kind") or "openai_compatible", str(f.get("base_url", "")).strip()
        model = str(f.get("test_model", "")).strip() or None if data.get("with_model") else None
        if not url:
            done({"ok": False, "text": t("请先填写地址。")})
            return
        if data.get("with_model") and not model:
            done({"ok": False, "text": t("请先选择或填写一个模型名。")})
            return
        typed = str(f.get("key") or "").strip()
        mode = f.get("key_mode")
        if mode == "keyring":
            staged = page.pending_keys.get(f.get("existing") or f.get("id"), _NOTHING)
            key = typed or (staged if staged is not _NOTHING else secrets.get_key(
                endpoint_of({"id": f.get("existing") or str(f.get("id", "")).strip(), "kind": "openai_compatible", "api_key_keyring": True})))
        elif mode == "env":
            key = os.environ.get(str(f.get("key_env", "")).strip()) or None
        else:
            key = None

    def probed(res):
        ms = int((time.perf_counter() - began) * 1000)
        if isinstance(res, Exception):
            done({"ok": False, "text": t("没有连上：") + f"{type(res).__name__}: {str(res)[:160]}"})
            return
        lines, ok = [], bool(res.models) or res.reachable
        if res.models:
            lines.append(t("连上了，{0} 毫秒，这个服务有 {1} 个模型").replace("{0}", str(ms)).replace("{1}", str(len(res.models))))
        elif res.models_error:
            lines.append((t("服务有响应，但没有提供模型列表：") if res.reachable else t("连不上服务：")) + res.models_error[:300])
        if res.chat_error:
            lines.append(t("调用模型失败：") + res.chat_error[:400])
            ok = False
        elif res.tool_calls:
            lines.append(t("模型回复用时 {0} 秒；").replace("{0}", f"{res.latency_ms / 1000:.1f}") + t(TOOL_CN[res.tool_calls]))
            ok = ok and res.tool_calls != "none"
        done({"ok": ok, "text": "\n".join(lines) or t("没有结果。"), "models": list(res.models or [])})
    run_async(providers.probe(kind, url, key, model, timeout_s=90.0 if model else 30.0), probed)


# --- 结论与记忆, and the feature book (read only) ----------------------------------------------------------------------------

def knowledge(win, tab: str, needle: str) -> dict:
    """The claims the agents made (成立 only once independently re-checked) and the notes they keep, newest first."""
    import json as _json

    from codedoctor.ui_text import CLAIM_CN, LEVEL_CN

    db = win.d.s.db
    claims = [_json.loads(r["doc"]) for r in db.query("SELECT doc FROM claims ORDER BY created_at DESC LIMIT 2000")]
    by: dict[str, int] = {}
    for c in claims:
        by[c["status"]] = by.get(c["status"], 0) + 1
    notes_n = db.one("SELECT COUNT(*) AS n FROM notes")["n"]
    q = (needle or "").strip().lower()
    rows = []
    if tab == "notes":
        notes = [_json.loads(r["doc"]) for r in db.query("SELECT doc FROM notes WHERE superseded_by IS NULL ORDER BY rowid DESC LIMIT 2000")]
        for m in (m for m in notes if not q or q in _json.dumps(m, ensure_ascii=False).lower()):
            rows.append({"kind": t(NOTE_KIND_CN.get(m["kind"], m["kind"])), "text": m["text"][:1200], "id": m["id"],
                         "meta": [m["owner"], t("项目共享") if m.get("scope") == "project" else t("私有"), m["created_at"][:16].replace("T", " ")]
                         + ([t("证据 {0} 条").replace("{0}", str(len(m["evidence"])))] if m.get("evidence") else [])})
    else:
        for c in (c for c in claims if not q or q in _json.dumps(c, ensure_ascii=False).lower()):
            rows.append({"status": c["status"], "kind": t(CLAIM_CN.get(c["status"], c["status"])), "level": t(LEVEL_CN.get(c.get("evidence_level"), c.get("evidence_level", ""))),
                         "text": c["statement"]["text"], "id": c["id"],
                         "meta": [c["author"]["id"], t("证据 {0} 条").replace("{0}", str(len(c.get("evidence", []))))] + ([c["task_id"]] if c.get("task_id") else [])})
    return {"stats": {"supported": by.get("supported", 0), "proposed": by.get("proposed", 0) + by.get("needs_revalidation", 0),
                      "refuted": by.get("refuted", 0), "notes": notes_n},
            "rows": rows[:SHOWN], "total": len(rows), "shown": SHOWN}


def book(lang: str) -> dict:
    from codedoctor.desktop import i18n
    from codedoctor.desktop.manual import text_of

    lang = lang or i18n.language()
    return {"lang": lang, "langs": [{"value": v, "label": name} for v, name in i18n.LANGS], "text": text_of(lang)}
