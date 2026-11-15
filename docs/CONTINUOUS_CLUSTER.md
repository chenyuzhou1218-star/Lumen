# User-adjustable, continuously reasoning dual-head cluster

Implemented increment after `d7fe62f`: configurable topology, persistent reasoning scheduler and large influence-tree queries. No frontend changes.

## Configure

Add this optional section to an otherwise valid project configuration:

```json
{
  "cluster": {
    "enabled": true,
    "max_agents": 40,
    "foresight": {
      "enabled": true,
      "interval_s": 30,
      "max_steps_per_cycle": 8,
      "max_tokens_per_cycle": 20000,
      "reserved_tokens_per_hour": 1000000
    }
  }
}
```

The user still supplies every Agent, role, endpoint, model and fallback. These are limits, not a command to create forty Agents or choose their models. The global maximum is forty configured Agents, including heads and Guardians. Enabled clusters require exactly one dispatch head, one logic head, and exactly one distinct Guardian for every Worker/investigator. A forty-Agent topology therefore contains two heads and nineteen pairs. An odd configured maximum can leave one slot unused. Raising the limit never spawns Agents. Changing the configuration requires daemon restart; live resize is not implemented.

Legacy non-cluster configurations keep their previous pairing rules, but are still limited to forty configured Agents. Continuous foresight requires the explicit cluster configuration above. The development daemon does not make new background API calls unless that switch is enabled.

## Continuous reasoning

The daemon schedules both heads even when no user task arrives. Each completed cycle is followed by another once its configured interval permits. Worker activity does not block an otherwise idle head. Each Agent retains one task/model context at a time: a busy head does not run a second hidden conversation concurrently. Its next cycle resumes when it is free. Recent task state and reports feed the next cycle with their strictest data classification; endpoint privacy checks remain effective. Both heads are instructed to propose future failures, trace downstream consequences, challenge competing explanations and specify falsifying tests. The dispatch head retains existing tools to assign real Workers; Guardians independently verify through the existing runtime.

Queued/running head tasks, pending user controls, paused/stopped/error states and unavailable models suppress new scheduling. In particular an unavailable primary does not cause model substitution outside its explicit fallback list. Reservations, timestamps and task publication share a transaction, preventing duplicate concurrent scheduling. They persist across restart. Each cycle uses a bounded step/token budget; the hourly reservation ceiling throttles admission. Reservations are not refunded from reported usage. This is a conservative scheduling allowance, **not an exact provider billing cap**: a single API request may exceed a token budget before usage is returned. Existing context estimation is approximate and provider output limits remain important. The hourly allowance rolls forward, so enabled heads continue later unless paused/stopped.

`GET /cluster/foresight` exposes enablement, the size ceiling and recent cycle records. Existing control routes pause/resume/stop individual heads. Setting foresight disabled and restarting stops future admission. Existing journal routes expose model requests/responses, tool arguments/results, task reports and original blob payloads for local review. These are observable actions and explanations; private model chain-of-thought is neither required nor exposed. Logs should remain protected by the daemon's deployment/access boundary.

## Business effect propagation

`cluster_impact` is available to heads, Workers and Guardians. It follows typed return-value/state/event influence from an exact graph node, retaining source paths, lines and provenance. It uses an iterative influence tree with bounded nodes, cycles and explicit truncation. Up to 50,000 reachable nodes can be requested; the complete tree is stored as evidence and the model sees the first 64 nodes plus the evidence ID. This is not enumeration of every possible execution path. Missing/dynamic edges and excluded ambiguous/inferred relations are not evidence of absence. The test covers a 3,000-edge propagation chain without recursion.

A structural blast radius can motivate broad regression and future-fault experiments; it does not establish that all affected nodes have a bug. The preceding experiment engine still requires distinct independent runs and raw evidence. Automatic correction of thousands of paths, continuous model-based review while a Worker is mid-tool, Guardian reassignment into unsupervised repair roles, native integration with every provider, and guaranteed superior repair quality are not established by this increment.

## Context and long-term capacity

Every Agent retains its own configurable `context_budget_tokens`, memory and journal. Large values are accepted as user budgets, not verified model capabilities; tests accepting 500 million do not mean any provider supports it. Context is not padded to that number, and a provider can reject an oversized request. The capability status explicitly says the limit is unverified. Neither M-sized storage nor compressed recall creates an M-token native context window. Use the actual chosen model's published or discovered limit; recommendation of a flagship head remains advice, never automatic assignment. API context optimization must preserve facts, locations, versions, evidence, prohibitions, conflicts and unresolved questions; that separate API optimization pipeline was not implemented here.
