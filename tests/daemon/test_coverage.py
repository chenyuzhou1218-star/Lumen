"""Hard requirement 1: the observation coverage list."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codedoctor import ids
from codedoctor.api import create_app
from codedoctor.services import Services
from codedoctor.telemetry import TelemetryError, TelemetryStore

FIXTURES = Path(__file__).resolve().parents[2] / "schemas" / "event" / "fixtures" / "valid"
NOW = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)


def fixture(name: str) -> dict:
    return copy.deepcopy(json.loads((FIXTURES / name).read_text(encoding="utf-8"))["instance"])


def health(probe_id: str, seq: int, at: datetime, **counters) -> dict:
    h = fixture("telemetry-health--probe-healthy.json")
    h.update(id="ev:health:" + ids.ulid(), heartbeat_seq=seq, received_at=at.isoformat().replace("+00:00", "Z"))
    h["component"]["id"] = probe_id
    h["counters"].update(counters)
    return h


@pytest.fixture
def tel(make_config):
    s = Services.open(make_config())
    yield TelemetryStore(s)
    s.db.close()


def rows(status_doc, **match):
    return [r for r in status_doc["rows"] if all(r.get(k) == v for k, v in match.items())]


def test_four_states(tel):
    web, api = fixture("coverage--browser-all.json"), fixture("coverage--api-listed-routes.json")
    tel.add_coverage(web)
    tel.add_coverage(api)
    tel.add_health(health(api["probe_id"], 1, NOW - timedelta(seconds=4)))
    tel.add_template(fixture("chain-template--shop-buy-confirmed.json"))
    doc = tel.coverage_status(now=NOW)

    assert {r["status"] for r in rows(doc, service="shop-api", layer="http_server")} == {"healthy"}
    assert rows(doc, service="shop-web", layer="ui")[0]["status"] == "declared"  # no health report yet
    stage = rows(doc, template="tpl:shop.buy", stage="server")[0]
    assert stage["status"] == "healthy" and stage["health"].startswith("ev:health:")
    # the db-write stage targets table 'orders', which the API probe lists -> covered
    assert rows(doc, template="tpl:shop.buy", stage="db-write")[0]["status"] == "healthy"


def test_degraded_reasons(tel):
    api = fixture("coverage--api-listed-routes.json")
    tel.add_coverage(api)
    tel.add_health(health(api["probe_id"], 1, NOW - timedelta(seconds=9)))
    tel.add_health(health(api["probe_id"], 3, NOW - timedelta(seconds=2), spans_dropped=17))  # seq 2 lost
    [row, *_] = rows(tel.coverage_status(now=NOW), service="shop-api", layer="db")
    assert row["status"] == "degraded"
    assert "17 spans dropped" in row["reason"] and "sequence gap" in row["reason"]


def test_reports_stopping_is_degraded(tel):
    api = fixture("coverage--api-listed-routes.json")
    tel.add_coverage(api)
    tel.add_health(health(api["probe_id"], 1, NOW - timedelta(minutes=5)))
    row = rows(tel.coverage_status(now=NOW), service="shop-api", layer="handler")[0]
    assert row["status"] == "degraded" and "no health report for 300s" in row["reason"]


def test_sampling_without_decisions_cannot_prove_absence(tel):
    api = fixture("coverage--api-listed-routes.json")
    api["sampling"] = {"strategy": "ratio", "ratio": 0.25, "records_decisions": False}
    tel.add_coverage(api)
    tel.add_health(health(api["probe_id"], 1, NOW))
    row = rows(tel.coverage_status(now=NOW), service="shop-api", layer="db")[0]
    assert row["status"] == "degraded" and "absences cannot be proven" in row["reason"]


def test_unlisted_route_and_unknown_service_are_not_instrumented(tel):
    api = fixture("coverage--api-listed-routes.json")
    api["scope"] = {"mode": "listed", "http_routes": ["/api/shop/list"]}
    tel.add_coverage(api)
    tel.add_health(health(api["probe_id"], 1, NOW))
    tpl = fixture("chain-template--shop-buy-confirmed.json")
    tpl["stages"].append({"id": "pay", "layer": "http_server", "match": {"cd_kind": "http.server", "service": "payment"},
                          "required": True, "deadline_ms": 2000})
    tel.add_template(tpl)
    doc = tel.coverage_status(now=NOW)
    server = rows(doc, template="tpl:shop.buy", stage="server")[0]
    assert server["status"] == "not_instrumented" and "not this stage's route" in server["reason"]
    pay = rows(doc, template="tpl:shop.buy", stage="pay")[0]
    assert pay["status"] == "not_instrumented" and "probe_id" not in pay


def test_invalid_telemetry_is_rejected(tel):
    bad = fixture("coverage--api-listed-routes.json")
    bad["sampling"] = {"strategy": "ratio", "records_decisions": True}  # ratio missing
    with pytest.raises(TelemetryError):
        tel.add_coverage(bad)


def test_coverage_over_http(make_config):
    with TestClient(create_app(make_config(), poll_s=0.05)) as client:
        api = fixture("coverage--api-listed-routes.json")
        assert client.post("/telemetry/coverage", json=api).status_code == 200
        h = health(api["probe_id"], 1, datetime.now(timezone.utc))
        assert client.post("/telemetry/health", json=h).status_code == 200
        assert client.post("/templates", json=fixture("chain-template--shop-buy-confirmed.json")).status_code == 200
        doc = client.get("/coverage").json()
        assert doc["cd_schema"] == "cd.event.coverage-status/0" and any(r["status"] == "healthy" for r in doc["rows"])
        assert client.post("/telemetry/health", json={"nope": 1}).status_code == 422
