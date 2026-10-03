# Transactional authority adapter requirements

Reuse an existing deployed ledger where its documented capabilities satisfy these semantics. The request/receipt vocabulary here is a logical mapping contract, not a claim that any endpoint or CLI exists. Configure and review a concrete mapping before invoking anything. No server, transport client, SSH installation, database migration or credentials ship in this package.

Required capabilities:

- Authenticated principal-to-team/repository authorization; clients cannot choose arbitrary actor IDs. Explicit primary owner/delegate registry and authorized revocation.
- Durable transaction for task/claim generation, current holder, lease expiry, conflict key, handover acceptance and event record. Concurrent same-scope grants have at most one winner. Generation increments across claim, transfer and reassignment; never reused after restore.
- Authority clock, epoch and monotonic state version. Reject expired/revoked grants and stale expected generation/version. Revocation must affect protected consumers; caches alone are insufficient.
- Idempotency record scoped to principal, repo, team and key; canonical payload digest; same key/payload returns the original outcome, changed payload conflicts. Persist successful outcome and event in the same transaction; retain keys beyond retry/lease lifetime.
- Read task, read active conflicts, read by operation key, read receipt and paginated event history. Return explicit conflict/unauthorized/stale/expired/revoked/unknown states; never interpret HTTP success alone as a granted lease.
- Outbox for GitHub projection committed with the authority event. Replayed projection uses event ID/state version, marks pending/failed projection, and cannot roll authority backward. GitHub downtime does not undo committed grants.
- Backup and recovery procedure that prevents reusing old fence tokens. Restore must bump epoch, revoke old grants, and preserve idempotency history or freeze uncertain keys for owner reconciliation.

Map the deployed contract in `.coordination/capability-mapping.md`: version; actual operation names and input/output fields; identity source; error behavior; idempotency retention; overlap model; server clock; generation/epoch recovery; revocation and fencing consumers; projection repair; limitations. Do not expose credential paths that contain secrets. Inspect the selected service's released contract and record mismatches; never assume a particular topology is required by this skill.

Enforcement boundary must be truthful: a transactional service prevents conflicting **ledger grants**. To prevent stale owners from mutating a protected resource, that consumer must validate epoch/generation and current authorization atomically with its write, or receive writes through an approved broker. GitHub push/merge credentials do not automatically implement custom fencing. Without a broker/gate, this design coordinates agents and relies on repository protections plus human integration review for code integration.

Operational recommendation: existing durable service first; otherwise a separately scoped small authenticated API plus transactional database and outbox worker. A managed SQL service is one option; a single-host SQLite service can serialize transactions but needs a durable disk, backups, and a single authoritative writer (no copied database per client). Multi-instance service requires shared transactional storage. Choose availability, retention, and price after destination/workload decisions. Do not deploy from this skill without that separate authorization.
