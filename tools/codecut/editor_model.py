"""Editing operations shared by the desktop UI and integration tests."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import uuid

import codecut as cut


def new_id():
    return uuid.uuid4().hex[:10]


class EditorModel:
    def __init__(self):
        self.path = cut.ROOT / 'projects' / 'untitled.json'
        self.data = dict(version=1,width=1280,height=720,fps=30,scenes=[],audio=[],texts=[],assets=[])
        self.undo_states = []
        self.redo_states = []
        self.revision = 0
        self.dirty = False

    @property
    def total(self):
        return sum(cut.duration(s,self.data['fps']) for s in self.data['scenes'])

    @property
    def frame(self):
        return 1/self.data['fps']

    def quantize(self, value):
        return round(value*self.data['fps'])/self.data['fps']

    def load(self, path):
        path = Path(path).resolve()
        data = cut.load(path)
        data.setdefault('texts',[])
        data.setdefault('assets',[])
        for item in self.all_items(data):
            for field in ['source','root']:
                src = item.get(field)
                if src and not src.startswith(('http://','https://')):
                    item[field] = str((path.parent/src).resolve())
        cut.validate(data,path,require_scenes=False)
        self.path,self.data = path,data
        self.undo_states.clear()
        self.redo_states.clear()
        self.revision += 1
        self.dirty = False

    @staticmethod
    def all_items(data):
        for item in data['scenes']+data['audio']+data.get('texts',[])+data.get('assets',[]):
            yield item
            yield from item.get('overlays',[])

    def commit(self, change):
        before = deepcopy(self.data)
        try:
            result = change()
            cut.validate(self.data,self.path,require_scenes=False)
        except Exception:
            self.data = before
            raise
        if self.data != before:
            self.undo_states.append(before)
            self.undo_states = self.undo_states[-80:]
            self.redo_states.clear()
            self.revision += 1
            self.dirty = True
        return result

    def undo(self):
        if self.undo_states:
            self.redo_states.append(deepcopy(self.data))
            self.data = self.undo_states.pop()
            self.revision += 1
            self.dirty = True

    def redo(self):
        if self.redo_states:
            self.undo_states.append(deepcopy(self.data))
            self.data = self.redo_states.pop()
            self.revision += 1
            self.dirty = True

    def save(self, path=None):
        target = Path(path or self.path).resolve()
        cut.save(target,self.data)
        self.path = target
        self.dirty = False

    def locate(self, ident):
        offset = 0
        for scene in self.data['scenes']:
            if scene['id'] == ident:
                return self.data['scenes'],scene,offset,'scene'
            for layer in scene.get('overlays',[]):
                if layer['id'] == ident:
                    return scene['overlays'],layer,offset+layer.get('start',0),'overlay'
            offset += cut.duration(scene,self.data['fps'])
        for track in ['audio','texts']:
            for item in self.data[track]:
                if item['id'] == ident:
                    return self.data[track],item,item.get('start',0),track
        raise cut.CutError('请先在时间线上选择一段素材。')

    def asset(self, source, kind=None, root=None):
        source = str(source)
        url = source.startswith(('http://','https://'))
        if not url:
            source = str(Path(source).resolve())
        if kind is None:
            ext = Path(source).suffix.lower()
            if ext in ['.html','.htm'] or url:
                kind = 'code'
            elif ext in ['.png','.jpg','.jpeg','.webp','.bmp','.ppm']:
                kind = 'image'
            else:
                info = cut.media_info(source)
                kind = 'video' if info['video'] else 'audio'
        item = dict(id=new_id(),kind=kind,source=source,name=Path(source).name if not url else source,duration=5.)
        if kind in ['video','audio']:
            info = cut.media_info(source)
            if not info['duration']:
                raise cut.CutError('无法读取素材时长。')
            item['duration'] = math.floor(info['duration']*self.data['fps'])/self.data['fps']
            item['_source_duration'] = info['duration']
        if root:
            item['root'] = str(Path(root).resolve())
        return item

    def add_assets(self, assets):
        def change():
            known = {a['source'] for a in self.data['assets']}
            for a in assets:
                if a['source'] not in known:
                    self.data['assets'].append(deepcopy(a))
                    known.add(a['source'])
        self.commit(change)

    def insert_asset(self, asset, time=0, overlay=False):
        item = deepcopy(asset)
        item.update(id=new_id(),trim=0,volume=1,speed=1)
        if item['kind'] == 'audio':
            item['start'] = self.quantize(max(0,time))
            self.commit(lambda:self.data['audio'].append(item))
        elif overlay:
            offset = 0
            parent = None
            for scene in self.data['scenes']:
                if offset <= time < offset+scene['duration']+.00001:
                    parent = scene
                    break
                offset += scene['duration']
            if parent is None:
                raise cut.CutError('请先添加主画面，再把播放头移到需要画中画的位置。')
            item.update(start=self.quantize(max(0,time-offset)),x=20,y=20,
                        width=max(2,int(self.data['width']*.3)//2*2),height=max(2,int(self.data['height']*.3)//2*2))
            item['duration'] = max(self.frame,min(item['duration'],parent['duration']-item['start']))
            self.commit(lambda:parent.setdefault('overlays',[]).append(item))
        else:
            offset,index = 0,len(self.data['scenes'])
            for i,scene in enumerate(self.data['scenes']):
                if time < offset+scene['duration']/2:
                    index = i
                    break
                offset += scene['duration']
            self.commit(lambda:self.data['scenes'].insert(index,item))
        return item['id']

    def add_text(self, time, text='在这里输入文字'):
        item = dict(id=new_id(),kind='text',text=text,start=self.quantize(max(0,time)),
                    duration=max(self.frame,min(3,self.total-time)) if self.total>time else 3,
                    font_size=48,color='#ffffff',x=self.data['width']/2,y=self.data['height']*.8,box=True,name='文字')
        self.commit(lambda:self.data['texts'].append(item))
        return item['id']

    @staticmethod
    def fresh_ids(item):
        item['id'] = new_id()
        for child in item.get('overlays',[]):
            EditorModel.fresh_ids(child)

    def split(self, ident, time):
        group,item,start,track = self.locate(ident)
        offset = self.quantize(time-start)
        if offset < self.frame-.00001 or offset > item['duration']-self.frame+.00001:
            raise cut.CutError('把播放头移到片段中间，再点击分割。')
        right = deepcopy(item)
        self.fresh_ids(right)
        def change():
            right['duration'] = self.quantize(item['duration']-offset)
            right['trim'] = item.get('trim',0)+offset*item.get('speed',1)
            right['fade_in'] = 0
            item['fade_out'] = 0
            item['duration'] = offset
            for clip in [item,right]:
                for f in ['fade_in','fade_out']:
                    clip[f] = min(clip.get(f,0),clip['duration'])
            if track != 'scene':
                right['start'] = item.get('start',0)+offset
            else:
                left_layers,right_layers = [],[]
                for layer in deepcopy(item.get('overlays',[])):
                    a,b = layer.get('start',0),layer.get('start',0)+layer['duration']
                    if a < offset:
                        left = deepcopy(layer)
                        left['duration'] = min(b,offset)-a
                        left['fade_out'] = min(left.get('fade_out',0),left['duration'])
                        left['fade_in'] = min(left.get('fade_in',0),left['duration'])
                        if left['duration'] >= self.frame-.00001:
                            left_layers.append(left)
                    if b > offset:
                        self.fresh_ids(layer)
                        layer['start'] = max(0,a-offset)
                        layer['duration'] = b-max(a,offset)
                        layer['trim'] = layer.get('trim',0)+max(0,offset-a)*layer.get('speed',1)
                        for f in ['fade_in','fade_out']:
                            layer[f] = min(layer.get(f,0),layer['duration'])
                        if layer['duration'] >= self.frame-.00001:
                            right_layers.append(layer)
                item['overlays'],right['overlays'] = left_layers,right_layers
            group.insert(group.index(item)+1,right)
        self.commit(change)
        return right['id']

    def remove(self, ident):
        group,item,_,_ = self.locate(ident)
        self.commit(lambda:group.remove(item))

    def duplicate(self, ident):
        group,item,_,track = self.locate(ident)
        copy = deepcopy(item)
        self.fresh_ids(copy)
        if track != 'scene':
            copy['start'] = copy.get('start',0)+copy['duration']
        self.commit(lambda:group.insert(group.index(item)+1,copy))
        return copy['id']

    def move(self, ident, time):
        group,item,_,track = self.locate(ident)
        def change():
            if track == 'scene':
                group.remove(item)
                offset,index = 0,len(group)
                for i,clip in enumerate(group):
                    if time < offset+clip['duration']/2:
                        index = i
                        break
                    offset += clip['duration']
                group.insert(index,item)
            elif track == 'overlay':
                parent_start = next(s for s in self.spans() if s[0]['id']==ident)[1]-item.get('start',0)
                item['start'] = self.quantize(max(0,time-parent_start))
            else:
                item['start'] = self.quantize(max(0,time))
        self.commit(change)

    def trim(self, ident, edge, delta):
        _,item,_,track = self.locate(ident)
        delta = self.quantize(delta)
        d = item['duration']
        speed = item.get('speed',1)
        def change():
            if edge == 'left':
                amount = max(-item.get('trim',0)/speed,min(delta,d-self.frame))
                if track != 'scene':
                    amount = max(-item.get('start',0),amount)
                    item['start'] = self.quantize(item.get('start',0)+amount)
                item['trim'] = max(0,item.get('trim',0)+amount*speed)
                item['duration'] = self.quantize(d-amount)
                if track == 'scene':
                    kept=[]
                    for layer in item.get('overlays',[]):
                        a=layer.get('start',0)-amount
                        if a < 0:
                            layer['trim']=layer.get('trim',0)-a*layer.get('speed',1)
                            layer['duration']+=a
                        layer['start']=max(0,a)
                        if layer['duration']>=self.frame:
                            kept.append(layer)
                    item['overlays']=kept
            else:
                nd = max(self.frame,d+delta)
                if '_source_duration' in item:
                    nd = min(nd,math.floor((item['_source_duration']-item.get('trim',0))/speed*self.data['fps'])/self.data['fps'])
                item['duration'] = self.quantize(max(self.frame,nd))
            for f in ['fade_in','fade_out']:
                item[f] = min(item.get(f,0),item['duration'])
        self.commit(change)

    def update(self, ident, fields):
        _,item,_,_ = self.locate(ident)
        def change():
            old_speed = item.get('speed',1)
            item.update(deepcopy(fields))
            item['duration'] = max(self.frame,self.quantize(item['duration']))
            if item.get('speed',1) != old_speed:
                item['duration'] = max(self.frame,self.quantize(item['duration']*old_speed/item['speed']))
                for f in ['fade_in','fade_out']:
                    item[f] = min(item.get(f,0),item['duration'])
            if '_source_duration' in item and item.get('trim',0)+item['duration']*item.get('speed',1)>item['_source_duration']+.05:
                raise cut.CutError('起点和时长超出了素材本身。请缩短时长或减小素材起点。')
        self.commit(change)

    def spans(self):
        result,offset = [],0
        for scene in self.data['scenes']:
            result.append((scene,offset,0))
            for layer in scene.get('overlays',[]):
                result.append((layer,offset+layer.get('start',0),1))
            offset += cut.duration(scene,self.data['fps'])
        for item in self.data['texts']:
            result.append((item,item.get('start',0),2))
        for item in self.data['audio']:
            result.append((item,item.get('start',0),3))
        return result
