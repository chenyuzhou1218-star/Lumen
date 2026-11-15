# Trial repositories and the benchmark (ADR 0016)

Planted-bug repositories used to measure Code Doctor with a real model, and the scripts that run and grade them.

| repos/ | bugs | grader | prompt |
|---|---|---|---|
| chainshop | 13 chained (orders - events - inventory/shipping/loyalty - payments - reports) | grade_chainshop.py | chain-prompt.txt |
| library | 13 coupled (counters/catalog, holds/loans, fines/reports, web/api) | grade_library.py | race-prompt.txt |
| gym-booking2 | 11 (stats/classes, waitlist, policy, reminders, web) | grade_gym2.py | gym2-prompt.txt |

Each grader runs every defect's scenario in a fresh process against a fixed copy and prints `N/M 个 bug 修对`.
Answer keys are the graders themselves (and `make_chainshop.py`, which writes chainshop and its key).

Run one benchmark (it spends model tokens - DeepSeek by default, keys from the Windows credential store):

    python bench/trials/bench.py chainshop 2 750000 "label"

It copies the repository to a fresh folder next to the script, writes a config (2 = 双人互检, otherwise 2 heads +
worker/guardian pairs), runs Code Doctor headless, grades the result and appends a line to `results.jsonl`.

`stress_scripted.py [workers] [timeout]` runs a 40-agent cluster with scripted models (no tokens) to check that the
system itself scales: 19 workers fixing 19 modules at once finished in 39-51 s after the fixes of 2026-10-30
(2344 s before).

Results so far: docs/reviews/2026-10-27-first-real-run-deepseek.md.
