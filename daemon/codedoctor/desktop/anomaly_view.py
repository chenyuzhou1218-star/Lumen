"""Anomalies, head decisions, the detail checklist and the heads' five states in the desktop (ADR 0014).

Read only: decisions are the logic head's (through its tools); nothing here changes a record. Every panel is
rebuilt only when what it shows changed, so the 1-second refresh of the task page stays cheap.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from codedoctor.agents.anomalies import (CHECK_CN, DECISIONS, KINDS, PHASE_HINT, PHASES, QUADRANT, REASONING_CN, SIZE_CN,
                                         STATUS_CN)
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import Card, Chip, Collapsible, hbox, label, vbox

SOFT = "rgba(255,255,255,105)"  # the quiet boxes of the design: lighter glass inside a glass card
STATUS_STYLE = {"new": (C["red"], C["red_soft"]), "fix_now": (C["red"], C["red_soft"]), "expand": (C["blue"], C["blue_soft"]),
                "backlog": (C["text2"], C["gray_soft"]), "confirm": (C["amber"], C["amber_soft"]),
                "resolved": (C["green"], C["green_soft"])}
PHASE_ICON = {"listening": "((•))", "reviewing": "▤", "reflecting": "✦", "commanding": "⇄", "delivery": "✓"}


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


def soft_box(*widgets, spacing: int = 4, padding: int = 12, border: str | None = None) -> QFrame:
    f = QFrame()
    f.setObjectName("SoftBox")
    line = f"1.5px solid {border}" if border else "none"
    if not border:
        line = "1px solid rgba(255,255,255,150)"
    f.setStyleSheet(f"#SoftBox {{ background: {SOFT if not border else 'rgba(255,255,255,200)'}; border: {line}; "
                    f"border-radius: 12px; }}")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(padding, padding - 2, padding, padding - 2)
    lay.setSpacing(spacing)
    for w in widgets:
        if w is not None:
            lay.addWidget(w)
    return f


def center(text: str, name: str | None = None, **kw):
    lb = label(text, name, **kw)
    lb.setAlignment(Qt.AlignHCenter)
    return lb


# --- the heads' five states ---------------------------------------------------------------------

class HeadPhaseStrip(QWidget):
    """监听待命 / 审核报告 / 主动反思 / 下达指令 / 交付审查 for one head, the current one highlighted."""

    def __init__(self, title: str):
        super().__init__()
        self.phase = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(label(title, size=13, bold=True))
        grid = QGridLayout()
        grid.setSpacing(8)
        self.pills: dict[str, QFrame] = {}
        for i, (key, text) in enumerate(PHASES.items()):
            pill = QFrame()
            pill.setObjectName("Pill")
            pl = QHBoxLayout(pill)
            pl.setContentsMargins(12, 9, 12, 9)
            pl.setSpacing(8)
            pl.addWidget(label(PHASE_ICON[key], size=13, color=C["blue"]))
            pl.addWidget(label(text, size=13), 1)
            self.pills[key] = pill
            grid.addWidget(pill, i // 2, i % 2)
        lay.addLayout(grid)
        self.hint_title = label("", size=13, bold=True)
        self.hint = label("", "Faint", wrap=True)
        lay.addWidget(soft_box(self.hint_title, self.hint))
        self.set_phase("listening")

    def set_phase(self, phase: str | None) -> None:
        phase = phase or "listening"
        if phase == self.phase:
            return
        self.phase = phase
        for key, pill in self.pills.items():
            on = key == phase
            pill.setStyleSheet(f"#Pill {{ background: {'rgba(255,255,255,215)' if on else SOFT}; border: 1px solid "
                               f"{C['border_strong'] if on else C['border']}; border-radius: 12px; }}")
        self.hint_title.setText(f"{PHASE_ICON[phase]}  {PHASES[phase]}")
        self.hint.setText(PHASE_HINT[phase])


# --- impact depth -------------------------------------------------------------------------------

class ImpactMatrix(QWidget):
    """Surface size x coupling impact -> handling, with how many decided anomalies are in each cell."""

    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(6)
        for col, text in enumerate(("表面表现", "潜在耦合影响", "处理方式", "数量")):
            self.grid.addWidget(label(text, size=12, bold=True, color=C["text2"]), 0, col)
        self.counts = {}
        for row, (key, (handling, prio)) in enumerate(sorted(QUADRANT.items(), key=lambda kv: (kv[0][0] == "large", kv[0][1] == "large")), 1):
            surface, impact = key
            self.grid.addWidget(label(SIZE_CN[surface], size=13), row, 0)
            self.grid.addWidget(label(SIZE_CN[impact], size=13), row, 1)
            self.grid.addWidget(label(handling, size=13, color=C["red"] if prio == 0 else None), row, 2)
            n = label("0", size=13, color=C["text2"])
            self.counts[key] = n
            self.grid.addWidget(n, row, 3)
        self.grid.setColumnStretch(2, 1)

    def set_counts(self, anomalies: list[dict]) -> None:
        tally = {k: 0 for k in self.counts}
        for a in anomalies:
            d = a.get("decision")
            if d:
                tally[(a["surface"], d["coupling_impact"])] += 1
        for k, lb in self.counts.items():
            lb.setText(str(tally[k]))


# --- anomaly inbox ------------------------------------------------------------------------------

def anomaly_row(a: dict) -> QWidget:
    d = a.get("decision") or {}
    fg, bg = STATUS_STYLE.get(a["status"], (C["text2"], C["gray_soft"]))
    chips = [Chip(STATUS_CN[a["status"]], fg, bg), Chip(KINDS.get(a["kind"], a["kind"]), C["text2"], C["gray_soft"])]
    if a["urgent"]:
        chips.append(Chip("重大", C["red"], C["red_soft"]))
    if a["hypothesis"]:
        chips.append(Chip("假设，待验证", C["amber"], C["amber_soft"]))
    if len(a["occurrences"]) > 1:
        chips.append(Chip(f"出现 {len(a['occurrences'])} 次", C["text2"], C["gray_soft"]))
    head = hbox(*chips, label(a["title"], size=13, bold=True), None, spacing=6)
    sub = (f"表面 {SIZE_CN[a['surface']]} · " + (f"耦合影响 {SIZE_CN[d['coupling_impact']]} → {d['handling']}（P{d['priority']}）"
                                                if d else "等待逻辑首脑决策") + f" · 上报：{a['reported_by']}")
    body = vbox(spacing=4)
    bl = body.layout()
    bl.addWidget(label(f"观察到：{a['observed']}", wrap=True, selectable=True, size=13))
    if a["where"]:
        bl.addWidget(label("位置：" + "，".join(a["where"]), "Faint", wrap=True, selectable=True))
    if a["evidence"]:
        bl.addWidget(label("证据：" + "，".join(a["evidence"][:12]), "Faint", wrap=True, selectable=True))
    if a.get("origin_worker"):
        bl.addWidget(label(f"来自 {a['origin_worker']} 的工作：复核必须交给另一个执行者", "Faint", wrap=True))
    if d:
        bl.addWidget(label(f"首脑决策：{DECISIONS[d['decision']]}（{d['by']}）——{d['rationale']}", wrap=True, selectable=True, size=13))
        for k, v in d["reasoning"].items():
            bl.addWidget(label(f"· {REASONING_CN.get(k, k)}：{v}", "Faint", wrap=True, selectable=True))
        basis = d["basis"]
        if basis["evidence"] or basis["hypothesis"]:
            bl.addWidget(label("影响依据：" + ("，".join(basis["evidence"]) if basis["evidence"] else
                                          f"假设“{basis['hypothesis']}”，证伪方法：{basis['falsification']}"),
                               "Faint", wrap=True, selectable=True))
    if a.get("links"):
        bl.addWidget(label("后续任务：" + "，".join(f"{l['task_id']}（{l['agent']}）" for l in a["links"]), "Faint", wrap=True,
                           selectable=True))
    if a.get("resolution"):
        r = a["resolution"]
        bl.addWidget(label(("确认是预期行为：" if r["by_design"] else "已解决：") + r["note"]
                           + (f"（依据结论 {', '.join(r['claims'])}）" if r["claims"] else ""), wrap=True, selectable=True,
                           size=13, color=C["green"]))
    if a.get("recurrences"):
        bl.addWidget(label(f"之后在类似位置又出现 {len(a['recurrences'])} 次，已要求首脑重新评估是否有共同根因。", wrap=True,
                           size=12, color=C["amber"]))
    bl.addWidget(label(f"{a['id']} · 记录永不删除", "Faint", selectable=True))
    return soft_box(Collapsible(vbox(head, label(sub, "Faint", wrap=True), spacing=3), body, expanded=False), padding=10)


class AnomalyPanel(Card):
    """The anomaly inbox of one investigation (task page) or of the whole project (cluster page)."""

    def __init__(self, title: str = "异常与首脑决策"):
        super().__init__(padding=16, spacing=10)
        self.title = title
        self.sig = None
        self.body = vbox(spacing=8)
        self.lay.addWidget(self.body)

    def update_from(self, anomalies: list[dict]) -> bool:
        sig = json.dumps([(a["id"], a["updated_at"]) for a in anomalies])
        self.setVisible(bool(anomalies))
        if sig == self.sig:
            return False
        self.sig = sig
        lay = self.body.layout()
        _clear(lay)
        by: dict[str, int] = {}
        for a in anomalies:
            by[a["status"]] = by.get(a["status"], 0) + 1
        chips = [Chip(f"{STATUS_CN[k]} {v}", *STATUS_STYLE[k]) for k, v in sorted(by.items(), key=lambda kv: list(STATUS_CN).index(kv[0]))]
        lay.addWidget(hbox(label(self.title, size=14, bold=True), None, *chips, spacing=6))
        lay.addWidget(label("零遗漏：Agent 发现的任何异常（哪怕少一个像素）都会写进首脑的收件箱；重大的立即唤醒首脑，"
                            "细小的保证进入下一轮审阅；重复出现的合并为同一条，但每次的证据都保留。", "Faint", wrap=True))
        order = {"new": 0, "fix_now": 1, "expand": 2, "confirm": 3, "backlog": 4, "resolved": 5}
        for a in sorted(anomalies, key=lambda a: (order[a["status"]], (a.get("decision") or {}).get("priority", 9), not a["urgent"]))[:60]:
            lay.addWidget(anomaly_row(a))
        if len(anomalies) > 60:
            lay.addWidget(label(f"另有 {len(anomalies) - 60} 条（已解决或已延后）没有显示。", "Faint"))
        matrix = ImpactMatrix()
        matrix.set_counts(anomalies)
        lay.addWidget(Collapsible(label("异常影响深度（表面表现 × 潜在耦合影响，由程序换算处理方式）", size=12, color=C["text2"]),
                                  vbox(matrix, label("“潜在影响大”必须有证据，或者有明确的待验证假设和证伪方法，"
                                                     "不能因为 AI 想象出复杂故事就无限消耗 token。", "Faint", wrap=True)),
                                  expanded=False))
        return True


# --- detail checklist ---------------------------------------------------------------------------

class ChecklistPanel(Card):
    """细节审查清单: status computed from supported claims, never ticked by an agent's say-so."""

    def __init__(self):
        super().__init__(padding=16, spacing=8)
        self.sig = None
        self.body = vbox(spacing=6)
        self.lay.addWidget(self.body)

    def update_from(self, items: list[dict]) -> bool:
        sig = json.dumps([(i["id"], i["status"], i["title"]) for i in items])
        self.setVisible(bool(items))
        if sig == self.sig:
            return False
        self.sig = sig
        lay = self.body.layout()
        _clear(lay)
        done = sum(i["status"] == "confirmed" for i in items)
        counted = sum(i["status"] != "not_applicable" for i in items)
        lay.addWidget(hbox(label("细节审查清单", size=14, bold=True), None,
                           label(f"{done} / {counted} 项已完成", size=13, color=C["text2"])))
        bar = QProgressBar()
        bar.setRange(0, max(counted, 1))
        bar.setValue(done)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setStyleSheet(f"QProgressBar {{ background: {C['gray_soft']}; border: none; border-radius: 3px; }}"
                          f"QProgressBar::chunk {{ background: {C['green']}; border-radius: 3px; }}")
        lay.addWidget(bar)
        for i in items:
            mark, color = {"confirmed": ("☑", C["green"]), "not_applicable": ("⊘", C["text3"]),
                           "pending": ("◐", C["amber"])}.get(i["status"], ("☐", C["text2"]))
            sub = CHECK_CN[i["status"]]
            if i["status"] == "not_applicable":
                sub += "：" + i["not_applicable"]["reason"]
            elif i["supported"]:
                sub += "（结论 " + "，".join(i["supported"][:4]) + "）"
            elif i["claims"]:
                sub += "（结论 " + "，".join(i["claims"][:4]) + " 还没被监督者确认）"
            lay.addWidget(hbox(label(mark, size=16, color=color), label(i["title"], size=13), None,
                               label(sub, "Faint", selectable=True), spacing=8))
        if any(i["status"] in ("open", "pending") for i in items):
            lay.addWidget(label("仍有未完成的检查项目", size=13, bold=True, color=C["red"]))
        lay.addWidget(label("完成状态由证据自动确认：只有经过监督者独立复查、状态为“成立”的结论才能勾选，AI 自己说完成不算。",
                            "Faint", wrap=True))
        return True
