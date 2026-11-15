"""Core editing and exported media tests for the desktop editor."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import codecut as cut
from editor_model import EditorModel


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='codecut-edit-')
        self.folder=Path(self.temp.name)
        self.model=EditorModel()
        self.model.path=self.folder/'project.json'
        self.model.data.update(width=160,height=90,fps=10)
        self.ff=cut.tool('ffmpeg')
        self.video=self.folder/'source.mp4'
        cut.run([self.ff,'-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=10:d=2',
                 '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2',
                 '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',self.video])
    def tearDown(self):self.temp.cleanup()
    def frame(self,file,time):
        return cut.run([self.ff,'-v','error','-ss',time,'-i',file,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']).stdout
    def insert_video(self):
        return self.model.insert_asset(self.model.asset(self.video),0)

    def test_split_speed_trim_undo_and_save(self):
        ident=self.insert_video()
        self.model.update(ident,{'speed':2})
        self.assertEqual(self.model.total,1)
        right=self.model.split(ident,.4)
        self.assertAlmostEqual(self.model.locate(right)[1]['trim'],.8)
        self.assertEqual(self.model.total,1)
        self.model.trim(right,'left',.1)
        self.assertAlmostEqual(self.model.locate(right)[1]['trim'],1)
        self.assertAlmostEqual(self.model.total,.9)
        self.model.undo()
        self.assertAlmostEqual(self.model.total,1)
        self.model.redo()
        self.assertAlmostEqual(self.model.total,.9)
        self.model.save()
        reopened=EditorModel()
        reopened.load(self.model.path)
        self.assertAlmostEqual(reopened.total,.9)
        self.model.move(right,0)
        self.assertEqual(self.model.data['scenes'][0]['id'],right)
        self.model.remove(right)
        self.model.undo()
        self.assertEqual(self.model.data['scenes'][0]['id'],right)

    def test_split_preserves_overlay_motion(self):
        ident=self.insert_video()
        html=self.folder/'layer.html'
        html.write_text('''<style>body{margin:0}</style><script>window.renderFrame=t=>{
          document.body.style.background='rgb('+Math.round(40+t*80)+',50,100)'}</script>''')
        overlay=self.model.insert_asset(self.model.asset(html),.2,True)
        self.model.update(overlay,{'duration':1.2,'width':40,'height':30,'x':100,'y':50})
        before=self.folder/'before.mp4'
        cut.render(deepcopy(self.model.data),self.model.path,before)
        self.model.split(ident,.8)
        cut.validate(self.model.data,self.model.path)
        right_layer=self.model.data['scenes'][1]['overlays'][0]
        self.assertAlmostEqual(right_layer['trim'],.6)
        self.assertAlmostEqual(right_layer['duration'],.6)
        after=self.folder/'after.mp4'
        cut.render(self.model.data,self.model.path,after)
        for t in [.4,1.0,1.7]:
            a,b=self.frame(before,t),self.frame(after,t)
            self.assertEqual(len(a),len(b))
            self.assertLess(sum(abs(x-y) for x,y in zip(a,b))/len(a),7)

    def test_title_speed_crop_fades_are_in_export(self):
        ident=self.insert_video()
        self.model.update(ident,{'speed':2,'fade_in':.2,'fade_out':.2,'crop':[.1,0,.1,0],
                                 'rotate':180,'mirror':True,'saturation':0,'volume':0})
        title=self.model.add_text(.2,'真实字幕')
        self.model.update(title,{'duration':.4,'font_size':18,'x':80,'y':45,'box':False})
        file=self.folder/'edited.mp4'
        cut.render(self.model.data,self.model.path,file)
        self.assertAlmostEqual(cut.media_info(file)['duration'],1,delta=.05)
        start=self.frame(file,0)
        self.assertLess(sum(start)/len(start),5)
        # Export with/without title must visibly differ at the title's active time.
        with_title=self.frame(file,.4)
        self.model.remove(title)
        bare=self.folder/'bare.mp4'
        cut.render(self.model.data,self.model.path,bare)
        without_title=self.frame(bare,.4)
        self.assertGreater(sum(abs(x-y) for x,y in zip(with_title,without_title)),30000)

    def test_failed_edit_rolls_back_and_audio_moves(self):
        ident=self.insert_video()
        before=deepcopy(self.model.data)
        with self.assertRaises(cut.CutError):self.model.update(ident,{'crop':[.8,0,.8,0]})
        self.assertEqual(before,self.model.data)
        with self.assertRaises(cut.CutError):self.model.update(ident,{'duration':10})
        self.assertEqual(before,self.model.data)
        audio=self.model.insert_asset(self.model.asset(self.video,'audio'),.2)
        self.model.move(audio,.5)
        self.assertAlmostEqual(self.model.locate(audio)[2],.5)
        split=self.model.split(audio,1)
        self.assertAlmostEqual(self.model.locate(split)[2],1)
        self.assertAlmostEqual(self.model.locate(split)[1]['trim'],.5)


if __name__=='__main__':unittest.main()
