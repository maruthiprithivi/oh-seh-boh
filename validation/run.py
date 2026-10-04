"""Serial, bounded offline validation; execute only after supervisor admission."""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time

from common import bootstrap_ready, clean_pin, digest, require, write_json

ROOT = Path(__file__).resolve().parent


class Containment:
    """Read an existing exclusive supervisor cgroup; never create/move members."""
    def __init__(self, path):
        base = Path("/sys/fs/cgroup").resolve(strict=True)
        require(path.is_absolute(), "absolute supervisor cgroup required")
        self.path = path.resolve(strict=True)
        require(self.path != base and self.path.is_relative_to(base), "existing non-root cgroup required")
        require(not os.access(self.path, os.W_OK) and not os.access(self.path / "cgroup.procs", os.W_OK), "supervisor-owned nondelegated cgroup required")
        require(hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"), "Linux pidfd settlement required")
        require(self.pids() == {os.getpid()}, "cgroup must exclusively contain this admitted job at start")
        relative = "/" + str(self.path.relative_to(base))
        self.membership = "0::" + relative
        require(self.membership in Path("/proc/self/cgroup").read_text().splitlines(), "job not in admitted cgroup")

    def pids(self):
        require(not any(path.is_dir() for path in self.path.iterdir()), "leaf containment required; child cgroup needs supervisor reconciliation")
        return {int(value) for value in (self.path / "cgroup.procs").read_text().split()}

    def quiet(self):
        return self.pids() <= {os.getpid()}

    def settle(self):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in self.pids() - {os.getpid()}:
                try:
                    descriptor = os.pidfd_open(pid)
                    try:
                        require(self.membership in Path(f"/proc/{pid}/cgroup").read_text().splitlines(), "process left admitted containment; supervisor reconciliation required")
                        signal.pidfd_send_signal(descriptor, sig)
                    finally:
                        os.close(descriptor)
                except ProcessLookupError:
                    pass
                except FileNotFoundError:
                    pass
            deadline = time.monotonic() + 5
            while not self.quiet() and time.monotonic() < deadline:
                time.sleep(0.1)
            if self.quiet():
                return True
        return self.quiet()


def quiet(process):
    try:
        os.killpg(process.pid, 0)
        return False
    except ProcessLookupError:
        return True


def stop(process):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not quiet(process):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            continue
        deadline = time.monotonic() + 5
        while not quiet(process) and time.monotonic() < deadline:
            time.sleep(0.1)
        if quiet(process):
            return True
    return quiet(process)


def run(plan_path):
    started = time.monotonic()
    plan = json.loads(plan_path.read_text())
    require(plan.get("contract") == "osb.validation-job.v1" and plan.get("authorized_disposable_linux") is True, "explicit admitted job required")
    require(sys.platform == "linux" and sys.version_info >= (3, 10), "Linux Python >=3.10 required")
    admitted = plan.get("admitted_cpus")
    require(isinstance(admitted, list) and 1 <= len(admitted) <= 2 and all(type(cpu) is int and cpu >= 0 for cpu in admitted), "supervisor must specify 1..2 admitted CPU IDs")
    affinity = sorted(os.sched_getaffinity(0))
    require(affinity == sorted(set(admitted)), "run through supervisor's existing admitted CPU affinity")
    require(type(plan.get("max_wall_seconds")) is int and 60 <= plan["max_wall_seconds"] <= 3600, "bounded <=one-hour job required")
    deadline = started + plan["max_wall_seconds"]
    containment = Containment(Path(plan["exclusive_existing_cgroup"]))
    roots = {name: Path(plan[name]).resolve(strict=True) for name in ("source", "pstack", "owner")}
    require(all(Path(plan[name]).is_absolute() for name in roots), "absolute source roots required")
    require(all(not left.is_relative_to(right) for name, left in roots.items() for other, right in roots.items() if name != other), "separate source roots required")
    for name, path in roots.items():
        clean_pin(path, plan[name + "_commit"], deadline=deadline - 30)
    for tool in ("bash", "git", "sqlite3"):
        require(shutil.which(tool) is not None, "missing preprovisioned dependency: " + tool)
    machine_id = Path("/etc/machine-id").read_text().strip()
    require(len(machine_id) == 32 and int(machine_id, 16) > 0, "initialized Linux machine identity required")
    bun, owner_job = Path(plan["bun"]), Path(plan["owner_job"])
    require(owner_job.is_absolute() and owner_job.is_file() and digest(owner_job) == plan["owner_job_sha256"], "reviewed owner job SHA mismatch")
    bootstrap = bootstrap_ready(roots["pstack"], bun)
    evidence = Path(plan["evidence"])
    require(evidence.is_absolute() and not evidence.exists(), "new evidence directory required")
    require(not any(evidence.resolve().is_relative_to(path) or path.is_relative_to(evidence.resolve()) for path in [*roots.values(), ROOT]), "evidence must be outside all source/job trees")
    load = plan["load"]
    require(type(load["agents"]) is int and 2 <= load["agents"] <= 16, "bounded 2..16 profile agents required")
    require(type(load["attempts_per_agent"]) is int and 1 <= load["attempts_per_agent"] <= 1000 and load["agents"] * load["attempts_per_agent"] <= 16000, "bounded profile attempts required")
    require(type(load["seconds"]) is int and 1 <= load["seconds"] <= 60, "short profile <=60 seconds required")
    require(all(type(load[key]) in (int, float) and load[key] > 0 for key in ("min_ops_per_second", "max_p99_seconds", "min_fairness")) and load["min_fairness"] <= 1, "predeclared positive acceptance thresholds required")
    os.umask(0o077)
    evidence.mkdir(mode=0o700, parents=True)
    environment = {key: value for key, value in os.environ.items() if key not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_REPO", "FM_HOME", "FM_COORD_CONFIG", "FM_COORD_AUTHORITY_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
    environment.update(OSB_TEST_OWNER_SOURCE=str(roots["owner"]), OSB_TEST_OWNER_COMMIT=plan["owner_commit"], PYTHONPYCACHEPREFIX=str(evidence / "pycache"))
    os.nice(10)
    steps, cancelled = [], False
    report = {"contract": "osb.validation-evidence.v1", "status": "running", "pins": {name: plan[name + "_commit"] for name in roots},
        "plan_sha256": digest(plan_path), "job_sources": {path.name: digest(path) for path in ROOT.glob("*.py")},
        "environment": {"platform": platform.platform(), "python": sys.version, "affinity": affinity, "containment": str(containment.path), "bootstrap": bootstrap},
        "load_thresholds": load, "steps": steps, "qualification": "bounded source/real-local-store evidence only; no production or deployed transport certification"}
    write_json(evidence / "report.json", report)

    def cancel(_signum, _frame):
        nonlocal cancelled
        cancelled = True

    handlers = {sig: signal.signal(sig, cancel) for sig in (signal.SIGTERM, signal.SIGINT)}

    def step(name, command, timeout=600):
        require(not cancelled, "job cancelled")
        remaining = deadline - time.monotonic() - 30
        require(remaining > 1, "job wall budget exhausted")
        began = time.monotonic()
        item = {"name": name, "argv": [str(arg) for arg in command], "status": "running"}
        steps.append(item)
        write_json(evidence / "report.json", report)
        process = None
        try:
            with (evidence / (name + ".stdout")).open("xb") as stdout, (evidence / (name + ".stderr")).open("xb") as stderr:
                process = subprocess.Popen(item["argv"], cwd=roots["source"], env=environment, stdout=stdout, stderr=stderr, start_new_session=True)
                end = time.monotonic() + min(timeout, remaining)
                while process.poll() is None:
                    require(not cancelled and time.monotonic() < end, "cancelled-or-stage-timeout")
                    try:
                        process.wait(timeout=0.25)
                    except subprocess.TimeoutExpired:
                        pass
            item["exit_code"] = process.returncode
            require(process.returncode == 0, "stage failed: " + name)
            require(quiet(process), "stage descendants remain: " + name)
            require(containment.quiet(), "nested stage processes remain in admitted containment: " + name)
            item["status"] = "pass"
        finally:
            try:
                if process is not None:
                    group_quiet = False
                    try:
                        group_quiet = stop(process)
                    finally:
                        contained_quiet = containment.settle()
                    require(group_quiet and contained_quiet, "owned stage or nested groups did not quiesce")
            except (ValueError, OSError):
                item["status"] = "cleanup-failed"
                raise
            finally:
                item["wall_seconds"] = time.monotonic() - began
                if item["status"] == "running":
                    item["status"] = "cancelled" if cancelled else "failure-or-timeout"
                write_json(evidence / "report.json", report)

    try:
        tests = roots["pstack"] / "pstack/skills/osb-coordination/tests"
        step("client-five", [sys.executable, tests / "acceptance.py"])
        step("lifecycle-ten", [sys.executable, tests / "lifecycle.py"])
        installed = [sys.executable, ROOT / "installed_pstack.py", "--pstack", roots["pstack"], "--pstack-commit", plan["pstack_commit"], "--bun", bun]
        step("installed-pstack", [*installed, "--evidence", evidence / "installed"])
        for mutation in ("skip-store-gate", "skip-publication-checkpoint"):
            step(mutation, [*installed, "--evidence", evidence / mutation, "--mutation", mutation])
        step("owner-validation", ["bash", owner_job, roots["owner"], evidence / "owner"], timeout=max(1, deadline - time.monotonic()))
        step("reference-scenarios", [sys.executable, roots["source"] / "lab/scenarios.py"])
        step("reference-ci", [sys.executable, roots["source"] / "lab/ci_scenarios.py"])
        step("oracle-controls", [sys.executable, ROOT / "oracle.py", "--self-test"])
        for profile in ("independent", "contention", "saturation", "soak"):
            result, snapshot = evidence / (profile + ".json"), evidence / (profile + "-snapshot.json")
            step("profile-" + profile, [sys.executable, ROOT / "reference_profile.py", "--source", roots["source"], "--snapshot", snapshot,
                "--test-only", "--profile", profile, "--agents", str(load["agents"]), "--operations-per-agent", str(load["attempts_per_agent"]),
                "--seconds", str(load["seconds"]), "--max-pending", "50" if profile == "saturation" else "100000", "--output", result])
            step("oracle-" + profile, [sys.executable, ROOT / "oracle.py", "--snapshot", snapshot])
            measured = json.loads(result.read_text())
            require(measured["worker_count_returned"] == load["agents"] and not measured["missing_workers"], "profile worker evidence incomplete")
            require(measured["throughput_ops_per_second"] >= load["min_ops_per_second"] and measured["latency_seconds"]["p99"] <= load["max_p99_seconds"], "predeclared throughput/latency floor missed")
            if profile in ("independent", "contention"):
                require(measured["jain_fairness_successful_claims"] >= load["min_fairness"], "predeclared fairness floor missed")
        for name, path in roots.items():
            clean_pin(path, plan[name + "_commit"], deadline=deadline - 30)
        require(not cancelled and time.monotonic() <= deadline, "job cancelled or wall budget exceeded")
        report["status"] = "pass-bounded-validation"
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as error:
        report["status"] = "cancelled" if cancelled else "failed-or-incomplete"
        report["reason"] = str(error)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        report["wall_seconds"] = time.monotonic() - started
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        report["child_cpu_seconds"] = usage.ru_utime + usage.ru_stime
        report["max_child_rss_kib_linux"] = usage.ru_maxrss
        write_json(evidence / "report.json", report)
    print(json.dumps({"status": report["status"], "report": str(evidence / "report.json")}))
    return 0 if report["status"] == "pass-bounded-validation" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    try:
        return run(args.plan)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "setupfailed", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
