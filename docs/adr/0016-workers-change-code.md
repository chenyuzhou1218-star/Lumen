# ADR 0016: Workers change code; the system supervises every change

Status: accepted (2026-10-28 .. 10-30), built from real DeepSeek runs on planted-bug repositories
(`docs/reviews/2026-10-27-first-real-run-deepseek.md`).

## Context

Code Doctor could only diagnose. On the same 11-bug repository WorkBuddy (one agent, free model) fixed 11/11; Code
Doctor found 10/11 and fixed nothing. Every attempt to let our agents fix failed the same way: they spent the budget
on paperwork (claims, anomaly reports, decisions) before changing a line.

## Decision

1. **Changing code** (`write_files`): `edit_file` (exact text, must occur once; CRLF-aware) and `create_file` (never
   overwrites). Every change is recorded as evidence: the diff plus the changed lines as they now read.
2. **Workers are the hands** (the user's design). With `write_files`, a worker only reads, changes code and runs
   tests. It writes no claims, anomalies or notes; the system lists what it changed. Its guardian is the supervisor
   and the reporter: it gets the diffs up front, re-runs the tests and submits the claims.
3. **Heads give orders.** With `write_files`, the heads have no paperwork tools. The dispatch head hands out FILES
   (`delegate(files=[...])`): one worker per file, a worker changes only its files (plus new tests), and the head
   cannot finish while a code file has no owner. Its own spending is capped (20%), a logic-head consult at 8%.
4. **The system runs the tests** (`permissions.test_command`), not a model: once before the first change (baseline),
   after every change - new failures are in the result of the edit that caused them - and before a worker or the
   dispatch head may finish. No model tokens.
5. Commands run without a shell (arguments split, quoted newlines allowed, shell operators refused). A command run
   is `ev:test:` evidence bound to the code version, so a fix can be `reproduced`.

## Results (13 chained bugs, 20 agents)

9/13 without live tests (one worker broke its own file, 23 tests failed unnoticed) -> 11/13 with them.
Two agents in 双人互检 fixed 12/13 of a 13-bug repository in 127 s; WorkBuddy 12/13 in 228 s.

## Additions (2026-10-30, iterating on the runs)

6. **Regressions vs open tests.** The baseline records passing tests too (`-rA`). A test that passed before and
   fails now is a regression and blocks everyone; a new test that does not pass yet blocks only the worker that
   wrote it.
7. **The worker split.** `ownership.plan`: files joined by imports, shared URL literals (a page and its handler)
   and the coupling graph stay with one worker up to 30 files; larger sets are cut along directories; loose files
   are packed by directory. Measured: splitting 12 tightly coupled files over six workers fixed 7/13, one worker
   13/13. A worker may change another's file (it is told whose) - interfaces cross files, and exact-match edits
   cannot clobber.
8. **Business-rule self-check and hidden defects** in the hands' prompt: money/points/stock never negative, undo
   restores exactly, units match the policy, callers still get what they expect; double actions, wrong-state
   actions, boundaries, time zones.
9. **Account errors** (HTTP 401/402/403, "insufficient balance") are explained in Chinese and pause that endpoint
   for every agent for 5 minutes.
10. **Scale.** Tools run in a pool sized by the agents (the default cpu+4 threads let workers waiting for the test
    lock starve the dispatch head), a test run that started after a request is shared with it, and the token count
    of an investigation is updated incrementally. Scripted 40-agent run: 2344 s -> 39 s.
11. **UI.** Settings → 改代码与测试 (and the first-run wizard); the task page shows 修改与测试 instead of the checklist,
    with an honest status ("完成 · 测试未全过"); one-click undo of an investigation's changes (files edited afterwards
    are skipped); the home page says agents change files here and suggests a git commit.
12. **Pairs that fix together (the user's design, 2026-10-30).** In a cluster of 2 heads + worker/guardian pairs, the
    worker mostly works and is free for the next job as soon as it finishes; its guardian supervises as its main
    job, fixes what its review finds itself (edit tools, in the worker's files - the review task carries them), and
    passes the same tests gate; what it cannot fix goes to the heads. Scripted 40-agent run: 32 s.
13. **Bigger clusters on a cheap model (Flash-1017, 20 agents, 4/13 and 6/13 where a pair fixed 13/13 and 12/13).**
    A worker read the whole package twice before its one edit; its edit used a module it did not import; the
    guardians, started last, found the reserve spent by the first of them. Now: a worker's order carries its own files
    (exact text) and an outline of the other code files; a guardian's review carries the worker's files as they are
    now and why the tests fail (the failing lines, not just the names); the review reserve is split per pair at work;
    and when every agent has stopped with a test still broken that passed before, the system undoes the change after
    which it broke (that file's changes from there on, all or nothing) - the code is never left worse than it was.
14. **The squad (the user's design, 2026-10-31).** Splitting coupled code by files made 20 agents worse than one pair
    (19/37 vs 36/37 on Flash). With heads, write_files and a test command (`cluster.squad`, on by default), the system
    itself starts, without head tokens: the MAIN pair on the whole project with about a lone pair's budget (45%) - the
    floor is a 双人互检 run; up to two ALTERNATE pairs fixing the same task in their own copies (25%, different angles);
    the other pairs are SCOUTS (20%): the worker writes one test per business scenario the dispatch head names
    (`scout`), test files only; its guardian checks the tests say what the spec says. A failing scout test is copied
    into the alternates' copies and reaches every fixer between its steps; a fixer is asked once to fix the scout
    tests that still fail before it finishes. The heads name scenarios and pass findings on (`tell_fixers`), at most
    10% together. At the end the system runs every test file any version has against the main version and each copy,
    keeps the one that passes the most (ties keep the main one) and copies it into the project; then the safety net.
15. **Backups instead of alternates (2026-10-31, measured).** First real squad runs on Flash: chainshop 4/13 -> 13/13,
    gym 9/11 -> 10/11, library 6/13 -> 9/13. The two alternate pairs fixing their own copies lost every comparison to
    the main version (a third of its budget) and spent 28% of the budget, while four bugs the scouts had found in
    library stayed unfixed. Now those pairs are BACKUPS: the system gives each failing scout test to an idle backup
    pair (two test files per task, 25% of the budget for all backup tasks), which fixes it in the project next to the
    main pair; the main pair is told who is on it and is not asked about it at its finish. A backup's guardian checks
    the fix against the README's rule. The squad's head is not held by anomaly paperwork: the tests settle the code
    and the open anomalies are listed in its answer. wait_for without ids also waits for subtasks the system starts.
16. **Scout tests checked by the system (2026-10-31, measured).** Squad with backups on Flash: 35/37 (chainshop 13/13,
    library 12/13, gym 10/11) against a pair's 36/37 and WorkBuddy's 35/37. The main guardian ran out of budget in two
    runs while scouts and their reviewers spent 27%; and a scout's test for a reported double booking passed on the
    buggy code, so nobody fixed it. Now scout tasks get no guardian review: when the system starts the squad it keeps
    a copy of the code as it was, and runs each new scout test there too - one that passes on the original code
    reproduces nothing, and the scout is told once to reproduce exactly what the user reported. Shares: main pair 51%,
    backups 25%, scouts 14%, heads 10%.
17. **Six agents (2026-10-31, measured).** 2 heads + 2 pairs on Flash: 36/37 (chainshop 13/13 in 200 s, library
    12/13, gym 11/11) - the same as 双人互检 with 7% less time and 10% fewer tokens; 20 agents 35/37 for twice the
    tokens. With two pairs the scout pair is also the backup pair; the system now counts a worker whose task is
    finishing as free (it skipped it as busy and a failing scout test stayed unfixed). The head is told the rules
    nobody writes down (the same person repeating an action on the same item), and scouts test a double action on an
    item with several copies. The task page shows each agent's part and the scouts' findings (who found, who fixes,
    fixed or not). The settings and the first-run wizard recommend 6 agents for changing code. Each response records
    the provider's prompt-cache hits (a simulation from the journal: 80-90% of each request repeats the previous one).
