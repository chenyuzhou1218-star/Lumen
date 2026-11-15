"""The programs Lumen starts for its right side (CodeCut, Code3D, CodePDF ... and what they start, such as Blender) end
with Lumen, even when Lumen does not get to close them itself - a crash, 结束任务 in Task Manager. A Windows job object
with "kill on close" does it: Windows closes the job's handle when Lumen's process ends, and every program in it goes.

Found 2026-11-14: a dozen tool editors from earlier Lumen runs were still running, holding memory, until x264 in the next
run could not get any.
"""

from __future__ import annotations

import os

_job = None


def _the_job():
    global _job
    if _job is not None or os.name != "nt":
        return _job
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    handle = k32.CreateJobObjectW(None, None)
    if not handle:
        return None
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):  # 9: extended limit information
        k32.CloseHandle(handle)
        return None
    _job = (k32, handle)  # the handle stays open for as long as Lumen runs, on purpose
    return _job


def adopt(proc) -> bool:
    """Put a started subprocess.Popen into Lumen's job; False where there is none (not Windows, or Windows refused)."""
    job = _the_job()
    if job is None:
        return False
    k32, handle = job
    try:
        return bool(k32.AssignProcessToJobObject(handle, int(proc._handle)))
    except (AttributeError, OSError):
        return False
