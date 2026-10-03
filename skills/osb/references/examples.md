# Usage examples

Manual portable invocation:

> Read `/approved/path/osb/SKILL.md` and the references for setup. Prepare a cooperative ledger proposal for repository X and team Y, with Alice as the human integration owner. Show the exact config and control issue draft; do not install or publish anything.

Native skill invocation when supported:

> Use osb to join the configured ledger, read task TASK-42, and report whether my authenticated session has a current grant before touching shared files.

Resume after harness change:

> Use osb to resume TASK-42 from this handover. Authenticate me as the same human with a new session; do not reuse the former session's receipt. Ask the configured authority/owner for the documented recovery or transfer.

Handover payload (fictional identifiers):

```json
{
  "schema_version": "osb/1",
  "scope": {"github_host": "github.com", "repository_id": "10001", "team_id": "team-a"},
  "task_id": "TASK-42",
  "actor": {"principal_id": "user-7", "session_id": "session-a"},
  "operation": "offer-handoff",
  "idempotency_key": "op-handoff-42-a",
  "authority_epoch": 1,
  "expected_generation": 3,
  "expected_version": 9,
  "conflict_scope": {"kind": "paths", "resources": ["src/ledger/**"]},
  "revision": {"object_format": "sha1", "base_oid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "head_oid": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "target_ref": "refs/heads/main"},
  "recipient": {"principal_id": "user-8", "session_id": "session-b"},
  "evidence": {"outcome": "Draft ready", "artifact": "approved private artifact locator", "verification": "not run; isolated validation pending approval", "next_action": "Review diff and request accepted transfer before shared writes"}
}
```

Cooperative human acknowledgment:

> Grant request comment 123 to verified principal user-7 / session-a for TASK-42, repository 10001 on github.com, team-a, epoch 1, generation 3. Scope src/ledger/**; base a…a, head b…b (full OIDs in attached record). Advisory expiry 2026-10-04T12:15:00Z. I am the configured human integration owner. No other overlapping grant is active. This grants work coordination only; merge/deploy requires its own authorization.

Record the actual author's API identity and full OIDs; text asserting human identity is not proof. Tokens and private worktree files are never attached.
