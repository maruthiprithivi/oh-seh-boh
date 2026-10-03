# Logical contract v1

This is a protocol description for adapter review and acceptance fixtures, not a new wire API or a mandatory replacement schema. `osb/1` versions this package's logical envelopes only. The deployed authority's implemented contract/version is authoritative and must be recorded separately in config. Bind that owner's contract through an explicit mapping and report unsupported semantics rather than introduce a competing authority format. No deployed-authority runtime compatibility is asserted here.

| Field | Required semantics |
|---|---|
| `schema_version` | `osb/1`; reject unknown major versions. |
| `scope` | `{github_host, repository_id, team_id}`; repository ID fetched from trusted host; node ID retained when available. |
| `task_id` | Durable opaque ID; issue node ID can link intent, issue number alone cannot identify repo. |
| `actor` | `{principal_id, session_id}`; principal verified by transport, session scoped to principal. |
| `operation`, `idempotency_key` | Explicit lifecycle action and stable opaque key; not a secret. |
| `authority_epoch` | Changes on authority cutover/disaster recovery; old grants become invalid. |
| `expected_generation`, `expected_version` | Compare-and-set preconditions; required for existing grant mutations; initial claim uses last observed generation/version. |
| `conflict_scope` | Repository integration key or normalized structured resources; configured overlap rules. Reject unknown/empty scope; default conservatively to repository-wide. |
| `revision` | `{object_format, base_oid, head_oid, target_ref}`; full resolved OIDs; target ref is not identity. |
| `recipient` | Authenticated intended human principal and session for accepted transfer. |
| `evidence` | Outcome, artifact/PR links, verification status and next action; private evidence stays in approved private storage. |

A grant receipt includes scope/task/actor, authority epoch, generation, state version, issued/expiry authority timestamps, granted conflict scope, revision, operation key, immutable event ID and status (`granted`, `denied`, `uncertain`, or lifecycle-specific result). Client-provided expiry/identity is not authoritative. A denial must never be converted to a grant by reading labels.

In service mode retain audit events outside mutable issue comments; in cooperative mode comment IDs and verified author IDs are receipts subject to GitHub edit/delete limits. Use UTC RFC3339 timestamps, reject malformed dates, and retain exact OIDs (SHA-1 40 hex / SHA-256 64 hex according to declared format). Task identity and owner principal IDs are not login display names.
