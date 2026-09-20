import tempfile
import unittest
from pathlib import Path

from release_rat.config import AppConfig, LLMConfig
from release_rat.delivery import DeliveryResult
from release_rat.github import GitHubError
from release_rat.judgment import JudgmentError
from release_rat.models import Judgment, Release
from release_rat.runner import ReleaseRat
from release_rat.state import StateStore


def make_release(**overrides):
    values = {
        "repository": "acme/tool",
        "release_id": "1",
        "tag_name": "v1.2.3",
        "name": "Tool release",
        "body": "Routine maintenance.",
        "html_url": "https://example.test/releases/v1.2.3",
        "published_at": "2026-09-20T12:00:00Z",
    }
    values.update(overrides)
    return Release(**values)


def make_config(repositories, state_path):
    return AppConfig(
        repositories=tuple(repositories),
        poll_interval_seconds=3600,
        include_prereleases=False,
        bootstrap_mode="seed",
        state_path=state_path,
        local_log_path=state_path.with_suffix(".jsonl"),
        discord_webhook_env="DISCORD_WEBHOOK_URL",
        github_token_env="GITHUB_TOKEN",
        llm=LLMConfig(
            enabled=False,
            base_url_env="OPENAI_BASE_URL",
            api_key_env="OPENAI_API_KEY",
            model_env="RELEASE_RAT_MODEL",
            default_base_url="https://api.openai.com/v1",
            default_model="gpt-5-mini",
        ),
    )


class FakeGitHub:
    def __init__(self, releases_by_repository):
        self.releases_by_repository = releases_by_repository

    def fetch_releases(self, repository, include_prereleases):
        result = self.releases_by_repository[repository]
        if isinstance(result, Exception):
            raise result
        return result


class FakeJudge:
    def __init__(self, judgments, errors=()):
        self.judgments = judgments
        self.errors = set(errors)
        self.calls = []

    def judge(self, release):
        self.calls.append(release.release_id)
        if release.release_id in self.errors:
            raise JudgmentError("judgment unavailable")
        return self.judgments[release.release_id]


class FakeDelivery:
    def __init__(self):
        self.calls = []

    def deliver(self, release, judgment):
        self.calls.append((release.release_id, judgment.summary))
        return DeliveryResult(channel="test", detail="delivered")


class FailOnceDelivery(FakeDelivery):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.persisted_judgments = []
        self.should_fail = True

    def deliver(self, release, judgment):
        stored_release = self.state.get_releases(release.repository)[0]
        self.persisted_judgments.append(
            (stored_release.status, stored_release.summary, stored_release.reason)
        )
        self.calls.append((release.release_id, judgment.summary))
        if self.should_fail:
            self.should_fail = False
            raise TimeoutError("delivery timed out")
        return DeliveryResult(channel="test", detail="delivered")


class TrackingStateStore(StateStore):
    def __init__(self, path):
        super().__init__(path)
        self.last_run_id = None

    def start_run(self, mode, started_at=None):
        self.last_run_id = super().start_run(mode, started_at)
        return self.last_run_id


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state = TrackingStateStore(Path(self.temp_dir.name) / "state.db")
        self.state.__enter__()
        self.addCleanup(self.state.__exit__, None, None, None)
        self.github = FakeGitHub({"acme/tool": []})
        self.judge = FakeJudge({})
        self.delivery = FakeDelivery()

    def make_rat(self, initial_releases, repositories=("acme/tool",)):
        self.github.releases_by_repository = {repository: [] for repository in repositories}
        self.github.releases_by_repository["acme/tool"] = initial_releases
        return ReleaseRat(
            make_config(repositories, self.state.path),
            self.github,
            self.state,
            self.judge,
            self.delivery,
        )

    def test_first_normal_poll_seeds_without_reporting(self):
        release = make_release(release_id="1", body="New feature")
        self.judge.judgments[release.release_id] = Judgment(True, "Feature", "new feature")
        rat = self.make_rat([release])

        summary = rat.poll("normal")

        self.assertEqual(summary.reported, 0)
        self.assertEqual(summary.seeded, 1)
        self.assertEqual(self.delivery.calls, [])

    def test_new_release_is_reported_once_across_two_polls(self):
        release = make_release(release_id="2", body="Breaking change")
        self.judge.judgments[release.release_id] = Judgment(True, "Breaking change", "breaking")
        self.github.releases_by_repository = {"acme/tool": []}
        rat = ReleaseRat(
            make_config(("acme/tool",), self.state.path),
            self.github,
            self.state,
            self.judge,
            self.delivery,
        )

        self.assertEqual(rat.poll("normal").reported, 0)
        self.github.releases_by_repository["acme/tool"] = [release]
        self.assertEqual(rat.poll("normal").reported, 1)
        self.assertEqual(rat.poll("normal").reported, 0)

        self.assertEqual(len(self.delivery.calls), 1)

    def test_empty_normal_poll_persists_a_baseline_for_the_next_process(self):
        self.github.releases_by_repository = {"acme/tool": []}
        first_rat = ReleaseRat(
            make_config(("acme/tool",), self.state.path),
            self.github,
            self.state,
            self.judge,
            self.delivery,
        )
        first_rat.poll("normal")
        self.state.__exit__(None, None, None)
        reopened_state = StateStore(self.state.path)
        reopened_state.__enter__()
        self.addCleanup(reopened_state.__exit__, None, None, None)
        release = make_release(release_id="persistent", body="Security fix")
        self.judge.judgments[release.release_id] = Judgment(
            True, "Security fix", "security"
        )
        self.github.releases_by_repository["acme/tool"] = [release]
        second_rat = ReleaseRat(
            make_config(("acme/tool",), self.state.path),
            self.github,
            reopened_state,
            self.judge,
            self.delivery,
        )

        summary = second_rat.poll("normal")

        self.assertEqual(summary.reported, 1)
        self.assertEqual(self.delivery.calls, [("persistent", "Security fix")])

    def test_backfill_reports_seeded_release(self):
        release = make_release(release_id="3", body="Security fix")
        self.judge.judgments[release.release_id] = Judgment(True, "Security fix", "security")
        rat = self.make_rat([release])

        rat.poll("normal")
        summary = rat.poll("backfill")

        self.assertEqual(summary.reported, 1)
        self.assertEqual(self.delivery.calls, [("3", "Security fix")])

    def test_delivery_failure_preserves_judgment_retries_and_finishes_run(self):
        self.github.releases_by_repository = {"acme/tool": []}
        baseline_rat = ReleaseRat(
            make_config(("acme/tool",), self.state.path),
            self.github,
            self.state,
            self.judge,
            self.delivery,
        )
        baseline_rat.poll("normal")
        release = make_release(release_id="retry", body="Security fix")
        self.judge.judgments[release.release_id] = Judgment(
            True, "Security fix", "security"
        )
        self.github.releases_by_repository["acme/tool"] = [release]
        delivery = FailOnceDelivery(self.state)
        rat = ReleaseRat(
            make_config(("acme/tool",), self.state.path),
            self.github,
            self.state,
            self.judge,
            delivery,
        )

        failed_summary = rat.poll("normal")
        failed_row = self.state.get_releases("acme/tool")[0]
        failed_run = self.state.get_run(self.state.last_run_id)
        retry_summary = rat.poll("normal")
        delivered_row = self.state.get_releases("acme/tool")[0]

        self.assertEqual(failed_summary.reported, 0)
        self.assertEqual(failed_summary.errors, 1)
        self.assertEqual(
            delivery.persisted_judgments[0], ("interesting", "Security fix", "security")
        )
        self.assertEqual(failed_row.status, "interesting")
        self.assertEqual(failed_row.summary, "Security fix")
        self.assertEqual(failed_row.reason, "security")
        self.assertIsNotNone(failed_run["finished_at"])
        self.assertEqual(failed_run["errors"], 1)
        self.assertIn("delivery failed (TimeoutError)", failed_run["error_text"])
        self.assertEqual(retry_summary.reported, 1)
        self.assertEqual(retry_summary.judged, 0)
        self.assertEqual(self.judge.calls, ["retry"])
        self.assertEqual(delivery.calls, [("retry", "Security fix"), ("retry", "Security fix")])
        self.assertEqual(delivered_row.delivered_via, "test")

    def test_uninteresting_release_is_judged_once_and_never_delivered(self):
        release = make_release(release_id="4", body="Documentation update")
        self.judge.judgments[release.release_id] = Judgment(False, "Docs", "routine")
        self.github.releases_by_repository = {"acme/tool": []}
        rat = ReleaseRat(
            make_config(("acme/tool",), self.state.path),
            self.github,
            self.state,
            self.judge,
            self.delivery,
        )
        rat.poll("normal")
        self.github.releases_by_repository["acme/tool"] = [release]

        summary = rat.poll("normal")
        second_summary = rat.poll("normal")

        self.assertEqual(summary.judged, 1)
        self.assertEqual(summary.ignored, 1)
        self.assertEqual(second_summary.judged, 0)
        self.assertEqual(self.judge.calls, ["4"])
        self.assertEqual(self.delivery.calls, [])

    def test_repository_error_does_not_block_healthy_repository(self):
        healthy_release = make_release(
            repository="acme/healthy", release_id="5", body="Security fix"
        )
        self.judge.judgments[healthy_release.release_id] = Judgment(
            True, "Security fix", "security"
        )
        self.github.releases_by_repository = {
            "acme/broken": GitHubError("unavailable"),
            "acme/healthy": [],
        }
        rat = ReleaseRat(
            make_config(("acme/broken", "acme/healthy"), self.state.path),
            self.github,
            self.state,
            self.judge,
            self.delivery,
        )
        rat.poll("normal")
        self.github.releases_by_repository["acme/healthy"] = [healthy_release]

        summary = rat.poll("normal")

        self.assertEqual(summary.repository_errors, 1)
        self.assertEqual(summary.errors, 1)
        self.assertEqual(summary.reported, 1)
        self.assertEqual(self.delivery.calls, [("5", "Security fix")])


if __name__ == "__main__":
    unittest.main()
