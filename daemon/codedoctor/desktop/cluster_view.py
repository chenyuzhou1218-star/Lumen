"""Business investigations and continuous foresight in the desktop (ADR 0010 backend, ADR 0011 UI).

Read only: nothing here approves a business rule, runs an experiment or changes a model. The panel
shows what the backend decided (delivery allowed or blocked, and why) from the same calls the
HTTP read routes use, and keeps the backend's limits in view: results hold only inside the
declared controlled scenarios, a structural lead is not a cause, and runtime trace coverage is
not claimed.
"""

from __future__ import annotations

import json
import time

from PySide6.QtWidgets import QVBoxLayout, QWidget

from codedoctor.cluster.contracts import BusinessError
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import Card, Chip, Collapsible, hbox, label, vbox
from codedoctor.ui_text import CHECK_CN, HYPOTHESIS_CN, PURPOSE_CN, SIGNATURE_CN, blocking_cn

_HYPO_COLOR = {"refuted_in_declared_scope": (C["text2"], C["gray_soft"]), "compatible_not_proven": (C["green"], C["green_soft"]),
               "untested": (C["amber"], C["amber_soft"])}


def investigation_for(daemon, task_id: str) -> tuple[dict, dict] | None:
    """(frozen investigation document, current status) for a root task, or None when it has no investigation."""
    inv = daemon.s.investigations.for_root(task_id)
    if inv is None:
        return None
    try:
        return daemon.s.investigations.get(inv), daemon.s.investigations.status(inv)
    except BusinessError:
        return None


class InvestigationPanel(Card):
    """The evidence-gated business investigation of one root task. Rebuilt only when its status changes."""

    def __init__(self):
        super().__init__(padding=16, spacing=8)
        self.sig = None
        self.body = vbox(spacing=8)
        self.lay.addWidget(self.body)

    def update_from(self, doc: dict, status: dict) -> bool:
        """Show this status; returns True when the panel was rebuilt."""
        sig = json.dumps(status, sort_keys=True, ensure_ascii=False)
        self.setVisible(True)
        if sig == self.sig:
            return False
        self.sig = sig
        lay = self.body.layout()
        while lay.count():
            lay.takeAt(0).widget().deleteLater()
        plan = doc["plan"]
        ok = status["delivery_allowed"]
        lay.addWidget(hbox(label("业务实验调查", size=13, bold=True, color=C["text2"]),
                           Chip("可以交付" if ok else "交付被阻止", C["green"] if ok else C["red"],
                                C["green_soft"] if ok else C["red_soft"]), None, label(status["id"], "Faint", selectable=True)))
        lay.addWidget(label("结论只在已声明的受控实验场景内成立，不是普遍的因果证明；本调查没有声明运行时追踪覆盖。"
                            "结构上的共同上游只是线索，不是已确认的原因。", "Faint", wrap=True))
        if plan.get("symptoms"):
            lay.addWidget(label("症状：" + "；".join(plan["symptoms"]), wrap=True, selectable=True, size=13))

        if status["blocking_reasons"]:
            reasons = vbox(*[label(f"• {blocking_cn(r)}", wrap=True, selectable=True, size=13, color=C["red"])
                             for r in status["blocking_reasons"]], spacing=2)
            lay.addWidget(vbox(label("为什么还不能交付", size=13, bold=True), reasons, spacing=4))

        hyps = vbox(spacing=6)
        for h in status["hypothesis_ledger"]:
            fg, bg = _HYPO_COLOR.get(h["state"], (C["text2"], C["gray_soft"]))
            detail = []
            for kind, items in (("支持", h["support"]), ("反驳", h["refutations"])):
                for s in items:
                    detail.append(f"{kind}：检查 {s['check']} 预测“{SIGNATURE_CN.get(s['predicted'], s['predicted'])}”，"
                                  f"实际“{SIGNATURE_CN.get(s['observed'], s['observed'])}”（{len(s['evidence'])} 条原始记录）")
            hyps.layout().addWidget(vbox(
                hbox(Chip(HYPOTHESIS_CN.get(h["state"], h["state"]), fg, bg), label(h["id"], size=13, bold=True), None),
                label(h["statement"], wrap=True, selectable=True, size=13),
                label(f"候选位置：{h['candidate']}", "Faint", wrap=True, selectable=True),
                *[label(d, "Faint", wrap=True) for d in detail], spacing=2))
        compatible = status["compatible_hypotheses"]
        lay.addWidget(vbox(label(f"假设（{len(status['hypothesis_ledger'])} 个，与观察相符的 {len(compatible)} 个）",
                                 size=13, bold=True), hyps, spacing=4))

        checks = vbox(spacing=4)
        predictions = {c["id"]: c for c in plan["checks"]}
        for c in status["checks"]:
            observed = SIGNATURE_CN.get(c["observed"], "还没有结果") if c["observed"] else "还没有结果"
            scenario = predictions.get(c["id"], {}).get("scenario", "")
            checks.layout().addWidget(label(
                f"• {c['id']}（{PURPOSE_CN.get(c['purpose'], c['purpose'])}，场景 {scenario}）：{CHECK_CN.get(c['state'], c['state'])}"
                f" · {observed}", wrap=True, size=13))
        lay.addWidget(vbox(label("实验检查（每项都要基线、故障、恢复三阶段，执行者和监督者各独立跑一遍）", size=13, bold=True),
                           checks, spacing=4))
        if status.get("next_check"):
            pairs = status["next_check_distinguishes_pairs"]
            lay.addWidget(label(f"下一项最能区分假设的检查：{status['next_check']}（能区分 {pairs} 对假设）" if pairs else
                                f"下一项待做的检查：{status['next_check']}（不用于区分假设）", size=13, color=C["blue"]))
        if status.get("structural_analysis_truncated"):
            lay.addWidget(label("注意：结构分析达到上限被截断，没列出的路径不代表不存在。", size=13, color=C["amber"], wrap=True))

        ev = status["evidence"]
        ev_body = label("\n".join(ev) if ev else "（还没有）", "Faint", wrap=True, selectable=True)
        ev_head = hbox(label(f"原始实验记录 {len(ev)} 条 · 代码版本 {status['code_version'][:19]}…", size=12, color=C["text2"]), None)
        lay.addWidget(Collapsible(ev_head, ev_body, expanded=False))
        return True


class ClusterInfo(QWidget):
    """Continuous foresight, registered experiments, approved business rules and safety limits (Agent 集群 page)."""

    def __init__(self, daemon):
        super().__init__()
        self.d = daemon
        self.sig = None
        self.box = vbox(spacing=12)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.box)
        self._at = 0.0

    def refresh(self, force: bool = False) -> None:
        if not force and time.time() - self._at < 3:
            return
        self._at = time.time()
        d = self.d
        fs = d.foresight.status()
        scenarios = sorted(d.s.investigations.registry.scenarios)
        contracts = [json.loads(r["doc"]) for r in d.s.db.query("SELECT doc FROM cluster_contracts ORDER BY id")]
        sig = json.dumps([fs, scenarios, contracts], sort_keys=True, default=str, ensure_ascii=False)
        if sig == self.sig:
            return
        self.sig = sig
        lay = self.box.layout()
        while lay.count():
            lay.takeAt(0).widget().deleteLater()

        agents = len(d.config.agents)
        card = Card(padding=16, spacing=6)
        card.lay.addWidget(hbox(label("持续推演（空闲时两个首脑推想未来可能出的 Bug）", size=14, bold=True), None,
                                Chip("已开启" if fs["enabled"] else "未开启", C["green"] if fs["enabled"] else C["text2"],
                                     C["green_soft"] if fs["enabled"] else C["gray_soft"])))
        card.lay.addWidget(label(
            f"集群规模：已配置 {agents} 个 Agent，上限 {fs['max_agents']}（硬上限 {fs['hard_ceiling']}，首脑和监督者都算在内）。"
            "调高上限不会自动创建 Agent，也不会替你选模型。" +
            ("" if fs["enabled"] else "要开启，在项目配置里设置 [cluster] enabled 和 foresight；开启后没有任务时也会按你设的频率和预算调用模型。"),
            "Faint", wrap=True))
        cycles = fs["recent_cycles"]
        if cycles:
            card.lay.addWidget(label("最近的推演：", size=13))
            for c in cycles[:8]:
                when = time.strftime("%m-%d %H:%M", time.localtime(c["scheduled_at"]))
                card.lay.addWidget(label(f"• {when}  {c['agent']}  预留 {c['reserved']:,} token  任务 {c['task_id']}", "Faint",
                                         selectable=True))
        lay.addWidget(card)

        card = Card(padding=16, spacing=6)
        card.lay.addWidget(label("业务实验", size=14, bold=True))
        card.lay.addWidget(label("已注册的实验场景：" + ("、".join(scenarios) if scenarios else
                                                     "没有（实验场景需要由应用显式注册；只打开一个项目不会导入或执行它的代码）"),
                                 wrap=True, size=13))
        if contracts:
            card.lay.addWidget(label(f"你已批准的业务规则（{len(contracts)} 条，只能由你批准，Agent 无权批准）：", size=13))
            for c in contracts:
                card.lay.addWidget(label(f"• {c['contract']['id']}：{c['contract']['description']}", wrap=True, selectable=True, size=13))
        else:
            card.lay.addWidget(label("还没有批准任何业务规则（例如“同一订单不能重复扣款”）。业务规则只能由你批准，Agent 无权批准。",
                                     "Faint", wrap=True))
        card.lay.addWidget(label("安全边界：首脑只能规划和调度，不能执行命令或实验；执行者和监督者各自独立运行实验；"
                                 "实验在本进程内运行受信任的场景代码，超时和取消是协作式的，不是强制隔离。",
                                 "Faint", wrap=True))
        lay.addWidget(card)

