"""UNRUN optional native PStack cases for a separately admitted existing GCP job.

Reuses frozen validation/installed_pstack.py and PStack lifecycle setup unchanged.
Requires operator-pinned clean packet/PStack/authority and preinstalled Bun.
No provisioning, installs, downloads, forge calls, LLMs or production configuration.
The external supervisor enforces the plan's wall cap and existing containment.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time


CASES = ("unavailable-route", "uncertain-effect-recovery")
EXCLUDED_ENVIRONMENT = ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_REPO", "FM_HOME", "FM_COORD_CONFIG",
                        "FM_COORD_AUTHORITY_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_plan(plan):
    require(isinstance(plan, dict), "native plan must be an object")
    require(plan.get("contract") == "osb.native-pstack-cases.v1", "native plan contract required")
    require(plan.get("admitted_existing_gcp") is True, "existing GCP admission required")
    require(isinstance(plan.get("admission_reference"), str) and plan["admission_reference"].strip(),
            "external supervisor admission reference required; flag is not approval")
    require(type(plan.get("max_wall_seconds")) is int and 60 <= plan["max_wall_seconds"] <= 180,
            "external supervisor wall cap must be 60..180 seconds")
    for key in ("packet", "pstack", "owner", "bun", "evidence", "exclusive_existing_cgroup"):
        require(isinstance(plan.get(key), str) and Path(plan[key]).is_absolute(), "absolute " + key + " required")
    cpus = plan.get("admitted_cpus")
    require(isinstance(cpus, list) and 1 <= len(cpus) <= 2 and
            all(type(cpu) is int and cpu >= 0 for cpu in cpus), "1..2 integer admitted CPU IDs required")
    require(len(set(cpus)) == len(cpus), "unique admitted CPU IDs required")
    for key in ("packet_commit", "pstack_commit", "owner_commit"):
        require(isinstance(plan.get(key), str) and re.fullmatch(r"[0-9a-f]{40}", plan[key]), "exact " + key + " required")
    require(isinstance(plan.get("bun_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", plan["bun_sha256"]),
            "preprovisioned Bun digest required")
    evidence = Path(plan["evidence"])
    for key in ("packet", "pstack", "owner"):
        root = Path(plan[key])
        require(not evidence.is_relative_to(root) and not root.is_relative_to(evidence),
                "evidence must not overlap source trees")
    require(plan.get("cases") == list(CASES), "both native cases required; no silent omission")
    return plan


def clean_environment(environment):
    """Same credential/config exclusions as the retained validation/run.py."""
    return {key: value for key, value in environment.items() if key not in EXCLUDED_ENVIRONMENT}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_read(bun, orch, fixture, command):
    process = subprocess.run([str(bun), str(orch), "--store", fixture.cfg["orch_store"], *command],
                             capture_output=True, text=True, timeout=15)
    return {"command": command, "exit": process.returncode, "stdout": process.stdout, "stderr": process.stderr}


def snapshot(fixture, destination):
    for label, path in (("store", fixture.cfg["orch_store"]), ("runs", fixture.cfg["run_directory"]),
                        ("client-journal", fixture.cfg["journal"])):
        if Path(path).exists():
            shutil.copytree(path, destination / label)
    for label, path in (("config.json", fixture.cfg_path), ("spec.json", fixture.spec_path),
                        ("worker.json", fixture.marker), ("relay.jsonl", fixture.directory / "relay.jsonl")):
        if path.exists():
            shutil.copyfile(path, destination / label)
    with sqlite3.connect("file:" + fixture.endpoint.db + "?mode=ro", uri=True) as source:
        with sqlite3.connect(destination / "authority.sqlite3") as target:
            source.backup(target)


def quiet(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False


def run_case(module, installed, bun, orch, relay, name, evidence):
    destination = evidence / name
    destination.mkdir(mode=0o700)
    fixture = module.Lifecycle("test_success_records_exact_head_and_refuses_repeat")
    report = {"scenario": name, "status": "setupfailed", "ok": False}
    try:
        fixture.setUp()
        fixture.cfg["orch_route"] = [str(bun), str(orch)]
        store = Path(fixture.cfg["orch_store"])
        (store / "mock-initialized.json").unlink()
        initialized = native_read(bun, orch, fixture, ["init"])
        report["native_init"] = initialized
        require(initialized["exit"] == 0, "native init failed")
        before = installed.observe(fixture)
        report["before"] = before
        require(not before["claims"] and not before["ledger_rows"], "fresh native fixture required")
        report["status"] = "behaviorfailure"
        if name == "unavailable-route":
            missing = fixture.directory / "absent-authority-endpoint.py"
            require(not missing.exists(), "unavailable route must be absent")
            # Executable Python passes fixed-route validation; actual endpoint is unavailable.
            fixture.cfg["route"] = [sys.executable, str(missing)]
            fixture.cfg["journal"] = str(fixture.directory / "unavailable-route-journal")
            report["first_receipt"] = fixture.result(fixture.launch(), 1)
            after = installed.observe(fixture)
            report["after"] = after
            require(report["first_receipt"]["outcome"] == "setupfailed", "unavailable route did not refuse")
            require(report["first_receipt"]["reason"] == "authority-refused-or-unavailable",
                    "refusal did not exercise unavailable authority discovery")
            require(not after["worker_started"] and not after["ledger_rows"] and not after["claims"],
                    "unavailable route started worker or mutated verdict/claim")
        else:
            audit = fixture.directory / "relay.jsonl"
            fixture.cfg["orch_route"] = [sys.executable, str(relay), str(bun), str(orch), str(audit)]
            first = fixture.result(fixture.launch(), 1)
            report["first_receipt"] = first
            require((first["outcome"], first["effect"], first["release"]) ==
                    ("behaviorfailure", "unknown", "confirmed"), "unknown native effect not retained")
            require(first["reason"] == "verdict-record-failed-or-unknown", "native record receipt-loss path not exercised")
            before_retry = installed.observe(fixture)
            report["before_retry"] = before_retry
            rows = before_retry["ledger_rows"]
            require(len(rows) == 1 and rows[0][:3] == ["42", fixture.spec["head_oid"], "unit-test-verified"],
                    "actual native effect not independently observed")
            require(Path(rows[0][3]).is_file(), "native row evidence missing")
            state_path = Path(first["run_directory"]) / "state.json"
            state_bytes = state_path.read_bytes()
            state = json.loads(state_bytes)
            require(state["phase"] == "terminal" and state["effect"] == "unknown", "durable unknown state missing")
            require(all(state.get(key) == first[key] for key in ("outcome", "reason", "effect", "release")),
                    "durable native outcome/reason/release disagrees with runner receipt")
            require(all(quiet(state[key]) for key in ("worker_pid", "publisher_pid")), "owned process not quiescent")
            marker_bytes, audit_bytes = fixture.marker.read_bytes(), audit.read_bytes()
            retry = fixture.result(fixture.launch(), 1)
            report["retry_receipt"] = retry
            require(retry["reason"] == "prior-launch-requires-explicit-reconciliation", "same attempt relaunched")
            require(fixture.marker.read_bytes() == marker_bytes and audit.read_bytes() == audit_bytes and
                    state_path.read_bytes() == state_bytes, "same attempt changed worker/record/durable state")
            after = installed.observe(fixture)
            report["after"] = after
            require(after == before_retry, "same attempt changed independent native observations")
            records = [json.loads(line) for line in audit.read_text().splitlines() if line]
            actual_records = [item for item in records if item["record"]]
            require(len(actual_records) == 1 and actual_records[0]["native_exit"] == 0 and
                    actual_records[0]["acknowledgment_withheld"] is True, "exactly one lost native ACK required")
            report["native_relay_receipts"] = records
            # The native child inherits publisher PGID; that group was checked above.
            report["native_ledger_check"] = native_read(bun, orch, fixture, ["ledger", "check", "42", fixture.spec["head_oid"]])
            check = report["native_ledger_check"]
            require(check["exit"] == 0 and check["stdout"].strip() == "unit-test-verified", "native check disagrees")
        report["native_summary"] = native_read(bun, orch, fixture, ["ledger", "summary"])
        require(report["native_summary"]["exit"] == 0, "native summary failed")
        require(report["after"]["active_claims"] == 0, "active claim after scenario")
        report.update(ok=True, status="expectations-satisfied")
    except Exception as error:
        report["error"] = str(error)
    finally:
        # Keep all evidence before frozen fixture cleanup removes its private temp tree.
        try:
            if hasattr(fixture, "cfg"):
                snapshot(fixture, destination)
        except Exception as error:
            report.update(ok=False, status="evidencefailure", evidence_error=str(error))
        try:
            cleanup_ok = fixture.doCleanups()
            report["cleanup_ok"] = cleanup_ok
            if cleanup_ok is not True:
                report.update(ok=False, status="cleanupfailed", cleanup_error="frozen fixture cleanup returned failure")
        except Exception as error:
            report.update(ok=False, status="cleanupfailed", cleanup_ok=False, cleanup_error=str(error))
        (destination / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    begin = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    require(sys.platform == "linux" and sys.version_info >= (3, 10), "separately admitted GCP Linux Python >=3.10 only")
    require(sys.dont_write_bytecode, "launch with PYTHONDONTWRITEBYTECODE=1 to preserve exact clean sources")
    plan = validate_plan(json.loads(args.plan.read_text()))
    environment = clean_environment(os.environ)
    os.environ.clear()
    os.environ.update(environment)
    packet, pstack, owner = (Path(plan[key]).resolve(strict=True) for key in ("packet", "pstack", "owner"))
    require(Path(__file__).resolve() == packet / "workflow/native_pstack_cases.py", "packet source binding mismatch")
    sys.path.insert(0, str(packet / "validation"))
    from common import bootstrap_ready, clean_pin, digest
    supervisor = load_module("retained_native_supervision", packet / "validation/run.py")
    require(sorted(os.sched_getaffinity(0)) == sorted(plan["admitted_cpus"]), "admitted CPU affinity mismatch")
    containment = supervisor.Containment(Path(plan["exclusive_existing_cgroup"]))
    require(all(not left.is_relative_to(right) for left in (packet, pstack, owner)
                for right in (packet, pstack, owner) if left != right) and len({packet, pstack, owner}) == 3,
            "separate source trees required")
    for tool in ("bash", "git", "sqlite3"):
        require(shutil.which(tool) is not None, "missing preprovisioned dependency: " + tool)
    machine_id = Path("/etc/machine-id").read_text().strip()
    require(re.fullmatch(r"[0-9a-f]{32}", machine_id) and int(machine_id, 16) > 0, "initialized Linux machine identity required")
    for path, pin in ((packet, plan["packet_commit"]), (pstack, plan["pstack_commit"]), (owner, plan["owner_commit"])):
        clean_pin(path, pin, deadline=begin + plan["max_wall_seconds"] - 30)
    bun = Path(plan["bun"]).resolve(strict=True)
    require(digest(bun) == plan["bun_sha256"], "Bun digest mismatch")
    bootstrap = bootstrap_ready(pstack, bun)
    evidence = Path(plan["evidence"]).resolve()
    require(not evidence.exists() and all(not evidence.is_relative_to(path) and not path.is_relative_to(evidence)
                                        for path in (packet, pstack, owner)),
            "unique evidence outside actual source trees required")
    evidence.mkdir(mode=0o700, parents=True)
    os.environ.update(OSB_TEST_OWNER_SOURCE=str(owner), OSB_TEST_OWNER_COMMIT=plan["owner_commit"],
                      OSB_NATIVE_TEST_RELAY="admitted-gcp-only")
    tests = pstack / "pstack/skills/osb-coordination/tests"
    sys.path.insert(0, str(tests))
    module = load_module("native_pstack_lifecycle", tests / "lifecycle.py")
    require(Path(module.acceptance.__file__).resolve() == tests / "acceptance.py", "fixture import binding mismatch")
    installed = load_module("retained_installed_pstack", packet / "validation/installed_pstack.py")
    orch = pstack / "pstack/skills/poteto-mode/scripts/orch/orch.ts"
    relay = packet / "workflow/native_orch_receipt_loss.py"
    results, job_error = [], None
    try:
        for name in CASES:
            require(time.monotonic() - begin < plan["max_wall_seconds"] - 30, "supervisor cleanup reserve reached")
            results.append(run_case(module, installed, bun, orch, relay, name, evidence))
            require(containment.quiet(), "native fixture descendants not quiescent")
        for path, pin in ((packet, plan["packet_commit"]), (pstack, plan["pstack_commit"]), (owner, plan["owner_commit"])):
            clean_pin(path, pin, deadline=begin + plan["max_wall_seconds"] - 30)
    except Exception as error:
        job_error = str(error)
    finally:
        try:
            contained_quiet = containment.settle()
        except Exception as error:
            contained_quiet = False
            job_error = (job_error + "; " if job_error else "") + "containment settlement: " + str(error)
    report = {"contract": plan["contract"], "ok": job_error is None and contained_quiet and
              len(results) == len(CASES) and all(item["ok"] for item in results), "results": results,
              "job_error": job_error, "contained_quiet": contained_quiet,
              "bindings": plan, "bootstrap": bootstrap, "elapsed_seconds": time.monotonic() - begin,
              "relay_sha256": digest(relay), "orch_sha256": digest(orch),
              "qualification": "two native local cases only; unknown-effect case proves independent native observation and same-attempt replay refusal, not completed explicit operator reconciliation; no live transport, forge, atomic fence or harness certification"}
    (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"ok": report["ok"], "report": str(evidence / "report.json")}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
