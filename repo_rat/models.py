"""Immutable domain values exchanged by the release pipeline.

Persistent lifecycle metadata belongs to :mod:`repo_rat.state`, rather
than these domain input and judgment models.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Release:
    repository: str
    release_id: str
    tag_name: str
    name: str
    body: str
    html_url: str
    published_at: str | None
    prerelease: bool = False

    @property
    def identity(self) -> str:
        return f"{self.repository}:{self.release_id}"


@dataclass(frozen=True)
class Judgment:
    interesting: bool
    summary: str
    reason: str
