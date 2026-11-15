from __future__ import annotations

import itertools
import os
import tempfile
from pathlib import Path

import pytest

from codedoctor import config as config_mod
from codedoctor.agents.runtime import AgentRuntime
from codedoctor.models import scripted

_counter = itertools.count()

# The desktop app remembers opened projects in ~/.codedoctor; tests must never write the user's list.
os.environ["CODEDOCTOR_HOME"] = tempfile.mkdtemp(prefix="cd-home-")
# the shared memory of the user (memory/digest.py) would ask the scripted test models for a rewrite of its own
os.environ["LUMEN_NO_DIGEST"] = "1"
# The tests read the Chinese texts; a Lumen never set up follows the computer's language (prefs.load), which is English on
# many machines: the test home says Chinese, as a user who chose it.
(Path(os.environ["CODEDOCTOR_HOME"]) / "ui.json").write_text('{"language": "zh"}', encoding="utf-8")
# ... and applied, as Lumen's start does (desktop/app.main): the window built here (make_app) never reads it, so the texts
# came out in English and every test reading Chinese failed unless an earlier test had switched the language.
from codedoctor.desktop import i18n as _i18n  # noqa: E402

_i18n.set_language("zh")

SHOP_PY = '''\
class ShopService:
    def buy(self, player, item_id, inventory_version):
        item = self.items[item_id]
        if player.gold < item.price:
            raise NotEnoughGold()
        if inventory_version != player.inventory_version:
            return None  # BUG: silent early return, nothing is written and the client gets no error
        player.gold -= item.price
        self.orders.insert(player.id, item_id)
        return item
'''


def _row(value, name, efforts=("low", "medium", "high", "xhigh", "max"), resolved=None):
    row = {"value": value, "resolvedModel": resolved or value, "displayName": name, "description": ""}
    if efforts:
        row.update(supportsEffort=True, supportedEffortLevels=list(efforts))
    return row


# Claude Code's model menu as it answered `initialize` on 2026-11-10 (claude_code.ask_menu), so tests never start it.
CLAUDE_MENU = [_row("default", "Default (recommended)", resolved="claude-opus-5-5"),
               _row("opus", "Opus 5.5", resolved="claude-opus-5-5"), _row("sonnet", "Sonnet 5.5", resolved="claude-sonnet-5-5"),
               _row("claude-fable-5-2", "Fable 5.2"), _row("haiku", "Haiku 5.5", resolved="claude-haiku-5-5"),
               _row("fable", "Fable 5.1", resolved="claude-fable-5-1"), _row("claude-haiku-4-5-20251001", "Haiku 4.5", ()),
               _row("claude-sonnet-5", "Sonnet 5"), _row("claude-opus-5", "Opus 5"), _row("claude-fable-5", "Fable 5"),
               _row("claude-opus-4-8", "Opus 4.8"), _row("claude-opus-4-7", "Opus 4.7"),
               _row("claude-opus-4-6", "Opus 4.6", ("low", "medium", "high", "max")),
               _row("claude-sonnet-4-6", "Sonnet 4.6", ("low", "medium", "high", "max"))]


@pytest.fixture(autouse=True)
def _collect_on_the_main_thread():
    """The windows of earlier tests are left to the garbage collector. When it ran on a worker thread (a daemon's
    to_thread) it freed their Qt objects there, and Qt ended the whole test run (Windows fatal exception 0x80000003).
    So garbage is only ever collected here, between tests, on the main thread."""
    import gc

    gc.disable()  # stays off for the whole run: threads left by earlier tests can allocate between tests too
    try:
        yield
    finally:
        gc.collect()


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    monkeypatch.setattr(AgentRuntime, "retry_delay_s", 0.0)


@pytest.fixture(autouse=True)
def claude_menu(monkeypatch):
    """What Claude Code lists (a list the test may change), asked afresh by every test."""
    from codedoctor import claude_code

    menu = [dict(m) for m in CLAUDE_MENU]
    monkeypatch.setattr(claude_code, "ask_menu", lambda timeout_s=45.0: [dict(m) for m in menu])
    monkeypatch.setattr(claude_code, "_menu", None)
    monkeypatch.setattr(claude_code, "_asked", False)
    claude_code._menu_file().unlink(missing_ok=True)
    return menu


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    (root / "server").mkdir(parents=True)
    (root / "server" / "shop.py").write_text(SHOP_PY, encoding="utf-8")
    (root / "README.md").write_text("Shop demo\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("secret outside the project\n", encoding="utf-8")
    return root


def unique_model(prefix: str = "m") -> str:
    return f"{prefix}-{next(_counter)}"


@pytest.fixture
def make_config(project: Path, tmp_path: Path):
    """make_config(scripts={model: turns}, agents=[...], endpoints=[...], **overrides) -> ProjectConfig"""

    def make(scripts: dict[str, list[dict]] | None = None, *, agents=None, endpoints=None, permissions=None,
             defaults=None, code_data_class=None, memory=None, computer=None):
        for model, turns in (scripts or {}).items():
            scripted.register(model, turns)
        first_model = next(iter(scripts)) if scripts else "none"
        raw = {
            "cd_schema": "cd.config.project/0",
            "project": {"name": "shop-demo", "root": str(project), "data_dir": str(tmp_path / "data")},
            "endpoints": endpoints or [{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
            "agents": agents or [{"id": "doctor", "role": "general", "endpoint": "fake", "model": first_model}],
            "defaults": defaults or {"budget": {"max_steps": 12}, "stall_steps": 3},
        }
        if permissions:
            raw["permissions"] = permissions
        if code_data_class:
            raw["project"]["code_data_class"] = code_data_class
        if computer:
            raw["computer"] = computer
        if memory:
            raw["memory"] = memory
        return config_mod.parse(raw, base_dir=tmp_path)

    return make
