import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicSetupTests(unittest.TestCase):
    def test_tracked_config_does_not_monitor_a_specific_users_stars(self):
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

        self.assertIsNone(config["starred_username"])

    def test_actions_workflow_reads_starred_username_from_a_repository_variable(self):
        workflow = (ROOT / ".github/workflows/release-rat.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("vars.RELEASE_RAT_STARRED_USERNAME", workflow)
        self.assertIn("--config \"$RUNNER_TEMP/release-rat.json\"", workflow)


if __name__ == "__main__":
    unittest.main()
