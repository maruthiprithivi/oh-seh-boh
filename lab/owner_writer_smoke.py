"""Source-only, optional coord.project.v1 writer checks for a disposable fixture.

No real credentials, remote writes, owner imports or implementation dependencies.
The supervisor selects handles and the runner supplies the clean source pin.
"""
from client import invoke_existing_endpoint


def run_writer_smoke(handles, authority, alice_epoch, record, observe, v2=False):
    scope = "synthetic-project"
    repo = "fixture-owner/fixture-repo"
    contexts = {"alice": {"scope_id": scope, "authority_id": authority,
                          "membership_epoch": alice_epoch}}

    def call(actor, operation, payload, name=None):
        return record(name or f"{actor}-{operation}", invoke_existing_endpoint(
            handles[actor], operation, {**contexts[actor], **payload}))

    def successful(result):
        return result["granted"]

    def refused(result, reason):
        # An interpreter/transport crash is not authority enforcement evidence.
        return (result["exit"] == 1 and result["receipt"] is None
                and result["stderr"].strip() == f"fm-coord: {reason}")

    def require_success(result):
        if not successful(result):
            raise ValueError("required writer setup/transition was refused")
        return result["receipt"]

    bob_status = record("bob-scope-status", invoke_existing_endpoint(
        handles["bob"], "scope-status", {"scope_id": scope}))
    contexts["bob"] = {"scope_id": scope, "authority_id": authority,
                       "membership_epoch": require_success(bob_status)["membership"]["epoch"]}
    sessions = {}
    for actor in ("alice", "bob"):
        home = f"fixture-{actor}"
        require_success(call(actor, "enroll", {"request_id": f"enroll-{actor}",
                        "home_id": home, "repos": [repo]}))
        receipt = require_success(call(actor, "session", {
            "request_id": f"session-{actor}", "home_id": home}))
        sessions[actor] = {"home_id": home, "generation": receipt["generation"]}
        require_success(call(actor, "submit", {**sessions[actor],
            "request_id": f"submit-{actor}", "intent_id": f"intent-{actor}",
            "repo": repo, "base": "refs/heads/main", "base_oid": "1" * 40,
            "branch": f"fixture/{actor}", "task_id": f"task-{actor}",
            "goal": "Disposable ownership smoke", "resources": [
                {"type": "file", "name": "fixture/shared.txt"}]}))

    payloads = {actor: {**sessions[actor], "request_id": f"claim-{actor}",
                       "intent_id": f"intent-{actor}", "version": 1,
                       "ttl_seconds": 300} for actor in ("alice", "bob")}
    alice = call("alice", "claim", payloads["alice"])
    claim = require_success(alice)
    replay = call("alice", "claim", payloads["alice"], "alice-claim-replay")
    observe("claim-replay-identical", successful(replay) and replay["receipt"] == claim)
    bob = call("bob", "claim", payloads["bob"], "bob-conflicting-claim")
    conflict = bob.get("receipt") or {}
    observe("overlapping-writer-refused", bob["exit"] == 0 and conflict.get("ok") is False
            and conflict.get("reason") == "scope-conflict"
            and any(row.get("claim_id") == claim["claim_id"] for row in conflict.get("conflicts", [])))
    live = {**sessions["alice"], "claim_id": claim["claim_id"], "fence": claim["fence"]}
    check = require_success(call("alice", "check", live))
    observe("claim-check-matches", check["claim_id"] == claim["claim_id"]
            and check["fence"] == claim["fence"])
    if v2:
        observe("v2-check-head-field", "head_oid" in check and check["head_oid"] is None)
    renewed = require_success(call("alice", "renew", {**live, "request_id": "renew-alice",
                                                          "ttl_seconds": 600}))
    observe("renew-extends-lease", renewed["expires_mono_ns"] > check["expires_mono_ns"])
    require_success(call("alice", "release", {**live, "request_id": "release-alice"}))
    released = call("alice", "check", live, "released-claim-check")
    observe("released-claim-refused", refused(released, "claim is not active"))
    # A denial is an immutable receipt: release must not change its replay result.
    denied_replay = call("bob", "claim", payloads["bob"], "bob-denial-replay")
    observe("denial-replay-identical", denied_replay["exit"] == 0
            and denied_replay["receipt"] == conflict)
    bob_claim = require_success(call("bob", "claim", {**payloads["bob"],
                                     "request_id": "claim-bob-after-release"}, "bob-claim-after-release"))
    observe("successor-fence-increases", bob_claim["fence"] > claim["fence"])
    require_success(call("alice", "scope-revoke", {"request_id": "revoke-bob",
                                                   "target_principal": "bob"}))
    stale = {**sessions["bob"], "claim_id": bob_claim["claim_id"], "fence": bob_claim["fence"]}
    revoked = call("bob", "check", stale, "revoked-claim-check")
    observe("revoked-claim-refused", refused(revoked, "membership unavailable or revoked"))
    revoked_replay = call("bob", "claim", {**payloads["bob"],
        "request_id": "claim-bob-after-release"}, "revoked-claim-replay")
    observe("revocation-before-replay", refused(revoked_replay, "membership unavailable or revoked"))
