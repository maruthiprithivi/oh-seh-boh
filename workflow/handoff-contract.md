# Delta handoff policy source preview

Reference inspected read-only: [BatonPass README](https://github.com/francisN21/baton-pass/blob/main/README.md),
[skill](https://github.com/francisN21/baton-pass/blob/main/SKILL.md), and
[receiver preflight](https://github.com/francisN21/baton-pass/blob/main/commands/foresight.md).
Its compact changed-context record, pause/transfer distinction and receiving-agent
preflight informed this schema. No source is copied, no plugin is installed and no
token reduction is inferred from its project description. Its local document/state
workflow does not establish atomic claims or fencing. OSB retains its one authority
and backlog; a next-task document cannot win an ownership conflict.

`handoff.py` is pure policy and CLI data preparation, **UNRUN**. An offer cannot
transfer work. The sequence is checkpoint, offer, receiver verification, existing
authority atomic acceptance, fresh live successor read, existing dispatcher resume.
If the selected owner endpoint has no compatible atomic acceptance operation,
refuse the transfer and retain current ownership. Do not invent a generic completion
or handoff endpoint for the frozen PStack local verifier route.
The inspected Firstmate-backed production adapter currently has no mapped generic
handoff-accept capability. These tests are logical policy/fixture acceptance only;
they do not establish production transfer. `bridge.apply_prepared` requires an
explicit reviewed `supported_operations` capability set and refuses unsupported
acceptance before owner authorization or effect invocation.

`pause` preserves the sender as owner and receiver; it never advances a generation.
`offer` names a distinct receiver and binds exact project/repository/authority/epoch,
run/dispatcher, task revision/base/head and old generation/fence. The packet includes
only changed context: worktree locator/branch/head and dirty/uncommitted state,
deviations, nonsecret environment prerequisites, verification status with evidence
digest for executed results, risks and next immediate action. Worktree locator may
be an approved opaque ID; do not publish private host paths or secret values.
Packet size is capped at 16 KiB; no history recap or duplicate backlog is introduced.

Before producing an acceptance intent, the receiver's reviewed adapter must verify
the repository identity, task revision, old owner/current capsule and the exact
offered delta/evidence against source and retained receipts. It must also obtain
existing controller proof of old worker quiescence. A Boolean read from a local JSON
file is not such proof. Firstmate's existing lifecycle/journal/fence rules remain
mandatory; neither apparent lease expiry nor document acceptance proves a process
stopped. Receiver preflight cannot replace the atomic expected-capsule acceptance.

An offer ID is an immutable occurrence approved/journaled by the existing authority,
not a random receiver-selected retry escape. The receiver's authenticated preflight
must bind that offer ID plus its digest. Reissuing after a refused/stale offer needs
an owner-approved new occurrence after reconciliation; altered bytes under the old
offer ID conflict. The acceptance key includes the approved occurrence, while retries
of that same occurrence retain one key and exact bytes.

Acceptance belongs to the existing authority: it must atomically compare old
owner/epoch/generation/fence/revision and offer digest, verify receiver ACL/session,
transfer once under the stable operation key, increment the successor generation
and fencing token, and journal the result/outbox in the same transaction or approved
CAS. A lost acknowledgment reconciles the original key; never create a fresh offer
to escape uncertainty. Do not overwrite immutable prior intent records.

`handoff-resume` requires the committed acceptance receipt and a fresh authenticated
read of the exact successor owner, epoch, generation/fence and task revision, with
predecessor quiescence bound to the accepted offer digest/ID and old capsule. It
only recommends resuming the configured existing dispatcher. The owner bridge must
check current ownership and effect preconditions again when it actually resumes;
this pure check is not an atomic external effect fence. Source dictionaries/digests
are neither signatures nor credentials. No module launches or controls a process.

Commands run only on the separately admitted GCP executor from the repository root:

```sh
python3 -m workflow.cli --config sender.json checkpoint --task task.json --claim claim.json --delta delta.json --mode pause
python3 -m workflow.cli --config sender.json checkpoint --task task.json --claim claim.json --delta delta.json --mode offer --to receiver --offer-id approved-offer-1
python3 -m workflow.cli --config receiver.json handoff-accept --packet offer.json --preflight preflight.json
python3 -m workflow.cli --config receiver.json handoff-resume --packet offer.json --receipt accepted.json --current current.json
```

Adversarial source covers pause transfer refusal, offer-as-permission refusal,
wrong repo/epoch/evidence/quiescence, changed head and stale fences, explicit dirty
work, modified delta, and committed/live successor checks. Execute the existing
synthetic GCP stage including `test_handoff.py`, then qualify actual owner acceptance
concurrency, delayed acknowledgment, revocation and Firstmate quiescence. Local
fixture passes cannot establish those owner properties. No new paid resources,
provider/security grants, plugin install, merge or deployment follows.
