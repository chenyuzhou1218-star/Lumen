"""AI: asks Lumen's team to work on this project (the page draws it as a panel on the right, kit/AIPanel.jsx).

It runs `codedoctor fix --with codesound --no-window "<request>"` in the project's folder. The agents write the project's code and run it
with CodeSound's own commands; the editor follows those files, so every change shows up as it happens. The folder must belong
to a Lumen project (whose models the user chose there); otherwise the panel says so and offers to open Lumen.
"""
from __future__ import annotations

import codecs
import os
from pathlib import Path
import shutil

from PySide6.QtCore import QProcess, QProcessEnvironment

import codesound as core

TOOL = 'codesound'
NAME = 'CodeSound'
SUB = 'Lumen 的团队来写这个项目的代码，自己合成、自己量声音再改，主窗口里实时显示。开始前会先保存你的代码。'
HINT = '例如：写一首两分钟的古风战曲，开头只有战鼓，后面号角和合唱加入。'


def lumen_dir() -> Path | None:
    """Lumen's Scripts folder: $CODEDOCTOR_SCRIPTS, else code-doctor next to this tools folder, else PATH."""
    env = os.environ.get('CODEDOCTOR_SCRIPTS')
    for cand in ([Path(env)] if env else []) + [core.ROOT.parents[1] / '.venv' / ('Scripts' if os.name == 'nt' else 'bin'), core.ROOT.parents[1] / 'code-doctor' / '.venv' / ('Scripts' if os.name == 'nt' else 'bin')]:
        if (cand / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')).is_file():
            return cand
    found = shutil.which('codedoctor')
    return Path(found).parent if found else None


class AIRunner:
    """The work behind the panel. editor: the tool's project (folder, dirty, save(), follow_tick(), emit)."""

    def __init__(self, editor):
        self.editor = editor
        self.proc: QProcess | None = None
        self.log: list = []
        self.status = 'Ctrl+Enter 交给 AI'
        self.light = ''
        self.can_open = False

    def state(self) -> dict:
        return {'log': self.log, 'status': self.status, 'light': self.light, 'busy': self.proc is not None, 'can_open': self.can_open}

    def push(self, **extra) -> None:
        self.editor.emit('ai', status=self.status, light=self.light, busy=self.proc is not None, can_open=self.can_open, **extra)

    def say(self, text: str, me: bool = False) -> None:
        lines = [{'text': t, 'me': me} for t in text.rstrip('\n').split('\n')] if text else []
        self.log += lines
        self.log = self.log[-2000:]
        self.push(add=lines)

    def send(self, request: str) -> dict:
        request = (request or '').strip()
        if not request or self.proc is not None:
            return {'ok': False}
        scripts = lumen_dir()
        if scripts is None:
            self.light = 'error'
            self.say('没有找到 Lumen（应在 D:\\CodeDoctor\\code-doctor）。')
            return {'ok': False}
        if self.editor.dirty and not self.editor.save():
            self.light = 'error'
            self.say('先保存代码，AI 才能接着改。')
            return {'ok': False}
        folder = self.editor.folder
        if folder is None:
            self.light = 'error'
            self.say('先打开或新建一个项目。')
            return {'ok': False}
        text = f'{request}\n\n（用 @{NAME} 做，项目文件夹：{folder.name}，在 {folder}）'
        self.proc = QProcess()
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(folder))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.failed)
        self._dec = codecs.getincrementaldecoder('utf-8')('replace')  # a character cut between two reads stays whole
        self.status, self.light, self.can_open = 'AI 正在做…', 'busy', False
        self.say('你：' + request, me=True)
        self.proc.start(str(scripts / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')), ['fix', '--with', TOOL, '--no-window', text])
        return {'ok': True}

    def read(self) -> None:
        if self.proc is not None:
            self.say(self._dec.decode(bytes(self.proc.readAllStandardOutput())).rstrip())

    def failed(self, error) -> None:
        """The program could not even start: the panel must not stay "busy" for ever."""
        if self.proc is not None and error == QProcess.FailedToStart:
            self.proc = None
            self.status, self.light, self.can_open = '启动不了：codedoctor 没有跑起来', 'error', False
            self.say('启动不了：codedoctor 没有跑起来。')
            self.push()

    def finished(self, code, _status=None) -> None:
        self.read()
        self.proc = None
        self.status = '完成' if code == 0 else '还不能开始：这个文件夹要先在 Lumen 里打开成项目' if code == 2 else '没有完成，详情见上面'
        self.light = 'ok' if code == 0 else 'error'
        self.can_open = code == 2
        self.push()
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
