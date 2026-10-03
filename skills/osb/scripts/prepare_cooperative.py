"""Offline cooperative-ledger draft preparation; no auth/network/publication.

Inputs must be populated from verified identity reads and human decisions.
Source-only: execution has not been validated in this task.
"""
import argparse
import json
from pathlib import Path
import re
import tempfile


def prepare(input_path, output_path):
    raw = input_path.read_bytes()
    if len(raw) > 65536:
        raise ValueError("input exceeds 64 KiB")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    required = ("setup_id", "github_host", "repository_id", "repository_node_id",
                "repository_full_name", "team_id", "owner_id", "owner_login",
                "task_id", "outcome", "base_oid", "head_oid", "object_format",
                "lease_policy", "contact_route", "evidence_location")
    for key in required:
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError("missing string field: " + key)
        if len(data[key]) > 4096 or any(ord(c) < 32 for c in data[key]):
            raise ValueError("oversized or control-character field: " + key)
    ttl = data.get("advisory_ttl_seconds")
    if type(ttl) is not int or not 60 <= ttl <= 86400:
        raise ValueError("advisory TTL must be an integer from 60 to 86400 seconds")
    for key in ("setup_id", "team_id", "task_id"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", data[key]):
            raise ValueError("invalid opaque identifier: " + key)
    for key in ("repository_id", "owner_id"):
        if not re.fullmatch(r"[1-9][0-9]*", data[key]):
            raise ValueError("expected resolved numeric GitHub ID: " + key)
    if not re.fullmatch(r"[A-Za-z0-9.-]+", data["github_host"]):
        raise ValueError("invalid GitHub host")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", data["repository_full_name"]):
        raise ValueError("invalid repository full name")
    if not re.fullmatch(r"[A-Za-z0-9-]+", data["owner_login"]):
        raise ValueError("invalid owner login")
    length = {"sha1": 40, "sha256": 64}.get(data["object_format"])
    if not length:
        raise ValueError("unsupported object format")
    for key in ("base_oid", "head_oid"):
        if not re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", data[key]):
            raise ValueError("full lowercase OID required: " + key)
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "config/ledger.example.json").read_text())
    config["scope"] = {"github_host": data["github_host"],
                       "repository_id": data["repository_id"],
                       "repository_node_id": data["repository_node_id"],
                       "team_id": data["team_id"]}
    config["repository_url"] = "https://" + data["github_host"] + "/" + data["repository_full_name"]
    config["primary_owner"] = {"principal_id": data["owner_id"], "display_login": data["owner_login"]}
    config["lease_policy"]["owner_policy"] = data["lease_policy"]
    config["lease_policy"]["ttl_seconds"] = ttl
    replacements = {
        "TEAM_ID": data["team_id"], "UNIQUE_SETUP_ID": data["setup_id"],
        "GITHUB_HOST": data["github_host"], "REPOSITORY_ID": data["repository_id"],
        "VERIFIED_PRINCIPAL_ID": data["owner_id"], "DISPLAY_LOGIN": data["owner_login"],
        "EXPLICIT_HUMAN_IDS_OR_NONE": "none", "OWNER_APPROVED_POLICY": "Advisory TTL " + str(ttl) + " seconds. " + data["lease_policy"],
        "CONTACT_ROUTE": data["contact_route"], "APPROVED_LOCATION": data["evidence_location"],
        "TASK_ID": data["task_id"], "CONCRETE_OUTCOME": data["outcome"], "OUTCOME": data["outcome"],
        "TASK_IDS_OR_NONE": "none", "VERIFIED_HUMAN_ID": data["owner_id"],
        "FULL_BASE_OID": data["base_oid"], "FULL_HEAD_OID": data["head_oid"],
        "FORMAT": data["object_format"], "APPROVED_CONTROL_URL": "PENDING_CONTROL_ISSUE_URL"}
    output_path = output_path.absolute()
    if output_path.exists():
        raise ValueError("output directory already exists; no overwrite permitted")
    if not output_path.parent.is_dir():
        raise ValueError("output parent must already exist")
    # Render first, then create destination exclusively; no existing output is replaced.
    with tempfile.TemporaryDirectory(prefix="ledger-draft-", dir=output_path.parent) as temp:
        stage = Path(temp) / "draft"
        stage.mkdir(mode=0o700)
        (stage / "ledger.json").write_text(json.dumps(config, indent=2) + "\n")
        for name in ("control-issue.md", "task-issue.md"):
            text = (root / "templates" / name).read_text()
            for key, value in replacements.items():
                text = text.replace("[" + key + "]", value)
            (stage / name).write_text(text)
        # Output parent must be private. A crash may leave incomplete local drafts.
        # No remote/config mutation follows automatically; inspect and discard privately.
        output_path.mkdir(mode=0o700, exist_ok=False)
        for source in stage.iterdir():
            with (output_path / source.name).open("xb") as dest:
                dest.write(source.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare(args.input, args.out)
    except (ValueError, OSError) as exc:
        # Never echo input values, file contents or secrets in diagnostics.
        parser.exit(1, "Draft preparation failed: " + type(exc).__name__ + "; inspect inputs privately.\n")
    print("Prepared local drafts. Review them; control issue URL remains pending. Nothing published.")


if __name__ == "__main__":
    main()
