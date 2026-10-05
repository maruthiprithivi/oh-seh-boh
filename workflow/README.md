# Optional factory workflow source preview

This package layers deterministic policy and durable effect intents over OSB.
The OSB authority core, reference lab and frozen PStack runner/fixtures are unchanged.
It is not yet a qualified continuously running system: all new sources are UNRUN,
and actual owner bridges remain to be mapped and qualified on GCP.

One continuously updated backlog lives in the selected authority. The CLI consumes
an exact snapshot, never promotes a local journal or GitHub projection into a second
backlog. One integration owner retains each task through ready, claim, work, review,
fix, verification, landing, release and backlog update. A failed or uncertain stage
is retained for that owner; a finished Breakfree job is not task completion proof.

## Existing ownership boundaries

Firstmate `f470a01c098c1536d83b802874bd954a2c04b506` already has
`fm-dispatch-resolve.sh`, validated `fm-spawn.sh` and journaled `fm-control.sh`
stop-before-relaunch. The resolver's recommended profile does not replace operator
approval, quota or spawn validation. Reuse those paths through a reviewed owner
bridge; do not implement another spawn/relaunch loop here. Source inspection did
not invoke those scripts or qualify the installed version.

Breakfree `00d7c6801dab6b35e5e3047e0e9e29de242a5fd5` restricts operations
in Firstmate mode. Primary sessions configure/observe model routing; crewmates use
only their allowed operations. Running jobs remain memory-resident and only finished
jobs persist. Do not use that registry as an authoritative live ownership ledger.
PStack retains its native workflow/evidence format and explicit local-store writer.

A run chooses exactly one dispatcher: `firstmate`, `claude-code`, `codex`, `omp`,
or `opencode`. Direct harness bridges are operator-owned and must qualify identity,
version, lifecycle, quiescence and revision handling. No direct bridge is shipped
or silently chosen as fallback when Firstmate/authority is unavailable. This package
does not edit those products or install provider configuration.

## Authority profiles

`transactional` uses the existing authenticated authority for atomic ownership,
revision/resource admission, leases and event/outbox commits. GitHub is a projection.
`github-cas-cooperative` uses the approved ledger branch CAS mapping described in
[the OSB contract](../skills/osb/references/github-cas.md); time/reassignment and
external effect boundaries remain cooperative. No live CAS client is shipped here.
Config cannot switch a journal between profiles, epochs or dispatchers. Migration
requires an explicit owner cutover after frozen admission, active-claim inventory
and reconciliation. Never automatically promote a mirror during an outage.
The local journal pins only its own configuration. The existing authority must
also enforce the run ID to dispatcher binding across multiple journal paths;
local file creation alone cannot ensure a globally single dispatcher.

## Deterministic CLI

Run from the repository root on admitted GCP only. Inputs are JSON data, not shell
commands. The CLI refuses duplicate keys, nonfinite values and inputs over 64 KiB.
It has no subprocess, network, dynamic plugin imports or runtime installation.

Operator-owned config has exactly these fields:

```json
{"project":"demo","repo_id":"42","principal":"operator",
 "acl":{"operator":["demo"]},
 "authority":{"profile":"transactional","id":"approved-authority","epoch":1},
 "run":{"id":"run-1","dispatcher":"firstmate"}}
```

The immutable task binding has `id`, positive integer `revision`, exact lower-case
40/64-hex `base` and `head`. Principal/ACL config is a local scope guard; real
authentication and membership must be checked by the existing authority route.
Digests are integrity checks, not authentication. Do not place credentials in inputs.

```sh
python3 -m workflow.cli --config config.json admit --snapshot snapshot.json
python3 -m workflow.cli --config config.json decide --task task.json --state state.json
python3 -m workflow.cli --config config.json envelope --task task.json --operation claim --payload claim.json
python3 -m workflow.cli --config config.json init-journal --journal /private/run.sqlite3
python3 -m workflow.cli --config config.json prepare --journal /private/run.sqlite3 --envelope intent.json
python3 -m workflow.cli --config config.json pending --journal /private/run.sqlite3
python3 -m workflow.cli --config config.json poll --journal /private/run.sqlite3
```

Snapshot keys are exactly `backlog`, `capacity`, `active`, `landing`. Each backlog
task has `project`, numeric-string `repo_id`, `id`, positive `revision`, exact `base`
and `head`, integer `priority`, `state` (`ready`, `running`, `completed`, `blocked`),
`ready`, `dependencies`, and `costs`. `ready` has nonempty `scope`, `acceptance`,
`verification` lists and named `integration_owner`. Dependencies bind `task` plus
exact completed `revision`. Costs and capacity contain nonnegative integer `cpu`,
`memory_mb`, `ci_slots`. Active tasks use the same schema with running state.
`landing` contains integer `limit` and `pending`, including already reserved work.
Each candidate reserves one additional landing slot in the advisory calculation.

Admission accumulates costs, excludes ancestor-path resource conflicts, cycles,
changed dependency revisions, malformed snapshots and mixed repositories. Priority
then ID orders selection deterministically. It never claims work. The actual owner
bridge must atomically recheck the snapshot revision, dependencies, costs, resources
and landing reservation while claiming. Cross-authority resource reservations cannot
be made atomic by this local helper and must be refused or separately serialized.

`decide` accepts a reviewed authority snapshot, current claim capsule and evidence.
Unknown state/ownership/epoch/base/head sends the owner to reconciliation. Review
requires current-head approval and a verified review role; display approval alone
does not establish maintainer approval. Every required check needs one current
base/head/revision pass; duplicate/conflicting evidence, missing drift acknowledgment,
manifest parity or fixture-readiness evidence cannot become green through prose.
Landing remains an explicitly authorized owner operation.

## Durable intents and bridge mapping

`journal.install` initializes only an explicitly created private journal. It pins
the entire operator config. `prepare` commits immutable intent bytes and a pending
notification together. Same key/same bytes replays its status; changed bytes conflict.
Key binds project, repo, authority, run, principal, task revision and operation.
Changed task work needs a new authoritative revision rather than an escape key.

`bridge.apply_prepared` is called by the existing dispatcher/integration owner,
not a new always-running controller. Its injected owner bridge must expose the
pinned dispatcher/profile, live `authorize_current`, and an effect-specific `apply`
mapping. A live read alone is not a fence: `apply` must use existing atomic authority
claim/admission and protected effect preconditions. No generic bridge becomes
qualified merely by returning True or implementing these names.

The helper commits `started` before the one owner call. Crash/lost response means
uncertainty, never automatic dispatch repeat. An unknown result is retained and
cannot be overwritten by an arbitrary later receipt. `record-observation` records
evidence only; it does not establish current permission. Recovery reads the original
authority key, Firstmate/other dispatcher journal and native effect state, proves
quiescence where needed, then uses that owner's reviewed reconciliation path.
No lease expiry is proof the prior worker stopped. Strong external fencing still
requires a consumer that validates ownership atomically with its protected write.

`notifications.py` supplies broker-free polling plus optional injected lightweight
and Cloudflare transport seams. Local workflow intents/outbox are one transaction;
a remote authority needs its own owner-side transactional outbox, not a local mirror.
See [transport contract](transport-contract.md). No service or transport is deployed.

## Qualification and next milestones

See [GCP source packet](../docs/factory-gcp-validation.md). New policy, journal,
bridge fixtures, transport helpers and skill are UNRUN. Native PStack source cases
are distinct from mocked bridge/unit tests. All build/import/test/lint/hook/render
execution stays on separately admitted existing GCP capacity, with provisioner
ownership separate. No paid compute, provider calls, new security grants, merge
or deployment is authorized by these sources.

Continue in bounded milestones: run deterministic source tests; fix demonstrated
failures; qualify owner mappings and the two missing native cases; qualify actual
notification routes and crash/recovery; then evaluate a bounded iterative backlog
run with existing dispatchers and operator-authorized landing. Preserve each result,
source pin and unrun gate. No token, latency, cost or energy reduction is claimed.
