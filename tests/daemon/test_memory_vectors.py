"""Semantic recall (ADR 0007, M6). A real embedding model is the user's choice and is never called
here; CONCEPT_EMBEDDER stands in for one: texts that mention the same concept, in Chinese or
English, get close vectors - which is what a multilingual embedding model provides."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from codedoctor import config as config_mod
from codedoctor import providers
from codedoctor.agents.tools import ToolContext, format_recalled, remember
from codedoctor.memory import related
from codedoctor.models import scripted
from codedoctor.models.base import ModelError
from codedoctor.models.openai_compat import OpenAICompatClient
from codedoctor.services import Services

from conftest import unique_model

CONCEPTS = [("reward", "奖励"), ("twice", "两次"), ("reconnect", "重连"), ("login", "登录"), ("timeout", "超时"),
            ("inventory", "背包"), ("gold", "金币")]


def concept_embedder(text: str) -> list[float]:
    t = text.lower()
    return [float(any(w in t for w in words)) for words in CONCEPTS] + [0.05]


def _cfg(make_config, *, model=None, local=True, max_data_class=None, min_similarity=None):
    model = model or unique_model("emb")
    scripted.register_embedder(model, concept_embedder)
    ep = {"id": "emb", "kind": "scripted", "base_url": "scripted:", "local": local}
    if max_data_class:
        ep["max_data_class"] = max_data_class
    emb = {"endpoint": "emb", "model": model}
    if min_similarity is not None:
        emb["min_similarity"] = min_similarity
    return make_config(endpoints=[{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}, ep],
                       memory={"embedding": emb}), model


@pytest.fixture
def emb(make_config):
    cfg, model = _cfg(make_config)
    s = Services.open(cfg)
    yield s
    s.db.close()


def _note(s, text, **kw):
    src = [s.journal.append("doctor", "state_change", {"state": "idle"})["id"]]
    return s.notes.write(owner="doctor", scope="project", kind="fact", sources=src, text=text, **kw)


def _recall(s, q, data_class="internal", **kw):
    return asyncio.run(related.recall_async(s, q, reader="doctor", data_class=data_class, **kw))


# --- configuration --------------------------------------------------------------------------------

def test_embedding_is_the_users_explicit_choice(make_config):
    cfg, model = _cfg(make_config, min_similarity=0.5)
    assert (cfg.embedding.endpoint, cfg.embedding.model, cfg.embedding.min_similarity) == ("emb", model, 0.5)
    assert make_config().embedding is None  # not configured: no semantic recall, nothing is called
    with pytest.raises(config_mod.ConfigError, match="unknown endpoint"):
        make_config(memory={"embedding": {"endpoint": "nope", "model": "m"}})
    with pytest.raises(config_mod.ConfigError, match="no embeddings API"):
        make_config(endpoints=[{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True},
                               {"id": "claude", "kind": "anthropic", "base_url": "https://api.anthropic.com", "local": False}],
                    memory={"embedding": {"endpoint": "claude", "model": "x"}})


def test_openai_compatible_embeddings_request_and_order():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]})

    async def go():
        c = OpenAICompatClient("http://x/v1", None, 5, httpx.MockTransport(handler))
        try:
            return await c.embed("bge-m3", ["a", "b"])
        finally:
            await c.aclose()

    assert asyncio.run(go()) == [[1.0, 0.0], [0.0, 1.0]]
    assert seen == [{"model": "bge-m3", "input": ["a", "b"]}]


def test_embedding_probe_sends_only_fixed_text():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append(body)
        return httpx.Response(200, json={"data": [{"index": i, "embedding": [0.1] * 8} for i in range(len(body["input"]))]})

    res = asyncio.run(providers.probe_embedding("openai_compatible", "http://x/v1", None, "bge-m3",
                                                transport=httpx.MockTransport(handler)))
    assert res.dimensions == 8 and res.error is None
    assert seen[0]["input"] == providers._EMBED_PROBE_TEXTS
    assert "嵌入" in asyncio.run(providers.probe_embedding("anthropic", "https://api.anthropic.com", None, "x")).error


# --- recall ----------------------------------------------------------------------------------------

def test_meaning_finds_a_chinese_note_for_an_english_question(emb):
    note = _note(emb, "断线重连后比赛奖励会到账两次")
    _note(emb, "登录接口超时时间是 30 秒")
    assert emb.notes.recall("match reward paid twice", reader="doctor") == []  # no word in common
    [hit] = _recall(emb, "match reward paid twice")
    assert hit.note["id"] == note["id"] and hit.meaning > 0.5
    assert "(close in meaning to the query: " in format_recalled(emb, [hit])
    assert emb.vectors.count() == {"vectors": 2, "withheld": 0, "pending": 0}


def test_meaning_adds_to_text_and_does_not_replace_it(emb):
    exact = _note(emb, "retryFetch retries /api/shop/buy")
    _note(emb, "背包上限没有检查")
    hits = _recall(emb, "retryFetch")
    assert hits[0].note["id"] == exact["id"]  # text recall still works when meaning says nothing


def test_notes_the_endpoint_may_not_see_are_never_sent(make_config):
    cfg, model = _cfg(make_config, local=False, max_data_class="internal")
    s = Services.open(cfg)
    try:
        _note(s, "比赛奖励到账两次")
        secret = _note(s, "重连奖励的密钥规则（机密）", data_class="confidential")
        hits = _recall(s, "reward twice")
        sent = [t for c in s.models.client("emb").embed_calls for t in c["texts"]]
        assert "重连奖励的密钥规则（机密）" not in sent
        assert secret["id"] not in {h.note["id"] for h in hits if h.meaning}
        assert s.vectors.count() == {"vectors": 1, "withheld": 1, "pending": 0}
        before = len(s.models.client("emb").embed_calls)
        _recall(s, "reward twice", data_class="confidential")  # the query itself may not leave either
        assert len(s.models.client("emb").embed_calls) == before
    finally:
        s.db.close()


def test_an_embedding_outage_falls_back_to_text(make_config):
    model = unique_model("down")

    def down(text):
        raise ModelError("connection refused", retryable=True)

    scripted.register_embedder(model, down)
    cfg = make_config(endpoints=[{"id": "fake", "kind": "scripted", "base_url": "scripted:", "local": True}],
                      memory={"embedding": {"endpoint": "fake", "model": model}})
    s = Services.open(cfg)
    try:
        note = _note(s, "reconnect replays settle")
        [hit] = _recall(s, "reconnect")
        assert hit.note["id"] == note["id"] and hit.meaning is None
        assert "connection refused" in s.vectors.last_error
    finally:
        s.db.close()


def test_vectors_of_another_model_are_not_reused(make_config):
    cfg, _ = _cfg(make_config)
    s = Services.open(cfg)
    _note(s, "比赛奖励到账两次")
    asyncio.run(s.vectors.index_pending())
    s.db.close()
    cfg2, _ = _cfg(make_config)  # the user switched to another embedding model
    s2 = Services.open(cfg2)
    try:
        assert s2.vectors.count()["pending"] == 1
    finally:
        s2.db.close()


def test_remembered_notes_carry_the_tasks_data_class(emb):
    ctx = ToolContext(services=emb, agent_id="doctor", role="general", task_id="task_01JB8Z2000000000000000TK01",
                      model={"provider": "scripted", "model": "m"},
                      call_entry_id=emb.journal.append("doctor", "tool_call", {})["id"], thread_id="thr_x",
                      known_agents=set(), data_class="confidential")
    res = remember(ctx, {"text": "从机密日志里看到的事实"})
    assert emb.notes.get(res.notes[0])["data_class"] == "confidential"


# --- in the running service -----------------------------------------------------------------------

async def test_task_start_recall_uses_meaning_and_the_service_indexes_in_the_background(make_config):
    from codedoctor.agents.daemon import Daemon

    agent_model = unique_model()
    scripted.register(agent_model, [{"text": "answer"}])
    cfg, _ = _cfg(make_config)
    cfg = config_mod.parse({**_raw(cfg), "agents": [{"id": "doctor", "role": "general", "endpoint": "fake", "model": agent_model}]})
    d = Daemon(cfg, poll_s=0.05)
    note = _note(d.s, "断线重连后比赛奖励会到账两次，见 server/session.py:10")
    await d.start()
    try:
        for _ in range(100):
            if d.s.vectors.count()["vectors"]:
                break
            await asyncio.sleep(0.02)
        assert d.s.vectors.count()["vectors"] == 1  # indexed by the background loop, before any recall
        sub = d.submit_task("doctor", "rewards", "Players get the match reward twice after they reconnect. Why?")
        await asyncio.wait_for(d.wait_for_report(sub["task_id"]), 10)
    finally:
        await d.halt()
    prompt = d.s.models.client("fake").calls[0]["messages"][1].content
    assert "server/session.py:10" in prompt and note["id"] in prompt
    await d.s.aclose()


def _raw(cfg) -> dict:
    """Back to the raw form, for building a variant of a parsed config in a test."""
    return {
        "cd_schema": "cd.config.project/0",
        "project": {"name": cfg.name, "root": str(cfg.root), "data_dir": str(cfg.data_dir)},
        "endpoints": [{"id": e.id, "kind": e.kind, "base_url": e.base_url, "local": e.local} for e in cfg.endpoints.values()],
        "agents": [{"id": a.id, "role": a.role, "endpoint": a.primary.endpoint, "model": a.primary.model} for a in cfg.agents.values()],
        "memory": {"embedding": {"endpoint": cfg.embedding.endpoint, "model": cfg.embedding.model}},
    }
