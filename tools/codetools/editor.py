"""CodeTools' window: every plugin in one list, each with its own form. Nothing here knows any plugin: the form comes from what the plugin says it asks for.

    editor.py [plugin id]
"""
from __future__ import annotations

import right_python

right_python.use('PySide6', 'PIL')

import json  # noqa: E402
from pathlib import Path  # noqa: E402
import sys  # noqa: E402

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QSize, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QAction, QDesktopServices, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,  # noqa: E402
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

import codetools as core  # noqa: E402
import look  # noqa: E402
from look import AMBER, GREEN, INK2, INK3, RED, RULE, TINT, Card, Empty, Mark  # noqa: E402

GROUPS = '创作 写作 文件 开发 科学 游戏'.split()
GLYPH = {'创作': 'spark', '写作': 'file', '文件': 'folder', '开发': 'code', '科学': 'flask', '游戏': 'game'}
EXTRA = f"""
QWidget#side {{ background: #ffffff; border-right: 1px solid {RULE}; }}
QListWidget#plugins {{ background: transparent; padding: 0 8px 12px 8px; }}
QListWidget#plugins::item {{ height: 30px; padding: 0 10px; border-radius: 7px; color: {INK2}; }}
QListWidget#plugins::item:hover {{ background: {TINT}; color: #111113; }}
QListWidget#plugins::item:selected {{ background: #f4f4f5; color: #111113; }}
QListWidget#plugins::item:disabled {{ color: {INK3}; background: transparent; }}
QTableWidget {{ background: #ffffff; border: 1px solid {RULE}; border-radius: 10px; gridline-color: #f2f2f4; selection-background-color: #f4f4f5; selection-color: #111113; }}
QHeaderView::section {{ background: {TINT}; border: none; border-bottom: 1px solid {RULE}; padding: 7px 10px; color: {INK2}; font-weight: 600; font-size: 12px; }}
QLabel#fieldLabel {{ color: {INK2}; font-size: 12px; }}
QLabel#plugTitle {{ font-size: 18px; font-weight: 650; }}
QFrame#warn {{ background: #fdf8ec; border: 1px solid #f1e2bd; border-radius: 10px; }}
QFrame#bad {{ background: #fdf1f0; border: 1px solid #f3d2ce; border-radius: 10px; }}
QPushButton#file {{ text-align: left; padding: 0 12px; border-color: {RULE}; }}
"""


class FilePick(QWidget):
    """A path and a button that looks for one."""

    def __init__(self, folder: bool, value: str):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.edit = QLineEdit(str(value or ''))
        self.edit.setPlaceholderText('选一个文件夹' if folder else '选一个文件')
        lay.addWidget(self.edit, 1)
        lay.addWidget(look.button('选择', lambda: self.pick(folder), '', 'folder'))

    def pick(self, folder: bool) -> None:
        path = QFileDialog.getExistingDirectory(self, '选文件夹') if folder else QFileDialog.getOpenFileName(self, '选文件')[0]
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()


class Window(QMainWindow):
    def __init__(self, start: str | None = None):
        super().__init__()
        self.setWindowTitle('CodeTools')
        self.setStyleSheet(look.THEME + EXTRA)
        self.resize(1240, 800)
        self.setMinimumSize(420, 420)
        self.prefs = QSettings('Lumen', 'CodeTools')
        self.plugins = core.load_all()
        self.proc: QProcess | None = None
        self.buffer = b''
        self.current = None
        self.widgets: dict = {}
        self.action_index = 0
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        bar.setObjectName('bar')
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setFixedHeight(56)
        top = QHBoxLayout(bar)
        top.setContentsMargins(16, 0, 14, 0)
        top.setSpacing(8)
        top.addWidget(Mark('tools'))
        top.addSpacing(2)
        name = QLabel('CodeTools')
        name.setObjectName('title')
        top.addWidget(name)
        count = QLabel(f'{len(self.plugins)} 个插件 · {sum(len(p.actions) for p in self.plugins.values())} 个功能')
        count.setObjectName('chip')
        count.setFixedHeight(20)
        top.addWidget(count)
        if core.BROKEN:  # said, not hidden: which file did not load, and why
            bad = QLabel(f'{len(core.BROKEN)} 个插件没有载入')
            bad.setObjectName('chip')
            bad.setFixedHeight(20)
            bad.setToolTip('\n'.join(f'{k}: {v}' for k, v in core.BROKEN.items()))
            top.addWidget(bad)
        top.addStretch(1)
        top.addWidget(look.button('结果文件夹', self.open_results, 'ghost', 'folder', '打开这个插件做出来的文件'))
        outer.addWidget(bar)

        main = QHBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        side = QWidget()
        side.setObjectName('side')
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(248)
        self.side = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 12, 0, 0)
        sl.setSpacing(8)
        self.find = QLineEdit()
        self.find.setObjectName('search')
        self.find.setPlaceholderText(f'在 {len(self.plugins)} 个插件里找')
        self.find.addAction(QAction(look.icon('search', INK3), '', self.find), QLineEdit.LeadingPosition)
        self.find.setStyleSheet('QLineEdit#search{padding-left:6px;}')
        self.find.textChanged.connect(self.fill)
        holder = QHBoxLayout()
        holder.setContentsMargins(12, 0, 12, 0)
        holder.addWidget(self.find)
        sl.addLayout(holder)
        self.list = QListWidget()
        self.list.setObjectName('plugins')
        self.list.setIconSize(QSize(14, 14))
        self.list.currentItemChanged.connect(self.picked)
        sl.addWidget(self.list, 1)
        main.addWidget(side)

        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        bl = QVBoxLayout(inner)
        bl.setContentsMargins(32, 24, 32, 28)
        self.page_lay, self.margins = bl, (32, 24, 32, 28)
        self.picker = QComboBox()  # the narrow form of the list on the left
        self.picker.currentIndexChanged.connect(self.pick_from_box)
        self.picker.hide()
        bl.addWidget(self.picker)
        bl.setSpacing(16)
        head = QVBoxLayout()
        head.setSpacing(6)
        trow = QHBoxLayout()
        trow.setSpacing(10)
        self.title = QLabel('')
        self.title.setObjectName('plugTitle')
        trow.addWidget(self.title)
        self.group = QLabel('')
        self.group.setObjectName('chip')
        self.group.setFixedHeight(20)
        trow.addWidget(self.group)
        trow.addStretch(1)
        head.addLayout(trow)
        self.blurb = QLabel('')
        self.blurb.setObjectName('muted')
        self.blurb.setWordWrap(True)
        head.addWidget(self.blurb)
        bl.addLayout(head)
        self.segs = QWidget()
        self.segs.setObjectName('segs')
        self.segs.setAttribute(Qt.WA_StyledBackground, True)
        self.seg_lay = QHBoxLayout(self.segs)
        self.seg_lay.setContentsMargins(3, 3, 3, 3)
        self.seg_lay.setSpacing(2)
        self.seg_group = QButtonGroup(self)
        self.seg_group.setExclusive(True)
        # the action buttons scroll sideways when they are more than the room: they are never cut off or piled up
        seg_scroll = QScrollArea()
        seg_scroll.setFrameShape(QFrame.NoFrame)
        seg_scroll.setWidgetResizable(True)
        seg_scroll.setWidget(self.segs)
        seg_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        seg_scroll.setFixedHeight(52)
        seg_scroll.setStyleSheet('QScrollArea{background:transparent;}')
        self.seg_scroll = seg_scroll
        bl.addWidget(seg_scroll)

        self.form_card = Card('填写', 'list')
        self.form_box = QWidget()
        self.form = QGridLayout(self.form_box)
        self.form.setContentsMargins(16, 14, 16, 6)
        self.form.setHorizontalSpacing(14)
        self.form.setVerticalSpacing(12)
        self.form_box.setMaximumWidth(760)
        self.form_card.body.addWidget(self.form_box)
        run_row = QHBoxLayout()
        run_row.setContentsMargins(16, 8, 16, 14)
        run_row.setSpacing(10)
        self.run_btn = look.button('运行', self.run, 'primary', 'play')
        run_row.addWidget(self.run_btn)
        self.light = QLabel()
        self.light.setFixedSize(7, 7)
        run_row.addWidget(self.light)
        self.status = QLabel('')
        self.status.setObjectName('faint')
        run_row.addWidget(self.status, 1)
        self.form_card.body.addLayout(run_row)
        bl.addWidget(self.form_card)

        self.result_card = Card('结果', 'check')
        self.results = QWidget()
        self.rl = QVBoxLayout(self.results)
        self.rl.setContentsMargins(16, 14, 16, 16)
        self.rl.setSpacing(10)
        self.result_card.body.addWidget(self.results)
        bl.addWidget(self.result_card)
        bl.addStretch(1)
        page.setWidget(inner)
        main.addWidget(page, 1)
        outer.addLayout(main, 1)
        self.setCentralWidget(root)
        self.fill('')
        if start and start in self.plugins:
            self.select(start)
        else:
            last = self.prefs.value('plugin', '')
            if last in self.plugins:
                self.select(last)
            elif self.list.count():
                self.list.setCurrentRow(1)

    def say(self, text: str, kind: str = '') -> None:
        self.status.setText(text)
        color = {'busy': AMBER, 'ok': GREEN, 'error': RED}.get(kind, '#d0d0d5')
        self.light.setStyleSheet(f'background:{color};border-radius:3px;')

    def fill(self, needle: str) -> None:
        q = needle.strip().lower()
        self.list.blockSignals(True)
        keep = self.current.id if self.current else None
        self.list.clear()
        last = None
        for p in sorted(self.plugins.values(), key=lambda x: GROUPS.index(x.group) if x.group in GROUPS else 9):
            if q and q not in f'{p.id} {p.name} {p.group} {p.blurb}'.lower():
                continue
            if p.group != last:
                head = QListWidgetItem(p.group)
                head.setFlags(Qt.NoItemFlags)
                head.setIcon(look.icon(GLYPH.get(p.group, 'dot'), INK3, INK3))
                f = head.font()
                f.setPointSizeF(8.6)
                f.setBold(True)
                head.setFont(f)
                head.setSizeHint(QSize(0, 34))
                self.list.addItem(head)
                last = p.group
            item = QListWidgetItem(p.name)
            item.setData(Qt.UserRole, p.id)
            item.setToolTip(p.blurb)
            item.setSizeHint(QSize(0, 30))
            self.list.addItem(item)
            if p.id == keep:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)

    def pick_from_box(self, index: int) -> None:
        if 0 <= index < self.list.count():
            self.list.setCurrentRow(index)

    NARROW = 640   # below this the list on the left folds into a drop-down above the form

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        narrow = self.width() < self.NARROW
        if getattr(self, '_narrow', None) == narrow or getattr(self, '_relaying', False):
            return
        self._relaying = True
        try:
            self._narrow = narrow
            self._fold(narrow)
        finally:
            self._relaying = False

    def _fold(self, narrow: bool) -> None:
        if hasattr(self, 'side'):
            self.side.setVisible(not narrow)
            self.picker.setVisible(narrow)
            self.page_lay.setContentsMargins(*((14, 14, 14, 18) if narrow else self.margins))

    def sync_picker(self, item) -> None:
        """The drop-down lists what the list on the left lists (its group headings too, as unselectable lines)."""
        if self.picker.count() != self.list.count():
            self.picker.blockSignals(True)
            self.picker.clear()
            for i in range(self.list.count()):
                it = self.list.item(i)
                self.picker.addItem(it.text())
                if not it.data(Qt.UserRole):  # a heading
                    self.picker.model().item(i).setEnabled(False)
            self.picker.blockSignals(False)
        self.picker.blockSignals(True)
        self.picker.setCurrentIndex(self.list.row(item))
        self.picker.blockSignals(False)

    def select(self, pid: str) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == pid:
                self.list.setCurrentRow(i)

    def picked(self, item, _old=None) -> None:
        pid = item.data(Qt.UserRole) if item else None
        if not pid:
            return
        self.current = self.plugins[pid]
        self.sync_picker(item)
        self.prefs.setValue('plugin', pid)
        self.title.setText(self.current.name)
        self.group.setText(self.current.group)
        self.blurb.setText(self.current.blurb)
        for b in self.seg_group.buttons():
            self.seg_group.removeButton(b)
            b.deleteLater()
        for i, a in enumerate(self.current.actions):
            b = QPushButton(a.label)
            b.setObjectName('tab')
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=i: self.show_action(n))
            self.seg_group.addButton(b)
            self.seg_lay.addWidget(b)
        self.seg_scroll.setVisible(len(self.current.actions) > 1)
        self.show_action(0)

    def action(self):
        return self.current.actions[max(0, min(self.action_index, len(self.current.actions) - 1))]

    def show_action(self, index: int) -> None:
        self.action_index = index
        buttons = self.seg_group.buttons()
        if 0 <= index < len(buttons):
            buttons[index].setChecked(True)
        while self.form.count():
            w = self.form.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.widgets = {}
        row = 0
        for f in self.action().fields:
            if f.kind == 'area':
                w = QPlainTextEdit(str(f.value or ''))
                w.setFixedHeight(132)
                w.setFont(look.mono(9.4))
            elif f.kind == 'choice':
                w = QComboBox()
                for c in f.choices:
                    w.addItem(str(c), str(c))  # what the plugin is given is the choice itself, whatever words it is shown in
                w.setCurrentIndex(max(0, w.findData(str(f.value))))
            elif f.kind == 'check':
                w = QCheckBox(f.label)
            elif f.kind in ('file', 'folder'):
                w = FilePick(f.kind == 'folder', f.value)
            else:
                w = QLineEdit(str(f.value if f.value is not None else ''))
            if isinstance(w, QCheckBox):
                w.setChecked(bool(f.value))
                self.form.addWidget(w, row, 0, 1, 2)
            else:
                label = QLabel(f.label)
                label.setObjectName('fieldLabel')
                label.setWordWrap(True)
                self.form.addWidget(label, row, 0, 1, 2)
                row += 1
                self.form.addWidget(w, row, 0, 1, 2)
            self.widgets[f.key] = (f, w)
            row += 1
        self.form_card.set_chip(f'{len(self.widgets)} 项' if self.widgets else '不用填，直接运行')
        self.run_btn.setText(self.action().label if len(self.current.actions) > 1 else '运行')
        self.clear_results()

    def values(self) -> dict:
        out = {}
        for key, (_f, w) in self.widgets.items():
            if isinstance(w, QPlainTextEdit):
                out[key] = w.toPlainText()
            elif isinstance(w, QComboBox):
                out[key] = w.currentData() if w.currentData() is not None else w.currentText()
            elif isinstance(w, QCheckBox):
                out[key] = w.isChecked()
            elif isinstance(w, FilePick):
                out[key] = w.value()
            else:
                out[key] = w.text()
        return out

    def run(self) -> None:
        if self.proc is not None or self.current is None:
            return
        action = self.action()
        if action.changes and QMessageBox.question(self, action.label, '这一步会改动你的文件。确定吗？') != QMessageBox.Yes:
            return
        self.clear_results()
        self.buffer = b''
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(core.ROOT))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)  # a crash's last words come with the answer
        self.proc.errorOccurred.connect(self.failed)
        self.proc.readyReadStandardOutput.connect(lambda: setattr(self, 'buffer', self.buffer + bytes(self.proc.readAllStandardOutput())))
        self.proc.finished.connect(self.done)
        self.run_btn.setEnabled(False)
        self.say('运行中…', 'busy')
        args_file = core.RESULTS / '.last_args.json'
        args_file.parent.mkdir(parents=True, exist_ok=True)
        args_file.write_text(json.dumps(self.values(), ensure_ascii=False), encoding='utf-8')
        self.proc.start(sys.executable.replace('pythonw.exe', 'python.exe'), [str(core.ROOT / 'codetools.py'), 'run', self.current.id, action.key, '--args-file', str(args_file)])

    def failed(self, error) -> None:
        """Could not even start: the button must not stay "busy" for ever."""
        if self.proc is not None and error == QProcess.FailedToStart:
            self.proc = None
            self.run_btn.setEnabled(True)
            self.clear_results(keep_status=True)
            self.say('没有做成', 'error')
            self.add(self.note('启动不了：Python 没有跑起来', 'bad'))

    def done(self, *_a) -> None:
        self.proc = None
        self.run_btn.setEnabled(True)
        answer = {}
        for line in reversed(self.buffer.decode('utf-8', 'replace').splitlines()):
            try:
                answer = json.loads(line)
                break
            except ValueError:
                continue
        self.clear_results(keep_status=True)
        if not answer.get('ok'):
            self.say('没有做成', 'error')
            said = [x for x in self.buffer.decode('utf-8', 'replace').splitlines() if x.strip() and not x.lstrip().startswith('{')]
            self.add(self.note(str(answer.get('error') or '\n'.join(said[-4:]) or '没有结果'), 'bad'))
            return
        self.say('做好了', 'ok')
        for line in answer.get('lines', []):
            w = QLabel(line)
            w.setWordWrap(True)
            w.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.add(w)
        for line in answer.get('warnings', []):
            self.add(self.note(str(line), 'warn'))
        if answer.get('table'):
            self.add(self.table(answer['table']))
        for path in answer.get('pictures', [])[:3]:
            self.add(self.picture(path))
        files = answer.get('files', [])[:12]
        for path in files:
            b = look.button(Path(path).name, lambda p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)), 'file', 'file', str(path))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.add(b)
        total = len(answer.get('lines', [])) + len(answer.get('warnings', [])) + len(files)
        self.result_card.set_chip(f'{len(files)} 个文件' if files else (f'{total} 条' if total else ''))

    @staticmethod
    def note(text: str, kind: str) -> QFrame:
        box = QFrame()
        box.setObjectName(kind)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)
        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f'background:{AMBER if kind == "warn" else RED};border-radius:3px;')
        lay.addWidget(dot, 0, Qt.AlignTop)
        w = QLabel(text)
        w.setWordWrap(True)
        w.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(w, 1)
        return box

    def picture(self, path: str) -> QLabel:
        w = QLabel()
        pix = QPixmap(path)
        if not pix.isNull():
            ratio = self.devicePixelRatioF()
            pix = pix.scaledToWidth(int(min(520, pix.width()) * ratio), Qt.SmoothTransformation)
            pix.setDevicePixelRatio(ratio)
            w.setPixmap(pix)
            w.setStyleSheet(f'border:1px solid {RULE};border-radius:8px;padding:6px;background:#ffffff;')
            w.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        return w

    @staticmethod
    def table(rows: list) -> QTableWidget:
        t = QTableWidget(len(rows) - 1, max(map(len, rows)))
        t.setHorizontalHeaderLabels([str(c) for c in rows[0]])
        t.verticalHeader().hide()
        t.setShowGrid(False)
        t.setAlternatingRowColors(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for r, row in enumerate(rows[1:]):
            for c, v in enumerate(row):
                t.setItem(r, c, QTableWidgetItem(str(v)))
        t.resizeColumnsToContents()
        t.verticalHeader().setDefaultSectionSize(30)
        t.setFixedHeight(min(360, 36 + 30 * (len(rows) - 1)))
        t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return t

    def add(self, w: QWidget) -> None:
        if getattr(self, '_empty', None) is not None:
            self._empty.deleteLater()
            self._empty = None
        self.rl.addWidget(w)

    def clear_results(self, keep_status: bool = False) -> None:
        while self.rl.count():
            item = self.rl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._empty = Empty('play', '还没有运行', f'填好上面的内容，点“{self.run_btn.text()}”')
        self._empty.setMinimumHeight(160)
        self.rl.addWidget(self._empty)
        self.result_card.set_chip('')
        if not keep_status:
            self.say('')

    def open_results(self) -> None:
        folder = core.RESULTS / (self.current.id if self.current else '')
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def main() -> int:
    app = QApplication(sys.argv[:1])
    look.apply(app)
    win = Window(sys.argv[1] if len(sys.argv) > 1 else None)
    import embed
    embed.show(win)  # inside Lumen: taken into its window; alone: simply shown
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
