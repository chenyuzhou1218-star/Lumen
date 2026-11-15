#!/usr/bin/env python3
"""CodeCut desktop editor. Native Qt UI; shared CLI rendering engine."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import Qt, Signal, QThread, QTimer, QMimeData, QProcess, QUrl, QSize, QRectF, QTranslator, QLibraryInfo
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QIcon, QDrag, QKeySequence, QAction, QFont, QImage, QDesktopServices
from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QPushButton, QToolButton, QListWidget, QListWidgetItem, QAbstractItemView,
    QScrollArea, QFrame, QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QSlider, QStackedWidget, QFileDialog, QMessageBox, QInputDialog,
    QColorDialog, QDialog, QDialogButtonBox, QProgressBar, QTabWidget)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import codecut as cut
from editor_model import EditorModel

CACHE = cut.ROOT/'state'/'cache'
CACHE.mkdir(parents=True,exist_ok=True)
COLORS = {0:'#405f92',1:'#7555a2',2:'#9b7040',3:'#287c70'}
KIND = {'video':'视频','image':'图片','audio':'音频','code':'代码画面','text':'文字'}


def clock(t):
    t = max(0,t)
    return f'{int(t)//60:02d}:{int(t)%60:02d}.{int(t*100)%100:02d}'


def button(label, callback, name='', primary=False):
    from glass_material import GlassButton
    b = GlassButton(label)
    b.setObjectName('primary' if primary else name)
    b.clicked.connect(callback)
    return b


class Task(QThread):
    success = Signal(object)
    failure = Signal(str)
    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn
    def run(self):
        try:
            self.success.emit(self.fn())
        except Exception as e:
            self.failure.emit(str(e))


class MediaBin(QListWidget):
    filesDropped = Signal(list)
    def __init__(self):
        super().__init__()
        self.setObjectName('mediaBin')
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(120,68))
        self.setGridSize(QSize(136,110))
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setWordWrap(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
    def startDrag(self, actions):
        current = self.currentItem()
        if current:
            mime = QMimeData()
            mime.setData('application/x-codecut-asset',current.data(Qt.UserRole).encode())
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.CopyAction)
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
    def dragMoveEvent(self,e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
    def dropEvent(self,e):
        if e.mimeData().hasUrls():
            self.filesDropped.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
            e.acceptProposedAction()


class VideoCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.image=None
    def paintEvent(self,event):
        p=QPainter(self)
        p.fillRect(self.rect(),QColor('#f4f4f5'))
        if self.image is not None:
            size=self.image.size().scaled(self.size(),Qt.KeepAspectRatio)
            rect=QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height())
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(rect,self.image)


class PreviewDecoder(QThread):
    frameReady=Signal(object,float)
    failed=Signal(str)
    def __init__(self,source,start,fps,width,height,parent=None):
        super().__init__(parent)
        self.source,self.start_time,self.fps,self.width,self.height=source,start,fps,width,height
        self.stopping=False
        self.process=None
    def run(self):
        try:
            self.process=subprocess.Popen([cut.tool('ffmpeg'),'-v','error','-ss',str(self.start_time),'-i',str(self.source),
                '-an','-vf',f'fps={self.fps}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=cut.CREATE_NO_WINDOW)
            start=time.monotonic()
            index=0
            size=self.width*self.height*3
            while not self.stopping:
                raw=self.process.stdout.read(size)
                if len(raw)!=size:break
                target=start+index/self.fps
                while not self.stopping and time.monotonic()<target:
                    self.msleep(max(1,min(10,int((target-time.monotonic())*1000))))
                if self.stopping:break
                image=QImage(raw,self.width,self.height,self.width*3,QImage.Format_RGB888).copy()
                self.frameReady.emit(image,self.start_time+index/self.fps)
                index+=1
        except Exception as e:
            if not self.stopping:self.failed.emit(str(e))
        finally:
            if self.process:
                if self.process.poll() is None:self.process.kill()
                self.process.wait()
                self.process.stdout.close()
    def stop(self):
        self.stopping=True
        if self.process and self.process.poll() is None:self.process.kill()
        self.wait(2000)


class Timeline(QWidget):
    selected = Signal(str)
    seek = Signal(float)
    edit = Signal(str,str,float)
    dropped = Signal(str,float,bool)
    filesDropped = Signal(list)
    def __init__(self,model):
        super().__init__()
        self.setObjectName('timeline')
        self.setAccessibleName('剪辑时间线：上方标尺，下方依次是主画面、画中画、文字和音频轨道')
        self.model = model
        self.pps,self.left,self.row = 96.,116,48
        self.position = 0
        self.selection = ''
        self.boxes = []
        self.drag = None
        self.delta = 0
        self.snap = True
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setMinimumHeight(232)
        self.refresh()
    def refresh(self):
        end=max([self.model.total+1,4]+[t+i['duration']+.5 for i,t,_ in self.model.spans()])
        self.setMinimumWidth(int(self.left+end*self.pps+120))
        self.update()
    def paintEvent(self,event):
        from editor_design import paint_timeline
        paint_timeline(self,event)
    def time_at(self,x):
        return self.model.quantize(max(0,(x-self.left)/self.pps))
    def mousePressEvent(self,e):
        if e.button()!=Qt.LeftButton:return
        pos=e.position()
        for ident,rect in reversed(self.boxes):
            if rect.contains(pos):
                self.selection=ident
                self.selected.emit(ident)
                mode='left' if pos.x()-rect.left()<8 else ('right' if rect.right()-pos.x()<8 else 'move')
                self.drag=(ident,mode,pos.x())
                self.delta=0
                self.update()
                return
        self.seek.emit(min(self.model.total,self.time_at(pos.x())))
        self.drag=('', 'seek',pos.x())
    def mouseMoveEvent(self,e):
        if self.drag:
            if self.drag[1]=='seek':
                self.seek.emit(min(self.model.total,self.time_at(e.position().x())))
                return
            self.delta=self.model.quantize((e.position().x()-self.drag[2])/self.pps)
            if self.snap and self.drag[1]=='move':
                _,item,start,_=self.model.locate(self.drag[0])
                candidate=start+self.delta
                targets=[0,self.position]
                for other,t,_ in self.model.spans():
                    if other['id']!=item['id']:targets.extend([t,t+other['duration']])
                nearest=min(targets,key=lambda t:abs(t-candidate))
                if abs(nearest-candidate)*self.pps<8:self.delta=nearest-start
            self.update()
        else:
            cursor=Qt.ArrowCursor
            for _,rect in self.boxes:
                if rect.contains(e.position()):
                    cursor=Qt.SizeHorCursor if min(abs(e.position().x()-rect.left()),abs(e.position().x()-rect.right()))<8 else Qt.OpenHandCursor
            self.setCursor(cursor)
    def mouseReleaseEvent(self,e):
        if self.drag and self.drag[0] and abs(self.delta)>=self.model.frame*.5:
            ident,mode,_=self.drag
            delta=self.delta
            self.drag=None
            self.delta=0
            self.edit.emit(ident,mode,delta)
        self.drag=None
        self.update()
    def dragEnterEvent(self,e):
        if e.mimeData().hasFormat('application/x-codecut-asset') or e.mimeData().hasUrls():e.acceptProposedAction()
    def dragMoveEvent(self,e):e.acceptProposedAction()
    def dropEvent(self,e):
        if e.mimeData().hasFormat('application/x-codecut-asset'):
            ident=bytes(e.mimeData().data('application/x-codecut-asset')).decode()
            row=int((e.position().y()-40)/self.row)
            self.dropped.emit(ident,min(self.model.total,self.time_at(e.position().x())),row==1)
        elif e.mimeData().hasUrls():
            self.filesDropped.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
        e.acceptProposedAction()


class Inspector(QWidget):
    apply = Signal(dict)
    def __init__(self):
        super().__init__()
        self.setMinimumWidth(248)
        self.outer=QVBoxLayout(self)
        self.heading=QLabel('片段调整')
        self.heading.setObjectName('panelTitle')
        self.outer.addWidget(self.heading)
        self.hint=QLabel('在下方时间线上点击一个片段，\n就可以调整时长、声音和画面。')
        self.hint.setWordWrap(True)
        self.hint.setObjectName('muted')
        self.outer.addWidget(self.hint)
        self.tabs=QTabWidget()
        self.outer.setContentsMargins(0,0,0,0)
        self.outer.setSpacing(10)
        self.outer.addWidget(self.tabs)
        self.form=None
        self.applyButton=button('应用调整',self.submit,primary=True)
        self.outer.addWidget(self.applyButton)
        self.outer.addStretch()
        self.fields={}
        self.item=None
        self.applyButton.hide()
    def spin(self,label,key,value,low,high,step=.1,decimals=2):
        s=QDoubleSpinBox()
        s.setRange(low,high)
        s.setDecimals(decimals)
        s.setSingleStep(step)
        s.setValue(value)
        s.setAccessibleName(label)
        s.setObjectName('prop_'+key)
        self.form.addRow(label,s)
        self.fields[key]=s
        return s
    def new_tab(self,name):
        page=QWidget()
        self.form=QFormLayout(page)
        self.form.setContentsMargins(0,16,0,4)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(13)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.tabs.addTab(page,name)

    def show_item(self,item,track,model):
        ident=item.get('id') if item else None
        active=self.tabs.currentIndex() if getattr(self,'last_id',None)==ident else 0
        self.last_id=ident
        self.fields={}
        while self.tabs.count():
            page=self.tabs.widget(0)
            self.tabs.removeTab(0)
            page.deleteLater()
        self.item=item
        self.applyButton.setVisible(item is not None)
        self.tabs.setVisible(item is not None)
        if item is None:
            self.heading.setText('项目概览')
            self.hint.setVisible(True)
            data=model.data
            clips=len(data['scenes'])+len(data['audio'])
            stat=lambda value,name:(f"<td style='padding:0 22px 12px 0'><div style='font-size:19px;font-weight:600;color:#111113'>{value}</div>"
                                    f"<div style='font-size:11px;color:#9a9aa2'>{name}</div></td>")
            self.hint.setTextFormat(Qt.RichText)
            self.hint.setText("<table>"
                              f"<tr>{stat(f'{model.total:.1f}s','总时长')}{stat(clips,'片段')}</tr>"
                              f"<tr>{stat(str(data['width'])+'×'+str(data['height']),'画面')}{stat(data['fps'],'帧 / 秒')}</tr>"
                              "</table><div style='color:#9a9aa2;font-size:12px'>在时间线上选中一个片段，<br>就可以调整画面、文字与声音。</div>")
            return
        text=track=='texts'
        self.heading.setText('文字' if text else KIND.get(item['kind'],'片段'))
        self.hint.setText('')
        self.hint.setVisible(False)
        self.new_tab('基础')
        if text:
            content=QTextEdit(item['text'])
            content.setFixedHeight(88)
            content.setAccessibleName('文字内容')
            self.fields['text']=content
            self.form.addRow(content)
            self.spin('字号','font_size',item.get('font_size',48),8,500,1,0)
            color=QLineEdit(item.get('color','#ffffff'))
            self.fields['color']=color
            self.form.addRow('文字颜色',color)
            self.form.addRow('',button('选择颜色',lambda:self.pick_color(color),'subtle'))
            box=QCheckBox('显示背景底板')
            box.setChecked(item.get('box',True))
            self.fields['box']=box
            self.form.addRow('',box)
            self.new_tab('时间与位置')
        else:
            name=QLineEdit(item.get('name',Path(item['source']).name))
            name.setToolTip(item['source'])
            self.fields['name']=name
            self.form.addRow('名称',name)
            self.spin('素材起点 · 秒','trim',item.get('trim',0),0,86400)
        self.spin('时长 · 秒','duration',item['duration'],model.frame,86400)
        if track!='scene':self.spin('出现时间 · 秒','start',item.get('start',0),0,86400)
        if text:
            self.spin('水平位置','x',item.get('x',model.data['width']/2),0,model.data['width'],1,0)
            self.spin('垂直位置','y',item.get('y',model.data['height']*.8),0,model.data['height'],1,0)
        else:
            if item['kind'] in ['video','code','audio']:
                self.spin('播放速度 · 倍','speed',item.get('speed',1),.25,4,.25)
            if item['kind']!='audio':
                self.new_tab('画面')
                rotation=QComboBox()
                rotation.addItems(['不旋转','90°','180°','270°'])
                rotation.setCurrentIndex(item.get('rotate',0)//90)
                self.fields['rotate']=rotation
                self.form.addRow('旋转',rotation)
                mirror=QCheckBox('水平镜像')
                mirror.setChecked(item.get('mirror',False))
                self.fields['mirror']=mirror
                self.form.addRow('',mirror)
                crop=item.get('crop',[0,0,0,0])
                for i,label in enumerate(['裁掉左侧 · %','裁掉顶部 · %','裁掉右侧 · %','裁掉底部 · %']):
                    self.spin(label,'crop'+str(i),crop[i]*100,0,95,1,0)
                if track=='overlay':
                    for key,label,limit in [('x','水平位置',model.data['width']),('y','垂直位置',model.data['height']),('width','画面宽度',model.data['width']),('height','画面高度',model.data['height'])]:
                        self.spin(label,key,item[key],0 if key in ['x','y'] else 2,limit,2 if key in ['width','height'] else 1,0)
                self.new_tab('色彩')
                self.spin('亮度','brightness',item.get('brightness',0),-1,1,.05)
                self.spin('对比度','contrast',item.get('contrast',1),0,3,.1)
                self.spin('饱和度','saturation',item.get('saturation',1),0,3,.1)
            self.new_tab('声音' if item['kind'] in ['video','audio'] else '淡入淡出')
            if item['kind'] in ['video','audio']:
                self.spin('音量','volume',item.get('volume',1),0,4)
            self.spin('淡入 · 秒','fade_in',item.get('fade_in',0),0,item['duration'])
            self.spin('淡出 · 秒','fade_out',item.get('fade_out',0),0,item['duration'])
        self.tabs.setCurrentIndex(max(0,min(active,self.tabs.count()-1)))

    def pick_color(self,field):
        c=QColorDialog.getColor(QColor(field.text()),self,'文字颜色')
        if c.isValid():field.setText(c.name())
    def submit(self):
        values={}
        for key,w in self.fields.items():
            if isinstance(w,QDoubleSpinBox):values[key]=w.value()
            elif isinstance(w,QCheckBox):values[key]=w.isChecked()
            elif isinstance(w,QTextEdit):values[key]=w.toPlainText()
            elif isinstance(w,QComboBox):values[key]=w.currentIndex()*90
            else:values[key]=w.text()
        if 'crop0' in values:values['crop']=[values.pop('crop'+str(i))/100 for i in range(4)]
        for key in ['width','height']:
            if key in values:values[key]=int(values[key])//2*2
        self.apply.emit(values)


from editor_design import THEME as STYLE


SKIP_DIRS={'.git','node_modules','.venv','venv','__pycache__','state','dist','build'}


def newest_project(folder,depth=2):
    """The most recently changed CodeCut project (.json with version and scenes) in a folder, as (path, mtime)."""
    found,todo=[],[(Path(folder),0)]
    while todo:
        here,level=todo.pop()
        try:entries=list(os.scandir(here))
        except OSError:continue
        for e in entries:
            if e.is_dir(follow_symlinks=False):
                if level<depth and e.name not in SKIP_DIRS and not e.name.startswith('.'):todo.append((Path(e.path),level+1))
            elif e.name.lower().endswith('.json'):
                try:st=e.stat()
                except OSError:continue
                if st.st_size<2_000_000:found.append((st.st_mtime,Path(e.path)))
    for mtime,path in sorted(found,reverse=True)[:12]:
        try:head=path.read_text(encoding='utf-8-sig',errors='replace')[:4000]
        except OSError:continue
        if '"scenes"' in head and '"version"' in head:return path.resolve(),mtime
    return None


class EditorWindow(QMainWindow):
    def __init__(self,project=None):
        super().__init__()
        self.model=EditorModel()
        self.selection=''
        self.position=0.
        self.tasks=[]
        self.proc=None
        self.job=None
        self.preview_revision=-1
        self.auto_play=False
        self._start_loaded=False
        self.decoder=None
        self.preview_file=None
        self.preview_size=(640,360)
        self.still_generation=0
        self.saved_revision=0
        self.visuals={}
        self.thumbnail_busy=False
        self.setMinimumSize(420,560)
        self.resize(1540,940)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)
        self.player=QMediaPlayer(self)
        self.audio=QAudioOutput(self)
        self.audio.setVolume(.7)
        self.player.setAudioOutput(self.audio)
        self.build()
        self.menus()
        self.player.mediaStatusChanged.connect(self.media_loaded)
        self.player.errorOccurred.connect(lambda _,message:self.statusBar().showMessage('播放器：'+message))
        self.autosave=QTimer(self)
        self.autosave.setInterval(1500)
        self.autosave.timeout.connect(self.autosave_project)
        self.autosave.start()
        self.still_timer=QTimer(self)
        self.still_timer.setSingleShot(True)
        self.still_timer.setInterval(100)
        self.still_timer.timeout.connect(self.request_still)
        if project:
            self.open_path(Path(project))
        else:
            self.refresh()
            QTimer.singleShot(300,self.offer_recovery)

    def follow(self,folder,path=None):
        """Follow a folder an AI edits (Code Doctor's @CodeCut): the newest CodeCut project there (or this one) is
        opened, and opened again whenever its file changes - unless it has unsaved edits of yours, never thrown away."""
        self.follow_folder=Path(folder).resolve()
        self.follow_file=Path(path).resolve() if path else None
        self.follow_seen=None
        if path and Path(path).exists():self.follow_seen=(self.follow_file,Path(path).stat().st_mtime)  # already open
        if getattr(self,'follow_timer',None) is None:
            self.follow_timer=QTimer(self)
            self.follow_timer.setInterval(800)
            self.follow_timer.timeout.connect(self.follow_tick)
            self.follow_timer.start()
        self.setWindowTitle('CodeCut · AI 剪辑中')
        self.statusBar().showMessage('正在跟随 AI 剪辑：'+str(self.follow_folder))
        self.follow_tick()

    def follow_tick(self):
        if self.follow_file is not None:
            try:newest=(self.follow_file,self.follow_file.stat().st_mtime)
            except OSError:return
        else:newest=newest_project(self.follow_folder)
        # background reads (thumbnails, a still frame) do not hold this back: their results are dropped when the
        # project changed under them, and one still frame could keep the AI's edits off the screen for good
        if newest is None or self.follow_seen==newest:return
        path,_=newest
        if self.model.dirty and self.model.path==path:
            self.statusBar().showMessage('AI 改了这个项目；你有没保存的修改，保存或撤销后再载入 AI 的版本。')
            return
        try:EditorModel().load(path)  # a file being written, or not valid yet: try again on the next tick
        except Exception:return
        self.follow_seen=newest
        self.open_path(path)
        self.statusBar().showMessage(f'AI 更新了剪辑 · {path.name} · {time.strftime("%H:%M:%S")}')

    def open_ai(self):
        """AI 剪辑: the small window that hands this project to Code Doctor's agents (ai_panel.py)."""
        if getattr(self,'ai_panel',None) is None:
            from ai_panel import AIPanel
            self.ai_panel=AIPanel(self)
            g=self.geometry()
            self.ai_panel.move(g.right()-self.ai_panel.width()-24,g.top()+90)
        self.ai_panel.show()
        self.ai_panel.raise_()
        self.ai_panel.activateWindow()
        self.ai_panel.ask.setFocus()

    def build(self):
        from editor_design import build
        build(self,MediaBin,Timeline,Inspector,VideoCanvas,button)

    def toggle_drawer(self,name):
        """Narrow layouts: bring a side panel in, or send it away again."""
        from editor_design import relayout
        self.drawer='' if self.drawer==name else name
        relayout(self)

    def resizeEvent(self,e):
        super().resizeEvent(e)
        if hasattr(self,'center'):
            from editor_design import relayout
            relayout(self)

    def fit_timeline(self):
        extent=max(4,self.model.total+1)
        width=self.timelineScroll.viewport().width()-self.timeline.left-24
        self.zoomSlider.setValue(max(16,min(260,int(width/extent))))

    def menus(self):
        file=self.menuBar().addMenu('文件')
        edit=self.menuBar().addMenu('编辑')
        for menu,label,shortcut,callback in [
            (file,'新建项目','Ctrl+N',self.new_project),(file,'打开项目','Ctrl+O',self.open_project),
            (file,'保存项目','Ctrl+S',self.save_project),(file,'另存为','Ctrl+Shift+S',lambda:self.save_project(True)),
            (file,'导入素材','Ctrl+I',self.import_dialog),(file,'项目画幅与帧率','',self.project_settings),
            (file,'导出 MP4','Ctrl+E',self.export_dialog),
            (edit,'撤销','Ctrl+Z',lambda:self.history(False)),(edit,'重做','Ctrl+Shift+Z',lambda:self.history(True)),
            (edit,'分割','Ctrl+B',self.split_clip),(edit,'复制片段','Ctrl+D',self.duplicate_clip)]:
            action=QAction(label,self)
            if shortcut:action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
        # Delete and Space act on the timeline, not inside text inputs.
        helpmenu=self.menuBar().addMenu('帮助')
        a=QAction('第一次怎么剪？',self)
        a.triggered.connect(self.help_dialog)
        helpmenu.addAction(a)
        a=QAction('打开使用说明',self)
        a.triggered.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(cut.ROOT/'README.md'))))
        helpmenu.addAction(a)
        # one line of chrome: the menus live behind the button beside the name; their shortcuts stay on the window
        self.mainMenu=QMenu(self)
        for menu in (file,edit,helpmenu):
            self.mainMenu.addMenu(menu)
            self.addActions(menu.actions())
        self.menuBar().hide()

    def show_menu(self):
        self.mainMenu.exec(self.menuButton.mapToGlobal(self.menuButton.rect().bottomLeft()))

    def update_stage(self):
        """No clips: the page that says where to start. Clips but no picture yet: say that, not "start here"."""
        if self.preview.currentIndex()==1:return
        clips=bool(self.model.data['scenes'] or self.model.data['audio'])
        self.preview.setCurrentIndex(2 if clips else 0)
        self.pendingLabel.setText('正在生成预览…' if self.job and self.job.get('preview') else '点“更新预览”查看合成效果')

    def error(self,message):
        QMessageBox.warning(self,'这一步没有完成',str(message)[-2200:])

    def guarded(self,fn):
        try:return fn()
        except Exception as e:self.error(e)

    def run_task(self,fn,success):
        task=Task(fn,self)
        self.tasks.append(task)
        task.success.connect(success)
        task.failure.connect(self.error)
        task.finished.connect(lambda:self.tasks.remove(task) if task in self.tasks else None)
        task.start()

    def refresh(self,edited=False):
        self.projectLabel.setText(('未命名项目' if self.model.path.stem=='untitled' else self.model.path.stem)+('  ·  未保存' if self.model.dirty else ''))
        self.setWindowTitle('CodeCut — '+self.model.path.stem+(' *' if self.model.dirty else ''))
        self.canvasInfo.setText(f'{self.model.data["width"]} × {self.model.data["height"]} · {self.model.data["fps"]} fps')
        if hasattr(self,'overviewLine'):
            from editor_design import update_overview
            update_overview(self)
        self.timeline.model=self.model
        self.timeline.selection=self.selection
        self.timeline.refresh()
        self.seekSlider.setRange(0,int(self.model.total*1000))
        self.position=min(self.position,self.model.total)
        self.update_stage()
        self.update_time()
        self.undoButton.setEnabled(bool(self.model.undo_states))
        self.redoButton.setEnabled(bool(self.model.redo_states))
        self.refresh_bin()
        try:
            _,item,_,track=self.model.locate(self.selection)
        except cut.CutError:item,track=None,''
        self.inspector.show_item(item,track,self.model)
        for b in self.editButtons:b.setEnabled(item is not None)
        self.playButton.setEnabled(bool(self.model.data['scenes']))
        self.previewButton.setEnabled(bool(self.model.data['scenes']) and self.proc is None)
        self.exportButton.setEnabled(bool(self.model.data['scenes']) and self.proc is None)
        if edited:
            self.pause_media()
            self.previewStatus.setText('● 剪辑已更新，生成预览后查看效果')

    def refresh_bin(self):
        from editor_design import populate_library
        populate_library(self)

    def select(self,ident):
        self.selection=ident
        self.timeline.selection=ident
        self.timeline.update()
        for b in self.editButtons:b.setEnabled(True)
        self.guarded(lambda:self.inspector.show_item(self.model.locate(ident)[1],self.model.locate(ident)[3],self.model))

    def update_time(self):
        self.timeline.position=self.position
        self.timeline.update()
        self.timeLabel.setText(clock(self.position)+' / '+clock(self.model.total))
        if not self.seekSlider.isSliderDown():self.seekSlider.setValue(int(self.position*1000))

    def seek(self,seconds):
        playing=self.decoder is not None
        if playing:self.pause_media()
        self.position=max(0,min(self.model.total,seconds))
        if self.preview_revision==self.model.revision:
            self.player.setPosition(int(self.position*1000))
            if playing:self.play_media()
            else:self.still_timer.start()
        self.update_time()

    def media_loaded(self,status):
        if self._start_loaded and status in [QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia]:
            self._start_loaded=False
            self.player.setActiveVideoTrack(-1)
            self.player.setPosition(int(self.position*1000))
            if self.decoder:self.player.play()

    def request_still(self):
        if not self.preview_file or self.preview_revision!=self.model.revision or self.decoder:return
        self.still_generation+=1
        generation=self.still_generation
        source=self.preview_file
        t=max(0,min(self.position,self.model.total-self.model.frame))
        def decode():
            return cut.run([cut.tool('ffmpeg'),'-v','error','-ss',t,'-i',source,'-frames:v','1','-f','image2pipe','-vcodec','png','pipe:1'],timeout=20).stdout
        def display(raw):
            if generation==self.still_generation and not self.decoder and source==self.preview_file:
                image=QImage.fromData(raw)
                if not image.isNull():self.video.image=image;self.video.update()
        self.run_task(decode,display)

    def pause_media(self):
        if self.decoder:
            decoder=self.decoder
            self.decoder=None
            decoder.stop()
        self.player.pause()
        self.playButton.setText('播放')
        from editor_design import icon
        self.playButton.setIcon(icon('play','#111113',15))

    def play_media(self):
        if not self.preview_file:return
        self.still_generation+=1
        if self.position>=self.model.total-self.model.frame:self.position=0
        w,h=self.preview_size
        decoder=PreviewDecoder(self.preview_file,self.position,self.model.data['fps'],w,h,self)
        self.decoder=decoder
        def frame(image,t):
            if self.decoder is decoder:
                if not getattr(decoder,'audio_started',False):
                    decoder.audio_started=True
                    self.player.setPosition(int(t*1000))
                    self.player.play()
                self.video.image=image
                self.video.update()
                self.position=t
                self.update_time()
        def finished():
            if self.decoder is decoder:
                self.decoder=None
                self.player.pause()
                self.playButton.setText('播放')
                from editor_design import icon
                self.playButton.setIcon(icon('play','#111113',15))
                self.position=self.model.total
                self.update_time()
            decoder.deleteLater()
        decoder.frameReady.connect(frame)
        decoder.finished.connect(finished)
        decoder.failed.connect(lambda message:self.statusBar().showMessage('预览播放：'+message))
        self.player.setPosition(int(self.position*1000))
        self.playButton.setText('暂停')
        from editor_design import icon
        self.playButton.setIcon(icon('pause','#111113',15))
        decoder.start()

    def zoom(self,value):
        self.timeline.pps=value
        self.timeline.refresh()

    def import_dialog(self):
        files,_=QFileDialog.getOpenFileNames(self,'导入视频、音频、图片或 HTML','','媒体和代码 (*.mp4 *.mov *.mkv *.webm *.avi *.mp3 *.wav *.m4a *.aac *.flac *.ogg *.png *.jpg *.jpeg *.webp *.bmp *.html *.htm);;所有文件 (*)')
        if files:self.import_files(files)

    def import_files(self,files):
        if not files:return
        self.statusBar().showMessage('正在读取素材与缩略图…')
        generation=self.model
        def prepare():
            assets=[]
            for source in files:
                if Path(source).is_dir():
                    if not (Path(source)/'index.html').exists():
                        raise cut.CutError('这个文件夹没有 index.html。请通过「代码 / Git」选择画面入口。')
                    item=generation.asset(Path(source)/'index.html',root=source)
                else:item=generation.asset(source)
                digest=hashlib.sha256(item['source'].encode()).hexdigest()[:20]
                if item['kind'] in ['video','image']:
                    thumb=CACHE/(digest+'.png')
                    if not thumb.exists():cut.run([cut.tool('ffmpeg'),'-v','error','-y','-i',item['source'],'-frames:v','1','-vf','scale=264:148:force_original_aspect_ratio=decrease','-threads','1',thumb],timeout=30)
                    item['_thumbnail']=str(thumb)
                if item['kind']=='audio':
                    wave=CACHE/(digest+'-wave.png')
                    if not wave.exists():cut.run([cut.tool('ffmpeg'),'-v','error','-y','-i',item['source'],'-filter_complex','showwavespic=s=800x80:colors=0xA8F5DF','-frames:v','1',wave],timeout=60)
                    item['_waveform']=str(wave)
                    item['_thumbnail']=str(wave)
                assets.append(item)
            return assets
        def added(assets):
            if self.model is not generation:return
            self.guarded(lambda:self.model.add_assets(assets))
            self.refresh()
            if assets:
                for i in range(self.bin.count()):
                    if self.bin.item(i).data(Qt.UserRole)==assets[0]['id']:self.bin.setCurrentRow(i)
            self.statusBar().showMessage(f'已导入 {len(assets)} 个素材。双击即可加入剪辑。',10000)
        self.run_task(prepare,added)

    def add_selected_asset(self,overlay=False):
        item=self.bin.currentItem()
        if not item:
            self.statusBar().showMessage('先在左侧选中一个素材。',5000)
            return
        self.insert_asset(item.data(Qt.UserRole),self.position if overlay else self.model.total,overlay)

    def insert_asset(self,ident,time,overlay=False):
        asset=next((a for a in self.library if a['id']==ident),None)
        if not asset:return
        def change():
            at=min(time,max(0,self.model.total-self.model.frame)) if asset['kind']=='audio' and self.model.total else time
            self.selection=self.model.insert_asset(asset,at,overlay)
            self.refresh(True)
        self.guarded(change)

    def code_dialog(self):
        d=QDialog(self)
        d.setWindowTitle('导入代码画面 / Git 仓库')
        d.setMinimumWidth(560)
        lay=QVBoxLayout(d)
        tip=QLabel('代码会运行成画面，进入视频。选择 HTML 入口，\n或粘贴已经运行的预览网址；Git 仓库可先下载再选入口。')
        tip.setWordWrap(True)
        lay.addWidget(tip)
        form=QFormLayout()
        source=QLineEdit()
        source.setPlaceholderText('HTML 路径或 http://localhost:5173')
        form.addRow('画面入口',source)
        lay.addLayout(form)
        row=QHBoxLayout()
        def choose():
            filename,_=QFileDialog.getOpenFileName(d,'选择 HTML 画面入口','','HTML (*.html *.htm)')
            if filename:source.setText(filename)
        row.addWidget(button('选择 HTML',choose))
        def folder():
            directory=QFileDialog.getExistingDirectory(d,'选择本地仓库')
            if directory:
                filename,_=QFileDialog.getOpenFileName(d,'选择仓库里的 HTML 入口',directory,'HTML (*.html *.htm)')
                if filename:
                    source.setText(filename)
                    source.setProperty('root',directory)
        row.addWidget(button('选择本地仓库',folder))
        def clone():
            url,ok=QInputDialog.getText(d,'下载 Git 仓库','Git 仓库地址（HTTPS、SSH 或本地路径）：')
            if not ok or not url:return
            dest=QFileDialog.getSaveFileName(d,'选择新的仓库文件夹名称',str(cut.ROOT/'repos'/'my-repo'),'文件夹名称 (*)')[0]
            if not dest:return
            def finished(result):
                directory=Path(result['directory'])
                entry,_=QFileDialog.getOpenFileName(d,'选择下载后的 HTML 画面入口',str(directory),'HTML (*.html *.htm)')
                if entry:source.setText(entry);source.setProperty('root',str(directory))
            self.run_task(lambda:cut.main(['repo',url,dest]),finished)
            self.statusBar().showMessage('正在下载仓库；不会自动执行仓库脚本。')
        row.addWidget(button('下载 Git 仓库',clone))
        lay.addLayout(row)
        small=QLabel('React / Vite 等项目需要先启动，或选择构建后的 HTML。\n网页自身的声音请作为音频素材单独导入。')
        small.setObjectName('muted')
        lay.addWidget(small)
        controls=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        controls.button(QDialogButtonBox.Ok).setText('导入素材库')
        controls.button(QDialogButtonBox.Cancel).setText('取消')
        controls.accepted.connect(d.accept)
        controls.rejected.connect(d.reject)
        lay.addWidget(controls)
        if d.exec()==QDialog.Accepted and source.text().strip():
            def add():
                asset=self.model.asset(source.text().strip(),'code',source.property('root'))
                self.model.add_assets([asset])
                self.refresh()
            self.guarded(add)

    def apply_properties(self,fields):
        def change():
            self.model.update(self.selection,fields)
            self.refresh(True)
        self.guarded(change)

    def timeline_edit(self,ident,mode,delta):
        def change():
            if mode=='move':self.model.move(ident,self.model.locate(ident)[2]+delta)
            else:self.model.trim(ident,mode,delta)
            self.refresh(True)
        self.guarded(change)

    def split_clip(self):
        def change():
            self.selection=self.model.split(self.selection,self.position)
            self.refresh(True)
        self.guarded(change)

    def trim_to_head(self,right):
        def change():
            _,item,start,_=self.model.locate(self.selection)
            offset=self.position-start
            if offset<=0 or offset>=item['duration']:raise cut.CutError('先把播放头移到片段中间。')
            self.model.trim(self.selection,'left' if right else 'right',offset if right else offset-item['duration'])
            self.refresh(True)
        self.guarded(change)

    def remove_clip(self):
        def change():
            self.model.remove(self.selection)
            self.selection=''
            self.refresh(True)
        self.guarded(change)

    def duplicate_clip(self):
        def change():
            self.selection=self.model.duplicate(self.selection)
            self.refresh(True)
        self.guarded(change)

    def add_title(self):
        self.selection=self.model.add_text(min(self.position,max(0,self.model.total-self.model.frame)))
        self.refresh(True)

    def history(self,redo):
        self.model.redo() if redo else self.model.undo()
        self.refresh(True)

    def confirm_unsaved(self):
        if not self.model.dirty:return True
        result=QMessageBox.question(self,'保存项目？','当前修改还没有保存。是否先保存？',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        if result==QMessageBox.Cancel:return False
        if result==QMessageBox.Save:return self.save_project()
        return True

    def new_project(self):
        if not self.confirm_unsaved():return
        self.clear_recovery()
        self.cancel_job()
        self.pause_media()
        self.player.stop()
        self.model=EditorModel()
        self.preview_revision=-1
        self.selection=''
        self.position=0
        self.preview.setCurrentIndex(0)
        self.refresh()

    def open_project(self):
        if not self.confirm_unsaved():return
        filename,_=QFileDialog.getOpenFileName(self,'打开 CodeCut 项目','','CodeCut 项目 (*.json)')
        if filename:self.open_path(Path(filename))

    def open_demo(self):
        if self.confirm_unsaved():self.open_path(cut.ROOT/'demo'/'project.json')

    def open_path(self,path):
        def load():
            new=EditorModel()
            new.load(path)
            self.clear_recovery()
            self.cancel_job()
            self.pause_media()
            self.player.stop()
            self.model=new
            self.selection=''
            self.position=0
            self.preview_revision=-1
            self.refresh()
            candidate=path.with_name('result.mp4')
            # Never reuse a file merely because its name looks like a preview.
            QTimer.singleShot(80,self.fit_timeline)
            QTimer.singleShot(200,self.start_preview)
            self.say_current()
        self.guarded(load)

    def save_project(self,as_new=False):
        filename=self.model.path
        if as_new or not filename.exists():
            name,_=QFileDialog.getSaveFileName(self,'保存剪辑项目',str(filename),'CodeCut 项目 (*.json)')
            if not name:return False
            filename=Path(name)
            if filename.suffix.lower()!='.json':filename=filename.with_suffix('.json')
        try:
            self.clear_recovery()
            self.model.save(filename)
            self.saved_revision=self.model.revision
            if getattr(self,'follow_timer',None) is not None:  # following an AI: your own save is not its change
                saved=self.model.path.resolve()
                self.follow_seen=(saved,saved.stat().st_mtime)
            self.refresh()
            self.statusBar().showMessage('项目已保存；源视频和音频不会被修改。',8000)
            return True
        except Exception as e:self.error(e);return False

    def autosave_project(self):
        """Saved by itself (the user, 2026-11-14: 自动保存): a project that has its file is written to that file 1.5 s after a
        change, like a document app; one that has none yet keeps a recovery copy until it is saved somewhere."""
        if not self.model.dirty and self.saved_revision==self.model.revision:return
        try:
            folder=getattr(self,'follow_folder',None)
            if folder is not None and (not self.model.path or Path(self.model.path).stem=='untitled' or not Path(self.model.path).is_file()):
                # Inside Lumen: what the user builds here goes into the project folder at once, so the AI on the left works
                # on this very edit (the user, 2026-11-14: the AI should operate the tool on the right) and its changes
                # come back here (follow_tick).
                target=Path(folder)/'CodeCut'/'project.json'
                n=2
                while target.exists():
                    target=Path(folder)/'CodeCut'/f'project-{n}.json'
                    n+=1
                target.parent.mkdir(parents=True,exist_ok=True)
                self.model.path=target
                self.follow_file=None
            if self.model.path and Path(self.model.path).stem!='untitled' and (Path(self.model.path).is_file() or folder is not None):
                self.model.save(self.model.path)
                self.saved_revision=self.model.revision
                if getattr(self,'follow_timer',None) is not None:  # following an AI: this save is not its change
                    saved=Path(self.model.path).resolve()
                    self.follow_seen=(saved,saved.stat().st_mtime)
                self.clear_recovery()
                self.say_current()
            elif self.model.dirty:
                cut.save(cut.ROOT/'state'/'recovery.json',{'version':1,'base':str(self.model.path),'project':self.model.data})
        except OSError:pass

    def say_current(self):
        """state/current.json: the project on this window's screen, for Lumen to tell its AI which file it is looking at."""
        try:
            cut.save(cut.ROOT/'state'/'current.json',{'project':str(Path(self.model.path).resolve()),'folder':str(getattr(self,'follow_folder','') or ''),
                                                    'pid':os.getpid(),'at':time.time()})
        except OSError:pass

    def offer_recovery(self):
        """What was not saved last time comes back by itself, without asking (no 恢复上次剪辑 question any more)."""
        path=cut.ROOT/'state'/'recovery.json'
        if not path.exists():return
        try:
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved.get('project'):
                self.model.data=saved['project']
                self.model.path=Path(saved['base'])
                self.model.dirty=True
                self.model.revision+=1
                self.refresh(True)
                self.statusBar().showMessage('已恢复上次没保存的修改',6000)
        except Exception as e:self.statusBar().showMessage('自动保存未能恢复：'+str(e))

    def clear_recovery(self):
        path=cut.ROOT/'state'/'recovery.json'
        try:
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved.get('project')==self.model.data:path.unlink()
        except (OSError,ValueError):pass

    def project_settings(self):
        d=QDialog(self)
        d.setWindowTitle('项目画幅与帧率')
        form=QFormLayout(d)
        preset=QComboBox()
        sizes=[(1280,720),(1920,1080),(720,1280),(1080,1920),(1080,1080),(640,360)]
        preset.addItems(['横屏 720p · 16:9','横屏 1080p · 16:9','竖屏 720p · 9:16','竖屏 1080p · 9:16','正方形 1080p','快速测试 640 × 360'])
        current=(self.model.data['width'],self.model.data['height'])
        if current not in sizes:sizes.append(current);preset.addItem(f'{current[0]} × {current[1]}')
        preset.setCurrentIndex(sizes.index(current))
        form.addRow('画幅',preset)
        fps=QComboBox()
        fps.addItems(['24','25','30','60'])
        fps.setCurrentText(str(self.model.data['fps']))
        form.addRow('帧率',fps)
        controls=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        controls.accepted.connect(d.accept)
        controls.rejected.connect(d.reject)
        form.addRow(controls)
        if d.exec()==QDialog.Accepted:
            w,h=sizes[preset.currentIndex()]
            def change():
                sx,sy=w/current[0],h/current[1]
                for item in self.model.all_items(self.model.data):
                    if item.get('kind')=='text':
                        item['x']*=sx;item['y']*=sy;item['font_size']=max(8,min(500,item.get('font_size',48)*min(sx,sy)))
                    elif 'width' in item:
                        for f,scale in [('x',sx),('y',sy),('width',sx),('height',sy)]:item[f]=int(item[f]*scale)//2*2
                self.model.data.update(width=w,height=h,fps=int(fps.currentText()))
            self.guarded(lambda:self.model.commit(change))
            self.refresh(True)

    def toggle_play(self):
        if self.decoder:self.pause_media();return
        if self.preview_revision!=self.model.revision:
            self.auto_play=True
            self.start_preview()
        else:
            if self.position>=self.model.total-self.model.frame:self.seek(0)
            self.play_media()

    def start_preview(self):
        if not self.model.data['scenes']:
            self.statusBar().showMessage('先把视频、图片或代码画面加入主画面轨道。',6000)
            self.auto_play=False
            return
        if self.proc:
            self.statusBar().showMessage('当前正在处理，请等待完成或点击取消。',6000)
            return
        data=deepcopy(self.model.data)
        scale=min(1,640/data['width'],640/data['height'])
        if scale<1:
            data['width']=max(64,int(data['width']*scale)//2*2)
            data['height']=max(64,int(data['height']*scale)//2*2)
            for item in EditorModel.all_items(data):
                if 'width' in item:
                    for key in ['x','y','width','height']:item[key]=max(0,int(item[key]*scale)//2*2)
                if item.get('kind')=='text':
                    item['x']*=scale;item['y']*=scale;item['font_size']=max(8,item.get('font_size',48)*scale)
        # a new name every time: a reopened project starts its revisions again, and the player may still hold the
        # file of the same number (Windows then refuses to replace it: "access denied" after an AI's edit)
        self.preview_seq=getattr(self,'preview_seq',0)+1
        self.start_job(data,CACHE/f'preview-{os.getpid()}-{self.preview_seq}.mp4',True)

    def export_dialog(self):
        if self.proc:
            self.statusBar().showMessage('先等待当前任务完成，或点击取消。',6000)
            return
        if not self.model.data['scenes']:
            self.error('主画面还是空的。先双击素材，将它加入时间线。')
            return
        name,_=QFileDialog.getSaveFileName(self,'导出 MP4',str(self.model.path.with_suffix('.mp4')),'MP4 视频 (*.mp4)')
        if not name:return
        output=Path(name)
        if output.suffix.lower()!='.mp4':output=output.with_suffix('.mp4')
        # QFileDialog already asks before replacing an existing selected file.
        self.start_job(deepcopy(self.model.data),output,False)

    def start_job(self,data,output,preview):
        if self.proc:return
        try:cut.validate(data,self.model.path)
        except Exception as e:self.error(e);return
        self.pause_media()
        folder=Path(tempfile.mkdtemp(prefix='job-',dir=CACHE))
        snapshot=folder/'project.json'
        cut.save(snapshot,data)
        self.job=dict(folder=folder,output=Path(output),preview=preview,revision=self.model.revision,
                      stdout='',stderr='',result=None,cancelled=False,model=self.model,size=(data['width'],data['height']))
        self.progress.setRange(0,0)
        self.progress.show()
        self.jobLabel.show()
        self.cancelButton.show()
        self.previewButton.setEnabled(False)
        self.jobLabel.setText('正在生成预览…' if preview else '正在导出视频…')
        self.update_stage()
        proc=QProcess(self)
        self.proc=proc
        proc.setProgram(sys.executable)
        proc.setArguments([str(cut.ROOT/'codecut.py'),'render',str(snapshot),'-o',str(output),'--force'])
        proc.readyReadStandardOutput.connect(self.read_job_stdout)
        proc.readyReadStandardError.connect(self.read_job_stderr)
        proc.finished.connect(self.job_finished)
        proc.errorOccurred.connect(self.job_error)
        proc.start()

    def job_error(self,error):
        if self.proc and self.job and error==QProcess.FailedToStart:
            message=self.proc.errorString()
            self.job['stdout']=json.dumps({'ok':False,'error':'无法启动导出进程：'+message})
            self.job_finished(-1,QProcess.CrashExit)

    def read_job_stdout(self):
        if self.proc and self.job:self.job['stdout']+=bytes(self.proc.readAllStandardOutput()).decode('utf-8',errors='replace')

    def read_job_stderr(self):
        if not self.proc or not self.job:return
        self.job['stderr']+=bytes(self.proc.readAllStandardError()).decode('utf-8',errors='replace')
        while '\n' in self.job['stderr']:
            line,self.job['stderr']=self.job['stderr'].split('\n',1)
            try:
                event=json.loads(line)
                if event.get('event')=='scene':self.jobLabel.setText(f'正在处理第 {event["index"]} / {event["total"]} 段画面…')
                if event.get('event')=='frames':
                    self.jobLabel.setText(f'正在生成代码画面：{event["done"]} / {event["total"]} 帧')
            except ValueError:pass

    def job_finished(self,exitcode,status):
        if not self.job:return
        self.read_job_stdout()
        job=self.job
        proc=self.proc
        self.job=None
        self.proc=None
        self.progress.hide()
        self.jobLabel.hide()
        self.cancelButton.hide()
        self.previewButton.setEnabled(True)
        self.update_stage()
        proc.deleteLater()
        try:
            lines=[json.loads(line) for line in job['stdout'].splitlines() if line.strip().startswith('{')]
            result=lines[-1] if lines else {'ok':False,'error':'导出进程没有返回结果。'}
        except ValueError:result={'ok':False,'error':'无法读取导出结果。'}
        if job['cancelled']:
            self.jobLabel.setText('已取消。可以继续编辑。')
            self.auto_play=False
        elif exitcode==0 and result.get('ok'):
            if job['preview']:
                if job['model'] is self.model and job['revision']==self.model.revision:
                    self.preview_revision=self.model.revision
                    self.preview.setCurrentIndex(1)
                    self.preview_file=job['output']
                    self.preview_size=job['size']
                    self._start_loaded=True
                    self.player.setSource(QUrl.fromLocalFile(str(job['output'])))
                    if self.auto_play:self.play_media()
                    else:self.request_still()
                    self.previewStatus.setText('● 预览已同步')
                    self.jobLabel.setText('预览就绪')
                else:
                    self.previewStatus.setText('● 剪辑已修改，请更新预览')
                self.auto_play=False
            else:
                self.jobLabel.setText('已导出：'+str(job['output']))
                self.statusBar().showMessage('导出成功 · '+str(job['output']))
                QMessageBox.information(self,'导出完成','视频已保存，并通过完整解码检查：\n'+str(job['output']))
        else:
            self.auto_play=False
            self.jobLabel.setText('未完成，可以修改后重试。')
            self.error(result.get('error','导出失败'))
        # Snapshot JSON contains only project data; remove this one known job file.
        snapshot=job['folder']/'project.json'
        snapshot.unlink(missing_ok=True)
        try:job['folder'].rmdir()
        except OSError:pass

    def cancel_job(self):
        if self.proc and self.job:
            self.job['cancelled']=True
            pid=self.proc.processId()
            if os.name=='nt' and pid:
                subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,creationflags=cut.CREATE_NO_WINDOW,timeout=10)
            else:self.proc.kill()
            self.proc.waitForFinished(3000)

    def help_dialog(self):
        QMessageBox.information(self,'第一次怎么剪？','1. 点素材区右上方「导入」，选视频、音乐或图片。\n2. 双击素材，把它放到下方时间线。\n3. 点击时间线上的标尺，把播放头放到要剪的位置。\n4. 选中片段后点「分割」，两段就可以分别处理。\n5. 拖片段左右边缘可裁剪，拖中间可调整顺序。\n6. 点「＋ 文字」添加标题；音乐放在声音轨。\n7. 点「更新预览」查看合成效果，再点右上角「导出视频」。\n\nCtrl+S 保存项目，Ctrl+Z 撤销。源素材不会被修改。')

    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
    def dropEvent(self,e):
        self.import_files([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
        e.acceptProposedAction()
    def keyPressEvent(self,e):
        if isinstance(QApplication.focusWidget(),(QLineEdit,QTextEdit,QDoubleSpinBox,QSpinBox)):
            super().keyPressEvent(e);return
        if e.key()==Qt.Key_Space:self.toggle_play();e.accept()
        elif e.key()==Qt.Key_Delete:self.remove_clip();e.accept()
        elif e.key()==Qt.Key_Left:self.seek(self.position-self.model.frame);e.accept()
        elif e.key()==Qt.Key_Right:self.seek(self.position+self.model.frame);e.accept()
        else:super().keyPressEvent(e)
    def closeEvent(self,e):
        if self.tasks:
            self.statusBar().showMessage('正在读取素材，请稍后关闭。')
            e.ignore();return
        if not self.confirm_unsaved():e.ignore();return
        self.clear_recovery()
        self.cancel_job()
        self.pause_media()
        self.player.stop()
        e.accept()


def main():
    parser=argparse.ArgumentParser(description='CodeCut Windows desktop editor')
    parser.add_argument('--project',type=Path)
    parser.add_argument('--follow',type=Path,help='Show the CodeCut project an AI is editing in this folder, live')
    parser.add_argument('--compact',action='store_true',help='A smaller window (beside another program)')
    args=parser.parse_args()
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs,True)
    app=QApplication(sys.argv)
    translator=QTranslator(app)
    if translator.load('qtbase_zh_CN',QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)
    app.setApplicationName('CodeCut')
    app.setOrganizationName('CodeCut')
    app.setFont(QFont('Microsoft YaHei UI',9))
    window=EditorWindow(args.project)
    if args.compact:window.resize(1180,760)
    if args.follow:window.follow(args.follow)
    import embed
    embed.show(window)
    from editor_design import apply_window_chrome
    apply_window_chrome(window)
    sys.exit(app.exec())


if __name__=='__main__':main()
