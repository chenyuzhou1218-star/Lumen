"""Verify the video decoding worker without controlling any desktop windows."""
from pathlib import Path
import sys
import tempfile
import unittest
from PySide6.QtCore import QCoreApplication,QEventLoop,QTimer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import codecut as cut
from editor import PreviewDecoder


class DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QCoreApplication.instance() or QCoreApplication([])
    def test_decodes_each_frame_and_reopens_another_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            for i,color in enumerate(['red','blue']):
                cut.run([cut.tool('ffmpeg'),'-v','error','-f','lavfi','-i',f'color=c={color}:s=160x90:r=10:d=0.5',
                         '-c:v','libx264','-pix_fmt','yuv420p',path/f'{i}.mp4'])
            colors=[]
            for i in range(2):
                loop=QEventLoop()
                frames=[]
                decoder=PreviewDecoder(path/f'{i}.mp4',0,10,160,90)
                decoder.frameReady.connect(lambda image,t:frames.append((image.pixelColor(50,50).getRgb(),t)))
                decoder.finished.connect(loop.quit)
                watchdog=QTimer()
                watchdog.setSingleShot(True)
                watchdog.timeout.connect(loop.quit)
                watchdog.start(10000)
                decoder.start()
                loop.exec()
                decoder.stop()
                watchdog.stop()
                self.assertEqual(len(frames),5)
                self.assertAlmostEqual(frames[-1][1],.4)
                colors.append(frames[0][0])
            self.assertGreater(colors[0][0],200)
            self.assertLess(colors[0][2],20)
            self.assertGreater(colors[1][2],200)
            self.assertLess(colors[1][0],20)


if __name__=='__main__':unittest.main()
