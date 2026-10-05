"""Injected owner-port call ordering; these are not installed harness tests."""
import sqlite3
import unittest
from workflow.bridge import apply_prepared
from workflow.contract import envelope, Refusal
from workflow.journal import install, prepare, pending
from workflow.tests.test_contract import config, task


class OwnerFixture:
    dispatcher = "firstmate"
    authority_profile = "transactional"
    def __init__(self, db, outcome="confirmed"):
        self.db = db; self.outcome = outcome; self.calls = []
    def authorize_current(self, e):
        self.calls.append("authorize")
        return True  # trusted synthetic fixture only; real adapter authenticates live
    def apply(self, e):
        self.calls.append("apply")
        assert not self.db.in_transaction
        assert self.db.execute("SELECT status FROM factory_intents WHERE key=?", (e["key"],)).fetchone()[0] == "started"
        if self.outcome == "exception": raise TimeoutError("lost reply")
        return {"status": self.outcome, "receipt": {"fixture": True}}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:"); self.c = config()
        install(self.db, self.c); self.db.commit()
        self.e = envelope(self.c, task(), "claim", {})
        self.db.execute("BEGIN IMMEDIATE")
        with self.db: prepare(self.db, self.c, self.e)
    def tearDown(self): self.db.close()
    def test_commit_before_effect_and_never_repeat(self):
        owner = OwnerFixture(self.db)
        self.assertEqual(apply_prepared(self.db, self.c, self.e["key"], owner), "confirmed")
        with self.assertRaises(Refusal): apply_prepared(self.db, self.c, self.e["key"], owner)
        self.assertEqual(owner.calls.count("apply"), 1)
    def test_lost_ack_is_retained_not_relaunched(self):
        owner = OwnerFixture(self.db, "exception")
        self.assertEqual(apply_prepared(self.db, self.c, self.e["key"], owner), "unknown")
        self.assertEqual(pending(self.db, self.c)[0]["status"], "unknown")
        with self.assertRaises(Refusal): apply_prepared(self.db, self.c, self.e["key"], owner)
    def test_wrong_dispatcher_cannot_apply(self):
        owner = OwnerFixture(self.db); owner.dispatcher = "codex"
        with self.assertRaises(Refusal): apply_prepared(self.db, self.c, self.e["key"], owner)
        self.assertEqual(owner.calls, [])
    def test_unavailable_authority_refuses_before_effect(self):
        owner = OwnerFixture(self.db)
        owner.authorize_current = lambda e: False
        with self.assertRaises(Refusal): apply_prepared(self.db, self.c, self.e["key"], owner)
        self.assertEqual(owner.calls, [])


if __name__ == "__main__": unittest.main()
