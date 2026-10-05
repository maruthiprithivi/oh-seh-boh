"""GCP-only handoff policy sources; no document can transfer a real claim."""
import unittest
from workflow.contract import Refusal
from workflow.handoff import checkpoint, accept_intent, resume_decision
from workflow.tests.test_contract import config, task


def delta():
    return {"worktree": {"locator": "approved-worktree-1", "branch": "feature/task-1", "head": "b" * 40, "dirty": False},
            "deviations": ["bounded source preview"], "environment": ["GCP test window required"],
            "verification": [{"check": "unit", "status": "unrun", "evidence_digest": None}],
            "risks": ["owner bridge unqualified"], "next_action": "Inspect retained receipts"}


def capsule(): return {"epoch": 3, "generation": 2, "fence": 9}


def receiver():
    c = config(); c["principal"] = "receiver"; c["acl"]["receiver"] = ["demo"]
    return c


def preflight(packet):
    return {"project": "demo", "repo_id": "42", "authority_id": "fixture-authority",
            "epoch": 3, "task": task(), "claim": capsule(), "owner": "operator",
            "offer_id": packet["offer_id"], "offer_digest": packet["digest"], "verified_delta_digest": packet["digest"],
            "quiescence_verified": True, "reconciled": True}


class HandoffTests(unittest.TestCase):
    def test_pause_keeps_ownership_and_cannot_accept(self):
        p = checkpoint(config(), task(), capsule(), delta(), mode="pause")
        self.assertEqual(p["to"], "operator")
        with self.assertRaises(Refusal): accept_intent(receiver(), p, preflight(p))
    def test_offer_is_not_permission_to_resume(self):
        p = checkpoint(config(), task(), capsule(), delta(), mode="offer", to="receiver", offer_id="offer-1")
        with self.assertRaises(Refusal): resume_decision(receiver(), p, {"document_accepted": True}, {})
    def test_receiver_must_verify_current_repository_revision_and_evidence(self):
        p = checkpoint(config(), task(), capsule(), delta(), mode="offer", to="receiver", offer_id="offer-1")
        for key, value in [("repo_id", "99"), ("epoch", 2), ("owner", "other"),
                           ("verified_delta_digest", "wrong"), ("quiescence_verified", False)]:
            s = preflight(p); s[key] = value
            with self.assertRaises(Refusal): accept_intent(receiver(), p, s)
        self.assertEqual(accept_intent(receiver(), p, preflight(p))["operation"], "handoff-accept")
    def test_stale_fence_or_changed_head_cannot_accept(self):
        p = checkpoint(config(), task(), capsule(), delta(), mode="offer", to="receiver", offer_id="offer-1")
        for field in ("generation", "fence"):
            s = preflight(p); s["claim"] = {**capsule(), field: 10}
            with self.assertRaises(Refusal): accept_intent(receiver(), p, s)
        s = preflight(p); s["task"] = {**task(), "head": "c" * 40}
        with self.assertRaises(Refusal): accept_intent(receiver(), p, s)
    def test_dirty_worktree_must_be_explicit_and_does_not_auto_commit(self):
        d = delta(); d["worktree"]["dirty"] = True
        with self.assertRaises(Refusal): checkpoint(config(), task(), capsule(), d, mode="offer", to="receiver", offer_id="offer-1")
        d["worktree"]["uncommitted"] = ["src/example.py"]
        p = checkpoint(config(), task(), capsule(), d, mode="offer", to="receiver", offer_id="offer-1")
        self.assertTrue(p["delta"]["worktree"]["dirty"])
    def test_atomic_acceptance_and_live_successor_capsule_required(self):
        p = checkpoint(config(), task(), capsule(), delta(), mode="offer", to="receiver", offer_id="offer-1")
        intent = accept_intent(receiver(), p, preflight(p))
        receipt = {"committed": True, "key": intent["key"], "offer_digest": p["digest"],
                   "owner": "receiver", "claim": {"epoch": 3, "generation": 3, "fence": 10},
                   "predecessor_quiescence": {"owner": "operator", "claim": capsule(), "offer_id": "offer-1",
                                              "offer_digest": p["digest"], "quiescence_verified": True}}
        s = {**preflight(p), "owner": "receiver", "claim": receipt["claim"], "current_claim_verified": True,
             "predecessor_quiescence": receipt["predecessor_quiescence"]}
        self.assertEqual(resume_decision(receiver(), p, receipt, s)["action"], "resume-existing-dispatcher")
        s["quiescence_verified"] = False
        with self.assertRaises(Refusal): resume_decision(receiver(), p, receipt, s)
        s["quiescence_verified"] = True
        s["predecessor_quiescence"] = {**receipt["predecessor_quiescence"], "offer_id": "old-offer"}
        with self.assertRaises(Refusal): resume_decision(receiver(), p, receipt, s)
        s["predecessor_quiescence"] = receipt["predecessor_quiescence"]
        s["claim"] = capsule()
        with self.assertRaises(Refusal): resume_decision(receiver(), p, receipt, s)
    def test_modified_delta_and_receiver_cannot_pass_digest(self):
        p = checkpoint(config(), task(), capsule(), delta(), mode="offer", to="receiver", offer_id="offer-1")
        p["delta"]["next_action"] = "Changed instruction"
        with self.assertRaises(Refusal): accept_intent(receiver(), p, preflight(p))

    def test_reoffer_requires_distinct_authority_occurrence_same_offer_cannot_mutate(self):
        p = checkpoint(config(), task(), capsule(), delta(), mode="offer", to="receiver", offer_id="offer-1")
        q = checkpoint(config(), task(), capsule(), delta(), mode="offer", to="receiver", offer_id="offer-2")
        self.assertNotEqual(accept_intent(receiver(), p, preflight(p))["key"], accept_intent(receiver(), q, preflight(q))["key"])
        stale = preflight(q); stale["offer_id"] = "offer-1"
        with self.assertRaises(Refusal): accept_intent(receiver(), q, stale)


if __name__ == "__main__": unittest.main()
