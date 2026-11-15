# ADR 0004: Seven hard requirements

- Status: proposed (pending review)
- Date: 2026-10-24
- Author: Claude (the user proposed the seven requirements; this document turns them into rules and records how each is implemented)

| # | Requirement | Status |
|---|---|---|
| 1 | Observation coverage list | ✅ implemented |
| 2 | Business invariants and interface contracts | 📋 rules defined; to be implemented with coupling analysis |
| 3 | Promotion rules for hypotheses | ✅ implemented |
| 4 | Conflict handling between the two heads | 📋 rules defined; to be implemented with the dual-head cluster |
| 5 | Task recovery and side-effect ledger | ✅ implemented |
| 6 | Version binding and evidence invalidation | ✅ implemented (config / DB-schema versions are not collected automatically yet, see below) |
| 7 | Bounded fault injection | 📋 rules defined; to be implemented with future-bug simulation |

---

## 1. Observation coverage list ✅

- Schema: `schemas/event/coverage-status.schema.json`
- Code: `daemon/codedoctor/telemetry.py`; `GET /coverage`, `codedoctor coverage`

There is one row for every service × layer pair and for every business stage of every chain template. Each row has one of four states:

| State | Meaning | Determined by |
|---|---|---|
| `healthy` (collecting normally) | Declared, and recent health reports show nothing lost | All of: heartbeats on time, consecutive heartbeat sequence numbers, 0 dropped spans, 0 export failures, 0 context-parse failures, export queue never full, sampling at 100% or decisions recorded |
| `degraded` (collection problem) | Declared, but data may be missing | Any one of the conditions above fails |
| `declared` (connected) | Declared, but no health report has arrived yet | — |
| `not_instrumented` (not connected) | Nothing observes it | No declaration, or the probe only covers listed routes/tables and this stage's route is not among them |

A `healthy` row must cite both the coverage declaration and the health report it was judged on (the schema enforces this). **Only `healthy` rows can support a conclusion that something did not happen** (this corresponds to the `confirmed_absent` checks in gap assessment).

## 2. Business invariants and interface contracts 📋

Rules (to be implemented with coupling analysis):

- **An invariant is a first-class object**, not a sentence. Each one records: id (`ent:invariant:<name>`), a description, the entities it covers (tables / fields / routes / states), **how it is checked** (e.g. a reconciliation query: total balance change = ledger entries over the same period; for each request id, at most one payment record), severity, and who confirmed it.
- **AI-proposed invariants are only candidates until the user confirms them** (same rule as chain templates). A violation of an unconfirmed invariant may not be reported as a bug.
- **An interface contract** records: request and response structure, error semantics, whether the call is idempotent and what its idempotency key is, timeouts and retry policy. A pair of "non-idempotent + caller retries" is matched automatically as a future-risk candidate (fault model `fm:duplicate_request`).
- Violations are expressed as claims with `relation: violates`, and evidence must come from actually running the check.

## 3. Promotion rules for hypotheses ✅

- Code: `daemon/codedoctor/claim_rules.py`, `evidence/validator.py`
- Schemas: `claim/status-event.schema.json`, `evidence/validation-result.schema.json`

**Nobody approves their own conclusion.** The author can only submit (`proposed`) or withdraw (`withdrawn`). Every other status change is made by the rule engine (`by: system`), and every change is recorded together with its basis.

| Transition | Conditions (all must hold) |
|---|---|
| `proposed → supported` | Evidence level is not `speculated`; four-level evidence validation is `accepted`; **at least one `reverified` review from someone other than the author** (another agent or the user); no `insufficient_evidence` review after the most recent re-check; every claim it depends on is already `supported`; not stale |
| `proposed → refuted` | A reviewer other than the author submits a `counterexample` with registered, intact evidence; **or** the claim's own predicate evaluates to false |
| `proposed/supported → needs_revalidation` | See item 6 |
| `→ superseded` | A new claim names this one in `supersedes` |

The four levels of evidence validation:

1. **Exists**: the evidence id is registered (fabricated ids are already rejected when a claim is submitted).
2. **Integrity**: the stored bytes still hash to the recorded value.
3. **Binding**: code / config / DB-schema version, trace and action match the claim (or the reference's `expect_binding`).
4. **Support**: predicates are evaluated by machine (`machine_verified`), or someone other than the author has re-checked it (`independently_verified`). "The evidence id exists" never counts as support.

**How the evidence level goes up (speculated → inferred → reproduced):** the level of an existing claim never changes. To go up a level, submit a **new claim** that cites the new evidence (for example, a reproduction run made with an intervention) and points to the old claim via `supersedes`. The old claim becomes `superseded`. Each step in the chain keeps its own evidence and reviews.

Tools agents can use: `check_claim` (see exactly what is still missing), `review_claim` (review someone else's claim), `withdraw_claim`. The user reviews through `POST /claims/{id}/reviews`.

## 4. Conflict handling between the two heads 📋

Rules (to be implemented with the dual-head cluster):

1. **Safety and authorization are vetoed by an independent controller.** The controller is deterministic code, not a model: permissions, data classes, the production-environment ban and fault-injection boundaries (item 7). A veto cannot be overruled by any head or worker, and is reported as an `escalation` with `reason: safety_veto`.
2. **Insufficient evidence cannot be marked verified.** This is already enforced by the claim rules in item 3; agreement between the heads cannot get around it.
3. **Major disagreements go to the user.** When logic head A judges that a risk exists (an open `risk_prediction` / a `supported` defect claim) and dispatch head B judges the work can be delivered, the delivery decision is blocked. Both sides' claims and evidence are packaged into an `escalation` with `reason: head_disagreement` for the user to decide.
4. A disagreement can first go through an independent investigation agent for one round of fact-finding, but the investigation's conclusion still has to pass the item 3 rules.

The message protocol already includes the `head_disagreement` and `safety_veto` escalation reasons.

## 5. Task recovery and side-effect ledger ✅

- Schema: `agent/side-effect.schema.json`
- Code: `agents/effects.py`, `agents/runtime.py` (`recover_interrupted`, `_resume_task`)

- Every tool is classified (by its tool definition, never by the model): read-only / `internal` (only changes Code Doctor's own records) / `external` (changes the project or the outside world), plus whether it is `retry_safe`.
- Before any non-read-only tool runs, an `intent` entry is written to the ledger; afterwards it becomes `done` or `failed` and links to the result.
- **The task is marked running before its message is marked delivered**, so a crash between the two cannot lose the task.
- At service startup:
  - every task still `running` becomes `interrupted`;
  - every ledger entry still at `intent` becomes `unknown`;
  - **nothing is retried automatically**;
  - an `interrupted` report is sent to the requester, listing what is done, what is unknown, and what is not safe to retry.
- **Resuming (`resume_task`) is not "start over"**:
  1. The original conversation is rebuilt exactly from the journal, and every call without a result is marked "outcome unknown".
  2. A reminder is appended: actions with an unknown outcome, or that are not safe to retry, must not be repeated; first check their actual effect with read-only tools, or ask the user.
  3. Step and token counts carry on from where they stopped.
- Resumable outcomes: interrupted, blocked, budget_exhausted, stalled.

## 6. Version binding and evidence invalidation ✅

- Code: `currency.py`, `claim_rules.py`

- **Code version** = a snapshot id of the whole working tree. A clean git checkout uses its commit id. Otherwise the id is `wt-<sha256>`, computed from HEAD plus the contents of every modified and untracked file (outside git, from file names, sizes and modification times). All evidence collected from the same state shares one version.
- Claim scopes and evidence bindings now also have `config_version` and `db_schema_version` fields.
- **Precise invalidation:** a claim that cites code excerpts becomes `needs_revalidation` only if one of those excerpts no longer appears verbatim in its file. Edits elsewhere in the file, or the excerpt simply moving, do not invalidate it. A claim with no code excerpts becomes stale on any version change, because nothing can show it is unaffected.
- A config or DB-schema version mismatch (when the current version is known) → `needs_revalidation`.
- **A stale conclusion is not a current fact:** it cannot be promoted, and must be replaced by a new claim made against the current version.
- When the service starts, all open claims are re-checked automatically (`refresh_all`). `POST /claims/refresh` is also available.
- **Memory is checked too:** when a memory note's cited code has changed, recall marks it `[POSSIBLY OUTDATED: …]`.
- Evidence itself never expires: it is a historical fact about its own version. What expires is a **conclusion's** claim to describe the current system.

**Not done yet:** collecting the application's config version and DB-schema version automatically (needs a project adapter, e.g. reading the migration table). Until then, these two checks only take effect when the versions are supplied.

## 7. Bounded fault injection 📋

Rules (to be implemented with future-bug simulation):

- Every injection needs a **fault-injection plan**, checked by the independent controller (item 4) before it may run. The plan must state:
  - **Target environment:** `local` / `test` / `staging`. **`production` is refused by default**; even when the user enables it, every single injection needs separate approval.
  - **Scope:** which services, endpoints, connections or processes.
  - **Fault:** a fault-model id (`fm:duplicate_request`, `fm:response_lost_after_commit`, `fm:network_partition`, …) and its parameters.
  - **Duration and count limits:** stop automatically when they are reached.
  - **Data:** only test data or a snapshot copy; real user data is never written.
  - **Recovery:** how it is cleaned up afterwards (remove the proxy rule, roll back the database snapshot, restart the service), plus how to verify the recovery succeeded.
  - **Approver:** who approved it, and when.
- Every injection writes `external` side-effect ledger entries (item 5), so after an interruption it is known which injections may still be in effect, and recovery reminds the user to carry out the recovery steps.
- An injection result can only serve as `reproduced` evidence; the item 3 rules still apply.
