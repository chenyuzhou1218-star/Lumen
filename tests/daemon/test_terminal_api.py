"""Code Doctor without the window: `codedoctor fix` in the project folder with live progress, show / tasks / undo, and
the HTTP API for scripts (submit without naming an agent, progress, result, undo, a bearer token)."""

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from codedoctor import cli
from codedoctor.api import create_app

from conftest import unique_model


def _config(tmp_path, project, script: list[dict]) -> "Path":  # noqa: F821
    path = tmp_path / "script.json"
    path.write_text(json.dumps({"demo": script}), encoding="utf-8")
    config = tmp_path / "cd.toml"
    config.write_text(f"""
cd_schema = "cd.config.project/0"

[project]
name = "shop-demo"
root = "{project.as_posix()}"
data_dir = "{(tmp_path / 'data').as_posix()}"

[permissions]
run_command = "deny"
write_files = true

[[endpoints]]
id = "demo"
kind = "scripted"
base_url = "scripted:{path.as_posix()}"
local = true

[[agents]]
id = "doctor"
role = "general"
endpoint = "demo"
model = "demo"
""", encoding="utf-8")
    return config


def test_fix_in_the_project_folder_shows_progress_and_the_result_and_undo_puts_it_back(project, tmp_path, monkeypatch, capsys):
    before = (project / "server/shop.py").read_text(encoding="utf-8")
    line = next(ln for ln in before.splitlines() if ln.strip())
    config = _config(tmp_path, project, [
        {"tool_calls": [{"name": "edit_file", "arguments": {"path": "server/shop.py", "old": line, "new": line + "  # fixed"}}]},
        {"text": "修好了 shop.py"}])
    # the window registered the project; the terminal finds it from the folder it runs in
    home = tmp_path / "home"
    home.mkdir()
    (home / "projects.json").write_text(json.dumps([{"name": "shop-demo", "config": str(config), "root": str(project)}]),
                                        encoding="utf-8")
    monkeypatch.setenv("CODEDOCTOR_HOME", str(home))
    monkeypatch.chdir(project / "server")

    assert cli.main(["fix", "购物车总价不对"]) == 0
    out = capsys.readouterr()
    assert "项目：shop-demo" in out.err
    assert "doctor  修改 server/shop.py" in out.out or "doctor  " in out.out  # live progress lines
    assert "=== 完成 ===" in out.out and "修好了 shop.py" in out.out
    assert "server/shop.py" in out.out and "+1 -1" in out.out
    assert (project / "server/shop.py").read_text(encoding="utf-8") != before

    assert cli.main(["tasks"]) == 0
    assert "购物车总价不对" in capsys.readouterr().out
    assert cli.main(["show", "last", "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["changes"][0]["path"] == "server/shop.py" and shown["outcome"] == "done"

    assert cli.main(["undo", "--yes"]) == 0
    assert "已恢复 1 个" in capsys.readouterr().out
    assert (project / "server/shop.py").read_text(encoding="utf-8") == before

    assert cli.main(["projects"]) == 0
    assert "shop-demo" in capsys.readouterr().out


def test_without_a_project_the_terminal_says_what_to_do(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CODEDOCTOR_HOME", str(tmp_path / "empty"))
    assert cli.main(["fix", "x"]) == 2
    assert "没找到项目" in capsys.readouterr().err


def test_http_api_for_scripts_progress_result_and_token(make_config):
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py"}}]},
        {"text": "看过了"}]})
    with TestClient(create_app(cfg, token="s3cret", poll_s=0.05)) as client:
        assert client.get("/health").status_code == 401  # no token
        auth = {"Authorization": "Bearer s3cret"}
        sub = client.post("/tasks", json={"instructions": "检查 shop.py"}, headers=auth).json()  # no agent, no title
        assert sub["agent"] == "doctor"
        seq, lines = 0, []
        for _ in range(300):
            p = client.get(f"/tasks/{sub['task_id']}/progress", params={"after_seq": seq}, headers=auth).json()
            lines += [e["text"] for e in p["events"]]
            seq = p["last_seq"]
            if p["settled"]:
                break
            time.sleep(0.02)
        assert any("读取 server/shop.py" in t for t in lines)
        r = client.get(f"/tasks/{sub['task_id']}/result", headers=auth).json()
        assert r["status"] == "完成" and r["answer"] == "看过了" and r["settled"]
        assert client.post("/tasks/task_nope/cancel", headers=auth).status_code == 404


def test_serve_off_this_machine_needs_a_token(project, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CODEDOCTOR_API_TOKEN", raising=False)
    config = _config(tmp_path, project, [{"text": "x"}])
    assert cli.main(["serve", "--config", str(config), "--host", "0.0.0.0"]) == 2
    assert "必须设访问令牌" in capsys.readouterr().err


def test_one_investigation_can_use_another_model_and_a_thinking_level(make_config):
    own, chosen = unique_model(), unique_model()
    from codedoctor.models import scripted

    scripted.register(chosen, [{"text": "答案来自用户这次选的模型"}])
    cfg = make_config({own: [{"text": "不该用到"}]})
    with TestClient(create_app(cfg, poll_s=0.05)) as client:
        sub = client.post("/tasks", json={"instructions": "看一下", "reasoning": "high",
                                          "model": {"endpoint": "fake", "model": chosen}}).json()
        for _ in range(300):
            r = client.get(f"/tasks/{sub['task_id']}/result").json()
            if r["settled"]:
                break
            time.sleep(0.02)
        assert r["answer"] == "答案来自用户这次选的模型"
        calls = client.app.state.daemon.s.models.client("fake").calls
        assert calls[-1]["model"] == chosen and calls[-1]["reasoning"] == "high"
        assert client.post("/tasks", json={"instructions": "x", "reasoning": "huge"}).status_code == 422


def test_a_single_agent_lists_its_anomalies_and_is_not_held_by_them(make_config):
    """Real Notepad test: the task was done, the answer said 被拦下 over small anomalies the agent had reported itself."""
    model = unique_model()
    cfg = make_config({model: [
        {"tool_calls": [{"name": "report_anomaly", "arguments": {
            "kind": "visual", "title": "窗口列表里同一个窗口出现两次", "observed": "list_windows 里重复", "surface": "small",
            "hypothesis": True}}]},
        {"text": "完成了"}]})
    with TestClient(create_app(cfg, poll_s=0.05)) as client:
        sub = client.post("/tasks", json={"instructions": "看一下"}).json()
        for _ in range(300):
            r = client.get(f"/tasks/{sub['task_id']}/result").json()
            if r["settled"]:
                break
            time.sleep(0.02)
        assert r["status"] == "完成" and r["answer"].startswith("完成了")
        assert "窗口列表里同一个窗口出现两次" in r["answer"]  # still listed in the answer, not dropped


def test_fix_with_codecut_runs_only_inside_the_projects_folder(project, tmp_path, monkeypatch, capsys):
    from codedoctor import video

    if video.home() is None:
        return
    config = _config(tmp_path, project, [{"text": "剪好了"}])
    home = tmp_path / "home"
    home.mkdir()
    (home / "projects.json").write_text(json.dumps([{"name": "shop-demo", "config": str(config), "root": str(project)}]),
                                        encoding="utf-8")
    monkeypatch.setenv("CODEDOCTOR_HOME", str(home))
    elsewhere = tmp_path / "videos"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)  # not in any project: the most recent one is NOT used for video work
    assert cli.main(["fix", "--with", "codecut", "--no-window", "剪一下"]) == 2
    assert "不在任何 Lumen 项目里" in capsys.readouterr().err
    monkeypatch.chdir(project)
    opened = []
    monkeypatch.setattr(video, "open_window", lambda folder: opened.append(folder) or True)
    assert cli.main(["fix", "--with", "codecut", "--no-window", "剪一下"]) == 0
    assert opened == []  # --no-window: called from CodeCut, whose window is already there
