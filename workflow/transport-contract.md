# Optional workflow notifications

This source helper is an optional workflow package, not a second controller or
authority. It has no authority-core writes, spawn/control APIs, dispatcher,
GitHub grants, network code, provisioning, credential loading, or executable
installation. Firstmate retains spawn/control and journaled relaunch; PStack
retains workflow/evidence; Breakfree retains allowed model routing. An authority
owner must map this helper to its existing transaction and authenticated reads
before integration. Source review does not establish runtime compatibility.

## Transaction boundary

`install_schema(connection)` is an explicit owner migration. Other helpers never
install a schema. It uses individual SQLite `execute` statements and never
commits an existing transaction. `append_notification(connection, envelope, acl)`
requires an active caller-owned transaction. The owner must append in the same
SQLite database and transaction as its authoritative or workflow journal change,
then commit or roll back both together. A caller merely opening a transaction
does not prove that it has made the correct authority transition; the hook mapping
and owner tests must establish that relationship. A remote authority requires
its own transactional outbox; this helper cannot make remote calls atomic.

Append, acquisition, acknowledgment and rejection never commit or roll back.
The owner uses short write transactions, normally `BEGIN IMMEDIATE`, commits
acquisition, then sends outside the transaction. Busy and stale snapshot errors
propagate to the owner's bounded retry policy. Never treat an exception as an
allocated attempt or publish before committing the append. No helper writes
authority task state.

## Envelope and ACL

`make_envelope` returns exactly `osb.factory.notification.v1` with `scope`,
`project`, `repository_id`, `authority_epoch`, `task`, nonnegative integer
`revision`, `event_id`, object `payload`, and SHA-256 `payload_digest`. IDs are
nonempty strings capped at 512 characters; the canonical UTF-8 encoded envelope
is capped at 64 KiB. Canonical JSON sorts keys, uses compact separators, escapes
non-ASCII characters, and refuses nonfinite numbers. A full canonical envelope
digest is retained in the outbox as well as the payload digest. Digests detect
content mismatch; they are not signatures or authentication.

The trusted operator supplies `ProjectACL({project: (scope, repository_id,
authority_epoch)})`. Never derive it from a message or GitHub projection.
Every ingress/send/ack/reconciliation checks the exact current route. Queue
access control and authenticated authority reads still belong to the existing
operator implementation. Revision is an advisory invalidation hint, never a
grant, claim, ownership transfer or instruction to overwrite authority.

An event ID must be unique within a project across epochs. Identical retries
return `False`; reusing that identity with changed content is refused. Owner
event IDs should be derived deterministically from the owner journal identity
and transition so an uncertain append response is safely retried. No random ID
is generated inside these helpers.

## Delivery and transport seams

Broker-free `poll_pending(connection, acl, now=..., limit=...)` reads eligible
notifications without mutating delivery or allocating claims. Callers reconcile
against current authority. For bounded delivery, `acquire_pending` allocates
`Delivery(envelope, event_digest, attempt)` and sets a retry visibility deadline.
`acknowledge` compares project/event ID, full event digest and attempt, including
idempotent acknowledgment of that same delivered attempt. A lost acknowledgment
can cause repeated notification; a delayed acknowledgment cannot close a later
attempt. The helper accepts acknowledgments from a trusted owner caller, not a
public queue message endpoint.

`LightweightQueue(operator_send)` and `CloudflareQueues(operator_send)` are
optional injected send seams. They snapshot and validate the versioned envelope
and pass it to an already admitted operator callable. They do not instantiate a
server, SDK, provider client, queue, URL, security grant or paid resource.
Lightweight self-host hosting and Cloudflare bindings, existing queue destination,
credentials and authentication are operator-owned. Neither adapter acknowledges
automatically. A trusted publisher may mark transport acceptance delivered while
consumers still periodically reconcile authority; transport acceptance is not
proof that a consumer performed any work. A consumer acknowledgment design must
preserve the publisher's attempt/digest correlation outside the notification
envelope and requires its own authenticated owner mapping.

Queue contents are notifications only. Missing, duplicate, delayed, reordered or
forged queue messages cannot change authoritative ownership. `reconcile` passes
only scope/project/repository/epoch/task to the supplied authority reader, which
reads the latest state. It does not pass the notification revision or payload as
state to apply. Owner readers must refuse unavailable/unverified routes and
retain uncertain-effect receipts before retrying actions. Consumers must also
perform periodic authority reconciliation independent of notifications, since a
queue can lose a message after transport acceptance. Epoch rotation refuses old
messages and retains their stored rows; an owner migration/reconciliation policy
must handle them explicitly.

## Retry and dead letters

`reject_delivery` CASes only the current allocated attempt. Attempts are bounded
by the trusted publisher's configured budget (1–1000; default 5), with a positive
retry/visibility duration of at most one day. Exhausted failures or expired last
attempts move to `dead`. Rows and envelope contents remain stored. Dead letters
never delete or mutate authoritative tasks and do not implicitly requeue or
escalate authority. The owner reads current authority and retained delivery
evidence before any explicit replay policy. Error text must be operator-sanitized
and is capped at 512 characters. Changing the configured attempt budget midway
is an operator policy change, not a message-controlled retry request.

`poll_pending` deliberately returns event-ID order rather than revision order;
consumers cannot depend on FIFO. It filters exact project routes before limiting
eligible results. Poll limits are 1–1000. Acquisition can return fewer than the
limit while moving exhausted rows to dead letters. Time is supplied by the owner
as a finite nonnegative clock; publishers must use a consistent clock policy.

## Validation provenance and exact GCP needs

**UNRUN.** Adversarial unittest source was written before the implementation.
No Python imports, tests, builds, lint, hooks or rendering were performed on Mac
or Optimus. Source inspection alone is not runtime PASS. Run only on the separately
admitted existing GCP Linux route, with Python 3 and SQLite, from the exported
`osb-factory` root, recording the source revision, exit status and complete output:

```sh
python3 -m unittest discover -s workflow/tests -p test_notifications.py -v
```

The source cases cover transaction rollback with the authority-side write,
autocommit misuse, duplicate and conflicting identities, project/repository/scope
and epoch ACLs, payload/field tampering, lost and stale acknowledgment, wrong
digest, exhaustion including publisher crash, out-of-order reconciliation,
transport-only behavior and exception, revision/attempt validation, absent schema,
and two-connection SQLite write contention. These tests use disposable temporary
databases and injected transports; they contact no provider.

Before a real authority integration is qualified, the owner also needs a test
showing its actual transition and this append commit/rollback atomically, its
authenticated unavailable-route refusal and retained uncertain-effect recovery,
crash after owner commit before publication, an injected queue loss followed by
periodic authority reconciliation, ACL/epoch rotation, and its configured busy
retry policy. Actual lightweight self-host and Cloudflare delivery contract tests
require existing preapproved transports and separately retained receipts. No
provisioning, new paid compute, merge or deployment is authorized by this packet.
