"""A project's code level above what its agents' services may receive (仅本机 code, a cloud model): found before any
investigation starts, explained in plain words once, and the user can fix it in one click (a real user's project
stopped with three identical English messages)."""

from __future__ import annotations

from codedoctor.evidence.registry import blocked_agents, raw_blocked_services

CLOUD = {"id": "deepseek", "name": "DeepSeek", "kind": "scripted", "base_url": "scripted:", "local": False,
         "max_data_class": "internal"}


def test_agents_whose_services_may_not_receive_the_code_are_found(make_config):
    assert blocked_agents(make_config(endpoints=[CLOUD], agents=[
        {"id": "doctor", "role": "general", "endpoint": "deepseek", "model": "m"}], code_data_class="local_only")) == ["doctor"]
    assert blocked_agents(make_config(endpoints=[CLOUD], agents=[
        {"id": "doctor", "role": "general", "endpoint": "deepseek", "model": "m"}], code_data_class="internal")) == []
    local = {"id": "ollama", "kind": "scripted", "base_url": "scripted:", "local": True}  # may receive anything
    assert blocked_agents(make_config(endpoints=[CLOUD, local], agents=[
        {"id": "doctor", "role": "general", "endpoint": "ollama", "model": "m"}], code_data_class="local_only")) == []


def test_a_new_configuration_is_checked_before_it_is_saved():
    raw = {"project": {"code_data_class": "local_only"}, "endpoints": [CLOUD],
           "agents": [{"id": "a", "endpoint": "deepseek", "model": "m"}]}
    assert raw_blocked_services(raw) == ["DeepSeek"]
    raw["project"]["code_data_class"] = "internal"
    assert raw_blocked_services(raw) == []


async def test_the_block_says_what_happened_and_how_to_fix_it_in_chinese(make_config):
    from codedoctor.models import scripted

    from test_agent import run_task

    scripted.register("reads-then-stops", [{"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py"}}]},
                                           {"text": "should not be asked"}])
    cfg = make_config(endpoints=[CLOUD], agents=[{"id": "doctor", "role": "general", "endpoint": "deepseek",
                                                  "model": "reads-then-stops"}], code_data_class="local_only")
    d, sub, report = await run_task(cfg)
    assert report["body"]["outcome"] == "blocked"
    esc = next(m for m in d.s.bus.list(task_id=sub["task_id"]) if m["kind"] == "escalation")
    text = esc["body"]["detail"]
    assert "最多只能收到“内部”级别" in text and "仅本机" in text and "改成内部代码" in text
    assert "No fallback models" not in text  # a fallback would not help: no service may receive this code
