"""Independent observation oracle: no authority/client/overlap implementation import."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path

from common import require


def intersects(left, right):
    # Independent path-component comparison, deliberately not backend.overlaps.
    for a in left:
        for b in right:
            if a["type"] == "repository" or b["type"] == "repository":
                return True
            x, y = tuple(a["name"].split("/")), tuple(b["name"].split("/"))
            if x == y or (a["type"] == "directory" and y[:len(x)] == x) or (b["type"] == "directory" and x[:len(y)] == y):
                return True
    return False


def violations(snapshot):
    require(snapshot.get("contract") == "osb.reference-observation.v1", "observation contract required")
    failures, held, allowed, seen = [], {}, Counter(), Counter()
    last_fence = 0
    if {tuple(key) for key in snapshot["acknowledged_keys"]} - {tuple(key) for key in snapshot["request_keys"]}:
        failures.append("lost-acknowledged-transition")
    last_sequence = 0
    for event in snapshot["events"]:
        if event["seq"] <= last_sequence:
            failures.append("non-increasing-event-sequence")
        last_sequence = event["seq"]
        p = json.loads(event["payload"])
        now = p.get("clock_ms", 0)
        held = {key: value for key, value in held.items() if value["expires_ms"] > now}
        key = (event["scope"], p.get("task"))
        if event["kind"] == "claim":
            grant = p["result"]
            if grant["fence"] <= last_fence:
                failures.append("reused-or-regressed-fence")
            last_fence = grant["fence"]
            if any(other[0] == key[0] and intersects(value["resources"], grant["resources"]) for other, value in held.items()):
                failures.append("overlapping-live-grants")
            held[key] = {**grant, "actor": p["actor"]}
        elif event["kind"] in ("release", "complete"):
            current = held.get(key)
            if current is None or current["actor"] != p["actor"] or current["fence"] != p["fence"]:
                failures.append("invalid-release-event")
            held.pop(key, None)
        elif event["kind"] in ("session", "revoke"):
            actor = p.get("actor") if event["kind"] == "session" else p.get("target")
            held = {key: value for key, value in held.items() if not (key[0] == event["scope"] and value["actor"] == actor)}
        elif event["kind"] == "recovery":
            held.clear()
        elif event["kind"] == "protected-write":
            current = held.get(key)
            identity = (*key, p["actor"], p["fence"])
            if current is None or current["actor"] != p["actor"] or current["fence"] != p["fence"]:
                failures.append("stale-or-unauthorized-write-event")
            else:
                allowed[identity] += 1
    for row in snapshot["writes"]:
        identity = (row["scope"], row["task"], row["actor"], row["fence"])
        if identity not in allowed:
            failures.append("write-without-authorized-event")
        seen[identity] += 1
    if allowed - seen:
        failures.append("acknowledged-write-missing-from-sink")
    if seen - allowed:
        failures.append("duplicate-or-unacknowledged-sink-write")
    if held:
        failures.append("live-grant-left-after-profile")
    active_rows = [row for row in snapshot["current_claims"] if row["active"] and row["expires"] > snapshot["clock_ms"]]
    if active_rows:
        failures.append("live-db-claim-left-after-profile")
    return sorted(set(failures))


def self_test():
    def event(seq, kind, task, actor="alice", fence=1):
        return {"seq": seq, "scope": "fixture", "kind": kind, "payload": json.dumps({"task": task, "actor": actor,
            "fence": fence, "clock_ms": 0, "result": {"fence": fence, "expires_ms": 100, "resources": [{"type": "directory", "name": "src"}]}})}
    valid = {"contract": "osb.reference-observation.v1", "events": [event(1, "claim", "one"), event(2, "protected-write", "one"), event(3, "release", "one")],
        "request_keys": [["alice", "ack"]], "acknowledged_keys": [["alice", "ack"]], "clock_ms": 0, "current_claims": [],
        "writes": [{"scope": "fixture", "task": "one", "actor": "alice", "fence": 1, "head": "a" * 40}]}
    require(not violations(valid), "positive oracle control failed")
    bad = copy.deepcopy(valid)
    bad["events"].insert(1, event(2, "claim", "two", "bob", 2))
    require("overlapping-live-grants" in violations(bad), "double-grant negative control escaped")
    bad = copy.deepcopy(valid)
    bad["writes"][0]["actor"] = "mallory"
    require("write-without-authorized-event" in violations(bad), "forged-write negative control escaped")
    bad = copy.deepcopy(valid)
    bad["request_keys"] = []
    require("lost-acknowledged-transition" in violations(bad), "lost-ack negative control escaped")
    bad = copy.deepcopy(valid)
    bad["request_keys"] = [["bob", "ack"]]
    require("lost-acknowledged-transition" in violations(bad), "cross-actor acknowledgment substitution escaped")
    bad = copy.deepcopy(valid)
    bad["current_claims"] = [{"scope": "fixture", "task": "one", "actor": "alice", "fence": 1, "active": 1, "expires": 100}]
    require("live-db-claim-left-after-profile" in violations(bad), "release-event/DB-state divergence escaped")
    return {"positive": "accepted", "negative_controls": ["overlapping grants", "forged sink write", "lost acknowledgment"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test()))
        return 0
    require(args.snapshot is not None, "snapshot required")
    failures = violations(json.loads(args.snapshot.read_text()))
    print(json.dumps({"violations": failures, "qualification": "reference-only post-run observation; not deployed authority proof"}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
