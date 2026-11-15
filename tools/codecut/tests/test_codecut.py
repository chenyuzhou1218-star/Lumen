"""Integration checks. Run: python -m unittest discover -s tests -v"""
import array
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import codecut as cut


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ff = cut.tool('ffmpeg')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='codecut-test-中文-')
        self.folder = Path(self.temp.name)
        self.project = self.folder / 'project.json'

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return cut.main([str(a) for a in args])

    def ffmpeg(self, *args):
        return cut.run([self.ff, '-hide_banner', '-loglevel', 'error', *args])

    def frame(self, source, t):
        return self.ffmpeg('-ss', t, '-i', source, '-frames:v', 1,
                           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-').stdout

    def audio(self, source, start, length):
        data = self.ffmpeg('-ss', start, '-i', source, '-t', length, '-vn', '-ac', 1,
                           '-ar', 48000, '-f', 'f32le', '-').stdout
        samples = array.array('f')
        samples.frombytes(data)
        return samples

    def test_demo_video_overlay_audio_and_timestamps(self):
        self.cli('demo', self.folder)
        out = self.folder / 'result.mp4'
        result = self.cli('render', self.project, '-o', out)
        self.assertEqual(result['duration'], 4)
        text = subprocess.run([self.ff, '-hide_banner', '-i', str(out)], capture_output=True).stderr.decode(errors='replace')
        self.assertIn('24 fps', text)
        self.assertAlmostEqual(cut.media_info(out)['duration'], 4, delta=.05)
        frames = self.ffmpeg('-i', out, '-map', '0:v:0', '-progress', 'pipe:1', '-f', 'null', '-').stdout
        self.assertEqual(int(re.findall(rb'(?m)^frame=(\d+)', frames)[-1]), 96)
        a, b = self.frame(out, .2), self.frame(out, 1.2)
        self.assertNotEqual(a, b, 'Code animation should change over time')
        b = self.frame(out, 3)
        # The top-left of the opaque code overlay is a dark blue background.
        offset = (200*640+370)*3
        self.assertLess(max(b[offset:offset+3]), 100)
        self.assertLess(max(map(abs, self.audio(out, .05, .25))), .001)
        self.assertGreater(max(map(abs, self.audio(out, .7, .25))), .01)

    def test_editing_and_validation_are_atomic(self):
        self.cli('init', self.project, '--width', 320, '--height', 180, '--fps', 10)
        self.ffmpeg('-f', 'lavfi', '-i', 'sine=duration=2', self.folder/'a.wav')
        # Audio can be added before any visuals.
        self.cli('add', self.project, 'audio', self.folder/'a.wav', '--id', 'a')
        shutil.copy(ROOT/'examples'/'animation.html', self.folder/'index.html')
        self.cli('add', self.project, 'code', self.folder, '--duration', '.5', '--id', 'one')
        self.cli('add', self.project, 'code', self.folder, '--duration', '.5', '--id', 'two')
        self.cli('move', self.project, 'two', '1')
        self.assertEqual(cut.load(self.project)['scenes'][0]['id'], 'two')
        before = self.project.read_bytes()
        with self.assertRaises(cut.CutError):
            self.cli('set', self.project, 'a', 'volume', 'nan')
        self.assertEqual(before, self.project.read_bytes())
        with self.assertRaises(cut.CutError):
            self.cli('add', self.project, 'code', self.folder, '--id', 'two')
        self.assertEqual(before, self.project.read_bytes())
        self.cli('remove', self.project, 'one')
        self.assertEqual(len(cut.load(self.project)['scenes']), 1)

    def test_browser_clock_without_hook_and_http_url(self):
        page = self.folder/'index.html'
        page.write_text('''<style>body{margin:0;background:black}</style><canvas width=160 height=90 id=c></canvas>
          <script>const x=c.getContext('2d');let n=0;function f(){x.fillStyle='rgb('+Math.min(255,++n*5)+',0,0)';
          x.fillRect(0,0,160,90);requestAnimationFrame(f)}requestAnimationFrame(f)</script>''', encoding='utf-8')
        self.cli('init', self.project, '--width', 160, '--height', 90, '--fps', 10)
        with cut.serve(self.folder) as url:
            self.cli('add', self.project, 'code', url+'/index.html', '--duration', '.5', '--wait', '0', '--id', 'clock')
            out = self.folder/'clock.mp4'
            self.cli('render', self.project, '-o', out)
        first, last = self.frame(out, 0), self.frame(out, .4)
        self.assertGreater(last[0], first[0]+30)

    def test_video_trim_silent_source_and_still_image(self):
        video = self.folder/'silent.mp4'
        self.ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=10:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', video)
        image = self.folder/'red.ppm'
        image.write_bytes(b'P6\n160 90\n255\n'+bytes([255, 0, 0])*160*90)
        self.cli('init', self.project, '--width', 160, '--height', 90, '--fps', 10)
        self.cli('add', self.project, 'video', video, '--trim', '.4', '--duration', '.4', '--id', 'v')
        self.cli('add', self.project, 'image', image, '--duration', '.3', '--id', 'i')
        out = self.folder/'out.mp4'
        self.cli('render', self.project, '-o', out)
        rgb = self.frame(out, .5)
        self.assertGreater(rgb[0], 230)
        self.assertLess(rgb[1], 10)
        self.assertAlmostEqual(cut.media_info(out)['duration'], .7, delta=.05)
        self.assertLess(max(map(abs, self.audio(out, 0, .6))), .001)
        # Existing outputs and original sources cannot be overwritten.
        before = out.read_bytes()
        with self.assertRaises(cut.CutError):
            self.cli('render', self.project, '-o', out)
        self.assertEqual(before, out.read_bytes())
        with self.assertRaises(cut.CutError):
            self.cli('render', self.project, '-o', video, '--force')

    def test_page_error_does_not_publish_partial_output(self):
        page = self.folder/'bad.html'
        page.write_text('<script>window.renderFrame=()=>{throw Error("broken frame")}</script>')
        self.cli('init', self.project, '--width', 160, '--height', 90, '--fps', 10)
        self.cli('add', self.project, 'code', page, '--duration', '.2')
        out = self.folder/'bad.mp4'
        with self.assertRaises(Exception):
            self.cli('render', self.project, '-o', out)
        self.assertFalse(out.exists())

    def test_git_repository_import(self):
        git = shutil.which('git')
        if not git:
            self.skipTest('Git not installed')
        repo = self.folder/'source'
        repo.mkdir()
        (repo/'index.html').write_text('<h1>real repository</h1>')
        cut.run([git, 'init', repo])
        cut.run([git, '-C', repo, 'add', 'index.html'])
        cut.run([git, '-C', repo, '-c', 'user.name=CodeCut Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'test'])
        clone = self.folder/'clone'
        result = self.cli('repo', repo, clone)
        self.assertIn('index.html', result['html_entries'])
        self.cli('init', self.project, '--width', 160, '--height', 90, '--fps', 10)
        self.cli('add', self.project, 'code', clone, '--duration', '.2', '--id', 'repo')
        out = self.folder/'repo.mp4'
        self.cli('preview', self.project, '--scene', 'repo', '-o', out)
        self.assertTrue(out.exists())


if __name__ == '__main__':
    unittest.main()
