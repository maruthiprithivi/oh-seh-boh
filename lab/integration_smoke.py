"""Optional actual coord.project.v1 source smoke on approved isolated Linux.

No implementation is bundled/downloaded. Supervisor supplies approved source
and exact source pin. Principals are synthetic; no SSH security proof.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from client import invoke_existing_endpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile", choices=("membership", "writer"), default="membership")
    parser.add_argument("--capability-mapping", required=True,
                        choices=("legacy-experimental", "osb-firstmate.coord.project.v2"))
    parser.add_argument("--test-only", required=True, action="store_true")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if args.output.exists():
        parser.error("never overwrite validation evidence")
    actual = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    if actual != args.expected_source_commit:
        parser.error("owner source commit mismatch")
    dirty = subprocess.run(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"],
                           capture_output=True, text=True, check=True, timeout=5).stdout
    if dirty.strip():
        parser.error("owner source must be a clean isolated checkout at the verified pin")
    endpoint, core = source / "bin/fm-coord-endpoint.py", source / "bin/fm-coord.sh"
    if not endpoint.is_file() or not core.is_file():
        parser.error("approved owner implementation is unavailable")
    observations = []

    def record(name, result):
        observations.append({"name": name, **result})
        return result

    def observe(name, passed):
        observations.append({"name": name, "passed": bool(passed)})

    with tempfile.TemporaryDirectory(prefix="osb-owner-integration-") as temp:
        db = str(Path(temp) / "ledger.sqlite3")
        for operation, payload in (("init", None), ("scope-create", {
            "request_id": "setup", "scope_id": "synthetic-project", "team_id": "synthetic-team",
            "repo": "fixture-owner/fixture-repo", "forge_host": "github.com", "forge_repo_id": "10001",
            "initial_primary": "alice"})):
            command = ["bash", str(core), "--db", db, operation]
            if payload is not None:
                command.append(json.dumps(payload))
            proc = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
            record(operation, {"exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
            if proc.returncode != 0:
                break
        else:
            # Handles are fixed here by the supervisor, never derived from agent JSON.
            handles = {actor: [sys.executable, str(endpoint), db, actor] for actor in ("alice", "bob")}
            info = record("authority-info", invoke_existing_endpoint(handles["alice"], "authority-info", {}))
            discovery = info.get("receipt") or {}
            has_authority = (isinstance(discovery, dict)
                             and isinstance(discovery.get("authority_id"), str)
                             and bool(discovery["authority_id"]))
            if args.capability_mapping == "osb-firstmate.coord.project.v2":
                mapping_matches = (info["granted"] and has_authority and discovery.get("protocol") == "coord.project.v1"
                    and type(discovery.get("schema_version")) is int and discovery["schema_version"] == 10
                    and discovery.get("capability_profile") == "firstmate.scoped.v2")
            else:
                mapping_matches = (info["granted"] and has_authority and discovery.get("protocol") == "coord.project.v1"
                    and "schema_version" not in discovery and "capability_profile" not in discovery)
            observe("capability-mapping-matches", mapping_matches)
            if mapping_matches:
                authority = info["receipt"]["authority_id"]
                status = record("scope-status", invoke_existing_endpoint(handles["alice"], "scope-status", {"scope_id": "synthetic-project"}))
                if status["granted"]:
                    epoch = status["receipt"]["membership"]["epoch"]
                    invite = {"request_id": "invite", "scope_id": "synthetic-project", "authority_id": authority,
                              "membership_epoch": epoch, "invitation_id": "invite-bob", "target_principal": "bob", "role": "writer"}
                    record("scope-invite", invoke_existing_endpoint(handles["alice"], "scope-invite", invite))
                    join = {"request_id": "join", "scope_id": "synthetic-project", "authority_id": authority, "invitation_id": "invite-bob"}
                    first = record("scope-join", invoke_existing_endpoint(handles["bob"], "scope-join", join))
                    repeated = record("scope-join-replay", invoke_existing_endpoint(handles["bob"], "scope-join", join))
                    observations.append({"name": "exact-join-replay", "passed": first["receipt"] == repeated["receipt"] and first["granted"]})
                    # Stale authority is sent directly so the framing layer does not fix it.
                    wrong = {**join, "request_id": str(uuid.uuid4()), "authority_id": "stale-authority"}
                    denied = record("stale-authority", invoke_existing_endpoint(handles["bob"], "scope-join", wrong))
                    observe("stale-authority-refused", denied["exit"] == 1 and denied["receipt"] is None
                            and denied["stderr"].strip() == "fm-coord: stale authority identity; rediscover after fenced recovery")
                    if args.profile == "writer":
                        from owner_writer_smoke import run_writer_smoke
                        try:
                            run_writer_smoke(handles, authority, epoch, record, observe,
                                             v2=args.capability_mapping == "osb-firstmate.coord.project.v2")
                        except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
                            observations.append({"name": "writer-profile-incomplete", "passed": False,
                                                 "error_type": type(error).__name__})
    passed = all(row.get("passed", True) for row in observations)
    required = {"authority-info", "scope-status", "scope-invite", "scope-join", "scope-join-replay"}
    completed = {row["name"] for row in observations if row.get("granted")}
    passed = passed and required <= completed and all(row.get("exit", 0) == 0 for row in observations if row["name"] in ("init", "scope-create"))
    passed = passed and any(row["name"] == "capability-mapping-matches" and row.get("passed") for row in observations)
    if args.profile == "writer":
        writer_checks = {"claim-replay-identical", "overlapping-writer-refused", "claim-check-matches",
                         "renew-extends-lease", "released-claim-refused", "denial-replay-identical",
                         "successor-fence-increases", "revoked-claim-refused", "revocation-before-replay"}
        passed = passed and writer_checks <= {row["name"] for row in observations if row.get("passed")}
        if args.capability_mapping == "osb-firstmate.coord.project.v2":
            passed = passed and any(row["name"] == "v2-check-head-field" and row.get("passed") for row in observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps({"source_commit": actual, "profile": args.profile,
        "capability_mapping": args.capability_mapping, "status": "passed" if passed else "failed-or-incomplete",
        "synthetic_principals": True, "real_ssh_binding_proven": False,
        "scope": "disposable-source-fixture", "observations": observations,
        "limits": "bounded synthetic source smoke only; owner concurrency/load/restore and deployed transport suites still required"}, indent=2) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
