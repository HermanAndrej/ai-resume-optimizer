import sqlite3
from typing import Any

from pydantic import ValidationError

from backend.models import CompatibilityScore
from backend.prompts.compatibility import COMPATIBILITY_SYSTEM
from backend.services.llm_client import LLMInvalidJSONError, call_llm, parse_llm_json


def score_compatibility(
    profile_text: str,
    jd_text: str,
    db_conn: sqlite3.Connection | None = None,
    application_id: str | None = None,
) -> tuple[CompatibilityScore, dict[str, Any]]:
    """Score how well a profile matches a job description.

    Returns (CompatibilityScore, usage_info). Raises LLMInvalidJSONError
    if the LLM returns malformed JSON or a schema-mismatched response.
    """
    user_message = f"PROFILE:\n{profile_text}\n\nJOB DESCRIPTION:\n{jd_text}"

    response_text, usage_info = call_llm(
        system=COMPATIBILITY_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        model="claude-sonnet-4-6",
        operation="compatibility_score",
        application_id=application_id,
        db_conn=db_conn,
        max_tokens=1024,
        use_cache=True,
    )

    data = parse_llm_json(response_text)

    try:
        score = CompatibilityScore.model_validate(data)
    except (ValidationError, TypeError) as exc:
        raise LLMInvalidJSONError(
            f"LLM response did not match CompatibilityScore schema: {exc}"
        ) from exc

    return score, usage_info
