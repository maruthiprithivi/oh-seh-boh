"""Delta checkpoint/offer policy over an existing authority, never document locks.

Inspired by BatonPass's compact handoff and receiver preflight. No plugin source
copied or installed. Every live snapshot/receipt below requires a reviewed owner
adapter; JSON dictionaries and digests are not authentication or permission.
"""
import hashlib
import json
from workflow.contract import Refusal, canonical, check_config, check_task, envelope, identifier, positive

PROTOCOL = "osb.factory.handoff.v1"


def _claim(c):
    if not isinstance(c, dict) or set(c) != {"epoch", "generation", "fence"} or not all(positive(v) for v in c.values()):
        raise Refusal("handoff-claim-binding")


def _hash(p):
    return hashlib.sha256(canonical({k: v for k, v in p.items() if k != "digest"}).encode()).hexdigest()


def checkpoint(config, task, claim, delta, *, mode, to=None, offer_id=None):
    check_config(config); check_task(task); _claim(claim)
    if claim["epoch"] != config["authority"]["epoch"] or mode not in {"pause", "offer"}:
        raise Refusal("handoff-mode-or-epoch")
    if mode == "pause":
        if to is not None and to != config["principal"]: raise Refusal("pause-does-not-transfer")
        if offer_id is not None: raise Refusal("pause-is-not-authority-offer")
        to = config["principal"]
    elif not identifier(to) or to == config["principal"] or not identifier(offer_id):
        raise Refusal("named-receiver-and-authority-approved-offer-required")
    if not isinstance(delta, dict) or set(delta) != {"worktree", "deviations", "environment", "verification", "risks", "next_action"}:
        raise Refusal("handoff-delta-fields")
    w = delta["worktree"]
    if (not isinstance(w, dict) or set(w) not in ({"locator", "branch", "head", "dirty"}, {"locator", "branch", "head", "dirty", "uncommitted"})
            or not isinstance(w.get("locator"), str) or not w["locator"] or len(w["locator"]) > 1024
            or not isinstance(w.get("branch"), str) or not w["branch"] or w.get("head") != task["head"]
            or type(w.get("dirty")) is not bool): raise Refusal("worktree-binding")
    if w["dirty"] and (not isinstance(w.get("uncommitted"), list) or not w["uncommitted"]
                       or not all(isinstance(x, str) and x for x in w["uncommitted"])):
        raise Refusal("explicit-uncommitted-state-required")
    for name in ("deviations", "environment", "risks"):
        if not isinstance(delta[name], list) or not all(isinstance(x, str) and x for x in delta[name]):
            raise Refusal("bounded-delta-list")
    if not isinstance(delta["next_action"], str) or not delta["next_action"]: raise Refusal("next-action-required")
    if not isinstance(delta["verification"], list): raise Refusal("verification-provenance")
    for v in delta["verification"]:
        if (not isinstance(v, dict) or set(v) != {"check", "status", "evidence_digest"} or not identifier(v["check"])
                or v["status"] not in {"pass", "failure", "unrun", "unknown"}): raise Refusal("verification-provenance")
        if v["status"] in {"pass", "failure"}:
            if not isinstance(v["evidence_digest"], str) or len(v["evidence_digest"]) != 64 or any(x not in "0123456789abcdef" for x in v["evidence_digest"]):
                raise Refusal("executed-result-needs-evidence")
        elif v["evidence_digest"] is not None: raise Refusal("unrun-is-not-executed-evidence")
    p = {"protocol": PROTOCOL, "mode": mode, "project": config["project"], "repo_id": config["repo_id"],
         "authority": dict(config["authority"]), "run": dict(config["run"]), "task": dict(task),
         "from": config["principal"], "to": to, "offer_id": offer_id, "claim": dict(claim), "delta": json.loads(canonical(delta))}
    p["digest"] = _hash(p)
    if len(canonical(p).encode()) > 16384: raise Refusal("handoff-delta-limit")
    return p


def _packet(config, p):
    check_config(config)
    if not isinstance(p, dict) or set(p) != {"protocol", "mode", "project", "repo_id", "authority", "run", "task", "from", "to", "offer_id", "claim", "delta", "digest"}:
        raise Refusal("handoff-packet-fields")
    if (p["protocol"] != PROTOCOL or p["mode"] != "offer" or p["to"] != config["principal"]
            or any(p[k] != config[k] for k in ("project", "repo_id", "authority", "run"))
            or p["digest"] != _hash(p)): raise Refusal("handoff-packet-binding")
    source = {**config, "principal": p["from"], "acl": {p["from"]: [p["project"]]}}
    # Revalidate the entire packet's schema without trusting sender ACL as auth.
    if checkpoint(source, p["task"], p["claim"], p["delta"], mode="offer", to=p["to"], offer_id=p["offer_id"]) != p:
        raise Refusal("handoff-packet-invalid")


def _preflight(config, p, s):
    _packet(config, p)
    if (not isinstance(s, dict) or s.get("reconciled") is not True
            or s.get("quiescence_verified") is not True or s.get("owner") != p["from"]
            or s.get("claim") != p["claim"] or s.get("task") != p["task"]
            or s.get("offer_digest") != p["digest"] or s.get("verified_delta_digest") != p["digest"]
            or s.get("offer_id") != p["offer_id"]
            or s.get("authority_id") != p["authority"]["id"] or s.get("epoch") != p["claim"]["epoch"]
            or s.get("project") != p["project"] or s.get("repo_id") != p["repo_id"]):
        raise Refusal("receiver-preflight-required")


def accept_intent(config, packet, receiver_preflight):
    """Prepare expected-capsule atomic acceptance intent, never transfer locally."""
    _preflight(config, packet, receiver_preflight)
    return envelope(config, packet["task"], "handoff-accept", {
        "offer_id": packet["offer_id"], "offer_digest": packet["digest"], "expected_owner": packet["from"],
        "expected_claim": packet["claim"], "receiver": packet["to"]})


def resume_decision(config, p, committed_receipt, current):
    _packet(config, p)
    r = committed_receipt
    expected_key = envelope(config, p["task"], "handoff-accept", {"offer_id": p["offer_id"]})["key"]
    predecessor = {"owner": p["from"], "claim": p["claim"], "offer_id": p["offer_id"],
                   "offer_digest": p["digest"], "quiescence_verified": True}
    if (not isinstance(r, dict) or r.get("committed") is not True or r.get("key") != expected_key
            or r.get("offer_digest") != p["digest"] or r.get("owner") != config["principal"]
            or r.get("predecessor_quiescence") != predecessor):
        raise Refusal("atomic-acceptance-receipt-required")
    _claim(r.get("claim"))
    c = r["claim"]
    if c["epoch"] != p["claim"]["epoch"] or c["generation"] <= p["claim"]["generation"] or c["fence"] <= p["claim"]["fence"]:
        raise Refusal("successor-capsule-required")
    if (not isinstance(current, dict) or current.get("current_claim_verified") is not True
            or current.get("quiescence_verified") is not True or current.get("predecessor_quiescence") != predecessor
            or current.get("owner") != config["principal"] or current.get("claim") != c
            or current.get("task") != p["task"] or current.get("project") != config["project"]
            or current.get("repo_id") != config["repo_id"] or current.get("authority_id") != config["authority"]["id"]
            or current.get("epoch") != config["authority"]["epoch"]):
        raise Refusal("live-successor-read-required")
    return {"action": "resume-existing-dispatcher", "dispatcher": config["run"]["dispatcher"],
            "claim": c, "task": p["task"]}
