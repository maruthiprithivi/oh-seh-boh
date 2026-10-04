"""Generic CI coordination scenarios; run only on approved isolated Linux.

Source-only until executed. No real CI logs, repository or provider calls.
Each tested transition crosses the actual OSB reference process boundary.
"""
import multiprocessing as mp
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from client import invoke
from scenarios import HEAD, Fixture, competing_worker
from result_classification import classify


class CICoordination(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="osb-ci-scenario-")
        self.f = Fixture(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, actor, operation, extra=None, fault=None, expected_exit=0):
        result = invoke(self.f.path, actor, operation, self.f.payload(actor, extra), fault=fault)
        self.assertEqual(result["exit"], expected_exit, result)
        self.assertIsInstance(result["receipt"], dict, result)
        return result["receipt"]

    def intent_and_claim(self, task="ci-task"):
        self.assertTrue(self.call("alice", "intent", {"task": task,
            "resources": [{"type": "file", "name": "src/shared.py"} ]})["ok"])
        grant = self.call("alice", "claim", {"task": task, "expected_version": 1})
        self.assertTrue(grant["ok"], grant)
        return {"task": task, "fence": grant["fence"]}

    def test_declared_base_and_head_binding(self):
        live = self.intent_and_claim()
        for field in ("base", "head"):
            result = self.call("alice", "protected-write", {**live, field: "c" * 40}, expected_exit=1)
            self.assertEqual(result.get("reason"), "revision-mismatch", result)
        valid = self.call("alice", "protected-write", {**live, "content": {"result": "synthetic-pass"}})
        self.assertTrue(valid["ok"], valid)
        with sqlite3.connect(self.f.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM protected_writes").fetchone()[0], 1)

    def test_cancel_release_retry_does_not_restore_authority(self):
        live = self.intent_and_claim()
        release = self.f.payload("alice", {**live, "request_id": "cancel-release"})
        lost = invoke(self.f.path, "alice", "release", release, fault="after-commit")
        self.assertEqual(lost["exit"], 73, lost)
        first = invoke(self.f.path, "alice", "release", release)
        second = invoke(self.f.path, "alice", "release", release)
        self.assertEqual(first["exit"], 0, first)
        self.assertEqual(second["exit"], 0, second)
        self.assertTrue(first["receipt"]["ok"], first)
        self.assertEqual(first["receipt"], second["receipt"])
        check = self.call("alice", "check", live, expected_exit=1)
        self.assertEqual(check.get("reason"), "expired-or-stale-fence", check)
        late = self.call("alice", "protected-write", {**live, "content": {"result": "late-pass"}}, expected_exit=1)
        self.assertEqual(late.get("reason"), "expired-or-stale-fence", late)
        with sqlite3.connect(self.f.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM protected_writes").fetchone()[0], 0)
        successor = self.call("bob", "claim", {"task": "ci-task", "expected_version": 3})
        self.assertTrue(successor["ok"], successor)
        self.assertGreater(successor["fence"], live["fence"])
        # Same committed release receipt is historical; it cannot revoke the successor.
        replay = invoke(self.f.path, "alice", "release", release)
        self.assertEqual(replay["exit"], 0, replay)
        self.assertEqual(replay["receipt"], first["receipt"])
        for operation in ("release", "complete"):
            stale = self.call("alice", operation, live, expected_exit=1)
            self.assertEqual(stale.get("reason"), "wrong-holder", stale)
        current = {"task": "ci-task", "fence": successor["fence"]}
        self.assertTrue(self.call("bob", "check", current)["ok"])
        self.assertTrue(self.call("bob", "protected-write", {**current,
            "content": {"result": "current-owner"}})["ok"])
        self.assertTrue(self.call("bob", "release", current)["ok"])

    def test_obsolete_worker_and_evidence_substitution(self):
        old = self.intent_and_claim()
        delayed = self.f.payload("alice", {**old, "request_id": "old-worker-result",
                                          "content": {"run": "synthetic-old", "result": "pass"}})
        session = self.call("alice", "session", {"session": "replacement-session"})
        self.assertTrue(session["ok"], session)
        self.f.identity["alice"].update(session="replacement-session", generation=session["generation"])
        replacement = self.call("alice", "claim", {"task": "ci-task", "expected_version": 2})
        self.assertTrue(replacement["ok"], replacement)
        self.assertGreater(replacement["fence"], old["fence"])
        obsolete = invoke(self.f.path, "alice", "protected-write", delayed)
        self.assertEqual(obsolete["exit"], 1, obsolete)
        self.assertEqual(obsolete["receipt"].get("reason"), "stale-session", obsolete)
        bound = self.f.payload("alice", {"task": "ci-task", "fence": replacement["fence"],
            "request_id": "current-evidence", "content": {"run": "synthetic-current", "result": "failed"}})
        stored = invoke(self.f.path, "alice", "protected-write", bound)
        self.assertEqual(stored["exit"], 0, stored)
        self.assertTrue(stored["receipt"]["ok"], stored)
        duplicate = invoke(self.f.path, "alice", "protected-write", bound)
        self.assertEqual(duplicate["exit"], 0, duplicate)
        self.assertEqual(duplicate["receipt"], stored["receipt"])
        changed = {**bound, "content": {"run": "synthetic-current", "result": "pass"}}
        substitution = invoke(self.f.path, "alice", "protected-write", changed)
        self.assertEqual(substitution["exit"], 1, substitution)
        self.assertEqual(substitution["receipt"].get("reason"), "idempotency-conflict", substitution)
        with sqlite3.connect(self.f.path) as db:
            rows = db.execute("SELECT head,payload FROM protected_writes").fetchall()
        self.assertEqual(rows, [(HEAD, '{"result":"failed","run":"synthetic-current"}')])
        # Hash bytes read from the normal consumer, rather than a claimed digest field.
        actual_digest = hashlib.sha256(rows[0][1].encode("utf-8")).hexdigest()
        expected_digest = hashlib.sha256(b'{"result":"failed","run":"synthetic-current"}').hexdigest()
        self.assertEqual(actual_digest, expected_digest)

    def test_result_classification_fixtures(self):
        cases = json.loads(Path(__file__).with_name("ci_result_fixtures.json").read_text())
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(classify(case["observation"]), case["expected"])

    def test_migration_namespace_serializes_competing_writers(self):
        for actor, task in (("alice", "migration-a"), ("bob", "migration-b")):
            result = self.call(actor, "intent", {"task": task,
                "resources": [{"type": "directory", "name": "db/migrations"}]})
            self.assertTrue(result["ok"], result)
        context = mp.get_context("spawn")
        barrier, queue = context.Barrier(2), context.Queue()
        workers = [context.Process(target=competing_worker, args=(self.f.path, actor,
            self.f.payload(actor, {"task": task, "expected_version": 1}), barrier, queue))
            for actor, task in (("alice", "migration-a"), ("bob", "migration-b"))]
        try:
            for worker in workers:
                worker.start()
            results = [queue.get(timeout=15) for _ in workers]
            for worker in workers:
                worker.join(15)
                self.assertFalse(worker.is_alive())
                self.assertEqual(worker.exitcode, 0)
            for result in results:
                self.assertIsInstance(result["receipt"], dict, result)
                self.assertEqual(result["exit"], 0 if result["receipt"].get("ok") else 1, result)
            self.assertEqual(sum(result["receipt"].get("ok") is True for result in results), 1)
            denied = [result["receipt"] for result in results if not result["receipt"].get("ok")]
            self.assertEqual([row.get("reason") for row in denied], ["scope-conflict"])
            with sqlite3.connect(self.f.path) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM claims WHERE active=1").fetchone()[0], 1)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(5)
            queue.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
