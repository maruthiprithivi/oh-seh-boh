"""Adversarial source fixtures; execute only on an admitted GCP executor."""
import copy
import unittest
from workflow.contract import Refusal, envelope, next_action, validate, canonical


def config():
    return {"project": "demo", "repo_id": "42", "principal": "operator",
            "acl": {"operator": ["demo"]}, "authority": {
                "profile": "transactional", "id": "fixture-authority", "epoch": 3},
            "run": {"id": "run-1", "dispatcher": "firstmate"}}


def task():
    return {"id": "task-1", "revision": 2, "base": "a" * 40, "head": "b" * 40}


def state():
    return {"phase": "claim", "owned": True, "reconciled": True,
            "owner": "operator", "revision": 2, "base": "a" * 40,
            "head": "b" * 40, "authority_id": "fixture-authority", "epoch": 3,
            "claim": {"fence": 9, "generation": 2}, "evidence": [],
            "required_checks": ["unit", "drift-ack", "fixture-ready"],
            "landing_authorized": False}


class ContractTests(unittest.TestCase):
    def test_same_intent_has_identical_bytes(self):
        a = envelope(config(), task(), "claim", {"resources": ["src"]})
        b = envelope(config(), task(), "claim", {"resources": ["src"]})
        self.assertEqual(canonical(a), canonical(b))

    def test_project_acl_is_configured_not_request_selected(self):
        c = config(); c["acl"] = {"operator": ["other"]}
        with self.assertRaises(Refusal): envelope(c, task(), "claim", {})

    def test_dispatcher_and_authority_cannot_change_on_receipt(self):
        e = envelope(config(), task(), "dispatch", {})
        e["run"]["dispatcher"] = "codex"
        with self.assertRaises(Refusal): validate(e, config())
        e = envelope(config(), task(), "dispatch", {})
        e["authority"]["profile"] = "github-cas-cooperative"
        with self.assertRaises(Refusal): validate(e, config())

    def test_bool_revision_and_bad_oid_refuse(self):
        for key, value in [("revision", True), ("head", "main"), ("id", "../escape")]:
            t = task(); t[key] = value
            with self.assertRaises(Refusal): envelope(config(), t, "claim", {})

    def test_unknown_effect_reconciles_without_dispatch(self):
        s = state(); s["phase"] = "unknown"
        self.assertEqual(next_action(config(), task(), s)["action"], "reconcile")

    def test_old_green_does_not_survive_new_head(self):
        s = state(); s["phase"] = "verify"
        s["evidence"] = [{"check": n, "status": "pass", "head": "c" * 40,
                          "base": "a" * 40, "revision": 2} for n in s["required_checks"]]
        self.assertEqual(next_action(config(), task(), s)["action"], "verify")

    def test_missing_drift_ack_and_fixture_readiness_block_landing(self):
        s = state(); s["phase"] = "verify"; s["landing_authorized"] = True
        s["evidence"] = [{"check": "unit", "status": "pass", "head": "b" * 40,
                          "base": "a" * 40, "revision": 2}]
        self.assertEqual(next_action(config(), task(), s)["missing"], ["drift-ack", "fixture-ready"])

    def test_review_requires_verified_reviewer_role_not_display_approval(self):
        s = state(); s["phase"] = "review"
        s["review"] = {"status": "approved", "verified_role": False, "head": "b" * 40}
        self.assertEqual(next_action(config(), task(), s)["action"], "review")

    def test_landing_needs_explicit_authorization(self):
        s = state(); s["phase"] = "landing"
        self.assertEqual(next_action(config(), task(), s)["action"], "await-landing-authorization")

    def test_stale_base_or_epoch_freezes_scope(self):
        for key, value in [("base", "c" * 40), ("epoch", 2), ("revision", 1)]:
            s = state(); s[key] = value
            self.assertEqual(next_action(config(), task(), s)["action"], "reconcile")

    def test_ready_snapshot_revision_and_epoch_checked_before_claim(self):
        for key, value in [("base", "c" * 40), ("epoch", 2), ("revision", 1)]:
            s = state(); s["phase"] = "ready"; s["owned"] = False; s[key] = value
            self.assertEqual(next_action(config(), task(), s)["action"], "reconcile")
        s = state(); s["phase"] = "ready"; s["owned"] = False
        self.assertEqual(next_action(config(), task(), s)["action"], "claim")

    def test_unowned_task_cannot_advance(self):
        s = state(); s["owned"] = False
        self.assertEqual(next_action(config(), task(), s)["action"], "reconcile")

    def test_duplicate_conflicting_evidence_never_counts_as_green(self):
        s = state(); s["phase"] = "verify"
        s["required_checks"] = ["unit"]
        good = {"check": "unit", "status": "pass", "head": "b" * 40,
                "base": "a" * 40, "revision": 2}
        s["evidence"] = [good, {**good, "status": "failure"}]
        self.assertEqual(next_action(config(), task(), s)["action"], "fix")


if __name__ == "__main__": unittest.main()
