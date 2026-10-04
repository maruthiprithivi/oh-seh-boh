# Bounded Linux baseline — 2026-10-04

Status: **first behavioral slices passed; qualification incomplete**. This reports reviewed receipts from an approved, disposable, externally supervised Linux execution. It does not claim the consolidated `validation/run.py` job ran, that all harnesses were installed, or that OSB is production ready.

## Exact public source and evidence identity

- Reference OSB: `61744a0850a2a9d6b843e22980973e9c3d3be44f`.
- PStack opt-in proposal: `5168f575f1ae6269850cb6dcd895e9b538bfc276`, PR497 remains draft.
- Frozen first-run archive SHA256: `647f649ac6a4be594afa7818798acd8ad3d790ba455c7e007b844344a791efff`.
- Private combined evidence archive SHA256: `b5e4335605166bb39a0b5459b029d1042e9cfd8cd30996790c2425c43acfc689`. The evidence custodian retains raw logs, versioned authority provenance, manifests, synthetic DB/store/journal snapshots and cleanup receipts. It is not a public download; this page exposes no private source/pins, paths, access identifiers or credentials.

The final guest supervisor checks clean source pins, the authority bundle digest and the frozen manifest's nine source hashes before execution, then clean pins again after it. The downloaded evidence digest matched before inspection. The five-test and ten-test raw unittest logs, native four-case report, provisioning provenance and supervisor code were inspected, alongside the original reference logs and failed setup trace.

## Actual results

| Stage | Result | Revision and measurement |
|---|---|---|
| Reference correctness | 11 methods passed, zero skips | Original exact OSB source; raw unittest duration 2.361s |
| Generic CI/reference classification | 5 methods passed, zero skips | Same original source; raw unittest duration 3.887s |
| Actual endpoint acceptance | 5 methods passed, zero skips | Corrected, independently reviewed supplied authority; stage wall 13.741s, unittest 13.519s |
| Actual-authority/mock-publisher lifecycle | 10 methods passed, zero skips | Same corrected authority and unchanged PStack tests; stage wall 71.416s, unittest 71.318s |
| Actual installed PStack | 4 scenarios passed, mutation `none` | Same corrected authority and actual native PStack store; stage wall 11.219s |

The original reference results were retained across the authority-only retry, not rerun or represented as validation of the corrected authority. The historical endpoint attempt produced **five setup errors** from a supplied authority Python indentation SyntaxError, before behavioral assertions. Its raw failures remain in the combined evidence. The independently reviewed one-line indentation correction passed a guest syntax check and the complete affected stage set. Corrected-source success does not retroactively validate the failed revision; exact private old/new pins remain in the custodian's receipt.

The final job exited zero at **2026-10-04 14:12:47 UTC**. Python was **3.12.3**, its SQLite library **3.45.1**, isolated SQLite CLI **3.50.4**, Bun **1.3.14+0d9b296af**, Commander **14.0.0**. Provisioning used official fixed archives and `bun install --production --frozen-lockfile --ignore-scripts --no-progress`, with unchanged source manifest/lockfile and verified native bootstrap marker. This was runtime-only dependency preparation; no TypeScript typecheck/full native PStack test suite is claimed.

## Independent installed-store observations

| Case | Actual native store | Worker | Authority observation |
|---|---|---|---|
| Success | Exactly one expected PR/head/`unit-test-verified` row, evidence path retained | Started | Claim released; zero active claims |
| Invalid store | Intentionally malformed header observed; no fabricated zero-row success | Never started | No claim; zero active claims |
| Session revocation | Readable native header, zero verdict rows | Started before revocation | Claim revoked; zero active claims |
| Cancellation | Readable native header, zero verdict rows | Started, then cancelled | Release acknowledged; zero active claims |

Each case had an empty violations list. Native init/summary/record/check and independent TSV/read-only claim observations provide evidence beyond the runner's self-reported outcome. Revocation correctly reports `release: pending-or-stale` alongside a separately observed revoked claim; do not rewrite that receipt as acknowledged release. A worker having started is also distinct from its later verdict effect being prevented.

The external supervisor recorded a two-CPU quota, 4GiB memory maximum, low CPU/I/O weight and control-group cleanup. Final-job CPU was 29.365s and recorded memory peak about 360MiB; these are this job's resource measurements, not throughput/capacity claims. Cleanup receipts confirm owned guest files removed and temporary access removed, with the existing shared VM preserved. Actual incremental billed cost is unknown; no budget figure is reported as measured spend.

## Subsequent reference profile failure

Two short reference-model profiles were measured on the same exact OSB target, each with eight workers, 30 task attempts per worker and a 30-second ceiling. Independent: **81.443 operations/s, p99 0.899s, Jain fairness 1.0**, 11.787s actual duration; all eight actors received 30 grants. Contention: **129.681 operations/s, p99 0.779s, Jain fairness 0.2903**, 4.072s actual duration; grants were distributed 0,0,4,0,0,0,6,14. **Contention failed the predeclared >=0.5 fairness gate.** The threshold was not changed. Missing workers, protected-effect failures and independently observed safety/live-claim violations were zero. The independent oracle's positive control and five negative assertions passed. Maximum individual worker RSS was 29,544KiB across the two profiles; aggregate memory was not captured.

These are reference-model measurements, not actual-authority/PStack capacity. The private profile evidence archive SHA256 is `7a58b4d20ca3871385fd1b731e938c4f9baf156f21b7d03d4b9e92263d05b4dc`. Its receipt corrects an inherited controller source-packet label: the actually staged readiness archive was `301a6e97bd7819d6560ae6d0d345d6547cee7d990f2ea770c459a2f5008e5d08`. Functional tests were not repeated. Raw reports and failure are retained.

Source diagnosis: the original load driver consumes a finite task slot immediately on claim conflict, retries only `busy`, and starts the next intent without conflict backoff. It exhausted the 240-attempt ceiling after 216 conflict refusals and only 24 grants, well before the time ceiling. This explains short-run opportunity imbalance; it does not prove indefinite starvation or excuse the failed gate. The reference backend has no fairness queue, so backend starvation freedom remains unproven.

The scoped load-driver source change adds at most eight cooperative conflict retries with 10–50ms jitter per task, retaining the same intent/request bytes and shared deadline. Every refusal remains measured. Reports expose retry-policy version, actual task attempts and conflict retries. Authority and PStack behavior, task ceilings and the >=0.5 gate are unchanged. This **changes the workload retry policy**; any new results require the new exact source pin and cannot overwrite or be compared as an identical-policy baseline. The change is unexecuted until the parent's admitted retry. It promises no fairness queue or starvation guarantee.

## Remaining gates and minimum next job

Subject to parent admission and independent source review, the immediate affected job reruns **independent and contention profiles only**, using the exact changed load driver, retained observer bytes and the same eight workers/30 attempts/30-second ceiling and >=1 ops/s, <=2s p99, >=0.5 fairness gates. Preserve the original failure. Continue the **two existing disposable mutation controls**, saturation and short-soak profiles only when separately admitted remaining time permits. Do not rerun the 16 reference methods or 15 endpoint/lifecycle fixtures for this load-driver-only change. Proposed next-slice envelope: 1–2 admitted CPUs, existing contained Linux allocation, <=20 minutes including setup/cleanup, remaining approved spend cap monitored externally. This is an unmeasured estimate and not an allocation or access grant. Provisioning is needed again because owned resources/access were cleaned.

Retain specific forbidden observations for mutations, actual operations/duration/latency/fairness/backpressure for profiles, and all failed/partial results. Profile time limits are ceilings, not proof of sustained soak. Full authority-owner suites still need their own exact reviewed validator and feasible time allocation; source compile and endpoint tests do not replace them.

Controlled-pilot gates in [readiness](readiness.md) therefore remain unmet: **failed contention fairness**, mutation controls, remaining bounded profiles, exact owner suites and operator failure/recovery rehearsal. Production additionally needs actual-authority sustained load, deployed transport/principal/revocation evidence, backup/restore/RPO/RTO/availability operations, installed-harness acceptance, license decision and any required fence-consuming external gateway. No live Git/CI/merge/deploy effect or atomic external fencing was tested.
