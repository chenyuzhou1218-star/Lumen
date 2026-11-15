"""3D through Code3D (codedoctor/model3d.py): agents run scene.py in the user's own Blender, inside the project folder only.
A scene is code, so running one asks for what running code asks for. The last tests run the real Blender, and are skipped
where it is not installed."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import pytest

from codedoctor import mcp_bridge, model3d
from codedoctor.agents.daemon import Daemon
from codedoctor.agents.tools import TOOLS, ToolContext, execute, usable

needs_code3d = pytest.mark.skipif(model3d.home() is None, reason="Code3D is not installed")


def has_blender() -> bool:
    if model3d.home() is None:
        return False
    sys.path.insert(0, str(model3d.home()))
    try:
        import code3d as core

        return core.find_blender() is not None
    finally:
        sys.path.pop(0)


needs_blender = pytest.mark.skipif(not has_blender(), reason="Blender is not installed")


def ctx(d, role="worker"):
    return ToolContext(services=d.s, agent_id="doctor", role=role, task_id="task_x", model={}, call_entry_id="jrn_x",
                       thread_id="thr_x", known_agents=set())


def daemon(make_config, write=True, commands="allowlist"):
    return Daemon(make_config(permissions={"run_command": commands, "write_files": write, "command_allowlist": ["python"]}))


@needs_code3d
def test_only_a_task_with_at_code3d_gets_the_tools(make_config, project):
    d = daemon(make_config)
    rt = d.agents["doctor"]
    plain = d.submit_task("doctor", "fix", "the cart total is wrong")["task_id"]
    cut = d.submit_task("doctor", "cut", "cut the intro", tools=["codecut"])["task_id"]
    model = d.submit_task("doctor", "make", "make a chair", tools=["code3d"])["task_id"]
    assert not set(model3d.NAMES) & set(rt._task_tools(plain))
    assert not set(model3d.NAMES) & set(rt._task_tools(cut))  # one toolset does not bring the other
    assert set(model3d.NAMES) <= set(rt._task_tools(model))
    assert not {"video_edit", "video_render"} & set(rt._task_tools(model))
    assert not [n for n in rt._task_tools(model) if n.startswith("graph_")]


@needs_code3d
@pytest.mark.parametrize("write,commands", [(False, "allowlist"), (True, "deny")])
def test_old_switches_no_longer_stop_a_scene(make_config, project, write, commands):
    """The user's rule: no permission switches; running a scene is offered whatever an old file says."""
    d = daemon(make_config, write=write, commands=commands)
    assert usable("code3d_project", d.s.config, "guardian") and usable("code3d_run", d.s.config, "worker")
    d.submit_task("doctor", "make", "make a chair", tools=["code3d"])  # engines get the tools from the bridge


@needs_code3d
def test_paths_outside_the_project_are_allowed(make_config, project):
    """The user's rule: no sandbox; a scene may live anywhere on the computer."""
    d = daemon(make_config)
    res = execute(TOOLS["code3d_run"], ctx(d), {"action": "init", "project": "../elsewhere"})
    assert res.ok and "\"ok\": true" in res.content
    assert (project.parent / "elsewhere").is_dir()


def test_the_tool_server_offers_them_only_when_called_in(tmp_path):
    assert any("code3d_run" in n for n in mcp_bridge.tool_names(["code3d"]))
    assert not any("code3d" in n for n in mcp_bridge.tool_names(["codecut"]))
    calls = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
    out = io.StringIO()
    mcp_bridge.serve(tmp_path, ["code3d"], stdin=iter(json.dumps(c) + "\n" for c in calls), stdout=out)
    assert {t["name"] for t in json.loads(out.getvalue())["result"]["tools"]} == set(model3d.NAMES)


def test_the_message_box_knows_it(monkeypatch):
    from codedoctor.desktop import composer

    monkeypatch.setattr(model3d, "home", lambda: model3d.Path("."))
    assert "code3d" in composer.mentionable() and composer.MENTIONS["code3d"] == "Code3D"
    assert composer.MENTION_RE.search("做把椅子 @Code3D").group(1).lower() == "code3d"


def test_spark_is_the_one_who_makes_it():
    from codedoctor.agents import team

    assert [m.id for m in team.MEMBERS if "code3d_run" in m.tools] == ["spark", "torch", "beacon"]
    prompt = team.engine_prompt("spark", "p", ["lumen", "spark"], (), "", tuple(team.BY_ID["spark"].tools), [])
    assert "code3d_run" in prompt and "Work from the picture" in prompt


@needs_blender
def test_a_scene_from_code_to_a_picture_the_model_sees(make_config, project):
    """The real thing: a project, a broken line, the fix, a render that comes back as a picture, a model file."""
    d = daemon(make_config)

    def run(tool="code3d_run", **args):
        return execute(TOOLS[tool], ctx(d), args)

    assert run(action="init", project="chair", width=320, height=180, samples=4).ok
    scene = project / "chair" / "scene.py"
    scene.write_text("import c3d\nc3d.sky()\nc3d.sphere(.5, mat='nope')\n", encoding="utf-8")
    assert run("code3d_project", action="check", project="chair").ok  # the name of a preset is only known when it runs
    bad = run(action="render", project="chair", timeout_s=120)
    assert not bad.ok and '"line": 3' in bad.content and "no preset" in bad.content
    scene.write_text("import c3d\nc3d.sky()\nc3d.ground()\nc3d.sphere(.5, at=(0,0,.5), mat='gold')\nc3d.camera()\n", encoding="utf-8")
    good = run(action="render", project="chair", timeout_s=120)
    assert good.ok and good.images and good.evidence
    assert json.loads(good.content.partition("\n")[2])["output"] == "chair/out/camera.png"
    assert model3d.change_line({"action": "render", "project": "chair"}, good) == "chair：渲染"
    look = run("code3d_project", action="look", project="chair")
    assert look.ok and look.images
    glb = run(action="export", project="chair", format="glb", timeout_s=120)
    assert glb.ok and (project / "chair" / "out" / "chair.glb").stat().st_size > 1000


@needs_blender
def test_a_scene_cannot_leave_its_folder(make_config, project, tmp_path):
    d = daemon(make_config)
    assert execute(TOOLS["code3d_run"], ctx(d), {"action": "init", "project": "bad"}).ok
    outside = Path.home() / "code3d-must-not-exist.txt"
    for code in (f"open(r'{outside}', 'w').write('x')\n", "import subprocess\nsubprocess.run(['cmd', '/c', 'echo'])\n",
                 "import socket\nsocket.create_connection(('example.com', 80))\n"):
        (project / "bad" / "scene.py").write_text(code, encoding="utf-8")
        res = execute(TOOLS["code3d_run"], ctx(d), {"action": "objects", "project": "bad", "timeout_s": 90})
        assert not res.ok and "Refused" in res.content
    assert not outside.exists()


@needs_blender
def test_nothing_is_exported_that_nobody_looked_at(make_config, project):
    """A real run: the team exported a scene with a black window; none of them had rendered it once."""
    d = daemon(make_config)

    def run(**args):
        return execute(TOOLS["code3d_run"], ctx(d), args)

    assert run(action="init", project="p", width=160, height=90).ok
    assert "looked at" in run(action="export", project="p", format="obj", timeout_s=60).content
    assert "looked at" in run(action="render", project="p", quality="final", timeout_s=60).content
    assert run(action="render", project="p", quality="check", timeout_s=90).ok
    assert run(action="export", project="p", format="obj", timeout_s=60).ok
    (project / "p" / "scene.py").write_text((project / "p" / "scene.py").read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert "looked at" in run(action="export", project="p", format="obj", timeout_s=60).content  # another version


def test_those_who_judge_are_told_to_judge_the_picture():
    from codedoctor.agents import team

    for who in ("beacon", "torch"):
        assert "code3d_run" in team.BY_ID[who].tools
        prompt = team.engine_prompt(who, "p", ["lumen", who], (), "", tuple(team.BY_ID[who].tools), [])
        assert "judge the picture" in prompt
    assert "at least three rounds" in team.engine_prompt("spark", "p", ["lumen", "spark"], (), "", tuple(team.BY_ID["spark"].tools), [])


def test_the_answer_shows_the_picture_the_team_made(tmp_path):
    out = tmp_path / "cafe" / "out"
    out.mkdir(parents=True)
    assert model3d.result_picture(tmp_path) is None
    (out / "latest.png").write_bytes(b"x")
    assert model3d.result_picture(tmp_path).name == "latest.png"
    (out / "final.png").write_bytes(b"x")
    assert model3d.result_picture(tmp_path).name == "final.png"
    assert model3d.result_picture(tmp_path, since=(out / "final.png").stat().st_mtime + 60) is None, "nothing from before this question"


def test_the_notes_come_first_and_a_street_is_one_thing(tmp_path):
    parts = [{"name": f"lit window.{i}", "size": [1, 1, 1]} for i in range(900)]
    res = {"ok": True, "output": str(tmp_path / "out" / "camera.png"), "scene": {"objects": parts, "things": [{"name": "street", "parts": 900}]}, "warnings": ["too dark"]}
    short = model3d._short(res, tmp_path)
    text = json.dumps(short)
    assert text.index("too dark") < text.index("street") and len(text) < 400
    assert short["output"] == "out/camera.png"
    assert model3d._short({"ok": True, "objects": parts[:2]}, tmp_path)["objects"], "an old Code3D still shows its list"
