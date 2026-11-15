"""Colours, fonts and the Qt style sheet.

White theme (2026-11-03, the user's choice, after Codex's desktop app): white surfaces, a very light grey for the
rail and the chat list, grey hairline borders, black primary buttons, a blue send button. The names below are the
glass theme's (2026-10-27), kept so every page picks the new values up; they are opaque now.
"""

from __future__ import annotations

import re

APP_NAME = "Lumen"  # the name the window shows (renamed from Code Doctor, 2026-11-03)
import sys as _sys

FONT_FAMILY = "PingFang SC" if _sys.platform == "darwin" else "Microsoft YaHei UI"  # Qt falls back to a CJK font elsewhere
MONO_FAMILY = "Menlo, Monaco" if _sys.platform == "darwin" else "Cascadia Mono, Consolas"

C = {
    "bg": "#ffffff",
    "sidebar": "#f9f9f9",      # quiet fills: the address box, the ask box
    "rail": "#ffffff",         # the side columns: white with a hairline, like the tools' windows
    "sidebar_hover": "#f5f5f6",
    "sidebar_sel": "#ededee",
    "card": "#ffffff",
    "border": "#ececec",
    "border_strong": "#dddddd",
    "text": "#1f1f1f",
    "text2": "#5d5d5d",
    "text3": "#8f8f8f",
    "ink": "#0d0d0d",          # headlines
    "accent": "#ef8a17",       # links, focus, the send button
    "accent_hover": "#d67708",
    "accent_soft": "#fff2df",
    "accent_bright": "#ffb454",
    "user_bubble": "#f4f4f4",
    "green": "#2f8f5b",
    "green_soft": "#e2f3ea",
    "red": "#c8463d",
    "red_soft": "#f9e3e1",
    "amber": "#b7791f",
    "amber_soft": "#fbf0dc",
    "blue": "#3b6fd6",
    "blue_soft": "#e4ecfb",
    "gray_soft": "#f2f2f2",
    "term_bg": "#fbfbfb",      # the terminal on the right: white like the rest (2026-11-10)
    "term_ink": "#26262b",
}

ACCENTS = {  # name -> (main, hover, soft, bright)
    "amber": ("#ef8a17", "#d67708", "#fff2df", "#ffb454"),
    "blue": ("#2f6bff", "#1f57e0", "#e8efff", "#7fa6ff"),
    "violet": ("#7c5cf0", "#6743dc", "#efeaff", "#b09dff"),
    "green": ("#1f9d6b", "#178257", "#e1f5ec", "#63cfa3"),
    "rose": ("#e5487a", "#cc2f62", "#fde8ef", "#f58cae"),
    "ink": ("#26241f", "#000000", "#efece6", "#d9d4ca"),
}
_look = {"font": 1.0, "radius": 1.0}


def configure(ui: dict) -> None:
    """The user's appearance settings (desktop/prefs.py). Colours are read when something is painted or styled."""
    C["accent"], C["accent_hover"], C["accent_soft"], C["accent_bright"] = ACCENTS.get(ui.get("accent"), ACCENTS["amber"])
    _look["font"] = {"small": 0.875, "large": 1.125}.get(ui.get("font_size"), 1.0)  # the same 14 / 16 / 18 px the page uses (App.jsx)
    _look["radius"] = 1.0  # the 圆角 setting is gone


# surfaces (opaque in the white theme)
GLASS = "#ffffff"          # cards
GLASS_STRONG = "#ffffff"   # inputs, menus, things you type into
GLASS_SOFT = "#f9f9f9"     # quiet boxes inside cards
GLASS_RIM = "#ececec"      # their borders
GLASS_HOVER = "#f4f4f4"
GLASS_SEL = "#ececec"
HAIRLINE = "#ececec"

ROLE_COLOR = {"general": "#1a7f86", "head_dispatch": "#3b6fd6", "head_logic": "#7a52c7", "worker": "#2f8f5b",
              "guardian": "#c97a22", "investigator": "#5a7a2b", "system": "#78849a", "user": "#3a6ba8"}
NODE_COLOR = {"symbol": "#4b7bec", "route": "#e17055", "state": "#e1a400", "table": "#d63384", "event": "#00a383",
              "ws_msg": "#0984e3", "file": "#78849a", "external": "#6c5ce7", "invariant": "#c8463d", "stage": "#636e72"}
NODE_CN = {"symbol": "函数/类", "route": "接口", "state": "状态", "table": "数据表", "event": "事件", "ws_msg": "网络消息",
           "file": "文件", "external": "外部服务"}
STATUS_STYLE = {  # (fg, bg)
    "完成": (C["green"], C["green_soft"]), "完成 · 测试未全过": (C["amber"], C["amber_soft"]), "成立": (C["green"], C["green_soft"]), "已核实": (C["green"], C["green_soft"]),
    "运行中": (C["blue"], C["blue_soft"]), "排队中": (C["text2"], C["gray_soft"]), "待验证": (C["amber"], C["amber_soft"]),
    "被拦下": (C["amber"], C["amber_soft"]), "预算用完": (C["amber"], C["amber_soft"]), "无进展已停止": (C["amber"], C["amber_soft"]),
    "中断": (C["amber"], C["amber_soft"]), "证据不足": (C["amber"], C["amber_soft"]), "需要重新验证": (C["amber"], C["amber_soft"]),
    "失败": (C["red"], C["red_soft"]), "被推翻": (C["red"], C["red_soft"]), "反例": (C["red"], C["red_soft"]),
    "已取消": (C["text2"], C["gray_soft"]), "已撤回": (C["text2"], C["gray_soft"]), "已被取代": (C["text2"], C["gray_soft"]),
    "高": (C["red"], C["red_soft"]), "中": (C["amber"], C["amber_soft"]), "低": (C["text2"], C["gray_soft"]),
}

_PRIMARY = "#0d0d0d"
_PRIMARY_HOVER = "#2f2f2f"


def qss() -> str:
    """The sheet with the user's size and roundness applied."""
    text = _sheet()
    if _look["font"] != 1.0:
        text = re.sub(r"font-size: (\d+)px", lambda m: f"font-size: {round(int(m.group(1)) * _look['font'])}px", text)
    if _look["radius"] != 1.0:
        text = re.sub(r"(border-[a-z-]*radius): (\d+)px", lambda m: f"{m.group(1)}: {round(int(m.group(2)) * _look['radius'])}px", text)
    return text


def _sheet() -> str:
    return f"""
    * {{ font-family: "{FONT_FAMILY}"; color: {C['text']}; }}
    QMainWindow, #Main {{ background: {C['bg']}; }}
    QLabel {{ background: transparent; }}
    #Sidebar {{ background: transparent; }}
    #Rail {{ background: {C['rail']}; border-right: 1px solid {C['border']}; }}
    #ChatPanel {{ background: {C['rail']}; border-right: 1px solid {C['border']}; }}
    #PluginCard {{ background: #ffffff; border: 1px solid {C['border']}; border-radius: 16px; }}
    #PluginCard:hover {{ border-color: {C['border_strong']}; background: {C['sidebar']}; }}
    #ChatSearch {{ background: #ffffff; border: 1px solid {C['border']}; border-radius: 12px; padding: 7px 12px; font-size: 13px; }}
    #RightDock {{ background: {C['bg']}; border-left: 1px solid {C['border']}; }}
    #HubNav {{ background: {C['rail']}; border-right: 1px solid {C['border']}; }}
    QSplitter::handle {{ background: {C['border']}; }}
    #Brand {{ font-size: 16px; font-weight: 700; color: {C['ink']}; }}
    #BrandSub {{ color: {C['text3']}; font-size: 10px; font-weight: 600; letter-spacing: 1px; }}
    QPushButton#Nav {{ text-align: left; padding: 9px 12px; border: none; border-radius: 13px; font-size: 14px;
                       background: transparent; color: {C['text2']}; }}
    QPushButton#Nav:hover {{ background: {C['sidebar_hover']}; color: {C['text']}; }}
    QPushButton#Nav:checked {{ background: {C['sidebar_sel']}; color: {C['ink']}; font-weight: 600; }}
    #SectionLabel {{ color: {C['text3']}; font-size: 12px; padding: 6px 12px 2px 12px; }}
    #NavSection {{ color: {C['text3']}; font-size: 11px; font-weight: 600; padding: 12px 12px 3px 12px; letter-spacing: 1px; }}
    QPushButton#NewTask {{ text-align: left; padding: 9px 12px; border: 1px solid {GLASS_RIM}; border-radius: 12px;
                           background: {GLASS}; font-size: 14px; font-weight: 600; color: {C['accent_hover']}; }}
    QPushButton#NewTask:hover {{ background: {GLASS_STRONG}; }}
    QPushButton#NewTask:checked {{ background: {GLASS_STRONG}; border-color: rgba(47,107,255,110); }}
    QPushButton#ProjectSwitch {{ text-align: left; background: transparent; border: 1px solid transparent; border-radius: 12px; }}
    QPushButton#ProjectSwitch:hover {{ background: {GLASS_HOVER}; border-color: {GLASS_RIM}; }}
    QPushButton#IconBtn {{ background: transparent; border: none; border-radius: 7px; padding: 4px; }}
    QPushButton#IconBtn:hover {{ background: {GLASS_HOVER}; }}
    QMenu {{ background: #f8fafd; border: 1px solid rgba(150,170,200,90); border-radius: 10px; padding: 6px; }}
    QMenu::item {{ padding: 7px 18px 7px 10px; border-radius: 7px; font-size: 13px; }}
    QMenu::item:selected {{ background: rgba(47,107,255,26); color: {C['ink']}; }}
    QMenu::item:disabled {{ color: {C['text2']}; }}
    QMenu::separator {{ height: 1px; background: {HAIRLINE}; margin: 5px 6px; }}
    QPushButton#Tab {{ border: none; border-bottom: 2px solid transparent; background: transparent; padding: 8px 4px;
                       margin-right: 18px; font-size: 14px; color: {C['text2']}; }}
    QPushButton#Tab:hover {{ color: {C['ink']}; }}
    QPushButton#Tab:checked {{ color: {C['ink']}; border-bottom-color: {C['accent']}; font-weight: 700; }}
    #PageSub {{ color: {C['text2']}; font-size: 13px; }}
    QListWidget {{ background: transparent; border: none; outline: none; }}
    QListWidget#TaskList {{ background: transparent; border: none; outline: none; font-size: 13px; }}
    QListWidget#TaskList::item {{ padding: 7px 10px; border-radius: 9px; margin: 1px 4px; color: {C['text']}; }}
    QListWidget#TaskList::item:hover {{ background: {GLASS_HOVER}; }}
    QListWidget#TaskList::item:selected {{ background: {GLASS_SEL}; color: {C['ink']}; }}
    QLineEdit#Search {{ background: {GLASS_STRONG}; border: 1px solid {GLASS_RIM}; border-radius: 10px; padding: 6px 10px;
                        margin: 0 8px; font-size: 13px; }}
    #ProjectCard {{ background: {GLASS}; border: 1px solid {GLASS_RIM}; border-radius: 12px; }}
    #Muted {{ color: {C['text2']}; }}
    #Faint {{ color: {C['text3']}; font-size: 12px; }}
    #Greeting {{ font-size: 28px; font-weight: 600; color: {C['ink']}; }}
    #PageTitle {{ font-size: 24px; font-weight: 700; color: {C['ink']}; }}
    #TaskTitle {{ font-size: 15px; font-weight: 600; color: {C['ink']}; }}
    #Composer {{ background: #ffffff; border: 1px solid {C['border_strong']}; border-radius: 26px; }}
    QPushButton#FileChip {{ background: #f1f2f4; border: none; border-radius: 12px; padding: 5px 12px; font-size: 13px;
                            color: #1f2329; }}
    QPushButton#FileChip:hover {{ background: #e8e9ec; }}
    QPlainTextEdit#ComposerEdit {{ background: transparent; border: none; font-size: 15px; padding: 2px; }}
    QPushButton#Send {{ background: {C['accent']}; color: white; border: none; border-radius: 17px;
                        font-size: 17px; font-weight: 700; min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; }}
    QPushButton#Send:hover {{ background: {C['accent_hover']}; }}
    QPushButton#Send:disabled {{ background: #b9cdfb; }}
    QPushButton#Pill {{ border: 1px solid {GLASS_RIM}; background: {GLASS_SOFT}; padding: 5px 12px; font-size: 13px;
                        border-radius: 14px; color: {C['text2']}; }}
    QPushButton#Pill:hover {{ background: {GLASS_STRONG}; color: {C['text']}; }}
    QPushButton#Pill::menu-indicator {{ width: 0; }}
    QPushButton#Pill:checked {{ background: rgba(47,107,255,40); color: {C['accent_hover']}; border-color: rgba(47,107,255,110);
                                font-weight: 600; }}
    QPushButton#ModelPill {{ border: none; background: transparent; padding: 5px 10px; font-size: 13px; border-radius: 12px;
                             color: {C['text2']}; }}
    QPushButton#ModelPill:hover {{ background: {GLASS_STRONG}; color: {C['text']}; }}
    QSlider#ThinkSlider::groove:horizontal {{ height: 6px; background: rgba(16,27,42,30); border-radius: 3px; }}
    QSlider#ThinkSlider::sub-page:horizontal {{ background: {C['blue']}; border-radius: 3px; }}
    QSlider#ThinkSlider::handle:horizontal {{ width: 22px; height: 22px; margin: -9px 0; border-radius: 11px;
                                              background: white; border: 1px solid rgba(16,27,42,40); }}
    QMenu {{ background: #ffffff; border: 1px solid {C['border']}; border-radius: 14px; padding: 6px; }}
    QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 8px; color: {C['text']}; font-size: 13px; }}
    QMenu::item:selected {{ background: {C['sidebar_hover']}; }}
    QMenu::item:disabled {{ color: {C['text3']}; }}
    QMenu::separator {{ height: 1px; background: rgba(16,27,42,22); margin: 4px 8px; }}
    QPushButton#Seg {{ border: 1px solid {GLASS_RIM}; background: {GLASS_SOFT}; padding: 5px 12px; font-size: 13px;
                       color: {C['text2']}; }}
    QPushButton#Seg:checked {{ background: {GLASS_STRONG}; color: {C['accent_hover']}; border-color: rgba(47,107,255,90);
                               font-weight: 600; }}
    QPushButton#SegL {{ border-top-left-radius: 14px; border-bottom-left-radius: 14px; }}
    QPushButton#Chip, QPushButton#Suggestion {{ background: {GLASS_SOFT}; border: 1px solid {GLASS_RIM}; border-radius: 16px;
                        padding: 7px 14px; font-size: 13px; color: {C['text2']}; }}
    QPushButton#Suggestion:hover {{ background: {GLASS_STRONG}; color: {C['ink']}; }}
    QPushButton#Ghost {{ background: {GLASS_SOFT}; border: 1px solid {GLASS_RIM}; border-radius: 14px; padding: 7px 15px;
                         font-size: 13px; }}
    QPushButton#Ghost:hover {{ background: {GLASS_STRONG}; }}
    QPushButton#Ghost:disabled {{ color: {C['text3']}; background: rgba(255,255,255,60); }}
    QPushButton#Primary {{ background: {_PRIMARY}; color: white; border: none; border-radius: 14px;
                           padding: 8px 18px; font-size: 13px; font-weight: 600; }}
    QPushButton#Primary:hover {{ background: {_PRIMARY_HOVER}; }}
    QPushButton#Primary:disabled {{ background: rgba(150,164,186,110); border-color: rgba(255,255,255,80); }}
    QPushButton#Link {{ background: transparent; border: none; color: {C['accent_hover']}; font-size: 13px; text-align: left; padding: 2px 0; }}
    QPushButton#Link:hover {{ color: {C['ink']}; }}
    #Card {{ background: {GLASS}; border: 1px solid {GLASS_RIM}; border-radius: 20px; }}
    #StepRow {{ border-radius: 8px; }}
    #StepRow:hover {{ background: {GLASS_HOVER}; }}
    #Detail {{ background: rgba(255,255,255,190); border: 1px solid {GLASS_RIM}; border-radius: 10px; }}
    #UserBubble {{ background: {C['user_bubble']}; border: none; border-radius: 22px; }}
    #Banner {{ background: #fdf6e9; border: 1px solid #f0dfba; border-radius: 12px; }}
    #Danger {{ background: #fdeeed; border: 1px solid #f2cdc9; border-radius: 12px; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 1px; }}
    QScrollBar::handle:vertical {{ background: #d9d9d9; border-radius: 3px; min-height: 40px; }}
    QScrollBar::handle:vertical:hover {{ background: #bdbdbd; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{ height: 0; }}
    QComboBox {{ background: {GLASS_STRONG}; border: 1px solid {GLASS_RIM}; border-radius: 12px; padding: 6px 12px; }}
    QComboBox:hover {{ background: rgba(255,255,255,230); }}
    QComboBox:focus {{ border-color: rgba(47,107,255,140); }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: #f8fafd; border: 1px solid rgba(150,170,200,90); border-radius: 10px;
                                   padding: 4px; selection-background-color: rgba(47,107,255,30); selection-color: {C['ink']};
                                   outline: none; }}
    QLineEdit {{ background: {GLASS_STRONG}; border: 1px solid {GLASS_RIM}; border-radius: 12px; padding: 7px 12px; font-size: 13px;
                 selection-background-color: #bcd3f2; selection-color: {C['ink']}; }}
    QLineEdit:focus {{ border-color: #8f8f8f; background: #ffffff; }}
    QSpinBox {{ background: #ffffff; border: 1px solid {GLASS_RIM}; border-radius: 12px; padding: 6px 10px; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; }}
    QCheckBox {{ spacing: 8px; background: transparent; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; background: #ffffff; border: 1px solid #c9c9c9; }}
    QCheckBox::indicator:hover {{ border-color: #8f8f8f; }}
    QCheckBox::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}
    QRadioButton {{ spacing: 8px; background: transparent; }}
    QDialog {{ background: #ffffff; }}
    QDialog QPushButton {{ background: #ffffff; border: 1px solid {C['border_strong']}; border-radius: 12px;
                           padding: 6px 18px; min-width: 56px; }}
    QDialog QPushButton:hover {{ background: {C['sidebar_hover']}; }}
    QDialog QPushButton#Primary {{ background: {_PRIMARY}; color: white; border: none; }}
    QDialog QPushButton#Primary:hover {{ background: {_PRIMARY_HOVER}; }}
    QDialog QLineEdit, QDialog QComboBox, QDialog QPlainTextEdit {{ background: #ffffff; border: 1px solid {C['border']}; }}
    QMessageBox {{ background: #ffffff; }}
    QPlainTextEdit {{ background: {GLASS_STRONG}; border: 1px solid {GLASS_RIM}; border-radius: 10px; padding: 4px 6px; }}
    QTextBrowser {{ selection-background-color: #bcd3f2; }}
    QToolTip {{ background: #1f1f1f; color: #f5f5f5; border: none; padding: 6px 9px; border-radius: 7px; }}
    QGraphicsView {{ background: rgba(255,255,255,175); border: 1px solid {GLASS_RIM}; border-radius: 16px; }}
    QProgressBar {{ background: rgba(255,255,255,120); border: none; border-radius: 3px; }}
    QProgressBar::chunk {{ background: {C['accent']}; border-radius: 3px; }}
    QTabWidget::pane {{ background: transparent; border: none; }}
    QTabBar::tab {{ background: transparent; border: none; padding: 8px 14px; color: {C['text2']}; }}
    QTabBar::tab:selected {{ color: {C['ink']}; border-bottom: 2px solid {C['accent']}; font-weight: 600; }}
    """
