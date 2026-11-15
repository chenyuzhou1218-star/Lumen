"""The chat page: a conversation's earlier turns (question and answer), then the current one - the question, every
step as it happens, any helpers' cards, the answer, the claims - and the reply box. Laid out like ChatGPT."""

from __future__ import annotations

import json
import time

from PySide6.QtCore import QRectF, QSize, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QTextEdit
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from codedoctor.agents import orchestration as orch
from codedoctor.desktop import chat_tools
from codedoctor.desktop import prefs as ui_prefs
from codedoctor.desktop.anomaly_view import AnomalyPanel, ChecklistPanel
from codedoctor.desktop.changes_view import ChangesPanel, collect as collect_changes, verdict as test_verdict
from codedoctor.desktop.cluster_view import InvestigationPanel, investigation_for
from codedoctor.desktop.composer import Banner, Composer
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.computer_view import ActionsPanel
from codedoctor.desktop.theme import C, ROLE_COLOR
from codedoctor.desktop.widgets import (Avatar, Card, Chip, Collapsible, Markdown, PulseDot, Spinner, StepRow, hbox,
                                        label, vbox)
from codedoctor.desktop.workspace_view import WorkspacePanel
from codedoctor.ui_text import (CLAIM_CN, ESCALATION_CN, LEVEL_CN, RESUMABLE, ROLE_CN, TOOL_ICON, VERDICT_CN,
                                describe_tool_call, duration, local_time, parse_ts, task_status)


CHAT_WIDTH = {"narrow": 680, "normal": 840, "wide": 1100}


class PictureCard(QWidget):
    """A picture in a chat, rounded, as wide as the answer and never wider: a fixed width pushed the whole answer past the
    edge of a narrow window. A click opens it."""

    def __init__(self, path, width: int = 640):
        super().__init__()
        self.path, self.most = path, width
        self.source = QPixmap(str(path))
        self.fitted: QPixmap | None = None
        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(str(path))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        if self.source.isNull():
            return 0
        return round(min(width, self.most) * self.source.height() / self.source.width())

    def sizeHint(self) -> QSize:
        return QSize(self.most, self.heightForWidth(self.most))

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self.heightForWidth(120))

    def paintEvent(self, _e):
        if self.source.isNull():
            return
        width = min(self.width(), self.most)
        ratio = self.devicePixelRatioF() or 1
        if self.fitted is None or self.fitted.width() != round(width * ratio):
            self.fitted = self.source.scaledToWidth(round(width * ratio), Qt.SmoothTransformation)
            self.fitted.setDevicePixelRatio(ratio)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, width, self.fitted.height() / ratio), 18, 18)
        p.setClipPath(clip)
        p.drawPixmap(0, 0, self.fitted)
        p.end()

    def mousePressEvent(self, _e):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))


class FindBar(QFrame):
    """Ctrl+F in a chat: a line above it. Enter goes on, Shift+Enter back, Esc closes."""

    def __init__(self):
        super().__init__()
        self.setObjectName("FindBar")
        self.setStyleSheet(f"#FindBar {{ background: white; border-bottom: 1px solid {C['border']}; }}"
                           "QLineEdit { border: none; background: transparent; font-size: 14px; padding: 2px 0; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(28, 7, 16, 7)
        lay.setSpacing(8)
        self.box = QLineEdit()
        self.box.setPlaceholderText("在回答里查找")
        self.box.installEventFilter(self)
        self.count = label("", size=12, color=C["text3"])
        self.back = self._button("上一个")
        self.next = self._button("下一个")
        self.close_btn = self._button("关闭")
        lay.addWidget(self.box, 1)
        for w in (self.count, self.back, self.next, self.close_btn):
            lay.addWidget(w)

    @staticmethod
    def _button(text: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("Ghost")
        b.setCursor(Qt.PointingHandCursor)
        return b

    def eventFilter(self, obj, e):
        if obj is self.box and e.type() == e.Type.KeyPress:
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                (self.back if e.modifiers() & Qt.ShiftModifier else self.next).click()
                return True
            if e.key() == Qt.Key_Escape:
                self.close_btn.click()
                return True
        return super().eventFilter(obj, e)


def _role(daemon, agent_id: str) -> str:
    a = daemon.config.agents.get(agent_id)
    return a.role if a else ("system" if agent_id == "system" else "user")



def _readable_escalation(daemon, body: dict) -> str:
    """An escalation for a person: anomalies by title (the panel below has the rest), other details without the
    long evidence ids that made the banner a wall of text."""
    import re

    detail = body.get("detail") or ""
    if body.get("reason") == "anomaly":
        ids = list(dict.fromkeys(re.findall(r"anm_[0-9A-Z]{26}", detail)))
        titles = []
        for i in ids:
            a = daemon.s.anomalies.get(i)
            if a:
                titles.append(f"· {a['title'][:120]}")
        return (f"有 {len(ids)} 条异常还没有首脑决策，所以结果被拦下：\n" + "\n".join(titles[:12])
                + ("\n…" if len(titles) > 12 else "") + "\n完整内容见下方“异常”面板，或 设置 → 异常收件箱。")
    lines = [ln for ln in detail.splitlines() if not ln.strip().startswith(("evidence:", "entities:"))]
    text = "\n".join(lines)
    return text if len(text) <= 1200 else text[:1200] + " …"


def engines_label(ep, model: str) -> str:
    """The AI behind an agent, as the user knows it: "Codex · GPT-6.1-Sol", "DeepSeek · deepseek-chat"."""
    if ep is None:
        return model
    if ep.kind == "engine":
        from codedoctor import engines

        return engines.label({"engine": ep.base_url.split(":", 1)[1], "engine_model": model})
    return f"{ep.name or ep.id} · {model}"


def _without_system_block(summary: str) -> str:
    """The panels below show the checklist and the anomaly record; the text copy the system appends to the answer
    (for the command line and other readers) is left out here, so it is not shown twice."""
    head, sep, tail = summary.rpartition("\n---\n")
    if sep and tail.lstrip().startswith(("细节审查清单", "异常记录")):
        return head.rstrip()
    return summary

from codedoctor.desktop.team_ui import MemberAvatar, MemberMessage, is_team_task  # noqa: E402


class StepList(QWidget):
    """Incrementally rendered actions of one task (from its journal)."""

    def __init__(self, daemon, task_id: str):
        super().__init__()
        self.d, self.task_id = daemon, task_id
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(1)
        self.last_seq = 0
        self.rows_by_call: dict[str, StepRow] = {}
        self.details: dict[int, Markdown] = {}
        self.steps = 0
        self.last_type = None
        self.started_at: str | None = None
        self.empty = label("还没有动作。", "Faint")
        self.lay.addWidget(self.empty)

    def refresh(self) -> bool:
        entries = self.d.s.journal.read(task_id=self.task_id, after_seq=self.last_seq, limit=500)
        for e in entries:
            self.last_seq = e["seq"]
            if e["agent"] == "system" and e["type"] != "test_run":  # the system's test runs are shown (ADR 0016)
                continue
            self.started_at = self.started_at or e["at"]
            self.last_type = e["type"]
            self._add(e)
        return bool(entries)

    def _add(self, e: dict) -> None:
        t, d = e["type"], e["data"]
        if d.get("truncated") and "tool" not in d and t in ("tool_call", "tool_result"):
            d = (self.d.s.journal.original(e) or {}).get("data") or d  # older entries kept only a preview inline
        when = local_time(e["at"])
        if t == "tool_call":
            row = StepRow(d["tool"], describe_tool_call(d["tool"], d.get("arguments", {})), when)
            self._append(row, e)
            self.rows_by_call[d.get("call_id")] = row
            if d["tool"] in ("claude_code", "codex"):  # an engine's step is each thing it does (codedoctor/engines.py)
                self.steps += 1
        elif t == "model_response" and d.get("total_ms") is not None:  # where the time went, on the header's tooltip
            self.timing = d
            return
        elif t == "tool_result":
            row = self.rows_by_call.get(d.get("call_id"))
            if row is not None and not d.get("truncated"):
                ev = d.get("evidence") or []
                sub = f"证据 {len(ev)}" if ev else ""
                row.set_result(d.get("ok"), sub)
                row._result_entry = e
        elif t == "model_response":
            self.steps += 0 if d.get("engine") else 1  # an engine's whole run is one response; its steps are counted above
            payload = self.d.s.journal.original(e).get("payload") or {}
            text = (payload.get("text") or "").strip() if isinstance(payload, dict) else ""
            if text and d.get("tool_calls"):
                row = StepRow("_thought", text.replace("\n", " ")[:200], when)
                row.text.setStyleSheet(f"font-size: 13px; color: {C['text2']}; font-style: italic;")
                self._append(row, e)
        elif t == "model_error" and d.get("status") == 429 and d.get("retryable"):
            row = StepRow("_switch", "模型服务正忙，自动等一会儿再试", when)  # retried (runtime BUSY_RETRIES), not a failure
            row.text.setStyleSheet(f"font-size: 13px; color: {C['text3']};")
            self._append(row, e)
        elif t == "model_error":
            row = StepRow("_error", f"模型出错：{d.get('error', '')[:160]}", when)
            row.text.setStyleSheet(f"font-size: 13px; color: {C['red']};")
            self._append(row, e)
        elif t == "test_run":
            reg, opn = d.get("regressions") or [], d.get("open") or []
            txt = f"系统自动跑测试：{d.get('summary', '')}"
            if reg:
                txt += f"；改坏了原来能过的 {len(reg)} 个：{', '.join(x.split('::')[-1] for x in reg[:4])}"
            elif opn:
                txt += f"；还有 {len(opn)} 个新写的测试没通过"
            row = StepRow("_test", txt, when)
            row.text.setStyleSheet(f"font-size: 13px; color: {C['red'] if reg else C['green'] if not opn else C['text2']};")
            self._append(row, e)
        elif t == "model_switch":
            self._append(StepRow("_switch", f"按你的配置切换到备用模型 {d.get('to')}", when), e)
        elif t in ("budget_stop", "stall_stop"):
            msg = "预算用完，停止" if t == "budget_stop" else f"连续 {d.get('steps_without_progress')} 步没有新进展，停止（避免浪费 token）"
            self._append(StepRow("_stop", msg, when), e)
        elif t == "state_change" and d.get("state") in ("interrupted", "resumed", "error"):
            txt = {"interrupted": "后台停止，任务中断", "resumed": "从中断处继续执行", "error": f"内部错误：{d.get('reason', '')}"}[d["state"]]
            self._append(StepRow("_resume" if d["state"] == "resumed" else "_error", txt, when), e)

    def _append(self, row: StepRow, entry: dict) -> None:
        self.empty.setVisible(False)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(2)
        hl.addWidget(row)
        row._entry = entry
        row.clicked.connect(lambda r=row, h=hl: self._toggle(r, h))
        self.lay.addWidget(holder)

    def _toggle(self, row: StepRow, holder_layout) -> None:
        key = id(row)
        if key in self.details:
            w = self.details.pop(key)
            w.setParent(None)
            w.deleteLater()
            return
        entry = getattr(row, "_result_entry", None) or row._entry
        orig = self.d.s.journal.original(entry)
        payload = orig.get("payload")
        if isinstance(payload, str):
            text = payload
        elif isinstance(payload, dict) and "text" in payload:
            text = (payload.get("text") or "") + ("\n\n" + json.dumps(payload.get("tool_calls"), ensure_ascii=False, indent=1)
                                                   if payload.get("tool_calls") else "")
        else:
            text = json.dumps(orig.get("data") if payload is None else payload, ensure_ascii=False, indent=1)
        if entry is row._entry and entry["type"] == "tool_call":
            text = json.dumps(entry["data"].get("arguments"), ensure_ascii=False, indent=1) + "\n\n（尚无结果）"
        box = QFrame()
        box.setObjectName("Detail")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 8, 12, 8)
        md = Markdown(text[:60000], mono=True, size=12)
        bl.addWidget(md)
        holder_layout.addWidget(box)
        self.details[key] = box

    def busy_text(self) -> str | None:
        if self.last_type in ("model_request", "message_in", "state_change", None):
            return "正在思考……"
        if self.last_type == "tool_call":
            return "正在执行……"
        return None


SQUAD_CN = {"main": "主力修复", "backup": "补位修复", "scout": "侦察"}
# the team area of the page, in this order: (key, title, what the group does)
GROUPS = [("main", "主力组", "修全部代码；监督者跟在后面复查、补修"),
          ("scout", "侦察组", "按业务场景写测试，查出主力漏掉的 bug"),
          ("backup", "补位组", "接手侦察兵查出、还没人修的 bug"),
          ("", "协作的 Agent", "")]
HANDS_MARK = "执行者做了什么（系统记录；执行者本身不写报告）"  # agents.runtime writes the hands' report with it


def _hands_report(text: str) -> tuple[list[str], str] | None:
    """(changes, the worker's last words) of a report the system wrote for the hands, or None for any other report."""
    if not text.startswith(HANDS_MARK):
        return None
    changes, last = [], ""
    for ln in text.splitlines()[1:]:
        if ln.startswith("- "):
            changes.append(ln[2:])
        elif ln.startswith("执行者最后说："):
            last = ln.removeprefix("执行者最后说：").strip()
        elif last and ln.strip() and not ln.startswith("每处修改的逐行差异"):
            last += "\n" + ln
    return changes, last


def _change_html(line: str) -> str:
    """修改 a.py（+1 -1 行） -> the path with coloured counts; 新建 / 运行 / failures as they are."""
    import html
    import re

    m = re.match(r"修改 (\S+)（\+(\d+) -(\d+) 行）", line)
    if m:
        return (f"<span style='color:{C['text']}'>{html.escape(m.group(1))}</span>&nbsp;&nbsp;"
                f"<span style='color:{C['green']}'>+{m.group(2)}</span> <span style='color:{C['red']}'>−{m.group(3)}</span>")
    if line.startswith("新建 "):
        return f"<span style='color:{C['text2']}'>新建</span>&nbsp;{html.escape(line[3:])}"
    colour = C["amber"] if "失败" in line else C["text3"] if line.startswith("没有修改") else C["text2"]
    return f"<span style='color:{colour}'>{html.escape(line)}</span>"


def _report_widget(text: str) -> QWidget:
    """A finished task's report: the changes as a compact list and the worker's words, or the agent's own text."""
    hands = _hands_report(text)
    if hands is None:
        md = Markdown(text[:4000], size=13)
        return md
    changes, last = hands
    box = vbox(spacing=3)
    if changes:
        lines = "<br>".join(_change_html(c) for c in changes[:30]) + ("<br>…" if len(changes) > 30 else "")
        changed = QLabel(lines)
        changed.setTextFormat(Qt.RichText)
        changed.setWordWrap(True)
        changed.setStyleSheet("font-size: 12px; font-family: 'Cascadia Mono', Consolas, monospace;")
        box.layout().addWidget(changed)
    else:
        box.layout().addWidget(label("没有修改文件", size=12, color=C["text3"]))
    if last:
        box.layout().addWidget(label(last[:600], size=13, color=C["text2"], wrap=True))
    return box


class ReviewRow(QWidget):
    """A guardian's review inside its worker's card: who, status, and its report on demand."""

    def __init__(self, daemon, row: dict):
        super().__init__()
        self.d, self.task_id = daemon, row["id"]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(4)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(16,27,42,22); border: none;")
        lay.addWidget(line)
        role = _role(daemon, row["agent"])
        self.chip = Chip()
        self.dot = PulseDot()
        self.first = label("", size=12, color=C["text2"])
        self.first.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        head = hbox(Avatar(role, 22), label(f"{row['agent']} 复查", size=12, bold=True, color=ROLE_COLOR.get(role)),
                    self.first, None, self.dot, self.chip, spacing=8)
        head.layout().setStretch(2, 1)
        self.body = vbox(spacing=4)
        self.report = None
        self.steps = StepList(daemon, row["id"])
        self.body.layout().addWidget(Collapsible(label("查看它的每一步", size=12, color=C["text3"]), self.steps))
        self.coll = Collapsible(head, self.body, expanded=False)
        lay.addWidget(self.coll)
        self.update_row(row)

    def update_row(self, row: dict) -> None:
        self.chip.set(task_status(row))
        running = row["state"] != "finished"
        self.dot.set_state(C["blue"] if running else C["green"], running)
        self.dot.setVisible(running)
        if row["state"] == "finished" and self.report is None:
            rep = orch.report_of(self.d.s, self.task_id)
            if rep:
                text = rep.get("summary", "")
                self.first.setText("· " + next((ln.strip("# ").strip() for ln in text.splitlines() if ln.strip()), "")[:90])
                self.report = Markdown(text[:4000], size=13)
                self.body.layout().insertWidget(0, self.report)
        if self.body.isVisible():
            self.steps.refresh()


class AgentCard(Card):
    """A collaborating agent's subtask: who, what, status, its report, its guardian's review, its steps on demand."""

    def __init__(self, daemon, row: dict):
        super().__init__(padding=14, spacing=6)
        self.d, self.task_id = daemon, row["id"]
        role = _role(daemon, row["agent"])
        body = orch.body_of(row)
        part = SQUAD_CN.get(body.get("squad", ""))  # the squad's parts (ADR 0016 item 14)
        kind = (f"复查（{part}）" if part else "复查") if body.get("review_of") else (
            part or ("咨询" if role == "head_logic" else "子任务"))
        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)
        hl.addWidget(Avatar(role, 30))
        title = label(row["title"], size=13, color=C["text"])
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title.setToolTip(row["title"])
        names = vbox(hbox(label(row["agent"], size=13, bold=True, color=ROLE_COLOR.get(role)),
                          label(f"{ROLE_CN.get(role, role)} · {kind}", size=12, color=C["text3"]), None, spacing=8),
                     title, spacing=1)
        hl.addWidget(names, 1)
        self.chip = Chip()
        self.dot = PulseDot()
        hl.addWidget(self.dot)
        hl.addWidget(self.chip)
        self.lay.addWidget(head)
        self.report_box = vbox(spacing=0)
        self.lay.addWidget(self.report_box)
        self.has_report = False
        self.steps = StepList(daemon, row["id"])
        self.coll = Collapsible(label("查看它的每一步", size=12, color=C["text3"]), self.steps, expanded=False)
        self.lay.addWidget(self.coll)
        self.reviews = vbox(spacing=0)
        self.lay.addWidget(self.reviews)
        self.update_row(row)

    def add_review(self, row: dict) -> ReviewRow:
        r = ReviewRow(self.d, row)
        self.reviews.layout().addWidget(r)
        return r

    def update_row(self, row: dict) -> None:
        status = task_status(row)
        self.chip.set(status)
        running = row["state"] != "finished"
        self.dot.set_state(C["blue"] if running else C["green"], running)
        self.dot.setVisible(running)
        if row["state"] == "finished" and not self.has_report:
            rep = orch.report_of(self.d.s, self.task_id)
            if rep:
                self.report_box.layout().addWidget(_report_widget(rep.get("summary", "")))
                self.has_report = True
        if self.coll.expanded:
            self.steps.refresh()


class TeamSection(QWidget):
    """One group of the team area: a header with what the group does and how far it is, then its cards."""

    def __init__(self, title: str, what: str):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.count = label("", size=12, color=C["text3"])
        lay.addWidget(hbox(label(title, size=14, bold=True, color=C["ink"]),
                           label(what, size=12, color=C["text2"]) if what else None, None, self.count, spacing=10))
        self.cards = vbox(spacing=10)
        lay.addWidget(self.cards)
        self.rows: dict[str, dict] = {}

    def add(self, card: QWidget) -> None:
        self.cards.layout().addWidget(card)

    def note(self, row: dict) -> None:
        self.rows[row["id"]] = row
        running = sum(r["state"] != "finished" for r in self.rows.values())
        n = len(self.rows)
        self.count.setText(f"{n} 项 · {running} 项进行中" if running else f"{n} 项 · 全部结束")


class ClaimRow(QWidget):
    def __init__(self, daemon, claim: dict):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(3)
        status = CLAIM_CN.get(claim["status"], claim["status"])
        top = hbox(Chip(status), Chip(LEVEL_CN.get(claim["evidence_level"], claim["evidence_level"]), C["text2"], C["gray_soft"]),
                   None, label(claim["id"], "Faint"), spacing=6)
        lay.addWidget(top)
        txt = label(claim["statement"]["text"], wrap=True, selectable=True, size=14)
        lay.addWidget(txt)
        reviews = daemon.s.claims.reviews(claim["id"])
        rv = "；".join(f"{r['reviewer']} {VERDICT_CN.get(r['verdict'], r['verdict'])}" for r in reviews) or "还没有独立复查"
        ev = len(claim.get("evidence", []))
        lay.addWidget(label(f"提出者 {claim['author']['id']} · 证据 {ev} 条 · 复查：{rv}", "Faint"))


class TaskView(QWidget):
    follow_up = Signal(str, str)

    def __init__(self, daemon, modes):
        super().__init__()
        self.d = daemon
        self.task_id: str | None = None
        self.chat_id: str | None = None  # the conversation shown (its first task): a reply continues it
        self.chat_title = ""
        self.question = ""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # header
        hdr = QFrame()
        hdr.setObjectName("TaskHeader")
        hdr.setStyleSheet("#TaskHeader { background: rgba(255,255,255,70); border-bottom: 1px solid rgba(255,255,255,160); }")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 12, 20, 12)
        hl.setSpacing(10)
        self.title = label("", "TaskTitle")
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status_chip = Chip()
        self.info = label("", "Muted")
        self.cancel_btn = QPushButton("取消任务")
        self.cancel_btn.setObjectName("Ghost")
        self.resume_btn = QPushButton("继续执行")
        self.resume_btn.setObjectName("Primary")
        for b in (self.cancel_btn, self.resume_btn):
            b.setCursor(Qt.PointingHandCursor)
        hl.addWidget(self.title, 1)
        hl.addWidget(self.status_chip)
        hl.addWidget(self.info)
        hl.addWidget(self.cancel_btn)
        hl.addWidget(self.resume_btn)
        outer.addWidget(hdr)

        # conversation
        self.scroll = QScrollArea()
        self.questions: list = []
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        host = QWidget()
        hostl = QHBoxLayout(host)
        hostl.setContentsMargins(24, 18, 24, 24)
        self.col = QWidget()
        self.col.setMaximumWidth(CHAT_WIDTH.get(ui_prefs.load()["chat_width"], 840))
        self.stream = QVBoxLayout(self.col)
        self.stream.setContentsMargins(0, 0, 0, 0)
        self.stream.setSpacing(16)
        hostl.addStretch(1)
        hostl.addWidget(self.col, 30)
        hostl.addStretch(1)
        self.scroll.setWidget(host)
        mid = QWidget()  # conversation on the left, workspace overview on the right (ADR 0013)
        ml = QHBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        self.find_bar = FindBar()
        self.find_bar.setVisible(False)
        self.hits: list = []
        self.hit_at = 0
        self.find_bar.box.textChanged.connect(self._find)
        self.find_bar.next.clicked.connect(lambda: self._step(1))
        self.find_bar.back.clicked.connect(lambda: self._step(-1))
        self.find_bar.close_btn.clicked.connect(self.close_find)
        ll.addWidget(self.find_bar)
        ll.addWidget(self.scroll, 1)
        ml.addWidget(left, 1)
        from codedoctor.desktop.sidebar import RailButton

        self.ws_toggle = RailButton("sidebar", "展开工作区一览：AI 做了什么、读了哪些文件、改了什么", checkable=False)
        self.ws_toggle.setFixedSize(36, 36)
        self.ws_toggle.clicked.connect(lambda: self.set_workspace_open(True))
        hl.addWidget(self.ws_toggle)
        self.workspace = WorkspacePanel(daemon)
        self.workspace.setMinimumWidth(300)
        self.workspace.setMaximumWidth(480)
        self.workspace.setObjectName("Workspace")
        self.workspace.setStyleSheet("#Workspace { background: rgba(246,249,253,215); border-left: 1px solid rgba(255,255,255,190); }")
        self.workspace.close_btn.clicked.connect(lambda: self.set_workspace_open(False))
        self.workspace.setVisible(False)
        ml.addWidget(self.workspace)
        outer.addWidget(mid, 1)

        # follow-up composer
        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(24, 6, 24, 16)
        self.composer = Composer(modes, placeholder=tr("reply_placeholder"))
        self.composer.setMaximumWidth(900)
        self.composer.send.connect(self.follow_up)
        bl.addStretch(1)
        bl.addWidget(self.composer, 30)
        bl.addStretch(1)
        ll.addWidget(bottom)

    def _section(self, group: str) -> TeamSection:
        if group not in self.sections:
            title, what = next((t, w) for k, t, w in GROUPS if k == group)
            self.sections[group] = TeamSection(title, what)
            order = [k for k, _, _ in GROUPS]
            at = sum(order.index(k) < order.index(group) for k in self.sections if k != group)
            self.sub_box.layout().insertWidget(at, self.sections[group])
        return self.sections[group]

    def set_workspace_open(self, on: bool) -> None:
        self.workspace.setVisible(on)
        self.ws_toggle.setVisible(not on)
        if on and self.task_id:
            self.workspace.show_task(self.task_id)

    # --- building -------------------------------------------------------------------------

    def _clear(self) -> None:
        self.questions.clear()  # labels about to go: a later resize must not reach for them
        self.hits = []
        self.find_bar.setVisible(False)
        while self.stream.count():
            it = self.stream.takeAt(0)
            w = it.widget()
            if w is not None:  # off the screen now, not when Qt gets round to deleting it
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _made_picture(self, task: dict):
        """@Code3D and the other making tools: what the team made, right in the answer."""
        called = orch.body_of(task).get("toolsets") or []
        from codedoctor import makers, model3d

        path = None
        if "code3d" in called:
            path = model3d.result_picture(self.d.s.config.root, parse_ts(task["created_at"]))
        elif set(called) & set(makers.IDS):
            path = makers.result_picture(called, self.d.s.config.root, parse_ts(task["created_at"]))
        return PictureCard(path) if path is not None else None

    def _turn(self, row: dict) -> None:
        """An earlier turn of the conversation, as it reads now: the question and the answer."""
        body = orch.body_of(row) or {"instructions": row["title"]}
        self._question(body.get("instructions", row["title"]), row["created_at"])
        self.stream.addWidget(self._assistant(row))
        reports = [m for m in self.d.s.bus.list(thread_id=row["thread_id"])
                   if m["kind"] == "report" and m["body"].get("task_id") == row["id"]]
        text = reports[-1]["body"].get("summary", "") if reports else task_status(row)
        self.stream.addWidget(Markdown(_without_system_block(text), size=15))
        self.stream.addWidget(self._answer_tools(_without_system_block(text), row["id"]))
        self.stream.addSpacing(10)

    def _remember(self, task_id: str, text: str, button: QPushButton) -> None:
        """This answer goes to the long-term memory of the project, for every AI that works here later."""
        try:
            first = self.d.s.journal.read(task_id=task_id, limit=1)
            self.d.s.notes.write(owner="user", scope="project", kind="fact", text=text[:4000], sources=[first[0]["id"]], task_id=task_id,
                                 data_class=self.d.s.config.code_data_class)
        except Exception as e:  # shown on the button itself: nothing else depends on it
            button.setText("没有记住")
            button.setToolTip(f"{type(e).__name__}: {str(e)[:200]}")
            return
        button.setText("已记住")
        button.setEnabled(False)

    def _answer_tools(self, text: str, task_id: str, question: str | None = None) -> QWidget:
        """Under an answer: copy it; for the last one, have it answered again, or change the question and ask again."""
        def small(title: str) -> QPushButton:
            b = QPushButton(title)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {C['text3']}; font-size: 12px; padding: 3px 8px; border-radius: 8px; }}"
                            f"QPushButton:hover {{ background: {C['sidebar_hover']}; color: {C['ink']}; }}")
            return b

        copy = small("复制")

        def copied():
            QApplication.clipboard().setText(text)
            copy.setText("已复制")

        copy.clicked.connect(copied)
        keep = small("记住")
        keep.setToolTip("存进这个项目的长期记忆，以后的 AI 都会看到")
        keep.clicked.connect(lambda: self._remember(task_id, text, keep))
        parts = [copy, keep]
        if question:
            again, change = small("再答一次"), small("改一改再问")
            again.clicked.connect(lambda: self.follow_up.emit(question, self.composer.mode_agent()))
            change.clicked.connect(lambda: self.composer.set_text(question))
            parts += [again, change]
        return hbox(*parts, None, spacing=2)

    # --- finding in a chat -------------------------------------------------------------------------------------------

    def open_find(self) -> None:
        self.find_bar.setVisible(True)
        self.find_bar.box.setFocus()
        self.find_bar.box.selectAll()
        self._find(self.find_bar.box.text())

    def close_find(self) -> None:
        for md in self.col.findChildren(Markdown):
            md.setExtraSelections([])
            cursor = md.textCursor()
            cursor.clearSelection()
            md.setTextCursor(cursor)
        self.hits = []
        self.find_bar.setVisible(False)
        self.composer.edit.setFocus()

    def _find(self, text: str) -> None:
        self.hits = []
        marked = QColor("#ffe7b0")
        for md in self.col.findChildren(Markdown):
            found = []
            at = md.document().find(text) if text else None
            while at is not None and not at.isNull():
                self.hits.append((md, at))
                mark = QTextEdit.ExtraSelection()
                mark.cursor = at
                mark.format.setBackground(marked)
                found.append(mark)
                at = md.document().find(text, at)
            md.setExtraSelections(found)
        self.hit_at = 0
        self._show_hit()

    def _step(self, by: int) -> None:
        if self.hits:
            self.hit_at = (self.hit_at + by) % len(self.hits)
            self._show_hit()

    def _show_hit(self) -> None:
        if not self.hits:
            self.find_bar.count.setText("没有找到" if self.find_bar.box.text() else "")
            return
        self.find_bar.count.setText(f"{self.hit_at + 1} / {len(self.hits)}")
        md, at = self.hits[self.hit_at]
        md.setTextCursor(at)
        spot = md.mapTo(self.scroll.widget(), md.cursorRect(at).center())
        self.scroll.ensureVisible(spot.x(), spot.y(), 40, 120)

    def _fit_questions(self) -> None:
        """A short question keeps to one line, and a long one must not hold the chat wider than the window."""
        room = max(120, self.scroll.viewport().width() - 90)
        for q in self.questions:
            q.setMinimumWidth(min(q.widest, 620, room))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit_questions()

    def _question(self, text: str, at: str) -> None:
        bubble = QFrame()
        bubble.setObjectName("UserBubble")
        bbl = QVBoxLayout(bubble)
        bbl.setContentsMargins(16, 10, 16, 10)
        q = label(text, wrap=True, selectable=True, size=15)
        widest = max((q.fontMetrics().horizontalAdvance(line) for line in q.text().splitlines() or [""]), default=0)
        q.widest = widest + 8
        self.questions.append(q)
        self._fit_questions()
        bbl.addWidget(q)
        bubble.setMaximumWidth(680)
        self.stream.addWidget(hbox(None, bubble))
        if ui_prefs.load()["show_times"]:
            self.stream.addWidget(hbox(None, label(local_time(at), "Faint")))

    def _assistant(self, task: dict) -> QWidget:
        """Who answers: Lumen, with the AI doing the work (the model, or Claude Code / Codex)."""
        from codedoctor.desktop.liquid import MedicalMark

        body = orch.body_of(task)
        agent = self.d.s.config.agents.get(task["agent"])
        if body.get("engine"):
            from codedoctor import engines

            who = engines.label(body)
        elif body.get("model"):
            who = body["model"]["model"]
        elif agent is not None:
            ep = self.d.s.config.endpoints.get(agent.primary.endpoint)
            who = engines_label(ep, agent.primary.model)
        else:
            who = ""
        mark = MemberAvatar("lumen", 34) if agent is not None and agent.team else MedicalMark(34)
        return hbox(mark, label("Lumen", size=14, bold=True, color=C["ink"]),
                    label(who, size=12, color=C["text3"]), None, spacing=8)

    def apply_prefs(self, ui: dict) -> None:
        self.col.setMaximumWidth(CHAT_WIDTH.get(ui["chat_width"], 840))

    def show_task(self, task_id: str) -> None:
        self.task_id = task_id
        self._clear()
        task = self.d.task(task_id)
        if task is None:
            return
        body = json.loads(task["body"]) if task.get("body") else {"instructions": task["title"]}
        self.chat_id = body.get("chat_of") or task_id
        if getattr(self, "_box_chat", None) not in (None, self.chat_id):  # another conversation: its box starts empty
            self.composer.drop_draft()
        self._box_chat = self.chat_id
        turns = self.d.chat_turns(self.chat_id)
        self.chat_title = turns[0]["title"] if turns else task["title"]  # a chat is named by its first message, or by the user
        self.chat_title = chat_tools.names_of(str(self.d.s.config.source or ""))["titles"].get(self.chat_id, self.chat_title)
        self.question = body.get("instructions", task["title"])
        for row in turns:  # the conversation so far, oldest first
            if row["id"] == task_id:
                break
            self._turn(row)
        # the question
        self._question(body.get("instructions", task["title"]), task["created_at"])

        # who answers
        self.stream.addWidget(self._assistant(task))
        self.main_steps = StepList(self.d, task_id)
        self.activity_head = hbox(label("", size=13, color=C["text2"]), None)
        self.activity_label = self.activity_head.layout().itemAt(0).widget()
        # steps unfold while it works; a finished answer reads as a reply, its steps one click away
        self.activity = Collapsible(self.activity_head, self.main_steps, expanded=task["state"] != "finished" and ui_prefs.load()["expand_steps"])
        act_card = Card(padding=12, spacing=4)
        act_card.lay.addWidget(self.activity)
        self.stream.addWidget(act_card)
        self._chat = bool(orch.body_of(task).get("chat"))  # 你好: a line back, no steps to show (agents/smalltalk.py)
        act_card.setVisible(not self._chat)

        self.busy = hbox(Spinner(), label("正在思考……", size=13, color=C["text2"]), None, spacing=8)
        self.stream.addWidget(self.busy)

        self.sub_box = vbox(spacing=18)  # the team, grouped by part (主力组 / 侦察组 / 补位组 / 其他协作)
        self.stream.addWidget(self.sub_box)
        self.sections: dict[str, TeamSection] = {}
        self.sub_cards: dict[str, QWidget] = {}  # task id -> its card, or the review row inside its worker's card

        self.answer_box = vbox(spacing=8)
        self.stream.addWidget(self.answer_box)
        self.answer_key = None
        self.inv_panel = InvestigationPanel()  # business investigation, when this task has one (ADR 0010)
        self.inv_panel.setVisible(False)
        self.stream.addWidget(self.inv_panel)
        self._inv_at = 0.0
        self.actions_panel = ActionsPanel()  # computer actions of this investigation (ADR 0012)
        self.actions_panel.setVisible(False)
        self.stream.addWidget(self.actions_panel)
        self.anomaly_panel = AnomalyPanel()  # anomaly inbox and head decisions (ADR 0014)
        self.anomaly_panel.setVisible(False)
        self.stream.addWidget(self.anomaly_panel)
        self.checklist_panel = ChecklistPanel()  # detail checklist of a cluster investigation (ADR 0014)
        self.checklist_panel.setVisible(False)
        self.stream.addWidget(self.checklist_panel)
        self._fixing = self.d.s.config.permissions.write_files and not self._chat  # ADR 0016: changes replace the checklist
        self.changes_panel = ChangesPanel()
        self.changes_panel.setVisible(False)
        self.stream.addWidget(self.changes_panel)
        self._cluster_root = _role(self.d, task["agent"]) == "head_dispatch" and not self._chat
        self.claims_box = vbox(spacing=0)
        self.stream.addWidget(self.claims_box)
        self.claims_sig = None
        self.esc_box = vbox(spacing=8)
        self.stream.addWidget(self.esc_box)
        self.esc_ids: set[str] = set()
        self.esc_texts: set[str] = set()  # one banner per message, however many agents hit it
        self.stream.addStretch(1)

        if self.workspace.isVisible():
            self.workspace.show_task(task_id)
        self.refresh(scroll_end=True)

    # --- refresh --------------------------------------------------------------------------

    def refresh(self, scroll_end: bool = False) -> None:
        if not self.task_id:
            return
        bar = self.scroll.verticalScrollBar()
        at_bottom = scroll_end or bar.value() >= bar.maximum() - 40
        task = self.d.task(self.task_id)
        if task is None:
            return
        changed = self.main_steps.refresh()

        status = task_status(task)
        if self._fixing and task["state"] == "finished" and task["outcome"] == "done":
            text, _ = test_verdict(collect_changes(self.d.s, self.task_id))
            if "改坏" in text or "没通过" in text:
                status = "完成 · 测试未全过"  # the answer may say done; the system's test run says otherwise
        self.title.setText(self.chat_title or task["title"])
        self.status_chip.set(status)
        if self.answer_key is not None:
            self.answer_chip.set(status)
        usage = task["usage"] or {}
        if task["state"] != "finished":
            elapsed = time.time() - parse_ts(task["created_at"])
        else:
            elapsed = (usage.get("wall_ms") or 0) / 1000
        steps = self.main_steps.steps
        whole, cached = usage.get('input_tokens', 0) + usage.get('output_tokens', 0), usage.get('cached_tokens', 0)
        if self.sub_cards:  # a team or cluster: everyone's tokens (a real team run showed only Lumen's 15k of 108k)
            whole, cached = orch.tree_tokens(self.d.s, self.task_id), orch.tree_cached(self.d.s, self.task_id)
        tokens = f" · token {whole - cached:,}" if usage or self.sub_cards else ""
        timing = getattr(self.main_steps, "timing", None)
        tip = (f"准备 {timing['prepare_ms'] / 1000:.1f} 秒 · 出第一个字 {timing['first_ms'] / 1000:.1f} 秒 · 模型 "
               f"{(timing.get('api_ms') or 0) / 1000:.1f} 秒" + (" · 接着上一条" if timing.get("reused") else " · 新进程")) if timing else ""
        if cached:
            tip = (tip + "\n" if tip else "") + f"另有 {cached:,} 是缓存重读，价格约十分之一，没有算在里面。"
        self.info.setToolTip(tip)
        self.info.setText(f"{steps} 步 · {duration(elapsed)}{tokens if ui_prefs.load()['show_tokens'] else ''}")
        running = task["state"] != "finished"
        self.activity_label.setText(f"{'正在工作' if running else '已完成'} · {steps} 步 · 用时 {duration(elapsed)}")
        busy = self.main_steps.busy_text() if task["state"] == "running" else None
        self.busy.setVisible(bool(busy))
        if busy:
            self.busy.layout().itemAt(1).widget().setText(busy)
        self.cancel_btn.setVisible(False)  # the composer's stop button stops it (like ChatGPT)
        self.composer.set_running(running)
        self.resume_btn.setVisible(task["state"] == "finished" and task["outcome"] in RESUMABLE)

        # collaborating agents: a worker's card holds its guardian's review
        for row in orch.children(self.d.s, self.task_id):
            body = orch.body_of(row)
            card = self.sub_cards.get(row["id"])
            if is_team_task(self.d, row):  # the Lumen team: a group chat, not cards (team_ui.py)
                if card is None:
                    card = MemberMessage(self.d, row)
                    self.sub_box.layout().addWidget(card)
                    self.sub_cards[row["id"]] = card
                    changed = True
                else:
                    card.update_row(row)
                continue
            group = body.get("squad") if body.get("squad") in SQUAD_CN else ""
            section = self._section(group)
            section.note(row)
            if card is None:
                worker_card = self.sub_cards.get(body.get("review_of") or "")
                if isinstance(worker_card, AgentCard):
                    card = worker_card.add_review(row)
                else:
                    card = AgentCard(self.d, row)
                    section.add(card)
                self.sub_cards[row["id"]] = card
                changed = True
            else:
                card.update_row(row)

        # final answer
        own = [m for m in task["messages"] if m["body"].get("task_id") == self.task_id]
        reports = [m for m in own if m["kind"] == "report"]
        if reports and reports[-1]["id"] != self.answer_key:
            self.answer_key = reports[-1]["id"]
            lay = self.answer_box.layout()
            while lay.count():
                lay.takeAt(0).widget().deleteLater()
            b = reports[-1]["body"]
            self.answer_chip = Chip(task_status(task))  # the status shows in the header; the answer reads as a reply
            lay.addWidget(Markdown(_without_system_block(b["summary"]), size=15))
            shown = self._made_picture(task)
            if shown is not None:
                lay.addWidget(shown)
            lay.addWidget(self._answer_tools(_without_system_block(b["summary"]), self.task_id, self.question))
            u = b.get("usage", {})
            if not self._chat:
                lay.addWidget(label(f"{u.get('steps', 0)} 步 · 模型调用 {u.get('model_calls', 0)} 次 · token 输入 "
                                    f"{u.get('input_tokens', 0):,} / 输出 {u.get('output_tokens', 0):,} · "
                                    f"证据 {len(b.get('evidence', []))} 条", "Faint", wrap=True))
            changed = True

        # escalations
        for m in own:
            if m["kind"] == "escalation" and m["id"] not in self.esc_ids:
                self.esc_ids.add(m["id"])
                reason = ESCALATION_CN.get(m["body"]["reason"], m["body"]["reason"])
                text = f"需要你处理 · {reason}\n{_readable_escalation(self.d, m['body'])}"
                if text in self.esc_texts:  # every agent of a team hit the same wall: one banner says it
                    continue
                self.esc_texts.add(text)
                self.esc_box.layout().addWidget(Banner(text))
                changed = True

        # business investigation: what the backend's delivery gate says. It re-checks raw evidence, so at most every 3 s.
        if changed or time.time() - self._inv_at >= 3:
            self._inv_at = time.time()
            found = investigation_for(self.d, self.task_id)
            if found:
                changed = self.inv_panel.update_from(*found) or changed

        if self.d.s.computer is not None:
            acts = self.d.s.computer.actions(task_ids=orch.tree(self.d.s, self.task_id), limit=300)
            changed = self.actions_panel.update_from(self.d, acts) or changed

        changed = self.anomaly_panel.update_from(self.d.s.anomalies.for_root(self.task_id)) or changed
        if self._fixing:
            changed = self.changes_panel.update_from(self.d.s, self.task_id) or changed
        elif self._cluster_root:
            changed = self.checklist_panel.update_from(self.d.s.anomalies.checklist(self.task_id)) or changed

        # claims of the whole tree
        claims = []
        stack = [self.task_id]
        while stack:
            tid = stack.pop()
            claims += self.d.s.claims.by_task(tid)
            stack += [c["id"] for c in orch.children(self.d.s, tid)]
        sig = [(c["id"], c["status"], len(self.d.s.claims.reviews(c["id"]))) for c in claims]
        if sig != self.claims_sig:
            self.claims_sig = sig
            lay = self.claims_box.layout()
            while lay.count():
                lay.takeAt(0).widget().deleteLater()
            if claims:
                card = Card(padding=16, spacing=2)
                card.lay.addWidget(label(f"结论（{len(claims)}）  —  只有“成立”是经过独立复查的事实", size=13, bold=True,
                                         color=C["text2"]))
                for c in claims:
                    card.lay.addWidget(ClaimRow(self.d, c))
                lay.addWidget(card)
            changed = True

        self.workspace.refresh()
        if changed and at_bottom:
            QTimer.singleShot(30, lambda: bar.setValue(bar.maximum()))
