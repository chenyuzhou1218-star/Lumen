"""Stable read endpoints for the separately developed UI. No API keys or automatic model selection."""
from __future__ import annotations

import json

from fastapi import HTTPException

from codedoctor.cluster.contracts import BusinessError


def mount(app, daemon):
    @app.get("/cluster/foresight")
    def foresight():
        return daemon.foresight.status()

    @app.get("/cluster/capabilities")
    def capabilities():
        return {"cd_schema": "cd.cluster.capabilities/0", "roles": daemon.agent_states(),
                "registered_experiments": sorted(daemon.s.investigations.registry.scenarios),
                "business_contracts_require_user_approval": True,
                "heads_execute_terminal_or_experiments": False, "heads_can_read_and_schedule": True,
                "runtime_trace_coverage": "not_implemented_here"}

    @app.get("/cluster/investigations")
    def investigations(root_task_id: str):
        investigation = daemon.s.investigations.for_root(root_task_id)
        return [] if investigation is None else [daemon.s.investigations.status(investigation)]

    @app.get("/cluster/investigations/{investigation_id}")
    def detail(investigation_id: str):
        try:
            return {"investigation": daemon.s.investigations.get(investigation_id),
                    "status": daemon.s.investigations.status(investigation_id)}
        except BusinessError as error:
            raise HTTPException(404, str(error)) from None

    @app.get("/cluster/contracts")
    def contracts():
        return [json.loads(r["doc"]) for r in daemon.s.db.query("SELECT doc FROM cluster_contracts ORDER BY id")]
