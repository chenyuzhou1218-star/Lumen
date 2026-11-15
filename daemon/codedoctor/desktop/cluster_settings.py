"""调度设置 → 选择协作方式 (ADR 0015): the four collaboration modes of ChatGPT's studio build - 单人助手 /
双人互检 / 协作小队 / 双首脑集群 - drawn as glass cards, a total-size slider, on-demand parallel pairs, continuous
monitoring with its limits, a one-step way to give new agents a model, and an honest view of context and memory.

Edits only the raw configuration the page saves (codedoctor.topology.draft); nothing takes effect before the user
saves and restarts. New agents get NO model: every model stays the user's choice (the batch row is the user
choosing for many at once).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from codedoctor import topology
from codedoctor.desktop.anomaly_view import soft_box
from codedoctor.desktop.liquid import LiquidSlider
from codedoctor.desktop.theme import C, ROLE_COLOR
from codedoctor.desktop.widgets import Collapsible, hbox, label

WORKER_ROLES = ("worker", "investigator")
ORDER = ("basic", "dual", "small", "advanced")
SIZE_TEXT = {"basic": "1 个 Agent", "dual": "2 个 Agent", "small": "5–38 个 Agent", "advanced": "4–40 个 Agent"}
COMPARE = [
    ("谁接你的任务", "单 Agent", "执行者", "调度首脑", "调度首脑"),
    ("复查", "自己核对证据", "监督者复查每条结论", "监督者复查（1 个看 2 个执行者）", "每个执行者有专属监督者"),
    ("拆分与并行", "不拆分", "不拆分", "首脑拆分，多个执行者并行", "首脑拆分，最多 19 个执行者并行"),
    ("异常决策", "自己决策", "执行者自己决策", "逻辑首脑决策", "逻辑首脑决策"),
    ("细节审查清单", "—", "—", "有", "有"),
    ("持续监控", "—", "—", "可开启", "可开启"),
    ("成本", "最低", "约 2 倍", "中等", "最高"),
    ("适合", "单个 Bug、快速检查", "要有人复核的问题", "跨几个模块的问题", "系统级耦合与因果"),
]


class FormationGlyph(QWidget):
    """A tiny diagram of a mode: heads on top, executors (green) over their supervisors (amber)."""

    def __init__(self, mode: str):
        super().__init__()
        self.mode = mode
        self.setFixedHeight(54)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        dot = lambda x, y, role, r=6: (p.setPen(Qt.NoPen), p.setBrush(QColor(ROLE_COLOR[role])),  # noqa: E731
                                       p.drawEllipse(QPointF(x, y), r, r))
        line = QPen(QColor(120, 140, 170, 110), 1.2)

        def link(a, b):
            p.setPen(line)
            p.drawLine(QPointF(*a), QPointF(*b))

        cx = w / 2
        if self.mode == "basic":
            dot(cx, h / 2, "general", 9)
        elif self.mode == "dual":
            link((cx - 16, h / 2), (cx + 16, h / 2))
            dot(cx - 16, h / 2, "worker", 8)
            dot(cx + 16, h / 2, "guardian", 8)
        else:
            heads = [(cx - 14, 10), (cx + 14, 10)]
            groups = 2 if self.mode == "small" else 4
            per = 2 if self.mode == "small" else 1
            span = min(w - 24, 34 * groups * per)
            xs = [cx - span / 2 + span * (i + 0.5) / (groups * per) for i in range(groups * per)]
            for i in range(groups):
                ws = xs[i * per:(i + 1) * per]
                gx = sum(ws) / len(ws)
                for x in ws:
                    link(heads[0] if x < cx else heads[1], (x, 30))
                    link((x, 30), (gx, 46))
            link(heads[0], heads[1])
            for x, y in heads:
                dot(x, y, "head_logic" if x < cx else "head_dispatch", 6)
            for i in range(groups):
                ws = xs[i * per:(i + 1) * per]
                for x in ws:
                    dot(x, 30, "worker", 4.5)
                dot(sum(ws) / len(ws), 46, "guardian", 4.5)
        p.end()


class ModeCard(QFrame):
    """One collaboration mode; click to choose it."""
    picked = Signal(str)

    def __init__(self, mode: str, title: str | None = None, desc: str | None = None, size_text: str | None = None):
        """title / desc / size_text: translated texts (the setup wizard); default the Chinese ones."""
        super().__init__()
        self.mode = mode
        self._checked = False
        self._hover = False
        self.setObjectName("ModeCard")
        self.setCursor(Qt.PointingHandCursor)
        title, desc = title or topology.MODES[mode][0], desc or topology.MODES[mode][1]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        lay.addWidget(FormationGlyph(mode))
        lay.addWidget(label(title, size=15, bold=True, color=C["ink"]))
        lay.addWidget(label(size_text or SIZE_TEXT[mode], size=12, color=C["accent_hover"]))
        d = label(desc, size=12, color=C["text2"], wrap=True)
        lay.addWidget(d, 1)
        self._style()

    def isChecked(self) -> bool:  # noqa: N802 (Qt naming, like a button)
        return self._checked

    def setChecked(self, on: bool) -> None:  # noqa: N802
        self._checked = on
        self._style()

    def click(self) -> None:
        self.picked.emit(self.mode)

    def _style(self) -> None:
        if self._checked:
            css = "background: rgba(255,255,255,225); border: 1.5px solid rgba(58,107,168,170);"
        elif self._hover:
            css = "background: rgba(255,255,255,175); border: 1px solid rgba(255,255,255,235);"
        else:
            css = "background: rgba(255,255,255,105); border: 1px solid rgba(255,255,255,170);"
        self.setStyleSheet(f"#ModeCard {{ {css} border-radius: 16px; }}")

    def enterEvent(self, e):
        self._hover = True
        self._style()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._style()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.picked.emit(self.mode)
        super().mouseReleaseEvent(e)


class ClusterSettings(QWidget):
    changed = Signal()            # raw configuration edited
    structure_changed = Signal()  # agents added / removed / given a model: the page re-renders its rows

    def __init__(self, raw: dict, running: int | None = None, saved: int | None = None):
        """running: how many agents the open window runs now; saved: how many the saved configuration has
        (changes take effect after save + restart)."""
        super().__init__()
        self.raw = raw
        self.running = running
        self.saved = saved
        self.edited = False
        mode, count = topology.current(raw)
        cl = raw.get("cluster", {})
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(label("选择协作方式", size=24, bold=True, color=C["ink"]))
        lay.addWidget(label("同一个问题可以交给一个 Agent，也可以交给一整支队伍。模型始终由你来选；没有任务的 Agent 不调用模型。",
                            size=13, color=C["text2"], wrap=True))
        if raw.get("permissions", {}).get("write_files"):  # ADR 0016: a measured hint, never an automatic switch
            tip = label("改代码时的实测参考（3 个测试仓库共 37 个耦合 bug，DeepSeek Flash）：双首脑集群 6 人修好 36 个，"
                        "共约 194 万 token；双人互检修好 36 个，约 217 万；20 人修好 35 个，约 454 万。小项目推荐 6 人："
                        "一组主力修全部代码，一组侦察兵按业务场景写测试、查出的问题再由它补位修好。20 人适合模块多、"
                        "彼此独立的大项目。", size=12, color=C["text2"], wrap=True)
            tip.setStyleSheet(f"background: rgba(255,255,255,140); border-radius: 10px; padding: 8px 12px; color: {C['text2']};")
            lay.addWidget(tip)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.mode_btns: dict[str, ModeCard] = {}
        for i, key in enumerate(ORDER):
            card = ModeCard(key)
            card.picked.connect(self._pick_mode)
            self.mode_btns[key] = card
            cards.addWidget(card, 0, i)
            cards.setColumnStretch(i, 1)
        self.mode_btns.get(mode, self.mode_btns["advanced"]).setChecked(True)
        lay.addLayout(cards)

        # size
        self.size_box = QWidget()
        sl = QVBoxLayout(self.size_box)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(6)
        self.count_label = label("", size=26, bold=True, color=C["ink"])
        sl.addWidget(hbox(label("总人数（含首脑和监督者）", size=13, color=C["text2"]), None, self.count_label))
        self.slider = LiquidSlider()
        self.slider.setPageStep(1)
        sl.addWidget(self.slider)
        self.summary = label("", size=13, color=C["text"])
        sl.addWidget(self.summary)
        lay.addWidget(self.size_box)

        # options of the multi-agent modes
        self.opts = QWidget()
        ol = QVBoxLayout(self.opts)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(8)
        self.parallel = QCheckBox("按需并行：首脑把任务拆开后，多个执行者同时工作；任务结束立即释放（空闲的 Agent 不调用模型）")
        self.parallel.setChecked(cl.get("parallel", True) and cl.get("mode") != "collab")
        fs = cl.get("foresight", {})
        self.foresight = QCheckBox("持续监控与主动发现问题：空闲时两个首脑推演未来可能出的 Bug（会按下面的频率和预算调用模型）")
        self.foresight.setChecked(fs.get("enabled", False))
        ol.addWidget(self.parallel)
        ol.addWidget(self.foresight)
        form = QFormLayout()
        form.setSpacing(8)
        self.interval = QDoubleSpinBox()
        self.interval.setRange(5, 86400)
        self.interval.setSuffix(" 秒")
        self.interval.setValue(fs.get("interval_s", 30))
        self.steps_per = QSpinBox()
        self.steps_per.setRange(1, 100)
        self.steps_per.setValue(fs.get("max_steps_per_cycle", 8))
        self.tokens = QSpinBox()
        self.tokens.setRange(1024, 1_000_000_000)
        self.tokens.setSingleStep(1000)
        self.tokens.setValue(fs.get("max_tokens_per_cycle", 20000))
        self.hourly = QSpinBox()
        self.hourly.setRange(2048, 2_000_000_000)
        self.hourly.setSingleStep(10000)
        self.hourly.setValue(fs.get("reserved_tokens_per_hour", 1000000))
        form.addRow("推演间隔", self.interval)
        form.addRow("每轮最多步骤", self.steps_per)
        form.addRow("每轮 token 上限", self.tokens)
        form.addRow("每小时 token 上限", self.hourly)
        fw = QWidget()
        fw.setLayout(form)
        ol.addWidget(Collapsible(label("持续监控的频率和预算", size=13, color=C["text2"]), fw, expanded=False))
        ol.addWidget(label("实际最大并发由你的 API 限额、本机资源和任务之间的依赖决定。持续监控需要 Lumen 保持运行。"
                           "减少人数会从配置里移除编号最大的几个（它们的历史记忆会保留）。", "Faint", wrap=True))
        lay.addWidget(self.opts)

        # what happens next / new agents without a model
        self.steps = label("", wrap=True, size=13, color=C["amber"])
        self.steps_box = soft_box(self.steps, padding=12)
        lay.addWidget(self.steps_box)
        self.batch = QWidget()
        bl = QHBoxLayout(self.batch)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)
        self.batch_note = label("", size=13, color=C["red"], wrap=True)
        self.batch_scope = QComboBox()
        for v, t in (("all", "所有还没选模型的 Agent"), ("worker", "还没选模型的执行者"), ("guardian", "还没选模型的监督者"),
                     ("head", "还没选模型的首脑"), ("general", "还没选模型的单 Agent")):
            self.batch_scope.addItem(t, v)
        self.batch_ep = QComboBox()
        for e in raw["endpoints"]:
            self.batch_ep.addItem(e.get("name") or e["id"], e["id"])
        self.batch_model = QComboBox()
        self.batch_model.setEditable(True)
        self.batch_model.setMinimumWidth(180)
        self.batch_model.lineEdit().setPlaceholderText("模型名")
        self.apply_btn = QPushButton("给它们用这个模型")
        self.apply_btn.setObjectName("Primary")
        for w in (self.batch_scope, self.batch_ep):
            bl.addWidget(w)
        bl.addWidget(self.batch_model, 1)
        bl.addWidget(self.apply_btn)
        self.batch_hint = label("", "Faint", wrap=True)
        self.batch_wrap = soft_box(self.batch_note, self.batch, self.batch_hint, spacing=6, padding=12)
        lay.addWidget(self.batch_wrap)

        # comparison
        table = QGridLayout()
        table.setHorizontalSpacing(16)
        table.setVerticalSpacing(7)
        for c, t in enumerate(("", *(topology.MODES[k][0] for k in ORDER))):
            table.addWidget(label(t, size=12, bold=True, color=C["text2"]), 0, c)
        for r, row in enumerate(COMPARE, 1):
            for c, t in enumerate(row):
                table.addWidget(label(t, size=12, wrap=True, color=C["text2"] if c == 0 else None), r, c)
        for c in range(1, 5):
            table.setColumnStretch(c, 1)
        tw = QWidget()
        tw.setLayout(table)
        lay.addWidget(Collapsible(label("四种协作方式对比", size=13, color=C["text2"]), tw, expanded=False))

        self._load_slider(mode, count)
        self.slider.valueChanged.connect(self._slider_moved)
        self.slider.sliderReleased.connect(self._slider_released)
        self.parallel.toggled.connect(lambda _: self._apply_options())
        self.foresight.toggled.connect(lambda _: self._apply_options())
        for w in (self.interval, self.steps_per, self.tokens, self.hourly):
            w.valueChanged.connect(lambda _: self._apply_options())
        self.batch_ep.currentIndexChanged.connect(self._fill_batch_models)
        self.apply_btn.clicked.connect(self._apply_batch)
        self._fill_batch_models()
        self._suggest()
        self._show()

    # --- reading ---------------------------------------------------------------------------------

    def mode(self) -> str:
        return next(k for k, b in self.mode_btns.items() if b.isChecked())

    def _sizes(self) -> tuple[int, ...]:
        return topology.sizes(self.mode())

    def _load_slider(self, mode: str, count: int) -> None:
        options = topology.sizes(mode)
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, len(options) - 1))
        self.slider.setValue(options.index(topology.nearest(mode, count)))
        self.slider.blockSignals(False)

    def _count(self) -> int:
        options = self._sizes()
        return options[min(self.slider.value(), len(options) - 1)]

    def _show(self) -> None:
        mode, n = self.mode(), self._count()
        multi = mode in ("small", "advanced")
        self.size_box.setVisible(multi)
        self.opts.setVisible(multi)
        recommended = multi and n == 6 and self.mode() == "advanced" and self.raw.get("permissions", {}).get("write_files")
        self.count_label.setText((f"{n}（推荐）" if recommended else f"{n}") if multi else "")
        singles = sum(a["role"] == "general" for a in self.raw["agents"])
        self.summary.setText(topology.describe(mode, n) + (f"　·　另有单 Agent {singles} 个（不算在集群里）" if singles and multi else ""))
        empty = [a["id"] for a in self.raw["agents"] if not a.get("model")]
        self.batch_wrap.setVisible(bool(empty))
        if empty:
            self.batch_note.setText(f"第 1 步：{len(empty)} 个新加的 Agent 还没有模型。选一个服务和模型，点“给它们用这个模型”"
                                    "一次选好（也可以在“Agent 模型”标签里逐个选）。")
        total = len(self.raw["agents"])
        if self.running is not None and not empty and not self.edited and total == self.saved and total != self.running:
            self.steps.setText(f"已经保存为 {total} 个 Agent，重启 Lumen 后生效（现在运行的是 {self.running} 个）。")
            self.steps_box.setVisible(True)
        elif self.running is not None and (self.edited or empty):
            steps = ([f"① 给新加的 {len(empty)} 个 Agent 选模型（下面一步完成）"] if empty else []) + \
                    ["② 点右下角“保存”" if empty else "① 点右下角“保存”", "③ 重启 Lumen（保存后会问你）" if empty else "② 重启 Lumen（保存后会问你）"]
            self.steps.setText(f"现在运行的是 {self.running} 个 Agent，这里设成了 {total} 个。要让它生效：" + "　".join(steps) + "。")
            self.steps_box.setVisible(True)
        else:
            self.steps_box.setVisible(False)

    def _suggest(self) -> None:
        """Pre-fill the batch picker with the model the existing workers use - a suggestion; the user applies it."""
        used = [a for a in self.raw["agents"] if a.get("model") and a["role"] in WORKER_ROLES] or \
               [a for a in self.raw["agents"] if a.get("model")]
        if not used:
            self.batch_hint.setText("")
            return
        a = used[0]
        i = self.batch_ep.findData(a["endpoint"])
        if i >= 0:
            self.batch_ep.setCurrentIndex(i)
            self._fill_batch_models()
        self.batch_model.setCurrentText(a["model"])
        self.batch_hint.setText(f"已经填好了 {a['id']} 正在用的 {a['endpoint']} / {a['model']} 作为建议，可以改成别的；"
                                "监督者最好选和执行者不同的模型（范围选“还没选模型的监督者”分开设）。")

    def _fill_batch_models(self) -> None:
        e = next((x for x in self.raw["endpoints"] if x["id"] == self.batch_ep.currentData()), {})
        self.batch_model.clear()
        self.batch_model.addItems(e.get("models", []))
        self.batch_model.setCurrentText("")

    # --- editing ---------------------------------------------------------------------------------

    def _foresight(self) -> dict:
        return {"enabled": self.foresight.isChecked(), "interval_s": self.interval.value(),
                "max_steps_per_cycle": self.steps_per.value(), "max_tokens_per_cycle": self.tokens.value(),
                "reserved_tokens_per_hour": max(self.hourly.value(), 2 * self.tokens.value())}

    def _redraft(self, mode: str, count: int) -> None:
        new = topology.draft(self.raw, mode, count, parallel=self.parallel.isChecked(), foresight=self._foresight())
        self.raw.clear()
        self.raw.update(new)  # same dict object: the page saves what was drafted here
        self.edited = True
        self.changed.emit()
        self.structure_changed.emit()

    def _pick_mode(self, mode: str) -> None:
        if mode == self.mode():
            return
        count = topology.nearest(mode, len([a for a in self.raw["agents"] if a["role"] != "general"]))
        for k, b in self.mode_btns.items():
            b.setChecked(k == mode)
        self._load_slider(mode, count)
        self._redraft(mode, count)

    def _slider_moved(self, _value: int) -> None:
        self._show()
        if not self.slider.isSliderDown():  # keyboard: apply at once
            self._slider_released()

    def _slider_released(self) -> None:
        mode, n = self.mode(), self._count()
        if mode not in ("small", "advanced") or n == len([a for a in self.raw["agents"] if a["role"] != "general"]):
            return
        self._redraft(mode, n)

    def _apply_options(self) -> None:
        if self.mode() not in ("small", "advanced"):
            return
        cl = self.raw.setdefault("cluster", {})
        cl["parallel"] = self.parallel.isChecked()
        cl["foresight"] = {**cl.get("foresight", {}), **self._foresight()}
        self.edited = True
        self._show()
        self.changed.emit()

    def _apply_batch(self) -> None:
        eid, model = self.batch_ep.currentData(), self.batch_model.currentText().strip()
        if not eid or not model:
            self.batch_note.setText("先选服务并填写模型名。")
            return
        scope = self.batch_scope.currentData()
        roles = {"worker": WORKER_ROLES, "guardian": ("guardian",), "head": ("head_dispatch", "head_logic"),
                 "general": ("general",)}.get(scope)
        for a in self.raw["agents"]:
            if not a.get("model") and (roles is None or a["role"] in roles):
                a["endpoint"], a["model"] = eid, model
        self.edited = True
        self.changed.emit()
        self.structure_changed.emit()


class ContextInfo(QWidget):
    """What 'context' really is here: a working context per agent (bounded by its model) plus unbounded long-term
    memory on disk. Large token targets are reached through memory and recall, never as one request."""

    def __init__(self, raw: dict):
        super().__init__()
        agents = raw["agents"]
        budget = {a["id"]: a.get("context_budget_tokens", 64000) for a in agents}
        heads = [a for a in agents if a["role"] in ("head_dispatch", "head_logic")]
        others = [a for a in agents if a not in heads]
        total = sum(budget.values())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        grid = QGridLayout()
        grid.setSpacing(10)
        cells = [
            ("每个普通 Agent 的工作上下文", f"{max((budget[a['id']] for a in others), default=0):,}",
             "token，单次请求的上限，要和所选模型的真实上下文一致"),
            ("每个首脑的工作上下文", f"{max((budget[a['id']] for a in heads), default=0):,}",
             "token；首脑另有全局系统模型：所有结论、异常、证据都在共享库里"),
            ("全部 Agent 的工作上下文合计", f"{total:,}", f"token，{len(agents)} 个 Agent 各一份，互不挤占"),
            ("长期记忆与原始证据", "不设上限", "日志、证据、结论、笔记都存在本机；压缩只影响发给模型的内容，原始记录永不丢失"),
        ]
        for i, (title, big, sub) in enumerate(cells):
            grid.addWidget(soft_box(label(title, size=12, color=C["text2"]), label(big, size=24, bold=True),
                                    label(sub, "Faint", wrap=True), spacing=2, padding=14), i // 2, i % 2)
        lay.addLayout(grid)
        lay.addWidget(label("说明：一次发给模型的内容受模型本身限制（常见 64k、128k、1M token）。像 10M、200M 这样的长期上下文，"
                            "靠的是长期记忆、证据库和按需精确召回，而不是一次塞进模型；这样既不会丢细节，也不会每一步都付全部的费用。"
                            "工作上下文在下面每个 Agent 的配置里按模型设置。", "Faint", wrap=True))

