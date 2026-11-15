# ADR 0005: Coupling graph and multi-agent cluster

- Status: proposed (pending review)
- Date: 2026-10-24
- Author: Claude
- Requested by the user: build coupling logic and multi-agent cooperation first, so they can be tested.

## 1. Coupling graph (core 2)

### Extraction (`daemon/codedoctor/graph/`)

| Language | Parser | What is extracted |
|---|---|---|
| Python | Standard library `ast` (exact syntax tree) | functions / classes / methods, imports (module aliases resolved), calls, route decorators (`@app.get/post/...`, `@app.route(methods=)`), attribute writes and mutating method calls, SQL in strings (only strings that really have SQL syntax), early `return None/False`, transaction markers, idempotency-key markers, retry loops |
| JS / TS | tree-sitter | ES imports / `require`, functions / classes / methods / object methods / assigned functions, calls, `new`, `fetch` / axios / `xhr.open` / project wrappers such as `retryFetch("/api/x", {method})`, express routes, event bus `emit` / `on` (including inline handlers), WebSocket messages (`send({type})`, `switch(msg.type)`, `msg.type === "x"`), attribute writes, early returns, retry loops |

Third-party directories (`lib*`, `vendor`, `third*`, `第三方`, `node_modules`) and minified / bundled files are skipped.

### Nodes and edges

- Nodes use the canonical entity ids from `schemas/claim/entity-ref`: `file`, `symbol`, `route`, `event` (new), `ws_msg`, `state`, `table`.
- **In-memory state is scoped by language**: `py/gold` and `js/gold` are different nodes, because a server and a client never share memory. Database tables are shared and are not scoped.
- Every edge records its **provenance** (`schemas/graph/edge`):
  - `static`: read from code; must carry the file and line;
  - `runtime`: observed in telemetry; must cite evidence;
  - `inferred`: from a proposed claim;
  - `verified`: from a supported claim.
- Every static edge also records **how it was resolved**:
  - `exact`: same file, explicit import, or literal string;
  - `name_match`: the only definition with that name in the project;
  - `ambiguous`: one of 2–3 definitions with the same name. **Analyses do not follow these edges**, so effects do not spread to unrelated functions that happen to share a name;
  - `heuristic`: attribute writes, SQL.

### Queries (`graph/model.py`)

- `impact`: what an entity affects downstream, and what affects it upstream. This crosses the client/server boundary (button handler → API route → server function → tables).
- `common_cause`: given several symptoms, ranks the dependencies or upstream causes they share. Shared state and tables rank first.
- `find` / `neighbors`.

### Risk detectors (`graph/risks.py`, `schemas/graph/risk`)

Seven deterministic patterns. They only look at **persistent data** (tables) and **business state** (gold, inventory, orders, rewards, health, and so on), because UI bookkeeping writes many fields from many events and that is normal. Each finding comes with a location, a fault model and a way to verify it, and is ranked by severity and business relevance. **A finding is a lead, never a bug report.**

| Pattern | Fault model |
|---|---|
| Several entry points write the same data, with no lock or transaction | `fm:concurrent_write` |
| A retry / reconnect / replay path that crosses the network or reaches a table or server-side business state, with no idempotency key | `fm:duplicate_request` |
| One function writes several stores without a transaction | `fm:partial_failure` |
| A business path returns quietly before its writes | `fm:silent_noop` |
| An event is emitted but nothing listens / something listens but nothing emits (platform events excluded) | `fm:lost_message` / `fm:dead_handler` |
| The client calls a route no scanned server code handles | `fm:contract_mismatch` |

**Validation:**
- `samples/shop-coupling` has 7 deliberately planted cross-module defects. All 7 are detected, with correct locations (`tests/daemon/test_graph.py`).
- The real game project: 232 files analysed in about 7–11 seconds. Third-party libraries are filtered out, and the high-risk findings point at business code (for example, `reconnect_player` in `server.py` writes several tables with no idempotency key).

## 2. Multi-agent cluster (`agents/orchestration.py`, `agents/tools_cluster.py`)

The orchestration skeleton is deterministic code. Models only decide what to investigate and what the evidence means.

```
user → head_dispatch ── consult ──→ head_logic   (coupling graph analysis, hypotheses, risks, objections)
              │
              ├─ delegate ──→ worker-1 ──finished──→ guardian-1 (automatic independent review)
              ├─ delegate ──→ worker-2 ──finished──→ guardian-2
              └─ wait_for (no tokens used) → outcomes, claim statuses, guardian verdicts
```

- **Tools are assigned by role**:
  - dispatch head: delegate, wait, consult, status — it does not edit code or run commands;
  - logic head: the full set of graph tools, reading code, claims, objections;
  - worker: reading code, graph queries, commands, claims;
  - guardian: read-only tools plus `review_claim`.
- **Guardian pairing**: in the config, `supervises: worker-1`. When the worker finishes, the system automatically creates a review subtask (`review_of`) listing the worker's claims, before the worker's task counts as finished. A guardian that re-verifies a claim, as someone other than its author, is what lets the claim become `supported` (the ADR 0004 promotion rules).
- **No duplicate work**: delegating an identical subtask that is still running or already succeeded is refused. A failed one may be delegated again.
- **Cancellation propagates**: cancelling a task also cancels every subtask under it, and a subtask checks whether any ancestor was cancelled.
- **Head conflict (hard requirement 4)**: an objection raised by the logic head blocks the dispatch head's delivery. The result becomes `blocked`, and a `head_disagreement` escalation is sent to the user with both sides' positions. Only the agent that raised an objection can withdraw it.
- **No progress means stop**: `wait_for` explicitly reports whether there were new results, so waiting repeatedly does not count as progress.
- **Models are still entirely the user's choice**: every head, worker and guardian is configured individually.

## 3. Desktop window

- The task list is now a tree: each user task shows its consult, worker and guardian-review subtasks underneath. Clicking any of them shows its step-by-step progress.
- New "Coupling graph" tab: build / refresh, statistics, the most important risk leads (with location and verification method), and lookup / impact / neighbours of any entity.
- The report tab now shows only the selected task's own report, and lists claims from the whole task tree with their status and who reviewed them.

## Not done yet

- Runtime edges (`runtime`): blocked on the tracing SDK and ingest.
- Business invariant / contract definitions (ADR 0004 item 2); state-machine extraction.
- Static analysis for other languages (C#, Java, Go, ...).
- Risk explanation text is in English.
- Full validation against real models: tested so far only with scripted models and once with a local qwen3 4b in basic mode.
