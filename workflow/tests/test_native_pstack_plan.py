"""UNRUN plan rejection tests; execute only in the separately admitted GCP job."""
import unittest

from workflow.native_pstack_cases import CASES, EXCLUDED_ENVIRONMENT, clean_environment, validate_plan


class NativePlanTests(unittest.TestCase):
    def plan(self):
        return {"contract": "osb.native-pstack-cases.v1", "admitted_existing_gcp": True,
                "admission_reference": "supervisor-approved-existing-allocation", "max_wall_seconds": 180,
                "admitted_cpus": [0], "exclusive_existing_cgroup": "/sys/fs/cgroup/approved-native-job",
                "packet": "/approved/packet", "packet_commit": "a" * 40,
                "pstack": "/approved/pstack", "pstack_commit": "b" * 40,
                "owner": "/approved/owner", "owner_commit": "c" * 40,
                "bun": "/approved/bin/bun", "bun_sha256": "d" * 64,
                "evidence": "/approved/evidence-new", "cases": list(CASES)}

    def test_explicit_exact_plan_is_accepted(self):
        self.assertEqual(validate_plan(self.plan())["cases"], list(CASES))

    def test_nonobject_plan_refuses_with_value_error(self):
        for plan in (None, [], "plan", True, 42):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_malformed_cpu_values_refuse_before_set_conversion(self):
        for cpus in ([[]], [{}], [True], ["0"], [0.0], [-1], [None], [0, []]):
            with self.subTest(cpus=cpus), self.assertRaises(ValueError):
                validate_plan({**self.plan(), "admitted_cpus": cpus})

    def test_retained_policy_excludes_ambient_credentials_and_owner_config(self):
        environment = {key: "secret-test-value" for key in EXCLUDED_ENVIRONMENT}
        environment.update(PATH="/approved/bin", PYTHONDONTWRITEBYTECODE="1")
        filtered = clean_environment(environment)
        self.assertEqual(filtered, {"PATH": "/approved/bin", "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertIn("GH_TOKEN", environment)

    def test_missing_or_forged_source_bindings_refuse(self):
        for key in ("packet_commit", "pstack_commit", "owner_commit", "bun_sha256"):
            with self.subTest(key=key):
                plan = self.plan()
                plan[key] = "latest"
                with self.assertRaises(ValueError):
                    validate_plan(plan)

    def test_omitted_case_and_source_nested_evidence_refuse(self):
        for change in ({"cases": [CASES[0]]}, {"evidence": "/approved/pstack/evidence"},
                       {"evidence": "/approved/owner"}, {"packet": "relative"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan({**self.plan(), **change})

    def test_admission_and_wall_limit_cannot_be_implicit(self):
        for change in ({"admitted_existing_gcp": False}, {"admission_reference": ""},
                       {"max_wall_seconds": True}, {"max_wall_seconds": 181}, {"admitted_cpus": []},
                       {"admitted_cpus": [0, 0]}, {"exclusive_existing_cgroup": "relative"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan({**self.plan(), **change})


if __name__ == "__main__":
    unittest.main()
