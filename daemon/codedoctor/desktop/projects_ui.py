"""Projects in the window (2026-11-03), after Codex's desktop app: the strip above the composer - 选择项目 (the
project this chat works in: any folder opened before, or a new one) and 此计算机 (where it runs) - and the 创建项目
dialog, a white card over the window blurred behind it: a name, the source folder, 取消 / 创建项目."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                               QVBoxLayout, QWidget)

from codedoctor.desktop import icons, projects
from codedoctor.desktop.i18n import tr
from codedoctor.desktop.theme import FONT_FAMILY

INK = QColor("#0d0d0d")
GREY = QColor("#8f8f8f")
TEXT = QColor("#1f1f1f")


def _font(px: float, weight: int = QFont.Normal) -> QFont:
    f = QFont(FONT_FAMILY)
    f.setPixelSize(int(px))
    f.setWeight(weight)
    return f


class StripButton(QAbstractButton):
    """An icon and a word on the strip; grey when it is a prompt (选择项目), dark when it names something."""

    def __init__(self, kind: str, text: str, prompt: bool = False):
        super().__init__()
        self.kind, self.text_, self.prompt = kind, text, prompt
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self._fit()

    def set_text(self, text: str, prompt: bool) -> None:
        self.text_, self.prompt = text, prompt
        self._fit()
        self.update()

    def _fit(self) -> None:
        from PySide6.QtGui import QFontMetrics

        self.setFixedWidth(QFontMetrics(_font(14)).horizontalAdvance(self.text_) + 46)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse() and self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#e9e9e9"))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 2, -1, -2), 8, 8)
        color = GREY if self.prompt else TEXT
        icons.paint(p, self.kind, QRectF(10, (self.height() - 17) / 2, 17, 17), color, 1.5)
        p.setPen(color)
        p.setFont(_font(14))
        p.drawText(QRectF(34, 0, self.width() - 36, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text_)
        p.end()


class ProjectStrip(QWidget):
    """选择项目 | 此计算机. `switch(config)`: work in that project; `create()`: the 创建项目 dialog."""
    switch = Signal(str)
    create = Signal()

    def __init__(self, config_path: str | None, root: str):
        super().__init__()
        self.config_path = config_path
        lay = QHBoxLayout(self)
        lay.setContentsMargins(30, 6, 30, 6)
        lay.setSpacing(6)
        here = next((i for i in projects.load() if config_path and projects._same(i["config"], config_path)), None)
        workspace = Path(root).resolve() == projects.workspace().resolve() if root else True
        name = (here or {}).get("label") or (here or {}).get("name") or Path(root).name
        self.project = StripButton("folder", tr("pick_project") if workspace else name, prompt=workspace)
        self.project.setToolTip(root)
        self.project.clicked.connect(self._menu)
        self.machine = StripButton("laptop", tr("this_computer"))
        self.machine.setToolTip(tr("this_computer_tip"))
        self.machine.setEnabled(False)  # the only place it runs today: a name, not a choice
        lay.addWidget(self.project)
        lay.addWidget(self.machine)
        lay.addStretch(1)

    def _menu(self) -> None:
        menu = QMenu(self)
        for item in projects.load()[:20]:
            if not Path(item["config"]).exists():
                continue
            current = bool(self.config_path) and projects._same(item["config"], self.config_path)
            act = menu.addAction(icons.icon("folder", "#3b4250", 16), (item.get("label") or item["name"]) + ("  ✓" if current else ""))
            act.setToolTip(item.get("root") or "")
            act.setEnabled(not current)
            act.triggered.connect(lambda _=False, c=item["config"]: self.switch.emit(c))
        menu.addSeparator()
        menu.addAction(icons.icon("plus", "#3b4250", 16), tr("new_project_item")).triggered.connect(self.create.emit)
        menu.exec(self.project.mapToGlobal(QPoint(0, self.project.height() + 4)))


class Dock(QWidget):
    """The strip and the composer as one piece: a light grey band behind the strip that runs on under the composer's
    rounded top, so the composer sits on it."""

    def __init__(self, strip: QWidget, composer: QWidget):
        super().__init__()
        self.strip = strip
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(strip)
        lay.addWidget(composer)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#e8e8e8"), 1))
        p.setBrush(QColor("#f4f4f4"))
        p.drawRoundedRect(QRectF(18.5, 0.5, self.width() - 37, self.strip.height() + 34), 16, 16)
        p.end()


# --- 创建项目 -----------------------------------------------------------------------------------------------------------

class _NameField(QWidget):
    """A folder icon, a hairline, the name: one rounded field whose border turns blue while typing."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(48)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(52, 0, 12, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(tr("project_name"))
        self.edit.setStyleSheet("QLineEdit { border: none; background: transparent; font-size: 15px; padding: 0; }")
        self.edit.textChanged.connect(lambda _: self.update())
        lay.addWidget(self.edit)
        self.setFocusProxy(self.edit)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        focus = self.edit.hasFocus()
        p.setPen(QPen(QColor("#2f6bff") if focus else QColor("#d9d9d9"), 1.4 if focus else 1))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        icons.paint(p, "folder", QRectF(15, 15, 18, 18), QColor("#3b4250"), 1.5)
        p.setPen(QPen(QColor("#e5e5e5"), 1))
        p.drawLine(46, 8, 46, self.height() - 8)
        p.end()


class _Source(QWidget):
    """源文件夹: 在此电脑上添加文件夹 and 添加, or the folder chosen (click 添加 again to change it)."""
    chosen = Signal(str)

    def __init__(self):
        super().__init__()
        self.folder = ""
        self.setFixedHeight(124)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 18, 16, 18)
        lay.setSpacing(10)
        self.line = QLabel()
        self.line.setAlignment(Qt.AlignCenter)
        self.line.setTextFormat(Qt.RichText)
        self.line.setStyleSheet("font-size: 15px; color: #5d5d5d; background: transparent;")
        self.line.setWordWrap(True)
        lay.addWidget(self.line)
        self.add = QPushButton("  " + tr("add"))
        self.add.setIcon(icons.icon("folder_plus", "#1f1f1f", 18))
        self.add.setCursor(Qt.PointingHandCursor)
        self.add.setStyleSheet("QPushButton { background: #f1f1f1; border: none; border-radius: 10px; padding: 6px 14px;"
                               " font-size: 14px; color: #1f1f1f; } QPushButton:hover { background: #e6e6e6; }")
        self.add.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.add)
        row.addStretch(1)
        lay.addLayout(row)
        self._show()

    def _show(self) -> None:
        if self.folder:
            self.line.setText(f"<b style='color:#1f1f1f'>{Path(self.folder).name}</b><br>"
                              f"<span style='font-size:12px;color:#8f8f8f'>{self.folder}</span>")
            self.add.setText("  " + tr("change"))
        else:
            self.line.setText(tr("add_folder_here"))
            self.add.setText("  " + tr("add"))

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self.window(), tr("add_folder_here_plain"), self.folder or str(Path.home()))
        if folder:
            self.folder = folder
            self._show()
            self.chosen.emit(folder)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#e5e5e5"), 1))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        p.end()


class _Card(QWidget):
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(18, 18, -18, -18)
        p.setPen(Qt.NoPen)
        for i in range(14, 0, -1):  # a soft shadow: many faint layers, no visible ring
            p.setBrush(QColor(0, 0, 0, 2))
            p.drawRoundedRect(r.adjusted(-i, -i + 8, i, i + 8), 22 + i, 22 + i)
        p.setPen(QPen(QColor("#e5e5e5"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(r, 22, 22)
        p.end()


class CreateProject(QWidget):
    """The 创建项目 dialog over the window, which is blurred behind it. exec() -> the new project's configuration
    path, or None (取消, ×, Esc)."""

    def __init__(self, window: QWidget, setup: dict | None = None):
        super().__init__(window)
        self.setup = setup
        self.result: str | None = None
        self.loop = QEventLoop()
        shot = window.grab().toImage()
        small = shot.scaled(max(1, shot.width() // 10), max(1, shot.height() // 10), Qt.IgnoreAspectRatio,
                            Qt.SmoothTransformation)
        self.backdrop = QPixmap.fromImage(small.scaled(shot.width(), shot.height(), Qt.IgnoreAspectRatio,
                                                       Qt.SmoothTransformation))
        self.backdrop.setDevicePixelRatio(shot.devicePixelRatio())
        self.card = _Card(self)
        self.card.setFixedSize(680, 452)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(46, 40, 46, 40)
        lay.setSpacing(14)
        top = QHBoxLayout()
        title = QLabel(tr("create_project"))
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #0d0d0d; background: transparent;")
        top.addWidget(title)
        top.addStretch(1)
        close = QPushButton()
        close.setIcon(icons.icon("close", "#5d5d5d", 18))
        close.setFixedSize(30, 30)
        close.setCursor(Qt.PointingHandCursor)
        close.setStyleSheet("QPushButton { border: none; border-radius: 15px; background: transparent; }"
                            " QPushButton:hover { background: #f0f0f0; }")
        close.clicked.connect(self._cancel)
        top.addWidget(close)
        lay.addLayout(top)
        lay.addSpacing(4)
        self.name = _NameField()
        lay.addWidget(self.name)
        lay.addSpacing(6)
        head = QLabel(tr("source_folder"))
        head.setStyleSheet("font-size: 15px; font-weight: 600; color: #1f1f1f; background: transparent;")
        lay.addWidget(head)
        self.source = _Source()
        self.source.chosen.connect(self._folder_chosen)
        lay.addWidget(self.source)
        self.error = QLabel("")
        self.error.setStyleSheet("color: #c8463d; font-size: 13px; background: transparent;")
        lay.addWidget(self.error)
        lay.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        cancel = QPushButton(tr("cancel"))
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet("QPushButton { border: none; background: transparent; color: #5d5d5d; font-size: 15px;"
                             " padding: 8px 16px; border-radius: 12px; } QPushButton:hover { background: #f2f2f2; }")
        cancel.clicked.connect(self._cancel)
        self.ok = QPushButton(tr("create_project"))
        self.ok.setCursor(Qt.PointingHandCursor)
        self.ok.setStyleSheet("QPushButton { border: none; background: #0d0d0d; color: white; font-size: 15px;"
                              " font-weight: 600; padding: 9px 20px; border-radius: 13px; }"
                              " QPushButton:hover { background: #2b2b2b; }"
                              " QPushButton:disabled { background: #bdbdbd; }")
        self.ok.clicked.connect(self._create)
        bottom.addWidget(cancel)
        bottom.addSpacing(8)
        bottom.addWidget(self.ok)
        lay.addLayout(bottom)
        self.name.edit.textChanged.connect(lambda _: self._enable())
        self._enable()
        self.setGeometry(window.rect())  # covers the window; the card in its middle
        self._place()

    def _place(self) -> None:
        if getattr(self, "card", None) is None:  # grabbing the window lays this out before the card exists
            return
        self.card.move((self.width() - self.card.width()) // 2, (self.height() - self.card.height()) // 2 - 20)

    def resizeEvent(self, e):
        self._place()
        super().resizeEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.backdrop)
        p.fillRect(self.rect(), QColor(255, 255, 255, 70))  # blurred and a little lighter: the dialog stands out
        p.end()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._cancel()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.ok.isEnabled():
            self._create()
        else:
            super().keyPressEvent(e)

    def _folder_chosen(self, folder: str) -> None:
        if not self.name.edit.text().strip():
            self.name.edit.setText(Path(folder).name)
        self._enable()

    def _enable(self) -> None:
        self.ok.setEnabled(bool(self.name.edit.text().strip() and self.source.folder))

    def _create(self) -> None:
        try:
            path = projects.for_folder(self.source.folder, self.setup, label=self.name.edit.text().strip())
        except Exception as e:
            self.error.setText(f"{type(e).__name__}: {e}"[:200])
            return
        self.result = str(path)
        self._close()

    def _cancel(self) -> None:
        self.result = None
        self._close()

    def _close(self) -> None:
        self.hide()
        self.loop.quit()

    def exec(self) -> str | None:
        self.show()
        self.raise_()
        self.name.setFocus()
        self.loop.exec()
        self.deleteLater()
        return self.result

