import tempfile
import unittest
from pathlib import Path

from release_rat.models import Judgment, Release
from release_rat.state import StateStore


def make_release(release_id="101", published_at="2026-09-19T12:00:00+00:00"):
    return Release(
        repository="python/cpython",
        release_id=release_id,
        tag_name=f"v{release_id}",
        name=f"Release {release_id}",
        body="A meaningful change.",
        html_url=f"https://example.test/releases/{release_id}",
        published_at=published_at,
    )


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "state.db"

    def test_insert_is_idempotent_and_pending_release_is_a_candidate(self):
        release = make_release(release_id="101")
        with StateStore(self.db_path) as state:
            self.assertTrue(state.insert_release(release))
            self.assertFalse(state.insert_release(release))
            rows = state.candidates("python/cpython", include_seeded=False)

        self.assertEqual([row.release_id for row in rows], ["101"])
        self.assertEqual(rows[0].status, "pending")

    def test_insert_releases_rolls_back_the_whole_batch_after_failure(self):
        class FailingStateStore(StateStore):
            def __init__(self, path):
                super().__init__(path)
                self.insert_count = 0

            def _insert_release(self, release):
                self.insert_count += 1
                inserted = super()._insert_release(release)
                if self.insert_count == 2:
                    raise RuntimeError("injected batch failure")
                return inserted

        with FailingStateStore(self.db_path) as state:
            with self.assertRaisesRegex(RuntimeError, "injected batch failure"):
                state.insert_releases([make_release("first"), make_release("second")])

            self.assertEqual(state.get_releases("python/cpython"), [])

    def test_seeded_release_is_only_backfill_candidate(self):
        release = make_release(release_id="102")
        with StateStore(self.db_path) as state:
            state.insert_release(release)
            state.seed_repository("python/cpython")
            self.assertEqual(state.candidates("python/cpython", False), [])
            self.assertEqual(len(state.candidates("python/cpython", True)), 1)

    def test_candidates_include_failed_rows_and_order_null_publication_first(self):
        with StateStore(self.db_path) as state:
            state.insert_release(make_release("published", "2026-09-19T12:00:00Z"))
            state.insert_release(make_release("older", "2026-09-18T12:00:00Z"))
            state.insert_release(make_release("unknown", None))
            state.save_judgment(
                "python/cpython", "published", None, error="temporary failure"
            )

            rows = state.candidates("python/cpython")

        self.assertEqual([row.release_id for row in rows], ["unknown", "older", "published"])
        self.assertEqual(rows[-1].status, "failed")
        self.assertEqual(rows[-1].reason, "temporary failure")

    def test_judgments_delivery_and_persistence_survive_reopen(self):
        interesting = make_release("interesting")
        uninteresting = make_release("uninteresting")
        with StateStore(self.db_path) as state:
            state.insert_releases([interesting, uninteresting])
            self.assertTrue(
                state.save_judgment(
                    "python/cpython",
                    "interesting",
                    Judgment(True, "New capability", "User-facing change"),
                )
            )
            self.assertTrue(
                state.save_judgment(
                    "python/cpython",
                    "uninteresting",
                    Judgment(False, "Routine maintenance", "Dependency refresh"),
                )
            )
            self.assertTrue(
                state.mark_delivery(
                    "python/cpython", "interesting", "discord", "2026-09-20T00:00:00Z"
                )
            )
            self.assertFalse(
                state.mark_delivery(
                    "python/cpython", "interesting", "local", "2026-09-20T01:00:00Z"
                )
            )

        with StateStore(self.db_path) as state:
            rows = {
                row.release_id: row
                for row in state.get_releases("python/cpython")
            }

        self.assertEqual(rows["interesting"].status, "interesting")
        self.assertEqual(rows["interesting"].summary, "New capability")
        self.assertEqual(rows["interesting"].delivered_via, "discord")
        self.assertEqual(rows["interesting"].delivered_at, "2026-09-20T00:00:00Z")
        self.assertEqual(rows["uninteresting"].status, "uninteresting")
        self.assertEqual(rows["uninteresting"].summary, "Routine maintenance")

    def test_delivery_failure_makes_interesting_release_retryable_without_losing_judgment(self):
        with StateStore(self.db_path) as state:
            state.insert_release(make_release("delivery-retry"))
            state.save_judgment(
                "python/cpython",
                "delivery-retry",
                Judgment(True, "New capability", "User-facing change"),
            )

            self.assertTrue(state.mark_delivery_failed("python/cpython", "delivery-retry"))
            row = state.get_releases("python/cpython")[0]
            candidates = state.candidates("python/cpython")

        self.assertEqual(row.status, "interesting")
        self.assertEqual(row.summary, "New capability")
        self.assertEqual(row.reason, "User-facing change")
        self.assertEqual([candidate.release_id for candidate in candidates], ["delivery-retry"])

    def test_run_recording_stores_summary_and_finish_timestamp(self):
        with StateStore(self.db_path) as state:
            run_id = state.start_run("normal", started_at="2026-09-20T00:00:00Z")
            state.finish_run(
                run_id,
                finished_at="2026-09-20T00:05:00Z",
                fetched=3,
                judged=2,
                reported=1,
                errors=1,
                error_text="one repository failed",
            )
            run = state.get_run(run_id)

        self.assertEqual(run["mode"], "normal")
        self.assertEqual(run["fetched"], 3)
        self.assertEqual(run["judged"], 2)
        self.assertEqual(run["reported"], 1)
        self.assertEqual(run["errors"], 1)
        self.assertEqual(run["error_text"], "one repository failed")
        self.assertEqual(run["finished_at"], "2026-09-20T00:05:00Z")


if __name__ == "__main__":
    unittest.main()
