"""Video editing through CodeCut (codedoctor/video.py): agents edit and render with CodeCut's command line, inside the
project folder only. The CodeCut tests run the real program and are skipped where it is not installed."""

from __future__ import annotations

import json
import shutil

import pytest

from codedoctor import video
from codedoctor.agents.daemon import Daemon
from codedoctor.agents.tools import TOOLS, ToolContext, execute, usable

needs_codecut = pytest.mark.skipif(video.home() is None, reason="CodeCut is not installed")


def ctx(d, role="worker"):
    return ToolContext(services=d.s, agent_id="doctor", role=role, task_id="task_x", model={}, call_entry_id="jrn_x",
                       thread_id="thr_x", known_agents=set())


def daemon(make_config, write=True):
    return Daemon(make_config(permissions={"run_command": "deny", "write_files": write}))


def media(project):
    """A 2-second test clip from CodeCut's own FFmpeg."""
    ff = video.home() / "tools" / "ffmpeg.exe"
    if not ff.is_file():
        ff = shutil.which("ffmpeg")
        if not ff:
            pytest.skip("no ffmpeg")
    import subprocess

    (project / "media").mkdir(exist_ok=True)
    subprocess.run([str(ff), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(project / "media" / "clip.mp4")], check=True)


def test_only_an_investigation_started_with_at_codecut_gets_the_video_tools(make_config, project):
    """Video tools only with @CodeCut; the user's rule: no read-only members, so rendering is never switched off."""
    d = daemon(make_config)
    rt = d.agents["doctor"]
    plain = d.submit_task("doctor", "fix", "the cart total is wrong")["task_id"]
    video_task = d.submit_task("doctor", "cut", "cut the intro to 5 s", tools=["codecut"])["task_id"]
    assert not set(video.NAMES) & set(rt._task_tools(plain))  # code work: no video tools, no tokens spent on them
    if video.home() is None:
        assert not set(video.NAMES) & set(rt._task_tools(video_task))
        return
    assert set(video.NAMES) <= set(rt._task_tools(video_task))
    assert not [n for n in rt._task_tools(video_task) if n.startswith("graph_")]  # the code graph says nothing about a cut
    assert any(n.startswith("graph_") for n in rt._task_tools(plain))
    with pytest.raises(KeyError):
        d.submit_task("doctor", "x", "y", tools=["photoshop"])
    ro = daemon(make_config, write=False)  # the user's rule: no read-only members, so an old switch stops no render
    assert usable("video_project", ro.s.config, "guardian") and usable("video_render", ro.s.config, "worker")


def test_at_codecut_sent_to_a_head_goes_to_a_worker(make_config, project):
    from codedoctor import video as v

    cfg = make_config(permissions={"run_command": "deny", "write_files": True})
    import types

    agents = {"head-dispatch": types.SimpleNamespace(role="head_dispatch", watched=()),
              "worker-1": types.SimpleNamespace(role="worker", watched=()),
              "worker-2": types.SimpleNamespace(role="worker", watched=()),
              "guardian-2": types.SimpleNamespace(role="guardian", watched=("worker-2",), id="guardian-2")}
    for k, a in agents.items():
        a.id = k
    fake = types.SimpleNamespace(agents=agents)
    assert v.hands(fake, "head-dispatch") == "worker-2"  # the worker with a guardian
    assert v.hands(fake, "worker-1") == "worker-1"
    assert cfg is not None


def test_paths_outside_the_project_are_allowed(make_config, project):
    """The user's rule: no sandbox; a cut may be saved anywhere on the computer."""
    d = daemon(make_config)
    res = execute(TOOLS["video_edit"], ctx(d), {"action": "init", "project": "../elsewhere.json"})
    assert res.ok and (project.parent / "elsewhere.json").is_file()


@needs_codecut
def test_an_agent_cuts_titles_speeds_up_and_renders(make_config, project):
    d = daemon(make_config)
    media(project)
    run = lambda tool, **a: execute(TOOLS[tool], ctx(d), a)  # noqa: E731
    assert run("video_edit", action="init", project="cut.json", width=320, height=180, fps=24).ok
    res = run("video_edit", action="add", project="cut.json", kind="video", source="media/clip.mp4", clip="main")
    assert res.ok, res.content
    res = run("video_edit", action="split", project="cut.json", clip="main", time=1)
    assert res.ok, res.content
    right = json.loads(res.content.partition("\n")[2])["right"]
    assert run("video_edit", action="update", project="cut.json", clip=right, fields={"speed": 2, "fade_out": 0.2}).ok
    assert run("video_edit", action="text", project="cut.json", text="你好", start=0, duration=1, clip="title").ok
    listed = json.loads(run("video_project", action="list", project="cut.json").content.partition("\n")[2])
    assert [s["id"] for s in listed["project"]["scenes"]] == ["main", right]
    assert listed["project"]["texts"][0]["id"] == "title" and abs(listed["duration"] - 1.5) < 0.05
    bad = run("video_edit", action="split", project="cut.json", clip="nope", time=1)
    assert not bad.ok and "not found" in bad.content
    res = run("video_render", project="cut.json", output="out/final.mp4")
    assert res.ok, res.content
    # a run of CodeCut is evidence a finding can cite (a real run: the guardian's claims were refused without it)
    assert res.evidence and res.evidence[0].startswith("ev:test:") and res.content.startswith("evidence: ev:test:")
    record = d.s.evidence.content(res.evidence[0]).decode("utf-8")
    assert record.startswith("$ codecut render cut.json -o out/final.mp4") and '"ok": true' in record
    assert video.change_line("video_render", {"project": "cut.json", "output": "out/final.mp4"}, res) == "导出 out/final.mp4（1.5 秒）"
    assert (project / "out" / "final.mp4").stat().st_size > 1000
    again = run("video_render", project="cut.json", output="out/final.mp4")
    assert not again.ok  # an existing output is kept unless overwrite=true


def test_the_hands_report_names_each_edit():
    from codedoctor.agents.tools import ToolResult

    ok = ToolResult(ok=True, content='evidence: ev:test:x\n{"ok": true, "left": "v", "right": "w"}')
    assert video.change_line("video_edit", {"action": "split", "project": "cut.json", "clip": "v", "time": 3}, ok) == \
        "cut.json：分割片段 v 于 3 秒"
    assert video.change_line("video_edit", {"action": "text", "project": "cut.json", "text": "你好"}, ok) == "cut.json：加字幕 “你好”"
    assert video.change_line("video_edit", {"action": "update", "project": "cut.json", "clip": "w",
                                            "fields": {"speed": 2}}, ok) == 'cut.json：修改片段 w：{"speed": 2}'
    bad = ToolResult(ok=False, content='ERROR: evidence: ev:test:y\n{"ok": false, "error": "Clip not found: z"}')
    assert "失败" in video.change_line("video_edit", {"action": "remove", "project": "cut.json", "clip": "z"}, bad)
