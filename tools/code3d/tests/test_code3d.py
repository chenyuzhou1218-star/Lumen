"""The command line and the window. Tests that need Blender run the real one, and are skipped where it is not installed."""
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
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import code3d as core

HAS_BLENDER = core.find_blender() is not None


def run(*args):
    out = subprocess.run([sys.executable, str(ROOT / 'code3d.py'), *map(str, args)], capture_output=True, timeout=240)
    return json.loads(out.stdout.decode('utf-8').strip().splitlines()[-1])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / 'p'


class Project(Base):
    def test_init_then_check(self):
        self.assertTrue(run('init', self.dir, '--width', 320)['ok'])
        self.assertEqual(core.load(self.dir)['width'], 320)
        self.assertTrue(run('check', self.dir)['ok'])
        self.assertFalse(run('init', self.dir)['ok'])  # never over an existing project

    def test_check_finds_a_broken_line_without_blender(self):
        run('init', self.dir)
        (self.dir / 'scene.py').write_text('import c3d\nc3d.sky(\n', encoding='utf-8')
        answer = run('check', self.dir)
        self.assertFalse(answer['ok'])
        self.assertEqual(answer['line'], 2)
        (self.dir / 'scene.py').write_text('import c3d\nc3d.no_such_thing()\n', encoding='utf-8')
        self.assertIn('no_such_thing', run('check', self.dir)['error'])

    def test_a_folder_without_a_project_says_so(self):
        self.dir.mkdir()
        self.assertIn('不是 Code3D 项目', run('check', self.dir)['error'])

    def test_settings_are_checked(self):
        run('init', self.dir)
        data = json.loads((self.dir / 'project.json').read_text(encoding='utf-8'))
        (self.dir / 'project.json').write_text(json.dumps({**data, 'width': 0}), encoding='utf-8')
        self.assertIn('width', run('check', self.dir)['error'])
        (self.dir / 'project.json').write_text(json.dumps({**data, 'script': '../x.py'}), encoding='utf-8')
        self.assertIn('script', run('check', self.dir)['error'])

    def test_output_stays_in_the_project(self):
        run('init', self.dir)
        self.assertIn('不在项目文件夹里', run('render', self.dir, '-o', '../x.png')['error'])

    def test_the_kit_is_described_from_its_own_source(self):
        kit = {f['call'].split('(')[0] for f in run('schema')['c3d']}
        self.assertTrue({'c3d.sky', 'c3d.camera', 'c3d.lathe', 'c3d.preset'} <= kit)
        self.assertFalse([k for k in kit if k.startswith('c3d._')])


@unittest.skipUnless(HAS_BLENDER, 'Blender is not installed')
class Real(Base):
    def test_stopping_the_command_stops_blender(self):
        """A cancelled render must not go on eating the processor behind the user's game."""
        run('init', self.dir, '--width', 1920, '--height', 1080, '--samples', 4096)
        (self.dir / 'scene.py').write_text('import c3d\nc3d.sky()\nc3d.ground()\nc3d.sphere(.5, at=(0,0,.5), mat=\'glass\')\nc3d.camera()\n', encoding='utf-8')
        proc = subprocess.Popen([sys.executable, str(ROOT / 'code3d.py'), 'render', str(self.dir), '--quality', 'final'], stdout=subprocess.PIPE)
        self.addCleanup(proc.stdout.close)
        for line in proc.stdout:
            if b'"render"' in line:
                break
        query = f"(Get-CimInstance Win32_Process -Filter 'ParentProcessId={proc.pid}').ProcessId"
        ask = lambda: subprocess.run(['powershell', '-NoProfile', '-Command', query], capture_output=True).stdout.decode().split()
        child = ask()
        self.assertTrue(child)
        proc.kill()
        proc.wait()
        gone = f"Get-Process -Id {child[0]} -ErrorAction SilentlyContinue"
        for _ in range(20):
            if not subprocess.run(['powershell', '-NoProfile', '-Command', gone], capture_output=True).stdout.strip():
                return
            time.sleep(.5)
        self.fail('Blender went on after the command was stopped')

    def test_a_scene_without_light_or_camera_still_shows_something_and_says_so(self):
        run('init', self.dir, '--width', 160, '--height', 90)
        (self.dir / 'scene.py').write_text('import c3d\nc3d.box(1, mat=\'plastic\')\n', encoding='utf-8')
        answer = run('render', self.dir, '--view', 'camera')
        self.assertTrue(answer['ok'], answer)
        words = ' '.join(answer['warnings'])
        self.assertIn('没有灯光', words)
        self.assertIn('没有相机', words)
        self.assertTrue((self.dir / 'out' / 'latest.png').is_file())


    def test_the_notes_say_what_is_wrong_with_the_picture(self):
        run('init', self.dir, '--width', 160, '--height', 90)
        (self.dir / 'scene.py').write_text("""import c3d
c3d.ground()
c3d.box(.3, at=(0, 0, .6), mat='plastic', name='crate')
c3d.mug(at=(9, 9, 0))
c3d.point(at=(0, 0, 2), power=1, colour=c3d.kelvin(1900))
c3d.camera(at=(2, -3, 1), look=(0, 0, .5))
""", encoding='utf-8')
        words = ' '.join(run('render', self.dir, '--quality', 'check')['warnings'])
        self.assertIn('crate 悬空', words)
        self.assertIn('mug 不在画面里', words)
        self.assertIn('太暗', words)

    def test_the_ready_things_build(self):
        run('init', self.dir, '--width', 160, '--height', 90)
        (self.dir / 'scene.py').write_text("""import c3d
c3d.dusk()
c3d.room()
c3d.street_outside()
c3d.table(at=(0, 1, 0))
c3d.mug(at=(.2, 1, .75), drink='coffee')
c3d.cup_and_saucer(at=(-.1, 1, .75), drink='water')
c3d.book(at=(.3, 1.1, .75))
c3d.potted_plant(at=(-.3, 1.1, .75))
c3d.pendant_lamp(at=(0, 1, 2.7))
c3d.camera(at=(0, -1, 1.2), look=(0, 1, .8), blur=2, focus=(0, 1, .8))
""", encoding='utf-8')
        answer = run('objects', self.dir)
        self.assertTrue(answer['ok'], answer)
        self.assertGreater(answer['count'], 60)


class Window(Base):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication
        QCoreApplication.setOrganizationName('Code3D-test')
        cls.app = QApplication.instance() or QApplication([])

    def window(self, **kw):
        import editor
        win = editor.EditorWindow(**kw)
        self.addCleanup(lambda: (setattr(win, 'saved_text', win.code.toPlainText()), win.close()))  # no "save?" question in a test
        return win

    def project(self):
        run('init', self.dir)
        win = self.window()
        win.open_project(self.dir)
        return win

    def test_nothing_runs_without_a_project(self):
        win = self.window()
        win.folder = None
        win.enable()
        self.assertFalse(win.preview_button.isEnabled())
        win.render('draft')
        self.assertIsNone(win.proc)

    def test_saving_and_outside_changes(self):
        win = self.project()
        self.assertFalse(win.dirty)
        win.code.insertPlainText('# mine\n')
        self.assertTrue(win.dirty)
        win.save()
        self.assertFalse(win.dirty)
        self.assertIn('# mine', (self.dir / 'scene.py').read_text(encoding='utf-8'))
        time.sleep(.05)
        (self.dir / 'scene.py').write_text('# the agent\n', encoding='utf-8')
        os.utime(self.dir / 'scene.py', (time.time() + 5, time.time() + 5))
        win.follow_tick()
        self.assertEqual(win.code.toPlainText(), '# the agent\n')  # nothing of yours to lose: it comes in by itself
        win.code.insertPlainText('# mine again\n')
        (self.dir / 'scene.py').write_text('# the agent again\n', encoding='utf-8')
        os.utime(self.dir / 'scene.py', (time.time() + 9, time.time() + 9))
        win.follow_tick()
        self.assertIn('# mine again', win.code.toPlainText())  # your unsaved work is never replaced by surprise
        self.assertFalse(win.reload_button.isHidden())

    def test_settings_go_to_the_project_file(self):
        win = self.project()
        win.fields['width'].setValue(640)
        self.assertEqual(core.load(self.dir)['width'], 640)

    def test_an_error_marks_its_line(self):
        win = self.project()
        win.code.setPlainText('a\nb\nc\n')
        win.code.show_error(2)
        self.assertEqual(win.code.textCursor().blockNumber(), 1)
        win.code.insertPlainText('x')  # typing clears the mark
        self.assertIsNone(win.code.error_line)

    def test_a_watched_folder_brings_up_the_project_being_made(self):
        base = Path(self.tmp.name) / 'root'
        base.mkdir()
        win = self.window(watch=base)
        win.folder = None
        win.watch_since = time.time() - 60
        target = base / '3d' / 'chair'
        run('init', target)
        for _ in range(3):
            win.follow_tick()
        self.assertEqual(win.folder, target.resolve())


if __name__ == '__main__':
    unittest.main()
