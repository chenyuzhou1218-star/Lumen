"""修改与测试: what the workers changed in an investigation and what the system's last test run says (ADR 0016).

Shown on the task page instead of the detail checklist when the project lets agents change files. The test state
is the system's own run, not a model's word: green when everything passes, red when a test that passed before the
investigation fails now.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from codedoctor.changes import collect, findings, verdict as _verdict  # noqa: F401  (collect: re-exported)
from codedoctor.desktop.theme import C
from codedoctor.desktop.widgets import hbox, label


def verdict(info: dict) -> tuple[str, str]:
    """(short text, colour) for the test state."""
    text, level = _verdict(info)
    return text, {"red": C["red"], "amber": C["amber"], "green": C["green"]}.get(level, C["text2"])


class ChangesPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(16, 14, 16, 14)
        self.lay.setSpacing(6)
        self.head = label("修改与测试", size=13, bold=True, color=C["text2"])
        self.state = QLabel()
        self.state.setWordWrap(True)
        self.lay.addWidget(hbox(self.head, None))
        self.lay.addWidget(self.state)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(2)
        self.lay.addLayout(self.rows)
        self.found_head = label("侦察兵发现的问题", size=13, bold=True, color=C["text2"])
        self.found_head.setVisible(False)
        self.lay.addWidget(self.found_head)
        self.found_rows = QVBoxLayout()
        self.found_rows.setSpacing(2)
        self.lay.addLayout(self.found_rows)
        self.foot = label("系统在每处修改后自动跑测试（不经过模型）；逐行改动见右侧“工作区一览”。", "Faint", wrap=True)
        self.lay.addWidget(self.foot)
        self._sig = None

    def update_from(self, services, root_task: str) -> bool:
        info = collect(services, root_task)
        sig = (tuple(sorted((k, v[0], v[1]) for k, v in info["files"].items())), info["runs"],
               str(info["last"])[:400] if info["last"] else "", str(sorted(info.get("found", {}).items()))[:2000])
        if sig == self._sig:
            return False
        self._sig = sig
        text, colour = verdict(info)
        last = info["last"] or {}
        detail = ""
        if last.get("regressions"):
            detail = "：" + "，".join(x.split("::")[-1] for x in last["regressions"][:6])
        self.state.setText(f"<span style='color:{colour}; font-weight:600'>{text}</span>{detail}"
                           f"<span style='color:{C['text2']}'>　·　系统共跑了 {info['runs']} 次测试</span>")
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for path, (add, rem, agents) in sorted(info["files"].items()):
            row = hbox(label(path, size=13, color=C["text"]), None,
                       label(f"+{add}", size=12, color=C["green"]), label(f"-{rem}", size=12, color=C["red"]),
                       label("、".join(sorted(agents)), size=12, color=C["text2"]))
            self.rows.addWidget(row)
        self._show_found(info)
        self.setVisible(bool(info["files"]) or info["runs"] > 0)
        return True

    def _show_found(self, info: dict) -> None:
        """One row per scout finding: the scenario's test, who fixes it, and the system's last word on it."""
        while self.found_rows.count():
            item = self.found_rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        found = findings(info)
        self.found_head.setVisible(bool(found))
        for f in found:
            who = "主力修" if f["fixer"] == "主力" else f"补位 {f['fixer']} 修"
            state = label("已修好" if f["fixed"] else "还没通过", size=12, color=C["green"] if f["fixed"] else C["amber"])
            self.found_rows.addWidget(hbox(label(f["test"], size=13, color=C["text"]), None,
                                           label(f"{f['scout'] or '侦察兵'} 发现 · {who}", size=12, color=C["text2"]),
                                           state))
