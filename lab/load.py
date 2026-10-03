"""Process-based burst/soak/saturation profiles; source only until allocation."""
import argparse
from collections import Counter
import json
import multiprocessing as mp
from pathlib import Path
import queue
import random
import resource
import sqlite3
import tempfile
import time
import uuid

from backend import Engine, PROTOCOL, overlaps
from scenarios import BASE, HEAD, Fixture

HARNESSES = ["omp", "claude-code", "codex", "opencode", "cursor", "agy", "kiro-cli", "kimi", "kiro"]


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))] if ordered else None


def worker(db, actor, identity, barrier, output, count, mode, deadline, seed):
    engine = Engine(db)
    rng = random.Random(seed)
    latencies, waits, reasons, receipts, wins, retries = [], [], Counter(), [], 0, 0
    barrier.wait(timeout=20)

    def call(operation, extra):
        nonlocal retries
        payload = {**identity, "base": BASE, "head": HEAD, "request_id": str(uuid.uuid4()), **extra}
        request = {"protocol": PROTOCOL, "operation": operation, "payload": payload}
        start = time.perf_counter()
        response = engine.execute(actor, request)
        for attempt in range(2):
            if response.get("reason") != "busy":
                break
            retries += 1
            time.sleep(rng.uniform(0.005, 0.025) * (attempt + 1))
            response = engine.execute(actor, request)
        latencies.append(time.perf_counter() - start)
        reasons["ok" if response.get("ok") else response.get("reason", "unknown")] += 1
        if response.get("ok"):
            receipts.append(payload["request_id"])
        return response

    for index in range(count):
        if time.monotonic() >= deadline:
            break
        task = actor + "-" + str(index)
        resources = [{"type": "directory", "name": "src/shared"}] if mode != "independent" else [
            {"type": "file", "name": "src/" + actor + "/" + str(index)}]
        if not call("intent", {"task": task, "resources": resources}).get("ok"):
            continue
        queue_start = time.perf_counter()
        grant = call("claim", {"task": task, "expected_version": 1})
        if not grant.get("ok"):
            continue
        waits.append(time.perf_counter() - queue_start)
        wins += 1
        time.sleep(rng.uniform(0.001, 0.004))
        write = call("protected-write", {"task": task, "fence": grant["fence"], "content": {"simulated_diff": task}})
        if not write.get("ok"):
            reasons["protected-effect-failed"] += 1
        call("release", {"task": task, "fence": grant["fence"]})
    usage = resource.getrusage(resource.RUSAGE_SELF)
    output.put({"actor": actor, "harness_label": HARNESSES[seed % len(HARNESSES)],
                "simulated": True, "wins": wins, "latencies": latencies, "waits": waits,
                "reasons": dict(reasons), "receipts": receipts, "busy_retries": retries,
                "cpu_seconds": usage.ru_utime + usage.ru_stime, "max_rss_kib_linux": usage.ru_maxrss})


def inspect_invariants(db, results):
    violations = []
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        keys = {row[0] for row in connection.execute("SELECT key FROM requests")}
        acknowledged = {key for result in results for key in result["receipts"]}
        lost = len(acknowledged - keys)
        if lost:
            violations.append("lost-acknowledged-transitions")
        holders = {}
        double, unauthorized = 0, 0
        for event in connection.execute("SELECT * FROM events ORDER BY seq"):
            p = json.loads(event["payload"])
            now = p.get("clock_ms", 0)
            holders = {k: v for k, v in holders.items() if v["expires_ms"] > now}
            task_key = (event["scope"], p.get("task"))
            if event["kind"] == "claim":
                for key, held in holders.items():
                    if key[0] == task_key[0] and overlaps(held["resources"], p["result"]["resources"]):
                        double += 1
                holders[task_key] = {**p["result"], "actor": p["actor"]}
            elif event["kind"] in ("release", "complete"):
                holders.pop(task_key, None)
            elif event["kind"] in ("revoke", "session"):
                removed = p.get("target") if event["kind"] == "revoke" else p.get("actor")
                holders = {k: v for k, v in holders.items() if not (k[0] == event["scope"] and v["actor"] == removed)}
            elif event["kind"] == "recovery":
                holders.clear()
            elif event["kind"] == "protected-write":
                held = holders.get(task_key)
                if not held or held["actor"] != p["actor"] or held["fence"] != p["fence"]:
                    unauthorized += 1
        if double:
            violations.append("double-ownership")
        if unauthorized:
            violations.append("unauthorized-protected-write")
        writes = connection.execute("SELECT count(*) FROM protected_writes").fetchone()[0]
        protected_failures = sum(r["reasons"].get("protected-effect-failed", 0) for r in results)
    return {"double_ownership": double, "lost_acknowledged_transitions": lost,
            "protected_writes": writes, "protected_effect_failures": protected_failures,
            "unauthorized_protected_writes": unauthorized,
            "unauthorized_write_rejection": "adversarial rejections measured separately in scenarios.py",
            "violations": violations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("independent", "contention", "saturation", "soak"), default="contention")
    parser.add_argument("--agents", type=int, default=8)
    parser.add_argument("--operations-per-agent", type=int, default=30)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--max-pending", type=int, default=10000)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--test-only", required=True, action="store_true")
    args = parser.parse_args()
    if not 2 <= args.agents <= 64 or not 1 <= args.seconds <= 3600 or not 1 <= args.operations_per_agent or args.agents * args.operations_per_agent > 20000:
        parser.error("bounded profiles require 2..64 agents, <=3600 seconds and <=20000 total task attempts")
    if args.output.exists():
        parser.error("output already exists; evidence is never overwritten")
    if not 1 <= args.max_pending <= 100000:
        parser.error("pending ceiling must be 1..100000")
    with tempfile.TemporaryDirectory(prefix="osb-load-") as root:
        actors = {"alice": "admin", **{"agent-" + str(i): "writer" for i in range(args.agents)}}
        fixture = Fixture(root, args.max_pending, actors)
        context = mp.get_context("spawn")
        barrier, output = context.Barrier(args.agents), context.Queue()
        started = time.monotonic()
        deadline = started + args.seconds
        processes = [context.Process(target=worker, args=(fixture.path, actor, fixture.identity[actor],
            barrier, output, args.operations_per_agent,
            "independent" if args.profile == "independent" else "contention", deadline, index))
            for index, actor in enumerate(a for a in actors if a != "alice")]
        for process in processes:
            process.start()
        results, missing = [], []
        for _ in processes:
            try:
                results.append(output.get(timeout=max(1, deadline - time.monotonic()) + 10))
            except queue.Empty:
                break
        for index, process in enumerate(processes):
            process.join(2)
            if process.is_alive():
                process.terminate()
                process.join(2)
            if process.exitcode != 0:
                missing.append({"worker": index, "exit": process.exitcode})
        elapsed = time.monotonic() - started
        latencies = [value for r in results for value in r["latencies"]]
        waits = [value for r in results for value in r["waits"]]
        reasons = sum((Counter(r["reasons"]) for r in results), Counter())
        wins = [r["wins"] for r in results]
        denominator = len(wins) * sum(value * value for value in wins)
        invariants = inspect_invariants(fixture.path, results)
        report = {"protocol": PROTOCOL, "status": "measured-reference-lab-only",
            "real_harnesses_executed": [], "profile": vars(args) | {"output": str(args.output)},
            "wall_seconds": elapsed, "task_attempt_ceiling": args.agents * args.operations_per_agent,
            "operations": len(latencies), "throughput_ops_per_second": len(latencies) / elapsed,
            "latency_seconds": {"p50": percentile(latencies, .50), "p95": percentile(latencies, .95), "p99": percentile(latencies, .99)},
            "queue_wait_seconds": {"definition": "successful claim call elapsed, no fairness queue is implemented",
                "p50": percentile(waits, .50), "p95": percentile(waits, .95), "p99": percentile(waits, .99)},
            "jain_fairness_successful_claims": sum(wins) ** 2 / denominator if denominator else 0,
            "claims_per_actor": {r["actor"]: r["wins"] for r in results}, "outcomes": dict(reasons),
            "busy_retries": sum(r["busy_retries"] for r in results),
            "cpu_seconds": sum(r["cpu_seconds"] for r in results),
            "max_worker_rss_kib_linux": max((r["max_rss_kib_linux"] for r in results), default=0),
            "database_bytes": fixture.path.stat().st_size, "journal_bytes": fixture.engine.journal.stat().st_size,
            "missing_workers": missing, "worker_count_returned": len(results), "invariants": invariants,
            "qualification": "short synthetic profile; not production capacity, prolonged soak, deployed auth or agent compatibility proof"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"report": str(args.output), "operations": len(latencies), "violations": invariants["violations"], "missing_workers": missing}))
        return 1 if invariants["violations"] or missing or len(results) != len(processes) or not latencies or not sum(wins) else 0


if __name__ == "__main__":
    raise SystemExit(main())
