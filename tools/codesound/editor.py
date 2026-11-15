"""CodeSound's window: the code on the left, the notes on the right, and a player under them.

    editor.py [folder]         a project
    editor.py --watch <root>   follows whichever project under root is being worked on (Lumen opens it like this)
"""
from __future__ import annotations

import right_python

right_python.use('PySide6')

import json
import os
from pathlib import Path
import sys

from PySide6.QtCore import QPointF, QProcess, QProcessEnvironment, QRectF, QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton, QSlider, QSplitter,
                               QStackedLayout, QVBoxLayout, QWidget)

import codesound as core
import look
from look import AMBER, GREEN, INK, INK2, INK3, RED, RULE, Card, CodeEdit, Empty, Mark, Notes, vrule

THEME = look.THEME
# One colour per track: distinct, a little quiet, readable on white.
COLOURS = ('#3d7bfd', '#ef8a3c', '#2fa66a', '#e05a5a', '#8e5ee0', '#d29f1c', '#25adc4', '#7a8bf0', '#c862b8', '#8a8a90')


def button(text: str, fn=None, kind: str = '', glyph: str = '', tip: str = '') -> QPushButton:
    return look.button(text, fn, kind, glyph, tip)


def clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f'{seconds // 60}:{seconds % 60:02d}'


class Roll(QWidget):
    """Every note of the song in its track's colour, the sections along the top, a line where the music is now. Click to jump."""

    def __init__(self, seek):
        super().__init__()
        self.score: dict | None = None
        self.seek = seek
        self.now = 0.0
        self.hover = -1.0
        self.setMinimumHeight(110)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def set_score(self, score: dict | None) -> None:
        self.score = score
        self.update()

    def seconds(self) -> float:
        return float((self.score or {}).get('seconds') or 1) or 1.0

    def mousePressEvent(self, e):
        if self.score:
            self.seek(max(0.0, (e.position().x() - 14) / max(1, self.width() - 28)) * self.seconds())

    def mouseMoveEvent(self, e):
        self.hover = e.position().x()
        self.update()

    def leaveEvent(self, _e):
        self.hover = -1.0
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#ffffff'))
        if not self.score:
            p.setPen(QColor(INK3))
            p.drawText(self.rect(), Qt.AlignCenter, '还没有音符：点“试听”合成一次')
            return
        left, right, top = 14.0, 14.0, 34.0
        w = self.width() - left - right
        tracks = self.score.get('tracks', [])
        drums = [t for t in tracks if t.get('instrument') == 'drums']
        bottom = 16.0 + len(drums) * 11
        h = self.height() - top - bottom
        per_beat = 60 / max(self.score.get('tempo') or 100, 1)
        total = self.seconds()
        x_of = lambda beat: left + beat * per_beat / total * w  # noqa: E731
        pitched = [e['m'] for t in tracks for e in t['notes'] if isinstance(e.get('m'), int)]
        low, high = (min(pitched) - 2, max(pitched) + 2) if pitched else (48, 72)
        span = max(high - low, 14)
        y_of = lambda m: top + h * (1 - (m - low) / span)  # noqa: E731
        # octaves: a hairline on every C
        p.setPen(QPen(QColor('#f2f2f4'), 1))
        for m in range(low, high + 1):
            if m % 12 == 0:
                y = y_of(m)
                p.drawLine(QPointF(left, y), QPointF(left + w, y))
        # sections: a rule and a quiet label
        small = QFont(self.font())
        small.setPointSizeF(8.2)
        p.setFont(small)
        for s in self.score.get('sections', []):
            x = x_of(s['start'])
            p.setPen(QPen(QColor(RULE), 1))
            p.drawLine(QPointF(x, 22), QPointF(x, self.height() - 4))
            p.setPen(QColor(INK3))
            p.drawText(QRectF(x + 6, 6, 160, 16), Qt.AlignLeft | Qt.AlignVCenter, str(s['name']))
        lane = 0
        colours = {}
        for i, t in enumerate(tracks):
            colour = QColor(COLOURS[i % len(COLOURS)])
            colours[t.get('name', str(i))] = colour
            if t.get('instrument') == 'drums':
                y = self.height() - bottom + 8 + lane * 11
                lane += 1
                pen = QPen(colour, 1.4)
                pen.setCapStyle(Qt.RoundCap)
                p.setPen(pen)
                for e in t['notes']:
                    x = x_of(e['b'])
                    p.drawLine(QPointF(x, y), QPointF(x, y + 6))
                continue
            p.setPen(Qt.NoPen)
            for e in t['notes']:
                if not isinstance(e.get('m'), int):
                    continue
                c = QColor(colour)
                c.setAlphaF(.45 + .55 * min(1.0, float(e.get('v', .7))))
                p.setBrush(c)
                x = x_of(e['b'])
                p.drawRoundedRect(QRectF(x, y_of(e['m']) - 2, max(3.0, e['d'] * per_beat / total * w - 1), 4), 2, 2)
        if 0 <= self.hover <= self.width():
            p.setPen(QPen(QColor('#d6d6db'), 1, Qt.DashLine))
            p.drawLine(QPointF(self.hover, 22), QPointF(self.hover, self.height() - 4))
            p.setPen(QColor(INK2))
            at = max(0.0, (self.hover - left) / max(1, w)) * total
            p.drawText(QRectF(self.hover + 5, self.height() - 20, 60, 16), Qt.AlignLeft | Qt.AlignVCenter, clock(at))
        x = left + self.now / total * w
        p.setPen(QPen(QColor(INK), 1.2))
        p.drawLine(QPointF(x, 24), QPointF(x, self.height() - 4))
        head = QPainterPath()
        head.addRoundedRect(QRectF(x - 4.5, 18, 9, 9), 4.5, 4.5)
        p.fillPath(head, QColor(INK))


class Legend(QWidget):
    """Which colour is which track."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(28)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(14, 0, 14, 8)
        self.lay.setSpacing(6)

    def set_score(self, score: dict | None) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, t in enumerate((score or {}).get('tracks', [])[:9]):
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(f'background:{COLOURS[i % len(COLOURS)]};border-radius:4px;')
            name = QLabel(f"{t.get('name') or t.get('instrument')}")
            name.setObjectName('faint')
            name.setToolTip(f"{t.get('instrument')} · {len(t.get('notes', []))} 个音")
            self.lay.addWidget(dot)
            self.lay.addWidget(name)
            self.lay.addSpacing(10)
        self.lay.addStretch(1)


class Window(QMainWindow):
    def __init__(self, folder: Path | None = None, watch: Path | None = None):
        super().__init__()
        self.setWindowTitle('CodeSound')
        self.setStyleSheet(look.THEME)
        self.resize(1280, 820)
        self.setMinimumSize(420, 420)
        self.show_code = False
        self.prefs = QSettings('Lumen', 'CodeSound')
        self.folder: Path | None = None
        self.watch = watch
        self.proc: QProcess | None = None
        self.dirty = False
        self.script_time = 0.0
        self.score_time = 0.0
        self.quiet_load = False
        self.ai = None
        self.buffer = b''
        self.dragging = False
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self.moved)
        self.player.durationChanged.connect(lambda _ms: self.moved(self.player.position()))
        self.player.playbackStateChanged.connect(self.play_state)
        self.build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.follow_tick)
        self.timer.start(900)
        target = folder or self.prefs.value('last', '')
        if not (target and (Path(target) / 'project.json').is_file()):
            target = core.ROOT / 'examples' / 'quiet_room'  # a window should have something to play from the first moment
        self.open_project(Path(target))

    NARROW, MID = 700, 1000

    def toggle_code(self) -> None:
        self.show_code = not self.show_code
        self.relayout()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if hasattr(self, 'split'):
            self.relayout()

    def relayout(self) -> None:
        if getattr(self, '_relaying', False):  # changing the bar can resize the window again: do not start over inside ourselves
            return
        self._relaying = True
        try:
            self._relayout()
        finally:
            self._relaying = False

    def _relayout(self) -> None:
        width = self.width()
        state = (width < self.NARROW, width < self.MID, width < 1180, self.show_code)
        if getattr(self, '_layout_state', None) == state:
            return
        self._layout_state = state
        self._relayout_now()

    def _relayout_now(self) -> None:
        """Wide: code | score and player. Narrower: the score and player take the room, the code is one tap away (it replaces them while
        it is open). The top bar loses its words first."""
        width = self.width()
        narrow, mid = width < self.NARROW, width < self.MID
        both = not mid
        self.code_card.setVisible(both or self.show_code)
        self.right_panel.setVisible(both or not self.show_code)
        self.code_toggle.setVisible(mid)
        self.code_toggle.setChecked(self.show_code) if self.code_toggle.isCheckable() else None
        for w in (self.title_label, self.crumb_label, self.name, self.unsaved, self.sample_button):
            w.setVisible(not narrow)
        squeeze = 'QPushButton{min-width:0;padding:0 6px;}'
        pass
        for g in self.ghosts:
            g.setText('' if width < 1180 else g.property('words'))
            g.setStyleSheet(squeeze if width < 1180 else '')
        for b in (self.check_btn, self.final_btn):
            b.setStyleSheet(squeeze if narrow else '')
        self.top_layout.setSpacing(2 if narrow else 6)
        self.top_layout.setContentsMargins(*((8, 0, 6, 0) if narrow else (16, 0, 14, 0)))
        for b in (self.check_btn, self.final_btn):
            pass
        self.volume.setVisible(not narrow)
        self.speaker.setVisible(not narrow)
        self.vr.setVisible(not narrow)
        self.split.setSizes([540, 700] if both else [1, 1])

    def build(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        bar.setObjectName('bar')
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setFixedHeight(56)
        top = QHBoxLayout(bar)
        top.setContentsMargins(16, 0, 14, 0)
        top.setSpacing(6)
        top.addWidget(Mark('music'))
        top.addSpacing(4)
        title = QLabel('CodeSound')
        title.setObjectName('title')
        top.addWidget(title)
        crumb = QLabel('/')
        crumb.setObjectName('crumb')
        top.addWidget(crumb)
        self.title_label, self.crumb_label, self.top_layout = title, crumb, top
        self.name = QLabel('')
        self.name.setObjectName('project')
        top.addWidget(self.name)
        self.unsaved = QLabel('')
        self.unsaved.setObjectName('faint')
        top.addWidget(self.unsaved)
        sample = QPushButton('例子')
        sample.setObjectName('ghost')
        sample.setIcon(look.icon('chev'))
        sample.setIconSize(QSize(13, 13))
        sample.setLayoutDirection(Qt.RightToLeft)
        sample.setCursor(Qt.PointingHandCursor)
        sample.setStyleSheet('QPushButton::menu-indicator{width:0;image:none;}')
        menu = QMenu(self)
        base = core.ROOT / 'examples'
        for e in sorted(p for p in base.iterdir() if (p / 'project.json').is_file()) if base.is_dir() else []:
            menu.addAction(e.name, lambda p=e: self.leave() and self.open_project(p))
        sample.setMenu(menu)
        top.addSpacing(6)
        top.addWidget(sample)
        self.sample_button = sample
        top.addStretch(1)
        self.ghosts = [button('新建', self.new_project, 'ghost', 'plus', '新建一个音乐项目'), button('打开', self.choose, 'ghost', 'folder', '打开一个项目文件夹'),
                       button('一键作曲', self.compose, 'ghost', 'wave', '选一个风格和长度，直接写好一首'), button('让 AI 做', self.open_ai, 'ghost', 'spark', '让 Lumen 的团队来写这首曲子')]
        for g in self.ghosts:
            g.setProperty('words', g.text())
            top.addWidget(g)
        self.code_toggle = button('', self.toggle_code, 'ghost', 'code', '代码')  # narrow: the code and the player take turns
        self.code_toggle.hide()
        top.addWidget(self.code_toggle)
        self.top_rule = vrule()
        top.addWidget(self.top_rule)
        self.check_btn = button('试听', lambda: self.render('check'), 'primary', '', '快速合成一遍，听个大概')
        self.final_btn = button('出成品', lambda: self.render('final'), '', '', '用最好的音质合成')
        self.export_btn = button('存 MP3', self.export, 'ghost', 'export', '把成品存成 MP3')
        self.ghosts.append(self.export_btn)
        for b in (self.check_btn, self.final_btn, self.export_btn):
            b.setProperty('words', b.text())
            top.addWidget(b)
        self.top_rule = None
        outer.addWidget(bar)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 14, 16, 14)
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        self.split = split
        self.code_card = Card('song.py', 'code')
        self.code = CodeEdit()
        self.code.textChanged.connect(self.changed)
        self.code_card.body.addWidget(self.code)
        self.code_card.add_tool(button('', self.save_now, 'icon', 'save', '保存 · Ctrl+S'))
        split.addWidget(self.code_card)

        right = QSplitter(Qt.Vertical)
        right.setChildrenCollapsible(False)
        self.right_panel = right
        self.roll_card = Card('乐谱', 'music')
        self.roll = Roll(self.seek)
        self.roll_card.body.addWidget(self.roll, 1)
        self.legend = Legend()
        self.roll_card.body.addWidget(self.legend)
        transport = QWidget()
        transport.setObjectName('cardHead')
        transport.setStyleSheet(f'QWidget#cardHead{{border-bottom:none;border-top:1px solid {RULE};}}')
        tr = QHBoxLayout(transport)
        tr.setContentsMargins(12, 10, 14, 10)
        tr.setSpacing(12)
        self.play_btn = QPushButton()
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setFixedSize(34, 34)
        self.play_btn.setIconSize(QSize(14, 14))
        self.play_btn.setStyleSheet(f'QPushButton{{background:{INK};border:none;border-radius:17px;min-height:34px;max-height:34px;padding:0;}}QPushButton:hover{{background:#2a2a2e;}}QPushButton:disabled{{background:#d5d5d9;}}')
        self.play_btn.clicked.connect(self.toggle)
        tr.addWidget(self.play_btn)
        self.time = QLabel('0:00')
        self.time.setStyleSheet(f'color:{INK};font-variant-numeric:tabular-nums;')
        self.time.setFixedWidth(38)
        tr.addWidget(self.time)
        self.bar = QSlider(Qt.Horizontal)
        self.bar.setRange(0, 1000)
        self.bar.sliderPressed.connect(lambda: setattr(self, 'dragging', True))
        self.bar.sliderReleased.connect(self.bar_released)
        tr.addWidget(self.bar, 1)
        self.length = QLabel('0:00')
        self.length.setObjectName('faint')
        self.length.setFixedWidth(38)
        tr.addWidget(self.length)
        self.vr = vrule(16)
        tr.addWidget(self.vr)
        speaker = QLabel()
        self.speaker = speaker
        speaker.setPixmap(look.pixmap('wave', INK3, 15))
        tr.addWidget(speaker)
        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(80)
        volume.setFixedWidth(84)
        self.volume = volume
        volume.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        self.audio.setVolume(.8)
        tr.addWidget(volume)
        self.roll_card.body.addWidget(transport)
        right.addWidget(self.roll_card)
        self.notes_card = Card('听感检查', 'check')
        self.notes = Notes('合成一次，这里会写长度、响度和量出来的问题。')
        self.notes_card.body.addWidget(self.notes)
        right.addWidget(self.notes_card)
        right.setSizes([560, 180])
        split.addWidget(right)
        split.setSizes([540, 700])
        lay.addWidget(split, 1)
        outer.addWidget(body, 1)

        foot = QWidget()
        foot.setObjectName('foot')
        foot.setAttribute(Qt.WA_StyledBackground, True)
        foot.setFixedHeight(30)
        f = QHBoxLayout(foot)
        f.setContentsMargins(16, 0, 16, 0)
        f.setSpacing(8)
        self.light = QLabel()
        self.light.setFixedSize(7, 7)
        f.addWidget(self.light)
        self.status = QLabel('')
        self.status.setObjectName('faint')
        f.addWidget(self.status, 1)
        self.where = QLabel('')
        self.where.setObjectName('faint')
        f.addWidget(self.where)
        outer.addWidget(foot)
        QShortcut(QKeySequence.Save, self, activated=self.save_now)
        QShortcut(QKeySequence('Ctrl+Space'), self, activated=self.toggle)
        self.play_state()
        self.say('就绪')

    def say(self, text: str, kind: str = '') -> None:
        self.status.setText(text)
        color = {'busy': AMBER, 'ok': GREEN, 'error': RED}.get(kind, '#d0d0d5')
        self.light.setStyleSheet(f'background:{color};border-radius:3px;')

    # --- projects -----------------------------------------------------------------------------------------------------
    def choose(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, '打开项目')
        if folder and self.leave():
            if (Path(folder) / 'project.json').is_file():
                self.open_project(Path(folder))
            else:
                self.say('这个文件夹不是 CodeSound 项目。', 'error')

    def new_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, '选一个空文件夹做新项目')
        if not folder or not self.leave():
            return
        try:
            core.cmd_init(type('A', (), {'folder': folder}))
        except core.Stop as e:
            self.say(str(e), 'error')
            return
        self.open_project(Path(folder))

    def leave(self) -> bool:
        return not self.dirty or self.save()

    def compose(self) -> None:
        """A whole piece from a style, with no code written: the song file just says which."""
        sys.path.insert(0, str(core.KIT))
        import compose as writer

        style, ok = QInputDialog.getItem(self, '一键作曲', '什么风格？', list(writer.STYLES), 0, False)
        if not ok:
            return
        seconds, ok = QInputDialog.getInt(self, '一键作曲', '大约多少秒？', 60, 15, 600, 15)
        if not ok:
            return
        if self.folder is None:
            base = Path.home() / 'CodeSound' / style
            n = 1
            while (base.parent / f'{style}{n}').exists():
                n += 1
            core.cmd_init(type('A', (), {'folder': str(base.parent / f'{style}{n}')}))
            self.open_project(base.parent / f'{style}{n}')
        seed = int(self.prefs.value('seed', 0) or 0) + 1
        self.prefs.setValue('seed', seed)
        self.code.setPlainText(f"import cs\n\ncs.compose({style!r}, seconds={seconds}, seed={seed})\n")
        self.render('check')

    def export(self) -> None:
        if self.folder is None:
            return
        try:
            res = core.cmd_export(type('A', (), {'folder': str(self.folder), 'format': 'mp3'}))
        except core.Stop as e:
            self.say(str(e), 'error')
            return
        self.say(f"存好了：{res['output']}，{res['size_kb']} KB", 'ok')

    def open_project(self, folder: Path) -> None:
        self.folder = folder.resolve()
        self.prefs.setValue('last', str(self.folder))
        self.name.setText(self.folder.name)
        self.where.setText(self.folder.name)
        self.where.setToolTip(str(self.folder))
        self.player.stop()
        self.player.setSource(QUrl())
        self.load_code()
        self.load_score()
        self.notes.clear()
        for name in ('final.wav', 'latest.wav'):
            if (self.folder / 'out' / name).is_file():
                self.set_audio(self.folder / 'out' / name)
                break
        self.play_state()

    @property
    def script(self) -> Path:
        return self.folder / core.load(self.folder)['script']

    def load_code(self) -> None:
        try:
            text = self.script.read_text(encoding='utf-8-sig')
            self.script_time = self.script.stat().st_mtime
            self.code_card.title.setText(self.script.name)
        except (OSError, core.Stop) as e:
            self.say(f'读不了：{e}', 'error')
            return
        self.quiet_load = True
        self.code.setPlainText(text)
        self.quiet_load = False
        self.mark_dirty(False)

    def mark_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self.unsaved.setText('· 未保存' if dirty else '')
        self.code_card.set_chip('未保存' if dirty else '')

    def changed(self) -> None:
        if not self.quiet_load:
            self.mark_dirty(True)

    def save_now(self) -> None:
        if self.save():
            self.say('存好了。', 'ok')

    def save(self) -> bool:
        if self.folder is None:
            return False
        try:
            self.script.write_text(self.code.toPlainText(), encoding='utf-8')
            self.script_time = self.script.stat().st_mtime
        except OSError as e:
            self.say(f'没有保存：{e}', 'error')
            return False
        self.mark_dirty(False)
        return True

    def load_score(self) -> None:
        path = self.folder / 'out' / 'score.json'
        try:
            score = json.loads(path.read_text(encoding='utf-8'))
            self.score_time = path.stat().st_mtime
        except (OSError, ValueError):
            score = None
        self.roll.set_score(score)
        self.legend.set_score(score)
        if score:
            bits = [str(score.get('key') or ''), f"{round(score.get('tempo') or 0)} 拍/分", f"{len(score.get('tracks', []))} 个声部"]
            self.roll_card.set_chip(' · '.join(b for b in bits if b))
            self.length.setText(clock(score.get('seconds') or 0))
        else:
            self.roll_card.set_chip('')

    def newest_project(self) -> Path | None:
        best, when = None, 0.0
        for base, dirs, files in os.walk(self.watch):
            depth = len(Path(base).relative_to(self.watch).parts)
            if depth > 3:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'venv', '__pycache__', 'out')]
            if 'project.json' in files and 'song.py' in files:
                t = (Path(base) / 'song.py').stat().st_mtime
                if t > when:
                    best, when = Path(base).resolve(), t
        return best

    def follow_tick(self) -> None:
        """Files change under the window when the AI is working: show what it has."""
        if self.watch is not None and self.proc is None and not self.dirty:
            found = self.newest_project()
            if found is not None and found != self.folder:
                self.open_project(found)
        if self.folder is None:
            return
        try:
            now = self.script.stat().st_mtime
            if now != self.script_time and not self.dirty:
                self.load_code()
            score = self.folder / 'out' / 'score.json'
            if score.is_file() and score.stat().st_mtime != self.score_time:
                self.load_score()
        except (OSError, core.Stop):
            pass

    # --- rendering ----------------------------------------------------------------------------------------------------
    def render(self, quality: str) -> None:
        if self.folder is None or self.proc is not None or not self.leave():
            return
        self.player.stop()
        self.player.setSource(QUrl())  # Windows keeps a playing file locked
        self.buffer = b''
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.proc.setProcessEnvironment(env)
        self.proc.readyReadStandardOutput.connect(self.read)
        self.proc.finished.connect(self.done)
        self.check_btn.setEnabled(False)
        self.final_btn.setEnabled(False)
        self.say('正在合成成品…' if quality == 'final' else '正在合成试听…', 'busy')
        self.proc.start(sys.executable, [str(core.ROOT / 'codesound.py'), 'render', str(self.folder), '--quality', quality])

    def read(self) -> None:
        if self.proc is not None:
            self.buffer += bytes(self.proc.readAllStandardOutput())

    def done(self, *_args) -> None:
        self.read()
        self.proc = None
        self.check_btn.setEnabled(True)
        self.final_btn.setEnabled(True)
        answer = {}
        for line in reversed(self.buffer.decode('utf-8', 'replace').splitlines()):
            try:
                answer = json.loads(line)
                break
            except ValueError:
                continue
        self.notes.clear()
        if not answer.get('ok'):
            where = f"第 {answer['line']} 行：" if answer.get('line') else ''
            self.say('没有做成，原因在下面。', 'error')
            self.notes.addItem(where + str(answer.get('error') or '合成失败了。'), 'error')
            self.notes_card.set_chip('')
            return
        m = answer.get('measured') or {}
        self.say(f"做好了：{answer.get('output')}", 'ok')
        facts = [f"{m.get('seconds', 0)} 秒", f"平均 {m.get('rms_db', '-')} dB"] + ([f"峰值 {m['peak_db']} dB"] if 'peak_db' in m else [])
        self.notes_card.set_chip(' · '.join(facts))
        warnings = answer.get('warnings') or []
        self.notes.addItems(warnings, 'warn')
        if not warnings:
            self.notes.addItem('没有量出问题。好不好听还是要靠你的耳朵。', 'ok')
        self.load_score()
        if answer.get('output', '').endswith('.wav') and '/sfx/' not in answer['output']:
            self.set_audio(self.folder / answer['output'])

    # --- listening ----------------------------------------------------------------------------------------------------
    def set_audio(self, path: Path) -> None:
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.play_state()

    def play_state(self, *_a) -> None:
        playing = self.player.playbackState() == QMediaPlayer.PlayingState
        self.play_btn.setIcon(look.icon('stop' if playing else 'play', '#ffffff', '#ffffff'))
        self.play_btn.setToolTip('暂停 · Ctrl+空格' if playing else '播放 · Ctrl+空格')
        self.play_btn.setEnabled(not self.player.source().isEmpty())

    def toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek(self, seconds: float) -> None:
        self.player.setPosition(int(seconds * 1000))

    def bar_released(self) -> None:
        self.dragging = False
        total = self.player.duration() or int(self.roll.seconds() * 1000)
        self.player.setPosition(int(self.bar.value() / 1000 * total))

    def moved(self, ms: int) -> None:
        self.roll.now = ms / 1000
        self.roll.update()
        total = self.player.duration() or int(self.roll.seconds() * 1000)
        self.time.setText(clock(ms / 1000))
        if total:
            self.length.setText(clock(total / 1000))
            if not self.dragging:
                self.bar.setValue(int(ms / total * 1000))

    def open_ai(self) -> None:
        if self.folder is None:
            self.say('先打开或新建一个项目。', 'error')
            return
        if self.ai is None:
            from ai_panel import AIPanel

            self.ai = AIPanel(self)
        self.ai.show()
        self.ai.raise_()

    def closeEvent(self, e):
        if self.dirty and QMessageBox.question(self, 'CodeSound', '保存改动吗？') == QMessageBox.Yes:
            self.save()
        super().closeEvent(e)


def main() -> int:
    args = sys.argv[1:]
    watch = None
    if len(args) == 2 and args[0] == '--watch':
        watch, args = Path(args[1]).resolve(), []
    app = QApplication(sys.argv[:1])
    look.apply(app)
    win = Window(Path(args[0]) if args else None, watch)
    import embed
    embed.show(win)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
