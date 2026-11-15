"""AI 剪辑: a small window beside the editor that asks Code Doctor's agents to edit this project.

It runs `codedoctor fix --with codecut --no-window "<request>"` in the project's folder. The agents edit the project file
with CodeCut's own commands (codecut.py split / text / update / ...), and the editor follows that file (EditorWindow.
follow) so every change shows up in the timeline as it happens. The folder must belong to a Code Doctor project (whose
models the user chose there); otherwise the panel says so and offers to open Code Doctor.
"""
from __future__ import annotations

import codecs
import os
from pathlib import Path
import shutil

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

import codecut as cut


def codedoctor_dir() -> Path | None:
    """Code Doctor's Scripts folder: $CODEDOCTOR_SCRIPTS, else code-doctor next to this tools folder, else PATH."""
    env = os.environ.get('CODEDOCTOR_SCRIPTS')
    for cand in ([Path(env)] if env else []) + [cut.ROOT.parents[1] / '.venv' / ('Scripts' if os.name == 'nt' else 'bin'), cut.ROOT.parents[1] / 'code-doctor' / '.venv' / ('Scripts' if os.name == 'nt' else 'bin')]:
        if (cand / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')).is_file():
            return cand
    found = shutil.which('codedoctor')
    return Path(found).parent if found else None


class AIPanel(QWidget):
    def __init__(self, editor):
        super().__init__(editor, Qt.Tool)
        self.editor = editor
        self.proc = None
        self.setWindowTitle('AI 剪辑 · CodeCut')
        self.resize(430, 560)
        self.setObjectName('aiPanel')
        self.setStyleSheet('QWidget#aiPanel{background:#ffffff;}')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        title = QLabel('让 AI 帮你剪')
        title.setObjectName('panelTitle')
        lay.addWidget(title)
        sub = QLabel('Lumen 的智能体用 CodeCut 剪这个项目，每一步都会在主窗口的时间线里实时出现。'
                     '开始前会先保存你的项目；不满意可以用 codedoctor undo（或 Lumen 窗口里的撤销）把项目文件改回去。')
        sub.setObjectName('muted')
        sub.setWordWrap(True)
        lay.addWidget(sub)
        self.log = QPlainTextEdit()
        self.log.setObjectName('console')
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('AI 的每一步会显示在这里。')
        lay.addWidget(self.log, 1)
        self.ask = QPlainTextEdit()
        self.ask.setPlaceholderText('例如：把开头剪到 5 秒，在 0 秒加标题“我的旅行”，配乐音量调到 30%，再导出成 final.mp4')
        self.ask.setFixedHeight(96)
        lay.addWidget(self.ask)
        row = QHBoxLayout()
        self.status = QLabel('')
        self.status.setObjectName('muted')
        row.addWidget(self.status, 1)
        from editor import button
        self.stopButton = button('停止', self.stop, 'subtle')
        self.stopButton.setVisible(False)
        row.addWidget(self.stopButton)
        self.openButton = button('打开 Lumen', self.open_code_doctor, 'subtle')
        self.openButton.setVisible(False)
        row.addWidget(self.openButton)
        self.sendButton = button('交给 AI', self.send, '', True)
        self.sendButton.setFixedWidth(96)
        row.addWidget(self.sendButton)
        lay.addLayout(row)

    def say(self, text: str) -> None:
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(text if text.endswith('\n') else text + '\n')
        self.log.moveCursor(QTextCursor.End)

    def send(self):
        request = self.ask.toPlainText().strip()
        if not request or self.proc is not None:
            return
        scripts = codedoctor_dir()
        if scripts is None:
            self.say('没有找到 Lumen（应在 D:\\CodeDoctor\\code-doctor）。')
            return
        model = self.editor.model
        if model.dirty or not model.path.exists():  # the agents edit the file: your edits go there first
            if not self.editor.save_project():
                self.say('先保存项目，AI 才能在项目文件上剪辑。')
                return
        path = model.path
        self.editor.follow(path.parent, path)
        text = f'{request}\n\n（用 @CodeCut 剪辑的项目文件：{path.name}，在 {path.parent}）'
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(path.parent))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.failed)
        self._dec = codecs.getincrementaldecoder('utf-8')('replace')  # a character cut between two reads stays whole
        self.say('你：' + request)
        self.ask.clear()
        self.status.setText('AI 正在剪辑…')
        self.sendButton.setEnabled(False)
        self.stopButton.setVisible(True)
        self.openButton.setVisible(False)
        self.proc.start(str(scripts / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')), ['fix', '--with', 'codecut', '--no-window', text])

    def read(self):
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

    def finished(self, code, _status=None):
        self.read()
        self.status.setText('完成' if code == 0 else '没有完成（详情见上面）' if code != 2 else '还不能开始')
        if code == 2:
            self.openButton.setVisible(True)
        self.proc = None
        self.sendButton.setEnabled(True)
        self.stopButton.setVisible(False)
        self.editor.follow_tick()  # the last edit on screen now, not at the next tick

    def stop(self):
        if self.proc is not None:
            self.proc.kill()
            self.say('已停止。已经做完的修改留在项目里；要改回去可以运行 codedoctor undo。')

    def open_code_doctor(self):
        scripts = codedoctor_dir()
        exe = scripts / ('codedoctor-desktop.exe' if os.name == 'nt' else 'codedoctor-desktop') if scripts else None
        if exe and exe.is_file():
            QProcess.startDetached(str(exe), [])

    def closeEvent(self, e):
        self.stop()
        super().closeEvent(e)
