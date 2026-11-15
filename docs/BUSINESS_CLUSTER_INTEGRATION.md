# Multi-Agent business cluster backend

This contribution takes ownership of the backend investigation loop. It adds no UI code. Existing Claude work was preserved in local prerequisite snapshot `7265ddf`, based on source HEAD `667f9aa`. The feature patch is relative to that preserved snapshot, not a replacement for Claude's files. Do not reset an active checkout or overwrite staged work to apply it.

## Run

From repository root with the existing daemon dependencies installed:

```powershell
$env:PYTHONPATH = "$PWD\daemon"
python -m pytest tests/daemon/test_business_cluster.py tests/daemon/test_cluster.py tests/daemon/test_cluster_upgrades.py
python -m tools.business_cluster_demo --output business-report.json --state-dir business-state
```

Output and state paths must be new. The demo preserves SQLite and blob evidence under the state directory. It runs six explicitly configured scripted Agents per investigation and actual SQLite/asyncio business code: duplicate purchase, concurrent lost update, and shared cart/invoice pricing. Each case yields 24 raw phase receipts: two checks, two actors, two repeats, three phases. Scripted decisions are a reproducible backend baseline, not a real-model benchmark.

## Agent integration

`cluster_inventory` lists registered scenarios and approved invariants. `cluster_candidates` finds typed upstream paths. `cluster_open` freezes a schema-validated plan; its tool definition embeds the full schema. `cluster_dispatch` atomically reserves and assigns checks. `cluster_run` executes only the assigned trusted scenario and role. `cluster_status` reports evidence, hypothesis ledger, pending tests, blockers and delivery permission. Final root reports cannot bypass the backend gate with plain text. Existing non-investigation tasks retain their previous behavior.

Applications explicitly register `Scenario` handlers on `services.investigations.registry`. Worker and Guardian handlers must differ. `approve_contract` is a trusted application call, not an Agent tool. See `tools/business_cluster_cases.py` for the bounded sample adapter and approved source evidence. Merely loading a project does not authorize importing its Python or executing commands.

Plans are immutable per root task. Scenario code versions must match the frozen graph snapshot. Changed code, altered evidence, changed handlers, unresolved hypotheses, missing independent runs or a failed regression block delivery. After restart, trusted adapters need explicit registration; interrupted execution remains blocked for operator reconciliation. Cooperative limits do not kill a hanging Python function.

## UI handoff

Use the existing daemon task submission/configuration routes. Additive read routes are:

| Route | Result |
| --- | --- |
| `GET /cluster/capabilities` | configured roles, adapter IDs, explicit safety and coverage flags |
| `GET /cluster/contracts` | approved business invariants and source references |
| `GET /cluster/investigations?root_task_id=...` | matching investigation status, or an empty list |
| `GET /cluster/investigations/{id}` | frozen plan and current evidence-derived status; 404 if absent |

Display `blocking_reasons`, `hypothesis_ledger`, checks, evidence IDs and scope alongside `delivery_allowed`. A structural lead must not be labelled a confirmed cause. A missing scenario or unknown metric must not be displayed as a pass. UI must preserve user-selected endpoints/models and only use explicitly configured fallback lists. Read APIs do not approve contracts or run experiments. Keep the daemon's existing access controls and local binding when exposing these routes.

## Review boundaries

New core: `daemon/codedoctor/cluster/`, `schemas/cluster/`, `samples/cluster_shop/`, the two business-cluster tools, and focused tests. Existing backend edits connect services/API, tool roles, delivery gates and atomic task/message publishing. Review bus/orchestration/runtime integration carefully; they are the shared-file merge points with parallel Claude backend work. No existing ADR is overwritten; ADR 0010 documents the scope and remaining product work.
