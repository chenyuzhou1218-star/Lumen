"""Fixes for the bugs confirmed on 2026-11-10 (report: trials/haiku-check-2026-11-10/REPORT.md). Each test
reproduces one bug: it failed before its fix. Scripted models only; nothing here calls a real model or the network."""

from __future__ import annotations

import asyncio
import os
import threading
import time

import pytest

from conftest import unique_model

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---- item 2: voice × after send ------------------------------------------------------------------------------------
@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_2_cancel_while_writing_out_sends_nothing(qapp, monkeypatch):
    from codedoctor.desktop import voice, voice_bar

    monkeypatch.setattr(voice.Recorder, "start", lambda self: None)
    monkeypatch.setattr(voice.Recorder, "stop", lambda self: b"\0" * 32000)
    monkeypatch.setattr(voice, "transcribe", lambda pcm, language="zh": (time.sleep(0.3), "一句话")[1])
    bar = voice_bar.VoiceBar()
    got = []
    bar.text.connect(lambda t, send: got.append((t, send)))
    bar.begin()
    bar.send_btn.click()   # ↑: sent once written out
    bar.cancel.click()     # ×: pressed while it is being written out
    deadline = time.time() + 5
    while time.time() < deadline and bar.busy:
        qapp.processEvents()
        time.sleep(0.02)
    qapp.processEvents()
    assert got == [] and not bar.busy


# ---- item 4 (Qt box): a refused send gives the words and files back ---------------------------------------------------
def test_4_refused_send_puts_words_and_files_back(qapp):
    from codedoctor.desktop.composer import Composer

    box = Composer([("agent", "Agent", "")])
    box.edit.setPlainText("一大段我写了很久的话")
    box.attached = [("notes.txt", "附件内容")]
    box._show_attached()
    box.send.connect(lambda text, agent: box.give_back())  # what MainWindow.submit does when the service refuses
    box._send()
    assert box.edit.toPlainText() == "一大段我写了很久的话"
    assert [n for n, _ in box.attached] == ["notes.txt"]


def test_4_accepted_send_clears_the_box(qapp):
    from codedoctor.desktop.composer import Composer

    box = Composer([("agent", "Agent", "")])
    box.edit.setPlainText("发出去的话")
    box.attached = [("notes.txt", "附件内容")]
    sent = []
    box.send.connect(lambda text, agent: sent.append(text))
    box._send()
    assert sent and "发出去的话" in sent[0] and box.edit.toPlainText() == "" and box.attached == []


# ---- item 5: a submit the window gave up on is not created later ----------------------------------------------------
def test_5_a_command_the_window_gave_up_on_never_runs(monkeypatch):
    import asyncio as _asyncio

    from codedoctor.backend import Backend

    b = Backend.__new__(Backend)  # the loop thread only, without starting a service
    b.loop = _asyncio.new_event_loop()
    threading.Thread(target=b.loop.run_forever, daemon=True).start()
    b.RUN_WAIT_S = 0.3
    ran = []
    b.loop.call_soon_threadsafe(time.sleep, 1.0)  # the service loop is busy for a while
    with pytest.raises(TimeoutError):
        b.run(lambda: ran.append("task created"))
    time.sleep(1.5)  # the busy loop finishes
    assert ran == []
    b.loop.call_soon_threadsafe(b.loop.stop)


def test_5_a_command_that_answers_in_time_returns_its_value():
    from codedoctor.backend import Backend

    b = Backend.__new__(Backend)
    import asyncio as _asyncio
    b.loop = _asyncio.new_event_loop()
    threading.Thread(target=b.loop.run_forever, daemon=True).start()
    assert b.run(lambda x: {"task_id": x}, "t1") == {"task_id": "t1"}
    b.loop.call_soon_threadsafe(b.loop.stop)


# ---- verdict: failing tests are only called "failed before" when the baseline shows them ----------------------------
def test_verdict_says_before_only_when_every_failure_is_in_the_baseline():
    from codedoctor.changes import verdict

    def info(**last):
        return {"files": {"a": 1}, "last": {"exit_code": 1, "summary": "1 failed, 5 passed", "regressions": [], "open": [], **last}}

    known = verdict(info(failed=["t/a.py::old"], baseline_failed=["t/a.py::old"]))
    assert known[1] == "amber" and "在这次修改之前就没过" in known[0]
    new = verdict(info(failed=["t/a.py::old", "t/b.py::x"], baseline_failed=["t/a.py::old"]))
    assert new[1] == "amber" and "在这次修改之前" not in new[0]
    no_record = verdict(info())
    assert no_record[1] == "amber" and "在这次修改之前" not in no_record[0]
    crash = verdict(info(failed=["<the test run itself: boom>"], baseline_failed=[]))
    assert "在这次修改之前" not in crash[0]
    assert verdict(info(exit_code=0, summary="5 passed"))[1] == "green"


# ---- item 7: the test baseline survives a restart ------------------------------------------------------------------
def test_7_baseline_is_kept_across_a_restart(make_config, project):
    import sys

    from codedoctor.agents import testrun
    from codedoctor.services import Services

    (project / "test_shop.py").write_text("def test_buy():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    cmd = f"{sys.executable.replace(chr(92), '/')} -m pytest -q -p no:cacheprovider"
    cfg = make_config({}, permissions={"test_command": cmd, "write_files": True, "run_command": "allowlist",
                                       "command_allowlist": ["python"]})
    s1 = Services.open(cfg)
    testrun.baseline(s1, "task_R", root=None)
    (project / "test_shop.py").write_text("def test_buy():\n    assert 1 + 1 == 3\n", encoding="utf-8")
    assert testrun.check(s1, "task_R", "doctor").regressions
    s1.db.close()
    s2 = Services.open(cfg)  # the service restarts and carries on
    try:
        assert testrun.check(s2, "task_R", "doctor").regressions == {"test_shop.py::test_buy"}
    finally:
        s2.db.close()


# ---- item 6: a second window on the same folder says so ------------------------------------------------------------
def test_6_second_window_is_told_its_chats_are_apart(tmp_path):
    import dataclasses
    from pathlib import Path

    from codedoctor.desktop.launcher import another_window, second_window
    from codedoctor.store.lock import AlreadyRunning

    @dataclasses.dataclass
    class Cfg:
        data_dir: Path

    seen = []

    def factory(cfg):
        seen.append(cfg.data_dir)
        if len(seen) == 1:
            raise AlreadyRunning("taken")
        return "backend"

    cfg2, _ = another_window(Cfg(tmp_path / "data"), factory)
    assert second_window(cfg2) and second_window(Cfg(tmp_path / "data")) is False


# ---- items 8 and 12: the quick chat obeys the endpoint's data level, and 停止 stops it -----------------------------
def test_8_quick_chat_does_not_send_above_the_endpoint_level(make_config):
    from codedoctor.agents.daemon import Daemon
    from codedoctor.models import scripted

    model = "chat-level-model"
    scripted.register(model, [{"text": "你好呀"}])
    cfg = make_config(endpoints=[{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True,
                                  "max_data_class": "internal"}], code_data_class="confidential",
                      agents=[{"id": "doctor", "role": "general", "endpoint": "fake", "model": model}])

    async def run():
        d = Daemon(cfg, poll_s=0.05)
        await d.start()
        try:
            sub = d.submit_task("doctor", "你好", "你好")
            rep = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
            return rep["body"]["outcome"], d.s.models.client("fake").calls
        finally:
            await d.halt()

    outcome, calls = asyncio.run(run())
    assert calls == [] and outcome == "failed"


def test_12_stop_on_a_quick_chat_gives_no_answer(make_config):
    from codedoctor.agents.daemon import Daemon
    from codedoctor.models import scripted

    model = "chat-stop-model"
    scripted.register(model, [{"text": "你好呀"}])
    cfg = make_config({model: [{"text": "你好呀"}]})

    async def run():
        d = Daemon(cfg, poll_s=0.05)
        await d.start()
        try:
            sub = d.submit_task("doctor", "你好", "你好")
            d.control("doctor", "stop")  # the person presses 停止 right away
            rep = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
            return rep["body"]["outcome"], d.s.models.client("fake").calls
        finally:
            await d.halt()

    outcome, calls = asyncio.run(run())
    assert outcome == "cancelled" and calls == []


# ---- item 10: a follow-up sent while the answer is still coming sees that answer ----------------------------------
def test_10_followup_sent_before_the_answer_sees_it(make_config):
    from codedoctor.agents.daemon import Daemon
    from codedoctor.models import scripted

    model = "followup-model"
    scripted.register(model, [{"text": "答案一：是 42"}, {"text": "好的，第二个也是 42"}])
    cfg = make_config({model: [{"text": "答案一：是 42"}, {"text": "好的，第二个也是 42"}]})

    async def run():
        d = Daemon(cfg, poll_s=0.05)
        await d.start()
        try:
            first = d.submit_task("doctor", "问题一", "第一个问题是什么")
            second = d.submit_task("doctor", "问题二", "那第二个呢", chat_of=first["task_id"])  # sent before the answer
            await asyncio.wait_for(d.wait_for_report(second["task_id"]), 10)
            return d.s.models.client("fake").calls
        finally:
            await d.halt()

    calls = asyncio.run(run())
    assert len(calls) == 2 and "答案一" in str(calls[1]["messages"])
    assert "(no answer yet)" not in str(calls[1]["messages"])


# ---- item 11: a key that cannot be removed is reported, not called "saved" -------------------------------------------
class _FakeKeyring:
    def __init__(self, stored=None, fail_delete=False):
        self.stored, self.fail_delete = stored, fail_delete

    def get_password(self, service, account):
        return self.stored

    def delete_password(self, service, account):
        if self.fail_delete:
            raise RuntimeError("Credential Manager refused")
        self.stored = None


def test_11_failed_delete_is_raised(monkeypatch):
    from codedoctor import secrets

    monkeypatch.setattr(secrets, "_keyring", lambda: _FakeKeyring(stored="old-key", fail_delete=True))
    with pytest.raises(RuntimeError):
        secrets.delete_key("ep1")


def test_11_delete_removes_a_stored_key_and_is_quiet_when_none(monkeypatch):
    from codedoctor import secrets

    kr = _FakeKeyring(stored="old-key")
    monkeypatch.setattr(secrets, "_keyring", lambda: kr)
    secrets.delete_key("ep1")
    assert kr.stored is None
    secrets.delete_key("ep1")  # nothing stored any more: no error


# ---- item 13: the default "npm test" starts on Windows -------------------------------------------------------------
def test_13_npm_is_found_by_its_full_path(monkeypatch):
    import shutil

    from codedoctor.agents import testrun

    monkeypatch.setattr(shutil, "which", lambda name: "C:/Program Files/nodejs/npm.CMD" if name == "npm" else None)
    assert testrun._argv("npm test") == ["C:/Program Files/nodejs/npm.CMD", "test"]
    assert testrun._argv("python -m pytest") [0] == "python"  # not on PATH here: left as it was


def test_13_npm_test_really_runs_when_npm_is_installed(make_config, project):
    import json as _json
    import shutil

    from codedoctor.agents import testrun
    from codedoctor.services import Services

    if shutil.which("npm") is None:
        pytest.skip("npm is not installed on this machine")
    (project / "package.json").write_text(_json.dumps({"name": "x", "scripts": {"test": "node -e \"process.exit(0)\""}}), encoding="utf-8")
    s = Services.open(make_config({}, permissions={"test_command": "npm test", "write_files": True, "run_command": "allowlist",
                                                   "command_allowlist": ["npm"]}))
    try:
        res = testrun.run(s, root=project)
    finally:
        s.db.close()
    assert res.ran and res.exit_code == 0, res.output


# ---- item 14: `codedoctor fix` that runs out of time does not exit 0 ------------------------------------------------
def test_14_fix_that_times_out_exits_nonzero(make_config, monkeypatch):
    import asyncio as _asyncio

    from codedoctor import cli, interface
    from codedoctor.models import scripted

    model = "fix-timeout-model"
    scripted.register(model, [{"text": "好了"}])
    cfg = make_config({model: [{"text": "好了"}]})
    monkeypatch.setattr(interface, "settled", lambda services, task_id: False)  # reviews still running
    monkeypatch.setattr(interface, "result", lambda services, task_id: {"outcome": "done", "tests": {"level": "green"}})
    monkeypatch.setattr(cli, "_print_result", lambda r, as_json=False: None)
    code = _asyncio.run(cli._fix(cfg, "doctor", "检查一下", 0.3, True, None))
    assert code != 0


# ---- item 16: "继续执行" after the step limit really continues --------------------------------------------------------
def test_16_resume_after_the_step_limit_makes_progress(make_config):
    from codedoctor.agents.daemon import Daemon
    from codedoctor.models import scripted

    model = "resume-budget-model"
    turns = [{"tool_calls": [{"name": "read_file", "arguments": {"path": "server/shop.py", "start_line": i}}]} for i in range(1, 4)]
    scripted.register(model, turns + [{"text": "做完了"}])
    cfg = make_config({model: turns + [{"text": "做完了"}]}, defaults={"budget": {"max_steps": 3}, "stall_steps": 9})

    async def run():
        d = Daemon(cfg, poll_s=0.05)
        await d.start()
        try:
            sub = d.submit_task("doctor", "t", "go")
            first = await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
            d.control("doctor", "resume_task", task_id=sub["task_id"])
            for _ in range(400):
                reports = [m for m in d.s.bus.list(task_id=sub["task_id"]) if m["kind"] == "report"]
                if len(reports) >= 2:
                    break
                await asyncio.sleep(0.02)
            return first["body"]["outcome"], [r["body"]["outcome"] for r in reports], len(d.s.models.client("fake").calls)
        finally:
            await d.halt()

    first, outcomes, calls = asyncio.run(run())
    assert first == "budget_exhausted"
    assert outcomes[-1] == "done" and calls == 4  # the resumed run asked the model again and finished


# ---- item 17: a tab Ray's page opens is the one Ray reads -----------------------------------------------------------
def test_17_ray_follows_a_tab_its_page_opens(qapp):
    from codedoctor.desktop.browser import BrowserPage

    page = BrowserPage()
    page.ensure()
    ray = page._agent()
    tab = ray.createWindow(None)  # what a target=_blank link in Ray's page asks for
    assert page.agent_view is tab and page.agent_view is not ray


# ---- item 18: a local address with a port is http, not https ---------------------------------------------------------
@pytest.mark.parametrize("text, url", [
    ("127.0.0.1:8080", "http://127.0.0.1:8080"),
    ("127.0.0.1:8080/x", "http://127.0.0.1:8080/x"),
    ("127.0.0.1", "http://127.0.0.1"),
    ("localhost:3000", "http://localhost:3000"),
    ("example.com", "https://example.com"),
    ("example.com:8443", "https://example.com:8443"),
])
def test_18_local_addresses_are_http(text, url):
    from codedoctor.desktop.browser import typed_url

    assert typed_url(text) == url


# ---- item 19: a changed embedding length brings the old notes back into meaning search ---------------------------
def test_19_old_notes_are_embedded_again_when_the_length_changes(make_config):
    from codedoctor.models import scripted
    from codedoctor.services import Services

    model = unique_model("embdim")
    state = {"dim": 7}
    scripted.register_embedder(model, lambda text: [1.0] + [0.0] * (state["dim"] - 1))
    cfg = make_config(endpoints=[{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True},
                                 {"id": "emb", "kind": "scripted", "base_url": "scripted:", "local": True}],
                      memory={"embedding": {"endpoint": "emb", "model": model}})
    s = Services.open(cfg)
    try:
        src = [s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]
        old = s.notes.write(owner="doctor", scope="project", kind="fact", sources=src, text="old note about reward twice")
        asyncio.run(s.vectors.index_pending())
        state["dim"] = 8  # the same model name now answers with a longer vector
        s.notes.write(owner="doctor", scope="project", kind="fact", sources=src, text="new note about gold")
        found = asyncio.run(s.vectors.search("reward", reader="doctor", include_shared=True, data_class="internal"))
        assert old["id"] in found
    finally:
        s.db.close()


# ---- item 20: a conclusion's id finds the notes that cite it ---------------------------------------------------------
def test_20_a_claim_id_finds_its_notes(make_config):
    from codedoctor.services import Services

    s = Services.open(make_config())
    try:
        src = [s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]
        note = s.notes.write(owner="doctor", scope="project", kind="fact", sources=src,
                             text="Gold price check was verified", claims=["clm_01J8ZQ7K3M9R2T5V6W8X0Y1Z2A"])
        for query in ("clm_01J8ZQ7K3M9R2T5V6W8X0Y1Z2A", "clm_01j8zq7k3m9r2t5v6w8x0y1z2a"):
            assert [r.note["id"] for r in s.notes.recall(query, reader="doctor")] == [note["id"]]
    finally:
        s.db.close()


# ---- item 15: a conclusion whose code changed is not shown as verified --------------------------------------------
def test_15_recall_marks_a_conclusion_stale_after_the_code_changed(make_config, project):
    from codedoctor import claim_rules, ids as _ids  # noqa: F401
    from codedoctor.currency import snapshot_version
    from codedoctor.memory import related
    from codedoctor.services import Services
    from test_claim_rules import AUTHOR, draft

    s = Services.open(make_config())
    try:
        ev_id, _ = s.evidence.add_code_excerpt(project, "server/shop.py", 6, 7, agent_id="doctor")
        c = s.claims.submit(draft(ev_id, project), author=AUTHOR)
        s.claims.add_review(c["id"], reviewer="guardian-1", verdict="reverified", notes="ok", evidence=[ev_id])
        assert claim_rules.evaluate(s, c["id"])["status"] == "supported"
        shop = project / "server" / "shop.py"
        shop.write_text(shop.read_text(encoding="utf-8").replace("return None", "raise StaleInventory()"), encoding="utf-8")
        asyncio.run(related.recall_async(s, "buy", reader="doctor", data_class="internal"))  # no refresh_all call here
        assert s.claims.get(c["id"])["status"] == "needs_revalidation"
    finally:
        s.db.close()


# ---- item 9: another conversation does not inherit this box's words and files ---------------------------------------
def test_9_switching_conversation_empties_the_box(qapp):
    from codedoctor.desktop.composer import Composer

    box = Composer([("agent", "Agent", "")])
    box.edit.setPlainText("写给上一个对话的半截话")
    box.attached = [("notes.txt", "附件内容")]
    box._show_attached()
    box.drop_draft()
    assert box.edit.toPlainText() == "" and box.attached == [] and box.mentions == []
