# Oh Seh Boh

OSB helps people and their coding agents coordinate work in a shared repository or project. It makes the current owner, task scope, integration owner and next handover visible, so a team can check the ledger before starting work or handing it to someone else.

The name comes from the user's reference to **Ho Seh Boh**, which the supplied reference describes as a Hokkien greeting meaning “How have you been?” This project uses the spelling **Oh Seh Boh**, shortened to **OSB**. That friendly check-in fits the problem: before touching shared work, find out how the other person's change is going.

Two developers can each be making good progress and still run into each other. One changes a shared module while another changes its callers. An agent starts from an old branch. Two teams trigger builds for nearly the same change. A handover happens in a chat that the next person never sees. OSB gives these conversations a durable place: what are you working on, who owns it now, what changed, and who should pick it up next?

The skill does not eliminate every code conflict. It helps teams notice overlapping work earlier and preserve ownership and handover context across tools. Merge, deployment, review and spending permissions remain with the people and systems that already control them.

## What is here

- `skills/osb`: portable `SKILL.md`, progressively loaded references, config/templates and an offline draft helper.
- `lab`: a small Python standard-library/SQLite reference backend, subprocess client, process-based scenarios, fault injection and load profiles.
- `docs`: architecture, testing boundaries, installation and validation instructions.

**Status: source preview, unexecuted.** No runtime tests, stress runs, real agent harnesses or deployed authentication have been validated. This README reports capability of the supplied sources, not passing results.

## Use the skill

Read [SKILL.md](skills/osb/SKILL.md) directly, or copy the full `skills/osb` folder into one approved skill root for your harness. See the [documented compatibility matrix](skills/osb/references/compatibility.md). Documentation support is separate from installed-version verification; `omp` and `agy` identities must be confirmed.

The usable minimal workflow is [cooperative GitHub setup](skills/osb/references/quickstart.md): verify repository/human identities, prepare a control issue and task/config drafts, publish them only within authorization, and let the named human integration owner acknowledge grants, handovers and releases. Issues provide visibility; comments and labels are not atomic locks.

For compliant low-contention automation, the skill describes a [GitHub ledger-branch CAS design](skills/osb/references/github-cas.md). No CAS client is shipped. For enforced ledger transitions, use a separately reviewed compatible transactional authority. Custom fencing must also be checked at protected consumers; a ledger grant cannot stop arbitrary direct Git/forge writes.

Example request:

> Use OSB to prepare a cooperative ledger for this repository. Alex is the human integration owner. Show the config and issue drafts before publishing. Keep this scope separate from our other projects.

## Test it

The [test project](lab/README.md) starts with two competing worker processes and grows through independent teams, scoped isolation, stale leases, revocation, handover, lost responses, crash/restore, mock projection and bounded burst/soak/saturation workloads. Worker labels such as Codex or Claude describe simulation profiles; they do not launch those products.

In an authorized disposable Linux environment with Python 3 and SQLite support:

```sh
python3 lab/scenarios.py
python3 lab/load.py --test-only --profile contention --agents 8 --operations-per-agent 30 --seconds 30 --output evidence/contention.json
```

Do not run these on a shared authority or against live GitHub. The lab uses synthetic identities, virtual lease time, a local mock projection and isolated databases. Its `osb.lab.v1` protocol is a reference model, not wire compatibility with another authority. [Real authority integration](docs/integration.md) requires that owner's tests, an approved fixed endpoint route and separate transport/security validation.

Load reports include workload size, throughput, p50/p95/p99 latency, claim wait, fairness, retries, CPU/RSS/storage and invariant failures. Capacity claims require actual evidence for the tested workload. A short burst or one-minute soak does not establish production capacity or long-running reliability.

## Dependencies and permissions

Reading the skill requires no executable dependency. The offline helper uses Python's standard library. Cooperative setup uses an existing GitHub browser/API or `gh` login. The reference lab is Linux-only and uses Python, SQLite and `flock`; no Redis, Kafka, Kubernetes, database server, LLM provider or cloud account is required by the source.

No automatic installation, membership grant, secret store, App/webhook setup, merge or deployment is part of this package. Public sources contain no supplied naming screenshot, private implementation history, credentials or user workspace receipts. No license has been selected; public visibility alone does not grant an open-source license.
