from __future__ import annotations

import pytest

from codedoctor.memory.notes import MemoryError_
from codedoctor.services import Services


@pytest.fixture
def services(make_config):
    s = Services.open(make_config())
    yield s
    s.db.close()


def _src(s: Services) -> list[str]:
    return [s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]


def test_blob_store_detects_tampering(services):
    digest = services.blobs.put(b"hello")
    assert services.blobs.intact(digest)
    services.blobs.path(digest).write_bytes(b"hellO")
    assert not services.blobs.intact(digest)


def test_journal_is_ordered_and_keeps_full_originals(services):
    big = {"text": "x" * 10000}
    e1 = services.journal.append("doctor", "tool_result", {"ok": True}, task_id="task_01JB8Z2000000000000000TK01", payload="full output")
    e2 = services.journal.append("doctor", "tool_result", big, task_id="task_01JB8Z2000000000000000TK01")
    entries = services.journal.read(task_id="task_01JB8Z2000000000000000TK01")
    assert [e["id"] for e in entries] == [e1["id"], e2["id"]]
    assert entries[0]["seq"] < entries[1]["seq"]
    assert services.journal.original(entries[0])["payload"] == "full output"
    assert entries[1]["data"]["truncated"] is True
    assert services.journal.original(entries[1])["data"] == big


def test_code_evidence_is_anchored_and_checked(services, project):
    ev_id, excerpt = services.evidence.add_code_excerpt(project, "server/shop.py", 6, 7, agent_id="doctor")
    assert ev_id.startswith("ev:code:wt-") and ev_id.endswith(":L6-L7")  # not a git repo -> working-tree hash
    assert "inventory_version" in excerpt
    assert services.evidence.check(ev_id) == "ok"
    rec = services.evidence.get(ev_id)
    services.blobs.path(rec["content"]["sha256"]).write_text("tampered")
    assert services.evidence.check(ev_id) == "tampered"
    assert services.evidence.check("ev:blob:" + "0" * 64) == "missing"


def test_recall_exact_identifiers_paths_and_line_numbers(services):
    s = services
    s.notes.write(owner="doctor", scope="agent", kind="fact", sources=_src(s),
                  text="ShopService.buy in server/shop.py:7 returns early when inventory_version differs.")
    s.notes.write(owner="doctor", scope="agent", kind="fact", sources=_src(s), text="The login page uses OAuth.")
    hits = s.notes.recall("shop.py:7 inventory_version", reader="doctor")
    assert hits and "inventory_version" in hits[0].note["text"]
    assert all("OAuth" not in h.note["text"] for h in hits)


def test_recall_chinese_short_and_long_terms(services):
    s = services
    s.notes.write(owner="doctor", scope="agent", kind="fact", sources=_src(s), text="结算服务在断线重连后会重复发放金币奖励。")
    s.notes.write(owner="doctor", scope="agent", kind="fact", sources=_src(s), text="登录接口的超时时间是 30 秒。")
    assert "金币" in s.notes.recall("金币", reader="doctor")[0].note["text"]               # 2 chars: LIKE path
    assert "金币" in s.notes.recall("重复发放金币", reader="doctor")[0].note["text"]       # long CJK: trigram path
    assert "登录" in s.notes.recall("登录 超时", reader="doctor")[0].note["text"]


def test_agent_memory_is_private_unless_shared(services):
    s = services
    s.notes.write(owner="worker-1", scope="agent", kind="fact", sources=_src(s), text="private: cache key format is user:{id}")
    s.notes.write(owner="worker-1", scope="project", kind="fact", sources=_src(s), text="shared: cache TTL is 300s")
    other = [h.note["text"] for h in s.notes.recall("cache", reader="worker-2")]
    assert other == ["shared: cache TTL is 300s"]
    assert len(s.notes.recall("cache", reader="worker-1")) == 2
    assert s.notes.recall("cache", reader="worker-2", include_shared=False) == []


def test_superseded_notes_leave_recall_but_stay_readable(services):
    s = services
    old = s.notes.write(owner="doctor", scope="agent", kind="fact", sources=_src(s), text="retry limit is 3")
    new = s.notes.write(owner="doctor", scope="agent", kind="fact", sources=[old["id"]], text="retry limit is 5 since commit abc")
    s.notes.supersede(old["id"], new["id"])
    assert [h.note["id"] for h in s.notes.recall("retry limit", reader="doctor")] == [new["id"]]
    assert s.notes.get(old["id"])["superseded_by"] == new["id"]


def test_notes_require_sources_and_canonical_entities(services):
    with pytest.raises(MemoryError_):
        services.notes.write(owner="doctor", scope="agent", kind="fact", sources=[], text="no source")
    with pytest.raises(MemoryError_):
        services.notes.write(owner="doctor", scope="agent", kind="fact", sources=_src(services), text="x", entities=["the shop"])


def test_memory_survives_reopen(make_config):
    cfg = make_config()
    s = Services.open(cfg)
    src = [s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]
    s.notes.write(owner="doctor", scope="project", kind="decision", sources=src, text="Use parent_based sampling for shop-api.")
    s.db.close()
    s2 = Services.open(cfg)
    try:
        assert s2.notes.recall("parent_based sampling", reader="anyone")[0].note["kind"] == "decision"
        assert s2.journal.count() == 1
    finally:
        s2.db.close()


def test_version_1_database_is_upgraded_in_place(tmp_path):
    import sqlite3

    from codedoctor.store import db as dbmod

    path = tmp_path / "old.sqlite3"
    raw = sqlite3.connect(path)
    raw.executescript(dbmod._DDL)  # the version 1 layout: tasks has no 'body' column, no effects/reviews tables
    raw.execute("INSERT INTO meta VALUES ('schema_version', '1')")
    raw.commit()
    raw.close()
    d = dbmod.Database(path)
    try:
        assert d.one("SELECT value FROM meta WHERE key='schema_version'")["value"] == str(dbmod.SCHEMA_VERSION)
        assert "body" in {r["name"] for r in d.query("PRAGMA table_info(tasks)")}
        assert d.one("SELECT COUNT(*) AS n FROM effects")["n"] == 0
    finally:
        d.close()
