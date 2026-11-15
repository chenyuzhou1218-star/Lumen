"""Editing for agents: the CLI's split / text / update / duplicate / info, and the window following a project an AI
edits (--follow; Code Doctor's @CodeCut and the AI 剪辑 panel)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import codecut as cut


def cli(*args, cwd):
    out = subprocess.run([sys.executable, str(ROOT / 'codecut.py'), *map(str, args)], cwd=cwd, capture_output=True,
                         env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    return json.loads(out.stdout.decode('utf-8').strip().splitlines()[-1]), out.returncode


class CliEditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='codecut-ai-')
        self.folder = Path(self.temp.name)
        ff = cut.tool('ffmpeg')
        (self.folder / 'media').mkdir()
        cut.run([ff, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=10:d=2', '-c:v', 'libx264',
                 '-pix_fmt', 'yuv420p', self.folder / 'media' / 'clip.mp4'])
        self.assertEqual(cli('init', 'p.json', '--width', 160, '--height', 90, '--fps', 10, cwd=self.folder)[1], 0)
        self.assertEqual(cli('add', 'p.json', 'video', 'media/clip.mp4', '--id', 'v', cwd=self.folder)[1], 0)

    def tearDown(self):
        self.temp.cleanup()

    def project(self):
        return json.loads((self.folder / 'p.json').read_text(encoding='utf-8'))

    def test_split_text_update_duplicate_info(self):
        self.assertEqual(self.project()['scenes'][0]['source'], 'media/clip.mp4')  # forward slashes, also on Windows
        res, code = cli('split', 'p.json', 'v', 1.2, cwd=self.folder)
        self.assertEqual(code, 0)
        right = res['right']
        self.assertEqual([round(s['duration'], 2) for s in self.project()['scenes']], [1.2, 0.8])
        self.assertAlmostEqual(self.project()['scenes'][1]['trim'], 1.2)
        res, code = cli('update', 'p.json', right, '{"speed": 2, "fade_out": 0.2}', cwd=self.folder)
        self.assertEqual(code, 0)
        self.assertAlmostEqual(self.project()['scenes'][1]['duration'], 0.4)  # the editor's rule: speed rescales
        self.assertEqual(cli('text', 'p.json', '你好', '--start', 0, '--duration', 1, '--id', 'title', cwd=self.folder)[1], 0)
        title = self.project()['texts'][0]
        self.assertEqual((title['id'], title['text'], title['x'], title['y']), ('title', '你好', 80, 72))
        self.assertEqual(cli('duplicate', 'p.json', 'v', cwd=self.folder)[1], 0)
        self.assertEqual(len(self.project()['scenes']), 3)
        info, code = cli('info', 'media/clip.mp4', cwd=self.folder)
        self.assertTrue(info['ok'] and info['video'] and abs(info['duration'] - 2) < .05)

    def test_bad_edits_say_why_and_change_nothing(self):
        before = self.project()
        for args, words in [(('split', 'p.json', 'v', 0.01), 'inside the clip'), (('split', 'p.json', 'nope', 1), 'not found'),
                            (('update', 'p.json', 'v', '{"id": "x"}'), 'cannot be changed'),
                            (('update', 'p.json', 'v', 'speed=2'), 'JSON object'),
                            (('text', 'p.json', 'x', '--id', 'v'), 'already used')]:
            res, code = cli(*args, cwd=self.folder)
            self.assertEqual(code, 1)
            self.assertIn(words, res['error'])
        self.assertEqual(self.project(), before)


class FollowTests(unittest.TestCase):
    def test_the_window_shows_each_change_an_ai_makes_but_never_drops_your_unsaved_edits(self):
        if not os.environ.get('CODECUT_WINDOW_TEST'):  # a window of its own process: its threads and player stay there
            out = subprocess.run([sys.executable, '-m', 'unittest', 'tests.test_ai.FollowTests'], cwd=ROOT,
                                 capture_output=True, timeout=300,
                                 env={**os.environ, 'CODECUT_WINDOW_TEST': '1', 'QT_QPA_PLATFORM': 'offscreen'})
            self.assertEqual(out.returncode, 0, out.stderr.decode('utf-8', 'replace')[-3000:])
            return
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        import editor
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix='codecut-follow-') as tmp:
            folder = Path(tmp)
            ff = cut.tool('ffmpeg')
            cut.run([ff, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=10:d=2', '-c:v', 'libx264',
                     '-pix_fmt', 'yuv420p', folder / 'clip.mp4'])
            self.assertEqual(editor.newest_project(folder), None)
            cli('init', 'cut.json', '--width', 160, '--height', 90, '--fps', 10, cwd=folder)
            cli('add', 'cut.json', 'video', 'clip.mp4', '--id', 'v', cwd=folder)
            win = editor.EditorWindow()

            def settle():  # thumbnails are read in the background; a reload waits for them
                end = time.time() + 15
                while (win.tasks or time.time() < end - 14.7) and time.time() < end:
                    app.processEvents()
                    time.sleep(0.02)
            try:
                win.follow(folder)
                settle()
                self.assertEqual(win.model.path, (folder / 'cut.json').resolve())
                self.assertEqual(len(win.model.data['scenes']), 1)
                time.sleep(0.05)
                cli('split', 'cut.json', 'v', 1, cwd=folder)  # the AI edits
                settle()
                win.tasks.append(object())  # a still frame being read: it once kept every AI edit off the screen
                win.follow_tick()
                win.tasks.clear()
                self.assertEqual(len(win.model.data['scenes']), 2)
                win.model.update('v', {'volume': 0.5})  # your own edit, not saved
                cli('text', 'cut.json', 'hi', cwd=folder)
                settle()
                win.follow_tick()
                self.assertTrue(win.model.dirty and not win.model.data['texts'])  # kept; the status bar explains
                # every preview gets a new file, also across reloads (the same name was once refused by Windows
                # because the player still held it, and an error box popped up after the AI's edit)
                names = []
                win.start_job = lambda data, output, preview: names.append(output.name)
                win.cancel_job()
                for _ in range(2):  # an AI's edit reopens the project: its revisions start again
                    win.open_path(folder / 'cut.json')
                    win.proc = None
                    win.start_preview()
                self.assertEqual(len(set(names)), len(names))
                self.assertGreaterEqual(len(names), 2)
                for _ in range(20):
                    app.processEvents()
            finally:
                win.model.dirty = False
                win.cancel_job()
                win.close()
                for _ in range(20):
                    app.processEvents()
                    time.sleep(0.02)


if __name__ == '__main__':
    unittest.main()
