"""Computer use in the desktop app (ADR 0012): the stop button, the approvals only the user can give, and the
record of what agents did on the screen.

Approving here calls the gate in-process. There is deliberately no other way for the user's approval to
arrive (no HTTP route), so no other local program can approve on the user's behalf.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from codedoctor.desktop.i18n import tr
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import Card, Chip, hbox, label, vbox

STATUS_CN = {"checking": "检查中", "refused": "被规则拦下", "pending_guardian": "等监督员批准", "guardian_decided": "监督员已决定",
             "pending_user": "等你批准", "approved": "已批准", "denied": "被拒绝", "executed": "已执行", "failed": "执行失败"}
STATUS_COLOR = {"executed": (C["green"], C["green_soft"]), "refused": (C["red"], C["red_soft"]), "denied": (C["red"], C["red_soft"]),
                "failed": (C["red"], C["red_soft"]), "pending_user": (C["amber"], C["amber_soft"]),
                "pending_guardian": (C["blue"], C["blue_soft"])}
VERDICT_CN = {"approve": "批准", "deny": "拒绝", "needs_user": "交给你决定"}
MODE_CN = {"off": "关闭", "guardian": "监督员事前批准", "ask": "每次问你", "on": "开启"}


def describe_cn(rec: dict) -> str:
    a, k = rec["args"], rec["kind"]
    if k in ("move", "click"):
        what = "移动鼠标" if k == "move" else {"left": "左键", "right": "右键", "middle": "中键"}.get(a.get("button", "left"), "") + \
            ("双击" if a.get("double") else "单击")
        sp = rec.get("screen_point")
        return f"{what}（截图中的 {a['x']:g}, {a['y']:g}" + (f"，屏幕 {sp[0]}, {sp[1]}）" if sp else "）")
    if k in ("edit", "create"):
        return f"{'修改' if k == 'edit' else '新建'}文件 {a.get('path', '?')}"
    if k == "delete":
        return f"删除：{a.get('path') or a.get('command', '?')}"
    if k == "command":
        return f"运行命令：{a.get('command', '')[:300]}"
    if k == "type":
        return f"输入 {len(a['text'])} 个字：{a['text'][:120]}"
    if k == "keys":
        return f"按键 {' + '.join(a['keys'])}"
    if k == "launch":
        return f"启动程序 {a['app']}"
    if k == "close":
        return f"{'强制' if a.get('force') else ''}关闭进程 {a['pid']}"
    return f"终端命令：{a['command'][:300]}"


def _pixmap(daemon, ev_id: str | None) -> QPixmap | None:
    if not ev_id or daemon.s.evidence.check(ev_id) != "ok":
        return None
    pm = QPixmap()
    pm.loadFromData(daemon.s.evidence.content(ev_id))
    return None if pm.isNull() else pm


class Thumb(QLabel):
    """A screenshot preview; click to see it full size."""

    def __init__(self, pm: QPixmap, w: int = 360, h: int = 220):
        super().__init__()
        self.pm = pm
        self.setPixmap(pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("点击查看原图")
        self.setStyleSheet(f"border: 1px solid {C['border']}; border-radius: 6px;")

    def mousePressEvent(self, _):
        dlg = QDialog(self)
        dlg.setWindowTitle("截图（红圈是要操作的位置）")
        lay = QVBoxLayout(dlg)
        scroll = QScrollArea()
        img = QLabel()
        img.setPixmap(self.pm)
        scroll.setWidget(img)
        lay.addWidget(scroll)
        dlg.resize(min(self.pm.width() + 40, 1400), min(self.pm.height() + 60, 900))
        dlg.exec()


class ApprovalCard(Card):
    def __init__(self, daemon, rec: dict, on_decided):
        super().__init__(padding=12, spacing=6)
        self.setStyleSheet(f"#Card {{ border: 1px solid {C['amber']}; }}")
        gate = daemon.s.computer
        row = hbox(spacing=12)
        pm = _pixmap(daemon, rec.get("view"))
        if pm is not None:
            row.layout().addWidget(Thumb(pm), 0, Qt.AlignTop)
        info = vbox(spacing=4)
        il = info.layout()
        il.addWidget(hbox(Chip(tr("ap_waiting"), C["amber"], C["amber_soft"]), label(tr("ap_wants", agent=rec["agent"]), bold=True, size=14), None))
        il.addWidget(label(describe_cn(rec), wrap=True, selectable=True, size=14))
        il.addWidget(label(tr("ap_purpose", t=rec["intent"]), wrap=True, selectable=True, size=13))
        il.addWidget(label(tr("ap_why", t=rec.get("user_reason") or "—"), wrap=True, size=13, color=C["amber"]))
        if rec.get("guardian_verdict"):
            il.addWidget(label(tr("ap_guardian", g=rec["guardian"], v=rec["guardian_verdict"], r=rec.get("guardian_reason", "")),
                               wrap=True, size=13, color=C["text2"]))
        approve, deny = QPushButton(tr("approve")), QPushButton(tr("deny"))
        approve.setObjectName("Primary")
        deny.setObjectName("Ghost")
        for b, ok in ((approve, True), (deny, False)):
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, ok=ok: self._decide(gate, rec["id"], ok, on_decided))
        il.addWidget(hbox(approve, deny, None, label(rec["id"], "Faint", selectable=True)))
        row.layout().addWidget(info, 1)
        self.lay.addWidget(row)

    def _decide(self, gate, action_id: str, approve: bool, on_decided) -> None:
        try:
            gate.user_decides(action_id, approve, "decided in the Lumen window")
        except PermissionError:
            pass  # already decided, timed out or stopped meanwhile
        on_decided()


class ComputerBar(QFrame):
    """Above every page, but only when there is something for the user: an action waiting for their approval, or the
    emergency stop to undo. (An always-on 'computer use is on / stop now' bar was removed at the user's request: the
    composer's stop button stops an investigation, Ctrl+Alt+End and the top-left corner stop computer use.)"""

    def __init__(self, daemon, parent=None):
        # parent: the window passes its column, so refresh() below never shows a parentless (= stray) window
        super().__init__(parent)
        self.d = daemon
        self.setObjectName("ComputerBar")
        self.setStyleSheet("#ComputerBar { background: rgba(255,255,255,120); border-bottom: 1px solid rgba(255,255,255,170); }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 8, 20, 8)
        lay.setSpacing(8)
        p = daemon.config.computer
        self.status = label("", size=13)
        self.summary = label(f"截屏 {MODE_CN[p.screenshot]} · 鼠标键盘 {MODE_CN[p.input]} · 开关程序 {MODE_CN[p.apps]} · "
                             f"终端 {MODE_CN[p.terminal]} · 允许的窗口：{'、'.join(p.windows) or '—'} · 紧急停止：Ctrl+Alt+End 或把鼠标推到屏幕左上角",
                             "Faint", wrap=True)
        self.stop_btn = QPushButton()
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self._toggle)
        lay.addWidget(hbox(self.status, None, self.stop_btn))
        self.summary.setVisible(False)
        self.pending = vbox(spacing=8)
        lay.addWidget(self.pending)
        self.sig = None
        self.refresh()

    def _toggle(self) -> None:
        gate = self.d.s.computer
        if gate.stopped():
            gate.resume()
        else:
            gate.stop("stopped in the Lumen window")
        self.refresh()

    def refresh(self) -> None:
        gate = self.d.s.computer
        if gate is None or getattr(self, "quiet", False):
            self.setVisible(False)
            return
        stopped = gate.stopped() if gate.available else None
        mine = gate.actions(statuses=("pending_user",))
        self.setVisible(bool(stopped or mine))
        self.status.setVisible(bool(stopped))
        self.stop_btn.setVisible(bool(stopped))
        if stopped:
            self.status.setText(tr("pc_stopped", why=stopped))
            self.status.setStyleSheet(f"font-size: 13px; color: {C['red']}; font-weight: 700;")
            self.stop_btn.setText(tr("pc_resume"))
        sig = [r["id"] for r in mine]
        if sig == self.sig:
            return
        self.sig = sig
        lay = self.pending.layout()
        while lay.count():
            lay.takeAt(0).widget().deleteLater()
        for rec in reversed(mine):  # oldest first
            lay.addWidget(ApprovalCard(self.d, rec, self.refresh))


class ActionsPanel(Card):
    """What agents did (or tried to do) on the screen in one investigation, newest last."""

    def __init__(self):
        super().__init__(padding=16, spacing=6)
        self.sig = None
        self.body = vbox(spacing=8)
        self.lay.addWidget(self.body)

    def update_from(self, daemon, actions: list[dict]) -> bool:
        self.setVisible(bool(actions))
        sig = [(a["id"], a["status"], a.get("after")) for a in actions]
        if sig == self.sig:
            return False
        self.sig = sig
        lay = self.body.layout()
        while lay.count():
            lay.takeAt(0).widget().deleteLater()
        done = sum(1 for a in actions if a["status"] == "executed")
        lay.addWidget(label(f"电脑操作（{len(actions)} 个，已执行 {done} 个）—— 每一步都先经过程序检查和监督员批准",
                            size=13, bold=True, color=C["text2"]))
        for a in reversed(actions):
            fg, bg = STATUS_COLOR.get(a["status"], (C["text2"], C["gray_soft"]))
            row = vbox(spacing=2)
            rl = row.layout()
            rl.addWidget(hbox(Chip(STATUS_CN.get(a["status"], a["status"]), fg, bg), label(a["agent"], bold=True, size=13),
                              label(describe_cn(a), size=13, wrap=True), stretch_at=2))
            rl.addWidget(label(f"目的：{a['intent']}", "Faint", wrap=True, selectable=True))
            for e in a.get("events", []):
                if e["what"] in ("refused", "denied", "failed", "guardian_deny", "guardian_needs_user", "user_denied", "no_guardian"):
                    rl.addWidget(label(f"{e['by']}：{e['note']}", "Faint", wrap=True, selectable=True))
            after = daemon.s.computer.shot(a["after"], a["task_id"]) if a.get("after") else None
            pm = _pixmap(daemon, after["evidence"]) if after else None
            if pm is not None:
                rl.addWidget(hbox(Thumb(pm, 240, 150), None))
            lay.addWidget(row)
        return True
