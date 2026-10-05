# Factory source milestone and GCP qualification packet

Status: **UNRUN**. This packet describes source and future execution, not runtime
PASS. Mac/Optimus were used only for source reads/writes and Git source management;
no imports, tests, builds, lint, hooks or rendering ran there. Existing OSB
`f40a652` reporting regression remains UNRUN; previous bounded evidence remains
at its historical exact pins. No merge, deployment or installation occurred.

## Bounded milestones

1. Authored adversarial policy/envelope/notification tests before their associated
   source implementations. Added deterministic admission, versioned identity and
   revision envelopes, transactional intent/outbox journaling and broker-free polls.
2. Added one-shot injected owner bridge with commit-before-effect and uncertainty
   retention. Added optional self-host lightweight/Cloudflare send seams. Those
   seams are source interfaces, not deployed queues or authenticated route evidence.
3. Corrected narrow PStack provenance and authored two additional native cases
   without modifying frozen runner/helpers. Broader factory qualification does not
   automatically become a plugin merge blocker.
4. Added bounded delta handoff policy/CLI sources inspired by read-only BatonPass
   inspection: pause versus offer, receiver preflight, approved offer identity,
   predecessor quiescence, atomic acceptance intent and live successor checks.
   The inspected production adapter does not support generic acceptance; the bridge
   explicitly refuses absent capabilities. Logical fixture acceptance is not an
   available production transition. This completes the source freeze before GCP.

The base checkout was clean on `source/factory-contract-and-outbox`, derived from
`f40a652d77c66831c3423ac6f10cacfb5a9ad647`. The prior branch and `task-2`
snapshot are preserved. No duplicate controller, new authority schema/migration,
Firstmate/Breakfree/PStack product change or OMP checkout edit was made.

## First admitted GCP stage

Separate provisioner/parent admits an **existing** GCP Linux allocation and exact
source commit. No allocation, provider calls, security grants or budget increase is
requested by executable source. Python >=3.10 plus its SQLite library suffices for
all synthetic workflow tests. No dependency installation is required. Set a
120-second external timeout for the whole synthetic stage, with 30 seconds reserved
for containment/evidence cleanup. This is a proposed bound, not measured duration.

From the exact clean source root, capture full output and exit status:

```sh
python3 -m unittest discover -s workflow/tests -p 'test_*.py' -v
```

This imports test sources on GCP and uses disposable local SQLite/owner fixtures;
it does not contact a live authority, harness, queue or provider. Include the native
plan rejection tests, which validate plans only and do not launch the native job.
Missing prerequisites, setup errors, skipped cases and external timeout are explicit
notexecuted/setupfailed outcomes, never PASS. Source review cannot substitute.

Test categories: exact dependency revisions and cycles; cumulative capacity/path
overlap/landing pressure; malformed neighbor snapshot; project/repo/epoch/dispatcher
binding; stale base/head and old green evidence; verified reviewer role; required
drift/readiness evidence; caller transaction rollback; idempotency conflicts;
lost/stale acknowledgments; bounded delivery/dead letters; changed authority epoch;
commit-before-owner-call and no repeat; duplicate JSON and private journal guards.

Separately execute the pre-existing reporting regression at its exact `f40a652` pin
under the retained [baseline instructions](linux-baseline.md). Do not rerun unchanged
functional suites simply to accumulate results. That regression tests failure
classification, not saturation capacity.

## Native PStack stage

Retained evidence supports **five endpoint methods, ten mock lifecycle methods,
four native installed cases and two detected mutant counterexamples**. Native
unavailable-route refusal and uncertain-effect recovery were absent. See
[provenance reconciliation](pstack-provenance-reconciliation.md) and the optional
`workflow/native_pstack_cases.py` source. Both new cases remain UNRUN.

The parent provides exact clean packet/PStack/compatible owner source, preprovisioned
Bun/Commander/SQLite/bash/git, established Linux machine identity, 1–2 admitted CPU
IDs and an existing exclusive supervisor-owned nondelegated leaf cgroup. Use an
external 180-second wall cap including a 30-second cleanup reserve; actual duration
is unmeasured. Native script validates all exact pins before and after and installs
nothing. A config flag does not establish GCP authorization.

The native plan contract is `osb.native-pstack-cases.v1`. Required fields are
`admitted_existing_gcp: true`, `admission_reference`, `max_wall_seconds` (60–180),
`admitted_cpus`, `exclusive_existing_cgroup`, absolute `packet`, `pstack`, `owner`,
`bun`, `evidence`, exact `packet_commit`, `pstack_commit`, `owner_commit`,
`bun_sha256`, and `cases: ["unavailable-route", "uncertain-effect-recovery"]`.
Use private evidence outside all source trees. Owner source bindings stay in the
private admitted plan; no private deployment route/credential is published.

```sh
python3 -m workflow.native_pstack_cases --plan /private/admitted-native-plan.json
```

For unavailable-route refusal, the native store still initializes and parses; the
authority endpoint is deliberately absent under a fresh bound journal. Require no
worker/verdict/claim changes and explicit unavailable-route refusal. For uncertain
effect, a test-only relay executes the actual native record once, withholds its
successful acknowledgment, preserves state/store/process receipts and verifies
same-attempt replay refusal with zero additional native record. Actual native check
and independent store/authority observation must agree. Test relay results do not
qualify real transport authentication or an external atomic effect fence.

## Owner integration and transport stages

After synthetic/native qualification, map an existing authenticated authority and
dispatcher without adding a controller. Show its actual authority transition and
outbox append share one transaction; simultaneous admissions have at most one
conflicting grant; dependency/revision/resource/landing reservations cannot race;
queue duplicates/loss/reorder trigger reads of current authority; outage freezes
effects; epoch rotation cannot promote a mirror. Qualify crash after commit before
send, dispatch outcome loss, stale checkpoint before publication, revocation,
restart/quiescence, and end-to-end ownership through authorized landing.

Actual lightweight and Cloudflare transport receipts require already admitted
routes. The injected seam alone is not wire/API compatibility. Keep destination
credentials/operator bindings outside source and fixtures. No network transport
test or queue/service provision follows from this packet.

## Workload and measurement provenance

Sanitized scenarios derive from read-only inspection of existing project CI and
the delegated issue/epic patterns: changed epic revision, stale base, old green
after a changed head, missing drift acknowledgment, mismatched manifest and
unavailable fixture despite a unique project name. Public fixtures use synthetic
identities/revisions/resources and contain no private incident records. Existing
integration trains already work; these sources do not imply they need replacement.
Historical selected-window failure samples are not a census or product-wide rate.

Before claiming efficiency, use the same scoped workload, exact source/harness/model
versions and comparable resource/route conditions for baseline and candidate.
Retain input/output/cache token counts, number of model calls, actual monotonic
stage/wall latency, admitted resource usage, retries, verification failures and
actual billed/provider cost where available. Report missing metrics as unknown.
Count source bytes/CLI calls separately from measured model tokens. Predeclare
acceptance gates before results, preserve failures and include reconciliation cost.
No token/latency/cost improvement or energy-saving guarantee is claimed now.
