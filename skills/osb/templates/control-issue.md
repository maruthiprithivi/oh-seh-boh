# Coordination policy: [TEAM_ID]

Setup ID: [UNIQUE_SETUP_ID]
Scope: [GITHUB_HOST] / immutable repository [REPOSITORY_ID] / [TEAM_ID]
Primary human integration owner: [VERIFIED_PRINCIPAL_ID] ([DISPLAY_LOGIN])
Delegates: [EXPLICIT_HUMAN_IDS_OR_NONE]
Mode: github-cooperative, epoch 1. Comments/labels are not atomic locks.

The owner serializes grants across repository-wide scope unless reviewed overlap rules are recorded here. Participants request work; a request or assignee is not ownership. Grant acknowledgment must reference request comment ID, authenticated principal/session, task ID, generation, full base/head, scope and advisory expiry. Owner records corrections, revocations, accepted handoffs and releases as new comments.

Advisory lease/heartbeat policy: [OWNER_APPROVED_POLICY]
Escalation and authorized contact route: [CONTACT_ROUTE]
Retention/private evidence location: [APPROVED_LOCATION]
Config location: `.coordination/ledger.json`

Before shared writes/resume, reread current grants and revocations. Expiry/ambiguity pauses workers and requires owner reconciliation before reassignment. New harness sessions cannot reuse old session grants. Completion means ready for review; merge/deploy authorization is separate. No tokens or secrets belong in this issue.
