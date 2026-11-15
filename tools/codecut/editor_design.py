"""Native desktop presentation: layout, icons, media cards and timeline painting."""
from pathlib import Path
from copy import deepcopy
import hashlib
import math
from PySide6.QtCore import Qt,QRectF,QSize
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap,QIcon,QFont,QPainterPath,QLinearGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QToolButton,QVBoxLayout,QHBoxLayout,
    QSplitter,QScrollArea,QStackedWidget,QSlider,QCheckBox,QLineEdit,QButtonGroup,QStyledItemDelegate,
    QStyle,QSizePolicy,QProgressBar,QApplication)
from glass_material import GlassCanvas,GlassPanel,GlassButton,GLASS_THEME
import look

THEME='''
QPushButton#textPreset { text-align:left; padding:18px 14px; font-size:18px; min-height:28px; }
QListWidget#mediaBin { background:transparent; border:0; outline:0; }
QTabWidget::pane { border:0; background:transparent; }
'''
THEME+=GLASS_THEME

PATHS={
 'media':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m3 16 5-5 4 4 3-3 6 6"/><circle cx="16" cy="8" r="1"/>',
 'audio':'<path d="M9 18V5l11-2v13M9 9l11-2"/><ellipse cx="6" cy="18" rx="3" ry="3"/><ellipse cx="17" cy="16" rx="3" ry="3"/>',
 'text':'<path d="M4 5h16M12 5v15M8 20h8M4 5v3M20 5v3"/>',
 'code':'<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18"/>',
 'folder':'<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/><path d="M3 9h18"/>',
 'import':'<path d="M12 15V3m-4 4 4-4 4 4M4 13v7h16v-7"/>',
 'export':'<rect x="3" y="10" width="18" height="11" rx="2"/><path d="M12 14V2m-4 4 4-4 4 4"/>',
 'save':'<path d="M4 3h13l4 4v14H3V3zM7 3v6h10V3M7 21v-8h10v8"/>',
 'undo':'<path d="M4 10h9a7 7 0 0 1 7 7v2M4 10l5-5M4 10l5 5"/>',
 'redo':'<path d="M20 10h-9a7 7 0 0 0-7 7v2m16-9-5-5m5 5-5 5"/>',
 'split':'<path d="M12 3v18M4 7h4v10H4M20 7h-4v10h4"/>',
 'copy':'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
 'trash':'<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
 'left':'<path d="M4 5v14h8M4 12h16m-4-4 4 4-4 4"/>',
 'right':'<path d="M20 5v14h-8M20 12H4m4-4-4 4 4 4"/>',
 'previous':'<path d="M6 4v16m12-16L8 12l10 8z"/>',
 'next':'<path d="M18 4v16M6 4l10 8-10 8z"/>',
 'play':'<path d="m8 4 12 8-12 8z"/>',
 'pause':'<path d="M8 4v16M16 4v16"/>',
 'settings':'<path d="M4 7h16M4 17h16M8 4v6m8 4v6"/>',
 'fit':'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
 'help':'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 3-3 2-3 5m0 3v.1"/>',
 'plus':'<path d="M12 4v16M4 12h16"/>',
 'menu':'<path d="M4 6h16M4 12h16M4 18h16"/>',
 'film':'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18m10-18v18M3 8h4m-4 8h4M17 8h4m-4 8h4"/>',
 'clock':'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
 'spark':'<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>'
}

def icon(name,color='#5f5f66',size=20):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{PATHS.get(name,PATHS["media"])}</g></svg>'
    pix=QPixmap(size*2,size*2)
    pix.fill(Qt.transparent)
    painter=QPainter(pix)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)

def apply_window_chrome(window):
    import os
    if os.name!='nt':return
    try:
        import ctypes
        from ctypes import wintypes
        setter=ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
        setter.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        setter.restype=ctypes.c_long
        dark=ctypes.c_int(0)
        setter(int(window.winId()),20,ctypes.byref(dark),ctypes.sizeof(dark))
        caption=ctypes.c_uint(0x00FFFFFF)
        setter(int(window.winId()),35,ctypes.byref(caption),ctypes.sizeof(caption))
        border=ctypes.c_uint(0x00EEEDED)
        setter(int(window.winId()),34,ctypes.byref(border),ctypes.sizeof(border))
    except (OSError,AttributeError):pass

def tool(name,tip,fn):
    b=QToolButton()
    b.setObjectName('iconButton')
    b.setIcon(icon(name))
    b.setIconSize(QSize(18,18))
    b.setFixedSize(34,32)
    b.setToolTip(tip)
    b.setAccessibleName(tip)
    b.clicked.connect(fn)
    return b

def separator():
    line=QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setStyleSheet('background:rgba(255,255,255,20);border:0;max-width:1px;margin:8px 8px;')
    return line

class AssetDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(126,112)
    def paint(self,p,option,index):
        data=index.data(Qt.UserRole+1) or {}
        r=QRectF(option.rect).adjusted(5,5,-5,-5)
        selected=bool(option.state&QStyle.State_Selected)
        hover=bool(option.state&QStyle.State_MouseOver)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        edge=QLinearGradient(r.topLeft(),r.bottomRight())
        edge.setColorAt(0,QColor('#111113') if selected else QColor('#cfcfd4') if hover else QColor('#ededee'))
        edge.setColorAt(1,QColor('#111113') if selected else QColor('#cfcfd4') if hover else QColor('#ededee'))
        fill=QLinearGradient(r.topLeft(),r.bottomLeft())
        fill.setColorAt(0,QColor('#f4f4f5' if selected else '#fafafa' if hover else '#ffffff'))
        fill.setColorAt(1,QColor('#f4f4f5' if selected else '#fafafa' if hover else '#ffffff'))
        p.setPen(QPen(edge,1.4 if selected else 1))
        p.setBrush(fill)
        p.drawRoundedRect(r,10,10)
        thumb=r.adjusted(1,1,-1,-39)
        p.setClipRect(thumb)
        path=data.get('_thumbnail','')
        if path and Path(path).exists():
            pix=QPixmap(path)
            if data.get('kind')=='audio':
                p.fillRect(thumb,QColor('#eef6f2'))
                p.drawPixmap(thumb.toRect(),pix)
            else:
                scaled=pix.scaled(thumb.size().toSize(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
                p.drawPixmap(int(thumb.center().x()-scaled.width()/2),int(thumb.center().y()-scaled.height()/2),scaled)
        else:
            p.fillRect(thumb,QColor('#f4f4f5' if data.get('kind')!='code' else '#f1f0fa'))
            k={'video':'film','image':'media','code':'code','audio':'audio'}.get(data.get('kind'),'media')
            icon(k,'#9a9aa2',30).paint(p,int(thumb.center().x()-16),int(thumb.center().y()-16),32,32)
        p.setClipping(False)
        p.setPen(QColor('#111113'))
        p.setFont(QFont('Microsoft YaHei UI',9))
        name=data.get('name',Path(data.get('source','')).name)
        label=p.fontMetrics().elidedText(name,Qt.ElideMiddle,int(r.width()-14))
        p.drawText(r.adjusted(8,r.height()-37,-7,-18),Qt.AlignVCenter,label)
        p.setFont(QFont('Segoe UI',8))
        p.setPen(QColor('#9a9aa2'))
        kind={'video':'视频','image':'图片','code':'代码画面','audio':'音频'}.get(data.get('kind'),'素材')
        p.drawText(r.adjusted(8,r.height()-19,-7,-2),Qt.AlignVCenter,kind)
        p.setPen(QColor('#9a9aa2'))
        p.drawText(r.adjusted(8,r.height()-19,-7,-2),Qt.AlignRight|Qt.AlignVCenter,f'{data.get("duration",0):.1f}s')
        p.restore()


def build(w,MediaBin,Timeline,Inspector,VideoCanvas,button):
    root=GlassCanvas()
    root.setObjectName('workspace')
    w.setCentralWidget(root)
    layout=QVBoxLayout(root)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(0)
    top=GlassPanel()
    top.setObjectName('topbar')
    top.setFixedHeight(54)
    head=QHBoxLayout(top)
    head.setContentsMargins(18,0,18,0)
    head.setSpacing(10)
    head.addWidget(look.Mark('cut'))
    brand=QLabel('CodeCut')
    brand.setObjectName('brand')
    w.brand=brand
    head.addWidget(brand)
    head.addSpacing(6)
    w.menuButton=tool('menu','菜单：文件、编辑、帮助',w.show_menu)
    head.addWidget(w.menuButton)
    head.addSpacing(10)
    w.projectLabel=QLabel('未命名项目')
    w.projectLabel.setObjectName('projectName')
    head.addWidget(w.projectLabel)
    head.addStretch()
    head.addWidget(tool('folder','打开项目 · Ctrl+O',w.open_project))
    head.addWidget(tool('save','保存项目 · Ctrl+S',w.save_project))
    head.addWidget(tool('settings','画幅与帧率',w.project_settings))
    head.addSpacing(6)
    ai=button('AI 剪辑',w.open_ai,'subtle')
    ai.setIcon(icon('spark','#5f5f66',16))
    ai.setIconSize(QSize(16,16))
    ai.setFixedWidth(104)
    ai.setToolTip('让 Lumen 的智能体帮你剪这个项目')
    w.aiButton=ai
    ai.setProperty('wide_text','AI 剪辑')
    head.addWidget(ai)
    head.addSpacing(4)
    export=button('导出视频',w.export_dialog,'exportVideo',True)
    export.setIcon(icon('export','#ffffff',16))
    export.setIconSize(QSize(16,16))
    export.setFixedWidth(120)
    w.exportButton=export
    export.setProperty('wide_text','导出视频')
    export.setToolTip('导出视频')
    head.addWidget(export)
    layout.addWidget(top)

    workspace=QWidget()
    body=QVBoxLayout(workspace)
    body.setContentsMargins(12,12,12,2)
    body.setSpacing(0)
    vertical=QSplitter(Qt.Vertical)
    vertical.setChildrenCollapsible(False)
    w.vertical=vertical
    horizontal=QSplitter(Qt.Horizontal)
    horizontal.setChildrenCollapsible(False)
    w.horizontal=horizontal

    library=GlassPanel()
    w.libraryPanel=library
    library.setObjectName('panel')
    library.setMinimumWidth(378)
    library.setMaximumWidth(420)
    lib=QHBoxLayout(library)
    lib.setContentsMargins(0,0,0,0)
    lib.setSpacing(0)
    rail=QWidget()
    w.rail=rail
    rail.setObjectName('rail')
    rail.setFixedWidth(62)
    nav=QVBoxLayout(rail)
    nav.setContentsMargins(5,10,5,10)
    nav.setSpacing(6)
    w.navGroup=QButtonGroup(w)
    w.navGroup.setExclusive(True)
    buttons=[]
    for n,(name,text) in enumerate([('media','素材'),('audio','音频'),('text','文字'),('code','代码')]):
        b=QToolButton()
        b.setObjectName('railButton')
        b.setIcon(icon(name,'#5f5f66',21))
        b.setIconSize(QSize(22,22))
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setCheckable(True)
        b.setFixedSize(52,64)
        w.navGroup.addButton(b,n)
        buttons.append(b)
        nav.addWidget(b)
    buttons[0].setChecked(True)
    nav.addStretch()
    nav.addWidget(tool('help','新手使用指南',w.help_dialog))
    lib.addWidget(rail)
    w.libraryStack=QStackedWidget()
    lib.addWidget(w.libraryStack,1)
    media=QWidget()
    ml=QVBoxLayout(media)
    ml.setContentsMargins(12,13,12,12)
    ml.setSpacing(8)
    titleline=QHBoxLayout()
    title=QLabel('项目素材')
    title.setObjectName('panelTitle')
    titleline.addWidget(title)
    titleline.addStretch()
    w.assetCount=QLabel('0 个素材')
    w.assetCount.setObjectName('muted')
    titleline.addWidget(w.assetCount)
    ml.addLayout(titleline)
    importButton=button('导入',w.import_dialog,'importMedia')
    importButton.setObjectName('subtle')
    importButton.setIcon(icon('plus','#5f5f66',16))
    importButton.setFixedWidth(72)
    importButton.setToolTip('导入视频、图片、音乐或 HTML')
    titleline.addWidget(importButton)
    w.mediaSearch=QLineEdit()
    w.mediaSearch.setObjectName('search')
    w.mediaSearch.setPlaceholderText('搜索素材名称')
    w.mediaSearch.setClearButtonEnabled(True)
    ml.addWidget(w.mediaSearch)
    filters=QHBoxLayout()
    filters.setSpacing(1)
    w.filterGroup=QButtonGroup(w)
    for i,text in enumerate(['全部','视频','音频','代码']):
        b=GlassButton(text)
        b.setObjectName('filter')
        b.setCheckable(True)
        w.filterGroup.addButton(b,i)
        filters.addWidget(b)
        if i==0:b.setChecked(True)
    filters.addStretch()
    ml.addLayout(filters)
    w.bin=MediaBin()
    w.bin.setGridSize(QSize(126,112))
    w.bin.setItemDelegate(AssetDelegate(w.bin))
    w.bin.setMouseTracking(True)
    w.bin.setSpacing(0)
    w.bin.filesDropped.connect(w.import_files)
    w.bin.itemDoubleClicked.connect(lambda item:w.insert_asset(item.data(Qt.UserRole),w.model.total,False))
    ml.addWidget(w.bin,1)
    w.libraryHint=QLabel('双击加入剪辑 · 拖动可放到指定位置')
    w.libraryHint.setObjectName('muted')
    w.libraryHint.setWordWrap(True)
    ml.addWidget(w.libraryHint)
    add=QHBoxLayout()
    add.setSpacing(6)
    mainAdd=button('加入主画面',w.add_selected_asset,'subtle')
    overlayAdd=button('画中画',lambda:w.add_selected_asset(True),'subtle')
    for b in [mainAdd,overlayAdd]:b.setEnabled(False)
    w.bin.currentItemChanged.connect(lambda current,previous:[b.setEnabled(current is not None) for b in [mainAdd,overlayAdd]])
    add.addWidget(mainAdd)
    add.addWidget(overlayAdd)
    ml.addLayout(add)
    w.libraryStack.addWidget(media)
    textpage=QWidget()
    tl=QVBoxLayout(textpage)
    tl.setContentsMargins(16,16,16,16)
    title=QLabel('文字与标题')
    title.setObjectName('panelTitle')
    tl.addWidget(title)
    hint=QLabel('添加后，在右侧编辑文字和样式。')
    hint.setObjectName('muted')
    hint.setWordWrap(True)
    tl.addWidget(hint)
    for label,size,color in [('添加标题',64,'#111113'),('添加字幕',36,'#111113'),('重点标注',48,'#2f6bff')]:
        def preset(checked=False,label=label,size=size,color=color):
            w.add_title()
            w.model.update(w.selection,{'font_size':size,'color':color,'text':label.replace('添加','')})
            w.refresh(True)
        b=button(label,preset,'textPreset')
        b.setIcon(icon('text',color,20))
        tl.addWidget(b)
    tl.addStretch()
    w.libraryStack.addWidget(textpage)
    codepage=QWidget()
    cp=QVBoxLayout(codepage)
    cp.setContentsMargins(18,18,18,18)
    title=QLabel('让代码成为画面')
    title.setObjectName('panelTitle')
    cp.addWidget(title)
    hint=QLabel('导入 HTML、Git 仓库，或连接\n已经运行的网页预览。')
    hint.setObjectName('muted')
    hint.setWordWrap(True)
    cp.addWidget(hint)
    cp.addSpacing(12)
    b=button('导入代码 / Git',w.code_dialog,'subtle')
    b.setIcon(icon('code','#5f5f66',18))
    cp.addWidget(b)
    cp.addStretch()
    cp.addWidget(button('体验示例项目',w.open_demo,'subtle'))
    w.libraryStack.addWidget(codepage)
    w.media_filter=''
    def filter_media(n):
        w.media_filter=['','video','audio','code'][n]
        w.refresh_bin()
    w.filterGroup.idClicked.connect(filter_media)
    def navigate(n):
        if w.layout_mode!='wide':
            same=getattr(w,'_nav_last',-1)==n and w.drawer=='library'
            w._nav_last=n
            w.drawer='' if same else 'library'
            relayout(w)
        if n in [0,1]:
            w.libraryStack.setCurrentIndex(0)
            w.filterGroup.button(2 if n==1 else 0).setChecked(True)
            filter_media(2 if n==1 else 0)
        else:w.libraryStack.setCurrentIndex(1 if n==2 else 2)
    w.navGroup.idClicked.connect(navigate)
    w.layout_mode='wide'
    w.mediaSearch.textChanged.connect(lambda _:w.refresh_bin())
    horizontal.addWidget(library)

    center=GlassPanel()
    w.center=center
    center.setObjectName('panel')
    center.setMinimumWidth(360)
    centerl=QVBoxLayout(center)
    centerl.setContentsMargins(14,9,14,10)
    centerl.setSpacing(4)
    line=QHBoxLayout()
    title=QLabel('播放器')
    title.setObjectName('panelTitle')
    line.addWidget(title)
    line.addStretch()
    w.canvasInfo=QLabel('1280 × 720 · 30 fps')
    w.canvasInfo.setObjectName('canvasBadge')
    line.addWidget(w.canvasInfo)
    centerl.addLayout(line)
    w.overviewLine=QLabel('')
    w.overviewLine.setObjectName('muted')
    w.overviewLine.setWordWrap(True)
    w.overviewLine.hide()
    centerl.addWidget(w.overviewLine)
    w.preview=QStackedWidget()
    w.preview.setMinimumHeight(190)
    w.preview.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
    welcome=QWidget()
    welcome.setObjectName('welcome')
    welcome.setStyleSheet('QWidget#welcome{background:#fafafa;border:1px solid #ededee;border-radius:10px;}')
    wl=QVBoxLayout(welcome)
    wl.setAlignment(Qt.AlignCenter)
    wl.setSpacing(10)
    artwork=QLabel()
    artwork.setPixmap(icon('film','#9a9aa2',44).pixmap(44,44))
    artwork.setAlignment(Qt.AlignCenter)
    wl.addWidget(artwork)
    empty=QLabel('每个好故事，都从这里开始')
    empty.setObjectName('emptyTitle')
    empty.setAlignment(Qt.AlignCenter)
    empty.setWordWrap(True)
    wl.addWidget(empty)
    help=QLabel('导入一段视频，或把代码画面加入时间线。')
    help.setObjectName('emptyHelp')
    help.setAlignment(Qt.AlignCenter)
    help.setWordWrap(True)
    wl.addWidget(help)
    options=QHBoxLayout()
    options.addStretch()
    options.addWidget(button('导入素材',w.import_dialog,'subtle'))
    options.addWidget(button('打开示例',w.open_demo,'subtle'))
    options.addStretch()
    wl.addLayout(options)
    w.preview.addWidget(welcome)
    w.video=VideoCanvas()
    w.preview.addWidget(w.video)
    pending=QWidget()  # the project has clips, the picture is not ready: never the "start here" page
    pending.setObjectName('pending')
    pending.setStyleSheet('QWidget#pending{background:#fafafa;border:1px solid #ededee;border-radius:10px;}')
    pl=QVBoxLayout(pending)
    pl.setAlignment(Qt.AlignCenter)
    pl.setSpacing(10)
    pendingArt=QLabel()
    pendingArt.setPixmap(icon('film','#9a9aa2',36).pixmap(36,36))
    pendingArt.setAlignment(Qt.AlignCenter)
    pl.addWidget(pendingArt)
    w.pendingLabel=QLabel('点“更新预览”查看合成效果')
    w.pendingLabel.setObjectName('emptyHelp')
    w.pendingLabel.setAlignment(Qt.AlignCenter)
    w.pendingLabel.setWordWrap(True)
    pl.addWidget(w.pendingLabel)
    w.preview.addWidget(pending)
    centerl.addWidget(w.preview,1)
    w.seekSlider=QSlider(Qt.Horizontal)
    w.seekSlider.setAccessibleName('预览播放位置')
    w.seekSlider.setRange(0,0)
    w.seekSlider.setFixedHeight(15)
    w.seekSlider.sliderMoved.connect(lambda n:w.seek(n/1000))
    centerl.addWidget(w.seekSlider)
    controls=QHBoxLayout()
    controls.setSpacing(4)
    w.timeLabel=QLabel('00:00.00 / 00:00.00')
    w.timeLabel.setObjectName('time')
    controls.addWidget(w.timeLabel)
    controls.addStretch()
    w.prevButton=tool('previous','回到开头',lambda:w.seek(0))
    controls.addWidget(w.prevButton)
    w.playButton=button('播放',w.toggle_play,'subtle')
    w.playButton.setIcon(icon('play','#111113',14))
    w.playButton.setFixedWidth(76)
    controls.addWidget(w.playButton)
    w.nextButton=tool('next','下一帧',lambda:w.seek(w.position+w.model.frame))
    controls.addWidget(w.nextButton)
    controls.addStretch()
    w.previewButton=button('更新预览',w.start_preview,'subtle')
    w.previewButton.setFixedWidth(88)
    w.previewButton.setProperty('wide_text','更新预览')
    controls.addWidget(w.previewButton)
    centerl.addLayout(controls)
    state=QHBoxLayout()  # one line, whatever is going on: the picture keeps its size
    state.setContentsMargins(0,0,0,0)
    state.setSpacing(8)
    w.previewStatus=QLabel('合成预览')
    w.previewStatus.setObjectName('previewStatus')
    state.addWidget(w.previewStatus)
    w.jobLabel=QLabel('')
    w.jobLabel.setObjectName('muted')
    w.jobLabel.hide()
    state.addWidget(w.jobLabel)
    state.addStretch()
    w.cancelButton=button('取消',w.cancel_job,'subtle')
    w.cancelButton.setStyleSheet('QPushButton{padding:0 12px;min-height:0;font-size:12px;}')
    w.cancelButton.setFixedHeight(24)
    w.cancelButton.hide()
    state.addWidget(w.cancelButton)
    stateBox=QWidget()
    stateBox.setFixedHeight(28)
    stateBox.setLayout(state)
    centerl.addWidget(stateBox)
    w.progress=QProgressBar()
    w.progress.setTextVisible(False)
    w.progress.setFixedHeight(3)
    keep=w.progress.sizePolicy()
    keep.setRetainSizeWhenHidden(True)
    w.progress.setSizePolicy(keep)
    w.progress.hide()
    centerl.addWidget(w.progress)
    horizontal.addWidget(center)

    right=GlassPanel()
    w.right=right
    right.setObjectName('panel')
    right.setMinimumWidth(282)
    right.setMaximumWidth(330)
    rl=QVBoxLayout(right)
    rl.setContentsMargins(14,13,14,12)
    rl.setSpacing(10)
    w.inspector=Inspector()
    w.inspector.setMinimumWidth(248)
    w.inspector.apply.connect(w.apply_properties)
    props=QScrollArea()
    props.setWidgetResizable(True)
    props.setWidget(w.inspector)
    rl.addWidget(props,1)
    w.inspector.outer.removeWidget(w.inspector.applyButton)
    w.inspector.applyButton.setObjectName('subtle')
    w.inspector.applyButton.setText('应用更改')
    rl.addWidget(w.inspector.applyButton)
    horizontal.addWidget(right)
    horizontal.setStretchFactor(0,0)
    horizontal.setStretchFactor(1,1)
    horizontal.setStretchFactor(2,0)
    horizontal.setSizes([382,820,294])
    vertical.addWidget(horizontal)

    bottom=GlassPanel()
    bottom.setObjectName('panel')
    bl=QVBoxLayout(bottom)
    bl.setContentsMargins(0,0,0,0)
    bl.setSpacing(0)
    tools=QWidget()
    tools.setFixedHeight(44)
    toolbar=QHBoxLayout(tools)
    toolbar.setContentsMargins(10,4,12,4)
    toolbar.setSpacing(3)
    w.undoButton=tool('undo','撤销 · Ctrl+Z',lambda:w.history(False))
    w.redoButton=tool('redo','重做 · Ctrl+Shift+Z',lambda:w.history(True))
    toolbar.addWidget(w.undoButton)
    toolbar.addWidget(w.redoButton)
    toolbar.addWidget(separator())
    split=button('分割',w.split_clip,'subtle')
    split.setIcon(icon('split',size=18))
    split.setToolTip('在播放头处分割 · Ctrl+B')
    split.setProperty('wide_text','分割')
    w.splitButton=split
    w.editButtons=[split]
    toolbar.addWidget(split)
    for name,tip,callback in [('left','保留播放头左侧',lambda:w.trim_to_head(False)),('right','保留播放头右侧',lambda:w.trim_to_head(True)),('copy','复制片段 · Ctrl+D',w.duplicate_clip),('trash','删除选中片段',w.remove_clip)]:
        b=tool(name,tip,callback)
        w.editButtons.append(b)
        toolbar.addWidget(b)
    toolbar.addWidget(separator())
    title=button('文字',w.add_title,'subtle')
    title.setIcon(icon('text',size=17))
    title.setProperty('wide_text','文字')
    title.setToolTip('添加文字')
    w.titleButton=title
    toolbar.addWidget(title)
    toolbar.addStretch()
    snap=QCheckBox('吸附')
    w.snapBox=snap
    snap.setChecked(True)
    toolbar.addWidget(snap)
    toolbar.addSpacing(14)
    toolbar.addWidget(tool('fit','让时间线适应窗口',w.fit_timeline))
    zoom=QSlider(Qt.Horizontal)
    zoom.setRange(16,260)
    zoom.setValue(96)
    zoom.setFixedWidth(92)
    zoom.setAccessibleName('时间线缩放')
    w.zoomSlider=zoom
    toolbar.addWidget(zoom)
    # in the narrow layouts the side panels fold away: this button brings the clip settings in (and sends them away again)
    w.inspectorButton=tool('settings','片段调整',lambda:w.toggle_drawer('inspector'))
    w.inspectorButton.hide()
    toolbar.addWidget(w.inspectorButton)
    w.toolbarSeparators=[x for x in tools.findChildren(QFrame) if x.frameShape()==QFrame.VLine] if 'QFrame' in globals() else []
    bl.addWidget(tools)
    w.timeline=Timeline(w.model)
    w.timeline.left=116
    w.timeline.row=48
    w.timeline.setMinimumHeight(232)
    w.timeline.visuals={}
    w.timeline.selected.connect(w.select)
    w.timeline.seek.connect(w.seek)
    w.timeline.edit.connect(w.timeline_edit)
    w.timeline.dropped.connect(w.insert_asset)
    w.timeline.filesDropped.connect(w.import_files)
    snap.toggled.connect(lambda v:setattr(w.timeline,'snap',v))
    zoom.valueChanged.connect(w.zoom)
    w.timelineScroll=QScrollArea()
    w.timelineScroll.setWidgetResizable(True)
    w.timelineScroll.setWidget(w.timeline)
    w.timelineScroll.setMinimumHeight(170)
    bl.addWidget(w.timelineScroll)
    bottom.setMinimumHeight(220)
    vertical.addWidget(bottom)
    vertical.setStretchFactor(0,1)
    vertical.setStretchFactor(1,0)
    vertical.setSizes([580,284])  # all four tracks in view; the bar can still be dragged lower on a small window
    body.addWidget(vertical)
    layout.addWidget(workspace,1)
    w.statusBar().setSizeGripEnabled(False)
    w.drawer=''
    relayout(w)
    w.statusBar().showMessage('拖动素材加入剪辑   ·   Ctrl+B 分割   ·   空格播放 / 暂停')


WIDE,INSPECTOR,MID=1500,1100,760


def relayout(w):
    """Only when the layout really changes (a wider or narrower step, a drawer opened or closed), and never inside itself: a window being
    dragged wider by a pixel asks hundreds of times, and each answer re-styles the buttons."""
    if getattr(w,'_relaying',False):
        return
    width=w.width()
    state=(width>=WIDE,width>=INSPECTOR,width>=MID,w.drawer)
    if getattr(w,'_layout_state',None)==state:
        return
    w._relaying=True
    try:
        _relayout(w)
        w._layout_state=state
    finally:
        w._relaying=False


def _relayout(w):
    """The window's parts for the room it has. Wide: everything beside each other. Mid: the player in the middle, the library and the clip
    settings one at a time beside it. Narrow (Lumen's tool area can be as thin as 420): the player takes the whole width, and the library
    or the clip settings take it over while they are open. Called again whenever the window is resized."""
    width=w.width()
    mode='wide' if width>=WIDE else 'mid' if width>=MID else 'narrow'
    w.layout_mode=mode
    narrow=mode=='narrow'
    wide=mode=='wide'
    drawer=w.drawer if not wide else ''
    w.drawer=drawer
    # the top bar: words go before the buttons do
    w.brand.setVisible(not narrow)
    w.projectLabel.setVisible(not narrow)
    squeeze='QPushButton{min-width:0;padding:0;}'  # the buttons' own style gives them a minimum width: icon-only ones must not keep it
    for b in (w.aiButton,w.exportButton):
        base=b.property('wide_text')
        b.setText(base if not narrow else '')
        b.setFixedWidth((104 if b is w.aiButton else 120) if not narrow else 36)
        b.setStyleSheet(squeeze if narrow else '')
    w.canvasInfo.setVisible(wide)
    # the library (rail + page)
    lib_open=wide or drawer=='library'
    w.libraryStack.setVisible(lib_open)
    w.rail.setVisible(True)
    if wide:
        w.libraryPanel.setMinimumWidth(378)
        w.libraryPanel.setMaximumWidth(420)
    else:
        w.libraryPanel.setMinimumWidth(62 if not lib_open else (62+230 if not narrow else 62))
        w.libraryPanel.setMaximumWidth(62 if not lib_open else (420 if not narrow else 16777215))
    # the clip settings
    inline=width>=INSPECTOR   # the clip settings and the numbers stay beside the player while there is room for them
    if inline and drawer=='inspector':
        w.drawer=drawer=''
    insp_open=inline or drawer=='inspector'
    w.right.setVisible(insp_open)
    if inline:
        w.right.setMinimumWidth(282)
        w.right.setMaximumWidth(330)
    else:
        w.right.setMinimumWidth(0)
        w.right.setMaximumWidth(330 if not narrow else 16777215)
    w.inspector.setMinimumWidth(248 if inline else 0)
    # the player: it gives way to a drawer only when there is no room for both
    w.center.setMinimumWidth(360 if wide else 0)
    w.center.setVisible(not (narrow and drawer))
    w.horizontal.setStretchFactor(1,10)
    w.overviewLine.setVisible(not inline)
    w.prevButton.setVisible(not narrow)
    w.nextButton.setVisible(not narrow)
    w.timeLabel.setVisible(True)
    w.previewButton.setText(w.previewButton.property('wide_text') if not narrow else '预览')
    w.previewButton.setFixedWidth(88 if not narrow else 60)
    w.playButton.setFixedWidth(76 if not narrow else 64)
    for b in (w.previewButton,w.playButton,w.splitButton,w.titleButton):
        b.setStyleSheet(squeeze if narrow else '')
    # the timeline's tool strip
    w.splitButton.setText(w.splitButton.property('wide_text') if not narrow else '')
    w.titleButton.setText(w.titleButton.property('wide_text') if not narrow else '')
    w.snapBox.setVisible(not narrow)
    w.zoomSlider.setVisible(not narrow)
    w.zoomSlider.setFixedWidth(92)
    w.inspectorButton.setVisible(not inline)
    for s in w.toolbarSeparators:
        s.setVisible(not narrow)
    w.horizontal.setSizes([382,820,294] if wide else [62 if not lib_open else 330,900,294] if inline else [1,1,1])
    update_overview(w)


def update_overview(w):
    """One line with what the panel of numbers says: clips, total length, picture, frame rate."""
    data=w.model.data
    clips=len(data['scenes'])+len(data['audio'])
    w.overviewLine.setText(f"{clips} 个片段 · 总时长 {w.model.total:.1f}s · {data['width']} × {data['height']} · {data['fps']} fps")


def paint_timeline(w,event):
    p=QPainter(w)
    p.setRenderHint(QPainter.Antialiasing)
    p.fillRect(w.rect(),QColor('#ffffff'))
    top=34
    labels=[('film','主画面','#7d97ff'),('media','画中画','#b18cff'),('text','文字','#f0b453'),('audio','声音','#3fc7a3')]
    step=1 if w.pps>=65 else 2 if w.pps>=28 else 5
    for row,(glyph,label,color) in enumerate(labels):
        y=top+row*w.row
        p.fillRect(0,y,w.width(),w.row-1,QColor(0,0,0,6 if row%2==0 else 2))
    for sec in range(0,int((w.width()-w.left)/w.pps)+2,step):
        x=w.left+sec*w.pps
        p.setPen(QPen(QColor(0,0,0,12),1))
        p.drawLine(int(x),top,int(x),w.height())
        p.setPen(QColor('#b6b6bc'))
        p.drawLine(int(x),top-7,int(x),top-1)
        p.setFont(QFont('Consolas',8))
        p.drawText(int(x)+5,21,f'{sec//60:02d}:{sec%60:02d}')
        for j in range(1,4):
            xx=x+j*step*w.pps/4
            p.setPen(QColor('#dedee2'))
            p.drawLine(int(xx),top-4,int(xx),top-1)
    p.fillRect(0,0,w.left,w.height(),QColor('#fafafa'))
    p.setPen(QColor('#ededee'))
    p.drawLine(w.left-1,0,w.left-1,w.height())
    p.setPen(QColor('#9a9aa2'))
    p.setFont(QFont('Microsoft YaHei UI',8))
    p.drawText(13,22,'轨道')
    spans=w.model.spans()
    for row,(glyph,label,color) in enumerate(labels):
        y=top+row*w.row
        icon(glyph,color,16).paint(p,12,y+15,16,16)
        p.setFont(QFont('Microsoft YaHei UI',9))
        p.setPen(QColor('#5f5f66'))
        p.drawText(QRectF(37,y,70,w.row),Qt.AlignVCenter,label)
        p.setPen(QColor('#ededee'))
        p.drawLine(0,y+w.row-1,w.left,y+w.row-1)
    w.boxes=[]
    basecolors=[QColor('#3550c8'),QColor('#6b46c9'),QColor('#a8701c'),QColor('#16866d')]
    for item,t,row in spans:
        r=QRectF(w.left+t*w.pps,top+row*w.row+4,max(8,item['duration']*w.pps-2),w.row-8)
        if w.drag and w.drag[0]==item['id']:
            if w.drag[1]=='move':r.translate(w.delta*w.pps,0)
            elif w.drag[1]=='left':r.adjust(w.delta*w.pps,0,0,0)
            else:r.adjust(0,0,w.delta*w.pps,0)
        w.boxes.append((item['id'],r))
        p.save()
        path=QPainterPath()
        path.addRoundedRect(r,6,6)
        p.setClipPath(path)
        gloss=QLinearGradient(r.topLeft(),r.bottomLeft())
        gloss.setColorAt(0,basecolors[row].lighter(108))
        gloss.setColorAt(1,basecolors[row])
        p.fillRect(r,gloss)
        visual=getattr(w,'visuals',{}).get(item.get('source',''),{})
        thumb=visual.get('thumbnail',item.get('_thumbnail',''))
        wave=visual.get('waveform',item.get('_waveform',''))
        if row in [0,1] and thumb and Path(thumb).exists():
            pix=QPixmap(thumb)
            mini=pix.scaled(int(r.height()*16/9),int(r.height()),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            for xx in range(int(r.left()),int(r.right()),max(1,mini.width())):p.drawPixmap(xx,int(r.top()),mini)
            scrim=QLinearGradient(r.left(),0,r.left()+min(r.width(),150),0)  # the name reads, the picture stays vivid
            scrim.setColorAt(0,QColor(8,8,12,235))
            scrim.setColorAt(.6,QColor(8,8,12,190))
            scrim.setColorAt(1,QColor(8,8,12,0))
            p.fillRect(r,scrim)
        if row==3 and wave and Path(wave).exists():
            p.setOpacity(.8)
            p.drawPixmap(r.toRect(),QPixmap(wave))
            p.setOpacity(1)
            p.fillRect(QRectF(r.x(),r.y(),r.width(),20),QColor(6,30,24,190))
        name=item.get('text','') if row==2 else item.get('name',Path(item.get('source','')).name)
        p.setFont(QFont('Microsoft YaHei UI',8))
        p.setPen(QColor('#ffffff'))
        p.drawText(r.adjusted(9,2,-8,-18),Qt.AlignVCenter,p.fontMetrics().elidedText(name.replace('\n',' '),Qt.ElideRight,max(1,int(r.width()-18))))
        p.setPen(QColor(255,255,255,170))
        p.setFont(QFont('Consolas',8))
        p.drawText(r.adjusted(9,21,-8,-2),Qt.AlignVCenter,f'{item["duration"]:.2f}s')
        p.restore()
        chosen=item['id']==w.selection
        p.setPen(QPen(QColor('#111113') if chosen else basecolors[row].darker(115),2 if chosen else 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r,6,6)
        shine=QLinearGradient(r.topLeft(),r.bottomRight())
        shine.setColorAt(0,QColor(255,255,255,40 if chosen else 22))
        shine.setColorAt(1,QColor(255,255,255,0))
        p.setPen(QPen(shine,1))
        p.drawRoundedRect(r.adjusted(1,1,-1,-1),5,5)
        if chosen:
            p.setPen(QPen(QColor('#ffffff'),2))
            for x in [r.left()+4,r.right()-4]:p.drawLine(int(x),int(r.top()+12),int(x),int(r.bottom()-12))
    if not spans:
        p.setPen(QColor('#9a9aa2'))
        p.setFont(QFont('Microsoft YaHei UI',10))
        p.drawText(QRectF(w.left+25,top,500,w.row),Qt.AlignVCenter,'把素材拖到这里，开始剪辑')
    x=w.left+w.position*w.pps
    p.setPen(QPen(QColor('#ff5d5d'),1.5))
    p.drawLine(int(x),top-10,int(x),w.height())
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#ff5d5d'))
    head=QPainterPath()
    head.moveTo(x-5,top-14)
    head.lineTo(x+5,top-14)
    head.lineTo(x+5,top-6)
    head.lineTo(x,top-1)
    head.lineTo(x-5,top-6)
    head.closeSubpath()
    p.drawPath(head)


def populate_library(w):
    from PySide6.QtWidgets import QListWidgetItem
    current=w.bin.currentItem().data(Qt.UserRole) if w.bin.currentItem() else None
    assets=deepcopy(w.model.data.get('assets',[]))
    known={a['source'] for a in assets}
    for clip in w.model.data['scenes']+w.model.data['audio']:
        for item in [clip]+clip.get('overlays',[]):
            if item['source'] not in known:
                assets.append(deepcopy(item))
                known.add(item['source'])
    w.library=assets
    w.assetCount.setText(f'{len(assets)} 个素材')
    w.bin.clear()
    query=w.mediaSearch.text().strip().lower()
    for asset in assets:
        visual=w.visuals.get(asset['source'],{})
        if visual.get('thumbnail'):asset['_thumbnail']=visual['thumbnail']
        if w.media_filter and asset['kind']!=w.media_filter:continue
        name=asset.get('name',Path(asset['source']).name)
        if query and query not in name.lower():continue
        item=QListWidgetItem(name)
        item.setData(Qt.UserRole,asset['id'])
        item.setData(Qt.UserRole+1,asset)
        item.setToolTip(f'{name}\n{asset["source"]}')
        w.bin.addItem(item)
        if asset['id']==current:w.bin.setCurrentItem(item)
    w.timeline.visuals=w.visuals
    w.timeline.update()
    missing=[deepcopy(a) for a in assets if a['source'] not in w.visuals]
    if missing and not w.thumbnail_busy:
        w.thumbnail_busy=True
        project_path=w.model.path
        def generate():
            import codecut as cut
            cache=cut.ROOT/'state'/'cache'
            result={}
            for asset in missing:
                source=asset['source']
                try:
                    stamp=str(Path(source).stat().st_mtime_ns) if Path(source).is_file() else 'url'
                    key=hashlib.sha256((source+stamp).encode()).hexdigest()[:20]
                    thumb=cache/f'card-{key}.png'
                    entry={}
                    if asset.get('_thumbnail') and Path(asset['_thumbnail']).exists():
                        entry['thumbnail']=asset['_thumbnail']
                    elif not thumb.exists():
                        if asset['kind']=='code':
                            with cut.code_page(asset,project_path,640,360) as (page,hook,errors):
                                cut.seek_page(page,hook,0,640,360,0)
                                page.screenshot(path=str(thumb))
                            entry['thumbnail']=str(thumb)
                        elif asset['kind']=='audio':
                            cut.run([cut.tool('ffmpeg'),'-v','error','-y','-i',source,'-filter_complex','showwavespic=s=640x100:colors=0x8CCBB0','-frames:v','1',thumb],timeout=45)
                            entry.update(thumbnail=str(thumb),waveform=str(thumb))
                        else:
                            cut.run([cut.tool('ffmpeg'),'-v','error','-y','-i',source,'-frames:v','1','-vf','scale=320:180:force_original_aspect_ratio=decrease','-threads','1',thumb],timeout=30)
                            entry['thumbnail']=str(thumb)
                    else:
                        entry['thumbnail']=str(thumb)
                        if asset['kind']=='audio':entry['waveform']=str(thumb)
                    if asset.get('_waveform'):entry['waveform']=asset['_waveform']
                    result[source]=entry
                except Exception:
                    result[source]={}
            return result
        def ready(result):
            w.thumbnail_busy=False
            w.visuals.update(result)
            populate_library(w)
        w.run_task(generate,ready)
