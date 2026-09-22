import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_rat.config import ConfigError, load_config
from release_rat.models import Judgment, Release


class LoadConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)

    def write_config(self, values):
        path = self.directory / "nested" / "config.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(values), encoding="utf-8")
        return path

    def test_load_config_resolves_paths_relative_to_config_file(self):
        config_path = self.write_config(
            {
                "repositories": ["python/cpython", "astral-sh/uv"],
                "poll_interval_seconds": 90,
                "include_prereleases": True,
                "bootstrap_mode": "seed",
                "state_path": "runtime/state.db",
                "local_log_path": "runtime/releases.jsonl",
                "discord_webhook_env": "MY_DISCORD_WEBHOOK",
                "github_token_env": "MY_GITHUB_TOKEN",
                "llm": {"enabled": False},
            }
        )

        config = load_config(config_path)

        self.assertEqual(config.repositories, ("python/cpython", "astral-sh/uv"))
        self.assertEqual(config.poll_interval_seconds, 90)
        self.assertTrue(config.include_prereleases)
        self.assertEqual(config.state_path, config_path.parent / "runtime/state.db")
        self.assertEqual(
            config.local_log_path, config_path.parent / "runtime/releases.jsonl"
        )
        self.assertFalse(config.llm.enabled)
        self.assertEqual(config.llm.base_url_env, "OPENAI_BASE_URL")
        self.assertEqual(config.llm.api_key_env, "OPENAI_API_KEY")
        self.assertEqual(config.llm.model_env, "RELEASE_RAT_MODEL")
        self.assertEqual(config.llm.default_base_url, "https://api.openai.com/v1")
        self.assertEqual(config.llm.default_model, "gpt-5-mini")

    def test_defaults_are_applied_and_empty_repositories_are_allowed(self):
        config = load_config(self.write_config({"repositories": []}))

        self.assertEqual(config.repositories, ())
        self.assertIsNone(config.starred_username)
        self.assertEqual(config.poll_interval_seconds, 3600)
        self.assertFalse(config.include_prereleases)
        self.assertEqual(config.bootstrap_mode, "seed")
        self.assertEqual(config.state_path, self.directory / "nested/state.db")
        self.assertEqual(config.local_log_path, self.directory / "nested/release-log.jsonl")

    def test_loads_optional_public_starred_username(self):
        config = load_config(
            self.write_config(
                {"repositories": [], "starred_username": "silascroe"}
            )
        )

        self.assertEqual(config.starred_username, "silascroe")

    def test_rejects_invalid_public_starred_username(self):
        for username in ("", "silas croe", "owner/repo", 42):
            with self.subTest(username=username):
                with self.assertRaises(ConfigError):
                    load_config(
                        self.write_config(
                            {"repositories": [], "starred_username": username}
                        )
                    )

    def test_duplicate_repositories_are_normalized_once_in_order(self):
        config = load_config(
            self.write_config(
                {"repositories": ["a/one", "b/two", "a/one", "b/two"]}
            )
        )

        self.assertEqual(config.repositories, ("a/one", "b/two"))

    def test_rejects_malformed_repository(self):
        for repository in ("not a repository", "owner", "/name", "owner/", "a/b/c"):
            with self.subTest(repository=repository):
                with self.assertRaises(ConfigError):
                    load_config(self.write_config({"repositories": [repository]}))

    def test_rejects_missing_repositories(self):
        with self.assertRaises(ConfigError):
            load_config(self.write_config({}))

    def test_rejects_non_positive_or_boolean_interval(self):
        for interval in (0, -1, True, 1.5, "90"):
            with self.subTest(interval=interval):
                with self.assertRaises(ConfigError):
                    load_config(
                        self.write_config(
                            {"repositories": [], "poll_interval_seconds": interval}
                        )
                    )

    def test_rejects_invalid_bootstrap_mode(self):
        with self.assertRaises(ConfigError):
            load_config(
                self.write_config(
                    {"repositories": [], "bootstrap_mode": "backfill"}
                )
            )

    def test_rejects_empty_required_paths(self):
        for field in ("state_path", "local_log_path"):
            with self.subTest(field=field):
                with self.assertRaises(ConfigError):
                    load_config(self.write_config({"repositories": [], field: ""}))

    def test_loading_does_not_read_secret_environment_values(self):
        path = self.write_config(
            {
                "repositories": [],
                "discord_webhook_env": "MISSING_OR_SECRET_WEBHOOK",
                "github_token_env": "MISSING_OR_SECRET_TOKEN",
                "llm": {"enabled": True},
            }
        )

        with patch.dict(
            os.environ,
            {
                "MISSING_OR_SECRET_WEBHOOK": "webhook-secret",
                "MISSING_OR_SECRET_TOKEN": "github-secret",
                "OPENAI_API_KEY": "api-secret",
            },
            clear=False,
        ):
            config = load_config(path)

        self.assertEqual(config.discord_webhook_env, "MISSING_OR_SECRET_WEBHOOK")
        self.assertEqual(config.github_token_env, "MISSING_OR_SECRET_TOKEN")


class ModelTests(unittest.TestCase):
    def test_release_identity_is_namespaced_by_repository(self):
        release = Release("owner/repo", "123", "v1", "Version 1", "", "url", None)
        self.assertEqual(release.identity, "owner/repo:123")

    def test_judgment_is_value_object(self):
        judgment = Judgment(True, "Useful change", "New capability")
        self.assertTrue(judgment.interesting)
        self.assertEqual(judgment.summary, "Useful change")


if __name__ == "__main__":
    unittest.main()
