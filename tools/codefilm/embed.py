"""Inside Lumen (2026-11-10). Started with LUMEN_EMBED=1, the window never shows on the desktop by itself: it is made
frameless and off-screen, its handle is printed (LUMEN_HWND=...), and Lumen takes it into its own window, above the
chat (desktop/tool_view.py in Lumen). Without the variable, the window shows as always. The same file in every tool.

Lumen gives the tool whatever room the user leaves it, often less than the window's own layout needs. Qt then lays the
parts over each other (2026-11-12: CodeCut's 素材, 播放器 and 项目概览 overlapped in a short strip). So inside Lumen the
window's content sits in a scroll area: below the size it needs it scrolls, it never overlaps."""
import os
import sys


def _scrolls(win) -> None:
    """The main window's content in a scroll area that fills it and scrolls only when the room is too small."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFrame, QMainWindow, QScrollArea

    if not isinstance(win, QMainWindow) or win.centralWidget() is None:
        return
    body = win.takeCentralWidget()
    area = QScrollArea()
    area.setObjectName('LumenEmbedScroll')
    area.setFrameShape(QFrame.NoFrame)
    area.setWidgetResizable(True)  # as big as the room, never smaller than the content's own minimum
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.viewport().setAutoFillBackground(False)
    area.setWidget(body)
    win.setCentralWidget(area)
    win.setMinimumSize(0, 0)  # Lumen decides the size; the scroll area takes up what the content cannot


def show(win) -> None:
    try:  # the words of the window in Lumen's language (i18n.py + en.json, next to this file)
        import i18n
        i18n.apply(win)
    except ImportError:
        pass
    if os.environ.get('LUMEN_EMBED') != '1':
        win.show()
        return
    from PySide6.QtCore import Qt

    _scrolls(win)
    # Windows' own file dialog loads dozens of shell add-ins and, parented to a window that lives inside Lumen, makes
    # the whole thing flash and stall (CodePage 一键导出, 2026-11-13). Qt's own dialog stays inside this process.
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
    win.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
    win.setAttribute(Qt.WA_ShowWithoutActivating, True)
    win.move(-32000, -32000)
    win.show()
    out = sys.stdout or sys.__stdout__
    if out is not None:
        out.write(f'LUMEN_HWND={int(win.winId())}\n')
        out.flush()
