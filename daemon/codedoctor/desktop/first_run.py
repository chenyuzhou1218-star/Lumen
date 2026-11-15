"""The first time Lumen opens (2026-11-03): after the greeting, the language, then the AIs - the user's
own Claude Code and Codex, and/or an API key. Asked once; from then on Lumen opens straight into the window,
and any folder opens with these choices (projects.for_folder) - no project to create.

Models stay the user's choice: what is picked here is what Lumen starts with, switchable for any question and
changeable in Settings. A typed key is written to the credential store only on 开始使用.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QStackedWidget, QWidget)

from codedoctor import engines, providers, secrets
from codedoctor.desktop import i18n, projects
from codedoctor.desktop import prefs as ui_prefs
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.liquid import Glass, MedicalMark
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import hbox, label, vbox

# Which API services come first: one fixed order for everyone, no country or region is asked (Lumen is open source);
# all the others follow in the order of providers.PRESETS.
FIRST = ("openai", "anthropic", "gemini", "openrouter", "deepseek", "xai", "mistral", "groq", "together",
                "fireworks", "nvidia", "cerebras", "perplexity")
STEPS = 2
_KNOWN: dict[str, str] = {}  # each engine's status, asked once per run of Lumen


def presets() -> list:
    first = FIRST
    listed = [p for p in providers.PRESETS if p.id != "custom-anthropic"]
    return sorted(listed, key=lambda p: first.index(p.id) if p.id in first else len(first) + listed.index(p))


def problem(choice: dict, status: dict) -> str | None:
    """Why the choices cannot be saved yet, or None. choice: chosen (engine names and/or "api"), preset, url, key,
    model, fix. status: each engine's status as asked (engines.status)."""
    chosen = choice["chosen"]
    if not chosen:
        return tr("err_pick_ai")
    for name in chosen:
        if name in engines.TITLES and status.get(name) != "ready":
            why = (tr("engine_checking") if name not in status else tr("engine_missing")
                   if status[name] == "missing" else tr("engine_login", cmd=engines.LOGIN_COMMAND[name]))
            return tr("err_engine_not_ready", name=engines.TITLES[name], why=why)
    if "api" in chosen:
        p = next((x for x in providers.PRESETS if x.id == choice["preset"]), None)
        if p is None:
            return tr("err_model")
        if not choice["model"].strip():
            return tr("err_model")
        if not p.local and not choice["key"].strip() and p.key_env:
            return tr("err_key")
    return None


def build_setup(choice: dict) -> tuple[dict, str | None, str | None]:
    """(the setup, the endpoint whose key to store, the key) from the choices (see problem)."""
    endpoints, agents_on = [], []
    key_for = key = None
    for name in choice["chosen"]:
        if name in engines.TITLES:
            ep = engines.endpoint(name)
            listed = engines.models(name)
            model = next((m["id"] for m in listed if m["yours"]), listed[0]["id"] if listed else name)
            endpoints.append(ep)
            agents_on.append((ep["id"], model))
        else:
            p = next(x for x in providers.PRESETS if x.id == choice["preset"])
            model = choice["model"].strip()
            ep = {"id": p.id, "name": p.name, "provider": p.id, "kind": p.kind,
                  "base_url": choice["url"].strip().rstrip("/"), "local": p.local,
                  "max_data_class": "local_only" if p.local else "internal",
                  "models": [model]}  # 更多模型 asks the service for the rest, live
            key = choice["key"].strip() or None
            if key:
                ep["api_key_keyring"] = True
                key_for = p.id
            endpoints.append(ep)
            agents_on.append((p.id, model))
    endpoint, model = agents_on[0]  # the first one chosen answers first; any question can switch
    agent = {"id": "doctor", "role": "general", "endpoint": endpoint, "model": model}
    if choice["chosen"][0] in engines.TITLES:  # Claude Code and Codex manage their own context: all of it is used (the user's rule)
        agent["context_budget_tokens"] = 1_000_000
    setup = {"language": i18n.language(), "endpoints": endpoints,
             "agents": [agent],
             "permissions": {"write_files": bool(choice["fix"])}}  # a project starts with everything on (projects.start_permissions)
    return setup, key_for, key


class _Status(QObject):
    found = Signal(str, str)  # (engine, status) from a worker thread


class FirstRun(Glass):
    finished = Signal()      # the setup is saved: open the window
    relanguage = Signal()  # the user picked another language: rebuild in it

    def __init__(self, parent=None):
        super().__init__(parent, radius=32, padding=26)
        self.setMinimumWidth(680)
        self.setMaximumWidth(900)
        self.status: dict[str, str] = {}
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(MedicalMark(40))
        top.addWidget(label("Lumen", size=16, bold=True, color=C["ink"]))
        top.addStretch(1)
        self.step_label = label("", size=12, bold=True, color=C["text3"])
        top.addWidget(self.step_label)
        self.body.addLayout(top)
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack, 1)
        self.stack.addWidget(self._place())
        self.stack.addWidget(self._ai())
        self.error = label("", size=13, color=C["red"], wrap=True)
        self.body.addWidget(self.error)
        nav = QHBoxLayout()
        self.back_btn = QPushButton(tr("back"))
        self.back_btn.setObjectName("Ghost")
        self.next_btn = QPushButton(tr("next"))
        self.next_btn.setObjectName("Primary")
        for b in (self.back_btn, self.next_btn):
            b.setMinimumHeight(38)
            b.setMinimumWidth(110)
            b.setCursor(Qt.PointingHandCursor)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        nav.addWidget(self.next_btn)
        self.body.addLayout(nav)
        self.back_btn.clicked.connect(lambda: self._go(0))
        self.next_btn.clicked.connect(self._next)
        self._go(0)
        self._check_engines()

    # --- step 1: the language ------------------------------------------------------------

    def _choice(self, text: str, checked: bool) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("Ghost")
        b.setCheckable(True)
        b.setChecked(checked)
        b.setMinimumHeight(46)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet("QPushButton:checked { background: rgba(255,255,255,235); border: 1.5px solid rgba(58,107,168,170);"
                        f" color: {C['ink']}; font-weight: 700; }}")
        return b

    def _place(self) -> QWidget:
        page = vbox(label(tr("lang_title"), size=28, bold=True, color=C["ink"]), spacing=10)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.lang_group = QButtonGroup(self)
        for i, (code, name) in enumerate(i18n.LANGS):
            b = self._choice(name, code == i18n.language())
            b.clicked.connect(lambda _=False, c=code: self._pick_language(c))
            self.lang_group.addButton(b)
            grid.addWidget(b, i // 2, i % 2)
        page.layout().addLayout(grid)
        page.layout().addStretch(1)
        return page

    def _pick_language(self, code: str) -> None:
        if code == i18n.language():
            return
        ui = ui_prefs.load()
        ui["language"] = code
        ui_prefs.save(ui)
        i18n.set_language(code)
        self.relanguage.emit()

    # --- step 2: the AIs ------------------------------------------------------------------------

    def _ai(self) -> QWidget:
        page = vbox(label(tr("pick_ai_title"), size=28, bold=True, color=C["ink"]),
                    label(tr("pick_ai_sub"), size=13, color=C["text2"], wrap=True), spacing=8)
        self.use: dict[str, QCheckBox] = {}
        self.state: dict[str, QWidget] = {}
        for name in engines.NAMES:
            box = QCheckBox(engines.TITLES[name])
            box.setStyleSheet("QCheckBox { font-size: 15px; font-weight: 700; }")
            self.use[name] = box
            self.state[name] = label(tr("engine_checking"), size=12, color=C["text3"])
            page.layout().addWidget(vbox(box, label(tr(f"use_{name}_sub"), size=12, color=C["text2"]), self.state[name],
                                         spacing=2))
        self.use["api"] = QCheckBox(tr("use_api"))
        self.use["api"].setStyleSheet("QCheckBox { font-size: 15px; font-weight: 700; }")
        page.layout().addWidget(vbox(self.use["api"], label(tr("use_api_sub"), size=12, color=C["text2"]), spacing=2))
        self.api_box = QWidget()
        form = QFormLayout(self.api_box)
        form.setSpacing(10)
        form.setContentsMargins(24, 2, 0, 0)
        self.preset = QComboBox()
        for p in presets():
            self.preset.addItem(p.name, p.id)
        self.url = QLineEdit()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key_note = label("", "Faint", wrap=True)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.test_btn = QPushButton(tr("test"))
        self.test_btn.setObjectName("Ghost")
        self.test_result = label("", size=13, wrap=True)
        form.addRow(tr("service"), self.preset)
        form.addRow(tr("address"), self.url)
        form.addRow(tr("api_key"), vbox(self.key, self.key_note, spacing=4))
        form.addRow(tr("model"), self.model)
        form.addRow("", vbox(hbox(self.test_btn, None), self.test_result, spacing=4))
        page.layout().addWidget(self.api_box)
        self.fix = QCheckBox(tr("let_fix"))  # changes are snapshotted and can be undone in one click
        self.fix.setChecked(True)
        page.layout().addWidget(self.fix)
        page.layout().addWidget(label(tr("let_fix_sub"), size=12, color=C["text2"], wrap=True))
        self.default_note = label("", size=13, bold=True, color=C["ink"])
        page.layout().addWidget(self.default_note)
        page.layout().addStretch(1)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.test_btn.clicked.connect(self._test)
        for box in self.use.values():
            box.toggled.connect(lambda _: self._show_choice())
        self._preset_changed()
        self._show_choice()
        return page

    def _check_engines(self) -> None:
        """Installed? Signed in? Each program is asked on a worker thread (Codex takes several seconds to answer)."""
        bridge = self._bridge = _Status()
        bridge.found.connect(self._got_status)

        def ask(name: str) -> None:
            status = _KNOWN[name] = engines.status(name)
            try:
                bridge.found.emit(name, status)
            except RuntimeError:  # the card was rebuilt (another language) meanwhile
                pass
        for name in engines.NAMES:
            if name in _KNOWN:  # asked already (the card is rebuilt when the language changes)
                self._got_status(name, _KNOWN[name])
            else:
                threading.Thread(target=ask, args=(name,), daemon=True).start()

    def _got_status(self, name: str, status: str) -> None:
        self.status[name] = status
        text = {"ready": tr("engine_ready"), "missing": tr("engine_missing"),
                "login": tr("engine_login", cmd=engines.LOGIN_COMMAND[name])}[status]
        try:
            self.state[name].setText(text)
            self.state[name].setStyleSheet(f"color: {C['green'] if status == 'ready' else C['text3']};")
            if status == "ready" and not any(b.isChecked() for b in self.use.values()):
                self.use[name].setChecked(True)  # a ready one is the natural default; the user can untick it
            self.use[name].setEnabled(status != "missing")
        except RuntimeError:  # the card was rebuilt (another language) while the program answered
            pass

    def _preset(self):
        return next(p for p in providers.PRESETS if p.id == self.preset.currentData())

    def _preset_changed(self, *_):
        p = self._preset()
        self.url.setText(p.base_url)
        needs_key = not p.local
        self.key.setVisible(needs_key)
        self.key_note.setText(tr("key_hint") if needs_key else tr("no_key_needed"))
        self.model.clear()  # no names written into Lumen: 测试连接 lists the service's own
        self.model.setCurrentText("")
        self.model.lineEdit().setPlaceholderText(tr("model_hint"))
        self.test_result.setText("")

    def _test(self) -> None:
        """With a model: one fixed test prompt. Without one: the service's own list of models, to pick from."""
        from codedoctor.desktop.settings_view import run_async

        model = self.model.currentText().strip() or None
        self.test_btn.setEnabled(False)
        self.test_result.setStyleSheet(f"color: {C['text2']};")
        self.test_result.setText(tr("testing"))
        p = self._preset()
        run_async(providers.probe(p.kind, self.url.text().strip(), self.key.text().strip() or None, model, timeout_s=90.0),
                  self._tested)

    def _tested(self, res) -> None:
        self.test_btn.setEnabled(True)
        if not isinstance(res, Exception) and res.models:  # what the service has now, in the list
            typed = self.model.currentText().strip()
            self.model.clear()
            self.model.addItems(res.models)
            self.model.setCurrentText(typed)
        if isinstance(res, Exception):
            text, color = tr("test_bad", why=f"{type(res).__name__}: {res}"), C["red"]
        elif not self.model.currentText().strip():
            text, color = ((tr("models_found", n=len(res.models)), C["green"]) if res.models else
                           (tr("test_bad", why=(res.models_error or "?")[:300]) + " " + tr("err_model"), C["red"]))
        elif res.chat_error or (not res.ok and not res.models):
            text, color = tr("test_bad", why=(res.chat_error or res.models_error or "?")[:300]), C["red"]
        else:
            text, color = tr("test_ok", s=f"{(res.latency_ms or 0) / 1000:.1f}"), C["green"]
        self.test_result.setStyleSheet(f"color: {color};")
        self.test_result.setText(text)

    def _chosen(self) -> list[str]:
        return [k for k in (*engines.NAMES, "api") if self.use[k].isChecked()]

    def _show_choice(self) -> None:
        self.api_box.setVisible(self.use["api"].isChecked())
        chosen = self._chosen()
        name = (engines.TITLES[chosen[0]] if chosen[0] in engines.TITLES else self._preset().name) if chosen else ""
        self.default_note.setText(tr("default_ai", name=name) if chosen else "")

    # --- navigation and saving --------------------------------------------------------------------

    def _go(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        self.step_label.setText(tr("step", n=i + 1, total=STEPS))
        self.back_btn.setVisible(i > 0)
        self.next_btn.setText(tr("start_using") if i == STEPS - 1 else tr("next"))
        self.error.setText("")

    def _next(self) -> None:
        if self.stack.currentIndex() < STEPS - 1:
            self._go(self.stack.currentIndex() + 1)
            return
        problem = self._problem()
        if problem:
            self.error.setText(problem)
            return
        try:
            setup, key_for, key = self.build()
            if key_for and key:
                secrets.set_key(key_for, key)  # written now - not while typing
            projects.save_setup(setup)
        except Exception as e:
            self.error.setText(tr("err_create", why=f"{type(e).__name__}: {e}"))
            return
        self.finished.emit()

    def _choice_now(self) -> dict:
        return {"chosen": self._chosen(), "preset": self.preset.currentData() or "", "url": self.url.text(),
                "key": self.key.text(), "model": self.model.currentText(), "fix": self.fix.isChecked()}

    def _problem(self) -> str | None:
        return problem(self._choice_now(), self.status)

    def build(self) -> tuple[dict, str | None, str | None]:
        """(the setup, the endpoint whose key to store, the key)."""
        return build_setup(self._choice_now())
