---
name: osb-factory
description: Prepare or reconcile an optional OSB factory backlog and durable workflow intents through an existing authority and one configured dispatcher.
---

# OSB factory workflow

Use the repository's deterministic `python3 -m workflow.cli` rather than rebuilding
admission, envelope or reconciliation snippets in each turn. This source preview
is UNRUN; execute only on the separately admitted GCP executor until qualified.
Do not install it or launch a controller from this skill.

Read [workflow contract](../../workflow/README.md) for config and commands. Keep one
authoritative backlog, one authority profile and one dispatcher per run. Admission
output is advisory: the existing authority must atomically revalidate and claim
before the dispatcher starts work. Firstmate owns its resolver, spawn, control and
journaled relaunch; PStack owns workflow/evidence; Breakfree provides only routing
allowed in the current session mode. Direct harness runs select one operator-owned
Claude Code, Codex, OMP or OpenCode bridge, with no simultaneous Firstmate controller.

Use `admit` for bounded ready candidates, `envelope` then `prepare` for immutable
intents, `decide` for the next scoped recommendation, and `pending` to find unresolved
outcomes. Read [transport contract](../../workflow/transport-contract.md) only when
configuring notifications. Queue messages and GitHub projections never grant work.
For pause or transfer, read [delta handoff](../../workflow/handoff-contract.md) and
use `checkpoint`, `handoff-accept`, `handoff-resume`. An offer or document acknowledgment
does not transfer ownership; existing authority acceptance and controller quiescence
must be verified before resuming.

On uncertain outcomes, preserve the journal and consult the current authority by
original key plus the existing dispatcher/native effect journal. A saved started
intent refuses automatic replay. Changed heads invalidate old green evidence.
Retain ownership through review, fixes, tests and authorized landing; completion is
not merge/deploy permission. Report source review separately from runtime results.
