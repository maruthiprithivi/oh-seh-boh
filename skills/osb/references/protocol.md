# Lifecycle

## Join and resume

Resolve repository ID from the authenticated GitHub API, not just `git remote`; compare it to approved config. Read the current authority epoch, actor/team permissions, task state, dependencies, scope conflicts and receipts. Authenticate each person independently. A new harness session gets a new session ID; it cannot inherit a previous session's lease by copying its receipt. Recovery must be authorized by the authority or human owner, preserving audit history.

Resolve base and head to full commit object IDs, with object format recorded. Track target branch as intent only. Task scope is a structured conflict key (repository-wide integration or explicit path/resource set). No overlap inference based only on task titles. If the existing authority supports task-exclusive claims but no path overlap prevention, say so and use the integration owner to serialize overlapping tasks.

## State transitions

| Operation | Preconditions and result |
|---|---|
| Create intent | Stable task ID, desired outcome, explicit scope, dependencies, next-step owner; creates `open`, no claim. |
| Claim | `open`/released task, dependencies satisfied, authorized actor, no conflicting live grant. Successful claim produces `claimed`, monotonic generation, expiry and receipt. Request alone is not a grant. |
| Heartbeat | Match actor/session, authority epoch and generation; lease still live and not revoked. Service extends using authority time; advisory modes require owner acknowledgment under their policy. Retain generation; cannot resurrect expired ownership. |
| Offer handoff | Current grant; persist work status, base/head, artifacts and next action. `handoff_pending` retains current holder until acceptance or release/expiry. |
| Accept handoff | Named recipient authenticates; expected generation matches and current grant live. Atomic transfer or human acknowledgment creates new generation and session. Old holder stops; offer alone never grants recipient rights. |
| Release | Service validates matching live holder and returns task to `open`. Cooperative release requires owner acknowledgment; CAS follows its reviewed validator policy. Retain generation history. |
| Complete | Matching live grant, evidence bound to current head. Service performs configured atomic transition to `ready_for_review` with release. Cooperative completion is a request until human release acknowledgment; CAS follows its reviewed validator policy. Explicit integration owner reviews. Tests skipped/blocked must be stated. |
| Revoke | Authorized primary owner/admin, reason and expected generation. Invalidates grant immediately in service mode; cooperative owner records revocation and contacts workers. |
| Expire | Authority time reaches expiry; mutations rejected. Reassignment requires new generation. Cooperative expiry is advisory and owner reconciles before new grant. |
| Reconcile | Read authority directly and compare projections/receipts. Repair visibility only within existing permissions. Authority inconsistency freezes affected scope and escalates. |

Before each shared write or delivery, check current grant and base/head; commit movement requires refreshed evidence and any configured authorization. In service mode pass fencing fields to the protected consumer as part of its transaction. A check followed by an unguarded write has a time-of-check race. If the consumer cannot enforce fencing, disclose that enforcement covers ledger transitions only; human integration review still controls merge/deploy.

Use the same idempotency key and exact payload for retries, including timeout after commit. Read by key before retrying; a changed payload requires a new intentional operation, never a retry. A conflict, revoked lease, stale generation, changed epoch, unauthorized actor, or incompatible contract is not retriable. Rate limits/transport failures permit at most two retries respecting server delay; then stop and report uncertain state. Do not expose credentials in diagnostics.

## Reconciliation and handover evidence

Collect task/scope, actor/session, authority epoch/generation, expiry, operation key, server receipt/version, base/head/object format, worktree/branch locator, PR/artifact links, verification evidence, unresolved risks, and precise next step. Local absolute paths are optional machine locators, never portable authority IDs. Include no secrets. Completion requires review evidence, not a fabricated test pass.

When GitHub is stale but service is reachable, trust service, mark projection pending, and repair by event ID/version later. When service is unreachable, do not fall back to a GitHub claim. When comments disagree in cooperative mode, stop overlapping shared writes and ask the configured owner to resolve; no election, majority vote, last-comment-wins, or first-assignee-wins rule.
