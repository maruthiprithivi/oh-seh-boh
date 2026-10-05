# PStack PR497 retained evidence reconciliation

This is a source documentation update on 2026-10-05, not a new runtime run or a remote PR update. No tests, imports, builds, lint, hooks, dependency installation or rendering were performed on Mac/Optimus. No merge, deploy, provisioner or remote write was performed. The retained evidence was inspected before choosing remaining GCP cases.

## Exact sources and receipts

PStack PR497 evidence is pinned to `5168f575f1ae6269850cb6dcd895e9b538bfc276`. Successful affected retry used an owner-pinned, separately reviewed corrected authority candidate; reference OSB was `61744a0850a2a9d6b843e22980973e9c3d3be44f`. The original failed authority candidate is a different revision and retains five setup errors, not passes. Full owner pins and custodian locations remain in the private reconciliation record outside this repository. These are historical validation candidates; newer Firstmate revisions do not inherit their runtime results.

Runtime evidence archive SHA256: `b5e4335605166bb39a0b5459b029d1042e9cfd8cd30996790c2425c43acfc689`. It is retained privately by the custodian, not a public download. The relative archive members below identify evidence without publishing local paths or private owner history.

| Relative retained path | Evidence inspected |
| --- | --- |
| `original-run/evidence/endpoint-acceptance.stderr` | Five endpoint setup errors preserved |
| `final-retry/evidence/admitted-retry-manifest.json` | Failed/corrected authority identities, frozen source hashes, required stages |
| `final-retry/evidence/dependency-source-provenance.json` | PStack/OSB/authority pins, binary identities, Commander version |
| `final-retry/evidence/endpoint-acceptance.stderr` | Five methods, zero skips, OK |
| `final-retry/evidence/endpoint-lifecycle.stderr` | Ten mock lifecycle methods, zero skips, OK |
| `extracted/final-stage-results.json` | Endpoint 13.741s, lifecycle 71.416s, installed 11.219s; terminal 2026-10-04 14:12:47 UTC |
| `extracted/final-installed-report.json` | Exactly four installed native cases and independent ledger/claim observations |
| `saturation/evidence/mango-osb-next-readiness-20261004T151038Z/skip-store-gate/report.json` | Detected `worker-started-with-invalid-store`; zero active claims |
| `saturation/evidence/mango-osb-next-readiness-20261004T151038Z/skip-publication-checkpoint/report.json` | Detected `forbidden-verdict-recorded` after revocation; zero active claims |

Installed native cases are success, invalid-store, revocation and cancel. Success records one expected verdict and confirms release. Invalid store returns setupfailed with no worker/claim. Revocation returns behaviorfailure with no verdict and pending-or-stale release, while the independent authority observation is revoked with zero active claims. Cancellation returns cancelled with confirmed release and no verdict. All four have zero observation violations. The two mutants' `ok: true` means the expected unsafe counterexample was detected; it does not mean mutated behavior was safe.

## Byte identity of copied proposal sources

Read-only SHA256 comparison on 2026-10-05 found all seven copied proposal files below match the retained admitted-retry manifest. Paths are relative to `extensions/pstack-proposal/pstack/skills/osb-coordination/`. This supports reuse of historical evidence for those bytes, not certification of changed future files or environments.

| File | SHA256 |
| --- | --- |
| `scripts/osb.py` | `acd9a27f07cf30f56268b2079a87c2af81e7bfd1f298853d9bcef71e7849e18b` |
| `scripts/run_local_verifier.py` | `8d9e629c79cddf98a388580ee56a1bb3f7c46e0d77dc7c98b3b005a5537a1e4d` |
| `tests/acceptance.py` | `f80a9b15c73c8dbe1a373b9ebf36fdcb9174cdc617e661ddd9dcd8e5f7b110a6` |
| `tests/lifecycle.py` | `134e081b69adee93816327ac0557379dc793432f2d24abb7d41a4f3b5882d733` |
| `tests/acquisition_fault.py` | `eb8c39fecd693b0f488e8243b64332482638880fe48f8c85a4ef0fbbbd62fc72` |
| `tests/drop_reply.py` | `137a66560d433aa74e28efedef9c6594c25e1f6575bb008d4b0283d3fca4e542` |
| `tests/local_commands.py` | `ac3e487af21a1a6b4c99dd85d4135f095fa649ff6dae6c491afc1d0fe289cf41` |

## Remaining GCP-only evidence needs

1. Installed native unavailable-route refusal: exact clean pinned sources, preprovisioned Bun/Commander and initialized private disposable orch store; unusable configured authority route must refuse before verifier launch or verdict mutation. Capture command exit/stdout/stderr, state/journal, worker marker, native ledger inspection and independent claim inspection where reachable. Distinguish unavailable observation from proof of no remote claim. A mock route refusal does not satisfy this case.
2. Installed native uncertain-effect recovery: use a bounded test-only supervisor fault that loses an actual native record outcome, preserving the real store and runner state/journal. Capture ledger before/after, exact claim and process-quiescence evidence. Same-attempt retry must refuse relaunch/repeat recording; inspect and reconcile the uncertain native effect before any approved successor. The mock unknown-publication pass and the mutant's unknown effect label do not satisfy recovery evidence.
3. OSB reporting regression at `f40a652d77c66831c3423ac6f10cacfb5a9ad647` remains UNRUN; run its deterministic reporting regression on admitted GCP capacity separately. Preserve the original reference fairness failure and the mixed saturation result. This is broader OSB evidence, separate from narrow plugin acceptance.

The existing retained four-case native harness does not include cases 1 and 2. The optional `workflow/native_pstack_cases.py` now provides those two test-only cases through the unchanged runner, actual native orch and independent store/claim observations. It remains UNRUN and needs review before a bounded GCP run; do not relabel the current harness output or rerun unchanged suites without cause. The separate provisioner must admit existing resources; this packet grants no new paid compute, provider calls, security grants or budget extension. Fixture setup failures and unresolved effects remain explicit outcomes.

The uncertain-effect case wraps only native orch's command route: successful native recording is independently observed, while a test-only relay durably retains its receipt and returns exit 75 to the unchanged runner. This exercises a runner-unknown/native-confirmed effect and same-attempt replay refusal; it does not complete explicit operator reconciliation, simulate ambiguous durable storage or prove general crash recovery. The wrapper is never installed as a production route. The unavailable-authority case uses an initialized actual PStack store, an absent endpoint behind the fixed Python route and a new journal to prevent journal-binding refusal from masquerading as transport refusal. Native summary and independent read-only claim/ledger observations remain mandatory. The harmless fixed foreground verifier is synthetic; publisher and store are native.

After separate admission, the supervisor supplies a **private** `osb.native-pstack-cases.v1` plan with `admitted_existing_gcp: true`, nonempty `admission_reference`, `admitted_cpus` (one or two CPU IDs), `exclusive_existing_cgroup` (existing exclusive, supervisor-owned, nondelegated leaf), and `max_wall_seconds` from 60 to 180. Source bindings are absolute `packet`, `pstack`, `owner` paths with full `packet_commit`, `pstack_commit`, `owner_commit`; the runtime plan carries owner pins privately. It also requires absolute preinstalled `bun`, its `bun_sha256`, a unique `evidence` directory outside all sources, and `cases: ["unavailable-route", "uncertain-effect-recovery"]`. Packet, PStack and owner trees must be separately pinned and clean. The existing supervisor owns the external wall watchdog and emergency containment settlement. The module reuses the retained containment reader/settler and requires exact admitted affinity; it creates no cgroups, credentials, VM or dependencies.

GCP-only command text after source review and exact pin checks:

```sh
cd /approved/reviewed-packet
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest workflow.tests.test_native_pstack_plan
PYTHONDONTWRITEBYTECODE=1 python3 workflow/native_pstack_cases.py --plan /private/admitted-native-plan.json
```

The plan tests and both native cases remain **UNRUN**. Retain each case report, copied native store, run state, client journal, authority snapshot, native summary/check output and relay receipt, plus the outer supervisor's exit/stdout/stderr/time/containment receipts. A missing case, failed binding, unquiet descendant or exhausted cleanup reserve cannot produce a complete pass. This bounded extension does not rerun the four original native cases, two mutants or fifteen unchanged fixtures. New source review and GCP execution are required before changing either native case's status.

PR review facts in the delegated handoff remain draft head `5168f575`, four resolved threads and Bugbot pass; latest reviewer `isditalleswatjekan` is APPROVED with association `NONE`. These are handoff facts, not a fresh forge query here. They do not establish verified maintainer approval. Broader factory qualification is not automatically a plugin merge blocker, and none of these receipts authorizes merge/deploy.
