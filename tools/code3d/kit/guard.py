"""Keeps a scene script to its own folder: scene.py is code, and an AI may have written it.

An audit hook refuses what a model has no business doing in Blender: starting programs, opening the network, loading
native libraries, and reading or writing files outside the project. It stops an honest mistake and a careless script.
It is not a sandbox against a determined attacker: Blender's own C code (bpy.ops, image loading) does not pass here.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

_REFUSED = ('subprocess.Popen', 'os.system', 'os.exec', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.spawn', 'os.startfile',
            'pty.spawn', 'socket.connect', 'socket.bind', 'socket.sendto', 'socket.getaddrinfo', 'urllib.Request', 'webbrowser.open',
            'ftplib.connect', 'smtplib.connect', 'http.client.connect', 'winreg.OpenKey', 'winreg.CreateKey', 'winreg.SetValue')
_NATIVE = ('ctypes.dlopen', 'ctypes.dlsym', 'ctypes.call_function')  # numpy and Blender's exporters use these; a scene may not
_CHANGES = ('os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.chmod', 'os.link', 'os.symlink', 'os.truncate', 'shutil.copyfile',
            'shutil.move', 'shutil.rmtree')
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


class Refused(PermissionError):
    pass


def install(project: Path, extra_read: list, script: str = '') -> None:
    """From here on, until Blender exits."""
    script = os.path.normcase(script)
    import_of_ctypes = os.path.normcase(os.path.dirname(os.__file__) + os.sep + 'ctypes')
    writes = [str(Path(project).resolve()).lower(), os.path.normcase(os.environ.get('TEMP', '') or os.path.join(project, 'out')).lower()]
    reads = writes + [str(Path(p).resolve()).lower() for p in extra_read]
    appdata = os.environ.get('APPDATA')
    if appdata:
        reads.append(str(Path(appdata) / 'Blender Foundation').lower())

    def inside(path, roots) -> bool:
        if not isinstance(path, (str, os.PathLike)):
            return True  # a file descriptor: already open
        try:
            p = os.path.normcase(os.path.abspath(os.fspath(path))).lower()
        except (TypeError, ValueError):
            return True
        return any(p == r or p.startswith(r + os.sep) for r in roots if r)

    def scene_itself() -> bool:
        """Is the code asking the scene's own, not a library it called?"""
        f = sys._getframe(2)
        while f is not None:
            name = os.path.normcase(f.f_code.co_filename)
            if not name.startswith(import_of_ctypes):
                return name == script
            f = f.f_back
        return False

    def hook(event, args):
        if event in _NATIVE:
            if scene_itself():
                raise Refused(f'scene.py may not load native code ({event}).')
            return
        if event in _REFUSED:
            raise Refused(f'scene.py may not do this: {event}. It only builds the scene, inside the project folder.')
        if event == 'open':
            path, mode, flags = args
            wants_write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & _WRITE_FLAGS)
            if not inside(path, writes if wants_write else reads):
                raise Refused(f"scene.py may only use files inside the project folder, not {path}")
        elif event in _CHANGES:
            for a in args:
                if isinstance(a, (str, os.PathLike)) and not inside(a, writes):
                    raise Refused(f"scene.py may only change files inside the project folder, not {a}")

    sys.addaudithook(hook)
