# Usable V1: cooperative ledger with existing GitHub tools

This workflow sets up and uses a real ledger without a new service or custom client. It requires a human owner and offers cooperative coordination, not lock enforcement. The CAS/service references are design/adapter requirements; this quickstart does not provision those runtimes. Commands below are instructions, not actions performed while creating this package. Use the repository's normal wrappers/guards where required. If `gh` is unavailable, use the GitHub browser UI for issue creation/comments and an existing authenticated API integration for immutable IDs; do not install tools automatically.

## Prepare and review

Choose an existing repository, host, team ID, named human integration owner and private/public visibility. In examples replace `github.com`, `OWNER/REPO`, numeric issue numbers and local draft paths with **verified approved** values. Do not copy example targets literally.

Read-only discovery through existing auth ([gh api](https://cli.github.com/manual/gh_api)):

```sh
gh auth status --hostname github.com
gh api --hostname github.com user --jq '{id: .id, node_id: .node_id, login: .login}'
gh api --hostname github.com repos/OWNER/REPO --jq '{id: .id, node_id: .node_id, full_name: .full_name, private: .private, permissions: .permissions}'
gh api --hostname github.com users/OWNER_LOGIN --jq '{id: .id, node_id: .node_id, login: .login}'
```

Never run `gh auth token` or `--show-token` for this workflow. The last lookup establishes identity only, not owner authorization; record the user's explicit owner designation. Copy `config/ledger.example.json` to a local review draft, fill resolved identity fields, mode `github-cooperative`, verified primary owner, control issue pending, and leave service/client fields null. Copy `templates/control-issue.md` and `templates/task-issue.md` to local drafts, fill all marked fields. Validate the decision by reading it with the user. Stop if destination or owner is unresolved.

Alternatively use the included offline standard-library draft helper. Populate `config/setup-input.example.json` with actual verified reads and approved decisions (examples are fictional); supply an existing private output parent and a **new** child directory:

```sh
python3 /approved/path/osb/scripts/prepare_cooperative.py --input /approved/path/setup-input.json --out /approved/path/private-drafts/new-ledger
```

It validates basic input shape and renders `ledger.json`, `control-issue.md`, `task-issue.md` without authentication, network, publication or overwriting an existing output. The output directory is created exclusively in a private parent; a crash may leave incomplete local drafts, which must be inspected/discarded privately before reuse. It does not verify identities or authorize setup; review drafts and replace the pending control URL after approved publication. Source is shipped, execution is untested. No helper execution is authorized on this task's Mac.

## Apply only within authorization

Create the control issue from the completed file ([gh issue create](https://cli.github.com/manual/gh_issue_create)):

```sh
gh issue create --repo https://github.com/OWNER/REPO --title 'Coordination ledger: TEAM' --body-file /approved/path/control-draft.md
```

Record its returned URL/ID in config. Put config at `.coordination/ledger.json` in the approved repository and the short continuity instruction from `compatibility.md` in its existing approved instruction file, using normal change/review flow. No commit, push, hook or branch-protection change is implied. No labels, Projects, App or webhook are required. If creation times out, read/search existing issues for the draft's unique setup ID before retrying; ambiguous matches require reconciliation. Do not create another control issue blindly.

Create first task from the filled task draft with a stable task ID:

```sh
gh issue create --repo https://github.com/OWNER/REPO --title 'TASK-ID: concrete outcome' --body-file /approved/path/task-draft.md
gh api --hostname github.com repos/OWNER/REPO/issues/123
gh api --hostname github.com --paginate repos/OWNER/REPO/issues/123/comments
```

Read the actual issue ID/node ID and link it to the stable task ID. Use repository-wide conflict scope for V1 unless the owner defines verified overlap rules. Resolve full base/head through existing Git/API tooling; record these in the request, not just branch names.

## Daily workflow

Read task and control issue plus all comment pages; authenticate current human/session, resolve repo identity, and compare latest grants/revocations. Prepare claim request as a local file with operation ID, task/scope, actor/session, expected generation and full base/head. Post only the authorized request:

```sh
gh issue comment 123 --repo https://github.com/OWNER/REPO --body-file /approved/path/claim-request.md
```

Read posted comment's API ID and author; await the configured human's acknowledgment as specified in `github-cooperative.md`. Post heartbeat/handoff/completion files using the same comment command with the appropriate operation/evidence. The human owner acknowledges extensions, transfers and releases. At resume and before shared writes, reread grant evidence; conflict/expiry/revocation stops shared writes. Owner offline means wait, not elect another owner.

This gives portable task history and an explicit integration owner today. “Always tracked” depends on participants following the project instruction and on review checks; native skill auto-discovery alone cannot enforce it. Upgrade to a validated deterministic CAS client or compatible authority only through an explicit capability review and cutover.
