"""The program's icon, Lumen itself at every size Windows asks for: python make_icon.py (run offscreen, once)."""
import os
from pathlib import Path
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication([])
from codedoctor.desktop.team_ui import art

image = art("lumen")
entries = []
for size in (16, 24, 32, 48, 64, 128, 256):
    out = QImage(size, size, QImage.Format_ARGB32)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, size, size), image)
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    out.save(buf, "PNG")
    entries.append((size, bytes(buf.data())))
head = struct.pack("<HHH", 0, 1, len(entries))
offset = 6 + 16 * len(entries)
table, body = b"", b""
for size, data in entries:
    table += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
    offset += len(data)
    body += data
target = Path(__file__).resolve().parent / "lumen.ico"
target.write_bytes(head + table + body)
print(target, target.stat().st_size)
sys.stdout.flush()
os._exit(0)
