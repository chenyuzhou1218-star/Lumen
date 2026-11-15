"""A real console for the terminal on the right (Windows 10 1809 and later): the shell runs in a pseudo console (ConPTY), so
it behaves exactly as in Windows Terminal - its own banner and prompt, colours, Tab completion, the arrow keys, programs
that draw on the whole screen. What it writes is the console's own text with VT escape codes; the page draws it.

Only the Windows API through ctypes: nothing to install.
"""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
STILL_ACTIVE = 259
HPCON = wintypes.HANDLE


class COORD(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD), ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.POINTER(ctypes.c_byte)), ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
                ("hStdError", wintypes.HANDLE)]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


k32.CreatePseudoConsole.argtypes = [COORD, wintypes.HANDLE, wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(HPCON)]
k32.CreatePseudoConsole.restype = ctypes.c_long
k32.ResizePseudoConsole.argtypes = [HPCON, COORD]
k32.ResizePseudoConsole.restype = ctypes.c_long
k32.ClosePseudoConsole.argtypes = [HPCON]
k32.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p, wintypes.DWORD]
k32.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
k32.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_void_p, ctypes.c_void_p]
k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
k32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION)]
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def available() -> bool:
    return os.name == "nt" and hasattr(k32, "CreatePseudoConsole")


class Pty:
    """One shell in a pseudo console. on_output(text) is called from a reading thread; on_exit() when the shell ends."""

    def __init__(self, command: str, cwd: str, cols: int = 100, rows: int = 30, on_output=None, on_exit=None):
        self.on_output, self.on_exit = on_output, on_exit
        self.size = (max(20, cols), max(5, rows))
        self.hpc = HPCON()
        self.pi = PROCESS_INFORMATION()
        self.alive = False
        in_read, self.in_write = wintypes.HANDLE(), wintypes.HANDLE()
        self.out_read, out_write = wintypes.HANDLE(), wintypes.HANDLE()
        if not k32.CreatePipe(ctypes.byref(in_read), ctypes.byref(self.in_write), None, 0) or \
                not k32.CreatePipe(ctypes.byref(self.out_read), ctypes.byref(out_write), None, 0):
            raise OSError(ctypes.get_last_error(), "CreatePipe")
        hr = k32.CreatePseudoConsole(COORD(*self.size), in_read, out_write, 0, ctypes.byref(self.hpc))
        if hr != 0:
            raise OSError(hr, "CreatePseudoConsole")
        size = ctypes.c_size_t()
        k32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        attrs = ctypes.create_string_buffer(size.value)
        if not k32.InitializeProcThreadAttributeList(attrs, 1, 0, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), "InitializeProcThreadAttributeList")
        if not k32.UpdateProcThreadAttribute(attrs, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, self.hpc, ctypes.sizeof(HPCON), None, None):
            raise OSError(ctypes.get_last_error(), "UpdateProcThreadAttribute")
        si = STARTUPINFOEXW()
        si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
        si.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES, all empty: the shell must not write into Lumen's own console
        si.lpAttributeList = ctypes.cast(attrs, ctypes.c_void_p)
        line = ctypes.create_unicode_buffer(command)
        ok = k32.CreateProcessW(None, line, None, None, False, EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT, None,
                                cwd if os.path.isdir(cwd) else os.path.expanduser("~"), ctypes.byref(si), ctypes.byref(self.pi))
        k32.DeleteProcThreadAttributeList(attrs)
        k32.CloseHandle(in_read)  # the console has its own ends now
        k32.CloseHandle(out_write)
        if not ok:
            k32.ClosePseudoConsole(self.hpc)
            raise OSError(ctypes.get_last_error(), "CreateProcessW")
        self.alive = True
        self._attrs = attrs
        threading.Thread(target=self._read, daemon=True, name="pty-read").start()

    def _read(self) -> None:
        buf = ctypes.create_string_buffer(65536)
        got = wintypes.DWORD()
        pending = b""
        while True:
            if not k32.ReadFile(self.out_read, buf, len(buf), ctypes.byref(got), None) or got.value == 0:
                break
            data = pending + buf.raw[:got.value]
            cut = len(data)
            while cut > 0 and (data[cut - 1] & 0xC0) == 0x80:  # a UTF-8 character split between two reads waits for its end
                cut -= 1
            if cut > 0 and data[cut - 1] >= 0xC0:
                cut -= 1
            text, pending = data[:cut].decode("utf-8", "replace"), data[cut:]
            if text and self.on_output:
                self.on_output(text)
        self.alive = False
        if self.on_exit:
            self.on_exit()

    def write(self, text: str) -> None:
        if not self.alive:
            return
        data = text.encode("utf-8")
        done = wintypes.DWORD()
        k32.WriteFile(self.in_write, data, len(data), ctypes.byref(done), None)

    def resize(self, cols: int, rows: int) -> None:
        size = (max(20, int(cols)), max(5, int(rows)))
        if self.alive and size != self.size:
            self.size = size
            k32.ResizePseudoConsole(self.hpc, COORD(*size))

    def running(self) -> bool:
        if not self.pi.hProcess:
            return False
        code = wintypes.DWORD()
        return bool(k32.GetExitCodeProcess(self.pi.hProcess, ctypes.byref(code))) and code.value == STILL_ACTIVE

    def close(self) -> None:
        """The shell and everything it started end; the reading thread ends when the console closes its pipe."""
        if self.pi.hProcess:
            if self.running():
                k32.TerminateProcess(self.pi.hProcess, 1)
            k32.CloseHandle(self.pi.hProcess)
            k32.CloseHandle(self.pi.hThread)
            self.pi.hProcess = None
        if self.hpc:
            k32.ClosePseudoConsole(self.hpc)
            self.hpc = HPCON()
        if self.in_write:
            k32.CloseHandle(self.in_write)
            self.in_write = wintypes.HANDLE()
        self.alive = False
