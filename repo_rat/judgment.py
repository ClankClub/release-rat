"""Release significance judgment with an optional LLM primary."""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

from .config import LLMConfig
from .models import Judgment, Release


_HTTP_TIMEOUT_SECONDS = 30


class JudgmentError(RuntimeError):
    """Raised when a model judgment cannot be obtained or validated."""


class Judge(Protocol):
    def judge(self, release: Release) -> Judgment:
        """Return a significance judgment for a release."""


class HeuristicJudge:
    """A deterministic significance judge suitable for offline operation."""

    _WEIGHTS = (
        ("breaking", 2),
        ("security", 2),
        ("cve-", 2),
        ("deprecated", 1),
        ("performance", 2),
        ("faster", 1),
        ("new feature", 1),
        ("support for", 1),
        ("compatibility", 1),
        ("docs", -1),
        ("documentation", -1),
        ("typo", -1),
        ("dependency bump", -1),
        ("chore", -1),
        ("maintenance", -1),
    )
    _SEMVER = re.compile(r"(?:^|[^0-9])v?(\d+)\.(\d+)\.(\d+)(?:$|[^0-9])")

    def judge(self, release: Release) -> Judgment:
        text = f"{release.name}\n{release.tag_name}\n{release.body}".lower()
        score = sum(weight for signal, weight in self._WEIGHTS if signal in text)
        if self._is_major_release(release.tag_name):
            score += 2
        security_signal = "security" in text or "cve-" in text
        interesting = security_signal or score >= 2
        return Judgment(
            interesting=interesting,
            summary=self._summary(release),
            reason=f"heuristic score: {score}",
        )

    @classmethod
    def _is_major_release(cls, tag_name: str) -> bool:
        match = cls._SEMVER.search(tag_name.lower())
        if not match:
            return False
        major, minor, patch = (int(part) for part in match.groups())
        return major > 0 and minor == 0 and patch == 0

    @staticmethod
    def _summary(release: Release) -> str:
        for line in release.body.splitlines():
            sentence = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line).strip()
            if not sentence or sentence.startswith("#"):
                continue
            return re.split(r"(?<=[.!?])\s+", sentence, maxsplit=1)[0][:360]
        return (release.name.strip() or release.tag_name.strip())[:360]


class OpenAICompatibleJudge:
    """Judge releases through an OpenAI-compatible chat completions endpoint."""

    _SYSTEM_PROMPT = (
        "Judge whether a software release is meaningful to users. Respond with strict "
        'JSON only: {"interesting": boolean, "summary": string, "reason": string}. '
        "The summary must be concise and factual."
    )

    def __init__(
        self,
        config: LLMConfig,
        transport: Callable[..., Any] = urllib.request.urlopen,
    ):
        self._config = config
        self._transport = transport

    def judge(self, release: Release) -> Judgment:
        if not self._config.enabled:
            raise JudgmentError("LLM judgment is disabled")

        try:
            request = self._request(release)
        except (ValueError, TypeError, AttributeError):
            # Neither the endpoint nor chained urllib errors may expose credentials.
            raise JudgmentError("LLM configuration is invalid") from None
        response_payload = self._post(request)
        return self._parse_judgment(response_payload)

    def _request(self, release: Release) -> urllib.request.Request:
        base_url = os.getenv(self._config.base_url_env, self._config.default_base_url).strip()
        api_key = os.getenv(self._config.api_key_env)
        model = os.getenv(self._config.model_env, self._config.default_model).strip()
        if not api_key:
            raise JudgmentError("LLM API key is not configured")

        endpoint = urllib.parse.urlsplit(base_url)
        if (
            endpoint.scheme not in {"http", "https"}
            or not endpoint.hostname
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.query
            or endpoint.fragment
            or endpoint.port == 0
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in base_url)
            or not model
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in model)
        ):
            raise ValueError("invalid endpoint or model")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": self._release_message(release)},
            ],
        }
        return urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "repo-rat",
            },
            method="POST",
        )

    @staticmethod
    def _release_message(release: Release) -> str:
        return (
            f"Repository: {release.repository}\n"
            f"Tag: {release.tag_name}\n"
            f"Name: {release.name}\n"
            f"Published at: {release.published_at or ''}\n"
            f"URL: {release.html_url}\n"
            f"Release notes:\n{release.body[:12_000]}"
        )

    def _post(self, request: urllib.request.Request) -> Any:
        try:
            with self._transport(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", None)
                if status is None:
                    status = response.getcode()
                if not 200 <= status < 300:
                    raise JudgmentError(f"LLM request failed with HTTP {status}")
                raw_body = response.read()
            return json.loads(raw_body)
        except JudgmentError:
            raise
        except urllib.error.HTTPError as exc:
            raise JudgmentError(f"LLM request failed with HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError):
            raise JudgmentError("LLM request failed") from None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise JudgmentError("LLM returned invalid JSON") from None
        except Exception as exc:
            raise JudgmentError(f"LLM request failed ({type(exc).__name__})") from None

    @staticmethod
    def _parse_judgment(payload: Any) -> Judgment:
        try:
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (IndexError, KeyError, TypeError, json.JSONDecodeError):
            raise JudgmentError("LLM response did not contain valid judgment JSON") from None

        interesting = parsed.get("interesting") if isinstance(parsed, dict) else None
        summary = parsed.get("summary") if isinstance(parsed, dict) else None
        reason = parsed.get("reason", "") if isinstance(parsed, dict) else ""
        if type(interesting) is not bool or not isinstance(summary, str) or not summary.strip():
            raise JudgmentError("LLM judgment has an invalid schema")
        return Judgment(
            interesting=interesting,
            summary=summary.strip(),
            reason=reason.strip() if isinstance(reason, str) else "",
        )


class FallbackJudge:
    """Use a fallback judge whenever the primary model judge is unavailable."""

    def __init__(self, primary: Judge, fallback: Judge):
        self._primary = primary
        self._fallback = fallback

    def judge(self, release: Release) -> Judgment:
        try:
            return self._primary.judge(release)
        except JudgmentError:
            return self._fallback.judge(release)
