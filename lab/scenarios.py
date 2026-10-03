"""Deterministic correctness/fault scenarios. Execute only in approved Linux lab."""
import json
import multiprocessing as mp
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from backend import Engine, PROTOCOL
from client import invoke
from projection import MockProjection

BASE, HEAD = "a" * 40, "b" * 40


class Fixture:
    def __init__(self, root, pending=1000, actors=None):
        self.path = Path(root) / "ledger.sqlite3"
        self.engine = Engine.create(self.path, pending)
        self.authority = self.engine.execute("lab-admin", {"protocol": PROTOCOL,
            "operation": "authority-info", "payload": {}})["authority_id"]
        self.actors = actors or {"alice": "admin", "bob": "writer", "carol": "writer", "reader": "reader"}
        self.admin("configure", {"scope": "shared", "team": "shared-team", "repo_id": "10001",
                                  "primary": "alice", "members": self.actors})
        self.identity = {}
        for actor, role in self.actors.items():
            self.identity[actor] = {"scope": "shared", "authority_id": self.authority,
                                    "membership_epoch": 1}
            if role != "reader":
                session = self.call(actor, "session", {"session": "session-" + actor})
                assert session["ok"], session
                self.identity[actor].update(session="session-" + actor, generation=session["generation"])

    def admin(self, operation, payload):
        result = self.engine.execute("lab-admin", {"protocol": PROTOCOL, "operation": operation, "payload": payload})
        assert result["ok"], result
        return result

    def payload(self, actor, extra=None):
        return {**self.identity[actor], "request_id": str(uuid.uuid4()), "base": BASE, "head": HEAD, **(extra or {})}

    def call(self, actor, operation, extra=None):
        return self.engine.execute(actor, {"protocol": PROTOCOL, "operation": operation,
                                          "payload": self.payload(actor, extra)})

    def intent(self, actor="alice", task="task", resources=None):
        result = self.call(actor, "intent", {"task": task, "base": BASE, "head": HEAD,
            "resources": resources or [{"type": "directory", "name": "src"}]})
        assert result["ok"], result
        return result

    def claim(self, actor="alice", task="task", **extra):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT version FROM tasks WHERE scope='shared' AND id=?", (task,)).fetchone()
        return self.call(actor, "claim", {"task": task, "expected_version": row[0] if row else 1, **extra})


def competing_worker(db, actor, payload, barrier, queue):
    barrier.wait(timeout=10)
    result = invoke(db, actor, "claim", payload)
    queue.put({"actor": actor, **result})


class Correctness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="osb-scenario-")
        self.f = Fixture(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_two_competing_agent_processes(self):
        self.f.intent(task="a")
        self.f.intent("bob", "b")
        context = mp.get_context("spawn")
        barrier, queue = context.Barrier(2), context.Queue()
        processes = [context.Process(target=competing_worker, args=(self.f.path, actor,
            self.f.payload(actor, {"task": task, "expected_version": 1}), barrier, queue))
            for actor, task in (("alice", "a"), ("bob", "b"))]
        for process in processes:
            process.start()
        observations = [queue.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(15)
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(sum(bool(r["receipt"] and r["receipt"].get("ok")) for r in observations), 1)

    def test_independent_resources_and_cross_scope(self):
        self.f.intent(task="a", resources=[{"type": "file", "name": "src/a.py"}])
        self.f.intent("bob", "b", [{"type": "file", "name": "src/b.py"}])
        self.assertTrue(self.f.claim(task="a")["ok"])
        self.assertTrue(self.f.claim("bob", "b")["ok"])
        self.f.admin("configure", {"scope": "other", "team": "blue", "repo_id": "10002",
            "primary": "zoe", "members": {"zoe": "admin"}})
        self.assertFalse(self.f.call("alice", "status", {"scope": "other"})["ok"])
        self.assertFalse(self.f.call("alice", "claim", {"scope": "other", "task": "a"})["ok"])
        self.assertFalse(self.f.call("alice", "status", {"repo_id": "10099"})["ok"])
        duplicate = self.f.engine.execute("lab-admin", {"protocol": PROTOCOL, "operation": "configure",
            "payload": {"scope": "alias", "team": "other", "repo_id": "10001", "primary": "zoe", "members": {"zoe": "admin"}}})
        self.assertFalse(duplicate["ok"])

    def test_lost_response_and_idempotent_effect(self):
        self.f.intent()
        payload = self.f.payload("alice", {"task": "task", "expected_version": 1})
        failed = invoke(self.f.path, "alice", "claim", payload, fault="after-commit")
        self.assertEqual(failed["exit"], 73)
        replay = invoke(self.f.path, "alice", "claim", payload)
        self.assertTrue(replay["receipt"]["ok"])
        self.assertEqual(replay["receipt"], invoke(self.f.path, "alice", "claim", payload)["receipt"])
        changed = {**payload, "task": "different"}
        self.assertFalse(invoke(self.f.path, "alice", "claim", changed)["receipt"]["ok"])
        receipt = replay["receipt"]
        effect = self.f.payload("alice", {"task": "task", "fence": receipt["fence"], "head": HEAD})
        invoke(self.f.path, "alice", "protected-write", effect, fault="after-commit")
        self.assertTrue(invoke(self.f.path, "alice", "protected-write", effect)["receipt"]["ok"])
        with sqlite3.connect(self.f.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM protected_writes").fetchone()[0], 1)

    def test_precommit_crash_quarantine(self):
        self.f.intent()
        payload = self.f.payload("alice", {"task": "task", "expected_version": 1})
        self.assertEqual(invoke(self.f.path, "alice", "claim", payload, fault="before-commit")["exit"], 72)
        self.assertEqual(self.f.claim()["reason"], "recovery-required")
        self.f.admin("recover", {"confirm": "ISOLATED_LAB_RECOVERY", "abandon_unconfirmed": True})
        self.assertFalse(invoke(self.f.path, "alice", "claim", payload)["receipt"]["ok"])
        with sqlite3.connect(self.f.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM claims WHERE active=1").fetchone()[0], 0)

    def test_expiry_revocation_and_stale_protected_write(self):
        self.f.intent()
        grant = self.f.claim(ttl_ms=10)
        self.f.admin("tick", {"milliseconds": 10})
        self.assertFalse(self.f.call("alice", "heartbeat", {"task": "task", "fence": grant["fence"]})["ok"])
        next_grant = self.f.claim("bob")
        self.assertTrue(next_grant["ok"])
        self.assertGreater(next_grant["fence"], grant["fence"])
        self.assertFalse(self.f.call("alice", "protected-write", {"task": "task", "fence": grant["fence"]})["ok"])
        self.assertTrue(self.f.call("alice", "revoke", {"target": "bob"})["ok"])
        self.assertFalse(self.f.call("bob", "check", {"task": "task", "fence": next_grant["fence"]})["ok"])

    def test_named_handoff_and_primary_are_distinct(self):
        self.f.intent()
        grant = self.f.claim()
        self.assertTrue(self.f.call("alice", "handoff-offer", {"task": "task", "fence": grant["fence"], "target": "bob"})["ok"])
        self.assertFalse(self.f.call("bob", "protected-write", {"task": "task", "fence": grant["fence"]})["ok"])
        accepted = self.f.call("bob", "handoff-accept", {"task": "task", "fence": grant["fence"]})
        self.assertTrue(accepted["ok"])
        self.assertGreater(accepted["fence"], grant["fence"])
        self.assertFalse(self.f.call("alice", "protected-write", {"task": "task", "fence": grant["fence"]})["ok"])
        self.assertTrue(self.f.call("alice", "effect-intent", {"effect_id": "merge-1", "head": HEAD, "primary_epoch": 1})["ok"])
        self.assertFalse(self.f.call("alice", "primary-transfer", {"target": "carol", "primary_epoch": 1})["ok"])
        self.assertTrue(self.f.call("alice", "effect-result", {"effect_id": "merge-1", "head": HEAD, "outcome": "refused", "primary_epoch": 1})["ok"])
        self.assertTrue(self.f.call("alice", "primary-transfer", {"target": "carol", "primary_epoch": 1})["ok"])
        self.assertTrue(self.f.call("bob", "check", {"task": "task", "fence": accepted["fence"]})["ok"])
        self.assertFalse(self.f.call("alice", "revoke", {"target": "alice"})["ok"])

    def test_same_operation_key_across_actors(self):
        self.f.intent(task="a", resources=[{"type": "file", "name": "a"}])
        self.f.intent("bob", "b", [{"type": "file", "name": "b"}])
        left, right = self.f.claim(task="a"), self.f.claim("bob", "b")
        for actor, task, grant in (("alice", "a", left), ("bob", "b", right)):
            self.assertTrue(grant["ok"])
            self.assertTrue(self.f.call(actor, "protected-write", {"task": task, "fence": grant["fence"],
                "request_id": "same-key-across-actors"})["ok"])
        with sqlite3.connect(self.f.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM protected_writes").fetchone()[0], 2)

    def test_restore_replays_acknowledged_history_and_fences_identity(self):
        backup = Path(self.temp.name) / "backup.sqlite3"
        with sqlite3.connect(self.f.path) as live, sqlite3.connect(backup) as saved:
            live.backup(saved)
        self.f.intent()
        granted = self.f.claim()
        with sqlite3.connect(self.f.path) as db:
            request_count = db.execute("SELECT count(*) FROM requests").fetchone()[0]
        with sqlite3.connect(backup) as saved, sqlite3.connect(self.f.path) as live:
            saved.backup(live)
        self.assertEqual(self.f.claim()["reason"], "recovery-required")
        recovery = self.f.admin("recover", {"confirm": "ISOLATED_LAB_RECOVERY"})
        self.assertNotEqual(recovery["authority_id"], self.f.authority)
        self.assertFalse(self.f.call("alice", "check", {"task": "task", "fence": granted["fence"]})["ok"])
        with sqlite3.connect(self.f.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM requests").fetchone()[0], request_count)
            self.assertEqual(db.execute("SELECT count(*) FROM members WHERE active=1").fetchone()[0], 0)
        # Repeating restore to the same pre-recovery snapshot must not duplicate redo.
        with sqlite3.connect(backup) as saved, sqlite3.connect(self.f.path) as live:
            saved.backup(live)
        second = self.f.admin("recover", {"confirm": "ISOLATED_LAB_RECOVERY"})
        self.assertNotEqual(second["authority_id"], recovery["authority_id"])
        with sqlite3.connect(self.f.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM requests").fetchone()[0], request_count)
            self.assertEqual(db.execute("SELECT count(*) FROM claims WHERE active=1").fetchone()[0], 0)

    def test_malicious_identity_reader_and_cross_scope_ack(self):
        self.assertFalse(self.f.call("bob", "status", {"principal": "alice"})["ok"])
        self.assertFalse(self.f.call("reader", "session", {"session": "evil"})["ok"])
        self.assertFalse(self.f.call("bob", "status", {"authority_id": "old"})["ok"])
        self.f.admin("configure", {"scope": "other", "team": "blue", "repo_id": "10002", "primary": "zoe", "members": {"zoe": "admin"}})
        with sqlite3.connect(self.f.path) as db:
            event = db.execute("SELECT event_id FROM events WHERE scope='other'").fetchone()[0]
        self.assertFalse(self.f.call("alice", "ack", {"event_id": event})["ok"])

    def test_bounded_backpressure_keeps_release_available(self):
        self.f.intent()
        grant = self.f.claim()
        with sqlite3.connect(self.f.path) as db:
            db.execute("UPDATE meta SET value='1' WHERE key='max_pending'")
        self.assertEqual(self.f.call("bob", "intent", {"task": "excess", "base": BASE, "head": HEAD,
            "resources": [{"type": "file", "name": "other"}]})["reason"], "backpressure")
        self.assertTrue(self.f.call("alice", "release", {"task": "task", "fence": grant["fence"]})["ok"])

    def test_projection_outage_deduplication_and_out_of_order(self):
        self.f.intent()
        grant = self.f.claim()
        events = self.f.call("alice", "events", {"after_seq": 0})["events"]
        relevant = [event for event in events if json.loads(event["payload"]).get("task") == "task"]
        sink = MockProjection(Path(self.temp.name) / "projection.sqlite3")
        with self.assertRaises(ConnectionError):
            sink.apply(relevant[-1], fail_before=True)
        with self.assertRaises(TimeoutError):
            sink.apply(relevant[-1], lose_reply=True)
        for event in reversed(relevant):
            sink.apply(event)
            sink.apply(event)
            self.assertTrue(self.f.call("alice", "ack", {"event_id": event["event_id"]})["ok"])
        with sqlite3.connect(sink.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM seen").fetchone()[0], len(relevant))
            self.assertEqual(db.execute("SELECT sequence FROM tasks WHERE task='task'").fetchone()[0], max(e["seq"] for e in relevant))
        self.assertTrue(self.f.call("alice", "check", {"task": "task", "fence": grant["fence"]})["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
