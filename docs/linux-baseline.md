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

The scoped load-driver change adds at most eight cooperative conflict retries with 10–50ms jitter per task, retaining the same intent/request bytes and shared deadline. Every refusal remains measured. Reports expose retry-policy version, actual task attempts and conflict retries. Authority and PStack behavior, task ceilings and the >=0.5 gate are unchanged. This **changes the workload retry policy**; new results have their own exact source pin and cannot overwrite or be compared as an identical-policy baseline. It promises no fairness queue or starvation guarantee.

## Measured bounded retry workload

The affected retry ran at exact OSB **`02900a253dd609b88a54c51ac9733f055b137469`**, with verified load-driver SHA256 `09a997fff28839a289ec107f8cf16c96fe1fd9676afbfaf7b9575951a2577ba5`. The private combined retry evidence archive SHA256 is `ca46eba9f50203c5be19bf318cec6c8fdbeb3164944c75bb1c5a276ea8a1cbd7`. Its raw reports, independent snapshot oracle outputs, source/hash assertions and cleanup receipts were inspected. The same eight workers, 30 task attempts per worker, 30-second ceiling and thresholds **>=1 operation/s, p99 <=2s, Jain >=0.5** were retained.

| Profile | Actual duration | Operations/s | p99 | Jain fairness | Result |
|---|---|---|---|---|---|
| Independent | 10.113s | 94.928 | 1.145s | 1.0 | All gates passed; 240 grants, 30 per actor |
| Contention with bounded conflict backoff | 9.947s | 120.838 | 0.395s | 0.9899 | All gates passed; 207 grants distributed 30,29,27,26,26,22,23,24 |

Contention retained **341 conflict refusals and 308 conflict retries**. Both profiles returned all eight workers, had zero reported protected-effect failures and zero independently observed safety/live-claim violations. The prior positive/five negative oracle controls were reused only for unchanged observer bytes; both new snapshots were checked freshly. There was no functional/endpoint/PStack rerun and no authority change.

The retry supervisor recorded aggregate cgroup peak **167,333,888 bytes (159.6MiB)**, CPU **7.052s** and zero throttled periods. These measurements cover this short job, not a production fleet. Job exit was zero at 14:41:29 UTC; guest directory removal and inactive unit were verified, then temporary access removal at **2026-10-04 14:41:43 UTC**, before the original deadline. Existing shared VM lifetime/settings were preserved, no new resources created, and the allocation finished. Actual billed cost remains unobserved. The inherited source-packet label correction noted above also applies to this controller receipt; staged archive/hash assertions identify the real inputs.

The original Jain 0.2903 failure remains valid for its original no-conflict-retry workload. The later pass supports **bounded cooperative retry behavior**, not backend starvation freedom, sustained soak, actual-authority scaling, installed agent harnesses or production readiness.

## Remaining gates and minimum next job

A subsequent admitted slice ran both existing disposable PStack mutations and the reference saturation/60-second profiles, at the same previously tested source pins. Private combined evidence SHA256: `c97202d5ae555a62d25ea09260c5fc90c46284889e7eea33c0d308694b9d5fcc`. Raw reports and snapshots were inspected. Skip-store-gate produced the specific **worker-started-with-invalid-store** counterexample; skip-publication-checkpoint produced the specific **forbidden-verdict-recorded after session revocation** counterexample. Both mutation reports had zero active claims; their successful test classification means safeguards were demonstrably necessary, not that mutated behavior was safe.

Saturation (eight workers, 50 task attempts each, pending ceiling 50, 30-second maximum) lasted **1.091s**, measured **407.841 operations/s, p99 0.243s, Jain 0.3068**, and reported **one failed protected effect**, eight writes from nine grants and 392 backpressure refusals. It is **not accepted saturation qualification** despite the raw supervisor pass label for its narrower implemented checks. Fairness gates were previously declared for independent/contention, not saturation; this new failure is the protected operation, not a retroactively invented fairness threshold.

Counts reconcile from the raw outcomes and retained snapshot: 400 intent calls (15 accepted/385 backpressured), 27 claim calls (nine accepted/12 conflicts/six backpressured), nine protected writes (eight accepted/one backpressured), and nine accepted releases = 445 operations, 41 accepted/12 conflicts/392 backpressure. Attribution of the single failed write to backpressure is a **source-and-count inference**: no other refusal category occurred, and scope-conflict arises only in claim. The backend checks pending capacity before protected-write as well as new workload. Thus an already granted task can have its write refused when projection capacity fills; this is capacity policy, not an observed unauthorized write or stale-fence violation. Zero oracle safety/live-claim violations do not imply every admitted operation completed.

The defect in qualification reporting was that `protected_effect_failures` was counted but omitted from `invariants.violations`, allowing zero exit. A narrowly reviewed reporting change now emits **protected-effect-failure**, causing the existing load command to fail qualification. A new deterministic regression obtains a real protected-write backpressure refusal, verifies zero effects and successful release/no active claims, then asserts the failed qualification count. This source change is **unexecuted pending affected Linux acceptance**. No backend capacity exemption, queue reservation, authority/PStack behavior or threshold change is made. Capacity reservations or a formally different completion policy would require separate reviewed design; do not silently grant writes past the ceiling to make a graph green.

The short-soak profile lasted **60.164s**, measured **136.811 operations/s, p99 0.375s, Jain 0.8534**, with 1,399 actual task attempts, 1,029 writes and **zero protected-effect failures**. All eight workers returned and both profile snapshot oracles reported zero safety/live-claim violations. This is a short reference exercise, not sustained actual-authority qualification. Aggregate cgroup peak was 417,800,192 bytes (398.4MiB), CPU 33.514s; ten throttled periods / 6.536s throttled time were recorded under the two-CPU quota. Cleanup verified files/unit removed and temporary access removed at **2026-10-04 15:12:40 UTC**, with the shared VM preserved. Actual billed cost remains unknown.

The mutants and short reference profiles now have retained evidence; saturation remains failed/incomplete. The immediate affected slice is the **single new reporting regression** and, only within parent-admitted remaining time, a saturation run proving that a protected-effect failure cannot be labelled qualification success. A safe zero-effect-failure rerun cannot erase the historical failure or establish reserved completion capacity. Do not rerun unchanged PStack tests/mutants or prior reference suites solely to extend evidence. Existing owned runtime/access were cleaned; parent admission and actual remaining budget decide any retry, with no automatic window extension. Full owner suites and operational qualification remain separate.

Retain specific forbidden observations for mutations, actual operations/duration/latency/fairness/backpressure for profiles, and all failed/partial results. Profile time limits are ceilings, not proof of sustained soak. Full authority-owner suites still need their own exact reviewed validator and feasible time allocation; source compile and endpoint tests do not replace them.

Controlled-pilot gates in [readiness](readiness.md) remain unmet: **saturation completion/qualification**, exact owner suites and operator failure/recovery rehearsal. Original fairness and saturation failures remain retained alongside bounded passes. Production additionally needs actual-authority sustained load, deployed transport/principal/revocation evidence, backup/restore/RPO/RTO/availability operations, installed-harness acceptance, license decision and any required fence-consuming external gateway. No live Git/CI/merge/deploy effect or atomic external fencing was tested.
