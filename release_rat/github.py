"""GitHub REST API release ingestion."""

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .models import Release


class GitHubError(RuntimeError):
    """Raised when GitHub releases cannot be fetched or decoded."""


_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")
_USERNAME = re.compile(r"^[A-Za-z0-9-]+$")
_API_URL = "https://api.github.com"
_API_VERSION = "2022-11-28"
_PAGE_SIZE = 100
_HTTP_TIMEOUT_SECONDS = 30


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ):
        self._token = token
        self._opener = opener

    def fetch_releases(
        self, repository: str, include_prereleases: bool
    ) -> list[Release]:
        if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository):
            raise GitHubError(f"invalid repository: {repository!r}")

        releases = []
        page = 1
        while True:
            payload = self._fetch_page(repository, page)
            if not isinstance(payload, list):
                raise GitHubError("GitHub releases response must be a JSON list")

            for item in payload:
                if not isinstance(item, dict):
                    continue
                if item.get("draft", False) or (
                    item.get("prerelease", False) and not include_prereleases
                ):
                    continue
                releases.append(self._to_release(repository, item))

            if len(payload) < _PAGE_SIZE:
                break
            page += 1

        return releases

    def fetch_public_starred_repositories(self, username: str) -> list[str]:
        """Return the public repositories starred by a GitHub user."""
        if not isinstance(username, str) or not _USERNAME.fullmatch(username):
            raise GitHubError(f"invalid GitHub username: {username!r}")

        repositories = []
        seen = set()
        page = 1
        while True:
            payload = self._fetch_starred_page(username, page)
            if not isinstance(payload, list):
                raise GitHubError("GitHub starred repositories response must be a JSON list")

            for item in payload:
                if not isinstance(item, dict) or item.get("private", False):
                    continue
                repository = item.get("full_name")
                if (
                    isinstance(repository, str)
                    and _REPOSITORY.fullmatch(repository)
                    and repository not in seen
                ):
                    repositories.append(repository)
                    seen.add(repository)

            if len(payload) < _PAGE_SIZE:
                break
            page += 1

        return repositories

    def _fetch_page(self, repository: str, page: int) -> Any:
        url = f"{_API_URL}/repos/{repository}/releases?per_page={_PAGE_SIZE}&page={page}"
        return self._fetch_json(url)

    def _fetch_starred_page(self, username: str, page: int) -> Any:
        url = f"{_API_URL}/users/{username}/starred?per_page={_PAGE_SIZE}&page={page}"
        return self._fetch_json(url)

    def _fetch_json(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
                "User-Agent": "release-rat",
            },
        )
        if self._token:
            request.add_header("Authorization", f"Bearer {self._token}")

        try:
            with self._opener(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                raw_body = response.read()
        except urllib.error.HTTPError as exc:
            message = f"GitHub request failed with HTTP {exc.code}: {exc.reason}"
            raise GitHubError(self._safe_message(message)) from exc
        except urllib.error.URLError as exc:
            raise GitHubError(self._safe_message(f"GitHub request failed: {exc.reason}")) from exc
        except OSError as exc:
            raise GitHubError(self._safe_message(f"GitHub request failed: {exc}")) from exc

        try:
            return json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise GitHubError(f"GitHub returned invalid JSON: {exc}") from exc

    def _safe_message(self, message: str) -> str:
        return message.replace(self._token, "[REDACTED]") if self._token else message

    @staticmethod
    def _to_release(repository: str, item: dict[str, Any]) -> Release:
        tag_name = item.get("tag_name") or ""
        published_at = item.get("published_at")
        html_url = item.get("html_url") or ""
        release_id = item.get("id")
        if release_id is None:
            release_id = f"{tag_name}|{published_at or ''}|{html_url}"

        return Release(
            repository=repository,
            release_id=str(release_id),
            tag_name=str(tag_name),
            name=str(item.get("name") or ""),
            body=str(item.get("body") or ""),
            html_url=str(html_url),
            published_at=str(published_at) if published_at is not None else None,
            prerelease=bool(item.get("prerelease", False)),
        )
