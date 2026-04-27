"""Unit tests for compat_scorer (LLM mocked — no real API calls)."""
import json
from unittest.mock import patch

import pytest

from backend.models import CompatibilityScore
from backend.services.llm_client import LLMInvalidJSONError
from backend.services.compat_scorer import score_compatibility


CANNED_SCORE = {
    "overall_fit_score": 7,
    "strengths": [
        "5 years of Python matches backend language requirement",
        "FastAPI experience aligns with REST API framework specified",
    ],
    "gaps": [
        "No Kubernetes experience; JD requires container orchestration",
    ],
    "recommendations": [
        "Add Kubernetes or Docker Swarm exposure from personal projects",
        "Quantify system scale to strengthen credibility",
    ],
}

CANNED_USAGE = {
    "model": "claude-sonnet-4-6",
    "input_tokens": 500,
    "output_tokens": 100,
    "cache_creation_input_tokens": 400,
    "cache_read_input_tokens": 0,
    "cost_cents": 0.25,
}


class TestScoreCompatibility:
    def test_returns_compatibility_score(self):
        with patch(
            "backend.services.compat_scorer.call_llm",
            return_value=(json.dumps(CANNED_SCORE), CANNED_USAGE),
        ):
            score, usage = score_compatibility("my profile", "some job description")

        assert isinstance(score, CompatibilityScore)
        assert score.overall_fit_score == 7
        assert usage["cost_cents"] == 0.25

    def test_strengths_and_gaps_populated(self):
        with patch(
            "backend.services.compat_scorer.call_llm",
            return_value=(json.dumps(CANNED_SCORE), CANNED_USAGE),
        ):
            score, _ = score_compatibility("profile", "jd")

        assert len(score.strengths) == 2
        assert len(score.gaps) == 1
        assert len(score.recommendations) == 2

    def test_invalid_json_raises(self):
        with patch(
            "backend.services.compat_scorer.call_llm",
            return_value=("not valid json at all", {}),
        ):
            with pytest.raises(LLMInvalidJSONError):
                score_compatibility("profile", "jd")

    def test_schema_mismatch_raises(self):
        bad_response = json.dumps({"overall_fit_score": "not_an_int"})
        with patch(
            "backend.services.compat_scorer.call_llm",
            return_value=(bad_response, {}),
        ):
            with pytest.raises(LLMInvalidJSONError):
                score_compatibility("profile", "jd")

    def test_score_out_of_range_raises(self):
        out_of_range = json.dumps({**CANNED_SCORE, "overall_fit_score": 11})
        with patch(
            "backend.services.compat_scorer.call_llm",
            return_value=(out_of_range, {}),
        ):
            with pytest.raises((LLMInvalidJSONError, Exception)):
                score_compatibility("profile", "jd")

    def test_passes_application_id_to_llm(self):
        with patch(
            "backend.services.compat_scorer.call_llm",
            return_value=(json.dumps(CANNED_SCORE), CANNED_USAGE),
        ) as mock_llm:
            score_compatibility("profile", "jd", application_id="abc123")
            call_kwargs = mock_llm.call_args
            assert call_kwargs.kwargs.get("application_id") == "abc123"

    def test_uses_sonnet_model(self):
        with patch(
            "backend.services.compat_scorer.call_llm",
            return_value=(json.dumps(CANNED_SCORE), CANNED_USAGE),
        ) as mock_llm:
            score_compatibility("profile", "jd")
            call_kwargs = mock_llm.call_args
            assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-6"
