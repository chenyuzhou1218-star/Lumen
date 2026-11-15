"""Folders: the list of folders this user has opened, and the setup they open with.

One window works on one folder (its own configuration, database and memory). The list lives in
~/.codedoctor/projects.json; a folder's configuration is written to ~/.codedoctor/configs/<name>.toml the first time
it is opened, from the setup chosen once on first run (setup.json: the AI services and models, whether the agents
may change code), and its data goes to the default ~/.codedoctor/projects/<name>/. Opening another folder happens in
the same process (MainWindow.switch_to). Computer-use permissions are never copied: the windows and programs they
allow belong to one folder.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from codedoctor import config as config_mod

def _home() -> Path:
    """~/.codedoctor, or CODEDOCTOR_HOME (tests point it at a temporary folder so they never touch the user's list)."""
    return Path(os.environ.get("CODEDOCTOR_HOME") or Path.home() / ".codedoctor")


def _registry() -> Path:
    return _home() / "projects.json"


def _configs() -> Path:
    return _home() / "configs"
_NAME = re.compile(r"^[\w\-. ]{1,60}$")  # also a folder name (data dir, config file)


def load() -> list[dict]:
    try:
        items = json.loads(_registry().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [i for i in items if isinstance(i, dict) and i.get("config")]


def _write(items: list[dict]) -> None:
    _home().mkdir(parents=True, exist_ok=True)
    tmp = _registry().with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_registry())


def _same(a: str, b: str) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def register(name: str, config_path: str, root: str, label: str | None = None) -> None:
    """Remember a project (most recently opened first). label: the name the user gave it (创建项目), kept from then on;
    `name` is its configuration's (lower-case ASCII)."""
    before = next((i for i in load() if _same(i["config"], config_path)), {})
    items = [i for i in load() if not _same(i["config"], config_path)]
    entry = {"name": name, "config": str(Path(config_path).resolve()), "root": root}
    if label or before.get("label"):
        entry["label"] = label or before["label"]
    items.insert(0, entry)
    try:
        _write(items[:50])
    except OSError:
        pass  # the list is a convenience; the project itself still works


def forget(config_path: str) -> None:
    _write([i for i in load() if not _same(i["config"], config_path)])


# --- the user's setup: chosen once, then every folder opens with it (2026-11-03) ----------------------------------

def _setup_file() -> Path:
    return _home() / "setup.json"


def load_setup() -> dict | None:
    """What the user chose the first time Lumen opened - {"endpoints", "agents", "permissions"; an old "region" is ignored} - or
    None before that (the first-run screen comes first)."""
    try:
        data = json.loads(_setup_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("endpoints") and data.get("agents") else None


def save_setup(setup: dict) -> None:
    _home().mkdir(parents=True, exist_ok=True)
    tmp = _setup_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(setup, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_setup_file())


def workspace() -> Path:
    """Where Lumen opens before any folder was chosen: ~/Lumen (made empty the first time)."""
    folder = Path.home() / "Lumen"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def last_opened() -> str | None:
    """The configuration of the folder opened most recently that still exists."""
    return next((i["config"] for i in load() if Path(i["config"]).exists()), None)


# What a new project starts with (the user, 2026-11-13): everything on. Agents may change files and run these commands (the
# list is what the project's own tools and tests need; each is still one command, no shell); the computer is on with the
# supervisor approving every mouse and keyboard action and every terminal command first, and irreversible ones asking the
# user. The window list is one empty fragment: it matches every window, because computer use refuses to start with none.
START_COMMANDS = config_mod.START_COMMANDS


def start_permissions() -> dict:
    return {"write_files": True, "run_command": "allowlist", "command_allowlist": list(START_COMMANDS)}


def start_computer() -> dict:
    return {"screenshot": "on", "input": "guardian", "terminal": "guardian", "windows": [""]}


def for_folder(folder: str | Path, setup: dict | None = None, label: str | None = None) -> Path:
    """The configuration that opens `folder`: the one it already has, else a new one made from the user's setup
    (their AI services and models, the permissions they chose) - no questions. label: the project's name as the user
    gave it (创建项目); shown in the window instead of the folder's."""
    folder = Path(folder).resolve()
    for item in load():
        if item.get("root") and _same(item["root"], str(folder)) and Path(item["config"]).exists():
            if label:
                register(item["name"], item["config"], item["root"], label)
            return Path(item["config"])
    setup = setup or load_setup()
    if setup is None:
        raise RuntimeError("Lumen has not been set up yet")
    # a configuration's name is lower-case ASCII (it names its data folder): "Lumen" -> code-doctor, 商城 -> folder
    base = re.sub(r"[^a-z0-9._-]+", "-", folder.name.lower()).strip("-._")[:50] or "folder"
    name, n = base, 2
    while any(i["name"] == name for i in load()) or (_configs() / f"{name}.toml").exists():
        name, n = f"{base}-{n}", n + 1
    raw = {"cd_schema": "cd.config.project/0",
           "project": {"name": name, "root": folder.as_posix(), "code_data_class": "internal"},
           "endpoints": copy.deepcopy(setup["endpoints"]), "agents": copy.deepcopy(setup["agents"])}
    from codedoctor.agents import team

    team.add_to_raw(raw)  # the Lumen team, on the model the user chose
    perm = start_permissions()  # a project starts with everything on; only the setup's own choice to let agents change files counts
    if "write_files" in (setup.get("permissions") or {}):
        perm["write_files"] = bool(setup["permissions"]["write_files"])
    from codedoctor.desktop.settings_view import detect_test_command

    test = detect_test_command(folder)  # this folder's own tests, run by the system after each change
    if test:
        perm["test_command"] = test
    raw["permissions"] = perm
    raw["computer"] = start_computer()
    path = _configs() / f"{name}.toml"
    _configs().mkdir(parents=True, exist_ok=True)
    config_mod.save_raw(raw, path)
    register(name, str(path), raw["project"]["root"], label)
    return path


def ensure_team(path: str | Path) -> bool:
    """The Lumen team joins a project that does not have it yet (agents/team.py), on the model the project's first
    agent uses - the model the user chose. True when the configuration changed."""
    from codedoctor.agents import team

    raw = config_mod.load_raw(path)
    if not team.add_to_raw(raw):
        return False
    config_mod.save_raw(raw, path)
    return True


def ask_code_level(parent, raw: dict) -> bool:
    """The code level chosen is above what the agents' services may receive (仅本机 code, a cloud model): every
    investigation would stop at once. Offer 内部; the user decides. False: cancelled."""
    from codedoctor.evidence.registry import DATA_CLASS_CN, raw_blocked_services

    blocked = raw_blocked_services(raw)
    if not blocked:
        return True
    level = DATA_CLASS_CN.get(raw["project"]["code_data_class"], raw["project"]["code_data_class"])
    box = QMessageBox(QMessageBox.Warning, "代码级别",
                      f"代码级别“{level}”的代码不能发给 {'、'.join(blocked)}，这个项目的调查会一开始就停下。\n"
                      "可以把代码发给它的话，改成“内部”再创建；否则保留，之后给 Agent 换成本机运行的模型。", parent=parent)
    internal = box.addButton("改成内部再创建", QMessageBox.AcceptRole)
    box.addButton("保留并创建", QMessageBox.DestructiveRole)
    cancel = box.addButton("取消", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() is cancel:
        return False
    if box.clickedButton() is internal:
        raw["project"]["code_data_class"] = "internal"
    return True
