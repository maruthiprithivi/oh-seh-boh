# Multi-team test project

This directory is an executable **isolated reference lab**, not an operational coordination service. `osb.lab.v1` implements enough transitions to test OSB's model with real independent processes. Synthetic actors are injected by the test supervisor; any local caller can select a synthetic actor. It therefore cannot authenticate real users or enforce a real team's access. Use private disposable files only. Eleven correctness and five generic CI methods passed in the [2026-10-04 bounded Linux baseline](../docs/linux-baseline.md). Two short profiles had zero observed safety violations; contention failed its predeclared fairness gate. Saturation/soak remain unrun. The bounded conflict-backoff source change is unexecuted and creates no backend fairness queue.

## Progressive scenarios

| Level | Workload/failure | Evidence |
|---|---|---|
| 1 | Two worker processes claim overlapping resources at a barrier | Exactly one live grant; denied actor receives no authority |
| 2 | Distinct files, several team labels in one repo, independent repo scopes | Useful concurrency; cross-scope read/write rejection; one claim domain per repo |
| 3 | Expiry at exact virtual deadline, revocation and stale protected writes | No resurrection; fence increases; former holder cannot mutate mock consumer |
| 4 | Named task handoff and separate integration-owner transfer | Offer alone grants nothing; atomic reference transfer changes fence; occupied effect blocks primary transfer |
| 5 | Lost response after commit; duplicate/reordered projection | Original receipt/effect retained; local sink dedupes event IDs and rejects old state ordering |
| 6 | Process exit before commit, stale backup restore, quarantine | Pending journal blocks work; explicit lab recovery replays confirmed history and changes authority ID |
| 7 | Spoofed body identity, reader mutation, wrong repo/event scope | Model authorization refuses; synthetic identity is not SSH/security proof |
| 8 | Independent burst, contention burst, saturation, bounded soak | Throughput, latency/fairness, wait, retries, resources and historical overlap/receipt invariants |

`scenarios.py` uses subprocesses for competing claims and commit-boundary crash injection, plus real SQLite state. `load.py` uses independent multiprocessing workers with deterministic seeds. It performs actual reference-backend transactions; it does not run OMP, Claude, Codex, OpenCode, Cursor, Antigravity, Kiro or Kimi. Harness labels are tags in metrics only.

The mock protected consumer writes inside the same SQLite transaction as its fence check. That tests a meaningful atomic boundary for the reference model; it is not proof that GitHub push, PR merge, CI or deployments have equivalent fencing. Integration effect records do not execute a forge merge.

`ci_scenarios.py` adds four generic process-based CI coordination checks: declared base/head binding, release and retry after lost cancellation reply, obsolete session result and replay-key evidence substitution, and a competing migration-directory claim race, plus one result-classification fixture method. All five passed in the bounded baseline. See [scope and missing real-CI capabilities](../docs/ci-coordination.md); these fixtures contain no incident data or inferred application failure causes.

## Backend boundaries

One host-local lock and SQLite database serialize requests. A one-second lock wait returns `busy`; clients keep request IDs and retry twice with backoff. Payloads are bounded to 64 KiB, resources to 100 entries, pages to 100, test workers to 64 and total task attempts to 20,000. Pending projection events have a configurable ceiling; new workload mutations backpressure, while read/revoke/release/ack remain available. Safety-event growth is not silently dropped.

The clock is virtual and advanced only by the fixture administrator. It permits exact deadline/clock-failure tests and does not claim real-time unattended lease service behavior. Intent revisions use full synthetic SHA-1 OIDs; no filesystem symlink resolution or real Git diff coverage is implemented.

Confirmed transaction statements are retained in a durable local JSONL journal, with an fsynced pending/high-water marker. Normal calls inspect the private marker/current database; full journal parsing/replay occurs only in explicit recovery, where corrupt/torn data refuses recovery. Normal requests do not scan/verify the entire historical journal. This journal contains synthetic ledger data and grows with transitions; no retention deletion is implemented. A backup without journal/marker is insufficient. Explicit abandonment of an unconfirmed transaction is a fixture operator action, not an automatic production recovery policy. Recovery revokes claims/sessions, quarantines memberships, increases fences and changes authority identity. A failure of fsync/disk or OS transport security needs further validation.

SQLite remains one writer; no distributed election, copied live databases or cross-partition atomic claims. Increase independent project partitions only after measurement and keep one authority for any shared resources. Outbox/mock-projector storage is local; no GitHub API stress occurs.

## Commands and allocation

Only run in an approved disposable Linux environment. No source creation authorization grants cloud spend or runtime installation. Python 3 standard library with SQLite is enough for this lab; the existing-authority integration layer may need that owner's additional pinned test tools.

```sh
python3 lab/scenarios.py
python3 lab/ci_scenarios.py
python3 lab/load.py --test-only --profile independent --agents 8 --operations-per-agent 30 --seconds 30 --output evidence/independent.json
python3 lab/load.py --test-only --profile contention --agents 16 --operations-per-agent 50 --seconds 60 --output evidence/contention.json
python3 lab/load.py --test-only --profile saturation --agents 8 --operations-per-agent 50 --max-pending 50 --seconds 30 --output evidence/saturation.json
python3 lab/load.py --test-only --profile soak --agents 16 --operations-per-agent 1000 --max-pending 100000 --seconds 60 --output evidence/short-soak.json
```

Soak runs until its wall-time **or task-attempt cap**; record actual duration/operations before labeling it a soak. A longer authorized qualification profile can increase time up to 3600 seconds while keeping bounded attempts; it still needs budget approval and sufficient attempts to reach the intended duration. Saturation is expected to produce backpressure rather than pretend all work was admitted. Evidence must retain failed/partial worker results; zero measured operations or claims fails the run. Missing workers, double ownership or lost acknowledged transitions fail regardless of throughput.

No fixed latency target is claimed before measurement. Set regression thresholds only from an approved baseline with machine size, Python/SQLite versions, exact source commit, worker count, resource overlap, journal/fsync configuration and sampling duration recorded. Jain's index reports success distribution; this backend has no starvation-preventing waiter queue. Claim wait is successful claim-call time, not time in a durable fairness queue.

Initial estimate: 10–15 minutes for source checks, deterministic scenarios and four short profiles on an existing 2-vCPU/8-GiB disposable Linux allocation. This is unmeasured, excludes provisioning/owner suites and does not establish thorough multi-hour stress qualification. A combined one-hour window may fit short validation but not real harness runs or extended soak. No allocation is approved by these files.
