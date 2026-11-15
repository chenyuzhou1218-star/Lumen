"""The making tools (codedoctor/makers.py and tools/<id>): what can be checked without a model, Blender or a browser."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from codedoctor import makers, video
from codedoctor.agents.daemon import Daemon

TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools"


def have(tool: str) -> bool:
    return (TOOLS_DIR / tool / f"{tool}.py").is_file()


def run(tool: str, *args: str, cwd=None) -> dict:
    out = subprocess.run([video.python(), str(TOOLS_DIR / tool / f"{tool}.py"), *args], capture_output=True, cwd=cwd, env={"PYTHONIOENCODING": "utf-8", **__import__("os").environ})
    return json.loads(out.stdout.decode("utf-8").strip().splitlines()[-1])


def test_every_maker_can_be_called_in():
    assert set(makers.IDS) <= set(video.TOOLSETS)


@pytest.mark.parametrize("tool", makers.IDS)
def test_a_message_can_call_in_each_tool(make_config, project, tool):
    """The list of allowed tools also stands in the message schema: a window that offers @CodeSound once only said 提交失败."""
    if makers.home(tool) is None:
        pytest.skip("not here")
    d = Daemon(make_config(permissions={"run_command": "allowlist", "write_files": True, "command_allowlist": ["python"]}))
    task = d.submit_task("doctor", "make", "make something", tools=[tool])["task_id"]
    assert set(makers.NAMES) <= set(d.agents["doctor"]._task_tools(task))
    plain = d.submit_task("doctor", "fix", "the cart total is wrong")["task_id"]
    assert not set(makers.NAMES) & set(d.agents["doctor"]._task_tools(plain))


@pytest.mark.skipif(not have("codetools"), reason="CodeTools is not here")
def test_every_plugin_runs_on_its_sample():
    res = run("codetools", "check")
    assert res["ok"], res.get("error")
    assert res["plugins"] >= 30


@pytest.mark.skipif(not have("codetools"), reason="CodeTools is not here")
def test_a_plugin_runs_through_the_bridge_and_stays_in_the_project(make_config, project):
    from codedoctor.agents.tools import TOOLS, ToolContext, execute

    d = Daemon(make_config(permissions={"run_command": "allowlist", "write_files": True, "command_allowlist": ["python"]}))
    ctx = ToolContext(services=d.s, agent_id="doctor", role="worker", task_id="task_x", model={}, call_entry_id="jrn_x", thread_id="thr_x", known_agents=set())
    res = execute(TOOLS["maker_run"], ctx, {"tool": "codetools", "action": "plugin", "project": "made", "plugin": "qr", "plugin_action": "make", "args": {"text": "hello"}})
    assert res.ok and res.images, res.content
    res = execute(TOOLS["maker_run"], ctx, {"tool": "codetools", "action": "plugin", "project": "made", "plugin": "disk", "plugin_action": "map", "args": {"folder": "../.."}})
    assert not res.ok and "outside" in res.content


@pytest.mark.skipif(not have("codefilm"), reason="CodeFilm is not here")
def test_a_sentence_becomes_a_storyboard_without_invented_words(tmp_path):
    res = run("codefilm", "plan", str(tmp_path / "f"), "--idea", "做一个30秒的古风宣传片《山河》")
    assert res["ok"] and res["style"] == "古风" and res["seconds"] == 30
    film = json.loads((tmp_path / "f" / "film.json").read_text(encoding="utf-8"))
    assert film["title"] == "山河" and all(not s["say"] for s in film["shots"]) and res["warnings"]
    assert run("codefilm", "check", str(tmp_path / "f"))["ok"]


def test_a_log_reader_never_gets_start_or_stop():
    assert makers.MAKERS["codelab"].runs == ()
    assert not makers.needs_running(["codelab"])


@pytest.mark.skipif(not have("codesound"), reason="CodeSound is not here")
def test_a_short_song_renders_and_is_measured(tmp_path):
    folder = tmp_path / "song"
    assert run("codesound", "init", str(folder))["ok"]
    (folder / "song.py").write_text("import cs\ncs.song(tempo=120, key='C major')\np = cs.track('piano')\nwith cs.section('a', 2):\n    p.tune('1 2 3 5 | 5:4')\n", encoding="utf-8")
    res = run("codesound", "render", str(folder))
    assert res["ok"], res
    assert (folder / "out" / "latest.wav").stat().st_size > 10000
    assert res["measured"]["seconds"] > 4
    assert (folder / "out" / "latest.png").is_file()


@pytest.mark.skipif(not have("codesound"), reason="CodeSound is not here")
def test_a_bar_that_does_not_add_up_is_reported(tmp_path):
    folder = tmp_path / "song"
    run("codesound", "init", str(folder))
    (folder / "song.py").write_text("import cs\ncs.song()\np = cs.track('piano')\nwith cs.section('a', 2):\n    p.tune('1 2 3 | 5:4')\n", encoding="utf-8")
    assert any("3 拍" in w for w in run("codesound", "score", str(folder))["warnings"])


@pytest.mark.skipif(not have("codepage"), reason="CodePage is not here")
def test_a_page_builds_from_data_alone(tmp_path):
    folder = tmp_path / "site"
    assert run("codepage", "init", str(folder))["ok"]
    page = json.loads((folder / "page.json").read_text(encoding="utf-8"))
    page["blocks"] = [{"id": "a", "type": "search-pill", "values": {"hint": "找<东西>"}}, {"id": "b", "type": "row2", "children": [[{"id": "c", "type": "heading"}], []]}]
    (folder / "page.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    assert run("codepage", "build", str(folder))["ok"]
    html = (folder / "out" / "index.html").read_text(encoding="utf-8")
    assert "找&lt;东西&gt;" in html and "cp-row-2" in html and "data-node" not in html


@pytest.mark.skipif(not have("codedata"), reason="CodeData is not here")
def test_data_is_looked_at_and_the_numbers_repeat(tmp_path):
    folder = tmp_path / "sales"
    assert run("codedata", "init", str(folder))["ok"]
    (folder / "data.csv").write_text("地区,销售额\n华东,10\n华北,5\n华东,3\n华东,3\n", encoding="utf-8")
    assert any("一模一样" in w for w in run("codedata", "look", str(folder))["files"][0]["warnings"])
    (folder / "analysis.py").write_text("import cd\nt = cd.read('data.csv')\nby = t.group('地区', sum='销售额')\ncd.say('合计', evidence=by)\ncd.table(by)\n", encoding="utf-8")
    assert run("codedata", "run", str(folder))["ok"]
    assert "16" in (folder / "out" / "report.html").read_text(encoding="utf-8")
    assert run("codedata", "recheck", str(folder))["ok"]


@pytest.mark.skipif(not have("codelab"), reason="CodeLab is not here")
def test_a_log_is_read_and_nan_is_called_out(tmp_path):
    log = tmp_path / "train.log"
    log.write_text("\n".join(f"step {i}/100 loss: {1 / (i + 1):.4f}" for i in range(50)) + "\nstep 50/100 loss: nan\n", encoding="utf-8")
    res = run("codelab", "watch", str(log), cwd=tmp_path)
    assert res["ok"] and res["progress_percent"] == 50.0
    assert any("NaN" in w for w in res["warnings"])
