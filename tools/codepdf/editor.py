"""CodePDF's window: pick a tool on the left, fill in a short form, start. The work itself is in codepdf.py.

    editor.py [tool]
"""
from __future__ import annotations

import right_python

right_python.use('PySide6', 'PIL')

from pathlib import Path  # noqa: E402
import sys  # noqa: E402

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QUrl, Signal  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,  # noqa: E402
                               QListWidgetItem, QMainWindow, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

import codepdf as core  # noqa: E402
import look  # noqa: E402
from look import AMBER, GREEN, INK2, INK3, RED, RULE, TINT, Card, Empty, Mark  # noqa: E402
from words import t  # noqa: E402

EXTRA = f"""
QWidget#side {{ background: #ffffff; border-right: 1px solid {RULE}; }}
QListWidget#tools {{ background: transparent; padding: 12px 8px; }}
QListWidget#tools::item {{ height: 32px; padding: 0 10px; border-radius: 7px; color: {INK2}; }}
QListWidget#tools::item:hover {{ background: {TINT}; color: #111113; }}
QListWidget#tools::item:selected {{ background: #f4f4f5; color: #111113; }}
QListWidget#files {{ background: #ffffff; border: 1px solid {RULE}; border-radius: 10px; padding: 4px; }}
QListWidget#files::item {{ height: 28px; padding: 0 8px; border-radius: 6px; }}
QListWidget#files::item:selected {{ background: #f4f4f5; color: #111113; }}
QLabel#fieldLabel {{ color: {INK2}; font-size: 12px; }}
QLabel#plugTitle {{ font-size: 18px; font-weight: 650; }}
QFrame#bad {{ background: #fdf1f0; border: 1px solid #f3d2ce; border-radius: 10px; }}
QPushButton#file {{ text-align: left; padding: 0 12px; border-color: {RULE}; }}
"""

SIZES = [('A4', 'A4'), ('A3', 'A3'), ('A5', 'A5'), ('Letter', 'Letter')]

# tool -> (glyph, title key, blurb key, fields). Field kinds: images / pdfs (a list), pdf (one file), combo, text, out
SPECS = {
    'images': ('image', 'img.title', 'img.blurb', [
        ('images', 'files', 'list.img'),
        ('combo', 'size', 'img.size', [('A4', 'A4'), ('A3', 'A3'), ('A5', 'A5'), ('Letter', 'Letter'), ('fit', 'img.fit')]),
        ('combo', 'margin', 'img.margin', [('0', 'img.m0'), ('1', 'img.m1'), ('2', 'img.m2')])]),
    'merge': ('file', 'merge.title', 'merge.blurb', [('pdfs', 'files', 'list.pdf')]),
    'split': ('list', 'split.title', 'split.blurb', [
        ('pdf', 'file', 'pick.pdf'),
        ('combo', 'mode', 'split.mode', [('each', 'split.each'), ('every', 'split.every'), ('ranges', 'split.ranges')]),
        ('text', 'n', 'split.n', '2'),
        ('text', 'ranges', 'split.ranges.hint', '')]),
    'compress': ('chart', 'compress.title', 'compress.blurb', [
        ('pdf', 'file', 'pick.pdf'),
        ('combo', 'level', 'compress.level', [('light', 'compress.light'), ('mid', 'compress.mid'), ('strong', 'compress.strong')], 1)]),
    'size': ('page', 'size.title', 'size.blurb', [
        ('pdf', 'file', 'pick.pdf'),
        ('combo', 'to', 'size.to', SIZES)]),
    'rotate': ('refresh', 'rotate.title', 'rotate.blurb', [
        ('pdf', 'file', 'pick.pdf'),
        ('combo', 'by', 'rotate.by', [('90', 'rotate.r90'), ('180', 'rotate.r180'), ('270', 'rotate.r270')]),
        ('text', 'pages', 'pages.hint', '')]),
    'pick': ('close', 'pick.title', 'pick.blurb', [
        ('pdf', 'file', 'pick.pdf'),
        ('combo', 'do', 'pick.do', [('keep', 'pick.keep'), ('drop', 'pick.drop')]),
        ('text', 'pages', 'pages.hint', '')]),
}


class Worker(QThread):
    finished_with = Signal(dict)

    def __init__(self, tool: str, args: dict):
        super().__init__()
        self.tool, self.args = tool, args

    def run(self) -> None:
        try:
            answer = core.run(self.tool, self.args)
        except core.Stop as e:
            answer = {'ok': False, 'error': str(e)}
        except Exception as e:  # noqa: BLE001 (whatever goes wrong, the window says it instead of dying)
            answer = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
        self.finished_with.emit(answer)


class Picker(QWidget):
    """One path (a PDF, or a folder) and a button that looks for it."""

    def __init__(self, hint: str, folder: bool = False):
        super().__init__()
        self.folder = folder
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(hint)
        lay.addWidget(self.edit, 1)
        lay.addWidget(look.button(t('pick'), self.pick, '', 'folder'))

    def pick(self) -> None:
        if self.folder:
            path = QFileDialog.getExistingDirectory(self, t('pick.folder'))
        else:
            path = QFileDialog.getOpenFileName(self, t('pick.pdf'), '', t('filter.pdf'))[0]
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()


class FileList(QWidget):
    """Several files in the order the result will have them."""

    def __init__(self, images: bool):
        super().__init__()
        self.images = images
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.list = QListWidget()
        self.list.setObjectName('files')
        self.list.setMinimumHeight(120)
        self.list.setMaximumHeight(200)
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(look.button(t('add'), self.add, '', 'plus'))
        row.addWidget(look.button(t('up'), lambda: self.move(-1), '', 'chev'))
        row.addWidget(look.button(t('down'), lambda: self.move(1), '', 'chev'))
        row.addWidget(look.button(t('remove'), self.remove, 'ghost', 'close'))
        row.addStretch(1)
        lay.addLayout(row)

    def add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, t('add'), '', t('filter.img' if self.images else 'filter.pdf'))
        for p in paths:
            item = QListWidgetItem(Path(p).name)
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            self.list.addItem(item)

    def remove(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def move(self, step: int) -> None:
        rows = sorted((self.list.row(i) for i in self.list.selectedItems()), reverse=step > 0)
        for r in rows:
            to = r + step
            if 0 <= to < self.list.count():
                item = self.list.takeItem(r)
                self.list.insertItem(to, item)
                item.setSelected(True)

    def value(self) -> list:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]


class Window(QMainWindow):
    def __init__(self, start: str | None = None):
        super().__init__()
        self.setWindowTitle(t('app'))
        self.setStyleSheet(look.THEME + EXTRA)
        self.resize(1100, 740)
        self.setMinimumSize(420, 420)
        self.prefs = QSettings('Lumen', 'CodePDF')
        self.tool = ''
        self.widgets: dict = {}
        self.worker: Worker | None = None
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
        top.addWidget(Mark('file'))
        name = QLabel(t('app'))
        name.setObjectName('title')
        top.addWidget(name)
        count = QLabel(t('chip', len(SPECS)))
        count.setObjectName('chip')
        count.setFixedHeight(20)
        top.addWidget(count)
        top.addStretch(1)
        top.addWidget(look.button(t('results'), self.open_results, 'ghost', 'folder', t('results.tip')))
        outer.addWidget(bar)

        main = QHBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        side = QWidget()
        side.setObjectName('side')
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(200)
        self.side = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setObjectName('tools')
        self.list.setIconSize(QSize(14, 14))
        for key, spec in SPECS.items():
            item = QListWidgetItem(look.icon(spec[0], INK3), t(spec[1]))
            item.setData(Qt.UserRole, key)
            self.list.addItem(item)
        self.list.currentItemChanged.connect(self.picked)
        sl.addWidget(self.list, 1)
        main.addWidget(side)

        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        bl = QVBoxLayout(inner)
        bl.setContentsMargins(28, 22, 28, 26)
        self.page_lay, self.margins = bl, (28, 22, 28, 26)
        self.picker = QComboBox()  # the narrow form of the list on the left
        for key, spec in SPECS.items():
            self.picker.addItem(t(spec[1]), key)
        self.picker.currentIndexChanged.connect(self.pick_from_box)
        self.picker.hide()
        bl.addWidget(self.picker)
        bl.setSpacing(16)
        self.title = QLabel('')
        self.title.setObjectName('plugTitle')
        self.title.setWordWrap(True)
        bl.addWidget(self.title)
        self.blurb = QLabel('')
        self.blurb.setObjectName('muted')
        self.blurb.setWordWrap(True)
        bl.addWidget(self.blurb)

        self.form_card = Card(t('fill'), 'list')
        self.form_box = QWidget()
        self.form = QVBoxLayout(self.form_box)
        self.form.setContentsMargins(16, 14, 16, 6)
        self.form.setSpacing(8)
        self.form_card.body.addWidget(self.form_box)
        run_row = QHBoxLayout()
        run_row.setContentsMargins(16, 8, 16, 14)
        run_row.setSpacing(10)
        self.run_btn = look.button(t('run'), self.run, 'primary', 'play')
        run_row.addWidget(self.run_btn)
        self.light = QLabel()
        self.light.setFixedSize(7, 7)
        run_row.addWidget(self.light)
        self.status = QLabel('')
        self.status.setObjectName('faint')
        self.status.setWordWrap(True)
        run_row.addWidget(self.status, 1)
        self.form_card.body.addLayout(run_row)
        bl.addWidget(self.form_card)

        self.result_card = Card(t('result'), 'check')
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
        keys = list(SPECS)
        last = start if start in SPECS else self.prefs.value('tool', '')
        self.list.setCurrentRow(keys.index(last) if last in SPECS else 0)

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

    def say(self, text: str, kind: str = '') -> None:
        self.status.setText(text)
        color = {'busy': AMBER, 'ok': GREEN, 'error': RED}.get(kind, '#d0d0d5')
        self.light.setStyleSheet(f'background:{color};border-radius:3px;')

    def picked(self, item, _old=None) -> None:
        if item is None:
            return
        self.tool = item.data(Qt.UserRole)
        if hasattr(self, 'picker'):
            self.picker.blockSignals(True)
            self.picker.setCurrentIndex(self.list.row(item))
            self.picker.blockSignals(False)
        self.prefs.setValue('tool', self.tool)
        _glyph, title, blurb, fields = SPECS[self.tool]
        self.title.setText(t(title))
        self.blurb.setText(t(blurb))
        while self.form.count():
            w = self.form.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.widgets = {}
        for spec in fields:
            kind, key = spec[0], spec[1]
            label = QLabel(t(spec[2]) if kind != 'text' else t('pages') if key == 'pages' else t(spec[2]))
            label.setObjectName('fieldLabel')
            label.setWordWrap(True)
            if kind in ('images', 'pdfs'):
                w = FileList(kind == 'images')
            elif kind == 'pdf':
                w = Picker(t('pick.pdf'))
                label = None
            elif kind == 'combo':
                w = QComboBox()
                for value, text in spec[3]:
                    w.addItem(t(text) if text not in ('A4', 'A3', 'A5', 'Letter') else text, value)
                w.setCurrentIndex(spec[4] if len(spec) > 4 else 0)
            else:
                w = QLineEdit(spec[3])
                w.setPlaceholderText(t(spec[2]))
                label = QLabel(t('split.n') if key == 'n' else t('split.ranges') if key == 'ranges' else t('pages'))
                label.setObjectName('fieldLabel')
            if label is not None:
                self.form.addWidget(label)
            self.form.addWidget(w)
            self.widgets[key] = w
        label = QLabel(t('out'))
        label.setObjectName('fieldLabel')
        self.form.addWidget(label)
        out = Picker(t('out.hint'), folder=True)
        self.form.addWidget(out)
        self.widgets['out'] = out
        if 'mode' in self.widgets:
            self.widgets['mode'].currentIndexChanged.connect(self.split_mode)
            self.split_mode()
        self.form_card.set_chip(t('items', len(self.widgets)))
        self.clear_results()
        if self.tool != 'images' and not core.has_pypdf():
            self.say(t('err.lib'), 'error')

    def split_mode(self) -> None:
        mode = self.widgets['mode'].currentData()
        self.widgets['n'].setVisible(mode == 'every')
        self.widgets['ranges'].setVisible(mode == 'ranges')
        for key, shown in (('n', mode == 'every'), ('ranges', mode == 'ranges')):
            idx = self.form.indexOf(self.widgets[key])
            label = self.form.itemAt(idx - 1).widget() if idx > 0 else None
            if isinstance(label, QLabel):
                label.setVisible(shown)

    def values(self) -> dict:
        out = {}
        for key, w in self.widgets.items():
            out[key] = w.currentData() if isinstance(w, QComboBox) else w.text().strip() if isinstance(w, QLineEdit) else w.value()
        return out

    def run(self) -> None:
        if self.worker is not None:
            return
        self.clear_results(keep_status=True)
        self.run_btn.setEnabled(False)
        self.say(t('busy'), 'busy')
        self.worker = Worker(self.tool, self.values())
        self.worker.finished_with.connect(self.done)
        self.worker.start()

    def done(self, answer: dict) -> None:
        if self.worker is not None:
            self.worker.wait()
        self.worker = None
        self.run_btn.setEnabled(True)
        self.clear_results(keep_status=True)
        if not answer.get('ok'):
            self.say(t('bad'), 'error')
            self.add(self.note(str(answer.get('error') or t('bad'))))
            return
        self.say(t('ok'), 'ok')
        for line in answer.get('lines', []):
            w = QLabel(line)
            w.setWordWrap(True)
            w.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.add(w)
        files = answer.get('files', [])
        for path in files:
            b = look.button(Path(path).name, lambda _=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)), 'file', 'file', str(path))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.add(b)
        if files:
            self.last_folder = str(Path(files[0]).parent)
        self.result_card.set_chip(t('files', len(files)) if files else '')

    @staticmethod
    def note(text: str) -> QFrame:
        box = QFrame()
        box.setObjectName('bad')
        lay = QHBoxLayout(box)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)
        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f'background:{RED};border-radius:3px;')
        lay.addWidget(dot, 0, Qt.AlignTop)
        w = QLabel(text)
        w.setWordWrap(True)
        w.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(w, 1)
        return box

    def add(self, w: QWidget) -> None:
        if getattr(self, '_empty', None) is not None:
            self._empty.deleteLater()
            self._empty = None
        self.rl.addWidget(w)

    def clear_results(self, keep_status: bool = False) -> None:
        self._empty = None
        while self.rl.count():
            item = self.rl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not keep_status:
            self._empty = Empty('play', t('empty'), t('empty.hint', t('run')))
            self._empty.setMinimumHeight(140)
            self.rl.addWidget(self._empty)
            self.say('')
        self.result_card.set_chip('')

    def open_results(self) -> None:
        folder = getattr(self, 'last_folder', '') or str(Path.home() / 'Documents')
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def closeEvent(self, e):
        if self.worker is not None and not self.worker.wait(3000):
            e.ignore()  # still working on a file: closing now would cut it off
            self.say(t('busy'), 'busy')
            return
        super().closeEvent(e)


def main() -> int:
    app = QApplication(sys.argv[:1])
    look.apply(app)
    win = Window(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in SPECS else None)
    import embed
    embed.show(win)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
