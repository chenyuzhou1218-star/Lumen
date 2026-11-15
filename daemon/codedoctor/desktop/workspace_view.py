"""Workspace overview panel (ADR 0013): a side panel of the task view, opened with the arrow on its right edge.

Everything comes from what Lumen stores permanently (journal, evidence, claims, notes, computer
actions, project snapshots), so it stays complete however much of a model's context was elided.
"""

from __future__ import annotations

import html
import json
import threading
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QPushButton, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout,
                               QWidget)

from codedoctor import workspace
from codedoctor.agents import orchestration as orch
from codedoctor.desktop.computer_view import STATUS_CN as ACTION_CN
from codedoctor.desktop.computer_view import describe_cn
from codedoctor.desktop.theme import C, MONO_FAMILY
from codedoctor.desktop.widgets import hbox, label
from codedoctor.ui_text import CLAIM_CN, describe_tool_call, local_time

KIND_CN = {"answer": "回答", "thought": "思路", "error": "模型出错", "switch": "切换备用模型", "stop": "停止", "state": "状态"}


def _text_view() -> QTextBrowser:
    v = QTextBrowser()
    v.setOpenLinks(False)
    v.setStyleSheet(f"font-family: {MONO_FAMILY}; font-size: 12px;")
    return v


def diff_html(diff: str) -> str:
    rows = []
    for line in diff.splitlines():
        colour = (C["green"] if line.startswith("+") and not line.startswith("+++") else
                  C["red"] if line.startswith("-") and not line.startswith("---") else
                  C["blue"] if line.startswith("@@") else C["text2"] if line.startswith(("+++", "---")) else C["text"])
        rows.append(f'<span style="color:{colour}">{html.escape(line) or "&nbsp;"}</span>')
    return f'<pre style="font-family:{MONO_FAMILY}; font-size:12px; margin:0">' + "<br>".join(rows) + "</pre>"


class _ListAndDetail(QSplitter):
    """A list above, the selected item's details below."""

    def __init__(self, on_select):
        super().__init__(Qt.Vertical)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.detail = _text_view()
        self.addWidget(self.list)
        self.addWidget(self.detail)
        self.setSizes([320, 260])
        self.list.currentItemChanged.connect(lambda cur, _: on_select(cur.data(Qt.UserRole) if cur else None))

    def fill(self, rows: list[tuple[str, object]]) -> None:
        keep = self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        for text, data in rows:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, data)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if 0 <= keep < self.list.count():
            self.list.setCurrentRow(keep)


class WorkspacePanel(QWidget):
    def __init__(self, daemon):
        super().__init__()
        self.d = daemon
        self.task_id: str | None = None
        self.sig = None
        self._at = 0.0
        self._changes: dict | None = None
        self._changes_at = 0.0
        self._changes_busy = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        self.close_btn = QPushButton("›")
        self.close_btn.setObjectName("Ghost")
        self.close_btn.setToolTip("收起工作区一览")
        self.close_btn.setFixedWidth(32)
        lay.addWidget(hbox(label("工作区一览", size=15, bold=True), None, self.close_btn))
        lay.addWidget(label("来自永久保存的日志和记录，不受模型上下文压缩影响。", "Faint", wrap=True))
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        self.changes_note = label("", "Faint", wrap=True)
        self.changes = _ListAndDetail(self._show_change)
        tab = QWidget()
        tl = QVBoxLayout(tab)
        tl.setContentsMargins(0, 6, 0, 0)
        tl.addWidget(self.changes_note)
        tl.addWidget(self.changes, 1)
        self.undo_btn = QPushButton("撤回这次调查的所有修改")
        self.undo_btn.setObjectName("Ghost")
        self.undo_btn.setToolTip("把项目恢复到调查开始时的样子；调查结束后又被改过的文件会跳过，不会覆盖你的修改")
        self.undo_btn.clicked.connect(self._undo)
        self.undo_btn.setVisible(False)
        tl.addWidget(hbox(None, self.undo_btn))
        self.tabs.addTab(tab, "改动")
        self.timeline = _ListAndDetail(self._show_step)
        self.tabs.addTab(self.timeline, "时间线")
        self.files = _ListAndDetail(self._show_file)
        self.tabs.addTab(self.files, "读过的文件")
        self.cmds = _ListAndDetail(self._show_cmd)
        self.tabs.addTab(self.cmds, "命令与操作")
        self.findings = _ListAndDetail(self._show_finding)
        self.tabs.addTab(self.findings, "结论与记忆")
        self.tabs.currentChanged.connect(lambda _: self.refresh(force=True))

    # --- refresh ----------------------------------------------------------------------------------

    def show_task(self, task_id: str) -> None:
        self.task_id, self.sig, self._changes, self._changes_at = task_id, None, None, 0.0
        self.refresh(force=True)

    def _signature(self, tree: list[str]) -> tuple:
        marks = ",".join("?" * len(tree))
        seq = self.d.s.db.one(f"SELECT MAX(seq) AS n FROM journal WHERE task_id IN ({marks})", tree)["n"]
        acts = len(self.d.s.computer.actions(task_ids=tree)) if self.d.s.computer else 0
        claims = tuple((c["id"], c["status"]) for t in tree for c in self.d.s.claims.by_task(t))
        return seq, acts, claims, workspace.get(self.d.s, self.task_id, "end") is not None

    def refresh(self, force: bool = False) -> None:
        if not self.task_id or not self.isVisible():
            return
        if not force and time.time() - self._at < 2:
            return
        self._at = time.time()
        tree = orch.tree(self.d.s, self.task_id)
        sig = self._signature(tree)
        if sig != self.sig:
            self.sig = sig
            self._fill_timeline()
            self._fill_files()
            self._fill_cmds(tree)
            self._fill_findings()
        if self.tabs.currentIndex() == 0:
            self._refresh_changes()

    # --- changes (computed off the UI thread: comparing with 'now' scans the project) ----------------

    def _refresh_changes(self) -> None:
        ended = workspace.get(self.d.s, self.task_id, "end") is not None
        stale = self._changes is None or (not ended and time.time() - self._changes_at > 10) or \
            (ended and self._changes.get("against") != "end")
        if not stale or self._changes_busy:
            return
        self._changes_busy = True
        task_id, out = self.task_id, {}

        def work():
            try:
                out["changes"] = workspace.changes(self.d.s, task_id)
            except Exception as e:  # shown in the panel
                out["error"] = f"{type(e).__name__}: {e}"

        threading.Thread(target=work, daemon=True).start()
        self._await_changes(task_id, out)

    def _await_changes(self, task_id: str, out: dict) -> None:
        if not out:
            QTimer.singleShot(100, lambda: self._await_changes(task_id, out))
            return
        self._changes_busy = False
        if task_id != self.task_id:
            return
        self._changes_at = time.time()
        if "error" in out:
            self.changes_note.setText("对比失败：" + out["error"])
            return
        ch = out["changes"]
        self._changes = ch
        if ch is None:
            self.changes_note.setText("这个调查没有项目快照（快照从 ADR 0013 之后开始的调查才有）。")
            self.changes.fill([])
            return
        span = "开始 → 结束" if ch["against"] == "end" else "开始 → 现在（调查还在进行）"
        self.changes_note.setText(
            f"调查开始以来（{span}）：新增 {len(ch['added'])}、修改 {len(ch['modified'])}、删除 {len(ch['deleted'])} 个文件。"
            "快照只能看出文件变了，看不出是谁改的：期间你自己或其他程序的修改也会算在内。"
            + ("（项目文件太多，快照被截断。）" if ch["truncated"] else ""))
        self.undo_btn.setVisible(ch["against"] == "end" and bool(ch["added"] or ch["modified"] or ch["deleted"]))
        rows = [(f"＋ {p}", ("added", p)) for p in ch["added"]] + \
               [(f"✎ {m['path']}" + ("" if m["text"] else "（二进制，只比较大小和时间）"), ("modified", m["path"], m["text"]))
                for m in ch["modified"]] + [(f"－ {p}", ("deleted", p)) for p in ch["deleted"]]
        self.changes.fill(rows or [("没有文件变化。", None)])

    def _undo(self) -> None:
        """One-click undo of an investigation's changes (ADR 0016), after asking."""
        from PySide6.QtWidgets import QMessageBox

        from codedoctor.desktop.dialogs import notice

        ch = self._changes or {}
        n = len(ch.get("added", [])) + len(ch.get("modified", [])) + len(ch.get("deleted", []))
        if QMessageBox.question(self, "撤回修改", f"把这次调查改动过的 {n} 个文件恢复到调查开始时的样子？\n"
                                                 "调查结束后又被改过的文件会跳过，不会覆盖你的修改。") != QMessageBox.Yes:
            return
        try:
            res = workspace.revert(self.d.s, self.task_id)
        except Exception as e:
            notice(self, "撤回失败", f"{type(e).__name__}: {e}", kind="error")
            return
        lines = [f"恢复 {p}" for p in res["restored"]] + [f"删除（调查中新建的）{p}" for p in res["removed"]] + \
                [f"跳过 {x['path']}：{x['why']}" for x in res["skipped"]]
        notice(self, "已撤回", f"恢复 {len(res['restored'])} 个、删除 {len(res['removed'])} 个、跳过 {len(res['skipped'])} 个文件。",
               kind="warning" if res["skipped"] else "info", details=lines)
        self._changes, self._changes_at = None, 0.0
        self.changes_note.setText("已撤回。")
        self.undo_btn.setVisible(False)

    def _show_change(self, data) -> None:
        if not data:
            self.changes.detail.clear()
            return
        if data[0] == "modified" and not data[2]:
            self.changes.detail.setPlainText("二进制文件或大于 512 KB 的文件：只记录大小和修改时间，不显示逐行差异。")
            return
        diff = workspace.diff(self.d.s, self.task_id, data[1])
        if diff:
            self.changes.detail.setHtml(diff_html(diff))
        else:
            self.changes.detail.setPlainText("没有可显示的文本差异（二进制文件，或内容没有保存）。")

    # --- the rest ------------------------------------------------------------------------------------

    def _fill_timeline(self) -> None:
        rows = []
        for it in workspace.timeline(self.d.s, self.task_id):
            when = local_time(it["at"])
            if it["kind"] == "tool":
                mark = "…" if it["ok"] is None else ("✓" if it["ok"] else "✗")
                rows.append((f"{when}  {it['agent']}  {mark} {describe_tool_call(it['tool'], it['arguments'])}", it))
            else:
                rows.append((f"{when}  {it['agent']}  [{KIND_CN.get(it['kind'], it['kind'])}] {it['text'][:160]}", it))
        self.timeline.fill(rows or [("还没有动作。", None)])

    def _show_step(self, it) -> None:
        if not it:
            self.timeline.detail.clear()
            return
        if it["kind"] != "tool":
            self.timeline.detail.setPlainText(f"{it['agent']} · {it['task']}\n\n{it['text']}")
            return
        text = f"{it['agent']} · 任务：{it['task']}\n\n参数：\n{json.dumps(it['arguments'], ensure_ascii=False, indent=1)}"
        if it["result_entry"]:
            res = self.d.s.journal.get(it["result_entry"])
            payload = self.d.s.journal.original(res).get("payload")
            text += "\n\n结果：\n" + (payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=1))[:60000]
        else:
            text += "\n\n（还没有结果）"
        self.timeline.detail.setPlainText(text)

    def _fill_files(self) -> None:
        rows = [(f"{f['path']}  ·  {', '.join(f['ranges'][:6])}{' …' if len(f['ranges']) > 6 else ''}  ·  {', '.join(f['agents'])}", f)
                for f in workspace.files_read(self.d.s, self.task_id)]
        self.files.fill(rows or [("还没有读过项目文件。", None)])

    def _show_file(self, f) -> None:
        if not f:
            self.files.detail.clear()
            return
        parts = []
        for ev in f["evidence"][:5]:
            if self.d.s.evidence.check(ev) == "ok":
                parts.append(f"── {ev.rsplit(':', 1)[-1]}  ({ev})\n" + self.d.s.evidence.content(ev).decode("utf-8", errors="replace"))
        self.files.detail.setPlainText("\n\n".join(parts) or "摘录无法读取。")

    def _fill_cmds(self, tree: list[str]) -> None:
        rows = []
        for c in workspace.commands(self.d.s, self.task_id):
            mark = "…" if c["ok"] is None else ("✓" if c["ok"] else "✗")
            code = f"（退出码 {c['exit_code']}）" if c["exit_code"] is not None else ""
            rows.append((f"{local_time(c['at'])}  {c['agent']}  {mark} $ {c['command'][:120]}{code}", ("cmd", c)))
        if self.d.s.computer is not None:
            for a in reversed(self.d.s.computer.actions(task_ids=tree, limit=500)):
                if a["kind"] == "terminal":
                    continue  # already listed with its output above
                rows.append((f"{local_time(a['created_at'])}  {a['agent']}  [{ACTION_CN.get(a['status'], a['status'])}] {describe_cn(a)}",
                             ("act", a)))
        rows.sort(key=lambda r: r[0])
        self.cmds.fill(rows or [("没有运行过命令，也没有电脑操作。", None)])

    def _show_cmd(self, data) -> None:
        if not data:
            self.cmds.detail.clear()
            return
        kind, x = data
        if kind == "cmd":
            self.cmds.detail.setPlainText(f"$ {x['command']}\n\n{x['output']}")
        else:
            events = "\n".join(f"{e['at'][11:19]} {e['by']}: {e['what']} {e.get('note', '')}" for e in x.get("events", []))
            self.cmds.detail.setPlainText(f"{describe_cn(x)}\n目的：{x['intent']}\n状态：{ACTION_CN.get(x['status'], x['status'])}\n\n{events}")

    def _fill_findings(self) -> None:
        cn = workspace.claims_and_notes(self.d.s, self.task_id)
        rows = [(f"[{CLAIM_CN.get(c['status'], c['status'])}] {c['statement']['text'][:140]}  ·  {c['author']['id']}", ("claim", c))
                for c in cn["claims"]]
        rows += [(f"[记忆] {n['text'][:140]}  ·  {n['owner']}", ("note", n)) for n in cn["notes"]]
        self.findings.fill(rows or [("还没有结论或记忆。", None)])

    def _show_finding(self, data) -> None:
        if not data:
            self.findings.detail.clear()
            return
        kind, x = data
        if kind == "claim":
            ev = "\n".join(f"- {r['id']}  ({r['role']}) {r.get('shows', '')}" for r in x.get("evidence", []))
            st = x["statement"]
            self.findings.detail.setPlainText(
                f"{x['id']}  [{CLAIM_CN.get(x['status'], x['status'])}]  {x['claim_type']} / {x['evidence_level']}\n"
                f"{st['text']}\n{st['subject']} -{st['relation']}-> {st['object']}\n\n证据：\n{ev or '无'}")
        else:
            self.findings.detail.setPlainText(f"{x['id']}  {x['kind']}  {x['owner']}\n\n{x['text']}")
