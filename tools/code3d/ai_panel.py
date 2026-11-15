"""AI 建模: a small window beside the editor that asks Lumen's team to work on this project.

It runs `codedoctor fix --with code3d --no-window "<request>"` in the project's folder. The agents write scene.py and render
with Code3D's own commands; the editor follows those files, so every change shows up as it happens. The folder must belong
to a Lumen project (whose models the user chose there); otherwise the panel says so and offers to open Lumen.
"""
from __future__ import annotations

import codecs
import os
from pathlib import Path
import shutil

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

import code3d as core


def lumen_dir() -> Path | None:
    """Lumen's Scripts folder: $CODEDOCTOR_SCRIPTS, else code-doctor next to this tools folder, else PATH."""
    env = os.environ.get('CODEDOCTOR_SCRIPTS')
    for cand in ([Path(env)] if env else []) + [core.ROOT.parents[1] / '.venv' / ('Scripts' if os.name == 'nt' else 'bin'), core.ROOT.parents[1] / 'code-doctor' / '.venv' / ('Scripts' if os.name == 'nt' else 'bin')]:
        if (cand / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')).is_file():
            return cand
    found = shutil.which('codedoctor')
    return Path(found).parent if found else None


class AIPanel(QWidget):
    def __init__(self, editor):
        super().__init__(editor, Qt.Tool)
        from editor import button

        self.editor = editor
        self.proc = None
        self.setWindowTitle('AI 建模 · Code3D')
        self.resize(430, 560)
        self.setObjectName('aiPanel')
        self.setStyleSheet('QWidget#aiPanel{background:#ffffff;}')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        title = QLabel('让 AI 帮你做')
        title.setObjectName('title')
        lay.addWidget(title)
        sub = QLabel('Lumen 的团队来写这个项目的代码，自己渲染、自己看图再改，主窗口里实时显示。开始前会先保存你的代码。')
        sub.setObjectName('muted')
        sub.setWordWrap(True)
        lay.addWidget(sub)
        self.log = QPlainTextEdit()
        self.log.setObjectName('console')
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('AI 的每一步会显示在这里。')
        lay.addWidget(self.log, 1)
        self.ask = QPlainTextEdit()
        self.ask.setObjectName('console')
        self.ask.setPlaceholderText('例如：做一盏黄铜台灯放在木桌上，傍晚的暖光，浅景深。')
        self.ask.setFixedHeight(96)
        lay.addWidget(self.ask)
        row = QHBoxLayout()
        self.status = QLabel('')
        self.status.setObjectName('muted')
        row.addWidget(self.status, 1)
        self.stopButton = button('停止', self.stop)
        self.stopButton.setVisible(False)
        row.addWidget(self.stopButton)
        self.openButton = button('打开 Lumen', self.open_lumen)
        self.openButton.setVisible(False)
        row.addWidget(self.openButton)
        self.sendButton = button('交给 AI', self.send, 'primary')
        row.addWidget(self.sendButton)
        lay.addLayout(row)

    def say(self, text: str) -> None:
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(text if text.endswith('\n') else text + '\n')
        self.log.moveCursor(QTextCursor.End)

    def send(self) -> None:
        request = self.ask.toPlainText().strip()
        if not request or self.proc is not None:
            return
        scripts = lumen_dir()
        if scripts is None:
            self.say('没有找到 Lumen（应在 D:\\CodeDoctor\\code-doctor）。')
            return
        if self.editor.dirty and not self.editor.save():
            self.say('先保存代码，AI 才能接着改。')
            return
        folder = self.editor.folder
        if folder is None:
            self.say('先打开或新建一个项目。')
            return
        text = f'{request}\n\n（用 @Code3D 做，项目文件夹：{folder.name}，在 {folder}）'
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(folder))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.failed)
        self._dec = codecs.getincrementaldecoder('utf-8')('replace')  # a character cut between two reads stays whole
        self.say('你：' + request)
        self.ask.clear()
        self.status.setText('AI 正在做…')
        self.sendButton.setEnabled(False)
        self.stopButton.setVisible(True)
        self.openButton.setVisible(False)
        self.proc.start(str(scripts / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')), ['fix', '--with', 'code3d', '--no-window', text])

    def read(self) -> None:
        if self.proc is not None:
            self.say(self._dec.decode(bytes(self.proc.readAllStandardOutput())).rstrip())

    def failed(self, error) -> None:
        """The program could not even start: the panel must not stay "busy" for ever."""
        if self.proc is not None and error == QProcess.FailedToStart:
            self.proc = None
            self.status.setText('启动不了：codedoctor 没有跑起来')
            self.say('启动不了：codedoctor 没有跑起来。')
            self.sendButton.setEnabled(True)
            self.stopButton.setVisible(False)

    def finished(self, code, _status=None) -> None:
        self.read()
        self.status.setText('完成' if code == 0 else '还不能开始' if code == 2 else '没有完成（详情见上面）')
        self.openButton.setVisible(code == 2)
        self.proc = None
        self.sendButton.setEnabled(True)
        self.stopButton.setVisible(False)
        self.editor.follow_tick()

    def stop(self) -> None:
        if self.proc is not None:
            self.proc.kill()
            self.say('已停止。已经做完的修改留在项目里。')

    def open_lumen(self) -> None:
        scripts = lumen_dir()
        exe = scripts / ('codedoctor-desktop.exe' if os.name == 'nt' else 'codedoctor-desktop') if scripts else None
        if exe and exe.is_file():
            QProcess.startDetached(str(exe), [])

    def closeEvent(self, e):
        self.stop()
        super().closeEvent(e)
