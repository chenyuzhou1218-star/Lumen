# ADR 0010: Evidence-gated multi-Agent business investigations

Status: implemented vertical slice; external adapters and real-model evaluation pending.

## Decision

The backend owns investigation state, assignments, evidence validation and delivery permission. Two heads plan and schedule; configured Workers execute; their separately configured Guardians independently execute. An Agent's prose, confidence, or majority vote cannot authorize delivery. Each Agent's endpoint/model remains explicitly user configured; existing fallback policy is retained.

Business coupling starts with typed upstream graph paths. These are structural candidates, never established causes. A plan binds symptoms, competing hypotheses, discriminating predictions, approved business invariants, regression checks, scenario handlers, execution budget and code snapshot. Unknown evidence remains unknown. Candidate traversal reports truncation.

Every check runs baseline, fault and rescue, repeated independently by Worker and Guardian. SQLite receipt records reference immutable content-addressed raw metrics and harness source. Delivery recomputes invariants from those bytes and validates actor, assignment, snapshot, source hash, controls and independent signatures. All checks and affected-business regressions must settle, exactly one declared hypothesis must remain compatible, descendant tasks must succeed, and no head objection may remain. Compatibility is limited to the declared experiments, not proof of universal causality.

Task creation, assignment binding and bus message insertion share one SQLite transaction. Notification follows commit. Check reservation and trial uniqueness prevent duplicate concurrent execution. A trial interrupted by a crash does not silently rerun. A new process must explicitly register trusted scenario adapters again; the database never imports executable code.

## Trust and safety

Business contracts require explicit trusted application/user approval with source evidence; Agents have no contract-approval tool. The small invariant DSL supports equality, integer sum conservation and unique keys; no eval or arbitrary expressions. Missing, malformed or unsupported metrics cannot become a successful check. Heads cannot acquire terminal or experiment execution by overriding their tool list.

Scenario handlers run trusted Python code in-process. Cancellation and time limits are cooperative between calls and do not terminate a blocked handler. This is not an isolation boundary for arbitrary repositories. General code execution requires a separately permissioned, isolated adapter and hard process limits. Harness hashing covers the handler source, not every transitive dependency or an external attestation. Distinct source and runs prevent simple receipt reuse; they do not prove semantic independence of two faulty implementations.

Additive cluster tables have their own schema version; existing daemon tables, WAL storage, evidence protocol and Agent/config protocols are reused without inventing event/evidence/claim fields. Plan schema ID is `https://code-doctor.local/schemas/v0/cluster/plan.schema.json`; the installed schema file is authoritative. Existing evidence-store methods construct protocol records and collectors use `cluster.experiments/0` and `cluster.harness/0` identifiers. A future incompatible plan version needs a new ID and explicit migration.

## Product scope

The complete three-core target remains: cross-end/cross-service event tracing, business coupling reasoning, and future-bug simulation, with long-term memory, permissions, repair, independent verification and UI. This increment implements the experiment-backed cluster loop and typed graph interface. It does not claim distributed trace coverage, arbitrary-project bug discovery, autonomous patch generation, production isolation, or real-model reasoning quality. Future adapters must bind OpenTelemetry/event correlation and causal claims to actual evidence, preserve unknown/missing coverage, and generate new fault scenarios for predicted future failures. Existing FastAPI daemon, SQLite WAL, content-addressed evidence and memory remain the foundation. Claude can develop UI against the additive read APIs independently.
