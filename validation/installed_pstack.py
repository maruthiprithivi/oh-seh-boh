"""Actual pinned PStack store acceptance and independent effect observations.

No LLM/forge calls or dependency installation. Supplied real authority only.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys

from common import bootstrap_ready, clean_pin, require, write_json


def observe(fixture, intentionally_invalid=False):
    ledger = Path(fixture.cfg["orch_store"]) / "ledger.tsv"
    require(ledger.is_file(), "independent observation: ledger missing")
    lines = ledger.read_text().splitlines()
    valid_header = bool(lines) and lines[0] == "pr\tsha\tverdict\tevidence\tverifier\tts"
    if intentionally_invalid:
        require(not valid_header, "intentional corruption was not observed")
        rows, ledger_state = None, "intentionally-malformed-header"
    else:
        require(valid_header, "independent observation: malformed ledger header")
        rows, ledger_state = [line.split("\t") for line in lines[1:] if line], "readable-native-header"
        require(all(len(row) == 6 for row in rows), "independent ledger parser: malformed record")
    with sqlite3.connect("file:" + fixture.endpoint.db + "?mode=ro", uri=True) as db:
        claims = list(db.execute("SELECT claim_id,intent_id,home_id,generation,fence,state FROM claims"))
    return {"ledger_rows": rows, "ledger_state": ledger_state, "claims": claims, "active_claims": sum(row[-1] == "active" for row in claims),
            "worker_started": fixture.marker.exists()}


def scenario(module, bun, orch, name, runner, evidence):
    fixture = module.Lifecycle("test_success_records_exact_head_and_refuses_repeat")
    try:
        fixture.setUp()
        module.RUNNER = runner
        fixture.cfg["orch_route"] = [str(bun), str(orch)]
        store = Path(fixture.cfg["orch_store"])
        (store / "mock-initialized.json").unlink()
        subprocess.run([str(bun), str(orch), "--store", str(store), "init"], check=True, capture_output=True, timeout=15)
        if name == "invalid-store":
            (store / "ledger.tsv").write_text("malformed-header\n")
            receipt = fixture.result(fixture.launch(), 1)
        elif name in ("revocation", "cancel"):
            fixture.cfg["local_verifier"][-1] = "wait"
            process = fixture.launch()
            fixture.wait_for_worker(process)
            if name == "revocation":
                fixture.endpoint.sessions["alice"] = fixture.endpoint.call("alice", "session", {})["generation"]
                fixture.marker.with_suffix(".continue").write_text("finish\n")
            else:
                process.send_signal(signal.SIGTERM)
            receipt = fixture.result(process, 1)
        else:
            receipt = fixture.result(fixture.launch(), 0)
        observation = observe(fixture, intentionally_invalid=name == "invalid-store")
        violations = []
        if name == "success":
            rows = observation["ledger_rows"]
            if len(rows) != 1 or rows[0][:3] != ["42", fixture.spec["head_oid"], "unit-test-verified"]:
                violations.append("actual-verdict-missing-or-wrong")
            elif not Path(rows[0][3]).is_file():
                violations.append("evidence-file-missing")
            check = subprocess.run([str(bun), str(orch), "--store", str(store), "ledger", "check", "42", fixture.spec["head_oid"]], text=True, capture_output=True, timeout=15)
            if check.returncode != 0 or check.stdout.strip() != "unit-test-verified":
                violations.append("native-ledger-check-failed")
        elif observation["ledger_rows"]:
            violations.append("forbidden-verdict-recorded")
        if observation["active_claims"]:
            violations.append("active-claim-after-cleanup")
        if name == "invalid-store" and observation["worker_started"]:
            violations.append("worker-started-with-invalid-store")
        result = {"scenario": name, "runner_receipt": receipt, "independent_observation": observation, "violations": violations}
        destination = evidence / name
        destination.mkdir(mode=0o700)
        shutil.copytree(store, destination / "store")
        runs = Path(fixture.cfg["run_directory"])
        if runs.exists():
            shutil.copytree(runs, destination / "runs")
        shutil.copytree(Path(fixture.cfg["journal"]), destination / "client-journal")
        with sqlite3.connect(fixture.endpoint.db) as source, sqlite3.connect(destination / "authority.sqlite3") as snapshot:
            source.backup(snapshot)
        write_json(destination / "observation.json", result)
        return result
    finally:
        fixture.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pstack", required=True, type=Path)
    parser.add_argument("--pstack-commit", required=True)
    parser.add_argument("--bun", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--mutation", choices=("none", "skip-store-gate", "skip-publication-checkpoint"), default="none")
    args = parser.parse_args()
    require(sys.platform == "linux", "authorized Linux only")
    clean_pin(args.pstack, args.pstack_commit)
    bootstrap_ready(args.pstack, args.bun)
    require(args.evidence.is_absolute() and not args.evidence.exists(), "unique evidence directory required")
    args.evidence.mkdir(mode=0o700, parents=True)
    tests = args.pstack / "pstack/skills/osb-coordination/tests"
    sys.path.insert(0, str(tests))
    spec = importlib.util.spec_from_file_location("pstack_lifecycle", tests / "lifecycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runner = args.pstack / "pstack/skills/osb-coordination/scripts/run_local_verifier.py"
    orch = args.pstack / "pstack/skills/poteto-mode/scripts/orch/orch.ts"
    scenarios = ("success", "invalid-store", "revocation", "cancel")
    if args.mutation != "none":
        copied = args.evidence / "mutant"
        copied.mkdir(mode=0o700)
        shutil.copyfile(runner.with_name("osb.py"), copied / "osb.py")
        source = runner.read_text()
        if args.mutation == "skip-store-gate":
            token = 'require(preflight.returncode == 0, "orch-store-preflight-refused")'
            require(source.count(token) == 1, "store mutation did not match exactly")
            source = source.replace(token, "pass # test-only omitted store gate", 1)
            scenarios = ("invalid-store",)
        else:
            token = 'require(client.checkpoint({"payload": capsule, "expected_revision": expected}).get("ok") is True, "publication-checkpoint-refused")'
            require(source.count(token) == 1, "checkpoint mutation did not match exactly")
            source = source.replace(token, "pass # test-only omitted publication checkpoint", 1)
            scenarios = ("revocation",)
        runner = copied / "run_local_verifier.py"
        runner.write_text(source)
    results = [scenario(module, args.bun, orch, name, runner, args.evidence) for name in scenarios]
    failures = [item for item in results if item["violations"]]
    if args.mutation == "none":
        ok = not failures
    else:
        expected = "worker-started-with-invalid-store" if args.mutation == "skip-store-gate" else "forbidden-verdict-recorded"
        ok = any(expected in item["violations"] for item in results)
    report = {"contract": "osb.installed-acceptance.v1", "mutation": args.mutation, "ok": ok, "results": results,
              "qualification": "actual local PStack store and supplied authority; no deployed auth, forge effects or atomic fence proof"}
    write_json(args.evidence / "report.json", report)
    print(json.dumps({"ok": ok, "mutation": args.mutation, "report": str(args.evidence / "report.json")}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
