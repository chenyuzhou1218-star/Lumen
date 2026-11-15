from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from codedoctor import cli
from codedoctor.api import create_app

from conftest import unique_model


def test_http_api_task_lifecycle(make_config):
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "remember", "arguments": {"text": "API test note about shop.py", "scope": "project"}}]},
        {"text": "finished via API"},
    ]})
    with TestClient(create_app(cfg, poll_s=0.05)) as client:
        health = client.get("/health").json()
        assert health["ok"] and health["agents"][0]["model"] == f"fake/{model}"

        sub = client.post("/tasks", json={"agent": "doctor", "title": "t", "instructions": "go"}).json()
        for _ in range(200):
            task = client.get(f"/tasks/{sub['task_id']}").json()
            if task["state"] == "finished":
                break
            time.sleep(0.02)
        assert task["outcome"] == "done"
        assert [m["kind"] for m in task["messages"]] == ["task", "report"]

        journal = client.get("/journal", params={"task_id": sub["task_id"]}).json()
        assert journal[0]["type"] == "message_in"
        assert [e["type"] for e in journal].count("model_response") == 2
        original = client.get(f"/journal/{journal[0]['id']}/original").json()
        assert original["payload"]["body"]["instructions"] == "go"

        hits = client.get("/memory/search", params={"q": "shop.py", "reader": "doctor"}).json()
        assert any("API test note" in h["text"] for h in hits)

        assert client.post("/tasks", json={"agent": "ghost", "title": "t", "instructions": "x"}).status_code == 404
        assert client.post("/control", json={"agent": "doctor", "command": "explode"}).status_code == 422


def test_cli_run_with_scripted_file(project, tmp_path, capsys):
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"demo": [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py", "start_line": 1, "end_line": 3}}]},
        {"text": "CLI answer"},
    ]}), encoding="utf-8")
    config = tmp_path / "cd.toml"
    config.write_text(f"""
cd_schema = "cd.config.project/0"

[project]
name = "shop-demo"
root = "{project.as_posix()}"
data_dir = "{(tmp_path / 'cli-data').as_posix()}"

[[endpoints]]
id = "demo"
kind = "scripted"
base_url = "scripted:{script.as_posix()}"
local = true

[[agents]]
id = "doctor"
role = "general"
endpoint = "demo"
model = "demo"
""", encoding="utf-8")
    assert cli.main(["run", "--config", str(config), "--agent", "doctor", "Look at the shop"]) == 0
    out = capsys.readouterr().out
    assert "=== done ===" in out and "CLI answer" in out and "ev:code:" in out

    assert cli.main(["memory", "--config", str(config), "--reader", "doctor", "Look at the shop"]) == 0
    assert "ended done" in capsys.readouterr().out  # the task summary note was saved to long-term memory

    assert cli.main(["check", "--config", str(config)]) == 0


def test_cli_rejects_bad_config(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"cd_schema": "cd.config.project/0", "project": {"name": "x", "root": "."},
                               "endpoints": [{"id": "e", "kind": "openai_compatible", "base_url": "http://x", "local": False, "api_key": "sk-1"}],
                               "agents": [{"id": "a", "role": "general", "endpoint": "e", "model": "m"}]}), encoding="utf-8")
    assert cli.main(["check", "--config", str(bad)]) == 2
    assert "config error" in capsys.readouterr().err
