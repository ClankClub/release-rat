import json
import unittest
from urllib.error import HTTPError

from release_rat.github import GitHubClient, GitHubError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, *, timeout=None):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def json_response(payload):
    return FakeResponse(payload)


class GitHubClientTests(unittest.TestCase):
    def test_fetch_releases_converts_payload_and_filters_prereleases(self):
        opener = FakeOpener(
            [
                json_response(
                    [
                        {
                            "id": 11,
                            "tag_name": "v2.0.0",
                            "name": "Major release",
                            "body": "Breaking change and faster startup.",
                            "html_url": "https://github.com/acme/tool/releases/tag/v2.0.0",
                            "published_at": "2026-09-19T12:00:00Z",
                            "prerelease": False,
                            "draft": False,
                        },
                        {
                            "id": 12,
                            "tag_name": "v2.1.0-rc1",
                            "prerelease": True,
                            "draft": False,
                        },
                    ]
                )
            ]
        )

        releases = GitHubClient(opener=opener).fetch_releases("acme/tool", False)

        self.assertEqual([release.release_id for release in releases], ["11"])
        self.assertEqual(releases[0].repository, "acme/tool")
        self.assertEqual(releases[0].name, "Major release")
        self.assertEqual(
            opener.requests[0].headers["Accept"], "application/vnd.github+json"
        )
        self.assertEqual(
            opener.requests[0].headers["X-github-api-version"], "2022-11-28"
        )
        self.assertEqual(opener.requests[0].headers["User-agent"], "release-rat")
        self.assertNotIn("Authorization", opener.requests[0].headers)

    def test_token_is_sent_as_bearer_header(self):
        opener = FakeOpener([json_response([])])

        GitHubClient(token="secret-token", opener=opener).fetch_releases(
            "acme/tool", True
        )

        self.assertEqual(opener.requests[0].headers["Authorization"], "Bearer secret-token")

    def test_fetches_a_second_page_when_first_page_is_full(self):
        first_page = [
            {
                "id": index,
                "tag_name": f"v{index}",
                "draft": False,
                "prerelease": False,
            }
            for index in range(100)
        ]
        opener = FakeOpener([json_response(first_page), json_response([])])

        releases = GitHubClient(opener=opener).fetch_releases("acme/tool", True)

        self.assertEqual(len(releases), 100)
        self.assertEqual(len(opener.requests), 2)
        self.assertIn("per_page=100&page=1", opener.requests[0].full_url)
        self.assertIn("per_page=100&page=2", opener.requests[1].full_url)

    def test_fallback_identity_and_draft_filtering(self):
        opener = FakeOpener(
            [
                json_response(
                    [
                        {
                            "tag_name": "v1.0.0",
                            "published_at": "2026-09-19T12:00:00Z",
                            "html_url": "https://example.test/v1.0.0",
                            "draft": False,
                        },
                        {"id": 2, "draft": True},
                    ]
                )
            ]
        )

        releases = GitHubClient(opener=opener).fetch_releases("acme/tool", True)

        self.assertEqual(
            releases[0].release_id,
            "v1.0.0|2026-09-19T12:00:00Z|https://example.test/v1.0.0",
        )

    def test_rejects_malformed_repository_before_request(self):
        opener = FakeOpener([])

        with self.assertRaises(GitHubError):
            GitHubClient(opener=opener).fetch_releases("acme/tool/releases", False)

        self.assertEqual(opener.requests, [])

    def test_translates_http_error_without_exposing_token(self):
        token = "secret-token"
        opener = FakeOpener(
            [HTTPError("https://api.github.com", 401, token, {}, None)]
        )

        with self.assertRaises(GitHubError) as raised:
            GitHubClient(token=token, opener=opener).fetch_releases("acme/tool", False)

        self.assertNotIn(token, str(raised.exception))
        self.assertIn("HTTP 401", str(raised.exception))

    def test_translates_malformed_json(self):
        class InvalidResponse(FakeResponse):
            def read(self):
                return b"not json"

        opener = FakeOpener([InvalidResponse(None)])

        with self.assertRaisesRegex(GitHubError, "invalid JSON"):
            GitHubClient(opener=opener).fetch_releases("acme/tool", False)


if __name__ == "__main__":
    unittest.main()
