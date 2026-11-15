"""Glass surfaces painted with alpha, a cached blurred backdrop and specular rims."""
from io import BytesIO
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF,QVariantAnimation,QEasingCurve
from PySide6.QtGui import QColor,QPainter,QPainterPath,QLinearGradient,QPixmap,QImage,QPen,QPalette
from PySide6.QtWidgets import QWidget,QFrame,QPushButton,QStyleOptionButton,QStyle


# Studio look, white (2026-11-10): white surfaces, hairline rules, one black for what matters; the same look as the other tools (look.py).
# The names stay (GlassCanvas, GlassPanel, GlassButton) so the editor's layout code is unchanged.
import look
BG='#ffffff'; PANEL='#ffffff'; RAISED='#ffffff'; HOVER='#f4f4f5'; LINE='#ededee'; LINE2='#e3e3e6'
TEXT='#111113'; MUTED='#5f5f66'; FAINT='#9a9aa2'; ACCENT='#111113'; ACCENT_HI='#2a2a2e'
GLASS_THEME=look.THEME+'''
QMainWindow { background:#ffffff; }
QWidget#workspace { background:transparent; }
QMenuBar { background:#ffffff; color:#5f5f66; border-bottom:1px solid #ededee; padding:2px 8px; }
QMenuBar::item { padding:5px 11px; border-radius:6px; }
QMenuBar::item:selected { background:#f4f4f5; color:#111113; }
QFrame#panel,QWidget#panel,QFrame#topbar { background:transparent; border:0; }
QLabel#brand { color:#111113; font-size:14px; font-weight:600; }
QLabel#projectName { color:#5f5f66; font-size:13.5px; font-weight:500; }
QLabel#panelTitle { color:#111113; font-size:12.5px; font-weight:600; }
QLabel#eyebrow { color:#9a9aa2; font-size:10px; letter-spacing:1px; }
QLabel#muted { color:#5f5f66; font-size:12px; }
QLabel#emptyTitle { color:#111113; font-size:17px; font-weight:600; }
QLabel#emptyHelp { color:#9a9aa2; font-size:12.5px; }
QLabel#time { color:#111113; font-family:"Cascadia Mono",Consolas; font-size:13px; }
QLabel#previewStatus { color:#5f5f66; font-size:11px; }
QLabel#canvasBadge { background:#ffffff; border:1px solid #ededee; border-radius:6px; padding:3px 8px; color:#5f5f66; font-size:11px; }
QWidget#rail { background:transparent; border-right:1px solid #ededee; }
QToolButton#railButton { color:#9a9aa2; border:0; border-radius:9px; padding:9px 0; font-size:11px; }
QToolButton#railButton:hover { background:#fafafa; color:#111113; }
QToolButton#railButton:checked { background:#f4f4f5; color:#111113; }
QPushButton { background:transparent; border:1px solid transparent; border-radius:8px; color:#111113; min-height:20px; max-height:16777215; padding:6px 12px; }
QPushButton:hover,QPushButton:pressed,QPushButton:disabled,QPushButton#subtle,QPushButton#primary,QPushButton#primary:hover,QPushButton#primary:disabled { background:transparent; border-color:transparent; }
QPushButton#filter { color:#5f5f66; padding:4px 10px; font-size:12px; }
QPushButton#filter:checked { color:#111113; }
QPushButton#textPreset { background:transparent; border-color:transparent; color:#111113; }
QPushButton#textPreset:hover { border-color:transparent; }
QToolButton#iconButton { background:transparent; border:1px solid transparent; border-radius:8px; padding:6px; }
QToolButton#iconButton:hover { background:#f4f4f5; }
QToolButton#iconButton:pressed { background:#ededee; }
QToolButton#iconButton:disabled { background:transparent; }
QLineEdit,QTextEdit,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QComboBox { background:#ffffff; color:#111113; border:1px solid #e3e3e6; border-radius:8px; padding:6px 9px; min-height:20px; }
QLineEdit:hover,QTextEdit:hover,QSpinBox:hover,QDoubleSpinBox:hover,QComboBox:hover { border-color:#cfcfd4; }
QLineEdit:focus,QTextEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus { border:1px solid #111113; background:#ffffff; }
QLineEdit#search { background:#fafafa; border:1px solid transparent; border-radius:8px; padding:7px 12px; }
QLineEdit#search:hover { border-color:#e3e3e6; }
QLineEdit#search:focus { background:#ffffff; border-color:#111113; }
QTabBar::tab { padding:9px 2px; margin-right:16px; font-size:12px; }
QStatusBar { color:#9a9aa2; background:#ffffff; border-top:1px solid #ededee; font-size:11px; }
QStatusBar::item { border:0; }
QDialog { background:#ffffff; }
'''

_ICONS=Path(__file__).resolve().parent/'assets'/'ui'
GLASS_THEME+='''
QDoubleSpinBox,QSpinBox { padding-right:25px; }
QDoubleSpinBox::up-button,QSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:21px; border:0; border-left:1px solid #ededee; border-top-right-radius:7px; background:transparent; }
QDoubleSpinBox::down-button,QSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:21px; border:0; border-left:1px solid #ededee; border-bottom-right-radius:7px; background:transparent; }
QDoubleSpinBox::up-button:hover,QSpinBox::up-button:hover,QDoubleSpinBox::down-button:hover,QSpinBox::down-button:hover { background:#f4f4f5; }
QDoubleSpinBox::up-arrow,QSpinBox::up-arrow { image:url("__UP__"); width:10px; height:6px; }
QDoubleSpinBox::down-arrow,QSpinBox::down-arrow,QComboBox::down-arrow { image:url("__DOWN__"); width:10px; height:6px; }
QCheckBox::indicator:checked { image:url("__CHECK__"); }
'''.replace('__UP__',(_ICONS/'chevron-up.svg').as_posix()).replace('__DOWN__',(_ICONS/'chevron-down.svg').as_posix()).replace('__CHECK__',(_ICONS/'check.svg').as_posix())


class GlassCanvas(QWidget):
    """The shared, softly blurred backdrop visible through every glass surface."""
    def __init__(self):
        super().__init__()
        self.backdrop=None
        self.backdrop_size=None
        self.setAutoFillBackground(False)
    def ensure_backdrop(self):
        size=(max(1,self.width()),max(1,self.height()))
        if self.backdrop is not None and self.backdrop_size==size:return
        pix=QPixmap(*size)
        pix.fill(QColor(BG))
        p=QPainter(pix)
        p.end()
        self.backdrop=pix
        self.backdrop_size=size
    def paintEvent(self,event):
        self.ensure_backdrop()
        p=QPainter(self)
        p.drawPixmap(0,0,self.backdrop)


class GlassPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(False)
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        if self.objectName()=='topbar':
            p.fillRect(self.rect(),QColor(BG))
            p.setPen(QPen(QColor(LINE),1))
            p.drawLine(0,self.height()-1,self.width(),self.height()-1)
            return
        radius=12
        p.setPen(QPen(QColor(LINE),1))
        p.setBrush(QColor(PANEL))
        p.drawRoundedRect(rect,radius,radius)


class GlassButton(QPushButton):
    def __init__(self,text='',parent=None):
        super().__init__(text,parent)
        self.glow=0.
        self.animation=QVariantAnimation(self)
        self.animation.setDuration(140)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.set_glow)
    def set_glow(self,value):
        self.glow=float(value)
        self.update()
    def animate(self,target):
        self.animation.stop()
        self.animation.setStartValue(self.glow)
        self.animation.setEndValue(target)
        self.animation.start()
    def enterEvent(self,event):
        self.animate(1.)
        super().enterEvent(event)
    def leaveEvent(self,event):
        self.animate(0.)
        super().leaveEvent(event)
    def paintEvent(self,event):
        option=QStyleOptionButton()
        self.initStyleOption(option)
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        primary=self.objectName() in ('primary','exportVideo')
        flat=self.objectName()=='filter'
        selected=self.isChecked()
        enabled=self.isEnabled()
        hover=self.glow if enabled else 0
        if primary:
            fill=QColor('#2a2a2e') if hover>.5 else QColor(ACCENT)
            if not enabled:fill=QColor('#d5d5d9')
            if self.isDown():fill=QColor('#000000')
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(r,8,8)
            text=QColor('#ffffff')
        elif flat:
            if selected or hover:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#f4f4f5') if selected else QColor(0,0,0,int(8*hover)))
                p.drawRoundedRect(r,7,7)
            text=QColor(TEXT if selected else MUTED if enabled else '#c3c3c9')
        else:
            fill=QColor('#f4f4f5') if selected or self.isDown() else QColor('#ffffff')
            p.setBrush(fill)
            edge=QColor('#e3e3e6')
            if enabled and (hover>.3 or selected):edge=QColor('#cfcfd4')
            if not enabled:edge=QColor(LINE)
            p.setPen(QPen(edge,1))
            p.drawRoundedRect(r,8,8)
            text=QColor(TEXT if enabled else '#b6b6bc')
        if self.hasFocus() and enabled:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(17,17,19,90),1.2))
            p.drawRoundedRect(r.adjusted(1,1,-1,-1),7,7)
        option.palette.setColor(QPalette.ButtonText,text)
        self.style().drawControl(QStyle.CE_PushButtonLabel,option,p,self)
