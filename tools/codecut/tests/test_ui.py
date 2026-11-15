"""What the window shows, as a person would see it: the stage while a project has no picture, the menu behind one button."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


class OwnProcess(unittest.TestCase):
    def test_the_window_tests_in_a_process_of_their_own(self):
        """A window's threads and player stay there: in one process with the decoder tests Qt ends the whole run."""
        if os.environ.get('CODECUT_WINDOW_TEST'):
            return
        out=subprocess.run([sys.executable,'-m','unittest','tests.test_ui'],cwd=ROOT,capture_output=True,timeout=120,
                           env={**os.environ,'CODECUT_WINDOW_TEST':'1','QT_QPA_PLATFORM':'offscreen'})
        self.assertEqual(out.returncode,0,out.stderr.decode('utf-8','replace')[-2000:])


@unittest.skipUnless(os.environ.get('CODECUT_WINDOW_TEST'),'runs in its own process')
class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication
        QCoreApplication.setOrganizationName('CodeCut-test')
        cls.app=QApplication.instance() or QApplication([])

    def window(self):
        import editor
        win=editor.EditorWindow()
        self.addCleanup(win.close)
        return win

    def test_an_empty_project_says_where_to_start(self):
        win=self.window()
        self.assertEqual(win.preview.currentIndex(),0)

    def test_clips_without_a_picture_never_show_the_start_page(self):
        win=self.window()
        win.model.data['scenes'].append({'source':'a.mp4','name':'a.mp4','duration':1})
        win.update_stage()
        self.assertEqual(win.preview.currentIndex(),2)
        self.assertIn('更新预览',win.pendingLabel.text())
        win.job=dict(preview=True)
        win.update_stage()
        self.assertIn('正在生成',win.pendingLabel.text())
        win.job=None
        win.model.data['scenes'].clear()
        win.update_stage()
        self.assertEqual(win.preview.currentIndex(),0)

    def test_the_menu_is_one_button_and_its_shortcuts_stay(self):
        win=self.window()
        self.assertTrue(win.menuBar().isHidden())
        titles=[a.text() for a in win.mainMenu.actions()]
        self.assertEqual(len(titles),3)
        keys=[a.shortcut().toString() for a in win.actions()]
        self.assertIn('Ctrl+S',keys)
        self.assertIn('Ctrl+Z',keys)


if __name__=='__main__':
    unittest.main()
