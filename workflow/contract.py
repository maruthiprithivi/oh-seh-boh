"""Optional factory policy, not claim authority or a process controller.

Every snapshot is supplied by a separately reviewed authenticated adapter.
No model-selected command, network request, spawn, credential or clock here.
"""
import hashlib
import json
import re

PROTOCOL = "osb.factory.intent.v1"
DISPATCHERS = {"firstmate", "claude-code", "codex", "omp", "opencode"}
PROFILES = {"transactional", "github-cas-cooperative"}
OPERATIONS = {"claim", "dispatch", "review", "fix", "verify", "landing",
              "release", "reconcile", "update-backlog", "handoff-accept"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class Refusal(ValueError): pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def positive(value):
    return type(value) is int and value > 0


def identifier(value):
    return isinstance(value, str) and bool(ID.fullmatch(value))


def check_config(c):
    if not isinstance(c, dict) or set(c) != {"project", "repo_id", "principal", "acl", "authority", "run"}:
        raise Refusal("configuration-fields")
    if not all(identifier(c[k]) for k in ("project", "principal")) or not isinstance(c["repo_id"], str) or not c["repo_id"].isdigit():
        raise Refusal("configuration-identity")
    acl = c["acl"]
    if (not isinstance(acl, dict) or not all(identifier(k) and isinstance(v, list)
            and all(identifier(p) for p in v) and len(set(v)) == len(v) for k, v in acl.items())
            or c["project"] not in acl.get(c["principal"], [])):
        raise Refusal("project-acl")
    a, r = c["authority"], c["run"]
    if not isinstance(a, dict) or set(a) != {"profile", "id", "epoch"} or a["profile"] not in PROFILES or not identifier(a["id"]) or not positive(a["epoch"]):
        raise Refusal("authority-binding")
    if not isinstance(r, dict) or set(r) != {"id", "dispatcher"} or not identifier(r["id"]) or r["dispatcher"] not in DISPATCHERS:
        raise Refusal("single-dispatcher-binding")


def check_task(t):
    if not isinstance(t, dict) or set(t) != {"id", "revision", "base", "head"} or not identifier(t["id"]) or not positive(t["revision"]):
        raise Refusal("task-binding")
    if not all(isinstance(t[k], str) and OID.fullmatch(t[k]) for k in ("base", "head")):
        raise Refusal("revision-binding")


def envelope(config, task, operation, payload):
    check_config(config); check_task(task)
    if operation not in OPERATIONS or not isinstance(payload, dict): raise Refusal("operation")
    # Key scopes one immutable intent; altered bytes with this key must conflict in journal/authority.
    key_material = [config["project"], config["repo_id"], config["authority"],
                    config["run"], config["principal"], task, operation]
    if operation == "handoff-accept":
        if not identifier(payload.get("offer_id")): raise Refusal("authority-approved-offer-id-required")
        key_material.append(payload["offer_id"])
    key = hashlib.sha256(canonical(key_material).encode()).hexdigest()
    result = {"protocol": PROTOCOL, "project": config["project"], "repo_id": config["repo_id"],
              "principal": config["principal"], "authority": dict(config["authority"]),
              "run": dict(config["run"]), "task": dict(task), "operation": operation,
              "key": key, "payload": json.loads(canonical(payload))}
    if len(canonical(result).encode()) > 65536: raise Refusal("envelope-limit")
    return result


def validate(value, config):
    if not isinstance(value, dict) or set(value) != {"protocol", "project", "repo_id", "principal", "authority", "run", "task", "operation", "key", "payload"}:
        raise Refusal("envelope-fields")
    expected = envelope(config, value["task"], value["operation"], value["payload"])
    if value != expected: raise Refusal("envelope-binding")
    return value


def next_action(config, task, state):
    """Return a single recommendation. An adapter must atomically revalidate before effects.

    This function never grants work or changes state. Snapshot contents are evidence
    only after live adapter authentication; a local JSON file cannot prove ownership.
    """
    check_config(config); check_task(task)
    if not isinstance(state, dict): raise Refusal("state-object")
    phase = state.get("phase")
    if phase in {"unknown", "reconcile"} or state.get("reconciled") is not True:
        return {"action": "reconcile", "reason": "uncertain-effect-or-state"}
    if (state.get("authority_id") != config["authority"]["id"]
            or state.get("epoch") != config["authority"]["epoch"]
            or any(state.get(k) != task[k] for k in ("revision", "base", "head"))):
        return {"action": "reconcile", "reason": "ownership-or-revision-changed"}
    if phase == "ready": return {"action": "claim"}
    if state.get("owned") is not True or state.get("owner") != config["principal"]:
        return {"action": "reconcile", "reason": "ownership-or-revision-changed"}
    claim = state.get("claim", {})
    if not isinstance(claim, dict) or not all(positive(claim.get(k)) for k in ("fence", "generation")):
        return {"action": "reconcile", "reason": "missing-current-claim"}
    if phase == "claim": return {"action": "dispatch", "dispatcher": config["run"]["dispatcher"]}
    if phase == "work": return {"action": "observe", "reason": "existing-dispatcher-owns-lifecycle"}
    if phase == "review":
        review = state.get("review", {})
        if (not isinstance(review, dict) or review.get("head") != task["head"]
                or review.get("verified_role") is not True or review.get("status") != "approved"):
            return {"action": "fix" if isinstance(review, dict) and review.get("status") == "changes-requested" else "review"}
        return {"action": "verify"}
    if phase == "verify":
        checks = state.get("required_checks")
        evidence = state.get("evidence")
        if (not isinstance(checks, list) or not checks or not all(identifier(k) for k in checks)
                or len(set(checks)) != len(checks) or not isinstance(evidence, list)):
            raise Refusal("verification-contract")
        current = [e for e in evidence if isinstance(e, dict) and
                   all(e.get(k) == task[k] for k in ("revision", "base", "head"))]
        if any(e.get("status") == "failure" and e.get("check") in checks for e in current):
            return {"action": "fix", "reason": "current-verification-failed"}
        missing = [k for k in checks if len([e for e in current if e.get("check") == k]) != 1
                   or not any(e.get("check") == k and e.get("status") == "pass" for e in current)]
        if missing: return {"action": "verify", "missing": missing}
        return {"action": "request-landing-review"}
    if phase == "landing":
        return {"action": "landing" if state.get("landing_authorized") is True else "await-landing-authorization"}
    if phase == "landed": return {"action": "release"}
    if phase == "released": return {"action": "update-backlog"}
    raise Refusal("unknown-workflow-phase")
