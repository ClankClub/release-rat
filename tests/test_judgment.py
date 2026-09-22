import json
import unittest
from unittest import mock

from repo_rat.config import LLMConfig
from repo_rat.judgment import FallbackJudge, HeuristicJudge, OpenAICompatibleJudge
from repo_rat.models import Release


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


def llm_config():
    return LLMConfig(
        enabled=True,
        base_url_env="TEST_LLM_BASE_URL",
        api_key_env="TEST_LLM_API_KEY",
        model_env="TEST_LLM_MODEL",
        default_base_url="https://llm.example.test/v1/",
        default_model="test-model",
    )


class FakeResponse:
    status = 200

    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(
            {"choices": [{"message": {"content": self.content}}]}
        ).encode("utf-8")


class FakeTransport:
    def __init__(self, content):
        self.content = content
        self.requests = []

    def __call__(self, request, *, timeout=None):
        self.requests.append(request)
        return FakeResponse(self.content)


class JudgmentTests(unittest.TestCase):
    def test_heuristic_judge_marks_security_release_interesting(self):
        release = make_release(
            tag_name="v4.0.0",
            body="This release fixes CVE-2026-1234 and changes the default auth flow.",
        )

        result = HeuristicJudge().judge(release)

        self.assertTrue(result.interesting)
        self.assertIn("CVE", result.summary)

    def test_heuristic_judge_marks_documentation_only_release_uninteresting(self):
        result = HeuristicJudge().judge(
            make_release(name="Documentation update", body="Docs typo fixes only.")
        )

        self.assertFalse(result.interesting)

    def test_heuristic_summary_uses_first_non_heading_sentence(self):
        result = HeuristicJudge().judge(
            make_release(body="# Changes\n- Faster startup. It also uses less memory.")
        )

        self.assertEqual(result.summary, "Faster startup.")

    @mock.patch.dict("os.environ", {"TEST_LLM_API_KEY": "test-key"})
    def test_invalid_llm_json_uses_heuristic_fallback(self):
        primary = OpenAICompatibleJudge(
            config=llm_config(), transport=FakeTransport("{bad")
        )

        result = FallbackJudge(primary, HeuristicJudge()).judge(
            make_release(body="New performance improvements reduce startup time.")
        )

        self.assertTrue(result.interesting)
        self.assertIn("performance", result.summary.lower())

    @mock.patch.dict("os.environ", {"TEST_LLM_API_KEY": "test-key"})
    def test_llm_response_without_string_summary_uses_heuristic_fallback(self):
        primary = OpenAICompatibleJudge(
            config=llm_config(),
            transport=FakeTransport('{"interesting": true, "summary": 42}'),
        )

        result = FallbackJudge(primary, HeuristicJudge()).judge(
            make_release(body="New performance improvements reduce startup time.")
        )

        self.assertTrue(result.interesting)
        self.assertIn("performance", result.summary.lower())

    @mock.patch.dict("os.environ", {"TEST_LLM_API_KEY": "test-key"})
    def test_llm_request_bounds_notes_and_demands_json(self):
        transport = FakeTransport(
            '{"interesting": true, "summary": "Meaningful release", "reason": "Feature"}'
        )
        release = make_release(body="x" * 12_500)

        result = OpenAICompatibleJudge(llm_config(), transport).judge(release)
        request_body = json.loads(transport.requests[0].data)
        user_message = request_body["messages"][1]["content"]
        system_message = request_body["messages"][0]["content"]

        self.assertTrue(result.interesting)
        self.assertEqual(transport.requests[0].full_url, "https://llm.example.test/v1/chat/completions")
        self.assertNotIn("temperature", request_body)
        self.assertIn("JSON", system_message)
        self.assertTrue(user_message.endswith("x" * 12_000))
        self.assertIn("acme/tool", user_message)
        self.assertIn("v1.2.3", user_message)

    def test_unconfigured_llm_uses_heuristic_fallback(self):
        result = FallbackJudge(
            OpenAICompatibleJudge(llm_config(), FakeTransport("unused")),
            HeuristicJudge(),
        ).judge(make_release(body="New performance improvements reduce startup time."))

        self.assertTrue(result.interesting)

    @mock.patch.dict("os.environ", {"TEST_LLM_API_KEY": "test-key"})
    def test_transport_failure_uses_heuristic_fallback(self):
        def unavailable_transport(request, *, timeout=None):
            raise RuntimeError("network unavailable")

        result = FallbackJudge(
            OpenAICompatibleJudge(llm_config(), unavailable_transport), HeuristicJudge()
        ).judge(make_release(body="New performance improvements reduce startup time."))

        self.assertTrue(result.interesting)


if __name__ == "__main__":
    unittest.main()
