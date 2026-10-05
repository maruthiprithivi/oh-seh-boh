"""Pure, advisory admission for an optional workflow package.

No clock, I/O, claims, spawning, or grants. A caller must revalidate the snapshot
and atomically claim through the existing authority transaction/CAS and resource
guard before dispatch. Candidate selection alone conveys no authority.

Tasks have exactly the keys in TASK_FIELDS; higher integer priority wins. Costs
and capacity specify all three named resources. Scope keys are relative,
slash-separated resource names or opaque names; exact and ancestor overlaps
conflict. Projects are isolated; one evaluation admits only one repository.
Completed dependency revisions must match exactly, including epic revisions.
Verification criteria are declarations, not runtime evidence of endpoint health.
"""
from copy import deepcopy
import re


RESOURCES = frozenset({"cpu", "memory_mb", "ci_slots"})
TASK_FIELDS = frozenset({"project", "repo_id", "id", "revision", "base", "head",
                         "state", "ready", "dependencies", "costs", "priority"})
READY_FIELDS = frozenset({"scope", "acceptance", "verification", "integration_owner"})
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _texts(value):
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)


def _id(value):
    return isinstance(value, str) and bool(ID.fullmatch(value))


def _resources(value):
    return isinstance(value, dict) and set(value) == RESOURCES and all(
        _integer(amount) for amount in value.values())


def _scope(key):
    if not _text(key) or key != key.strip() or key.startswith("/") or "\\" in key:
        return False
    parts = key.rstrip("/").split("/")
    return all(part and part not in {".", ".."} for part in parts)


def _task(value):
    if not isinstance(value, dict) or set(value) != TASK_FIELDS:
        return False
    if not all(_id(value[key]) for key in ("project", "id")):
        return False
    if not isinstance(value["repo_id"], str) or not value["repo_id"].isdigit():
        return False
    if not all(isinstance(value[key], str) and OID.fullmatch(value[key]) for key in ("base", "head")):
        return False
    if not _integer(value["revision"], 1) or type(value["priority"]) is not int:
        return False
    if not _text(value["state"]) or value["state"] not in {"ready", "running", "completed", "blocked"}:
        return False
    ready = value["ready"]
    if not isinstance(ready, dict) or set(ready) != READY_FIELDS:
        return False
    if not all(_texts(ready[key]) for key in ("scope", "acceptance", "verification")):
        return False
    if not _text(ready["integration_owner"]) or not all(_scope(key) for key in ready["scope"]):
        return False
    dependencies = value["dependencies"]
    if not isinstance(dependencies, list):
        return False
    seen = set()
    for dependency in dependencies:
        if (not isinstance(dependency, dict) or set(dependency) != {"task", "revision"}
                or not _id(dependency["task"]) or not _integer(dependency["revision"], 1)
                or dependency["task"] in seen):
            return False
        seen.add(dependency["task"])
    return _resources(value["costs"])


def _identifier(value):
    return value.get("id", "<invalid>") if isinstance(value, dict) and _text(value.get("id")) else "<invalid>"


def _overlap(left, right):
    left, right = left.rstrip("/"), right.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _cyclic_dependencies(tasks):
    """Iterative elimination also marks children blocked by a dependency cycle."""
    remaining = set(tasks)
    edges = {identifier: {dep["task"] for dep in value["dependencies"] if dep["task"] in tasks}
             for identifier, value in tasks.items()}
    removable = [identifier for identifier in remaining if not edges[identifier]]
    while removable:
        removed = set(removable)
        remaining.difference_update(removed)
        for identifier in remaining:
            edges[identifier].difference_update(removed)
        removable = [identifier for identifier in remaining if not edges[identifier]]
    return remaining


def evaluate(backlog, capacity, active, landing, expected_project):
    """Return deterministic ``candidates`` and ``refusals`` from a snapshot.

    Every selected task reserves one landing slot in this advisory result. Active
    tasks consume capacity and scopes; landing.pending must include all existing
    work already reserved for landing. Refusals sort by priority then task ID;
    malformed tasks use priority zero and a safe identifier. Input is untouched.
    """
    refusals, candidates = [], []

    def refuse(value, reason):
        priority = value.get("priority", 0) if isinstance(value, dict) else 0
        refusals.append((priority if type(priority) is int else 0, _identifier(value), reason))

    def finish():
        return {"candidates": deepcopy(candidates), "refusals": [
            {"id": identifier, "reason": reason}
            for _, identifier, reason in sorted(refusals, key=lambda item: (-item[0], item[1], item[2]))]}

    if not isinstance(backlog, list):
        refuse(None, "invalid_context")
        return finish()
    context_valid = (_id(expected_project) and _resources(capacity) and isinstance(active, list)
                     and all(_task(item) and item["project"] == expected_project for item in active)
                     and isinstance(landing, dict) and set(landing) == {"limit", "pending"}
                     and all(_integer(landing[key]) for key in ("limit", "pending")))
    if not context_valid:
        for value in backlog:
            refuse(value, "invalid_context")
        return finish()

    valid = []
    malformed = False
    for value in backlog:
        if not _task(value):
            refuse(value, "malformed_task")
            malformed = True
        elif value["project"] != expected_project:
            refuse(value, "project_mismatch")
        else:
            valid.append(value)
    # An omitted malformed entry could hide held scope, costs, or a newer
    # dependency revision. No neighboring task can be safely recommended.
    if malformed:
        for value in valid:
            refuse(value, "invalid_snapshot")
        return finish()
    grouped = {}
    for value in valid:
        grouped.setdefault(value["id"], []).append(value)
    tasks = {}
    for identifier, values in grouped.items():
        if len(values) > 1:
            newest = max(value["revision"] for value in values)
            for value in values:
                refuse(value, "stale_revision" if value["revision"] < newest else "ambiguous_task")
        else:
            tasks[identifier] = values[0]
    ready = sorted((value for value in tasks.values() if value["state"] == "ready"),
                   key=lambda value: (-value["priority"], value["id"]))
    repositories = {value["repo_id"] for value in valid + active}
    active_ids = {value["id"] for value in active}
    if len(active_ids) != len(active) or any(value["state"] != "running" for value in active):
        for value in ready:
            refuse(value, "invalid_context")
        return finish()
    if len(repositories) > 1:
        for value in ready:
            refuse(value, "repository_mix")
        return finish()
    cycles = _cyclic_dependencies(tasks)
    used = {key: sum(value["costs"][key] for value in active) for key in RESOURCES}
    scopes = [key for value in active for key in value["ready"]["scope"]]
    active_by_id = {value["id"]: value for value in active}
    for value in ready:
        identifier = value["id"]
        reason = None
        if identifier in active_by_id:
            reason = ("stale_revision" if value["revision"] != active_by_id[identifier]["revision"]
                      else "already_active")
        elif identifier in cycles:
            reason = "dependency_cycle"
        else:
            for dependency in sorted(value["dependencies"], key=lambda item: item["task"]):
                completed = tasks.get(dependency["task"])
                if completed is None:
                    reason = "dependency_missing"
                elif completed["revision"] != dependency["revision"]:
                    reason = "dependency_revision_changed"
                elif completed["state"] != "completed":
                    reason = "dependency_incomplete"
                if reason:
                    break
        if reason is None and landing["pending"] + len(candidates) >= landing["limit"]:
            reason = "landing_backpressure"
        if reason is None and any(_overlap(key, held) for key in value["ready"]["scope"] for held in scopes):
            reason = "resource_conflict"
        if reason is None and any(used[key] + value["costs"][key] > capacity[key] for key in RESOURCES):
            reason = "capacity_exhausted"
        if reason:
            refuse(value, reason)
        else:
            candidates.append(value)
            scopes.extend(value["ready"]["scope"])
            for key in RESOURCES:
                used[key] += value["costs"][key]
    return finish()
