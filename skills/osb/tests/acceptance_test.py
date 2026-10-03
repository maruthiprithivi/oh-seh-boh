"""Source-only acceptance runner. Run only in an authorized isolated environment.

The external adapter implements fixtures against the selected real authority.
This runner is not a ledger implementation or a compatibility certification.
"""
import argparse
import json
from pathlib import Path
import subprocess
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, help="Explicit executable adapter path")
    parser.add_argument("--minimal", action="store_true")
    parser.add_argument("--scenario", action="append", default=[],
                        help="Explicit capability-profile scenario ID; repeat as needed")
    args = parser.parse_args()
    adapter = Path(args.adapter).resolve(strict=True)
    if not adapter.is_file():
        parser.error("adapter must be an explicitly reviewed executable file")
    fixtures = json.loads((Path(__file__).parent / "fixtures/scenarios.json").read_text())
    scenario_ids = {item["id"] for item in fixtures["scenarios"]}
    if args.minimal and args.scenario:
        parser.error("choose --minimal or explicit --scenario profile, not both")
    if set(args.scenario) - scenario_ids:
        parser.error("unknown scenario ID")
    suite = unittest.TestSuite()

    class Scenario(unittest.TestCase):
        def __init__(self, scenario):
            super().__init__("runTest")
            self.scenario = scenario

        def shortDescription(self):
            return self.scenario["id"]

        def runTest(self):
            # Keep expected values in the assertion runner, not the adapter input.
            scenario_input = {key: value for key, value in self.scenario.items()
                              if key != "expected"}
            payload = {"fixture_version": fixtures["fixture_version"],
                       "scope": fixtures["scope"], "scenario": scenario_input,
                       "source_contract_context": fixtures.get("source_contract_context")}
            # No shell, inherited credentials never printed; adapter must redact output.
            result = subprocess.run([str(adapter)], input=json.dumps(payload),
                                    capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(result.returncode, 0, "adapter failed; inspect its redacted report")
            self.assertLessEqual(len(result.stdout.encode()), 1024 * 1024,
                                 "adapter response exceeds 1 MiB")
            observed = json.loads(result.stdout)
            self.assertEqual(observed["scenario_id"], self.scenario["id"])
            for key, expected in self.scenario["expected"].items():
                self.assertIn(key, observed["observations"], key)
                actual = observed["observations"][key]
                self.assertIs(type(actual), type(expected), key)
                self.assertEqual(actual, expected, key)

    for scenario in fixtures["scenarios"]:
        selected = (scenario["id"] in args.scenario if args.scenario
                    else not args.minimal or scenario["minimal"])
        if selected:
            suite.addTest(Scenario(scenario))
    success = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
