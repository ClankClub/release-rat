import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the Release Rat configuration is invalid."""


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    base_url_env: str
    api_key_env: str
    model_env: str
    default_base_url: str
    default_model: str


@dataclass(frozen=True)
class AppConfig:
    repositories: tuple[str, ...]
    poll_interval_seconds: int
    include_prereleases: bool
    bootstrap_mode: str
    state_path: Path
    local_log_path: Path
    discord_webhook_env: str
    github_token_env: str
    llm: LLMConfig


_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")
_DEFAULTS = {
    "poll_interval_seconds": 3600,
    "include_prereleases": False,
    "bootstrap_mode": "seed",
    "state_path": "state.db",
    "local_log_path": "release-log.jsonl",
    "discord_webhook_env": "DISCORD_WEBHOOK_URL",
    "github_token_env": "GITHUB_TOKEN",
}
_LLM_DEFAULTS = {
    "enabled": True,
    "base_url_env": "OPENAI_BASE_URL",
    "api_key_env": "OPENAI_API_KEY",
    "model_env": "RELEASE_RAT_MODEL",
    "default_base_url": "https://api.openai.com/v1",
    "default_model": "gpt-5-mini",
}


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ConfigError(f"{field} must be a non-empty string")
    return value


def _path(value: Any, field: str, config_path: Path) -> Path:
    value = _string(value, field)
    candidate = Path(value)
    return candidate if candidate.is_absolute() else config_path.parent / candidate


def load_config(path: Path) -> AppConfig:
    """Load and validate configuration without reading any secret values."""
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            raw = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"unable to load configuration {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("configuration must be a JSON object")

    repositories = raw.get("repositories")
    if not isinstance(repositories, list):
        raise ConfigError("repositories must be a list")
    normalized_repositories = []
    seen = set()
    for repository in repositories:
        if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository):
            raise ConfigError(f"invalid repository: {repository!r}")
        if repository not in seen:
            normalized_repositories.append(repository)
            seen.add(repository)

    interval = raw.get("poll_interval_seconds", _DEFAULTS["poll_interval_seconds"])
    if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
        raise ConfigError("poll_interval_seconds must be a positive integer")

    include_prereleases = raw.get(
        "include_prereleases", _DEFAULTS["include_prereleases"]
    )
    if not isinstance(include_prereleases, bool):
        raise ConfigError("include_prereleases must be a boolean")

    bootstrap_mode = raw.get("bootstrap_mode", _DEFAULTS["bootstrap_mode"])
    if bootstrap_mode != "seed":
        raise ConfigError("bootstrap_mode must be 'seed'")

    llm_raw = raw.get("llm", {})
    if not isinstance(llm_raw, dict):
        raise ConfigError("llm must be an object")
    llm_values = {**_LLM_DEFAULTS, **llm_raw}
    if not isinstance(llm_values["enabled"], bool):
        raise ConfigError("llm.enabled must be a boolean")
    llm = LLMConfig(
        enabled=llm_values["enabled"],
        base_url_env=_string(llm_values["base_url_env"], "llm.base_url_env"),
        api_key_env=_string(llm_values["api_key_env"], "llm.api_key_env"),
        model_env=_string(llm_values["model_env"], "llm.model_env"),
        default_base_url=_string(
            llm_values["default_base_url"], "llm.default_base_url"
        ),
        default_model=_string(llm_values["default_model"], "llm.default_model"),
    )

    return AppConfig(
        repositories=tuple(normalized_repositories),
        poll_interval_seconds=interval,
        include_prereleases=include_prereleases,
        bootstrap_mode=bootstrap_mode,
        state_path=_path(
            raw.get("state_path", _DEFAULTS["state_path"]), "state_path", config_path
        ),
        local_log_path=_path(
            raw.get("local_log_path", _DEFAULTS["local_log_path"]),
            "local_log_path",
            config_path,
        ),
        discord_webhook_env=_string(
            raw.get("discord_webhook_env", _DEFAULTS["discord_webhook_env"]),
            "discord_webhook_env",
        ),
        github_token_env=_string(
            raw.get("github_token_env", _DEFAULTS["github_token_env"]),
            "github_token_env",
        ),
        llm=llm,
    )
