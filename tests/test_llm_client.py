"""Tests for llm_client: parse_llm_json edge cases and calculate_cost_cents math."""
import pytest

from backend.services.llm_client import (
    LLMInvalidJSONError,
    MODEL_PRICING,
    calculate_cost_cents,
    parse_llm_json,
)


# ---------------------------------------------------------------------------
# parse_llm_json
# ---------------------------------------------------------------------------


class TestParseLLMJson:
    def test_plain_json_object(self):
        result = parse_llm_json('{"name": "Alice", "age": 30}')
        assert result == {"name": "Alice", "age": 30}

    def test_plain_json_array(self):
        result = parse_llm_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_json_fenced_with_json_tag(self):
        text = '```json\n{"key": "value"}\n```'
        assert parse_llm_json(text) == {"key": "value"}

    def test_json_fenced_without_tag(self):
        text = '```\n{"key": "value"}\n```'
        assert parse_llm_json(text) == {"key": "value"}

    def test_json_embedded_in_prose(self):
        text = 'Here is the parsed data: {"name": "Bob"} Hope that helps!'
        assert parse_llm_json(text) == {"name": "Bob"}

    def test_json_embedded_array_in_prose(self):
        text = 'The result is [1, 2, 3] as expected.'
        assert parse_llm_json(text) == [1, 2, 3]

    def test_nested_json_object(self):
        text = '{"outer": {"inner": [1, 2]}}'
        assert parse_llm_json(text) == {"outer": {"inner": [1, 2]}}

    def test_whitespace_padding(self):
        text = '   \n  {"k": "v"}  \n  '
        assert parse_llm_json(text) == {"k": "v"}

    def test_invalid_raises(self):
        with pytest.raises(LLMInvalidJSONError):
            parse_llm_json("This is just plain text with no JSON.")

    def test_partial_json_raises(self):
        with pytest.raises(LLMInvalidJSONError):
            parse_llm_json('{"unclosed": ')

    def test_empty_string_raises(self):
        with pytest.raises(LLMInvalidJSONError):
            parse_llm_json("")

    def test_fenced_with_surrounding_prose(self):
        text = "Sure! Here you go:\n```json\n{\"x\": 1}\n```\nLet me know if you need more."
        assert parse_llm_json(text) == {"x": 1}


# ---------------------------------------------------------------------------
# calculate_cost_cents
# ---------------------------------------------------------------------------


class TestCalculateCostCents:
    def test_zero_tokens(self):
        cost = calculate_cost_cents("claude-haiku-4-5-20251001", 0, 0)
        assert cost == 0.0

    def test_haiku_input_only(self):
        # 1M input tokens at $0.80/M = $0.80 = 80 cents
        cost = calculate_cost_cents("claude-haiku-4-5-20251001", 1_000_000, 0)
        assert abs(cost - 80.0) < 0.001

    def test_haiku_output_only(self):
        # 1M output tokens at $4.00/M = $4.00 = 400 cents
        cost = calculate_cost_cents("claude-haiku-4-5-20251001", 0, 1_000_000)
        assert abs(cost - 400.0) < 0.001

    def test_sonnet_mixed(self):
        # 100k input at $3/M + 10k output at $15/M = $0.30 + $0.15 = $0.45 = 45 cents
        cost = calculate_cost_cents("claude-sonnet-4-6", 100_000, 10_000)
        assert abs(cost - 45.0) < 0.001

    def test_cache_read_cheaper_than_input(self):
        # For haiku: cache_read is $0.08/M vs input $0.80/M
        cost_normal = calculate_cost_cents("claude-haiku-4-5-20251001", 1_000_000, 0)
        cost_cached = calculate_cost_cents(
            "claude-haiku-4-5-20251001", 1_000_000, 0,
            cache_read_input_tokens=1_000_000,
        )
        assert cost_cached < cost_normal

    def test_cache_write_more_expensive_than_input(self):
        # For haiku: cache_write is $1.00/M vs input $0.80/M
        cost_normal = calculate_cost_cents("claude-haiku-4-5-20251001", 1_000_000, 0)
        cost_write = calculate_cost_cents(
            "claude-haiku-4-5-20251001", 1_000_000, 0,
            cache_creation_input_tokens=1_000_000,
        )
        assert cost_write > cost_normal

    def test_unknown_model_returns_zero(self):
        cost = calculate_cost_cents("unknown-model-xyz", 1_000_000, 1_000_000)
        assert cost == 0.0

    def test_both_models_in_pricing(self):
        assert "claude-haiku-4-5-20251001" in MODEL_PRICING
        assert "claude-sonnet-4-6" in MODEL_PRICING

    def test_typical_import_cost_range(self):
        # A typical resume parse: ~2k input + ~1k output with Haiku
        # Should be well under 1 cent
        cost = calculate_cost_cents("claude-haiku-4-5-20251001", 2000, 1000)
        assert cost < 1.0
        assert cost > 0.0
