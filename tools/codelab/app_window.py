"""A window for a tool that is otherwise a command line: open a project, edit its file, press a button, see what came out.

CodeGame, CodeDeck, CodeData, CodeCAD, CodeLab and CodeFilm each carry this same file; their editor.py says what is
different (the Config). The window is a web page (ui/, built into ui_dist/; the same page in all six, kit/ProjectApp.jsx)
in an empty Qt frame (webshell.py); this file is the program behind it, reached over the page's bridge.
    editor.py [folder]         a project
    editor.py --watch <root>   follows whichever project under root changed last (Lumen opens it like this)
    --mode light|dark          浅色 or 深色; without it the window follows Lumen's setting
With nothing to open, the first example opens: a window should show something from the first moment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import Callable

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QTimer

import webshell

GLYPH = {'CodeGame': 'game', 'CodeDeck': 'slides', 'CodeData': 'chart', 'CodeCAD': 'cube', 'CodeLab': 'flask', 'CodeFilm': 'film'}


@dataclass
class Action:
    label: str
    args: list            # before the folder comes the command, {folder} is replaced
    primary: bool = False
    then_open: str = ''   # a file in the project to open when it worked
    asks: list = field(default_factory=list)  # questions the page asks first: {key, label, multiline, required, placeholder}


@dataclass
class Config:
    name: str
    tool: Path                                  # the tool's main .py
    blurb: str
    mains: tuple                                # the file that marks a project; the first found is what is edited
    actions: list
    opens: list = field(default_factory=list)   # (label, path in the project)
    new_kinds: list = field(default_factory=list)  # (label, extra args of init)
    add_files: str = ''                         # a filter: files that can be added to the project (data)
    describe: Callable | None = None            # answer -> lines to show
    log_mode: bool = False                      # CodeLab: a log file instead of a project
    glyph: str = ''                             # the drawing in the tool's mark; by name when empty


def file_url(path: Path) -> str:
    """A picture's address for the page, changed whenever the file is, so a new render shows at once."""
    try:
        stamp = int(path.stat().st_mtime * 1000)
    except OSError:
        stamp = 0
    return path.resolve().as_uri() + f'?v={stamp}'


class Project:
    """What the window does. The page asks through api_*; what changes on this side reaches it through emit."""

    def __init__(self, cfg: Config, folder: Path | None = None, watch: Path | None = None):
        self.cfg = cfg
        self.prefs = QSettings('Lumen', cfg.name)
        self.shell = None
        self.folder: Path | None = None
        self.log_file: Path | None = None
        self.watch = watch
        self.proc: QProcess | None = None
        self.text = ''           # the code as the page has it
        self.disk = ''           # the code as it was last read or saved
        self.script_time = 0.0
        self.picture_list: list = []
        self.notes: list = []
        self.notes_chip = ''
        self.status = {'text': '', 'kind': ''}
        self.buffer = b''
        self.after = ''
        self.running = ''
        from ai_panel import AIRunner

        self.ai = AIRunner(self)
        last = self.prefs.value('last', '')
        target = folder or (Path(last) if last else None)
        if cfg.log_mode:
            if target and Path(target).is_file():
                self.open_log(Path(target), run=False)
        elif target and self.is_project(Path(target)):
            self.open_project(Path(target))
        elif self.examples():
            self.open_project(self.examples()[0])
        self.say('', '')
        self.timer = QTimer()
        self.timer.timeout.connect(self.follow_tick)
        self.timer.start(1500)

    def emit(self, kind: str, **data) -> None:  # replaced by the window's own once it exists
        pass

    @property
    def dirty(self) -> bool:
        return self.opened() and not self.cfg.log_mode and self.text != self.disk

    def opened(self) -> bool:
        return self.folder is not None or self.log_file is not None

    # --- what the page draws ------------------------------------------------------------------------------------------
    def config(self) -> dict:
        from ai_panel import HINT, SUB

        c = self.cfg
        return {'name': c.name, 'glyph': c.glyph or GLYPH.get(c.name, 'dot'), 'blurb': c.blurb, 'log_mode': c.log_mode, 'add_files': bool(c.add_files),
                'actions': [{'label': a.label, 'primary': a.primary, 'asks': a.asks} for a in c.actions],
                'new_kinds': [label for label, _ in c.new_kinds],
                'examples': [{'name': e.name, 'path': str(e)} for e in self.examples()],
                'ai': {'sub': SUB, 'hint': HINT}}

    def state(self) -> dict:
        place = self.log_file or self.folder
        main = self.main_file() if self.folder else None
        return {'opened': self.opened(), 'project': place.name if place else '', 'where': str(place) if place else '',
                'file': self.log_file.name if self.log_file else main.name if main else (self.cfg.mains[0] if self.cfg.mains else ''),
                'status': self.status, 'running': self.running if self.proc is not None else '',
                'pictures': [{'name': p.stem, 'url': file_url(p)} for p in self.picture_list],
                'pictures_key': '|'.join(str(p) for p in self.picture_list),
                'notes': self.notes, 'notes_chip': self.notes_chip, 'opens': self.opens()}

    def push(self, *keys) -> None:
        s = self.state()
        self.emit('state', **({k: s[k] for k in keys} if keys else s))

    def opens(self) -> list:
        return [{'label': label, 'rel': rel, 'ok': self.folder is not None and (self.folder / rel).exists()} for label, rel in self.cfg.opens]

    def say(self, text: str, kind: str = '') -> None:
        """The line at the bottom, with a light: amber while working, green when it worked, red when it did not."""
        self.status = {'text': text or ('就绪' if self.opened() else ('打开一份日志' if self.cfg.log_mode else '打开或新建一个项目')), 'kind': kind}
        self.push('status')

    # --- the page's calls ---------------------------------------------------------------------------------------------
    def api_boot(self) -> dict:
        return {'config': self.config(), 'state': self.state(), 'code': self.text}

    def api_edit(self, text: str) -> dict:
        self.text = text
        return {'dirty': self.dirty}

    def api_save(self) -> dict:
        if self.save():
            self.say('存好了。', 'ok')
        return {'dirty': self.dirty}

    def api_say(self, text: str, kind: str = '') -> dict:
        self.say(text, kind)
        return {}

    def api_new(self, kind: int = 0) -> dict:
        self.new_project(kind)
        return {}

    def api_open(self) -> dict:
        self.choose()
        return {}

    def api_example(self, path: str) -> dict:
        if self.leave():
            self.open_project(Path(path))
        return {}

    def api_open_log(self) -> dict:
        self.choose_log()
        return {}

    def api_add_file(self) -> dict:
        self.add_file()
        return {}

    def api_run(self, index: int, values: dict | None = None) -> dict:
        if 0 <= index < len(self.cfg.actions):
            self.run(self.cfg.actions[index], values or {})
        return {}

    def api_open_rel(self, rel: str) -> dict:
        self.open_file(rel)
        return {}

    def api_ai_state(self) -> dict:
        return self.ai.state()

    def api_ai_send(self, text: str) -> dict:
        return self.ai.send(text)

    def api_ai_stop(self) -> dict:
        self.ai.stop()
        return {}

    def api_ai_open_lumen(self) -> dict:
        self.ai.open_lumen()
        return {}

    # the window asks these before it closes
    def unsaved(self) -> bool:
        return self.dirty

    def save_all(self) -> bool:
        return self.save()

    def closing(self) -> None:
        self.timer.stop()
        self.ai.stop()
        if self.proc is not None:  # a program the window started does not outlive it
            self.proc.kill()
            self.proc = None

    # --- projects -----------------------------------------------------------------------------------------------------
    def examples(self) -> list:
        base = self.cfg.tool.parent / 'examples'
        return sorted(p for p in base.iterdir() if p.is_dir() and self.is_project(p)) if base.is_dir() else []

    def is_project(self, folder: Path) -> bool:
        return any(m and (folder / m).is_file() for m in self.cfg.mains)

    def main_file(self) -> Path | None:
        for m in self.cfg.mains:
            if m and (self.folder / m).is_file():
                return self.folder / m
        return None

    def choose(self) -> None:
        folder = self.shell.pick_folder('打开项目') if self.shell else None
        if not folder or not self.leave():
            return
        if self.is_project(folder):
            self.open_project(folder)
        else:
            self.say(f'这个文件夹不是 {self.cfg.name} 项目。', 'error')

    def new_project(self, kind: int = 0) -> None:
        extra = self.cfg.new_kinds[kind][1] if 0 <= kind < len(self.cfg.new_kinds) else []
        folder = self.shell.pick_folder('选一个空文件夹做新项目') if self.shell else None
        if not folder or not self.leave():
            return
        res = self.call(['init', str(folder), *extra])
        if res.get('ok'):
            self.open_project(folder)
        else:
            self.say(str(res.get('error') or '没有建成。'), 'error')

    def call(self, args: list) -> dict:
        import subprocess

        try:
            out = subprocess.run([sys.executable, str(self.cfg.tool), *args], capture_output=True, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                                 creationflags=0x08000000 if os.name == 'nt' else 0, timeout=300)
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': '等了 5 分钟还没有结果，已放弃。'}
        except OSError as e:
            return {'ok': False, 'error': f'启动不了：{e}'}
        return self.answer_of(out.stdout) or {'ok': False, 'error': self.last_lines(out.stdout + b'\n' + out.stderr)}

    @staticmethod
    def last_lines(raw: bytes, n: int = 4) -> str:
        """What a program said that is not one of its JSON lines: the last few, so a crash is shown instead of an empty answer."""
        lines = [x.rstrip() for x in raw.decode('utf-8', 'replace').splitlines() if x.strip() and not x.lstrip().startswith('{')]
        return '\n'.join(lines[-n:])

    @staticmethod
    def answer_of(raw: bytes) -> dict:
        for line in reversed(raw.decode('utf-8', 'replace').splitlines()):
            try:
                answer = json.loads(line)
            except ValueError:
                continue
            if isinstance(answer, dict) and 'event' not in answer:
                return answer
        return {}

    def open_project(self, folder: Path) -> None:
        self.folder = folder.resolve()
        self.log_file = None
        self.prefs.setValue('last', str(self.folder))
        self.load_code()
        self.notes, self.notes_chip = [], ''
        self.show_pictures()
        self.say('', '')
        self.push()

    def leave(self) -> bool:
        return not self.dirty or self.save()

    def load_code(self) -> None:
        path = self.main_file()
        if path is None:
            return
        try:
            self.disk = self.text = path.read_text(encoding='utf-8-sig')
            self.script_time = path.stat().st_mtime
        except (OSError, UnicodeDecodeError) as e:  # a file in use, or not UTF-8: say it, do not break the window
            self.say(f'读不了 {path.name}：{e}', 'error')
            return
        self.emit('code', text=self.text)

    def save(self) -> bool:
        path = self.main_file() if self.folder else None
        if path is None:
            return False
        try:
            path.write_text(self.text, encoding='utf-8')
            self.script_time = path.stat().st_mtime
        except OSError as e:
            self.say(f'没有保存：{e}', 'error')
            return False
        self.disk = self.text
        return True

    def add_file(self) -> None:
        if self.folder is None:
            self.say('先打开或新建一个项目。', 'error')
            return
        path = self.shell.pick_file('加入文件', self.cfg.add_files) if self.shell else None
        if path:
            target = self.folder / path.name
            try:
                target.write_bytes(path.read_bytes())
            except OSError as e:  # in use, no room, no right to write: said, not raised in the page's call
                self.say(f'没有加入 {path.name}：{e}', 'error')
                return
            self.say(f'加入了 {target.name}', 'ok')

    # --- a log instead of a project -----------------------------------------------------------------------------------
    def choose_log(self) -> None:
        path = self.shell.pick_file('打开训练日志', '日志 (*.log *.txt *.csv *.out);;所有文件 (*)') if self.shell else None
        if path:
            self.open_log(path)

    def open_log(self, path: Path, run: bool = True) -> None:
        self.log_file = path.resolve()
        self.folder = None
        self.prefs.setValue('last', str(self.log_file))
        self.disk = self.text = self.tail()
        self.emit('code', text=self.text)
        self.push()
        if run:
            self.run(self.cfg.actions[0])

    # --- running ------------------------------------------------------------------------------------------------------
    def target(self) -> str:
        return str(self.log_file if self.cfg.log_mode else self.folder)

    def run(self, action: Action, values: dict | None = None) -> None:
        if self.proc is not None:
            return
        if (self.cfg.log_mode and self.log_file is None) or (not self.cfg.log_mode and (self.folder is None or not self.leave())):
            self.say('先打开日志。' if self.cfg.log_mode else '先打开或新建一个项目。', 'error')
            return
        self.buffer = b''
        self.after = action.then_open
        self.running = action.label
        self.proc = QProcess()
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(self.cfg.tool.parent))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)  # what it prints on stderr (a crash) is kept too, and shown if there is no answer
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.done)
        self.proc.errorOccurred.connect(self.failed)
        self.say(f'{action.label}…', 'busy')
        self.push('running')
        self.proc.start(sys.executable, [str(self.cfg.tool), *[str(a).replace('{folder}', self.target()) for a in action.args]])

    def read(self) -> None:
        if self.proc is not None:
            self.buffer += bytes(self.proc.readAllStandardOutput())
            for line in self.buffer.decode('utf-8', 'replace').splitlines()[-3:]:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get('event') == 'progress' and event.get('at'):
                    self.say(f'{self.running} · {event["at"]}', 'busy')

    def failed(self, error) -> None:
        """The program could not even start: the window must not stay "busy" for ever."""
        if self.proc is not None and error == QProcess.FailedToStart:
            self.proc = None
            self.notes = [{'text': '启动不了：Python 没有跑起来。', 'kind': 'error'}]
            self.notes_chip = ''
            self.say('没有做成，原因在“说明”里。', 'error')
            self.push()

    def done(self, *_args) -> None:
        self.read()
        self.proc = None
        answer = self.answer_of(self.buffer)
        self.notes = []
        if not answer.get('ok'):
            where = f"第 {answer['line']} 行：" if answer.get('line') else ''
            self.notes = [{'text': where + str(answer.get('error') or self.last_lines(self.buffer) or '没有结果。'), 'kind': 'error'}]
            self.notes += [{'text': str(w), 'kind': 'warn'} for w in answer.get('warnings') or []]
            self.notes_chip = ''
            self.say('没有做成，原因在“说明”里。', 'error')
            self.push()
            return
        lines = list(self.cfg.describe(answer)) if self.cfg.describe else []
        warnings = [str(w) for w in answer.get('warnings') or []]
        self.notes = [{'text': w, 'kind': 'warn'} for w in warnings] + [{'text': str(t), 'kind': ''} for t in lines]
        self.notes_chip = f'{len(warnings)} 条要看' if warnings else ''
        self.status = {'text': '做好了。' + (f'有 {len(warnings)} 条要看。' if warnings else ''), 'kind': 'ok'}
        if self.cfg.log_mode:
            self.disk = self.text = self.tail()
            self.emit('code', text=self.text)
            pics = answer.get('pictures') or []
            if pics:
                self.picture_list = [Path(pics[0])]
        else:
            self.show_pictures(answer)
        self.push()
        if self.after:
            self.open_file(self.after)

    def tail(self) -> str:
        """The end of the log, read without taking it whole (a log can be gigabytes) and without locking it."""
        try:
            size = self.log_file.stat().st_size
            with open(self.log_file, 'rb') as f:
                if size > 400_000:
                    f.seek(size - 400_000)
                raw = f.read()
        except OSError:
            return ''
        for enc in ('utf-8', 'gb18030'):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode('utf-8', 'replace')
        return '\n'.join(text.replace('\r', '\n').splitlines()[-200:])

    def show_pictures(self, answer: dict | None = None) -> None:
        names = list((answer or {}).get('pictures') or [])
        if not names and self.folder is not None and (self.folder / 'out').is_dir():
            names = [p.relative_to(self.folder).as_posix() for p in sorted((self.folder / 'out').glob('*.png')) if not p.name.startswith('chart_')]
        self.picture_list = [self.folder / n for n in names] if self.folder else []

    def open_file(self, rel: str) -> None:
        path = self.folder / rel if self.folder else None
        if path is None or not path.exists():
            self.say(f'还没有 {rel}', 'error')
            return
        if self.shell:
            self.shell.api_open_path(str(path))

    def newest_project(self) -> Path | None:
        """The newest project under the watched folder. Walking a whole tree every 1.5 s froze the window, so the walk is repeated at most
        every 10 s; in between the answer is remembered."""
        import time

        now = time.monotonic()
        if now - getattr(self, '_scan_at', -99.0) < 10.0:
            return getattr(self, '_scan_found', None)
        self._scan_at = now
        self._scan_found = self._walk_newest()
        return self._scan_found

    def _walk_newest(self) -> Path | None:
        best, when = None, 0.0
        for base, dirs, files in os.walk(self.watch):
            if len(Path(base).relative_to(self.watch).parts) > 3:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'venv', '__pycache__', 'out')]
            for m in self.cfg.mains:
                if m and m in files:
                    try:
                        t = (Path(base) / m).stat().st_mtime
                    except OSError:  # gone while we looked
                        continue
                    if t > when:
                        best, when = Path(base).resolve(), t
        return best

    def follow_tick(self) -> None:
        """Files change under the window when the AI is working: show what it has."""
        if self.watch is not None and self.proc is None and not self.dirty:
            found = self.newest_project()
            if found is not None and found != self.folder:
                self.open_project(found)
        if self.folder is None or self.cfg.log_mode:
            return
        path = self.main_file()
        try:
            if path is not None and path.stat().st_mtime != self.script_time and not self.dirty:
                self.load_code()
        except (OSError, UnicodeDecodeError):
            pass
        self.push('opens')


HERE = Path(__file__).resolve().parent


def args_of(argv: list) -> tuple:
    """(folder, watch, mode) from the command line."""
    mode, args = webshell.take_mode(argv)
    watch = None
    if len(args) == 2 and args[0] == '--watch':
        watch, args = Path(args[1]).resolve(), []
    return (Path(args[0]).resolve() if args else None), watch, mode


def launch(cfg: Config, project_class=Project) -> int:
    folder, watch, mode = args_of(sys.argv[1:])
    app = webshell.make_app()
    project = project_class(cfg, folder, watch)
    win = webshell.window(project, cfg.name, HERE / 'ui_dist', mode=webshell.fixed_mode(mode), icon=HERE / 'assets' / f'{cfg.name.lower()}.ico', minimum=(380, 300))
    import embed

    embed.show(win)
    return app.exec()
