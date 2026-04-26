"""Reusable Anthropic LLM client with typed errors, cost tracking, and prompt caching."""
import json
import re
import sqlite3
import time
from typing import Any

import anthropic

# Prices in USD per million tokens. Verify current prices at:
# https://www.anthropic.com/pricing#anthropic-api
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {
        "input_per_m": 0.80,
        "output_per_m": 4.00,
        "cache_write_per_m": 1.00,
        "cache_read_per_m": 0.08,
    },
    "claude-sonnet-4-6": {
        "input_per_m": 3.00,
        "output_per_m": 15.00,
        "cache_write_per_m": 3.75,
        "cache_read_per_m": 0.30,
    },
}


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base error for all LLM client failures."""


class LLMAuthError(LLMError):
    """Invalid or missing API key."""


class LLMRateLimitError(LLMError):
    """Rate limit hit; caller may retry."""


class LLMBudgetError(LLMError):
    """Account has insufficient credits."""


class LLMInvalidJSONError(LLMError):
    """LLM returned text that could not be parsed as JSON."""


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------


def calculate_cost_cents(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float:
    """Return total cost in US cents for a single API call."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0

    regular_input = input_tokens - cache_creation_input_tokens - cache_read_input_tokens
    regular_input = max(regular_input, 0)

    cost_usd = (
        regular_input * pricing["input_per_m"]
        + output_tokens * pricing["output_per_m"]
        + cache_creation_input_tokens * pricing["cache_write_per_m"]
        + cache_read_input_tokens * pricing["cache_read_per_m"]
    ) / 1_000_000

    return round(cost_usd * 100, 6)


def _log_usage(
    db_conn: sqlite3.Connection,
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_cents: float,
    application_id: str | None = None,
) -> None:
    db_conn.execute(
        """
        INSERT INTO usage_log
            (application_id, operation, model, input_tokens, output_tokens, cost_cents)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (application_id, operation, model, input_tokens, output_tokens, cost_cents),
    )
    db_conn.commit()


# ---------------------------------------------------------------------------
# Core call
# ---------------------------------------------------------------------------


def call_llm(
    system: str,
    messages: list[dict[str, Any]],
    *,
    model: str = "claude-haiku-4-5-20251001",
    operation: str = "unknown",
    application_id: str | None = None,
    db_conn: sqlite3.Connection | None = None,
    max_tokens: int = 4096,
    use_cache: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Call the Anthropic API and return (response_text, usage_info).

    Applies prompt caching to the system prompt when use_cache=True.
    Retries on rate limits with exponential backoff (1s, 2s, 4s).
    Translates SDK exceptions to typed LLMError subclasses.
    Logs cost to usage_log when db_conn is provided.
    """
    client = anthropic.Anthropic()

    system_block: Any
    if use_cache:
        system_block = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_block = system

    delays = [1, 2, 4]
    last_exc: Exception | None = None

    for attempt, delay in enumerate([0] + delays):
        if delay:
            time.sleep(delay)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_block,
                messages=messages,
            )
        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            last_exc = exc
            if attempt == len(delays):
                raise LLMRateLimitError(str(exc)) from exc
            continue
        except anthropic.BadRequestError as exc:
            if "credit" in str(exc).lower() or "billing" in str(exc).lower():
                raise LLMBudgetError(str(exc)) from exc
            raise LLMError(str(exc)) from exc
        except anthropic.APIError as exc:
            raise LLMError(str(exc)) from exc

        text = response.content[0].text if response.content else ""
        usage = response.usage

        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0)

        cost = calculate_cost_cents(
            model, input_tokens, output_tokens, cache_creation, cache_read
        )

        usage_info = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation,
            "cache_read_input_tokens": cache_read,
            "cost_cents": cost,
        }

        if db_conn is not None:
            _log_usage(db_conn, operation, model, input_tokens, output_tokens, cost, application_id)

        return text, usage_info

    raise LLMRateLimitError(str(last_exc))


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def parse_llm_json(text: str) -> Any:
    """Parse JSON from LLM output.

    Handles:
    - Plain JSON
    - JSON wrapped in markdown fences (```json ... ``` or ``` ... ```)
    - JSON embedded in prose (finds the first { or [ and attempts to parse from there)

    Raises LLMInvalidJSONError if no valid JSON can be extracted.
    """
    text = text.strip()

    # Try plain parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Find first JSON structure in prose
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        idx = text.find(start_char)
        if idx == -1:
            continue
        # Walk backward from the last matching close to find longest valid JSON
        last = len(text)
        while last > idx:
            last = text.rfind(end_char, idx, last)
            if last == -1:
                break
            try:
                return json.loads(text[idx : last + 1])
            except json.JSONDecodeError:
                pass

    raise LLMInvalidJSONError(f"Could not extract JSON from LLM response: {text[:200]!r}")
