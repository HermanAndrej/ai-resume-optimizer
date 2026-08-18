import os
import time
import json
import re
from typing import Optional, Iterator
import sqlite3

import anthropic


client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL_PRICING = {
    # VERIFY at https://docs.anthropic.com/en/docs/about-claude/models
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},
    "claude-opus-4-7":           {"input": 15.00, "output": 75.00},
}

DEFAULT_MODEL = "claude-sonnet-4-6"
VALIDATION_MODEL = "claude-haiku-4-5-20251001"


class LLMError(Exception):
    pass


class LLMAuthError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMBudgetError(LLMError):
    pass


class LLMInvalidJSONError(LLMError):
    def __init__(self, raw_response: str):
        super().__init__(f"Invalid JSON in LLM response: {raw_response[:200]}...")
        self.raw_response = raw_response


def calculate_cost_cents(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return (input_cost + output_cost) * 100


def _log_usage(
    db_conn: Optional[sqlite3.Connection],
    project_id: Optional[str],
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Optional[float]:
    if not db_conn:
        return None
    cost = calculate_cost_cents(model, input_tokens, output_tokens)
    db_conn.execute(
        """INSERT INTO usage_log (project_id, operation, model, input_tokens, output_tokens, cost_cents)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (project_id, operation, model, input_tokens, output_tokens, cost),
    )
    db_conn.commit()
    return cost


def call_llm(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    operation: str = "chat",
    project_id: Optional[str] = None,
    db_conn: Optional[sqlite3.Connection] = None,
    max_retries: int = 3,
) -> tuple[str, dict]:
    """Non-streaming LLM call. Returns (response_text, usage_info)."""
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            in_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens
            cost = _log_usage(db_conn, project_id, operation, model, in_tok, out_tok)
            return response.content[0].text, {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_cents": cost,
                "model": model,
            }
        except anthropic.AuthenticationError:
            raise LLMAuthError("Invalid or missing API key. Check your .env file.")
        except anthropic.RateLimitError as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise LLMRateLimitError("Rate limit exceeded after retries. Try again shortly.")
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e).lower():
                raise LLMBudgetError("Your Anthropic account has insufficient credit.")
            raise LLMError(str(e))
        except anthropic.APIError as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise LLMError(str(e))

    raise LLMError(f"LLM call failed after {max_retries} retries: {last_error}")


def stream_llm(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    operation: str = "chat",
    project_id: Optional[str] = None,
    db_conn: Optional[sqlite3.Connection] = None,
) -> Iterator[tuple[str, Optional[dict]]]:
    """Streaming LLM call. Yields (text_chunk, usage_info); usage_info only on final chunk."""
    try:
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text, None

            final = stream.get_final_message()
            in_tok = final.usage.input_tokens
            out_tok = final.usage.output_tokens
            cost = _log_usage(db_conn, project_id, operation, model, in_tok, out_tok)
            yield "", {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_cents": cost,
                "model": model,
            }
    except anthropic.AuthenticationError:
        raise LLMAuthError("Invalid or missing API key.")
    except anthropic.RateLimitError:
        raise LLMRateLimitError("Rate limit exceeded.")
    except anthropic.APIError as e:
        raise LLMError(str(e))


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        raise LLMInvalidJSONError(text)
