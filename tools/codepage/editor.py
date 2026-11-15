"""CodePage's window: the drag-and-drop builder (builder/index.html) in its own window, with real files behind it.

    editor.py [folder]         edit the page in that folder
    editor.py --watch <root>   follow whichever page under root changed last (Lumen opens it like this)

The builder also works in a plain browser; here it can read and write page.json directly, so that the AI and the person share it.
"""
from __future__ import annotations

import right_python

right_python.use('PySide6')

import os
import time
from pathlib import Path
import shutil
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QSettings, Qt, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

import codepage as core


def lumen_dir() -> Path | None:
    """Lumen's Scripts folder: $CODEDOCTOR_SCRIPTS, else code-doctor next to this tools folder, else PATH."""
    env = os.environ.get('CODEDOCTOR_SCRIPTS')
    for cand in ([Path(env)] if env else []) + [core.ROOT.parents[1] / '.venv' / ('Scripts' if os.name == 'nt' else 'bin'), core.ROOT.parents[1] / 'code-doctor' / '.venv' / ('Scripts' if os.name == 'nt' else 'bin')]:
        if (cand / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')).is_file():
            return cand
    found = shutil.which('codedoctor')
    return Path(found).parent if found else None


class Host(QObject):
    """What the page may ask of the computer: only the files the person points at, and handing the backend to Lumen."""

    said = Signal(str)    # a line from Lumen while it writes the backend
    ended = Signal(str)   # how it ended, in words

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.proc = None

    @Slot(str, result=bool)
    def backend(self, brief: str) -> bool:
        """Write the brief next to page.json and ask Lumen's team to build the backend in that folder."""
        scripts = lumen_dir()
        folder = self.window.folder
        if scripts is None or folder is None or self.proc is not None:
            return False
        (folder / 'BACKEND.md').write_text(brief + '\n', encoding='utf-8')
        text = f'{brief}\n\n（需求也写在 {folder / "BACKEND.md"}。页面用 @CodePage 改，项目文件夹：{folder}）'
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(folder))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._done)
        self.proc.errorOccurred.connect(self._failed)
        self.proc.start(str(scripts / ('codedoctor.exe' if os.name == 'nt' else 'codedoctor')), ['fix', '--with', 'codepage', '--no-window', text])
        self.said.emit(f'需求写在 {folder / "BACKEND.md"}，Lumen 开始做了。')
        return True

    def _read(self) -> None:
        if self.proc is not None:
            text = bytes(self.proc.readAllStandardOutput()).decode('utf-8', 'replace').rstrip()
            if text:
                self.said.emit(text)

    def _failed(self, error) -> None:
        """Could not even start: the button must not stay "busy" for ever."""
        if self.proc is not None and error == QProcess.FailedToStart:
            self.proc = None
            self.ended.emit('启动不了：codedoctor 没有跑起来')

    def _done(self, code, _status=None) -> None:
        self._read()
        self.proc = None
        self.ended.emit('完成：后端写好了，详情见上面' if code == 0 else '还不能开始：这个文件夹要先在 Lumen 里打开成项目' if code == 2 else '没有做完，详情见上面')

    def stop(self) -> None:
        if self.proc is not None:
            self.proc.kill()

    @Slot(str, result=str)
    def save(self, text: str) -> str:
        folder = self.window.folder
        if folder is None:
            chosen = QFileDialog.getExistingDirectory(self.window, '存到哪个文件夹', '', QFileDialog.ShowDirsOnly | QFileDialog.DontUseNativeDialog)
            if not chosen:
                return ''
            folder = self.window.folder = Path(chosen)
        (folder / 'page.json').write_text(text, encoding='utf-8')
        return str(folder / 'page.json')

    @Slot(str, result=str)
    def exportHtml(self, html: str) -> str:  # noqa: N802 (called from JavaScript)
        start = str((self.window.folder or Path.home()) / 'index.html')
        path, _ = QFileDialog.getSaveFileName(self.window, '导出网页', start, '网页 (*.html)', options=QFileDialog.DontUseNativeDialog)
        if not path:
            return ''
        Path(path).write_text(html, encoding='utf-8')
        return path

    @Slot(result=str)
    def open(self) -> str:
        chosen = QFileDialog.getExistingDirectory(self.window, '打开有 page.json 的文件夹', '', QFileDialog.ShowDirsOnly | QFileDialog.DontUseNativeDialog)
        if not chosen or not (Path(chosen) / 'page.json').is_file():
            return ''
        self.window.folder = Path(chosen)
        return (Path(chosen) / 'page.json').read_text(encoding='utf-8-sig')

    @Slot(result=str)
    def pageFile(self) -> str:  # noqa: N802
        self.window.follow()
        folder = self.window.folder
        if folder is None or not (folder / 'page.json').is_file():
            return ''
        try:
            return (folder / 'page.json').read_text(encoding='utf-8-sig')
        except OSError:
            return ''

    @Slot(str)
    def preview(self, html: str) -> None:
        path = Path(tempfile.gettempdir()) / 'codepage-preview.html'
        path.write_text(html, encoding='utf-8')
        # one preview window, reused: every click used to open another full browser window and they piled up
        view = self.window.previews[0] if self.window.previews else None
        if view is None:
            view = QWebEngineView()
            view.setWindowTitle('预览')
            view.resize(1100, 760)
            self.window.previews.append(view)
        view.load(QUrl.fromLocalFile(str(path)))
        view.show()
        view.raise_()


class Window(QMainWindow):
    def __init__(self, folder: Path | None, watch: Path | None):
        super().__init__()
        self.setWindowTitle('CodePage')
        self.resize(1360, 860)
        self.prefs = QSettings('Lumen', 'CodePage')
        self.watch = watch
        last = self.prefs.value('last', '')
        self.folder = folder or (Path(last) if last and (Path(last) / 'page.json').is_file() and watch is None else None)
        self.previews: list = []
        self._scanned = -99.0
        self.view = QWebEngineView()
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.channel = QWebChannel(self)
        self.host = Host(self)
        self.channel.registerObject('host', self.host)
        self.view.page().setWebChannel(self.channel)
        self.setCentralWidget(self.view)
        self.view.loadFinished.connect(self._translate)
        self.view.load(QUrl.fromLocalFile(str(core.ROOT / 'builder' / 'index.html')))

    def _translate(self, ok: bool) -> None:
        """The builder's words in Lumen's language (i18n.py + en.json); 中文 changes nothing."""
        if not ok:
            return
        try:
            import i18n
            script = i18n.web_script(Path(__file__).resolve().parent)
        except ImportError:
            return
        if script:
            self.view.page().runJavaScript(script)

    def follow(self) -> None:
        """Walking a whole tree every 1.5 s froze the window: at most every 10 s."""
        if self.watch is None:
            return
        now = time.monotonic()
        if now - self._scanned < 10.0:
            return
        self._scanned = now
        best, when = None, 0.0
        for base, dirs, files in os.walk(self.watch):
            if len(Path(base).relative_to(self.watch).parts) > 3:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'venv', '__pycache__', 'out')]
            if 'page.json' in files:
                try:
                    t = (Path(base) / 'page.json').stat().st_mtime
                except OSError:
                    continue
                if t > when:
                    best, when = Path(base), t
        if best is not None:
            self.folder = best

    def closeEvent(self, e):
        self.host.stop()
        if self.folder is not None:
            self.prefs.setValue('last', str(self.folder))
        super().closeEvent(e)


def main() -> int:
    args = sys.argv[1:]
    watch = None
    if len(args) == 2 and args[0] == '--watch':
        watch, args = Path(args[1]).resolve(), []
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--allow-file-access-from-files')
    app = QApplication(sys.argv[:1])
    try:  # a dark Windows made unstyled text white on white (内容看不见); these windows are light, whatever the system is
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except (AttributeError, RuntimeError):
        pass
    win = Window(Path(args[0]).resolve() if args else None, watch)
    import embed
    embed.show(win)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())

