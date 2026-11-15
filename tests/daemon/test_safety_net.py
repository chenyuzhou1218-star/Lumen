"""The system's last line of defence (ADR 0016 item 13): when every agent has stopped and a test that passed before
still fails, the change after which it broke is undone; the changes that broke nothing stay."""

from __future__ import annotations

import sys

from codedoctor.agents import ownership, testrun
from codedoctor.agents.daemon import Daemon
from codedoctor.agents.tools import TOOLS, ToolContext, execute


def ctx(d):
    return ToolContext(services=d.s, agent_id="doctor", role="worker", task_id="task_sn", model={}, call_entry_id="jrn_x",
                       thread_id="thr_x", known_agents=set())


def test_the_change_that_broke_a_passing_test_is_undone_and_the_others_stay(make_config, project):
    (project / "sn").mkdir()
    (project / "sn/__init__.py").write_text("", encoding="utf-8")
    (project / "sn/price.py").write_text("def total(a, b):\n    return a + b\n", encoding="utf-8")
    (project / "sn/notes.py").write_text("NOTE = 'old'\n", encoding="utf-8")
    (project / "tests_sn").mkdir()
    (project / "tests_sn/test_price.py").write_text(
        "from sn.price import total\n\ndef test_total():\n    assert total(1, 2) == 3\n", encoding="utf-8")
    d = Daemon(make_config(permissions={"run_command": "deny", "write_files": True,
                                        "test_command": f'"{sys.executable}" -m pytest -q -p no:cacheprovider tests_sn'}))
    good = execute(TOOLS["edit_file"], ctx(d), {"path": "sn/notes.py", "old": "'old'", "new": "'new'"})
    bad = execute(TOOLS["edit_file"], ctx(d), {"path": "sn/price.py", "old": "return a + b", "new": "return a + b + policy.fee"})
    assert good.ok and bad.ok and "REGRESSIONS" in bad.content and "NameError" in bad.content  # told why, not just which

    text = testrun.safety_net(d.s, "task_sn")
    assert "undid 1 change(s) in sn/price.py" in text and "1 passed" in text
    assert (project / "sn/price.py").read_text(encoding="utf-8") == "def total(a, b):\n    return a + b\n"
    assert (project / "sn/notes.py").read_text(encoding="utf-8") == "NOTE = 'new'\n"
    assert testrun.safety_net(d.s, "task_sn") == ""  # nothing broken any more


def test_a_worker_gets_its_files_whole_and_the_rest_as_an_outline(project):
    (project / "pkg").mkdir()
    (project / "pkg/mine.py").write_text("import os\n\ndef work():\n    x = 1\n    return x\n", encoding="utf-8")
    (project / "pkg/other.py").write_text("from pkg import mine\n\nRATE = 3\n\nclass Shop:\n    def buy(self):\n"
                                          "        secret_body = 1\n", encoding="utf-8")
    text = ownership.briefing(project, ["pkg/mine.py"])
    assert "=== pkg/mine.py ===\nimport os\n\ndef work():\n    x = 1\n    return x" in text
    assert "--- pkg/other.py" in text and "RATE = 3" in text and "    def buy(self):" in text
    assert "secret_body" not in text  # bodies of other files are not sent


def test_breaking_a_test_written_during_the_investigation_is_said_at_once(make_config, project):
    """A real 20-agent run lost the library's double-borrow fix: a fixer added the guard, a contradictory scout test
    then failed, and it removed the guard again. Neither test existed before the investigation, so neither counted as
    a regression; now the flip is named right after the edit."""
    (project / "lb").mkdir()
    (project / "lb/__init__.py").write_text("", encoding="utf-8")
    (project / "lb/loans.py").write_text("LOANS = []\n\ndef borrow(m, b):\n    LOANS.append((m, b))\n", encoding="utf-8")
    (project / "tests_lb").mkdir()
    d = Daemon(make_config(permissions={"run_command": "deny", "write_files": True,
                                        "test_command": f'"{sys.executable}" -m pytest -q -p no:cacheprovider tests_lb'}))
    scout = {"path": "tests_lb/test_scout_dup.py", "content":
             "import pytest\nfrom lb import loans\n\ndef test_same_book_twice_refused():\n    loans.LOANS.clear()\n"
             "    loans.borrow('m', 'b')\n    with pytest.raises(ValueError):\n        loans.borrow('m', 'b')\n"}
    wrong = {"path": "tests_lb/test_scout_tiers.py", "content":
             "from lb import loans\n\ndef test_borrow_many():\n    loans.LOANS.clear()\n"
             "    for _ in range(3):\n        loans.borrow('m', 'b')\n"}
    from codedoctor.agents import squad
    import shutil

    orig = squad.original_dir(d.s, "task_sn")  # a squad investigation keeps the code as it was before any change
    shutil.copytree(project / "lb", orig / "lb")
    (orig / "tests_lb").mkdir()
    assert execute(TOOLS["create_file"], ctx(d), scout).ok
    assert execute(TOOLS["create_file"], ctx(d), wrong).ok
    guard = "def borrow(m, b):\n    if (m, b) in LOANS:\n        raise ValueError('already borrowed')\n    LOANS.append((m, b))\n"
    fix = execute(TOOLS["edit_file"], ctx(d), {"path": "lb/loans.py", "old": "def borrow(m, b):\n    LOANS.append((m, b))\n",
                                               "new": guard})
    assert "BROKEN JUST NOW" in fix.content and "test_borrow_many" in fix.content  # the contradiction shows at the fix
    # and which side to trust: the broken test only described the old code, the one now passing had found the bug
    assert "test_borrow_many  [passed on the original code: old behaviour]" in fix.content
    assert "test_same_book_twice_refused  [failed on the original code: found a bug]" in fix.content
    undo = execute(TOOLS["edit_file"], ctx(d), {"path": "lb/loans.py", "old": guard, "new": "def borrow(m, b):\n    LOANS.append((m, b))\n"})
    assert "BROKEN JUST NOW" in undo.content and "test_same_book_twice_refused" in undo.content
    assert "README and the task decide" in undo.content

