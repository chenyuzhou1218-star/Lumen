"""Claude Code and Codex with their own models and levels (codedoctor/engines.py): the window lists each engine's models
by its own names, its level slider has that model's own levels (Codex: Low ... Ultra; no 不思考), and the choice reaches
the engine's command line."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from codedoctor import claude_code, codex, engines  # noqa: E402
from codedoctor.agents.daemon import Daemon  # noqa: E402

CACHE = {"models": [
    {"slug": "gpt-9-sol", "display_name": "GPT-9-Sol", "visibility": "list", "priority": 1, "default_reasoning_level": "low",
     "supported_reasoning_levels": [{"effort": e} for e in ("low", "medium", "high", "xhigh", "max", "ultra")]},
    {"slug": "gpt-9-luna", "display_name": "GPT-9-Luna", "visibility": "list", "priority": 3,
     "supported_reasoning_levels": [{"effort": e} for e in ("low", "medium", "high", "xhigh", "max")]},
    {"slug": "gpt-hidden", "display_name": "Hidden", "visibility": "hide", "priority": 2,
     "supported_reasoning_levels": [{"effort": "low"}]},
]}


@pytest.fixture
def codex_home(tmp_path, monkeypatch):
    (tmp_path / "models_cache.json").write_text(json.dumps(CACHE), encoding="utf-8")
    (tmp_path / "config.toml").write_text('model = "gpt-9-luna"\nmodel_reasoning_effort = "high"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    return tmp_path


def test_codex_lists_its_own_models_with_their_own_levels(codex_home):
    listed = codex.models()
    assert [m["name"] for m in listed] == ["GPT-9-Sol", "GPT-9-Luna"]  # its order; hidden ones left out
    assert listed[0]["efforts"][-1] == "ultra" and "ultra" not in listed[1]["efforts"]
    assert listed[1]["yours"] and not listed[0]["yours"]  # the default set in Codex's config.toml


def test_the_choice_is_checked_against_what_the_engine_has(codex_home, make_config):
    d = Daemon(make_config())
    sub = d.submit_task("doctor", "t", "i", engine="codex", engine_model="gpt-9-sol", engine_effort="ultra")
    assert sub["task_id"]
    with pytest.raises(ValueError, match="Ultra"):
        d.submit_task("doctor", "t", "i", engine="codex", engine_model="gpt-9-luna", engine_effort="ultra")
    with pytest.raises(ValueError):
        d.submit_task("doctor", "t", "i", engine="codex", engine_effort="off")  # no 不思考 in any engine
    with pytest.raises(ValueError, match="Ultra"):
        d.submit_task("doctor", "t", "i", engine="claude_code", engine_effort="ultra")  # Claude Code ends at Max
    assert engines.label({"engine": "codex", "engine_model": "gpt-9-sol", "engine_effort": "xhigh"}) \
        == "Codex · GPT-9-Sol · Extra High"


def test_the_choice_reaches_each_engines_command_line(make_config):
    conf = Daemon(make_config()).s.config
    args = codex.argv(conf, ["codex"], None, "gpt-9-sol", "ultra")
    assert args[args.index("-m") + 1] == "gpt-9-sol" and 'model_reasoning_effort="ultra"' in args and args[-1] == "-"
    args = claude_code.argv(conf, "claude", None, "claude-opus-5-5", "max")
    assert args[args.index("--model") + 1] == "claude-opus-5-5" and args[args.index("--effort") + 1] == "max"
    names = [m["name"] for m in claude_code.models()]
    assert names[:5] == ["Opus 5.5", "Sonnet 5.5", "Fable 5.2", "Haiku 5.5", "Fable 5.1"] and "Haiku 4.5" in names  # as Claude Code lists them
    plain = codex.argv(conf, ["codex"])
    assert "-m" not in plain and not any("model_reasoning_effort" in a for a in plain)  # else Codex's own settings


def test_the_window_offers_each_models_own_levels_by_their_names(codex_home, monkeypatch):
    """Each model's own levels by their names; the user's rule: the message also carries the chat's 批准方式."""
    pytest.importorskip("PySide6")
    from codedoctor.desktop.app import make_app
    from codedoctor.desktop.composer import Composer
    from codedoctor.desktop.picker import ThinkingPopover

    make_app()
    monkeypatch.setattr(codex, "executable", lambda: ["codex"])
    monkeypatch.setattr(claude_code, "executable", lambda: "claude")
    c = Composer([("dual", "双人互检", "worker-1")])
    c._set_level("off", "")  # 不思考 for the project's models ...
    c._set_model({"engine": "codex", "id": "gpt-9-luna", "model": "Codex · GPT-9-Luna"}, "")
    assert c.level == "medium"  # ... means nothing to Codex: a real level instead, there is no 默认
    keys, name = c._levels()
    assert keys == ["low", "medium", "high", "xhigh", "max"] and [name(k) for k in keys][-2:] == ["Extra High", "Max"]
    pop = ThinkingPopover(c, None, c._model_name(), keys, name)
    pop.slider.changed.emit(len(keys) - 1)
    assert pop.title.text() == "Max"
    c._set_level("max", "")
    # the user's rule: every message carries its 批准方式 (帮我审查 = auto unless they chose another)
    assert c.options() == {"engine": "codex", "engine_model": "gpt-9-luna", "engine_effort": "max", "approval": "auto"}
    assert "reasoning" not in c.options()
    c._set_model({"engine": "codex", "id": "gpt-9-sol", "model": "Codex · GPT-9-Sol"}, "")
    assert c._levels()[0][-1] == "ultra" and c.level == "max"  # still one of this model's levels
    c._set_model({"engine": "claude_code", "id": "claude-haiku-5-5", "model": "Claude Code · Haiku 5.5"}, "")
    keys, name = c._levels()  # Haiku has Claude's five levels too, under their own names
    assert keys == ["low", "medium", "high", "xhigh", "max"] and [name(k) for k in keys] == ["低", "中等", "高", "超高", "最高"]
    assert ThinkingPopover(c, None, c._model_name(), [], name).slider is None  # a model without levels: nothing to choose


async def test_an_agent_on_a_codex_service_hands_its_tasks_to_codex(make_config, monkeypatch):
    """Claude Code / Codex set up as a service (kind engine, first run): the agent on it gives Codex the task, with
    the agent's model; a model chosen for one task (another service) wins."""
    import asyncio

    seen = []

    async def fake_run(rt, msg, body):
        from codedoctor.agents.runtime import Usage

        seen.append(body)
        return "done", "ok", {"evidence": [], "claims": [], "usage": Usage()}

    monkeypatch.setattr(codex, "run", fake_run)
    cfg = make_config({"plain-model": [{"text": "answered by the API model"}]},
                      endpoints=[{"id": "codex", "kind": "engine", "base_url": "engine:codex", "local": False,
                                  "max_data_class": "internal", "models": ["gpt-9-sol"]},
                                 {"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
                      agents=[{"id": "doctor", "role": "general", "endpoint": "codex", "model": "gpt-9-sol"}])
    d = Daemon(cfg, poll_s=0.05)
    await d.start()
    try:
        sub = d.submit_task("doctor", "t", "fix it")
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 30)
        other = d.submit_task("doctor", "t", "fix it", model={"endpoint": "fake", "model": "plain-model"})
        report = await asyncio.wait_for(d.wait_for_report(other["task_id"]), 30)
    finally:
        await d.halt()
    assert len(seen) == 1 and seen[0]["engine"] == "codex" and seen[0]["engine_model"] == "gpt-9-sol"
    assert "answered by the API model" in report["body"]["summary"]
    from codedoctor.models.factory import build_client

    client = build_client(cfg.endpoints["codex"])
    with pytest.raises(Exception, match="investigations"):
        await client.chat("gpt-9-sol", [], [])
