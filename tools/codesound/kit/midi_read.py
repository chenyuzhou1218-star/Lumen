"""Reads a standard MIDI file: note starts and lengths in beats, and the first tempo."""
from __future__ import annotations

from pathlib import Path
import struct


def _vlq(data: bytes, at: int) -> tuple:
    value = 0
    while True:
        b = data[at]
        at += 1
        value = (value << 7) | (b & 0x7f)
        if not b & 0x80:
            return value, at


def read(path: str) -> dict:
    data = Path(path).read_bytes()
    if data[:4] != b'MThd':
        raise ValueError('not a MIDI file')
    _, tracks, division = struct.unpack('>HHH', data[8:14])
    if division & 0x8000:
        raise ValueError('time-code MIDI files are not read')
    at = 14
    notes, tempo = [], None
    for _ in range(tracks):
        size = struct.unpack('>I', data[at + 4:at + 8])[0]
        p, end = at + 8, at + 8 + size
        at = end
        now, status = 0, 0
        open_notes: dict = {}
        while p < end:
            delta, p = _vlq(data, p)
            now += delta
            if data[p] & 0x80:
                status = data[p]
                p += 1
            kind = status & 0xf0
            if status == 0xff:
                meta = data[p]
                length, p = _vlq(data, p + 1)
                if meta == 0x51 and tempo is None:
                    tempo = 60_000_000 / int.from_bytes(data[p:p + 3], 'big')
                p += length
            elif status in (0xf0, 0xf7):
                length, p = _vlq(data, p)
                p += length
            elif kind in (0xc0, 0xd0):
                p += 1
            else:
                a, b = data[p], data[p + 1]
                p += 2
                if kind == 0x90 and b:
                    open_notes[(status & 15, a)] = (now, b)
                elif kind in (0x80, 0x90) and (status & 15, a) in open_notes:
                    start, vel = open_notes.pop((status & 15, a))
                    if status & 15 != 9:  # channel ten is percussion, not pitches
                        notes.append((start / division, max(1, now - start) / division, a, vel))
    return {'tempo': tempo, 'notes': sorted(notes)}
