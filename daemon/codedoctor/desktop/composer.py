"""The rounded message box: auto-growing text; along the bottom ＋ (attach files), 帮我批准 (approve computer actions
for me in this investigation), the way of working, and one model button (the model and the thinking level for this
investigation: 选择模型, 思考强度 › with a slider, 更多模型 › asked live from the services, 快速模式), then send."""

from __future__ import annotations

import re
from pathlib import Path

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QTextOption
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


from codedoctor.desktop import chat_tools
from codedoctor.desktop.theme import C
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.picker import ApprovalButton, ApprovalPopover, IconButton, MentionChip, StopButton, TeamButton, level_name, ListPopover, ModelPill, SendButton, ThinkingPopover, model_list
from codedoctor.desktop.voice_bar import MicButton, VoiceBar
from codedoctor.desktop.widgets import label, shadow
from codedoctor.models.reasoning import LEVELS


class _Edit(QPlainTextEdit):
    submit = Signal()
    at = Signal()  # "@" typed: the menu of tools to call in
    files = Signal(list)  # files dropped or pasted on the box
    keep = Signal()  # Ctrl+S: keep what is written as a phrase

    def _local_files(self, data) -> list[str]:
        return [u.toLocalFile() for u in data.urls() if u.isLocalFile()] if data.hasUrls() else []

    def dragEnterEvent(self, e):  # noqa: N802 (Qt naming)
        if self._local_files(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):  # noqa: N802 (Qt naming)
        if self._local_files(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):  # noqa: N802 (Qt naming)
        found = self._local_files(e.mimeData())
        if found:
            e.acceptProposedAction()
            self.files.emit(found)
        else:
            super().dropEvent(e)

    def insertFromMimeData(self, source):  # noqa: N802 (Qt naming): files copied in Explorer and pasted here
        found = self._local_files(source)
        if found:
            self.files.emit(found)
        else:
            super().insertFromMimeData(source)

    def keyPressEvent(self, e: QKeyEvent):
        if e.matches(QKeySequence.StandardKey.Save):
            self.keep.emit()
            return
        # Enter sends, Shift+Enter starts a new line (like chat apps), or Ctrl+Enter sends if the user chose that.
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            from codedoctor.desktop import prefs

            ctrl_only = prefs.load()["send_key"] == "ctrl_enter"
            if (e.modifiers() & Qt.ControlModifier) if ctrl_only else not (e.modifiers() & Qt.ShiftModifier):
                self.submit.emit()
                return
        super().keyPressEvent(e)
        if e.text() == "@":
            self.at.emit()

    def inputMethodEvent(self, e):  # noqa: N802 (Qt naming)
        """While an input method composes (拼音 not yet chosen) the box looks empty to Qt, which kept drawing the grey
        hint under the letters being typed: the hint is hidden for as long as anything is being composed."""
        if e.preeditString():
            if self.placeholderText():
                self._hint = self.placeholderText()
                self.setPlaceholderText("")
        elif getattr(self, "_hint", None):
            self.setPlaceholderText(self._hint)
            self._hint = None
        super().inputMethodEvent(e)


# Tools the user can call in with @ (one investigation at a time): key -> name. Their tools exist only in that
# investigation (agents/runtime._task_tools); CodeCut also opens its window, following the project (desktop/app.py).
MENTIONS = {"codecut": "CodeCut", "code3d": "Code3D", "codesound": "CodeSound", "codepage": "CodePage", "codegame": "CodeGame", "codedeck": "CodeDeck", "codedata": "CodeData",
            "codecad": "CodeCAD", "codelab": "CodeLab", "codetools": "CodeTools", "codefilm": "CodeFilm", "codepdf": "CodePDF"}
MENTION_RE = re.compile(r"@\s?(codecut|code3d|codesound|codepage|codegame|codedeck|codedata|codecad|codelab|codetools|codefilm|codepdf)\b", re.I)


def mentionable() -> list[str]:
    """The tools installed here (codedoctor/video.home(), model3d.home(), makers.home())."""
    from codedoctor import makers, model3d, video

    return [k for k, there in (("codecut", video.home()), ("code3d", model3d.home())) if there is not None] + makers.installed()


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


ATTACH_MAX = 200_000      # characters per attached file
ATTACH_TOTAL = 400_000    # all attachments of one message


class Composer(QFrame):
    _sent = None  # (text, files, @ tools) of the message being sent, until it is known to have gone out (give_back)
    send = Signal(str, str)  # (text, agent id); options() has the model, the thinking level and the approval choice
    stop = Signal()          # the stop button next to send (shown while the investigation runs)
    team = Signal()          # the way of working was clicked: open its settings (协作方式)
    turn_on_computer = Signal()  # 打开电脑操作 in the approval menu
    mentions_changed = Signal(list)  # the @ tools called in (the window shows the first one's own view above the chat)

    def __init__(self, modes: list[tuple[str, str, str]], placeholder: str | None = None):
        """modes: [(key, label, agent id)] - the ways of working, chosen in the tray under the card."""
        super().__init__()
        self.setObjectName("ComposerHost")
        self.modes = modes
        self.mode_key = modes[0][0] if modes else ""
        self.attached: list[tuple[str, str]] = []  # (file name, text)
        self.model_choice: dict | None = None    # {"endpoint", "model"}; None: each agent's own model
        self.level: str | None = "medium"         # 思考强度: always a real level, there is no 默认
        self.approval = "auto"                    # 批准方式: ask 全部问我 / auto 帮我审查 (a new chat starts here) / full 完全放开
        self.mentions: list[str] = []             # tools called in with @ for this message (MENTIONS keys)
        self.mention_chips: dict[str, MentionChip] = {}
        self.computer_on = False
        self.full_confirmed = False
        self.fetch_models: Callable | None = None  # set by the window: asks the services for their models (更多模型)
        self.choices: list[tuple[str, str, str]] = []
        self.more: list | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("Composer")
        shadow(self.card, 30, 18, 4)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(20, 16, 14, 12)
        lay.setSpacing(8)
        self.edit = _Edit()
        self.edit.setObjectName("ComposerEdit")
        self.edit.setPlaceholderText(placeholder or tr("placeholder"))
        self.edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.edit.textChanged.connect(self._grow)
        self.edit.submit.connect(self._send)
        self.edit.at.connect(self._open_mentions)
        self.edit.files.connect(self.add_files)
        self.edit.keep.connect(self._keep_phrase)
        self.edit.textChanged.connect(self._maybe_phrases)
        self.setAcceptDrops(True)  # the whole card takes files, not only the text in it
        lay.addWidget(self.edit)
        self.attach_row = QHBoxLayout()
        self.attach_row.setSpacing(6)
        self.attach_row.setContentsMargins(0, 0, 0, 0)
        self.attach_box = QWidget()
        self.attach_box.setLayout(self.attach_row)
        self.attach_box.setVisible(False)
        lay.addWidget(self.attach_box)
        self.mention_row = QHBoxLayout()  # above the buttons: beside them a tool's name ran over them in a narrow window
        self.mention_row.setSpacing(4)
        self.mention_row.setContentsMargins(0, 0, 0, 0)
        self.mention_row.addStretch(1)
        self.mention_box = QWidget()
        self.mention_box.setLayout(self.mention_row)
        self.mention_box.setVisible(False)
        lay.addWidget(self.mention_box)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.attach_btn = IconButton("plus", tr("attach_tip"), 34, 18)
        self.attach_btn.clicked.connect(self._pick_files)
        row.addWidget(self.attach_btn)
        self.approve_btn = ApprovalButton()
        self.approve_btn.clicked.connect(self._open_approval)
        row.addWidget(self.approve_btn)
        self.mode_btn = TeamButton(self._mode_label())  # the way of working: kept, not shown - the window is a chat
        self.mode_btn.clicked.connect(self.team.emit)
        self.mode_btn.setVisible(False)
        row.addWidget(self.mode_btn)
        self.hint = label("", "Faint")  # notes about attachments; empty otherwise
        row.addWidget(self.hint)
        row.addStretch(1)
        self.model_btn = ModelPill()
        self.model_btn.clicked.connect(self._open_thinking)
        row.addWidget(self.model_btn)
        row.addSpacing(4)
        self.mic_btn = MicButton()  # voice input (desktop/voice_bar.py)
        self.mic_btn.clicked.connect(self._start_voice)
        row.addWidget(self.mic_btn)
        row.addSpacing(4)
        self.stop_btn = StopButton()
        self.stop_btn.clicked.connect(self._stopping)
        self.stop_btn.clicked.connect(self.stop.emit)
        self.stop_btn.setVisible(False)
        row.addWidget(self.stop_btn)
        row.addSpacing(6)
        self.send_btn = SendButton()
        self.send_btn.clicked.connect(self._send)
        self.send_btn.setEnabled(False)
        row.addWidget(self.send_btn)
        self.tools = QWidget()
        self.tools.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tools)
        self.voice = VoiceBar()  # shown instead of the box and its buttons while recording
        self.voice.setVisible(False)
        self.voice.text.connect(self._voice_text)
        self.voice.closed.connect(self._end_voice)
        self.voice.problem.connect(lambda why: self.hint.setText(why))
        lay.addWidget(self.voice)
        outer.addWidget(self.card)
        self.buttons = {key: None for key, _, _ in modes}  # the ways of working by key (set_mode / mode_agent)
        self._show_model_btn()
        self._grow()

    # --- voice ---------------------------------------------------------------------------------------------------------

    def _start_voice(self) -> None:
        from codedoctor.desktop import voice

        if not voice.available():
            self.hint.setText(tr("voice_no_mic"))
            return
        self.hint.setText("")
        self.edit.setVisible(False)
        self.tools.setVisible(False)
        self.attach_box.setVisible(False)
        self.voice.setVisible(True)
        self.voice.begin()

    def _end_voice(self) -> None:
        self.voice.setVisible(False)
        self.edit.setVisible(True)
        self.tools.setVisible(True)
        self.attach_box.setVisible(bool(self.attached))
        self.edit.setFocus()

    def _voice_text(self, text: str, send: bool) -> None:
        """Written out: into the box (to read and correct), or sent at once (↑)."""
        current = self.edit.toPlainText().rstrip()
        self.edit.setPlainText(f"{current} {text}".strip() if current else text)
        self._end_voice()
        cursor = self.edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.edit.setTextCursor(cursor)
        if send:
            self._send()

    # --- way of working --------------------------------------------------------------------------------------------

    def _mode_label(self) -> str:
        return next((t for k, t, _ in self.modes if k == self.mode_key), "")

    def mode_agent(self) -> str:
        return next((a for k, _, a in self.modes if k == self.mode_key), self.modes[0][2])

    def set_mode(self, key: str) -> None:
        if any(k == key for k, _, _ in self.modes):
            self.mode_key = key
            self.mode_btn.set_name(self._mode_label())

    # --- model and thinking ----------------------------------------------------------------------------------------

    def set_models(self, choices: list[tuple[str, str, str]]) -> None:
        """[(label, endpoint id, model)]: the models of the project's services, offered first in the list."""
        self.choices = list(choices)

    def set_computer_enabled(self, on: bool) -> None:
        """Whether the project lets agents use the computer (the approval choice only acts then)."""
        self.computer_on = on
        self.approve_btn.set_off(not on)

    def _open_approval(self) -> None:
        pop = ApprovalPopover(self, self.approval, self.computer_on)
        pop.chosen.connect(self._set_approval)
        pop.turn_on.connect(self.turn_on_computer.emit)
        pop.learn_more.connect(self._learn_approval)
        pop.open_above(self.approve_btn, align_right=False)

    def _set_approval(self, key: str) -> None:
        if key == "full" and not self.full_confirmed:
            from PySide6.QtWidgets import QMessageBox

            if QMessageBox.question(self, tr("appr_full"), tr("full_confirm")) != QMessageBox.Yes:
                return
            self.full_confirmed = True
        self.approval = key
        self.approve_btn.set_key(key)

    def _learn_approval(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        doc = Path(__file__).resolve().parents[3] / "docs" / "adr" / "0012-computer-use.md"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(doc)))

    def _model_name(self) -> str:
        return _short(self.model_choice["model"], 28) if self.model_choice else ""

    def _levels(self) -> tuple[list[str], Callable[[str], str]]:
        """The levels the chosen model has, and their names: Lumen's 不思考 ... 最高, or an engine model's own
        (Codex: Low ... Ultra, as that model has them; Claude Code: Low ... Max) - an engine has no 不思考."""
        engine = (self.model_choice or {}).get("engine")
        if not engine:
            return list(LEVELS), level_name
        from codedoctor import engines

        listed = engines.models(engine)
        mine = next((m for m in listed if m["id"] == self.model_choice.get("id")), None)
        keys = mine["efforts"] if mine else sorted({e for m in listed for e in m["efforts"]}, key=engines.EFFORTS.index)
        return keys, lambda key: engines.effort_name(engine, key)

    def _open_thinking(self) -> None:
        keys, name = self._levels()
        pop = ThinkingPopover(self, self.level, self._model_name(), keys, name)
        pop.level_chosen.connect(lambda k: self._set_level(k, ""))
        pop.choose_model.connect(lambda: (pop.close(), self._open_models()))
        pop.open_above(self.model_btn)

    def _open_models(self) -> None:
        def ask(fill):
            def got(result):
                self.more = result
                try:
                    fill(result)
                except RuntimeError:  # the list was closed before the services answered
                    pass
            self.fetch_models(got)
        pop = model_list(self, self.choices, self.model_choice, self.more, ask if self.fetch_models else None)
        pop.chosen.connect(lambda c: self._set_model(c, ""))
        pop.open_above(self.model_btn)

    def _set_model(self, choice: dict | None, text: str) -> None:
        self.model_choice = choice
        levels = self._levels()[0]
        if levels and self.level not in levels:  # e.g. 不思考 for Codex, Ultra for a model without it
            self.level = "medium" if "medium" in levels else levels[0]
        self._show_model_btn()

    def _set_level(self, key: str | None, text: str) -> None:
        self.level = key
        self._show_model_btn()

    def _show_model_btn(self) -> None:
        self.model_btn.set_state(self._model_name(), self._levels()[1](self.level) if self.level else "", False)

    def options(self) -> dict:
        """What this message asks for besides its text: {"reasoning", "model", "approval"} (absent: each agent's own
        settings; 请求批准)."""
        out: dict = {}
        if (self.model_choice or {}).get("own"):  # the lead's own model, shown so that nobody has to guess
            if self.level:
                out["reasoning"] = self.level
        elif self.model_choice and self.model_choice.get("engine"):
            out["engine"] = self.model_choice["engine"]  # Claude Code / Codex on the user's subscription,
            if self.model_choice.get("id"):              # with its own model and level
                out["engine_model"] = self.model_choice["id"]
            if self.level:
                out["engine_effort"] = self.level
        else:
            if self.level:
                out["reasoning"] = self.level
            if self.model_choice:
                out["model"] = dict(self.model_choice)
        out["approval"] = self.approval
        if self.mentions:
            out["tools"] = list(self.mentions)
        return out

    # --- @ tools ---------------------------------------------------------------------------------------------------

    # --- phrases: "/" in an empty box, Ctrl+S keeps what is written ------------------------------------------------------

    def _maybe_phrases(self) -> None:
        if self.edit.toPlainText() in ("/", "、") and chat_tools.phrases():  # 、 is what the same key gives under a Chinese input method
            self._open_phrases()

    def _open_phrases(self, removing: bool = False) -> None:
        pop = ListPopover(self, 400)
        kept = chat_tools.phrases()
        pop.heading("删除哪一条？" if removing else "常用语")
        for text in kept:
            pop.row(text, _short(" ".join(text.split()), 44))
        if not kept:
            pop.note("还没有常用语。写好一段话，按 Ctrl+S 存下来，以后在空的输入框里打 / 就能调出来。")
        elif not removing:
            pop.row(None, "删除一条……")
        pop.chosen.connect(lambda value: self._phrase_chosen(value, removing))
        pop.finish()
        self._near_cursor(pop)
        self._phrase_pop = pop

    def _phrase_chosen(self, value, removing: bool) -> None:
        if value is None:
            self._open_phrases(True)
        elif removing:
            chat_tools.remove_phrase(value)
            self.edit.clear()
            self.hint.setText("已删除这条常用语")
        else:
            self.set_text(value)

    def _keep_phrase(self) -> None:
        text = self.edit.toPlainText().strip()
        if text:
            chat_tools.add_phrase(text)
            self.hint.setText("已存为常用语：在空的输入框里打 / 调出")

    def _near_cursor(self, pop) -> None:
        from PySide6.QtCore import QPoint

        pop.adjustSize()
        spot = self.edit.viewport().mapToGlobal(self.edit.cursorRect().topLeft())
        pop.move(spot + QPoint(-24, -pop.height() + 14))
        pop.show()

    def _open_mentions(self) -> None:
        """@ typed: the tools to call in; picking one removes the "@" and shows the tool as a chip."""
        pop = ListPopover(self, 340)
        pop.heading(tr("mention_head"))
        names = mentionable()
        for key in names:
            pop.row(key, MENTIONS[key], tr(f"{key}_sub"), key in self.mentions)
        if not names:
            pop.note(tr("mention_none"))
        pop.chosen.connect(self._mention_chosen)
        pop.finish()
        self._near_cursor(pop)
        self._mention_pop = pop

    def _mention_chosen(self, key) -> None:
        cur = self.edit.textCursor()
        cur.movePosition(cur.MoveOperation.Left, cur.MoveMode.KeepAnchor)
        if cur.selectedText() == "@":
            cur.removeSelectedText()
        self.add_mention(key)
        self.edit.setFocus()

    def add_mention(self, key: str) -> None:
        if key not in MENTIONS or key in self.mentions:
            return
        self.mentions.append(key)
        chip = MentionChip(MENTIONS[key])
        chip.setToolTip(tr(f"{key}_tip"))
        chip.clicked.connect(lambda _=False, k=key: self.remove_mention(k))
        self.mention_chips[key] = chip
        self.mention_row.insertWidget(self.mention_row.count() - 1, chip)
        self.mention_box.setVisible(True)
        self.mentions_changed.emit(list(self.mentions))

    def remove_mention(self, key: str) -> None:
        if key in self.mentions:
            self.mentions.remove(key)
        chip = self.mention_chips.pop(key, None)
        if chip is not None:
            chip.deleteLater()
        self.mention_box.setVisible(bool(self.mentions))
        self.mentions_changed.emit(list(self.mentions))

    # --- attachments -----------------------------------------------------------------------------------------------

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, tr("add_files"), "", "*.*")
        self.add_files(paths)

    def dragEnterEvent(self, e):  # noqa: N802 (Qt naming)
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):  # noqa: N802 (Qt naming)
        found = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if found:
            e.acceptProposedAction()
            self.add_files(found)

    def add_files(self, paths: list[str]) -> None:
        """Files picked, dropped or pasted: their text goes with the question."""
        total = sum(len(t) for _, t in self.attached)
        for p in paths:
            try:
                text = Path(p).read_bytes()[:ATTACH_MAX * 4].decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = Path(p).read_bytes()[:ATTACH_MAX * 4].decode("gbk")
                except UnicodeDecodeError:
                    self._attach_note(tr("att_not_text", name=Path(p).name))
                    continue
            except OSError as e:
                self._attach_note(tr("att_unreadable", name=Path(p).name, why=e))
                continue
            text = text[:ATTACH_MAX]
            if total + len(text) > ATTACH_TOTAL:
                self._attach_note(tr("att_too_much"))
                break
            total += len(text)
            self.attached.append((Path(p).name, text))
        self._show_attached()

    def _attach_note(self, text: str) -> None:
        self.hint.setText(text)

    def _show_attached(self) -> None:
        while self.attach_row.count():
            item = self.attach_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, (name, text) in enumerate(self.attached):
            chip = QPushButton(f"{_short(name, 28)}   ×")
            chip.setObjectName("FileChip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip(tr("att_remove", name=name, n=f"{len(text):,}"))
            chip.clicked.connect(lambda _=False, k=i: self._remove(k))
            self.attach_row.addWidget(chip)
        self.attach_row.addStretch(1)
        self.attach_box.setVisible(bool(self.attached))
        self._grow()

    def _remove(self, i: int) -> None:
        if 0 <= i < len(self.attached):
            self.attached.pop(i)
        self._show_attached()

    # --- text ------------------------------------------------------------------------------------------------------

    def set_running(self, on: bool) -> None:
        """The investigation shown here runs: the stop button appears next to send."""
        if self.stop_btn.isVisible() != on:
            self.stop_btn.setVisible(on)
            self.stop_btn.setEnabled(True)  # a new run: stoppable again
            self.stop_btn.setToolTip(tr("stop_tip"))

    def _stopping(self) -> None:
        """Clicked: it shows at once that the stop was taken (the task ends within a moment)."""
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("正在停止……")
        self.stop_btn.update()

    def set_text(self, text: str) -> None:
        self.edit.setPlainText(text)
        self.edit.setFocus()
        cur = self.edit.textCursor()
        cur.movePosition(cur.MoveOperation.End)
        self.edit.setTextCursor(cur)

    def _grow(self):
        doc_h = self.edit.document().size().height() * self.edit.fontMetrics().lineSpacing()
        hint = self.edit.fontMetrics().horizontalAdvance(self.edit.placeholderText())
        if not self.edit.toPlainText() and hint > self.edit.viewport().width() - 14:  # the hint wraps when the box is narrow: it must not be cut
            doc_h = max(doc_h, self.edit.fontMetrics().lineSpacing() * 2)
        self.edit.setFixedHeight(int(min(max(doc_h + 12, 40), 220)))
        self.send_btn.setEnabled(bool(self.edit.toPlainText().strip()))
        self.send_btn.update()
        self.send_btn.setToolTip(tr("send_tip"))

    def resizeEvent(self, e):
        """Everything fits: the least needed gives way first, and the model's name shortens."""
        super().resizeEvent(e)
        wide = self.width()
        self.mic_btn.setVisible(wide >= 440)
        self.approve_btn.setVisible(wide >= 340)
        self.model_btn.limit = max(96, wide - (250 if wide >= 440 else 200 if wide >= 340 else 110))
        self.model_btn._fit()
        self._grow()

    def _send(self):
        text = self.edit.toPlainText().strip()
        if not text:
            return
        for m in MENTION_RE.finditer(text):  # "@CodeCut" typed out works like the menu
            if m.group(1).lower() in mentionable():
                self.add_mention(m.group(1).lower())
        from codedoctor import makers

        for key in self.mentions:  # one pair of tools serves them all, so the words must say which one was picked from the menu
            if key in makers.MAKERS and f"@{key}" not in text.lower():
                text = f"@{MENTIONS[key]} {text}"
        for name, body in self.attached:  # the files go with the question, fenced as data
            text += f"\n\n附件 {name}：\n```\n{body}\n```"
        self._sent = (self.edit.toPlainText(), list(self.attached), list(self.mentions))  # what is kept if it is refused
        self.send.emit(text, self.mode_agent())
        if self._sent is None:  # give_back() put it all back during the send: nothing went out, the box keeps it
            return
        self._sent = None
        self.edit.clear()
        for key in list(self.mentions):  # called in for this message only
            self.remove_mention(key)
        self.attached = []
        self._show_attached()
        self.hint.setText("")

    def drop_draft(self) -> None:
        """Another conversation is on the screen: the words, files and @ tools of this box are not carried over into it
        (Haiku check item 9: they used to stay and go out with the other conversation's next message)."""
        self.edit.clear()
        self.attached = []
        self._show_attached()
        for key in list(self.mentions):
            self.remove_mention(key)

    def give_back(self) -> None:
        """The service refused what _send() sent (called from inside the send): the words, the files and the @ tools
        go back into the box, so nothing typed is lost. Does nothing outside a send."""
        if self._sent is None:
            return
        text, files, mentions = self._sent
        self._sent = None
        self.edit.setPlainText(text)
        self.attached = files
        self._show_attached()
        for key in mentions:
            self.add_mention(key)


class Banner(QFrame):
    def __init__(self, text: str, kind: str = "Banner", action: tuple[str, Callable] | None = None):
        """action: (button text, what it does) - a fix the user can apply right here."""
        super().__init__()
        self.setObjectName(kind)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        icon = label("⚠" if kind == "Banner" else "⛔", size=15)
        lay.addWidget(icon)
        self.text = label(text, wrap=True, size=13, color=C["amber"] if kind == "Banner" else C["red"])
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.text, 1)
        if action:
            fix = QPushButton(action[0])
            fix.setObjectName("Primary")
            fix.setCursor(Qt.PointingHandCursor)
            fix.clicked.connect(action[1])
            lay.addWidget(fix, 0, Qt.AlignVCenter)


class HomePage(QWidget):
    """A new chat: Lumen itself, the question and the message box, together in the middle. The project is chosen in the
    tree on the left, nothing here repeats it. Warnings only when something stops work (a missing key, code that may not
    go to the chosen service)."""
    new_chat = Signal()

    def __init__(self, project: str, root: str, modes, warnings: list[str], config_path: str | None = None):
        super().__init__()
        from codedoctor.desktop.team_ui import Figure

        outer = self.outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 14, 28, 22)
        outer.setSpacing(0)
        outer.addStretch(4)
        self.hello = QWidget()  # Lumen and the question: put away when an @ tool's window is above (set_compact)
        hl = QVBoxLayout(self.hello)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        mark = QHBoxLayout()
        mark.addStretch(1)
        self.figure = Figure("lumen", 136)
        mark.addWidget(self.figure)
        mark.addStretch(1)
        hl.addLayout(mark)
        hl.addSpacing(10)
        greet = label(tr("greeting"), "Greeting")
        greet.setAlignment(Qt.AlignCenter)
        greet.setToolTip(root)
        hl.addWidget(greet)
        hl.addSpacing(26)
        outer.addWidget(self.hello)
        col = QWidget()
        col.setMaximumWidth(760)
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(12)
        self.warn_box = QWidget()
        wl = QVBoxLayout(self.warn_box)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(8)
        cl.addWidget(self.warn_box)
        self._warnings = None
        self.set_warnings(warnings)
        self.composer = Composer(modes)
        cl.addWidget(self.composer)  # no suggestion chips: generic examples did not help
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(col, 10)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(6)

    def set_compact(self, on: bool) -> None:
        """A tool's window above: no greeting, the message box at the bottom."""
        self.hello.setVisible(not on)
        self.outer.setStretch(0, 1 if on else 4)
        self.outer.setStretch(self.outer.count() - 1, 0 if on else 6)
        self.outer.setContentsMargins(28, 8 if on else 14, 28, 16 if on else 22)

    def set_warnings(self, warnings: list) -> None:
        """Texts, or (text, (button text, action)) for a warning with a fix."""
        texts = [w if isinstance(w, str) else w[0] for w in warnings]
        if texts == self._warnings:
            return
        self._warnings = texts
        lay = self.warn_box.layout()
        while lay.count():
            lay.takeAt(0).widget().deleteLater()
        for w in warnings:
            lay.addWidget(Banner(w) if isinstance(w, str) else Banner(w[0], action=w[1]))
        self.warn_box.setVisible(bool(warnings))
