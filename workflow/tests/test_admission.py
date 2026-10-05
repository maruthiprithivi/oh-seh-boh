"""Adversarial policy source. Run on GCP only; no local execution recorded."""
import copy
import unittest

from workflow.admission import evaluate


def task(identifier, **changes):
    value = {
        "project": "project-a", "repo_id": "12345", "id": identifier,
        "revision": 1, "base": "a" * 40, "head": "b" * 40, "state": "ready",
        "ready": {"scope": ["src/" + identifier], "acceptance": ["bounded outcome"],
                  "verification": ["GCP verification"], "integration_owner": "owner"},
        "dependencies": [], "costs": {"cpu": 1, "memory_mb": 10, "ci_slots": 1},
        "priority": 0,
    }
    value.update(changes)
    return value


class AdmissionTests(unittest.TestCase):
    def evaluate(self, backlog, active=None, capacity=None, landing=None):
        return evaluate(backlog, capacity or {"cpu": 2, "memory_mb": 20, "ci_slots": 2},
                        active or [], landing or {"limit": 10, "pending": 0}, "project-a")

    def ids(self, result):
        return [item["id"] for item in result["candidates"]]

    def reason(self, result, identifier):
        return next(item["reason"] for item in result["refusals"] if item["id"] == identifier)

    def test_capacity_accumulates_and_accounts_for_active(self):
        result = self.evaluate([task("c"), task("b"), task("a")], [task("active", state="running")])
        self.assertEqual(self.ids(result), ["a"])
        self.assertEqual(self.reason(result, "b"), "capacity_exhausted")
        self.assertEqual(self.reason(result, "c"), "capacity_exhausted")

    def test_dependency_must_be_completed_at_exact_revision(self):
        dep = task("dep", state="completed", revision=2)
        result = self.evaluate([dep, task("a", dependencies=[{"task": "dep", "revision": 1}])])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(self.reason(result, "a"), "dependency_revision_changed")

    def test_dependencies_do_not_become_completed_by_selection(self):
        result = self.evaluate([task("a"), task("b", dependencies=[{"task": "a", "revision": 1}])])
        self.assertEqual(self.ids(result), ["a"])
        self.assertEqual(self.reason(result, "b"), "dependency_incomplete")

    def test_path_ancestor_conflicts_but_sibling_prefix_does_not(self):
        a, b, c = task("a"), task("b"), task("c")
        a["ready"]["scope"] = ["src/module"]
        b["ready"]["scope"] = ["src/module/file.py"]
        c["ready"]["scope"] = ["src/modules"]
        result = self.evaluate([c, b, a])
        self.assertEqual(self.ids(result), ["a", "c"])
        self.assertEqual(self.reason(result, "b"), "resource_conflict")

    def test_active_scope_conflicts(self):
        active, candidate = task("active", state="running"), task("a")
        active["ready"]["scope"] = ["lock:landing"]
        candidate["ready"]["scope"] = ["lock:landing"]
        self.assertEqual(self.reason(self.evaluate([candidate], [active]), "a"), "resource_conflict")

    def test_landing_full_and_selected_work_reserves_landing_capacity(self):
        self.assertEqual(self.reason(self.evaluate([task("a")], landing={"limit": 1, "pending": 1}), "a"),
                         "landing_backpressure")
        result = self.evaluate([task("b"), task("a")], landing={"limit": 1, "pending": 0})
        self.assertEqual(self.ids(result), ["a"])
        self.assertEqual(self.reason(result, "b"), "landing_backpressure")

    def test_project_isolation_and_repository_mix(self):
        result = self.evaluate([task("a"), task("foreign", project="project-b")])
        self.assertEqual(self.ids(result), ["a"])
        self.assertEqual(self.reason(result, "foreign"), "project_mismatch")
        result = self.evaluate([task("a"), task("b", repo_id="67890")])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(self.reason(result, "a"), "repository_mix")

    def test_malformed_costs_and_unknown_fields_fail_closed(self):
        for costs in ({"cpu": True}, {"cpu": -1}, {"cpu": 1.5}, {"gpu": 1}, {"cpu": "1"}):
            with self.subTest(costs=costs):
                self.assertEqual(self.reason(self.evaluate([task("a", costs=costs)]), "a"), "malformed_task")
        self.assertEqual(self.reason(self.evaluate([task("a", surprise="grant")]), "a"), "malformed_task")
        self.assertEqual(self.reason(self.evaluate([task("a", state=[])]), "a"), "malformed_task")

    def test_epic_split_invalidates_previously_ready_child(self):
        epic = task("epic", state="completed", revision=8)
        child = task("child", dependencies=[{"task": "epic", "revision": 7}])
        self.assertEqual(self.reason(self.evaluate([epic, child]), "child"), "dependency_revision_changed")

    def test_fixture_project_name_does_not_prove_endpoint_health(self):
        # A unique project changes isolation only. Endpoint runtime evidence is
        # enforced by the integration module before claim/dispatch, never inferred
        # from this pure policy or a verification declaration.
        candidate = task("a", project="fixture-unique")
        result = evaluate([candidate], {"cpu": 2, "memory_mb": 20, "ci_slots": 2},
                          [], {"limit": 10, "pending": 0}, "project-a")
        self.assertEqual(self.ids(result), [])
        self.assertEqual(self.reason(result, "a"), "project_mismatch")

    def test_deterministic_priority_then_identifier_and_no_mutation(self):
        backlog = [task("c", priority=2), task("b", priority=1), task("a", priority=1)]
        before = copy.deepcopy(backlog)
        first = self.evaluate(backlog)
        second = self.evaluate(list(reversed(backlog)))
        self.assertEqual(first, second)
        self.assertEqual(self.ids(first), ["c", "a"])
        self.assertEqual(backlog, before)

    def test_cycles_fail_closed(self):
        result = self.evaluate([task("a", dependencies=[{"task": "b", "revision": 1}]),
                                task("b", dependencies=[{"task": "a", "revision": 1}])])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(self.reason(result, "a"), "dependency_cycle")

    def test_stale_duplicate_revision_and_active_same_task(self):
        result = self.evaluate([task("a", revision=1), task("a", revision=2)])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(result["refusals"], [{"id": "a", "reason": "ambiguous_task"},
                                           {"id": "a", "reason": "stale_revision"}])
        result = self.evaluate([task("a")], [task("a", state="running", revision=2)])
        self.assertEqual(self.reason(result, "a"), "stale_revision")

    def test_invalid_active_capacity_landing_and_traversal_refuse_safely(self):
        for options in ({"active": [{"id": "broken"}]}, {"capacity": {"cpu": True}},
                        {"landing": {"limit": 1, "pending": -1}}):
            self.assertEqual(self.reason(self.evaluate([task("a")], **options), "a"), "invalid_context")
        candidate = task("a")
        candidate["ready"]["scope"] = ["src/../private"]
        self.assertEqual(self.reason(self.evaluate([candidate]), "a"), "malformed_task")

    def test_malformed_neighbor_invalidates_whole_backlog_snapshot(self):
        broken = task("broken")
        broken["ready"]["scope"] = []
        result = self.evaluate([task("a"), broken])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(self.reason(result, "broken"), "malformed_task")
        self.assertEqual(self.reason(result, "a"), "invalid_snapshot")

    def test_malformed_neighboring_active_scope_invalidates_snapshot(self):
        broken = task("active", state="running")
        broken["ready"]["scope"] = ["src/../unknown"]
        result = self.evaluate([task("a")], [broken])
        self.assertEqual(self.ids(result), [])
        self.assertEqual(self.reason(result, "a"), "invalid_context")

    def test_exact_lowercase_oids_and_immutable_repository_ids(self):
        for changes in ({"head": "main"}, {"base": "b" * 39}, {"head": "A" * 40},
                        {"repo_id": "org/repo"}, {"repo_id": 12345}):
            with self.subTest(changes=changes):
                result = self.evaluate([task("a"), task("broken", **changes)])
                self.assertEqual(self.ids(result), [])
                self.assertEqual(self.reason(result, "broken"), "malformed_task")
                self.assertEqual(self.reason(result, "a"), "invalid_snapshot")
        result = self.evaluate([task("a", base="a" * 64, head="b" * 64)])
        self.assertEqual(self.ids(result), ["a"])


if __name__ == "__main__":
    unittest.main()
