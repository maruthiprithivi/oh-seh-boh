"""Read-only post-run capture around a pinned reference load profile."""
import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

from common import require, write_json


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    require(args.snapshot.is_absolute() and not args.snapshot.exists(), "unique snapshot required")
    sys.path.insert(0, str(args.source / "lab"))
    spec = importlib.util.spec_from_file_location("load", args.source / "lab/load.py")
    load = importlib.util.module_from_spec(spec)
    sys.modules["load"] = load
    spec.loader.exec_module(load)
    original = load.inspect_invariants

    def capture(db, results):
        with sqlite3.connect("file:" + str(db) + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            snapshot = {"contract": "osb.reference-observation.v1",
                "events": [dict(row) for row in connection.execute("SELECT seq,scope,kind,payload FROM events ORDER BY seq")],
                "request_keys": [[json.loads(row[0])[2], row[1]] for row in connection.execute("SELECT namespace,key FROM requests")],
                "acknowledged_keys": [[item["actor"], key] for item in results for key in item["receipts"]],
                "writes": [dict(row) for row in connection.execute("SELECT scope,task,actor,fence,head FROM protected_writes")]}
            snapshot["clock_ms"] = int(connection.execute("SELECT value FROM meta WHERE key='clock'").fetchone()[0])
            snapshot["current_claims"] = [dict(row) for row in connection.execute("SELECT scope,task,actor,fence,expires,active FROM claims")]
        write_json(args.snapshot, snapshot)
        return original(db, results)

    load.inspect_invariants = capture
    sys.argv = [str(args.source / "lab/load.py"), *remaining]
    return load.main()


if __name__ == "__main__":
    raise SystemExit(main())
