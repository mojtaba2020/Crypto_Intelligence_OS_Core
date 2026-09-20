import unittest

from scripts.agent_fleet import plan


class FleetPlannerTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "schema_version": 1, "mode": "dry_run", "max_active_workers": 2,
            "tasks": [
                {"id": "data", "agent_id": "A001", "kind": "data_audit"},
                {
                    "id": "model",
                    "agent_id": "A041",
                    "kind": "model_research",
                    "depends_on": ["data"],
                },
                {
                    "id": "eval",
                    "agent_id": "A100",
                    "kind": "independent_evaluation",
                    "depends_on": ["model"],
                },
            ],
        }

    def test_dependency_order_and_no_execution(self):
        report = plan(self.manifest)
        self.assertEqual([w[0]["id"] for w in report["planned_waves"]], ["data", "model", "eval"])
        self.assertEqual(report["active_workers"], 0)
        self.assertEqual(report["external_calls"], 0)

    def test_cycle_rejected(self):
        self.manifest["tasks"][0]["depends_on"] = ["eval"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            plan(self.manifest)

    def test_external_access_rejected(self):
        self.manifest["tasks"][0]["requires_external_access"] = True
        with self.assertRaisesRegex(ValueError, "external access"):
            plan(self.manifest)

    def test_live_mode_rejected(self):
        self.manifest["mode"] = "live"
        with self.assertRaisesRegex(ValueError, "dry_run"):
            plan(self.manifest)

    def test_bad_agent_rejected(self):
        self.manifest["tasks"][0]["agent_id"] = "A101"
        with self.assertRaisesRegex(ValueError, "agent_id"):
            plan(self.manifest)


if __name__ == "__main__":
    unittest.main()
