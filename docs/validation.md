# Validation status and reproducible plan

Status at source publication: **unexecuted**. Independent source reviews refined repeated restore replay, operation-key scoping, lifecycle and permissions wording. Those reviews are not runtime tests. No passing metrics or capacity numbers are supplied.

The skill is OSB; the standalone reference test protocol is `osb.lab.v1`. The logical `osb/1` envelopes are adapter-review vocabulary. Neither claims compatibility with an installed harness or another service's wire API. Runtime validation belongs in a separately approved disposable Linux allocation; no provider/harness spend or live enrollment follows from these instructions.

Run from the repository root with Python 3 SQLite support. Do not execute on a shared live authority:

```sh
python3 -m py_compile lab/backend.py lab/client.py lab/scenarios.py lab/load.py lab/projection.py skills/osb/scripts/prepare_cooperative.py skills/osb/tests/acceptance_test.py
python3 lab/scenarios.py
python3 lab/load.py --test-only --profile independent --agents 8 --operations-per-agent 30 --seconds 30 --output evidence/independent.json
python3 lab/load.py --test-only --profile contention --agents 16 --operations-per-agent 50 --seconds 60 --output evidence/contention.json
python3 lab/load.py --test-only --profile saturation --agents 8 --operations-per-agent 50 --max-pending 50 --seconds 30 --output evidence/saturation.json
python3 lab/load.py --test-only --profile soak --agents 16 --operations-per-agent 1000 --max-pending 100000 --seconds 60 --output evidence/short-soak.json
```

Verify offline preparation in a fresh private fixture directory: run `skills/osb/scripts/prepare_cooperative.py` with `config/setup-input.example.json`, inspect all three output drafts, rerun same target and require refusal/no changes, inject non-object JSON, malformed OID, invalid TTL and oversized input, and require refusal/no completed output. Never publish the fictional example IDs.

Report command exit codes, failure messages, source commit, machine/Python/SQLite versions, actual operation count/duration, throughput, latency percentiles, retries/fairness, resources, lost acknowledgments, double ownership, unauthorized mock writes and omitted scenarios. A killed worker or unsupported capability is not a pass. Source-shape assertions are not actual authority proof; use the [integration plan](integration.md) separately.

Short allocation estimate: 10–15 minutes for this source/helper/scenario/profile slice on an existing 2-vCPU/8-GiB Linux instance, excluding provisioning and another authority's owner suites. Unmeasured estimate; no price quote or approved cap. A one-hour combined allocation can at best establish short-profile evidence; thorough multi-hour soak, large-fleet stress, real harness interoperability and live transport security need separate evidence and authorization.

Refinement loop: keep failed evidence, locate the invariant/measurement gap, make the narrow source correction, rerun affected scenarios plus relevant profiles on the approved executor, and compare only like-for-like baselines. Do not silently relax an invariant or call failed/partial runs successful to improve a graph.
