"""Deterministic optional workflow CLI. GCP-only execution until qualified.

JSON inputs are data, never commands. No subprocess, dynamic imports, network,
provider calls, authority setup, process control, merge or deploy.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from workflow.admission import evaluate
from workflow.contract import Refusal, canonical, check_config, envelope, next_action
from workflow.journal import install, prepare, observe, pending
from workflow.notifications import ProjectACL, poll_pending


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result: raise Refusal("duplicate-json-key")
        result[k] = v
    return result


def read(path):
    with open(path, "rb") as f: data = f.read(65537)
    if len(data) > 65536: raise Refusal("input-limit")
    return json.loads(data, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal("nonfinite-json")))


def connect(path, create=False):
    p = Path(path).absolute()
    if create:
        # Existing files are never initialized or migrated implicitly.
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    if p.is_symlink() or not p.is_file() or p.stat().st_uid != os.getuid() or p.stat().st_mode & 0o077:
        raise Refusal("journal-must-be-existing-private-owned-file")
    # mode=rw avoids implicit creation if a path disappears.
    return sqlite3.connect(p.as_uri() + "?mode=rw", uri=True, timeout=1)


def admit_snapshot(c, s):
    check_config(c)
    if not isinstance(s, dict) or set(s) != {"backlog", "capacity", "active", "landing"}:
        raise Refusal("snapshot-fields")
    for values in (s["backlog"], s["active"]):
        if isinstance(values, list) and any(isinstance(t, dict) and t.get("repo_id") != c["repo_id"] for t in values):
            raise Refusal("configured-repository-mismatch")
    return evaluate(s["backlog"], s["capacity"], s["active"], s["landing"], c["project"])


def main():
    parser = argparse.ArgumentParser(description="OSB optional advisory workflow and immutable intent journal")
    parser.add_argument("--config", required=True)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("init-journal", "pending", "poll"):
        subs.add_parser(name).add_argument("--journal", required=True)
    decision = subs.add_parser("decide"); decision.add_argument("--task", required=True); decision.add_argument("--state", required=True)
    adm = subs.add_parser("admit"); adm.add_argument("--snapshot", required=True)
    env = subs.add_parser("envelope"); env.add_argument("--task", required=True); env.add_argument("--operation", required=True); env.add_argument("--payload", required=True)
    prep = subs.add_parser("prepare"); prep.add_argument("--journal", required=True); prep.add_argument("--envelope", required=True)
    rec = subs.add_parser("record-observation"); rec.add_argument("--journal", required=True); rec.add_argument("--key", required=True); rec.add_argument("--status", choices=["confirmed", "refused", "unknown"], required=True); rec.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        c = read(args.config); check_config(c)
        if args.command == "decide": result = next_action(c, read(args.task), read(args.state))
        elif args.command == "admit":
            result = admit_snapshot(c, read(args.snapshot))
        elif args.command == "envelope": result = envelope(c, read(args.task), args.operation, read(args.payload))
        else:
            db = connect(args.journal, args.command == "init-journal")
            try:
                if args.command in {"init-journal", "prepare", "record-observation"}:
                    db.execute("BEGIN IMMEDIATE")
                    with db:
                        if args.command == "init-journal": install(db, c); result = {"initialized": True}
                        elif args.command == "prepare": result = {"status": prepare(db, c, read(args.envelope))}
                        else: result = {"status": observe(db, c, args.key, args.status, read(args.receipt))}
                elif args.command == "pending": result = pending(db, c)
                else:
                    # Pure broker-free read at owner-supplied zero virtual time;
                    # outbound retry scheduling is an adapter operation, not CLI authority.
                    pending(db, c)  # validates immutable run binding
                    acl = ProjectACL({c["project"]: (c["project"], c["repo_id"], str(c["authority"]["epoch"]))})
                    result = poll_pending(db, acl, now=0)
            finally: db.close()
        print(canonical({"protocol": "osb.factory.cli.v1", "ok": True, "result": result,
                         "authority": "advisory-local-workflow-only"}))
        return 0
    except (Refusal, ValueError, TypeError, KeyError, OSError, sqlite3.Error):
        print(canonical({"protocol": "osb.factory.cli.v1", "ok": False, "reason": "input-or-state-refused"}))
        return 2


if __name__ == "__main__": sys.exit(main())
