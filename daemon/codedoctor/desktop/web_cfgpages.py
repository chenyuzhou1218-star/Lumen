"""自动测试 and 电脑操作 in React: what each page shows (state) and what its controls change (act).

They edit the same raw configuration as the other settings (web_settings.py; 保存 writes it). No lists of allowed commands,
windows or programs any more (the user, 2026-11-14: "把所有的白名单全都删掉"): what needs the user is the 批准方式 under the
message box. The screenshot level stays internal unless changed.
"""

from __future__ import annotations

from pathlib import Path

from codedoctor.desktop import locale

t = locale.t



class Refused(ValueError):
    """A change the page may not make; the words are shown to the user."""


def code(raw: dict) -> dict:
    return {"test_command": raw.get("permissions", {}).get("test_command", "")}


def computer(raw: dict, data_classes) -> dict:
    from codedoctor.config import START_COMPUTER

    cur = raw.get("computer", START_COMPUTER)
    return {"disabled": bool(cur.get("disabled", False)), "background": bool(cur.get("background", True)),
            "data_class": cur.get("screenshot_data_class", "internal"),
            "data_classes": [{"value": v, "label": t(text)} for v, text in data_classes]}


def act_code(raw: dict, action: str, data: dict) -> None:
    from codedoctor.config import START_COMMANDS
    from codedoctor.desktop.settings_view import detect_test_command

    perm = dict(raw.get("permissions", {}))
    if action == "code_detect":
        found = detect_test_command(Path(raw.get("project", {}).get("root", ".")))
        if not found:
            raise Refused(t("没找到测试：项目里没有 tests 目录、test_*.py 或 package.json 的 test 脚本。"))
        data = {"test_command": found}
    if "test_command" in data:
        test = str(data["test_command"]).strip()
        if test:
            perm["test_command"] = test
        else:
            perm.pop("test_command", None)
    perm["run_command"] = "allowlist"  # an old field name: any command runs (agents/tools.py run_command has no list)
    perm.setdefault("command_allowlist", list(START_COMMANDS))
    raw["permissions"] = perm


def act_computer(raw: dict, data: dict, data_classes) -> None:
    """Computer use is on from the start; 禁止电脑操作 is the only way to switch it off. Screenshots, mouse and keyboard, starting
    programs and the terminal are always on, in every window but Lumen's own; who is asked is the approval choice under the
    message box."""
    old = raw.get("computer", {})
    comp = {k: v for k, v in old.items() if k in ("capture", "guardian_timeout_s", "user_timeout_s", "max_actions_per_task")}
    cur = computer(raw, data_classes)
    cur.update({k: v for k, v in data.items() if k in cur and k != "data_classes"})
    if cur["data_class"] not in dict(data_classes):
        raise Refused(t("没有这个选项：") + str(cur["data_class"]))
    comp.update({"screenshot": "on", "input": "guardian", "apps": "guardian", "terminal": "guardian", "windows": [""]})
    if old.get("launch"):  # short names an older configuration gave some programs; any other program starts by its path
        comp["launch"] = list(old["launch"])
    if not cur["background"]:
        comp["background"] = False
    if cur["data_class"] != "internal":
        comp["screenshot_data_class"] = cur["data_class"]
    if cur["disabled"]:
        comp["disabled"] = True
    raw["computer"] = comp
