"""模型与 API: the user's services (any OpenAI-compatible API, Anthropic, local servers) and
which model every agent uses. Nothing here chooses a model on the user's behalf.

Keys typed here go straight to Windows Credential Manager (codedoctor.secrets); the
configuration file only records where to find them.
"""

from __future__ import annotations

import asyncio
import copy
import os
import re
import threading
from pathlib import Path

from PySide6.QtCore import QSize, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QLayout, QSpinBox, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from codedoctor import config as config_mod
from codedoctor import providers, secrets
from codedoctor.config import Endpoint
from codedoctor.desktop.cluster_settings import ClusterSettings, ContextInfo
from codedoctor.desktop.dialogs import notice
from codedoctor.desktop.theme import C, ROLE_COLOR
from codedoctor.desktop.widgets import CardGrid, Avatar, Card, Chip, hbox, label, vbox
from codedoctor.ui_text import ROLE_CN

DATA_CLASS_CN = [("public", "公开代码"), ("internal", "内部代码"), ("confidential", "机密"), ("secret", "绝密"),
                 ("local_only", "仅本机（不得出本机）")]
KEY_CN = {"keyring": ("密钥已保存", C["green"], C["green_soft"]), "env": ("密钥来自环境变量", C["green"], C["green_soft"]),
          "missing": ("缺少密钥", C["red"], C["red_soft"]), "not_needed": ("无需密钥", C["text2"], C["gray_soft"])}
TOOL_CN = {"native": "支持标准工具调用", "text": "工具调用写在文字里（已自动兼容）", "none": "没有调用工具：这个模型可能不适合做 Agent"}


def endpoint_of(e: dict) -> Endpoint:
    return Endpoint(id=e["id"], kind=e["kind"], base_url=e.get("base_url", ""), local=e.get("local", False),
                    api_key_env=e.get("api_key_env"), api_key_keyring=e.get("api_key_keyring", False))


def key_status(e: dict) -> str:
    return secrets.key_status(endpoint_of(e))


class _Bridge(QObject):
    done = Signal(object)


def run_async(coro, callback) -> None:
    """Run a coroutine on a worker thread; deliver the result (or exception) to `callback` on the UI thread."""
    bridge = _Bridge()
    bridge.done.connect(callback)
    bridge._keep = bridge  # alive until delivered

    def work():
        try:
            out = asyncio.run(coro)
        except Exception as e:  # shown to the user, never raised into Qt
            out = e
        bridge.done.emit(out)

    threading.Thread(target=work, daemon=True).start()


def fallbacks_text(a: dict) -> str:
    return ", ".join(f"{f['endpoint']}/{f['model']}" for f in a.get("fallbacks", []))


def parse_fallbacks(text: str, endpoint_ids) -> list[dict]:
    out = []
    for part in filter(None, (p.strip() for p in re.split(r"[,，\n]", text))):
        ep, sep, model = part.partition("/")
        if not sep or not model.strip():
            raise ValueError(f"“{part}” 应写成 服务ID/模型名")
        if ep.strip() not in endpoint_ids:
            raise ValueError(f"没有 ID 为 “{ep.strip()}” 的服务")
        out.append({"endpoint": ep.strip(), "model": model.strip()})
    return out


_NOTHING = object()


class EndpointDialog(QDialog):
    """Add or edit one service. A typed key is NOT written here: the page keeps it and writes it to the credential
    store only when the user clicks 保存 (放弃修改 or closing without saving leaves nothing behind).
    staged: the key already typed for this service and not yet saved (None = deletion pending)."""

    def __init__(self, parent, existing: dict | None, taken_ids: set[str], staged=_NOTHING):
        super().__init__(parent)
        self.staged = staged
        self.typed_key: str | None = None   # set on accept: the key to save with the configuration
        self.drop_key = False               # set on accept: the service stopped using the credential store
        self.setWindowTitle("编辑服务" if existing else "添加服务")
        self.setMinimumWidth(460)
        self.existing = existing
        self.taken = taken_ids - ({existing["id"]} if existing else set())
        self.fetched: list[str] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(10)
        lay.addWidget(label("任何兼容 OpenAI 接口（/v1/chat/completions）的服务都能用，Claude 用 Anthropic 接口。"
                            "选一个预设会自动填好地址，也可以选“自定义”。", "Muted", wrap=True))
        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignRight)

        self.preset = QComboBox()
        for p in providers.PRESETS:
            self.preset.addItem(p.name, p.id)
        self.name = QLineEdit()
        self.id = QLineEdit()
        self.id.setPlaceholderText("小写字母、数字、- 或 _，Agent 配置里用它指向这个服务")
        self.kind = QComboBox()
        self.kind.addItem("OpenAI 兼容接口", "openai_compatible")
        self.kind.addItem("Anthropic 接口", "anthropic")
        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("https://…/v1")
        self.local = QCheckBox("这是本机/局域网里的服务（例如 Ollama、LM Studio）")
        self.note = label("", "Faint", wrap=True)

        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key_keyring = QRadioButton("保存到 Windows 凭据管理器（推荐）")
        self.key_env = QRadioButton("从环境变量读取：")
        self.env_name = QLineEdit()
        self.env_name.setPlaceholderText("例如 OPENAI_API_KEY")
        self.no_key = QRadioButton("不需要密钥")
        self.key_state = label("", "Faint")
        key_box = vbox(self.key, self.key_keyring, hbox(self.key_env, self.env_name, stretch_at=1), self.no_key,
                       self.key_state, spacing=5)

        self.data_class = QComboBox()
        for v, t in DATA_CLASS_CN:
            self.data_class.addItem(t, v)
        self.text_calls = QCheckBox("兼容把工具调用写成文字的模型（推荐保持打开）")
        self.models = QPlainTextEdit()
        self.models.setPlaceholderText("常用的模型名，一行一个。可以点“获取模型列表”从服务读取。")
        self.models.setFixedHeight(74)
        self.fetch_btn = QPushButton("获取模型列表")
        self.fetch_btn.setObjectName("Ghost")
        self.test_model = QComboBox()
        self.test_model.setEditable(True)
        self.test_model.setMinimumWidth(240)
        self.test_btn = QPushButton("测试连接与工具调用")
        self.test_btn.setObjectName("Primary")
        self.result = label("测试只发送一句固定的测试提示，不发送你的代码。", "Faint", wrap=True)
        self.result.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form.addRow("服务商", self.preset)
        form.addRow("", self.note)
        form.addRow("显示名称", self.name)
        form.addRow("服务 ID", self.id)
        form.addRow("接口类型", self.kind)
        form.addRow("地址", self.base_url)
        form.addRow("", self.local)
        form.addRow("API 密钥", key_box)
        form.addRow("可发送的代码级别", self.data_class)
        form.addRow("", self.text_calls)
        form.addRow("模型", vbox(self.models, hbox(self.fetch_btn, None), spacing=5))
        form.addRow("测试", vbox(hbox(self.test_model, self.test_btn, None), self.result, spacing=5))
        lay.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.local.toggled.connect(self._local_toggled)
        for r in (self.key_keyring, self.key_env, self.no_key):
            r.toggled.connect(self._key_mode_changed)
        self.fetch_btn.clicked.connect(lambda: self._probe(with_model=False))
        self.test_btn.clicked.connect(lambda: self._probe(with_model=True))

        if existing:
            self._load(existing)
        else:
            self._preset_changed()

    # --- form state -----------------------------------------------------------------------

    def _load(self, e: dict) -> None:
        self.preset.blockSignals(True)
        idx = self.preset.findData(e.get("provider") or ("custom-anthropic" if e["kind"] == "anthropic" else "custom"))
        self.preset.setCurrentIndex(max(idx, 0))
        self.preset.blockSignals(False)
        self.note.setText(providers.preset(self.preset.currentData()).note)
        self.name.setText(e.get("name", e["id"]))
        self.id.setText(e["id"])
        self.id.setReadOnly(True)
        self.id.setToolTip("已有的服务不能改 ID（Agent 配置引用它）。需要的话新建一个服务。")
        self.kind.setCurrentIndex(max(self.kind.findData(e["kind"]), 0))
        self.base_url.setText(e.get("base_url", ""))
        self.local.setChecked(e.get("local", False))
        self.env_name.setText(e.get("api_key_env", ""))
        if e.get("api_key_keyring"):
            self.key_keyring.setChecked(True)
        elif e.get("api_key_env"):
            self.key_env.setChecked(True)
        else:
            self.no_key.setChecked(True)
        self.data_class.setCurrentIndex(max(self.data_class.findData(e.get("max_data_class", "local_only" if e.get("local") else "internal")), 0))
        self.text_calls.setChecked(e.get("text_tool_calls", True))
        self.models.setPlainText("\n".join(e.get("models", [])))
        self._fill_test_models()
        self._show_key_state()

    def _preset_changed(self) -> None:
        p = providers.preset(self.preset.currentData())
        self.note.setText(p.note)
        self.name.setText(p.name)
        base = re.sub(r"[^a-z0-9_-]", "", p.id) or "api"
        nid, n = base, 2
        while nid in self.taken:
            nid, n = f"{base}-{n}", n + 1
        self.id.setText(nid)
        self.kind.setCurrentIndex(max(self.kind.findData(p.kind), 0))
        self.base_url.setText(p.base_url)
        self.local.setChecked(p.local)
        self.env_name.setText(p.key_env or "")
        (self.no_key if p.local else self.key_keyring).setChecked(True)
        self.data_class.setCurrentIndex(self.data_class.findData("local_only" if p.local else "internal"))
        self.text_calls.setChecked(True)
        self.models.setPlainText("")  # the service's own list: 获取模型列表
        self.fetched = []
        self._fill_test_models(keep=False)
        self._show_key_state()

    def _local_toggled(self, local: bool) -> None:
        if not local and self.data_class.currentData() == "local_only":
            self.data_class.setCurrentIndex(self.data_class.findData("internal"))

    def _key_mode_changed(self) -> None:
        self.key.setEnabled(self.key_keyring.isChecked())
        self.env_name.setEnabled(self.key_env.isChecked())
        self._show_key_state()

    def _show_key_state(self) -> None:
        if self.key_keyring.isChecked():
            saved = self.existing is not None and secrets.key_status(endpoint_of({**self.existing, "api_key_env": None,
                                                                                 "api_key_keyring": True})) == "keyring"
            if isinstance(self.staged, str):
                hint = "已填写，点页面上的“保存”后生效（留空表示不修改）"
            elif self.staged is None:
                hint = "保存后会删除已保存的密钥；在这里填写一个新密钥可以替换它"
            else:
                hint = "已保存（留空表示不修改）" if saved else "粘贴你的 API 密钥"
            self.key.setPlaceholderText(hint)
            self.key_state.setText("密钥只保存在本机的 Windows 凭据管理器，不写进配置文件和日志。")
        elif self.key_env.isChecked():
            var = self.env_name.text().strip()
            self.key_state.setText("该环境变量当前已设置。" if var and os.environ.get(var)
                                   else "该环境变量当前没有设置。")
        else:
            self.key_state.setText("")

    def _model_list(self) -> list[str]:
        seen, out = set(), []
        for m in self.models.toPlainText().splitlines():
            m = m.strip()
            if m and m not in seen:
                seen.add(m)
                out.append(m)
        return out

    def _fill_test_models(self, keep: bool = True) -> None:
        cur = self.test_model.currentText() if keep else ""
        self.test_model.clear()
        names = self._model_list() + [m for m in self.fetched if m not in self._model_list()]
        self.test_model.addItems(names)
        if cur:
            self.test_model.setCurrentText(cur)

    def _key_for_test(self) -> str | None:
        typed = self.key.text().strip()
        if self.key_keyring.isChecked():
            if typed:
                return typed
            if self.staged is not _NOTHING:
                return self.staged  # the unsaved key (or None: deletion pending)
            return secrets.get_key(endpoint_of({"id": self.id.text().strip(), "kind": "openai_compatible", "api_key_keyring": True}))
        if self.key_env.isChecked():
            return os.environ.get(self.env_name.text().strip()) or None
        return None

    # --- probe ----------------------------------------------------------------------------

    def _probe(self, with_model: bool) -> None:
        url = self.base_url.text().strip()
        if not url:
            self.result.setText("请先填写地址。")
            return
        model = self.test_model.currentText().strip() if with_model else None
        if with_model and not model:
            self.result.setText("请先选择或填写一个模型名。")
            return
        self.fetch_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self.result.setStyleSheet(f"color: {C['text2']};")
        self.result.setText("正在测试……" if with_model else "正在读取模型列表……")
        run_async(providers.probe(self.kind.currentData(), url, self._key_for_test(), model, timeout_s=90.0), self._probe_done)

    def _probe_done(self, res) -> None:
        self.fetch_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self.last_probe = res
        if isinstance(res, Exception):
            self._result(f"测试出错：{type(res).__name__}: {res}", C["red"])
            return
        lines = []
        if res.models:
            self.fetched = res.models
            self._fill_test_models()
            lines.append(f"服务可用，提供 {len(res.models)} 个模型（已加入下拉列表）。")
        elif res.models_error:
            lines.append(("服务有响应，但没有提供模型列表：" if res.reachable else "连不上服务：") + res.models_error[:300])
        if res.chat_error:
            lines.append("调用模型失败：" + res.chat_error[:400])
        elif res.tool_calls:
            lines.append(f"模型回复用时 {res.latency_ms / 1000:.1f} 秒；{TOOL_CN[res.tool_calls]}。")
        color = C["green"] if (res.ok or (res.tool_calls is None and res.models)) else (C["amber"] if res.reachable else C["red"])
        self._result("\n".join(lines) or "没有结果。", color)

    def _result(self, text: str, color: str) -> None:
        self.result.setStyleSheet(f"color: {color};")
        self.result.setText(text)

    # --- accept ---------------------------------------------------------------------------

    def value(self) -> dict:
        """The endpoint as it will be written to the configuration (no key in it)."""
        e = dict(self.existing or {})
        local = self.local.isChecked()
        e.update(id=self.id.text().strip(), name=self.name.text().strip() or self.id.text().strip(),
                 provider=self.preset.currentData(), kind=self.kind.currentData(),
                 base_url=self.base_url.text().strip().rstrip("/"), local=local,
                 max_data_class=self.data_class.currentData())
        for k in ("api_key_env", "api_key_keyring"):
            e.pop(k, None)
        if self.key_keyring.isChecked():
            e["api_key_keyring"] = True
            if (self.existing or {}).get("api_key_env"):  # an environment variable, when set, still wins
                e["api_key_env"] = self.existing["api_key_env"]
        elif self.key_env.isChecked():
            e["api_key_env"] = self.env_name.text().strip()
        if self.kind.currentData() == "openai_compatible" and not self.text_calls.isChecked():
            e["text_tool_calls"] = False
        else:
            e.pop("text_tool_calls", None)
        models = self._model_list()
        if models:
            e["models"] = models
        else:
            e.pop("models", None)
        return e

    def _accept(self) -> None:
        e = self.value()
        problems = []
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", e["id"]):
            problems.append("服务 ID 只能用小写字母、数字、- 和 _，并以字母或数字开头。")
        elif e["id"] in self.taken:
            problems.append(f"已经有 ID 为 “{e['id']}” 的服务。")
        if not re.match(r"https?://", e["base_url"]):
            problems.append("地址要以 http:// 或 https:// 开头。")
        if e.get("api_key_env") is not None and not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", e["api_key_env"]):
            problems.append("环境变量名只能用大写字母、数字和下划线。")
        if not e["local"] and e["max_data_class"] == "local_only":
            problems.append("远程服务不能接收“仅本机”的数据。")
        if problems:
            QMessageBox.warning(self, "请检查", "\n".join(problems))
            return
        typed = self.key.text().strip()
        self.typed_key = typed if e.get("api_key_keyring") and typed else None
        self.drop_key = bool((self.existing or {}).get("api_key_keyring")) and not e.get("api_key_keyring")
        self.key.clear()
        self.accept()


def watched_ids(a: dict) -> list[str]:
    """The workers a raw guardian entry re-checks (supervises, or supervises_workers in 协作小队)."""
    return ([a["supervises"]] if a.get("supervises") else []) + [w for w in a.get("supervises_workers", [])
                                                                 if w != a.get("supervises")]


def agents_summary(ids: list[str]) -> str:
    """'doctor、head-dispatch' - or for many: '41 个（doctor、head-dispatch、head-logic 和 19 对执行者 / 监督者）'."""
    if not ids:
        return "无"
    if len(ids) <= 6:
        return "、".join(ids)
    pairs = sum(i.startswith("worker-") for i in ids)
    others = [i for i in ids if not i.startswith(("worker-", "guardian-"))]
    rest = len(ids) - len(others) - 2 * pairs
    text = "、".join(others[:4]) + (f" 和 {pairs} 对执行者 / 监督者" if pairs else "") + (f" 等 {rest} 个" if rest > 0 else "")
    return f"{len(ids)} 个（{text.lstrip('、 ')}）"


class EndpointCard(Card):
    edit = Signal(str)
    remove = Signal(str)
    drop_key = Signal(str)
    test = Signal(str)

    def __init__(self, e: dict, used_by: list[str], pending=_NOTHING):
        """pending: a key typed and not yet saved (str), or None when its deletion is pending."""
        super().__init__(padding=16, spacing=5)
        status = key_status(e)
        text, fg, bg = KEY_CN[status]
        if isinstance(pending, str):
            text, fg, bg = "新密钥待保存", C["amber"], C["amber_soft"]
        elif pending is None:
            text, fg, bg = "保存后删除密钥", C["red"], C["red_soft"]
        top = QHBoxLayout()
        top.setSpacing(8)
        name = label(e.get("name") or e["id"], size=15, bold=True)
        name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        top.addWidget(name, 1)
        top.addWidget(Chip("本机" if e.get("local") else "云端", C["text2"], C["gray_soft"]))
        top.addWidget(Chip(text, fg, bg))
        self.lay.addLayout(top)
        kind = "Anthropic 接口" if e["kind"] == "anthropic" else ("测试脚本" if e["kind"] == "scripted" else "OpenAI 兼容接口")
        self.lay.addWidget(label(f"ID  {e['id']}   ·   {kind}   ·   {e.get('base_url', '')}", "Muted", wrap=True))
        dc = dict(DATA_CLASS_CN).get(e.get("max_data_class", "local_only" if e.get("local") else "internal"), "")
        users = label(f"可接收：{dc}   ·   使用它的 Agent：{agents_summary(used_by)}", "Faint", wrap=True)
        users.setToolTip("、".join(used_by))
        self.lay.addWidget(users)
        self.test_result = label("", "Faint", wrap=True)
        self.test_result.setVisible(False)
        self.lay.addWidget(self.test_result)
        if pending is not _NOTHING:
            self.lay.addWidget(label("密钥的改动和其他设置一样，点右下角“保存”才写进 Windows 凭据管理器；“放弃修改”或不保存就关掉，"
                                     "什么都不会留下。", size=12, color=C["amber"], wrap=True))
        elif status == "missing":
            where = "在“编辑与测试”里填写密钥" if e.get("api_key_keyring") else f"设置环境变量 {e.get('api_key_env')}，或在“编辑与测试”里改为保存到凭据管理器"
            self.lay.addWidget(label(f"这个服务还没有密钥：{where}。", size=12, color=C["red"], wrap=True))
        self.lay.addSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setObjectName("Ghost")
        self.test_btn.setToolTip("连上这个服务，读出它的模型列表，看看要多久")
        self.test_btn.clicked.connect(lambda: self.test.emit(e["id"]))
        row.addWidget(self.test_btn)
        ed = QPushButton("编辑")
        ed.setObjectName("Ghost")
        ed.clicked.connect(lambda: self.edit.emit(e["id"]))
        row.addWidget(ed)
        if status == "keyring" and pending is _NOTHING:
            dk = QPushButton("删除密钥")
            dk.setObjectName("Ghost")
            dk.setToolTip("从 Windows 凭据管理器里删除这个服务的密钥（点“保存”后执行）")
            dk.clicked.connect(lambda: self.drop_key.emit(e["id"]))
            row.addWidget(dk)
        row.addStretch(1)
        rm = QPushButton("删除")
        rm.setObjectName("Ghost")
        rm.clicked.connect(lambda: self.remove.emit(e["id"]))
        row.addWidget(rm)
        self.lay.addLayout(row)

    def show_test(self, text: str, good: bool) -> None:
        self.test_result.setText(text)
        self.test_result.setStyleSheet(f"color: {C['green'] if good else C['red']}; font-size: 12px;")
        self.test_result.setVisible(True)


COL_AGENT, COL_SERVICE, COL_REMOVE = 150, 150, 56


class TeamIntro(QWidget):
    """The Lumen team at a glance: eight avatars with their names and what each one does."""

    def __init__(self):
        super().__init__()
        from codedoctor.agents import team
        from codedoctor.desktop.team_ui import MemberAvatar

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(6)
        lay.addWidget(label("Lumen 团队", size=15, bold=True))
        lay.addWidget(label("你只跟 Lumen 说话；专门的活它会交给最合适的成员，几个人可以同时干。每个成员都记得自己做过的事，"
                            "需要时还能叫一次性的助手帮忙。每个成员用你选的模型，可以在下面单独换。",
                            wrap=True, size=13, color=C["text2"]))
        cells = []
        for m in team.MEMBERS:
            cell = vbox(hbox(None, MemberAvatar(m.id, 48), None, spacing=0),
                        label(m.name, size=12, bold=True, color=C["ink"]), label(m.job, size=11, color=C["text3"]),
                        spacing=2)
            for i in (1, 2):
                cell.layout().itemAt(i).widget().setAlignment(Qt.AlignHCenter)
            cell.setToolTip(f"{m.name} {m.cn} · {m.meaning}")
            cells.append(cell)
        lay.addWidget(CardGrid(cells, 76, 4, 8))


WIDE_ROW = 820  # below this a row goes onto two lines, nothing is cut off at the window's edge


class AgentHeader(QWidget):
    """The columns' names, while the rows are one line each."""

    def __init__(self):
        super().__init__()
        g = QHBoxLayout(self)
        g.setContentsMargins(4, 0, 4, 2)
        g.setSpacing(10)
        g.addSpacing(30)
        for text, width in (("Agent", COL_AGENT), ("服务", COL_SERVICE), ("模型", None), ("思考", 96), ("备用模型", None)):
            lb = label(text, "Faint")
            if width:
                lb.setFixedWidth(width)
            g.addWidget(lb, 0 if width else 1)
        g.addSpacing(COL_REMOVE)
        g.setSizeConstraint(QLayout.SetNoConstraint)
        self.setMinimumWidth(1)  # the column names must not hold a narrow window open

    def minimumSizeHint(self):
        return QSize(1, 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.setMaximumHeight(16777215 if e.size().width() >= WIDE_ROW else 0)


def agent_header() -> QWidget:
    return AgentHeader()


class AgentRow(QWidget):
    changed = Signal()
    remove = Signal(str)

    def __init__(self, a: dict, endpoints: list[dict], removable: bool):
        super().__init__()
        self.a = a
        self.endpoints = {e["id"]: e for e in endpoints}
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(4, 6, 4, 6)
        self.grid.setSpacing(10)
        if a.get("team"):  # a member of the Lumen team: its avatar, name and job; its meaning on hover
            from codedoctor.agents import team
            from codedoctor.desktop.team_ui import MemberAvatar

            m = team.BY_ID[a["id"]]
            self.face = MemberAvatar(m.id, 34)
            who = vbox(hbox(label(m.name, size=14, bold=True), label(m.cn, size=13, color=m.colour), None, spacing=5),
                       label(m.job, size=12, color=C["text3"]), spacing=0)
            who.setToolTip(m.meaning)
        else:
            self.face = Avatar(a["role"], 30)
            who = vbox(label(a["id"], size=14, bold=True), label(ROLE_CN.get(a["role"], a["role"]) +
                                                                 (f" · 监督 {'、'.join(watched_ids(a))}" if watched_ids(a) else ""),
                                                                 size=12, color=ROLE_COLOR.get(a["role"])), spacing=0)
        who.setFixedWidth(COL_AGENT)
        self.who = who
        self.ep = QComboBox()
        self.ep.setMinimumWidth(100)
        for e in endpoints:
            self.ep.addItem(e.get("name") or e["id"], e["id"])
        self.ep.setCurrentIndex(max(self.ep.findData(a["endpoint"]), 0))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setMinimumWidth(120)
        self._fill_models()
        self.model.setCurrentText(a["model"])
        self.fb = QLineEdit(fallbacks_text(a))
        self.fb.setMinimumWidth(90)
        self.fb.setPlaceholderText("备用：服务ID/模型，可不填")
        self.fb.setToolTip("主模型出错时按顺序改用这些模型。不填则出错时暂停并通知你。例如：openai/gpt-x, ollama/qwen3:4b")
        self.think = QComboBox()  # 思考强度 (models/reasoning.py): each provider gets its own parameter
        self.think.setFixedWidth(96)
        self.think.setToolTip("思考强度：越高想得越深，也越慢、越费 token")
        from codedoctor.models.reasoning import LEVEL_CN, LEVELS

        for k in LEVELS:
            self.think.addItem(f"{LEVEL_CN[k]}", k)
        self.think.setCurrentIndex(max(self.think.findData((a.get("params") or {}).get("reasoning") or "medium"), 0))
        self.think.currentIndexChanged.connect(self._apply_think)
        self.rm = QPushButton("移除")
        self.rm.setObjectName("Ghost")
        self.rm.setFixedWidth(COL_REMOVE)
        keep = self.rm.sizePolicy()
        keep.setRetainSizeWhenHidden(True)
        self.rm.setSizePolicy(keep)
        self.rm.clicked.connect(lambda: self.remove.emit(a["id"]))
        self.wide = None
        self._arrange(True)
        # only now: a parentless button made visible becomes a tiny window of its own on Windows
        self.rm.setVisible(removable)
        self.ep.currentIndexChanged.connect(self._ep_changed)
        self.model.currentTextChanged.connect(self._apply)
        self.fb.textChanged.connect(lambda _: self.changed.emit())

    def _fill_models(self) -> None:
        e = self.endpoints.get(self.ep.currentData()) or {}
        cur = self.model.currentText()
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(e.get("models", []))
        self.model.setCurrentText(cur)
        self.model.blockSignals(False)

    def _ep_changed(self) -> None:
        self._fill_models()
        e = self.endpoints.get(self.ep.currentData()) or {}
        if e.get("models") and self.model.currentText() not in e["models"]:
            self.model.setCurrentText("")  # the old model name belongs to another service: make the user choose
        self._apply()

    def _apply(self) -> None:
        self.a["endpoint"] = self.ep.currentData()
        self.a["model"] = self.model.currentText().strip()
        self.changed.emit()

    def _apply_think(self) -> None:
        params = self.a.setdefault("params", {})
        if self.think.currentData():
            params["reasoning"] = self.think.currentData()
        else:
            params.pop("reasoning", None)
            if not params:
                self.a.pop("params")
        self.changed.emit()

    def commit_fallbacks(self, endpoint_ids) -> None:
        fbs = parse_fallbacks(self.fb.text(), endpoint_ids)
        if fbs:
            self.a["fallbacks"] = fbs
        else:
            self.a.pop("fallbacks", None)


def _agent_row_arrange(self, wide: bool) -> None:
    """One line when there is room, two when there is not."""
    if wide == self.wide:
        return
    self.wide = wide
    g = self.grid
    parts = (self.face, self.who, self.ep, self.model, self.think, self.fb, self.rm)
    for w in parts:
        g.removeWidget(w)
    for i in range(7):
        g.setColumnStretch(i, 0)
    if wide:
        self.ep.setFixedWidth(COL_SERVICE)
        for i, w in enumerate(parts):
            g.addWidget(w, 0, i)
        g.setColumnStretch(3, 1)
        g.setColumnStretch(5, 1)
    else:
        self.ep.setMinimumWidth(100)
        self.ep.setMaximumWidth(16777215)
        g.addWidget(self.face, 0, 0)
        g.addWidget(self.who, 0, 1, 1, 3)
        g.addWidget(self.rm, 0, 4)
        g.addWidget(self.ep, 1, 1)
        g.addWidget(self.model, 1, 2)
        g.addWidget(self.think, 1, 3)
        g.addWidget(self.fb, 1, 4)
        g.setColumnStretch(1, 2)
        g.setColumnStretch(2, 3)
        g.setColumnStretch(4, 2)


AgentRow._arrange = _agent_row_arrange
AgentRow.resizeEvent = lambda self, e: (QWidget.resizeEvent(self, e), self._arrange(e.size().width() >= WIDE_ROW))[0]


class EmbeddingRow(QWidget):
    """Semantic recall (ADR 0007): the user picks an embedding model, or none. Writes raw['memory']['embedding']."""
    changed = Signal()

    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw
        cur = raw.get("memory", {}).get("embedding") or {}
        self.endpoints = {e["id"]: e for e in raw["endpoints"]}
        g = QHBoxLayout(self)
        g.setContentsMargins(4, 6, 4, 6)
        g.setSpacing(10)
        self.ep = QComboBox()
        self.ep.setMinimumWidth(100)
        self.ep.addItem("不使用", None)
        for e in raw["endpoints"]:
            if e["kind"] == "openai_compatible":  # the Anthropic API has no embeddings
                self.ep.addItem(e.get("name") or e["id"], e["id"])
        self.ep.setCurrentIndex(max(self.ep.findData(cur.get("endpoint")), 0))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setMinimumWidth(130)
        self.model.lineEdit().setPlaceholderText("嵌入模型名，例如 bge-m3、text-embedding-3-small")
        self._fill_models()
        self.model.setCurrentText(cur.get("model", ""))
        self.test = QPushButton("测试")
        self.test.setObjectName("Ghost")
        self.result = label("", "Faint", wrap=True)
        g.addWidget(label("嵌入模型", "Muted"))
        g.addWidget(self.ep)
        g.addWidget(self.model, 1)
        g.addWidget(self.test)
        self._enable()
        self.ep.currentIndexChanged.connect(self._ep_changed)
        self.model.currentTextChanged.connect(lambda _: self._apply())
        self.test.clicked.connect(self._test)

    def _fill_models(self) -> None:
        e = self.endpoints.get(self.ep.currentData()) or {}
        cur = self.model.currentText()
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(e.get("models", []))
        self.model.setCurrentText(cur)
        self.model.blockSignals(False)

    def _enable(self) -> None:
        on = self.ep.currentData() is not None
        self.model.setEnabled(on)
        self.test.setEnabled(on)

    def _ep_changed(self) -> None:
        self._fill_models()
        self.model.setCurrentText("")  # a model name belongs to one service: make the user choose again
        self._apply()

    def _apply(self) -> None:
        eid = self.ep.currentData()
        mem = self.raw.get("memory", {})
        if eid:
            old = mem.get("embedding", {})
            emb = {"endpoint": eid, "model": self.model.currentText().strip()}
            if "min_similarity" in old and old.get("endpoint") == eid and old.get("model") == emb["model"]:
                emb["min_similarity"] = old["min_similarity"]  # tuned for that model only
            self.raw["memory"] = {**mem, "embedding": emb}
        elif "embedding" in mem:
            rest = {k: v for k, v in mem.items() if k != "embedding"}
            if rest:
                self.raw["memory"] = rest
            else:
                self.raw.pop("memory")
        self._enable()
        self.result.setText("")
        self.changed.emit()

    def _test(self) -> None:
        e = self.endpoints[self.ep.currentData()]
        model = self.model.currentText().strip()
        if not model:
            self.result.setText("请先选择或填写嵌入模型名。")
            return
        key = secrets.get_key(endpoint_of(e)) if e.get("api_key_env") or e.get("api_key_keyring") else None
        self.test.setEnabled(False)
        self.result.setStyleSheet(f"color: {C['text2']};")
        self.result.setText("正在测试（只发送两句固定的测试文字）……")
        run_async(providers.probe_embedding(e["kind"], e["base_url"], key, model, timeout_s=90.0), self._test_done)

    def _test_done(self, res) -> None:
        self.test.setEnabled(True)
        self.last_probe = res
        if isinstance(res, Exception):
            text, color = f"测试出错：{type(res).__name__}: {res}", C["red"]
        elif res.error:
            text, color = f"不能用：{res.error}", C["red"]
        else:
            text, color = f"可用：向量维度 {res.dimensions}，用时 {res.latency_ms} ms。", C["green"]
        self.result.setStyleSheet(f"color: {color};")
        self.result.setText(text)


class ComputerSettings(QWidget):
    """Computer-use permissions (ADR 0012). Writes raw['computer']; config validation runs on save."""
    changed = Signal()
    MODES = [("off", "关闭"), ("guardian", "监督员事前批准"), ("ask", "每次问我")]

    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw
        cur = raw.get("computer", {})
        form = QFormLayout(self)
        form.setContentsMargins(4, 4, 4, 4)
        self.shot = QComboBox()
        for v, t in (("off", "关闭"), ("on", "开启（只截允许的窗口）")):
            self.shot.addItem(t, v)
        self.shot.setCurrentIndex(max(self.shot.findData(cur.get("screenshot", "off")), 0))
        self.modes = {}
        for key, title in (("input", "鼠标和键盘"), ("apps", "启动 / 关闭程序"), ("terminal", "终端命令")):
            box = QComboBox()
            for v, t in self.MODES:
                box.addItem(t, v)
            box.setCurrentIndex(max(box.findData(cur.get(key, "off")), 0))
            self.modes[key] = (box, title)
        self.windows = QPlainTextEdit("\n".join(cur.get("windows", [])))
        self.windows.setPlaceholderText("每行一个窗口标题里的文字，例如：MyGame")
        self.windows.setFixedHeight(64)
        self.launch = QPlainTextEdit("\n".join(f"{t['id']} = {t['path']}" + "".join(f" {a}" for a in t.get("args", []))
                                               for t in cur.get("launch", [])))
        self.launch.setPlaceholderText("每行一个可以启动的程序：名称 = 路径 [参数]，例如：game = D:/games/mygame.exe --windowed")
        self.launch.setFixedHeight(64)
        self.dc = QComboBox()
        for v, t in DATA_CLASS_CN:
            self.dc.addItem(t, v)
        self.dc.setCurrentIndex(max(self.dc.findData(cur.get("screenshot_data_class", "internal")), 0))
        self.where = QComboBox()
        self.where.addItem("在后台，不占用我的鼠标键盘", True)
        self.where.addItem("在前台，用我的鼠标键盘", False)
        self.where.setCurrentIndex(max(self.where.findData(cur.get("background", True)), 0))
        form.addRow("操作方式", self.where)
        form.addRow("截屏", self.shot)
        for box, title in self.modes.values():
            form.addRow(title, box)
        form.addRow("允许操作的窗口", self.windows)
        form.addRow("允许启动的程序", self.launch)
        form.addRow("截图的数据级别", self.dc)
        for w in (self.shot, self.dc, self.where, *(b for b, _ in self.modes.values())):
            w.currentIndexChanged.connect(self._apply)
        self.windows.textChanged.connect(self._apply)
        self.launch.textChanged.connect(self._apply)

    def _launch_list(self) -> list[dict]:
        out = []
        for line in filter(None, (ln.strip() for ln in self.launch.toPlainText().splitlines())):
            name, sep, rest = line.partition("=")
            parts = rest.split()
            if not sep or not name.strip() or not parts:
                raise ValueError(f"“{line}” 应写成 名称 = 路径 [参数]")
            item = {"id": name.strip().lower(), "path": parts[0]}
            if parts[1:]:
                item["args"] = parts[1:]
            out.append(item)
        return out

    def _apply(self) -> None:
        comp = {k: v for k, v in self.raw.get("computer", {}).items() if k in ("capture", "guardian_timeout_s", "user_timeout_s",
                                                                              "max_actions_per_task")}
        comp["screenshot"] = self.shot.currentData()
        if self.where.currentData() is False:
            comp["background"] = False
        for key, (box, _) in self.modes.items():
            comp[key] = box.currentData()
        wins = [ln.strip() for ln in self.windows.toPlainText().splitlines() if ln.strip()]
        if wins:
            comp["windows"] = wins
        try:
            launch = self._launch_list()
        except ValueError:
            launch = self.raw.get("computer", {}).get("launch", [])  # keep the last valid list while typing
        if launch:
            comp["launch"] = launch
        if self.dc.currentData() != "internal":
            comp["screenshot_data_class"] = self.dc.currentData()
        if all(comp.get(k, "off") == "off" for k in ("screenshot", "input", "apps", "terminal")) and not wins and not launch:
            self.raw.pop("computer", None)
        else:
            self.raw["computer"] = comp
        self.changed.emit()


def detect_test_command(root: Path) -> str:
    """A sensible default for permissions.test_command (the user can change it)."""
    import sys

    if (root / "package.json").exists():
        try:
            import json as _json

            if "test" in _json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts", {}):
                return "npm test"
        except (OSError, ValueError):
            pass
    if any((root / d).is_dir() for d in ("tests", "test")) or list(root.glob("test_*.py")):
        own = next((p for p in (root / ".venv" / "Scripts" / "python.exe", root / "venv" / "Scripts" / "python.exe",
                                root / ".venv" / "bin" / "python") if p.exists()), None)  # the project's own packages
        return f"{(own or Path(sys.executable)).as_posix()} -m pytest -q -p no:cacheprovider"
    return ""


class CodeSettings(QWidget):
    """Changing code and running tests (ADR 0016). Writes raw['permissions']; config validation runs on save."""
    changed = Signal()

    def __init__(self, raw: dict):
        super().__init__()
        self.raw = raw
        cur = raw.get("permissions", {})
        form = QFormLayout(self)
        form.setContentsMargins(4, 4, 4, 4)
        self.write = QCheckBox("允许 Agent 直接修改项目文件（执行者动手改，监督者复查并汇报）")
        self.write.setChecked(bool(cur.get("write_files")))
        self.cmd = QComboBox()
        for v, t in (("deny", "不允许"), ("allowlist", "只允许下面列出的命令")):
            self.cmd.addItem(t, v)
        self.cmd.setCurrentIndex(max(self.cmd.findData(cur.get("run_command", "deny")), 0))
        self.allow = QPlainTextEdit("\n".join(cur.get("command_allowlist", [])))
        self.allow.setPlaceholderText("每行一个允许的命令开头，例如：python -m pytest")
        self.allow.setFixedHeight(70)
        self.test = QLineEdit(cur.get("test_command", ""))
        self.test.setPlaceholderText("例如：python -m pytest -q    （留空 = 不自动跑测试）")
        detect = QPushButton("自动检测")
        detect.setObjectName("Ghost")
        detect.clicked.connect(self._detect)
        test_row = QHBoxLayout()
        test_row.addWidget(self.test, 1)
        test_row.addWidget(detect)
        form.addRow(self.write)
        form.addRow("运行命令", self.cmd)
        form.addRow("允许的命令", self.allow)
        form.addRow("测试命令", test_row)
        self.hint = label("", "Faint", wrap=True)
        form.addRow(self.hint)
        self.write.toggled.connect(self._apply)
        self.cmd.currentIndexChanged.connect(lambda: self.allow.setEnabled(self.cmd.currentData() == "allowlist"))
        self.allow.setEnabled(self.cmd.currentData() == "allowlist")
        self.cmd.currentIndexChanged.connect(self._apply)
        self.allow.textChanged.connect(self._apply)
        self.test.textChanged.connect(self._apply)
        self._hint()

    def _detect(self) -> None:
        root = Path(self.raw.get("project", {}).get("root", "."))
        found = detect_test_command(root)
        if found:
            self.test.setText(found)
        else:
            self.hint.setText("没找到测试：项目里没有 tests 目录、test_*.py 或 package.json 的 test 脚本。")

    def _hint(self) -> None:
        if self.write.isChecked() and not self.test.text().strip():
            self.hint.setText("建议填上测试命令：系统会在开工前、每处修改后、交差前自动跑测试（不花 token），"
                              "谁改坏了原来能过的测试，当场就会被指出来。")
        elif self.test.text().strip():
            self.hint.setText("测试由系统直接运行（不经过模型），不需要加进“允许的命令”。")
        else:
            self.hint.setText("")

    def _apply(self) -> None:
        perm = dict(self.raw.get("permissions", {}))
        perm["write_files"] = self.write.isChecked()
        perm["run_command"] = self.cmd.currentData()
        allow = [ln.strip() for ln in self.allow.toPlainText().splitlines() if ln.strip()]
        if allow:
            perm["command_allowlist"] = allow
        else:
            perm.pop("command_allowlist", None)
        if perm["run_command"] == "allowlist" and not allow:
            perm["run_command"] = "deny"  # an empty allowlist means nothing may run (and is invalid in the schema)
        test = self.test.text().strip()
        if test:
            perm["test_command"] = test
        else:
            perm.pop("test_command", None)
        if not perm.get("write_files"):
            perm.pop("write_files", None)
        self.raw["permissions"] = perm
        self._hint()
        self.changed.emit()


SECTIONS = [("services", "服务与密钥"), ("agents", "Agent 模型"), ("schedule", "协作方式"), ("memory", "长期记忆"),
            ("code", "改代码与测试"), ("computer", "电脑操作"), ("appearance", "外观")]
SECTION_SUB = {
    "services": "可以接入任意多个服务：DeepSeek、OpenAI、Claude、Gemini、通义、Kimi、智谱、OpenRouter、本机 Ollama……"
                "只要兼容 OpenAI 接口或 Anthropic 接口就行。密钥保存在 Windows 凭据管理器，不写进配置文件。",
    "agents": "每个 Agent 用哪个服务、哪个模型，完全由你选。监督者会独立复查它所监督的执行者，建议给监督者选和执行者不同的模型。",
    "schedule": "单人助手、双人互检、协作小队、双首脑集群四种协作方式，以及集群的人数（首脑、执行者、监督者合计最多 40 个）。",
    "memory": "长期记忆永久保存在本机。选一个嵌入模型后，Agent 还能按意思想起用词不同的旧结论。",
    "code": "允许 Agent 直接改代码时：执行者只管动手改，监督者逐处复查并汇报；系统在每处修改后自动跑测试，谁改坏了当场指出。"
            "开始时关闭，只诊断不修改。",
    "computer": "截屏、鼠标键盘、开关程序、终端。开始时全部关闭；有副作用的操作先由监督员批准，不可逆的还要你本人批准。",
    "appearance": "壁纸、开场动画和动态效果。只影响这台电脑上的你，改了立即生效，不用保存，也不用重启。",
}


class ModelsPage(QWidget):
    restart_requested = Signal()
    section_changed = Signal(str)
    keys_changed = Signal()  # a key was saved or removed: the sidebar and home page re-check at once
    appearance_changed = Signal(dict)  # wallpaper / motion (per user, applied at once, not in the project)
    replay_welcome = Signal()
    open_page = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.path = cfg.source
        self.raw = config_mod.load_raw(self.path) if self.path else None
        self.dirty = False
        self.section = "services"
        self.pending_keys: dict[str, str | None] = {}  # endpoint id -> key to save, or None to delete (on 保存)
        self.running_agents = len(cfg.agents)  # what the open window runs; changes apply after save + restart
        self.saved_agents = len(cfg.agents)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 22, 22, 14)
        outer.setSpacing(10)
        self.page_title = label("设置", "PageTitle")
        outer.addWidget(self.page_title)
        self.tab_row = QWidget()
        tabs = QHBoxLayout(self.tab_row)
        tabs.setContentsMargins(0, 0, 0, 0)
        tabs.setSpacing(0)
        self.tab_group = QButtonGroup(self)
        self.tab_btns: dict[str, QPushButton] = {}
        for key, text in SECTIONS:
            b = QPushButton(text)
            b.setObjectName("Tab")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.tab_group.addButton(b)
            self.tab_btns[key] = b
            b.clicked.connect(lambda _=False, k=key: self.show_section(k))
            tabs.addWidget(b)
        tabs.addStretch(1)
        self.tab_btns[self.section].setChecked(True)
        outer.addWidget(self.tab_row)
        self.sub = label("", "PageSub", wrap=True)
        outer.addWidget(self.sub)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)

        bar = QHBoxLayout()
        self.state = label("", "Faint")
        self.state.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # a long path must not widen the window
        bar.addWidget(self.state, 1)
        self.revert_btn = QPushButton("放弃修改")
        self.revert_btn.setObjectName("Ghost")
        self.revert_btn.clicked.connect(self.revert)
        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self.save)
        bar.addWidget(self.revert_btn)
        bar.addWidget(self.save_btn)
        outer.addLayout(bar)
        self.rows: list[AgentRow] = []
        self.computer = self.cluster = self.embedding = None
        # The "Agent 模型" tab is expensive with 40 agents (an editable combo box per row): it is built once and
        # kept while switching tabs; render() (the data changed) drops it.
        self._agents_cache: QWidget | None = None
        self._agents_rows: list[AgentRow] = []
        self.render()

    def embed(self) -> None:
        """Shown inside the 设置 hub: its menu replaces the tab row, the title names the current section."""
        self.tab_row.hide()
        self._embedded = True
        self.page_title.setText(dict(SECTIONS)[self.section])

    # --- sections -------------------------------------------------------------------------

    def show_section(self, key: str) -> None:
        if key != self.section:
            if not self._leave_section():
                self.tab_btns[self.section].setChecked(True)
                return
            self.section = key
            self._build()
        self.tab_btns[key].setChecked(True)
        self.section_changed.emit(key)

    def _leave_section(self) -> bool:
        """Keep what was typed in the section being left (fallback models, program list); refuse to leave on an error."""
        if self.raw is None:
            return True
        try:
            ids = {e["id"] for e in self.raw["endpoints"]}
            for row in self.rows:
                row.commit_fallbacks(ids)
        except ValueError as e:
            QMessageBox.warning(self, "备用模型写法有误", str(e))
            return False
        if self.computer is not None:
            try:
                self.computer._launch_list()
            except ValueError as e:
                QMessageBox.warning(self, "允许启动的程序写法有误", str(e))
                return False
            self.computer._apply()
        return True

    # --- rendering ------------------------------------------------------------------------

    def render(self) -> None:
        """The configuration changed: rebuild the current tab (and forget the kept "Agent 模型" tab)."""
        cache, self._agents_cache = self._agents_cache, None
        self._agents_rows = []
        if cache is not None and cache is not self.scroll.widget():
            cache.deleteLater()  # if it is on screen, _swap() below takes it out and deletes it
        self._build()

    def _swap(self, host: QWidget) -> None:
        # Often called from a signal of a widget inside the old content (the pairs slider being released, a mode
        # button, a row's "remove"). setWidget() would delete that widget at once, while Qt is still inside its
        # event handler - which crashes the whole app. Take the old content out and delete it once control is back
        # in the event loop instead (or keep it, if it is the kept "Agent 模型" tab).
        old = self.scroll.takeWidget()
        self.scroll.setWidget(host)
        host.show()
        if old is not None and old is not host:
            old.hide()
            if old is self._agents_cache:
                old.setParent(self)  # kept, hidden, owned by the page (never a parentless window)
                old.hide()
            else:
                old.deleteLater()

    def _build(self) -> None:
        self.computer = self.cluster = self.embedding = None
        self.sub.setText(SECTION_SUB[self.section])
        if getattr(self, "_embedded", False):
            self.page_title.setText(dict(SECTIONS)[self.section])
        if self.section == "agents" and self._agents_cache is not None:
            self.rows = self._agents_rows
            self._swap(self._agents_cache)
            self._update_bar()
            return
        self.rows = []
        host = QWidget()
        self.body = QVBoxLayout(host)
        self.body.setContentsMargins(0, 6, 8, 4)
        self.body.setSpacing(10)
        slow = self.section == "agents" and self.raw is not None and len(self.raw["agents"]) > 12
        if slow:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if self.raw is None:
                self.body.addWidget(label("这个窗口没有从配置文件启动，不能在这里修改。", "Muted"))
            else:
                getattr(self, f"_render_{self.section}")()
            self.body.addStretch(1)
            if self.section == "agents":
                self._agents_cache, self._agents_rows = host, self.rows
            self._swap(host)
        finally:
            if slow:
                QApplication.restoreOverrideCursor()
        self._update_bar()

    def _render_services(self) -> None:
        eps, agents = self.raw["endpoints"], self.raw["agents"]
        head = QHBoxLayout()
        head.addWidget(label(f"已接入 {len(eps)} 个服务", size=15, bold=True))
        head.addStretch(1)
        every = QPushButton("全部测试")
        every.setObjectName("Ghost")
        every.clicked.connect(self.test_all)
        head.addWidget(every)
        add = QPushButton("＋ 添加服务")
        add.setObjectName("Primary")
        add.clicked.connect(lambda: self.edit_endpoint(None))
        head.addWidget(add)
        self.body.addLayout(head)
        self.endpoint_cards: dict[str, EndpointCard] = {}
        for e in eps:
            used = [a["id"] for a in agents if a["endpoint"] == e["id"] or any(f["endpoint"] == e["id"] for f in a.get("fallbacks", []))]
            card = EndpointCard(e, used, self.pending_keys.get(e["id"], _NOTHING))
            card.edit.connect(self.edit_endpoint)
            card.remove.connect(self.remove_endpoint)
            card.drop_key.connect(self.drop_key)
            card.test.connect(self.test_endpoint)
            self.endpoint_cards[e["id"]] = card
        self.body.addWidget(CardGrid(list(self.endpoint_cards.values())))

    def test_endpoint(self, eid: str) -> None:
        """The service answers or it does not: how long it took and how many models it lists. Nothing of the project is sent."""
        card = self.endpoint_cards[eid]
        e = next(x for x in self.raw["endpoints"] if x["id"] == eid)
        if e["kind"] == "engine":
            from codedoctor import engines

            name = e["base_url"].split(":", 1)[1]
            card.test_btn.setEnabled(False)
            card.show_test("正在检查……", True)

            async def ask():
                import asyncio

                return await asyncio.to_thread(engines.status, name)

            def answered(state) -> None:
                card.test_btn.setEnabled(True)
                words = {"ready": f"已登录，{len(engines.models(name))} 个模型", "login": "还没有登录", "missing": "没有安装"}
                card.show_test(f"{engines.TITLES[name]}：{words.get(state, state)}", state == "ready")

            run_async(ask(), answered)
            return
        if e["kind"] == "scripted":
            card.show_test("这是测试脚本，没有可连接的服务", True)
            return
        import time as _time

        card.test_btn.setEnabled(False)
        card.show_test("正在连接……", True)
        pending = self.pending_keys.get(eid, _NOTHING)
        key = pending if isinstance(pending, str) else secrets.get_key(endpoint_of(e))
        began = _time.perf_counter()

        def done(res) -> None:
            if eid not in self.endpoint_cards or self.endpoint_cards[eid] is not card:
                return
            card.test_btn.setEnabled(True)
            ms = int((_time.perf_counter() - began) * 1000)
            if isinstance(res, Exception):
                card.show_test(f"没有连上：{type(res).__name__}: {str(res)[:120]}", False)
            elif res.models:
                card.show_test(f"连上了，{ms} 毫秒，这个服务有 {len(res.models)} 个模型", True)
            elif res.reachable:
                card.show_test(f"连上了，{ms} 毫秒。它没有列出模型：{(res.models_error or '')[:100]}", True)
            else:
                card.show_test(f"没有连上：{(res.models_error or '没有回应')[:140]}", False)

        run_async(providers.probe(e["kind"], e.get("base_url", ""), key, None, timeout_s=30.0), done)

    def test_all(self) -> None:
        for eid in list(self.endpoint_cards):
            self.test_endpoint(eid)

    def _render_agents(self) -> None:
        eps, agents = self.raw["endpoints"], self.raw["agents"]
        head = QHBoxLayout()
        head.addWidget(label(f"{len(agents)} 个 Agent", size=15, bold=True))
        head.addStretch(1)
        from codedoctor import topology

        mode = topology.current(self.raw)[0]
        if mode == "advanced":
            pair = QPushButton("＋ 添加一对 执行者 + 监督者")
            pair.setObjectName("Ghost")
            pair.clicked.connect(self.add_pair)
            head.addWidget(pair)
        else:
            head.addWidget(label("人数和结构在“调度设置”里改", "Faint"))
        crew = [a for a in agents if a.get("team")]
        if crew:  # the Lumen team first: the one the user talks to (agents/team.py)
            self.body.addWidget(TeamIntro())
            card = Card(padding=10, spacing=0)
            card.lay.addWidget(agent_header())
            for a in crew:
                row = AgentRow(a, eps, False)
                row.changed.connect(self._mark_dirty)
                self.rows.append(row)
                card.lay.addWidget(row)
            self.body.addWidget(card)
            self.body.addSpacing(14)
            agents = [a for a in agents if not a.get("team")]
            head.itemAt(0).widget().setText(f"其他模式的 Agent（{len(agents)} 个）")
        self.body.addLayout(head)
        card = Card(padding=10, spacing=0)
        card.lay.addWidget(agent_header())
        workers = {a["id"] for a in agents if a["role"] in ("worker", "investigator")}
        for a in agents:
            removable = mode == "advanced" and a["role"] in ("worker", "investigator", "guardian") and \
                (a["role"] == "guardian" or len(workers) > 1)
            row = AgentRow(a, eps, removable)
            row.changed.connect(self._mark_dirty)
            row.remove.connect(self.remove_agent)
            self.rows.append(row)
            card.lay.addWidget(row)
        self.body.addWidget(card)
        self.body.addSpacing(10)
        self.body.addWidget(label("上下文与记忆", size=15, bold=True))
        ctx = Card(padding=16, spacing=8)
        ctx.lay.addWidget(ContextInfo(self.raw))
        self.body.addWidget(ctx)

    def _render_schedule(self) -> None:
        sched = Card(padding=18, spacing=8)
        self.cluster = ClusterSettings(self.raw, running=self.running_agents,
                                       saved=None if self.dirty else self.saved_agents)  # ADR 0014
        self.cluster.changed.connect(self._mark_dirty)
        self.cluster.structure_changed.connect(self._structure_changed)
        sched.lay.addWidget(self.cluster)
        self.body.addWidget(sched)

    def _render_memory(self) -> None:
        agents = self.raw["agents"]
        card = Card(padding=18, spacing=10)
        card.setMaximumWidth(680)
        card.lay.addWidget(label("每个成员怎么记事", size=15, bold=True))
        card.lay.addWidget(label("Lumen 团队的每个成员都有自己的记忆。这里的设置作用于这个项目的所有 Agent，保存后重启生效。", "Muted", wrap=True))
        form = QFormLayout()
        form.setSpacing(12)
        first = next(iter(agents), {})
        recall = QSpinBox()
        recall.setRange(0, 50)
        recall.setValue(int((first.get("memory") or {}).get("recall_k", 8)))
        recall.setToolTip("开始一项工作前，成员最多想起多少条有关的旧结论。0 表示不主动回忆。")
        context = QComboBox()
        for tokens, text in ((64000, "64K"), (128000, "128K"), (200000, "200K"), (400000, "400K"), (1000000, "1M")):
            context.addItem(text, tokens)
        context.setCurrentIndex(max(context.findData(first.get("context_budget_tokens", 64000)), 0))
        context.setToolTip("一个成员一次工作能带多少上下文。越长记得越多，也越费 token。")

        def recall_changed(v):
            for a in self.raw["agents"]:
                a.setdefault("memory", {})["recall_k"] = v
            self._mark_dirty()

        def context_changed(_):
            for a in self.raw["agents"]:
                a["context_budget_tokens"] = context.currentData()
            self._mark_dirty()

        recall.valueChanged.connect(recall_changed)
        context.currentIndexChanged.connect(context_changed)
        form.addRow("每次回忆多少条", recall)
        form.addRow("最长上下文", context)
        card.lay.addLayout(form)
        look = QPushButton("查看所有记忆和结论")
        look.setObjectName("Ghost")
        look.clicked.connect(lambda: self.open_page.emit("knowledge"))
        card.lay.addWidget(hbox(look, None))
        self.body.addWidget(card)
        self.body.addWidget(label("按意思回忆（可选）", size=15, bold=True))
        self.body.addWidget(label("选一个嵌入模型后，Agent 能想起意思相近、但用词不同的旧结论。不选就只按文字和耦合关系回忆。笔记只会发给数据级别允许的服务。", "Muted", wrap=True))
        emb_card = Card(padding=14, spacing=4)
        emb_card.setMaximumWidth(680)
        self.embedding = EmbeddingRow(self.raw)
        self.embedding.changed.connect(self._mark_dirty)
        emb_card.lay.addWidget(self.embedding)
        emb_card.lay.addWidget(self.embedding.result)
        self.body.addWidget(emb_card)

    def _render_appearance(self) -> None:
        from codedoctor.desktop import i18n
        from codedoctor.desktop import prefs as ui_prefs

        ui = ui_prefs.load()

        def combo(key, options):
            box = QComboBox()
            for value, text in options:
                box.addItem(text, value)
            box.setCurrentIndex(max(box.findData(ui[key]), 0))
            box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(8)
            box.currentIndexChanged.connect(lambda _=0, k=key, b=box: self.appearance_changed.emit({k: b.currentData()}))
            return box

        def check(key, text):
            box = QCheckBox(text)
            box.setChecked(ui[key])
            box.toggled.connect(lambda v, k=key: self.appearance_changed.emit({k: v}))
            return box

        look = Card(padding=18, spacing=12)
        look.lay.addWidget(label("样子", size=15, bold=True))
        form = QFormLayout()
        form.setSpacing(12)
        form.addRow("强调色", combo("accent", (("amber", "光的琥珀"), ("blue", "天蓝"), ("violet", "紫"), ("green", "绿"), ("rose", "玫瑰"), ("ink", "墨"))))
        form.addRow("字号", combo("font_size", (("small", "小"), ("normal", "中"), ("large", "大"))))
        form.addRow("聊天宽度", combo("chat_width", (("narrow", "窄"), ("normal", "中"), ("wide", "宽"))))
        wall = combo("wallpaper", ui_prefs.WALLPAPERS)
        form.addRow("壁纸", wall)
        look.lay.addLayout(form)
        look.lay.addWidget(check("reduced_motion", "减少动态效果（页面不做入场动画）"))
        look.lay.addWidget(check("figure_motion", "让小人轻轻浮动"))
        replay = QPushButton("播放一次开场动画")
        replay.setObjectName("Ghost")
        replay.clicked.connect(self.replay_welcome.emit)
        look.lay.addWidget(hbox(replay, None))

        use = Card(padding=18, spacing=12)
        use.lay.addWidget(label("用起来", size=15, bold=True))
        form = QFormLayout()
        form.setSpacing(12)
        lang = QComboBox()
        for v, t in i18n.LANGS:
            lang.addItem(t, v)
        lang.setCurrentIndex(max(lang.findData(ui["language"]), 0))

        def language_changed(*_):
            self.appearance_changed.emit({"language": lang.currentData()})
            i18n.set_language(lang.currentData())
            notice(self, i18n.tr("ui_language"), i18n.tr("restart_lang"), kind="info")

        lang.currentIndexChanged.connect(language_changed)
        form.addRow(i18n.tr("ui_language"), lang)
        form.addRow("发送消息", combo("send_key", (("enter", "Enter 发送，Shift+Enter 换行"), ("ctrl_enter", "Ctrl+Enter 发送，Enter 换行"))))
        form.addRow("浏览器搜索", combo("search_engine", (("google", "Google"), ("bing", "必应"))))
        form.addRow("界面颜色", combo("mode", ui_prefs.MODES))
        form.addRow("终端字号", combo("term_font", ui_prefs.TERM_FONTS))
        use.lay.addLayout(form)
        use.lay.addWidget(check("show_times", "在消息下面显示时间"))
        use.lay.addWidget(check("expand_steps", "回答时展开每一步"))
        use.lay.addWidget(check("notify_done", "回答做完时提醒我（窗口不在最前面时）"))
        use.lay.addWidget(check("show_tokens", "在聊天顶部显示 token 用量"))
        look.lay.addStretch(1)
        use.lay.addStretch(1)
        self.body.addWidget(CardGrid([look, use], 340))

    def _render_code(self) -> None:
        card = Card(padding=14, spacing=8)
        self.code = CodeSettings(self.raw)
        self.code.changed.connect(self._mark_dirty)
        card.lay.addWidget(self.code)
        self.body.addWidget(card)
        self.body.addWidget(label("修改都在你的项目文件夹里直接进行。建议先提交 git，这样随时能看到改了什么、也能一键撤回；"
                                  "调查页右侧的“工作区一览”会逐行列出每处改动。", "Faint", wrap=True))

    def _render_computer(self) -> None:
        self.body.addWidget(label("“监督员事前批准”：执行者的每个操作先由它的监督员批准才执行，删除、发送、付款、丢失未保存内容这类"
                                  "不可逆操作还要你本人批准；没有监督员的 Agent 每个操作都问你。鼠标键盘只能进入下面列出的窗口。"
                                  "紧急停止：窗口顶部的按钮、Ctrl+Alt+End、或把鼠标推到屏幕左上角。", "Faint", wrap=True))
        comp_card = Card(padding=14, spacing=8)
        self.computer = ComputerSettings(self.raw)
        self.computer.changed.connect(self._mark_dirty)
        comp_card.lay.addWidget(self.computer)
        self.body.addWidget(comp_card)

    def pending(self) -> dict:
        """For the cluster page: what the settings say vs. what is saved (the window runs self.running_agents)."""
        agents = self.raw["agents"] if self.raw else []
        return {"settings": len(agents), "dirty": self.dirty, "saved": self.saved_agents,
                "no_model": sum(not a.get("model") for a in agents)}

    def _structure_changed(self) -> None:
        """Pairs were added / removed or given a model in the scheduling settings: show the new rows."""
        self.dirty = True
        pos = self.scroll.verticalScrollBar().value()
        self.render()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(pos))

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._update_bar()

    def _update_bar(self) -> None:
        editable = self.raw is not None
        on = editable and self.dirty  # nothing to save: the bar is not there at all
        self.save_btn.setEnabled(on)
        self.revert_btn.setEnabled(on)
        for w in (self.state, self.save_btn, self.revert_btn):
            w.setVisible(on)
        self.state.setText("有未保存的修改。保存后重启 Lumen 生效。" if on else "")

    # --- edits ----------------------------------------------------------------------------

    def edit_endpoint(self, eid: str | None) -> None:
        eps = self.raw["endpoints"]
        existing = next((e for e in eps if e["id"] == eid), None)
        dlg = EndpointDialog(self, copy.deepcopy(existing) if existing else None, {e["id"] for e in eps},
                             self.pending_keys.get(eid, _NOTHING) if eid else _NOTHING)
        if dlg.exec() != QDialog.Accepted:
            return
        self.accept_endpoint(existing, dlg.value(), dlg.typed_key, dlg.drop_key)

    def accept_endpoint(self, existing: dict | None, value: dict, typed_key: str | None, drop_key: bool = False) -> None:
        """Put an edited service into the configuration; its key waits for 保存 like everything else."""
        eps = self.raw["endpoints"]
        if existing:
            eps[eps.index(existing)] = value
            if existing["id"] != value["id"] and existing.get("api_key_keyring"):
                self.pending_keys[existing["id"]] = None  # renamed: the key under the old id goes with the old name
        else:
            eps.append(value)
        if typed_key:
            self.pending_keys[value["id"]] = typed_key
        elif drop_key:
            self.pending_keys[value["id"]] = None
        self.dirty = True
        self.render()

    def drop_key(self, eid: str) -> None:
        if QMessageBox.question(self, "删除密钥", f"删除服务 “{eid}” 保存在 Windows 凭据管理器里的密钥？\n点“保存”后才会真正删除；"
                                "用到它的 Agent 之后会因为没有密钥而停下提示你。") != QMessageBox.Yes:
            return
        self.pending_keys[eid] = None
        self.dirty = True
        self.render()

    def remove_endpoint(self, eid: str) -> None:
        users = [a["id"] for a in self.raw["agents"]
                 if a["endpoint"] == eid or any(f["endpoint"] == eid for f in a.get("fallbacks", []))]
        if users:
            notice(self, "不能删除这个服务", f"还有 {agents_summary(users)} 在用它。先在“Agent 模型”里把它们改到别的服务，再删除。",
                   kind="warning", details=users if len(users) > 6 else None, details_title="在用它的 Agent")
            return
        if QMessageBox.question(self, "删除服务", f"删除服务 “{eid}”？点“保存”后，保存在凭据管理器里的密钥也会一起删除。") != QMessageBox.Yes:
            return
        self.raw["endpoints"] = [e for e in self.raw["endpoints"] if e["id"] != eid]
        self.pending_keys[eid] = None
        self.dirty = True
        self.render()

    def add_pair(self) -> None:
        agents = self.raw["agents"]
        ids = {a["id"] for a in agents}
        n = 1
        while f"worker-{n}" in ids or f"guardian-{n}" in ids:
            n += 1
        tmpl_w = next((a for a in reversed(agents) if a["role"] == "worker"), agents[0])
        tmpl_g = next((a for a in reversed(agents) if a["role"] == "guardian"), tmpl_w)
        w = {"id": f"worker-{n}", "role": "worker", "endpoint": tmpl_w["endpoint"], "model": tmpl_w["model"]}
        g = {"id": f"guardian-{n}", "role": "guardian", "endpoint": tmpl_g["endpoint"], "model": tmpl_g["model"],
             "supervises": f"worker-{n}"}
        for src, dst in ((tmpl_w, w), (tmpl_g, g)):
            for k in ("params", "memory", "context_budget_tokens", "fallbacks"):
                if k in src:
                    dst[k] = copy.deepcopy(src[k])
        agents += [w, g]
        self.dirty = True
        self.render()

    def remove_agent(self, aid: str) -> None:
        agents = self.raw["agents"]
        guards = [a["id"] for a in agents if aid in watched_ids(a)]
        what = f"{aid}" + (f" 和监督它的 {'、'.join(guards)}" if guards else "")
        if QMessageBox.question(self, "移除 Agent", f"移除 {what}？它们的历史记忆会保留。") != QMessageBox.Yes:
            return
        drop = {aid, *guards}
        self.raw["agents"] = [a for a in agents if a["id"] not in drop]
        self.dirty = True
        self.render()

    def revert(self) -> None:
        self.pending_keys.clear()  # typed keys are dropped with everything else
        self.raw = config_mod.load_raw(self.path)
        self.dirty = False
        self.render()

    def save(self) -> bool:
        ids = {e["id"] for e in self.raw["endpoints"]}
        try:
            for row in self.rows:
                row.commit_fallbacks(ids)
        except ValueError as e:
            QMessageBox.warning(self, "备用模型写法有误", str(e))
            return False
        empty = [a["id"] for a in self.raw["agents"] if not a.get("model")]
        if empty:
            QMessageBox.warning(self, "还有 Agent 没选模型", f"有 {len(empty)} 个 Agent 还没有选模型，所以没有保存。\n\n"
                                "在“调度设置”里用“给它们用这个模型”一次选好（已经帮你填了建议），或者在“Agent 模型”里逐个选，"
                                "然后再点保存。")
            self.show_section("schedule")
            return False
        if self.computer is not None:
            try:
                self.computer._launch_list()
            except ValueError as e:
                QMessageBox.warning(self, "允许启动的程序写法有误", str(e))
                return False
            self.computer._apply()
        emb = self.raw.get("memory", {}).get("embedding")
        if emb and not emb.get("model"):
            QMessageBox.warning(self, "请选择嵌入模型", "已选择用于“按意思回忆”的服务，但还没有填写嵌入模型名。不想用可以选“不使用”。")
            return False
        try:
            saved = config_mod.save_raw(self.raw, self.path)
        except Exception as e:
            notice(self, "保存失败", "配置没有保存，文件保持原样。原因：", kind="error", details=[str(e)])
            return False
        problems = []
        for eid, key in self.pending_keys.items():  # keys follow the configuration: written only now
            try:
                if key:
                    secrets.set_key(eid, key)
                else:
                    secrets.delete_key(eid)
            except Exception as e:
                problems.append(f"{eid}：{e}")
        self.pending_keys.clear()
        self.keys_changed.emit()
        if problems:
            notice(self, "密钥没有写进凭据管理器", "配置已保存，但下面这些服务的密钥没能写进 Windows 凭据管理器，请重新填写：",
                   kind="warning", details=problems)
        self.dirty = False
        self.saved_agents = len(saved.agents)
        self.render()  # the Save button is outside the content, so re-rendering here is safe; hints now say "saved"
        self._update_bar()
        self.last_warnings = config_mod.independence_warnings(saved)  # suggestions only; nothing is changed for the user
        choice = notice(self, "已保存", "配置已保存（旧版本备份为 .bak）。重启 Lumen 后，新的服务、Agent 和模型才会生效。",
                        kind="ok", details=self.last_warnings or None,
                        details_title=f"{len(self.last_warnings)} 条建议（不影响运行）" if self.last_warnings else "",
                        buttons=("立即重启", "稍后"))
        if choice == "立即重启":
            self.restart_requested.emit()
        return True
