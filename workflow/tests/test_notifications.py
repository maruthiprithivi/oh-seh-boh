"""Adversarial source tests. Execute only on the separately admitted GCP route."""
import sqlite3
import tempfile
import unittest

from workflow.notifications import (
    CloudflareQueues, LightweightQueue, ProjectACL, append_notification,
    acknowledge, acquire_pending, install_schema, make_envelope, poll_pending,
    reconcile, reject_delivery,
)


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        install_schema(self.db)
        self.acl = ProjectACL({"alpha": ("scope-a", "repo-1", "epoch-1")})
        self.now = 100

    def tearDown(self):
        self.db.close()

    def event(self, event_id="evt-1", revision=2, **changes):
        values = dict(scope="scope-a", project="alpha", repository_id="repo-1",
                      authority_epoch="epoch-1", task="task-1", revision=revision,
                      event_id=event_id, payload={"kind": "ready"})
        values.update(changes)
        return make_envelope(**values)

    def append(self, envelope=None):
        self.db.execute("BEGIN")
        result = append_notification(self.db, envelope or self.event(), self.acl)
        self.db.commit()
        return result

    def acquire(self, now=100, **kwargs):
        self.db.execute("BEGIN")
        result = acquire_pending(self.db, self.acl, now=now, **kwargs)
        self.db.commit()
        return result

    def test_append_rejects_autocommit_and_does_not_commit_owner_transaction(self):
        with self.assertRaises(RuntimeError):
            append_notification(self.db, self.event(), self.acl)
        self.db.execute("CREATE TABLE authority (revision INTEGER)")
        self.db.execute("BEGIN")
        self.db.execute("INSERT INTO authority VALUES (2)")
        append_notification(self.db, self.event(), self.acl)
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM authority").fetchone()[0], 0)
        self.assertEqual(poll_pending(self.db, self.acl, now=100), [])

    def test_duplicate_is_idempotent_but_conflicting_event_is_refused(self):
        self.append()
        self.assertFalse(self.append())
        self.db.execute("BEGIN")
        with self.assertRaises(ValueError):
            append_notification(self.db, self.event(payload={"kind": "different"}), self.acl)
        self.db.rollback()
        self.assertEqual(len(poll_pending(self.db, self.acl, now=100)), 1)

    def test_project_acl_rejects_untrusted_route_epoch_and_unknown_project(self):
        for changes in ({"project": "other"}, {"scope": "other"},
                        {"repository_id": "other"}, {"authority_epoch": "old"}):
            self.db.execute("BEGIN")
            with self.assertRaises(PermissionError):
                append_notification(self.db, self.event(**changes), self.acl)
            self.db.rollback()
        self.append()
        self.assertEqual(poll_pending(self.db, ProjectACL({}), now=100), [])

    def test_tampered_payload_and_extra_fields_are_refused(self):
        for mode in ("payload", "field"):
            envelope = self.event()
            if mode == "payload":
                envelope["payload"]["kind"] = "grant"
            else:
                envelope["grant"] = "allow"
            self.db.execute("BEGIN")
            with self.assertRaises(ValueError):
                append_notification(self.db, envelope, self.acl)
            self.db.rollback()

    def test_lost_ack_retries_and_old_ack_cannot_ack_new_attempt(self):
        self.append()
        first = self.acquire(lease_seconds=10)[0]
        self.assertEqual(self.acquire(now=109), [])
        second = self.acquire(now=110)[0]
        self.assertEqual(second.attempt, 2)
        self.db.execute("BEGIN")
        self.assertFalse(acknowledge(self.db, first, self.acl))
        self.assertTrue(acknowledge(self.db, second, self.acl))
        self.assertTrue(acknowledge(self.db, second, self.acl))
        self.db.commit()
        self.assertEqual(self.acquire(now=200), [])

    def test_ack_wrong_digest_refused_without_removing_event(self):
        from dataclasses import replace
        self.append()
        delivery = self.acquire()[0]
        self.db.execute("BEGIN")
        self.assertFalse(acknowledge(self.db, replace(delivery, event_digest="0" * 64), self.acl))
        self.db.commit()
        self.assertEqual(len(self.acquire(now=200)), 1)

    def test_bounded_retry_dead_letter_preserves_notification_and_authority(self):
        self.append()
        delivery = self.acquire(max_attempts=1)[0]
        self.db.execute("BEGIN")
        self.assertTrue(reject_delivery(self.db, delivery, self.acl, now=101,
                                        max_attempts=1, error="transport unavailable"))
        self.db.commit()
        self.assertEqual(self.acquire(now=1000), [])
        row = self.db.execute("SELECT status, envelope FROM factory_notification_outbox").fetchone()
        self.assertEqual(row[0], "dead")
        self.assertIn("task-1", row[1])

    def test_crash_after_last_attempt_dead_letters_on_next_poll(self):
        self.append()
        self.acquire(max_attempts=1, lease_seconds=1)
        self.assertEqual(self.acquire(now=102, max_attempts=1), [])
        self.assertEqual(self.db.execute("SELECT status FROM factory_notification_outbox").fetchone()[0], "dead")

    def test_reordered_notifications_reconcile_current_authority_only(self):
        self.append(self.event(event_id="new", revision=10))
        self.append(self.event(event_id="old", revision=3))
        queries = []
        def owner_read(**identity):
            queries.append(identity)
            return {"revision": 11, "state": "landed"}
        deliveries = self.acquire()
        results = [reconcile(item.envelope, self.acl, owner_read) for item in deliveries]
        self.assertEqual(results, [{"revision": 11, "state": "landed"}] * 2)
        self.assertEqual(len(queries), 2)
        self.assertNotIn("revision", queries[0])
        self.assertNotIn("payload", queries[0])

    def test_transports_only_call_injected_notification_sender(self):
        self.append()
        delivery = self.acquire()[0]
        sent = []
        for adapter in (LightweightQueue, CloudflareQueues):
            adapter(lambda envelope: sent.append(envelope)).send(delivery, self.acl)
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["protocol"], "osb.factory.notification.v1")
        self.assertEqual(self.db.execute("SELECT status FROM factory_notification_outbox").fetchone()[0], "pending")

    def test_revision_and_attempt_boundaries(self):
        for revision in (-1, True, "2"):
            with self.assertRaises(ValueError):
                self.event(revision=revision)
        self.append()
        self.db.execute("BEGIN")
        with self.assertRaises(ValueError):
            acquire_pending(self.db, self.acl, now=100, max_attempts=0)
        self.db.rollback()

    def test_no_implicit_schema_or_recovery_from_missing_owner_migration(self):
        other = sqlite3.connect(":memory:")
        try:
            other.execute("BEGIN")
            with self.assertRaises(sqlite3.OperationalError):
                append_notification(other, self.event(), self.acl)
            other.rollback()
            self.assertEqual(other.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
        finally:
            other.close()

    def test_writer_contention_never_allocates_two_equal_attempts(self):
        with tempfile.TemporaryDirectory() as folder:
            first = sqlite3.connect(folder + "/outbox.sqlite", timeout=0)
            second = sqlite3.connect(folder + "/outbox.sqlite", timeout=0)
            try:
                install_schema(first)
                first.execute("BEGIN IMMEDIATE")
                append_notification(first, self.event(), self.acl)
                first.commit()
                first.execute("BEGIN IMMEDIATE")
                acquired = acquire_pending(first, self.acl, now=100)
                with self.assertRaises(sqlite3.OperationalError):
                    second.execute("BEGIN IMMEDIATE")
                first.commit()
                second.execute("BEGIN IMMEDIATE")
                self.assertEqual(acquire_pending(second, self.acl, now=101), [])
                second.commit()
                self.assertEqual(acquired[0].attempt, 1)
            finally:
                first.close()
                second.close()

    def test_transport_exception_preserves_attempt_for_retry(self):
        self.append()
        delivery = self.acquire(lease_seconds=1)[0]
        def unavailable(envelope):
            raise OSError("injected unavailable transport")
        with self.assertRaises(OSError):
            CloudflareQueues(unavailable).send(delivery, self.acl)
        self.assertEqual(self.acquire(now=102)[0].attempt, 2)

    def test_epoch_rotation_requires_authority_owned_reconciliation(self):
        self.append()
        rotated = ProjectACL({"alpha": ("scope-a", "repo-1", "epoch-2")})
        self.assertEqual(poll_pending(self.db, rotated, now=100), [])
        with self.assertRaises(PermissionError):
            reconcile(self.event(), rotated, lambda **identity: self.fail("must refuse old route"))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM factory_notification_outbox").fetchone()[0], 1)

    def test_schema_install_does_not_commit_existing_owner_transaction(self):
        self.db.execute("CREATE TABLE owner_marker (value INTEGER)")
        self.db.execute("BEGIN")
        self.db.execute("INSERT INTO owner_marker VALUES (1)")
        install_schema(self.db)
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM owner_marker").fetchone()[0], 0)

    def test_corrupt_index_is_refused_before_allocation(self):
        self.append()
        self.db.execute("UPDATE factory_notification_outbox SET event_id='changed-index'")
        self.db.commit()
        with self.assertRaises(ValueError):
            poll_pending(self.db, self.acl, now=100)
        self.assertEqual(self.db.execute("SELECT attempt FROM factory_notification_outbox").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
