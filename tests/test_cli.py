import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from repo_rat.cli import main, parse_args


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)

    def write_config(self, values=None):
        path = self.directory / "nested" / "config.json"
        path.parent.mkdir()
        path.write_text(json.dumps(values or {"repositories": []}), encoding="utf-8")
        return path

    def test_backfill_selects_single_backfill_run(self):
        args = parse_args(["--backfill", "--config", "custom.json"])

        self.assertTrue(args.backfill)
        self.assertFalse(args.watch)
        self.assertFalse(args.once)
        self.assertEqual(args.config, Path("custom.json"))

    def test_default_is_single_normal_poll(self):
        args = parse_args([])

        self.assertTrue(args.once)
        self.assertFalse(args.watch)
        self.assertFalse(args.backfill)

    def test_watch_and_backfill_are_rejected_together(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                parse_args(["--watch", "--backfill"])

        self.assertEqual(raised.exception.code, 2)

    def test_watch_stops_cleanly_when_injected_sleeper_is_interrupted(self):
        config_path = self.write_config()
        output = io.StringIO()

        def interrupted_sleep(_seconds):
            raise KeyboardInterrupt

        exit_code = main(
            ["--watch", "--config", str(config_path)],
            sleeper=interrupted_sleep,
            stdout=output,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("fetched=0", output.getvalue())

    def test_invalid_configuration_returns_failure_without_creating_state(self):
        missing_config = self.directory / "missing.json"
        errors = io.StringIO()

        exit_code = main(["--config", str(missing_config)], stderr=errors)

        self.assertEqual(exit_code, 1)
        self.assertIn("configuration/state initialization failed", errors.getvalue())
        self.assertFalse((self.directory / "state.db").exists())


if __name__ == "__main__":
    unittest.main()
