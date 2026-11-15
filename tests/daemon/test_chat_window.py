"""The window as a chat (2026-11-03): the list shows each conversation once, by its first message, opening its latest
turn; the voice bar's level and recording helpers."""

from __future__ import annotations

import struct

from codedoctor.desktop import voice
from codedoctor.desktop.sidebar import chats


def test_a_conversation_is_listed_once_by_its_first_message():
    rows = [  # newest first, as Daemon.recent_tasks gives them
        {"id": "t3", "title": "好的，改吧", "state": "running", "outcome": None, "chat_of": "t1", "parent_task_id": None},
        {"id": "h1", "title": "helper", "state": "finished", "outcome": "done", "chat_of": None, "parent_task_id": "t3"},
        {"id": "t2", "title": "另一个问题", "state": "finished", "outcome": "done", "chat_of": None, "parent_task_id": None},
        {"id": "t1", "title": "结账总价不对", "state": "finished", "outcome": "done", "chat_of": None, "parent_task_id": None},
    ]
    listed = chats(rows)
    assert [(c["id"], c["title"], c["open"], c["state"]) for c in listed] == [
        ("t1", "结账总价不对", "t3", "running"),  # named by its first message, opens (and shows the state of) the latest
        ("t2", "另一个问题", "t2", "finished")]


def test_the_waveform_level_follows_loudness():
    silence = struct.pack("<800h", *([0] * 800))
    speech = struct.pack("<800h", *([6000, -6000] * 400))
    assert voice.rms(silence) == 0.0
    assert 0.3 < voice.rms(speech) <= 1.0
    assert voice.rms(b"") == 0.0


def test_a_click_without_speech_writes_nothing():
    assert voice.transcribe(b"\x00\x00" * 1000) == ""  # under 0.3 s: not even sent to the recognizer
