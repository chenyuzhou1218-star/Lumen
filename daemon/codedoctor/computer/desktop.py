"""The desktop an agent can see and act on (ADR 0012).

`WindowsDesktop` talks to Windows through ctypes (no extra dependency besides Pillow for images).
`FakeDesktop` is an in-memory desktop for tests: nothing in the test suite ever moves the real
mouse or presses a real key.

This layer only performs what it is told. Whether an action is allowed - which window, which
program, who approved it - is decided by the gate (computer/gate.py) before anything here runs.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Callable, Protocol

from PIL import Image, ImageDraw

Rect = tuple[int, int, int, int]  # left, top, right, bottom in virtual-screen pixels

# Key names agents may use. The Windows key is deliberately absent: its shortcuts act on the whole system.
VK = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
      "esc": 0x1B, "escape": 0x1B, "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "home": 0x24,
      "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
      "space": 0x20, **{f"f{i}": 0x6F + i for i in range(1, 25)},
      **{chr(c): ord(chr(c).upper()) for c in range(ord("a"), ord("z") + 1)}, **{str(d): ord(str(d)) for d in range(10)}}
_EXTENDED = {0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x26, 0x28, 0x25, 0x27}


@dataclass(frozen=True)
class Window:
    handle: int
    title: str
    pid: int
    rect: Rect
    minimized: bool = False

    def contains(self, x: int, y: int) -> bool:
        left, top, right, bottom = self.rect
        return left <= x < right and top <= y < bottom


class Desktop(Protocol):
    def windows(self, minimized: bool = False) -> list[Window]: ...  # top-level windows with a title, topmost first
    def restore(self, handle: int) -> None: ...      # a minimized window back, without taking the focus
    def foreground(self) -> int | None: ...
    def root_at(self, x: int, y: int) -> int | None: ...  # top-level window under a point
    def screen_rect(self) -> Rect: ...
    def capture(self, rect: Rect) -> Image.Image: ...
    def capture_window(self, handle: int) -> Image.Image | None: ...  # the window's own picture, even when covered
    def cursor(self) -> tuple[int, int]: ...
    def focus(self, handle: int) -> bool: ...
    def move(self, x: int, y: int) -> None: ...
    def click(self, x: int, y: int, button: str, count: int) -> None: ...
    def type_text(self, text: str) -> None: ...
    def press(self, keys: list[str]) -> None: ...
    def look(self, dx: int, dy: int) -> None: ...      # relative mouse move (turns a game's camera)
    def hold(self, keys: list[str], seconds: float) -> None: ...
    def mouse_hold(self, button: str, seconds: float) -> None: ...
    def launch(self, path: str, args: list[str], cwd: str | None) -> int: ...
    def close(self, pid: int, force: bool) -> bool: ...
    def running(self, pid: int) -> bool: ...
    def watch_stop_hotkey(self, on_stop: Callable[[], None]) -> None: ...
    def shutdown(self) -> None: ...


# --- in-memory desktop for tests -------------------------------------------------------------------

@dataclass
class FakeDesktop:
    """Windows are drawn as coloured rectangles; every input is recorded in `log`."""
    wins: list[Window] = field(default_factory=list)  # topmost first
    fg: int | None = None
    log: list[tuple] = field(default_factory=list)
    screen: Rect = (0, 0, 1920, 1080)
    pos: tuple[int, int] = (960, 540)
    procs: dict[int, bool] = field(default_factory=dict)
    next_pid: int = 4000
    own_picture: bool = True   # False: like a program that does not draw itself for PrintWindow
    focus_works: bool = True   # False: like Windows refusing to change the foreground

    def windows(self, minimized: bool = False) -> list[Window]:
        return [w for w in self.wins if minimized or not w.minimized]

    def restore(self, handle: int) -> None:
        self.wins = [replace(w, minimized=False) if w.handle == handle else w for w in self.wins]
        self.log.append(("restore", handle))

    def foreground(self) -> int | None:
        return self.fg

    def root_at(self, x: int, y: int) -> int | None:
        return next((w.handle for w in self.windows() if w.contains(x, y)), None)

    def screen_rect(self) -> Rect:
        return self.screen

    def capture(self, rect: Rect) -> Image.Image:
        left, top, right, bottom = rect
        img = Image.new("RGB", (right - left, bottom - top), "#202020")
        draw = ImageDraw.Draw(img)
        for i, w in enumerate(reversed(self.windows())):
            colour = ("#4a7", "#a74", "#47a", "#a4a")[i % 4]
            draw.rectangle([w.rect[0] - left, w.rect[1] - top, w.rect[2] - left - 1, w.rect[3] - top - 1], fill=colour)
        return img

    def capture_window(self, handle: int) -> Image.Image | None:
        w = next((w for w in self.windows() if w.handle == handle), None)
        if w is None or not self.own_picture:
            return None
        return Image.new("RGB", (w.rect[2] - w.rect[0], w.rect[3] - w.rect[1]), "#4a7")  # its own colour only

    def cursor(self) -> tuple[int, int]:
        return self.pos

    def focus(self, handle: int) -> bool:
        if not self.focus_works:
            return False
        self.restore(handle)
        self.fg = handle
        self.wins.sort(key=lambda w: w.handle != handle)  # brought to the top of the z-order
        self.log.append(("focus", handle))
        return True

    def move(self, x: int, y: int) -> None:
        self.pos = (x, y)
        self.log.append(("move", x, y))

    def click(self, x: int, y: int, button: str, count: int) -> None:
        self.pos = (x, y)
        self.log.append(("click", x, y, button, count))

    def type_text(self, text: str) -> None:
        self.log.append(("type", text))

    def press(self, keys: list[str]) -> None:
        self.log.append(("press", tuple(keys)))

    def look(self, dx: int, dy: int) -> None:
        self.log.append(("look", dx, dy))

    def hold(self, keys: list[str], seconds: float) -> None:
        self.log.append(("hold", tuple(keys), seconds))

    def mouse_hold(self, button: str, seconds: float) -> None:
        self.log.append(("mouse_hold", button, seconds))

    def post_click(self, handle: int, x: int, y: int, button: str, count: int) -> None:
        self.log.append(("post_click", handle, x, y, button, count))

    def post_text(self, handle: int, text: str) -> None:
        self.log.append(("post_text", handle, text))

    def post_keys(self, handle: int, keys: list[str]) -> None:
        self.log.append(("post_keys", handle, tuple(keys)))

    def launch(self, path: str, args: list[str], cwd: str | None, quiet: bool = False) -> int:
        self.next_pid += 1
        self.procs[self.next_pid] = True
        self.log.append(("launch", path, tuple(args), cwd))
        return self.next_pid

    def close(self, pid: int, force: bool) -> bool:
        self.log.append(("close", pid, force))
        self.procs[pid] = False
        return True

    def running(self, pid: int) -> bool:
        return self.procs.get(pid, False)

    def watch_stop_hotkey(self, on_stop: Callable[[], None]) -> None:
        self.on_stop = on_stop

    def shutdown(self) -> None:
        pass


# --- Windows ----------------------------------------------------------------------------------------

class WindowsDesktop:
    """Win32 through ctypes. Coordinates are physical virtual-screen pixels (the process is made DPI aware)."""

    STOP_HOTKEY = "Ctrl+Alt+End"

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("computer use is only implemented for Windows")
        from ctypes import wintypes

        self.w = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.dwm = ctypes.WinDLL("dwmapi")
        self.kernel32 = ctypes.WinDLL("kernel32")
        try:  # per-monitor DPI awareness v2, so window rects, captures and cursor positions agree
            self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass
        self._procs: dict[int, subprocess.Popen] = {}
        self._hotkey_thread: int | None = None
        self.user32.WindowFromPoint.argtypes = [wintypes.POINT]
        self.user32.WindowFromPoint.restype = wintypes.HWND
        self.user32.GetAncestor.restype = wintypes.HWND
        self.user32.GetForegroundWindow.restype = wintypes.HWND

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self.INPUT, self.MOUSEINPUT, self.KEYBDINPUT = INPUT, MOUSEINPUT, KEYBDINPUT

    # --- reading ---------------------------------------------------------------------------------

    def _rect(self, hwnd) -> Rect:
        r = self.w.RECT()
        if self.dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:  # extended frame bounds
            self.user32.GetWindowRect(hwnd, ctypes.byref(r))
        return r.left, r.top, r.right, r.bottom

    def restore(self, handle: int) -> None:
        if self.user32.IsIconic(handle):
            self.user32.ShowWindow(handle, 4)  # SW_SHOWNOACTIVATE
            time.sleep(0.3)

    def windows(self, minimized: bool = False) -> list[Window]:
        out: list[Window] = []
        proto = ctypes.WINFUNCTYPE(self.w.BOOL, self.w.HWND, self.w.LPARAM)

        def visit(hwnd, _):
            if not self.user32.IsWindowVisible(hwnd):
                return True
            n = self.user32.GetWindowTextLengthW(hwnd)
            if n == 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            self.user32.GetWindowTextW(hwnd, buf, n + 1)
            pid = self.w.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append(Window(int(hwnd), buf.value, pid.value, self._rect(hwnd), bool(self.user32.IsIconic(hwnd))))
            return True

        self.user32.EnumWindows(proto(visit), 0)  # z-order, topmost first
        return [w for w in out if minimized or not w.minimized]

    def foreground(self) -> int | None:
        h = self.user32.GetForegroundWindow()
        return int(h) if h else None

    def root_at(self, x: int, y: int) -> int | None:
        h = self.user32.WindowFromPoint(self.w.POINT(x, y))
        if not h:
            return None
        root = self.user32.GetAncestor(h, 2)  # GA_ROOT
        return int(root or h)

    def screen_rect(self) -> Rect:
        gm = self.user32.GetSystemMetrics
        left, top = gm(76), gm(77)
        return left, top, left + gm(78), top + gm(79)

    def capture(self, rect: Rect) -> Image.Image:
        from PIL import ImageGrab

        return ImageGrab.grab(bbox=rect, all_screens=True).convert("RGB")

    def capture_window(self, handle: int) -> Image.Image | None:
        """The window's own picture via PrintWindow (PW_RENDERFULLCONTENT): what covers it is never in it. None when
        the window cannot draw itself this way (some GPU-drawn programs give a black picture)."""
        w = self.w
        gdi = ctypes.WinDLL("gdi32")
        u = self.user32
        for f, res, args in ((u.GetWindowDC, w.HDC, [w.HWND]), (u.ReleaseDC, ctypes.c_int, [w.HWND, w.HDC]),
                             (u.PrintWindow, w.BOOL, [w.HWND, w.HDC, w.UINT]),
                             (gdi.CreateCompatibleDC, w.HDC, [w.HDC]), (gdi.CreateCompatibleBitmap, w.HBITMAP, [w.HDC, ctypes.c_int, ctypes.c_int]),
                             (gdi.SelectObject, w.HGDIOBJ, [w.HDC, w.HGDIOBJ]), (gdi.DeleteObject, w.BOOL, [w.HGDIOBJ]),
                             (gdi.DeleteDC, w.BOOL, [w.HDC])):
            f.restype, f.argtypes = res, args
        wr = w.RECT()
        u.GetWindowRect(handle, ctypes.byref(wr))
        width, height = wr.right - wr.left, wr.bottom - wr.top
        if width <= 0 or height <= 0:
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                        ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                        ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                        ("biClrImportant", w.DWORD)]

        wdc = u.GetWindowDC(handle)
        mdc = gdi.CreateCompatibleDC(wdc)
        bmp = gdi.CreateCompatibleBitmap(wdc, width, height)
        old = gdi.SelectObject(mdc, bmp)
        try:
            ok = u.PrintWindow(handle, mdc, 2)
            info = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=width, biHeight=-height, biPlanes=1,
                                    biBitCount=32, biCompression=0)
            buf = ctypes.create_string_buffer(width * height * 4)
            gdi.GetDIBits(ctypes.c_void_p(mdc), ctypes.c_void_p(bmp), 0, height, buf, ctypes.byref(info), 0)
        finally:
            gdi.SelectObject(mdc, old)
            gdi.DeleteObject(bmp)
            gdi.DeleteDC(mdc)
            u.ReleaseDC(handle, wdc)
        if not ok:
            return None
        img = Image.frombuffer("RGB", (width, height), buf, "raw", "BGRX", 0, 1)
        left, top, right, bottom = self._rect(handle)  # without the invisible resize borders
        img = img.crop((left - wr.left, top - wr.top, right - wr.left, bottom - wr.top))
        if max(hi for _, hi in img.getextrema()) == 0:
            return None  # all black: this program does not draw itself for PrintWindow
        return img

    def cursor(self) -> tuple[int, int]:
        p = self.w.POINT()
        self.user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y

    # --- acting ----------------------------------------------------------------------------------

    def focus(self, handle: int) -> bool:
        """Bring the window to the front. Windows refuses SetForegroundWindow to a background process (real Notepad
        test: a browser stayed in front), so this process attaches its input to the foreground thread first."""
        if self.foreground() == handle:
            return True
        u = self.user32
        if u.IsIconic(handle):
            u.ShowWindow(handle, 9)  # SW_RESTORE
        me = self.kernel32.GetCurrentThreadId()
        threads = {u.GetWindowThreadProcessId(self.user32.GetForegroundWindow(), None), u.GetWindowThreadProcessId(handle, None)}
        attached = [t for t in threads - {0, me} if u.AttachThreadInput(me, t, True)]
        try:
            u.BringWindowToTop(handle)
            u.SetForegroundWindow(handle)
        finally:
            for t in attached:
                u.AttachThreadInput(me, t, False)
        if self.foreground() != handle:
            u.SwitchToThisWindow(handle, True)
        for _ in range(10):
            if self.foreground() == handle:
                return True
            time.sleep(0.05)
        return False

    def _send(self, inputs: list) -> None:
        arr = (self.INPUT * len(inputs))(*inputs)
        sent = self.user32.SendInput(len(inputs), arr, ctypes.sizeof(self.INPUT))
        if sent != len(inputs):
            raise OSError(f"SendInput delivered {sent} of {len(inputs)} events (another program may block input)")

    def _mouse(self, flags: int) -> object:
        i = self.INPUT(type=0)
        i.u.mi = self.MOUSEINPUT(0, 0, 0, flags, 0, 0)
        return i

    def _key(self, vk: int = 0, scan: int = 0, flags: int = 0) -> object:
        i = self.INPUT(type=1)
        i.u.ki = self.KEYBDINPUT(vk, scan, flags, 0, 0)
        return i

    def move(self, x: int, y: int) -> None:
        if not self.user32.SetCursorPos(x, y):
            raise OSError("SetCursorPos failed")

    def click(self, x: int, y: int, button: str, count: int) -> None:
        down, up = {"left": (0x02, 0x04), "right": (0x08, 0x10), "middle": (0x20, 0x40)}[button]
        self.move(x, y)
        self._send([e for _ in range(count) for e in (self._mouse(down), self._mouse(up))])

    def type_text(self, text: str) -> None:
        events = []
        for ch in text:
            if ch == "\n":
                events += [self._key(0x0D), self._key(0x0D, flags=0x2)]
                continue
            data = ch.encode("utf-16-le")
            for k in range(0, len(data), 2):  # one event pair per UTF-16 code unit (surrogate pairs too)
                unit = int.from_bytes(data[k:k + 2], "little")
                events += [self._key(scan=unit, flags=0x4), self._key(scan=unit, flags=0x4 | 0x2)]
        if events:
            self._send(events)

    def press(self, keys: list[str]) -> None:
        codes = [VK[k] for k in keys]
        ext = lambda vk: 0x1 if vk in _EXTENDED else 0  # noqa: E731
        self._send([self._key(vk, flags=ext(vk)) for vk in codes] +
                   [self._key(vk, flags=0x2 | ext(vk)) for vk in reversed(codes)])

    def look(self, dx: int, dy: int) -> None:
        """A relative mouse move, as a hand moves it: games that hold the cursor (Minecraft) turn the camera by these
        raw deltas; an absolute move would do nothing there. Sent in small steps so the turn is smooth."""
        steps = max(1, min(40, int(max(abs(dx), abs(dy)) / 20)))
        done_x = done_y = 0
        for i in range(1, steps + 1):
            tx, ty = round(dx * i / steps), round(dy * i / steps)
            i_ = self.INPUT(type=0)
            i_.u.mi = self.MOUSEINPUT(tx - done_x, ty - done_y, 0, 0x0001, 0, 0)  # MOUSEEVENTF_MOVE, relative
            self._send([i_])
            done_x, done_y = tx, ty
            time.sleep(0.008)

    def hold(self, keys: list[str], seconds: float) -> None:
        """Keys down together for a while, then up (walk forward: W for 1.5 s)."""
        codes = [VK[k] for k in keys]
        ext = lambda vk: 0x1 if vk in _EXTENDED else 0  # noqa: E731
        self._send([self._key(vk, flags=ext(vk)) for vk in codes])
        try:
            time.sleep(seconds)
        finally:
            self._send([self._key(vk, flags=0x2 | ext(vk)) for vk in reversed(codes)])

    def mouse_hold(self, button: str, seconds: float) -> None:
        """A mouse button held where the cursor is (break a block in Minecraft: left for a few seconds)."""
        down, up = {"left": (0x02, 0x04), "right": (0x08, 0x10), "middle": (0x20, 0x40)}[button]
        self._send([self._mouse(down)])
        try:
            time.sleep(seconds)
        finally:
            self._send([self._mouse(up)])

    # --- in the window itself: the user's mouse, keyboard and front window are not touched ---------------------------

    def _post_setup(self) -> None:
        if getattr(self, "_posting", False):
            return
        w = self.w
        u = self.user32
        u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        u.PostMessageW.restype = w.BOOL
        u.ScreenToClient.argtypes = [w.HWND, ctypes.POINTER(w.POINT)]
        u.RealChildWindowFromPoint.argtypes = [w.HWND, w.POINT]
        u.RealChildWindowFromPoint.restype = w.HWND
        u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        self._posting = True

    def _deepest(self, handle: int, x: int, y: int) -> tuple[object, int, int]:
        """(the innermost child window at a point of the window's own picture, as a screen point, and that point in the
        child's client coordinates). An old program is not scaled for this screen: its picture (PrintWindow) is in its
        own pixels, so everything here is worked out in its own coordinates - on a 125% screen they differ from the
        screen's, and a click on a button landed beside it."""
        self._post_setup()
        u, w = self.user32, self.w
        left, top, _, _ = self._rect(handle)
        outer = w.RECT()
        u.GetWindowRect(handle, ctypes.byref(outer))
        ox, oy = x - outer.left, y - outer.top  # in the picture before its invisible borders were cut off: same origin
        u.GetWindowDpiAwarenessContext.argtypes = [w.HWND]
        u.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
        u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        before = u.SetThreadDpiAwarenessContext(u.GetWindowDpiAwarenessContext(handle))
        try:
            own = w.RECT()
            u.GetWindowRect(handle, ctypes.byref(own))
            sx, sy = own.left + ox, own.top + oy
            hwnd = handle
            while True:
                pt = w.POINT(sx, sy)
                u.ScreenToClient(hwnd, ctypes.byref(pt))
                child = u.RealChildWindowFromPoint(hwnd, pt)
                if not child or int(child) == int(hwnd):
                    return hwnd, pt.x, pt.y
                hwnd = child
        finally:
            u.SetThreadDpiAwarenessContext(before)

    def _focused(self, handle: int) -> object:
        """The control that has the keyboard inside that window's thread, without activating it."""
        self._post_setup()
        w = self.w

        class GUITHREADINFO(ctypes.Structure):
            _fields_ = [("cbSize", w.DWORD), ("flags", w.DWORD), ("hwndActive", w.HWND), ("hwndFocus", w.HWND),
                        ("hwndCapture", w.HWND), ("hwndMenuOwner", w.HWND), ("hwndMoveSize", w.HWND),
                        ("hwndCaret", w.HWND), ("rcCaret", w.RECT)]

        info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        thread = self.user32.GetWindowThreadProcessId(handle, None)
        if thread and self.user32.GetGUIThreadInfo(thread, ctypes.byref(info)) and info.hwndFocus:
            return info.hwndFocus
        clicked = self.__dict__.setdefault("_clicked", {}).get(handle)  # a window behind others names no focus
        if clicked is not None and self.user32.IsWindow(clicked):
            return clicked
        return self._text_field(handle) or handle

    def _text_field(self, handle: int) -> object | None:
        """The window's first text control, for typing before any click."""
        w = self.w
        found: list = []
        proto = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

        def visit(hwnd, _):
            name = ctypes.create_unicode_buffer(128)
            self.user32.GetClassNameW(hwnd, name, 128)
            if "edit" in name.value.lower():
                found.append(hwnd)
                return False
            return True

        self.user32.EnumChildWindows.argtypes = [w.HWND, proto, w.LPARAM]
        self.user32.EnumChildWindows(handle, proto(visit), 0)
        return found[0] if found else None

    def _post(self, hwnd, msg: int, wparam: int, lparam: int) -> None:
        if not self.user32.PostMessageW(hwnd, msg, wparam, lparam):
            raise OSError(f"the window did not take the message (error {ctypes.get_last_error()})")

    def post_click(self, handle: int, x: int, y: int, button: str, count: int) -> None:
        down, up, dbl, mk = {"left": (0x0201, 0x0202, 0x0203, 1), "right": (0x0204, 0x0205, 0x0206, 2),
                             "middle": (0x0207, 0x0208, 0x0209, 16)}[button]
        hwnd, cx, cy = self._deepest(handle, x, y)
        self.__dict__.setdefault("_clicked", {})[handle] = hwnd
        name = ctypes.create_unicode_buffer(128)
        self.user32.GetClassNameW(hwnd, name, 128)
        if "button" in name.value.lower() and button == "left" and count == 1:
            self._post(hwnd, 0x00F5, 0, 0)  # BM_CLICK: a button needs the mouse captured, which only the front window gets
            time.sleep(0.05)
            return
        at = (cy & 0xFFFF) << 16 | (cx & 0xFFFF)
        self._post(hwnd, 0x0200, 0, at)  # WM_MOUSEMOVE
        self._post(hwnd, down, mk, at)
        self._post(hwnd, up, 0, at)
        if count > 1:
            self._post(hwnd, dbl, mk, at)
            self._post(hwnd, up, 0, at)
        time.sleep(0.05)

    def post_text(self, handle: int, text: str) -> None:
        target = self._focused(handle)
        for unit in text.replace("\r\n", "\n").encode("utf-16-le"):
            pass
        raw = text.replace("\r\n", "\n").encode("utf-16-le")
        for i in range(0, len(raw), 2):
            code = int.from_bytes(raw[i:i + 2], "little")
            self._post(target, 0x0102, 13 if code == 10 else code, 1)  # WM_CHAR
            time.sleep(0.004)

    def post_keys(self, handle: int, keys: list[str]) -> None:
        """Single keys (Enter, Tab, arrows ...). A shortcut with Ctrl or Alt is refused by the gate: the modifier's state
        cannot be told to a window that is not in front."""
        target = self._focused(handle)
        for key in keys:
            vk = VK[key]
            self._post(target, 0x0100, vk, 1)  # WM_KEYDOWN
            self._post(target, 0x0101, vk, 0xC0000001)  # WM_KEYUP
            time.sleep(0.02)

    def launch(self, path: str, args: list[str], cwd: str | None, quiet: bool = False) -> int:
        info = None
        if quiet:  # not over what the user is doing
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = 4  # SW_SHOWNOACTIVATE
        proc = subprocess.Popen([path, *args], cwd=cwd, startupinfo=info)
        self._procs[proc.pid] = proc
        return proc.pid

    def close(self, pid: int, force: bool) -> bool:
        proc = self._procs.get(pid)
        if proc is None:
            return False
        if force:
            proc.terminate()
            return True
        closed = False
        for w in self.windows():
            if w.pid == pid:
                self.user32.PostMessageW(w.handle, 0x0010, 0, 0)  # WM_CLOSE: the program may still ask to save
                closed = True
        return closed

    def running(self, pid: int) -> bool:
        proc = self._procs.get(pid)
        return proc is not None and proc.poll() is None

    def watch_stop_hotkey(self, on_stop: Callable[[], None]) -> None:
        """Ctrl+Alt+End anywhere stops all computer use. Ignored if another program owns the hotkey."""
        def loop():
            self._hotkey_thread = self.kernel32.GetCurrentThreadId()
            if not self.user32.RegisterHotKey(None, 0xCD01, 0x0002 | 0x0001 | 0x4000, 0x23):  # ctrl+alt, no repeat, End
                return
            msg = self.w.MSG()
            while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312:  # WM_HOTKEY
                    on_stop()
            self.user32.UnregisterHotKey(None, 0xCD01)

        threading.Thread(target=loop, name="computer-stop-hotkey", daemon=True).start()

    def shutdown(self) -> None:
        if self._hotkey_thread:
            self.user32.PostThreadMessageW(self._hotkey_thread, 0x0012, 0, 0)  # WM_QUIT


def default_desktop() -> Desktop | None:
    return WindowsDesktop() if sys.platform == "win32" else None
