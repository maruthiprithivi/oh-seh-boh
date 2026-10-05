"""GCP-only CLI boundary source fixtures; no real authority or dispatcher."""
import json
from pathlib import Path
import tempfile
import unittest
from workflow.cli import read, connect, admit_snapshot
from workflow.contract import Refusal, envelope
from workflow.tests.test_contract import config, task


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
    def test_duplicate_keys_nonfinite_and_oversize_refuse(self):
        source = self.root / "input.json"
        for data in ('{"x":1,"x":2}', '{"x":NaN}', ' ' * 65537):
            source.write_text(data)
            with self.assertRaises(Refusal): read(source)
    def test_journal_creation_is_exclusive_and_private(self):
        path = self.root / "run.sqlite3"
        db = connect(path, create=True); db.close()
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError): connect(path, create=True)
        with self.assertRaises(Refusal): connect(self.root / "absent.sqlite3")
    def test_symlink_and_public_journal_refuse(self):
        path = self.root / "run.sqlite3"
        db = connect(path, create=True); db.close()
        link = self.root / "link.sqlite3"; link.symlink_to(path)
        with self.assertRaises(Refusal): connect(link)
        path.chmod(0o644)
        with self.assertRaises(Refusal): connect(path)
    def test_acl_string_cannot_authorize_substring(self):
        c = config(); c["acl"] = {"operator": "not-demo-but-substring"}
        with self.assertRaises(Refusal): envelope(c, task(), "claim", {})

    def test_same_project_wrong_repository_cannot_be_admitted(self):
        s = {"backlog": [{"project": "demo", "repo_id": "99"}], "active": [],
             "capacity": {"cpu": 1, "memory_mb": 128, "ci_slots": 1}, "landing": {"limit": 1, "pending": 0}}
        with self.assertRaises(Refusal): admit_snapshot(config(), s)


if __name__ == "__main__": unittest.main()
