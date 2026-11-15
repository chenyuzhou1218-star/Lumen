"""The window in another language (desktop/locale.py): every text it shows has an English entry, texts are
translated where they reach the screen, and an agent's own words are never touched."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_every_text_the_window_shows_has_an_english_entry():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "extract_ui_strings.py")], capture_output=True,
                         env={"PYTHONIOENCODING": "utf-8", "SYSTEMROOT": r"C:\Windows"}, cwd=ROOT)
    found = json.loads(out.stdout.decode("utf-8"))
    cat = json.loads((ROOT / "daemon/codedoctor/desktop/locale/en.json").read_text(encoding="utf-8"))
    missing = [k for k in found["exact"] if k not in cat["exact"]] + [k for k in found["templates"] if k not in cat["templates"]]
    assert not missing, f"{len(missing)} texts have no English entry (add them to desktop/locale/en.json): {missing[:10]}"


def test_texts_are_translated_and_agents_words_are_not():
    from codedoctor.desktop import locale

    locale.load("en")
    try:
        assert locale.t("设置") == "Settings"
        assert locale.t("3 步 · 4 秒 · token 5,280") == "3 steps · 4 s · token 5,280"  # a template, pieces in it
        assert locale.t("● 事件") == "● Events"  # a symbol in front
        assert locale.t("这是一个 Agent 写的中文回答") == "这是一个 Agent 写的中文回答"  # unknown: untouched
        assert locale.t("plain English") == "plain English"
    finally:
        locale.load("zh")
    assert locale.t("设置") == "设置"  # Chinese: nothing changes


def test_labels_qt_makes_itself_are_translated_too():
    """A form row's label, list items and table headers are made inside Qt (no Python constructor runs): the
    appearance page showed 壁纸 in English mode."""
    from PySide6.QtWidgets import QApplication, QComboBox, QFormLayout, QLabel, QListWidget, QTableWidget, QWidget

    from codedoctor.desktop import locale, prefs

    QApplication.instance() or QApplication([])
    locale.install("en")
    try:
        host = QWidget()
        form = QFormLayout(host)
        wall = QComboBox()
        for v, t in prefs.WALLPAPERS:
            wall.addItem(t, v)
        form.addRow("壁纸", wall)
        assert form.labelForField(wall).text() == "Wallpaper"
        assert [wall.itemText(i) for i in range(wall.count())] == ["Plain white", "Flowing silk", "Aurora"]
        items = QListWidget()
        items.addItems(["设置"])
        items.addItem("设置")
        assert {items.item(i).text() for i in range(2)} == {"Settings"}
        table = QTableWidget(0, 1)
        table.setHorizontalHeaderLabels(["设置"])
        assert table.horizontalHeaderItem(0).text() == "Settings"
        assert isinstance(form.labelForField(wall), QLabel)
    finally:
        locale.load("zh")
