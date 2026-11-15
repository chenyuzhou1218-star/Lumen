"""Probe coverage declarations, telemetry health reports, chain templates, and the
observation coverage list computed from them (hard requirement 1).

Declarations and health reports are stored as evidence (kinds 'coverage' and
'health'), so every coverage verdict can cite exactly what it was based on.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from codedoctor import ids
from codedoctor.protocol.registry import validator
from codedoctor.store.db import dumps

STALE_HEARTBEATS = 3  # health older than this many heartbeat intervals counts as "reports stopped"


class TelemetryError(ValueError):
    pass


def _check(schema: str, doc: dict) -> None:
    errors = list(validator(schema).iter_errors(doc))
    if errors:
        e = errors[0]
        raise TelemetryError(f"{schema} {'/'.join(map(str, e.absolute_path))}: {e.message}")


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class TelemetryStore:
    def __init__(self, services):
        self.s = services

    def _store(self, doc: dict, kind: str, *, service: str | None, probe_id: str | None) -> str:
        data = dumps(doc).encode("utf-8")
        digest = self.s.blobs.put(data)
        provenance = {"source": "probe" if probe_id else "ingest", "collected_by": "telemetry.ingest/0.1.0"}
        if probe_id:
            provenance["probe_id"] = probe_id
        return self.s.evidence.register({
            "cd_schema": "cd.evidence.record/0", "id": doc["id"], "kind": kind, "created_at": ids.now(),
            "content": {"sha256": digest, "media_type": "application/json", "size_bytes": len(data)},
            "binding": {"services": [service]} if service else {},
            "provenance": provenance, "data_class": "internal",
            "redaction": {"applied": False, "policy_id": "none/0"}, "content_trust": "untrusted",
        })

    def add_coverage(self, doc: dict) -> str:
        _check("event/coverage.schema.json", doc)
        return self._store(doc, "coverage", service=doc["service"]["name"], probe_id=doc["probe_id"])

    def add_health(self, doc: dict) -> str:
        _check("event/telemetry-health.schema.json", doc)
        probe = doc["component"]["id"] if doc["component"]["type"] == "probe" else None
        return self._store(doc, "health", service=None, probe_id=probe)

    def add_template(self, doc: dict) -> None:
        _check("event/chain-template.schema.json", doc)
        with self.s.db.tx() as c:
            c.execute("INSERT OR REPLACE INTO templates (id, version, doc) VALUES (?,?,?)", (doc["id"], doc["version"], dumps(doc)))

    def _docs(self, kind: str) -> list[tuple[str, dict]]:
        rows = self.s.db.query("SELECT id FROM evidence WHERE kind = ? ORDER BY created_at, id", (kind,))
        return [(r["id"], json.loads(self.s.evidence.content(r["id"]))) for r in rows]

    def templates(self) -> list[dict]:
        rows = self.s.db.query("SELECT doc FROM templates ORDER BY id, version")
        latest: dict[str, dict] = {}
        for r in rows:
            d = json.loads(r["doc"])
            latest[d["id"]] = d
        return list(latest.values())

    # --- the coverage list ------------------------------------------------------------

    def coverage_status(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        declarations: dict[str, tuple[str, dict]] = {}
        for ev_id, d in self._docs("coverage"):
            prev = declarations.get(d["probe_id"])
            if prev is None or d["declared_at"] >= prev[1]["declared_at"]:
                declarations[d["probe_id"]] = (ev_id, d)
        health: dict[str, list[tuple[str, dict]]] = {}
        for ev_id, h in self._docs("health"):
            if h["component"]["type"] == "probe":
                health.setdefault(h["component"]["id"], []).append((ev_id, h))

        rows: list[dict] = []
        by_key: dict[tuple[str, str], list[dict]] = {}
        for probe_id, (cov_id, cov) in sorted(declarations.items()):
            status, reason, h_id, last_at = self._probe_status(cov, sorted(health.get(probe_id, []), key=lambda x: x[1]["heartbeat_seq"]), now)
            for layer in cov["layers"]:
                row = {"service": cov["service"]["name"], "layer": layer, "status": status, "reason": reason,
                       "probe_id": probe_id, "coverage": cov_id}
                if h_id:
                    row["health"] = h_id
                if last_at:
                    row["last_report_at"] = last_at
                rows.append(row)
                by_key.setdefault((row["service"], layer), []).append({**row, "_scope": cov["scope"]})

        for tpl in self.templates():
            default_service = tpl["trigger"].get("service")
            for stage in tpl["stages"]:
                service = stage["match"].get("service")
                if service is not None:
                    candidates = by_key.get((service, stage["layer"]), [])
                else:  # stage does not name its service: any probe covering this layer may observe it
                    candidates = [c for (svc, layer), cs in by_key.items() if layer == stage["layer"] for c in cs]
                    service = candidates[0]["service"] if candidates else default_service
                if service is None:
                    continue
                base = {"service": service, "layer": stage["layer"], "template": tpl["id"], "stage": stage["id"]}
                route = stage["match"].get("attributes_equal", {}).get("http.route")
                table = stage["match"].get("attributes_equal", {}).get("db.collection.name")
                covering = [c for c in candidates if _in_scope(c["_scope"], route, table)]
                if covering:
                    best = sorted(covering, key=lambda c: ["healthy", "declared", "degraded"].index(c["status"]))[0]
                    rows.append({**base, "service": best["service"],
                                 **{k: v for k, v in best.items() if k not in ("_scope", "service", "layer")}})
                elif candidates:
                    rows.append({**base, "status": "not_instrumented",
                                 "reason": f"a probe covers {service}/{stage['layer']} but not this stage's route/table (scope 'listed')"})
                else:
                    rows.append({**base, "status": "not_instrumented", "reason": f"no probe declares {service}/{stage['layer']}"})

        doc = {"cd_schema": "cd.event.coverage-status/0", "computed_at": ids.now(), "rows": rows}
        _check("event/coverage-status.schema.json", doc)
        return doc

    @staticmethod
    def _probe_status(cov: dict, reports: list[tuple[str, dict]], now: datetime) -> tuple[str, str, str | None, str | None]:
        if not reports:
            return "declared", "declared, but no health report has arrived yet", None, None
        h_id, h = reports[-1]
        last_at = h["received_at"]
        problems = []
        age_s = (now - _ts(last_at)).total_seconds()
        if age_s > STALE_HEARTBEATS * cov["heartbeat_interval_ms"] / 1000:
            problems.append(f"no health report for {age_s:.0f}s (heartbeat every {cov['heartbeat_interval_ms'] / 1000:g}s)")
        if len(reports) >= 2 and reports[-1][1]["heartbeat_seq"] - reports[-2][1]["heartbeat_seq"] > 1:
            problems.append("health reports were lost (heartbeat sequence gap)")
        counters = h["counters"]
        if counters.get("spans_dropped", 0):
            problems.append(f"{counters['spans_dropped']} spans dropped")
        if counters.get("export_failures", 0):
            problems.append(f"{counters['export_failures']} export failures")
        if counters.get("propagation_extract_failures", 0):
            problems.append(f"{counters['propagation_extract_failures']} trace-context parse failures")
        q = h.get("queue")
        if q and q["length_max"] >= q["capacity"]:
            problems.append("export queue was full")
        sampling = cov["sampling"]
        if sampling["strategy"] == "always_off":
            problems.append("sampling is off")
        elif sampling["strategy"] in ("ratio", "parent_based_ratio", "tail", "unknown") and sampling.get("ratio", 0) < 1 \
                and not sampling["records_decisions"]:
            problems.append("sampling below 100% without recorded decisions: absences cannot be proven")
        if problems:
            return "degraded", "; ".join(problems), h_id, last_at
        return "healthy", "health reports regular, nothing lost", h_id, last_at


def _in_scope(scope: dict, route: str | None, table: str | None) -> bool:
    if scope["mode"] == "all":
        return True
    if route is not None:
        return route in scope.get("http_routes", [])
    if table is not None:
        return table in scope.get("db_tables", [])
    return True
