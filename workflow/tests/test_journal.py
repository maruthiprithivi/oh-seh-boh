"""Durable workflow intents, not durable claim authority. GCP-only fixtures."""
import sqlite3
import unittest
from contextlib import contextmanager
import json
import hashlib
from workflow.contract import envelope, canonical, Refusal
from workflow.journal import install, prepare, start, settle, observe, pending
from workflow.notifications import ProjectACL, poll_pending
from workflow.tests.test_contract import config, task


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.c = config(); install(self.db, self.c); self.db.commit()

    def tearDown(self): self.db.close()

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        with self.db: yield

    def test_intent_and_notification_roll_back_together(self):
        self.db.execute("BEGIN IMMEDIATE")
        prepare(self.db, self.c, envelope(self.c, task(), "claim", {}))
        self.db.rollback()
        self.assertEqual(pending(self.db, self.c), [])
        acl = ProjectACL({"demo": ("demo", "42", "3")})
        self.assertEqual(poll_pending(self.db, acl, now=0), [])

    def test_identical_retry_preserves_bytes_changed_payload_conflicts(self):
        e = envelope(self.c, task(), "claim", {"resources": ["src"]})
        with self.tx(): prepare(self.db, self.c, e)
        with self.tx(): self.assertEqual(prepare(self.db, self.c, e), "pending")
        e["payload"] = {"resources": ["other"]}
        with self.assertRaises(Refusal):
            with self.tx(): prepare(self.db, self.c, e)

    def test_unknown_never_becomes_pass_or_automatic_retry(self):
        e = envelope(self.c, task(), "dispatch", {})
        with self.tx(): prepare(self.db, self.c, e)
        with self.tx(): start(self.db, self.c, e["key"])
        with self.tx(): settle(self.db, self.c, e["key"], "unknown", {"effect": "unknown"})
        self.assertEqual(pending(self.db, self.c)[0]["status"], "unknown")
        with self.assertRaises(Refusal):
            with self.tx(): settle(self.db, self.c, e["key"], "confirmed", {"effect": "pass"})

    def test_duplicate_receipt_conflict_refuses(self):
        e = envelope(self.c, task(), "verify", {})
        with self.tx(): prepare(self.db, self.c, e)
        with self.tx(): start(self.db, self.c, e["key"])
        with self.tx(): settle(self.db, self.c, e["key"], "confirmed", {"source": "fixture"})
        with self.tx(): settle(self.db, self.c, e["key"], "confirmed", {"source": "fixture"})
        with self.assertRaises(Refusal):
            with self.tx(): settle(self.db, self.c, e["key"], "confirmed", {"source": "other"})

    def test_one_dispatcher_and_no_mirror_promotion(self):
        e = envelope(self.c, task(), "claim", {})
        changed = config(); changed["run"]["dispatcher"] = "codex"
        with self.assertRaises(Refusal):
            with self.tx(): prepare(self.db, changed, envelope(changed, task(), "claim", {}))
        changed = config(); changed["authority"]["profile"] = "github-cas-cooperative"
        with self.assertRaises(Refusal):
            with self.tx(): prepare(self.db, changed, envelope(changed, task(), "claim", {}))

    def test_local_observation_cannot_suppress_unresolved_owner_intent(self):
        e = envelope(self.c, task(), "dispatch", {})
        with self.tx(): prepare(self.db, self.c, e)
        with self.tx(): observe(self.db, self.c, e["key"], "confirmed", {"claim": "local-prose"})
        self.assertEqual(pending(self.db, self.c)[0]["status"], "pending")
        with self.assertRaises(Refusal):
            with self.tx(): settle(self.db, self.c, e["key"], "confirmed", {"claim": "local-prose"})

    def test_stored_payload_tampering_refuses_before_start(self):
        e = envelope(self.c, task(), "dispatch", {"scope": "src"})
        with self.tx(): prepare(self.db, self.c, e)
        e["payload"] = {"scope": "outside"}
        with self.db: self.db.execute("UPDATE factory_intents SET envelope=? WHERE key=?", (json.dumps(e), e["key"]))
        with self.assertRaises(Refusal): pending(self.db, self.c)
        with self.assertRaises(Refusal):
            with self.tx(): start(self.db, self.c, e["key"])

    def test_start_cas_refuses_second_invocation(self):
        e = envelope(self.c, task(), "dispatch", {})
        with self.tx(): prepare(self.db, self.c, e)
        with self.tx(): start(self.db, self.c, e["key"])
        with self.assertRaises(Refusal):
            with self.tx(): start(self.db, self.c, e["key"])

    def test_local_observation_during_owner_call_does_not_win_receipt_race(self):
        e = envelope(self.c, task(), "dispatch", {})
        with self.tx(): prepare(self.db, self.c, e)
        with self.tx(): start(self.db, self.c, e["key"])
        with self.tx(): observe(self.db, self.c, e["key"], "confirmed", {"prose": "looks done"})
        self.assertEqual(pending(self.db, self.c)[0]["status"], "started")
        with self.tx(): settle(self.db, self.c, e["key"], "unknown", {"effect": "reply-lost"})
        self.assertEqual(pending(self.db, self.c)[0]["status"], "unknown")

    def test_replaced_envelope_key_refuses_even_with_valid_digest(self):
        e = envelope(self.c, task(), "dispatch", {})
        with self.tx(): prepare(self.db, self.c, e)
        other_task = task(); other_task["id"] = "other-task"
        other = envelope(self.c, other_task, "dispatch", {})
        encoded = canonical(other); digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.db: self.db.execute("UPDATE factory_intents SET envelope=?,digest=? WHERE key=?", (encoded, digest, e["key"]))
        with self.assertRaises(Refusal):
            with self.tx(): start(self.db, self.c, e["key"])


if __name__ == "__main__": unittest.main()
