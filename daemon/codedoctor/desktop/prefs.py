"""Per-user appearance preferences (not part of any project): ~/.codedoctor/ui.json.

    welcome         play the written greeting when Lumen starts
    wallpaper       "plain" (纯白, the default since 2026-11-03), "silk" (流光丝绸) or "aurora" (极光)
    reduced_motion  no entrance animations, the greeting shows at once
    language        interface language (desktop/i18n.LANGS), chosen in the first-run wizard
    accent          the colour of links, focus and the send button (theme.ACCENTS)
    font_size       small / normal / large
    chat_width      narrow / normal / wide: the width of a conversation
    send_key        enter / ctrl_enter
    search_engine   google / bing: where the browser's search box goes
    show_times      the time under each of your messages
    expand_steps    a running answer shows its steps
    show_tokens     tokens in a chat's header
    figure_motion   the figures float
    notify_done     tell me when an answer is ready and the window is not in front
    mode            light / dark: every page, the terminal with them (light unless the user chooses dark: the user, 2026-11-11)
    term_font       the size of the terminal's text, in pixels (11-18)
    last_pick       the model the user chose last in a message box ({"engine", "id", "model"} or {"endpoint", "model"});
                    {} when none was chosen yet: then no model is filled in for them (the user's rule: never switch it)
    last_level      the thinking level chosen with it
    auto_fold       a long answer's process is folded away when it ends (省略); off: it stays open
    fold_turns      {turn id: true (folded) / false (open)}: what the user chose for a turn, kept for good
    spend_limit     new tokens one question may use (every AI working on it, cache re-reads not counted); reached, it
                    stops and the chat asks whether to go on (the user, 2026-11-12: money must never go wrong)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {"welcome": True, "wallpaper": "plain", "reduced_motion": False, "language": "", "theme": 2, "accent": "amber",
            "font_size": "normal", "chat_width": "normal", "send_key": "enter", "search_engine": "google",
            "show_times": True, "expand_steps": True, "show_tokens": True, "figure_motion": True, "notify_done": True,
            "mode": "light", "term_font": 13, "auto_fold": True, "fold_turns": {},
            "last_pick": {}, "last_level": "", "spend_limit": 0}
SPEND_LIMITS = [(0, "不限"), (50_000, "5 万"), (100_000, "10 万"), (300_000, "30 万"), (1_000_000, "100 万"), (3_000_000, "300 万")]
MODES = [("light", "浅色"), ("dark", "深色")]
TERM_FONTS = [(11, "11"), (12, "12"), (13, "13"), (14, "14"), (15, "15"), (16, "16"), (18, "18")]
WALLPAPERS = [("plain", "纯白"), ("silk", "流光丝绸"), ("aurora", "极光")]


def _path() -> Path:
    return Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor") / "ui.json"


def load() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in data.items() if k in DEFAULTS and type(v) is type(DEFAULTS[k])})
    from codedoctor.desktop import i18n

    if not out["language"]:  # never chosen: this computer's language (fr, zh), else English
        out["language"] = i18n.system_language()
    elif out["language"] not in dict(i18n.LANGS):  # one that is gone (ja, ko, zh-TW ...): English
        out["language"] = "en"
    if out["search_engine"] not in ("google", "bing"):  # only these two (the user, 2026-11-13)
        out["search_engine"] = "google"
    if out["wallpaper"] not in dict(WALLPAPERS):
        out["wallpaper"] = DEFAULTS["wallpaper"]
    if out["spend_limit"] not in dict(SPEND_LIMITS):
        out["spend_limit"] = DEFAULTS["spend_limit"]
    if out["mode"] not in dict(MODES):
        out["mode"] = DEFAULTS["mode"]
    if out["term_font"] not in dict(TERM_FONTS):
        out["term_font"] = DEFAULTS["term_font"]
    if data.get("theme", 1) < 2:  # saved before the white theme: the user asked for white everywhere (2026-11-03)
        out["wallpaper"] = "plain"
    return out


def save(prefs: dict) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: prefs[k] for k in DEFAULTS if k in prefs}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass  # a preference that cannot be saved is used for this session only
