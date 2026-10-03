# Cooperative GitHub mode

This mode is an agreement among cooperative participants, not safe mutual exclusion against racing or malicious clients. Choose it only with that explicit understanding. The named human integration owner (or an explicitly delegated human) serializes grant decisions. Agents never elect a replacement.

Use one task issue per intent, and one control issue identifying team and owner. Optional Project fields/labels show `open`, `claim-requested`, `claimed`, `handoff_pending`, `ready_for_review`, and `blocked`. Assignees show responsibility; none of these prove a grant.

1. Read all pages of current task/control comments, verify IDs and authors using API identity, and check existing grants, revocations, overlaps, dependencies and base/head. Never accept the author claimed inside a comment body as authentication.
2. Submit a structured request with operation key, task, repository ID, team, session, conflict scope, expected generation and base/head. Capture the posted comment ID. If posting times out, search/read for that key and identical content before any retry; GitHub comment creation itself has no application idempotency guarantee. Duplicate requests do not create additional grants.
3. Wait for the configured human owner's explicit acknowledgment naming the request comment ID, holder identity/session, generation, advisory expiry and base/head. Owner increments generation and considers all pending requests before granting. Capture author ID and acknowledgment comment ID. Verify it has not been contradicted, revoked, or edited before proceeding. Owner must not grant overlapping live work simultaneously.
4. Heartbeat by reporting progress against the grant. Owner controls expiry extensions, reassignment, revocation and accepted transfers. Expiry pauses workers; it does not automatically make work available. Before reassignment owner reconciles prior work, records revocation/release, and notifies affected participants through an authorized channel.
5. Offer handoff with evidence; recipient requests acceptance; owner acknowledges a new generation. Completion posts evidence for human review and release acknowledgment. Closing an issue or merging a linked PR is not a lease operation.

Use append-only corrections by convention. Comments are editable/deletable, so retain redacted receipt copies and treat missing/changed grant evidence as a reconciliation trigger. This remains a cooperative audit trail rather than tamper-proof storage. A worker that ignores revocation can still write using its GitHub credentials. Branch protections and human review remain necessary controls; this skill never changes them.

Practical default: heartbeat at meaningful milestones or before shared writes, with owner-defined advisory TTL. Do not flood issues with automated minute-by-minute heartbeats. For sustained unattended concurrency, choose service mode.
