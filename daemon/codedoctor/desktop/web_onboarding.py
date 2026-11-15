"""The greeting and the first-run setup in React (web/src/Onboarding.jsx), shown by the launcher before any window.

The page is the window's own page, opened as index.html?boot=onboarding, with a bridge of its own: the texts are the
ones the Qt cards used (i18n.tr, in the ten interface languages), the setup is built and saved by the same functions
(first_run.build_setup, first_run.problem), and a typed key goes to the credential store only on 开始使用.
"""

from __future__ import annotations

import json
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtWidgets import QWidget

from codedoctor.desktop.i18n import tr

KEYS = ("tagline", "skip", "enter", "lang_title", "language", "pick_ai_title",
        "pick_ai_sub", "engine_checking", "engine_ready", "engine_missing", "use_api", "use_api_sub", "service", "address", "api_key",
        "key_hint", "no_key_needed", "model", "model_hint", "test", "testing", "let_fix", "let_fix_sub", "back", "next", "start_using",
        "open_folder", "open_failed_any")


def texts() -> dict:
    from codedoctor import engines

    out = {k: tr(k) for k in KEYS}
    for name in engines.NAMES:
        out[f"use_{name}_sub"] = tr(f"use_{name}_sub")
    out["default_ai"] = tr("default_ai", name="{0}")
    return out


def presets_json() -> list[dict]:
    from codedoctor.desktop.first_run import presets

    return [{"id": p.id, "name": p.name, "kind": p.kind, "base_url": p.base_url, "local": p.local, "key_env": p.key_env or ""} for p in presets()]


class OnboardingBridge(QObject):
    show = Signal(str)     # {"page": "welcome" | "setup" | "failed", ...}
    status = Signal(str)   # {"name", "status", "text"}: Claude Code or Codex answered whether it is installed and signed in
    tested = Signal(str)   # {"ok", "text", "models"}: the API test

    def __init__(self, launcher):
        super().__init__()
        self.launcher = launcher
        self.last: dict = {"page": "welcome"}

    @Slot(result=str)
    def boot(self) -> str:
        from codedoctor.desktop import i18n
        from codedoctor.desktop import prefs as ui_prefs
        from codedoctor.desktop.web_chat import prefs_json

        catalog = __import__("codedoctor.desktop.zh_hant", fromlist=["catalog"]).catalog() if i18n.language() == "zh-TW" else {}
        return json.dumps({"lang": i18n.language(), "catalog": catalog, "prefs": prefs_json(ui_prefs.load()), "texts": texts()}, ensure_ascii=False)

    @Slot(result=str)
    def current(self) -> str:
        return json.dumps(self.last, ensure_ascii=False)

    @Slot(result=str)
    def setup(self) -> str:
        """Step 1's choices and step 2's AIs, in the interface language."""
        from codedoctor import engines
        from codedoctor.desktop import i18n
        from codedoctor.desktop.first_run import _KNOWN

        return json.dumps({"lang": i18n.language(), "langs": [{"value": c, "label": n} for c, n in i18n.LANGS],
                           "texts": texts(), "presets": presets_json(),
                           "engines": [{"name": n, "title": engines.TITLES[n], "status": _KNOWN.get(n, ""), "text": _status_text(n, _KNOWN.get(n, ""))}
                                       for n in engines.NAMES]}, ensure_ascii=False)

    @Slot(str)
    def language(self, code: str) -> None:
        """Another interface language: saved, and the page asks for everything again in it."""
        from codedoctor.desktop import i18n
        from codedoctor.desktop import prefs as ui_prefs

        ui = ui_prefs.load()
        ui["language"] = code
        ui_prefs.save(ui)
        i18n.set_language(code)
        self.show.emit(json.dumps({"page": "setup", "relanguage": True}))

    @Slot()
    def check_engines(self) -> None:
        """Installed? Signed in? Each program asked on a worker thread (Codex takes seconds), once per run of Lumen."""
        from codedoctor import engines
        from codedoctor.desktop.first_run import _KNOWN

        def ask(name: str) -> None:
            status = _KNOWN[name] = engines.status(name)
            try:
                self.status.emit(json.dumps({"name": name, "status": status, "text": _status_text(name, status)}, ensure_ascii=False))
            except RuntimeError:  # the window went meanwhile
                pass
        for name in engines.NAMES:
            if name in _KNOWN:
                self.status.emit(json.dumps({"name": name, "status": _KNOWN[name], "text": _status_text(name, _KNOWN[name])}, ensure_ascii=False))
            else:
                threading.Thread(target=ask, args=(name,), daemon=True).start()

    @Slot(str)
    def test(self, data: str) -> None:
        """With a model: one fixed test prompt; without one: the service's own list of models."""
        from codedoctor import providers
        from codedoctor.desktop.settings_view import run_async

        d = json.loads(data)
        p = next(x for x in providers.PRESETS if x.id == d["preset"])
        model = (d.get("model") or "").strip() or None

        def done(res):
            if isinstance(res, Exception):
                out = {"ok": False, "text": tr("test_bad", why=f"{type(res).__name__}: {res}")}
            elif not model:
                out = {"ok": bool(res.models), "text": tr("models_found", n=len(res.models)) if res.models
                       else tr("test_bad", why=(res.models_error or "?")[:300]) + " " + tr("err_model")}
            elif res.chat_error or (not res.ok and not res.models):
                out = {"ok": False, "text": tr("test_bad", why=(res.chat_error or res.models_error or "?")[:300])}
            else:
                out = {"ok": True, "text": tr("test_ok", s=f"{(res.latency_ms or 0) / 1000:.1f}")}
            out["models"] = list(getattr(res, "models", None) or [])
            try:
                self.tested.emit(json.dumps(out, ensure_ascii=False))
            except RuntimeError:
                pass
        run_async(providers.probe(p.kind, (d.get("url") or "").strip(), (d.get("key") or "").strip() or None, model, timeout_s=90.0), done)

    @Slot(str, result=str)
    def finish(self, data: str) -> str:
        """开始使用: checked, the key (if any) written to the credential store, the setup saved; then the folder opens."""
        from codedoctor import secrets
        from codedoctor.desktop import projects
        from codedoctor.desktop.first_run import _KNOWN, build_setup, problem

        d = json.loads(data)
        choice = {"chosen": d.get("chosen") or [], "preset": d.get("preset") or "",
                  "url": d.get("url") or "", "key": d.get("key") or "", "model": d.get("model") or "", "fix": bool(d.get("fix", True))}
        why = problem(choice, _KNOWN)
        if why:
            return json.dumps({"ok": False, "error": why}, ensure_ascii=False)
        try:
            setup, key_for, key = build_setup(choice)
            if key_for and key:
                secrets.set_key(key_for, key)  # written now - not while typing
            projects.save_setup(setup)
        except Exception as e:
            return json.dumps({"ok": False, "error": tr("err_create", why=f"{type(e).__name__}: {e}")}, ensure_ascii=False)
        self.launcher.open_default()
        return json.dumps({"ok": True})

    @Slot()
    def proceed(self) -> None:
        """进入, 跳过动画, or the greeting written to its end."""
        self.launcher._after_welcome()

    @Slot()
    def choose_folder(self) -> None:
        self.launcher.choose_folder()


def _status_text(name: str, status: str) -> str:
    from codedoctor import engines

    if not status:
        return tr("engine_checking")
    return {"ready": tr("engine_ready"), "missing": tr("engine_missing"), "login": tr("engine_login", cmd=engines.LOGIN_COMMAND[name])}[status]


class OnboardingView(QWidget):
    """The page in the launcher's window."""

    def __init__(self, launcher):
        super().__init__()
        from PySide6.QtWebChannel import QWebChannel
        from PySide6.QtWebEngineCore import QWebEngineSettings
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWidgets import QVBoxLayout

        from codedoctor.desktop import prefs as ui_prefs
        from codedoctor.desktop.web_chat import DIST, paper

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        self.bridge = OnboardingBridge(launcher)
        self.channel = QWebChannel(self)
        self.channel.registerObject("lumen", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.page().setBackgroundColor(paper(ui_prefs.load()))
        lay.addWidget(self.view)
        url = QUrl.fromLocalFile(str(DIST / "index.html"))
        url.setQuery("boot=onboarding")
        self.view.load(url)

    def show_page(self, view: dict) -> None:
        self.bridge.last = view
        self.bridge.show.emit(json.dumps(view, ensure_ascii=False))
