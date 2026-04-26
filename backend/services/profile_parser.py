"""Parses raw resume text into a structured ParsedProfile using the LLM."""
import sqlite3

from pydantic import ValidationError

from backend.models import ParsedProfile
from backend.prompts.profile_parse import PROFILE_PARSE_SYSTEM
from backend.services.llm_client import LLMInvalidJSONError, call_llm, parse_llm_json


def parse_resume_text(
    text: str,
    db_conn: sqlite3.Connection | None = None,
    application_id: str | None = None,
) -> tuple[ParsedProfile, dict]:
    """Send resume text to Haiku and return (ParsedProfile, usage_info).

    usage_info contains model, token counts, and cost_cents.
    Raises LLMInvalidJSONError if the response cannot be parsed or validated.
    """
    response_text, usage_info = call_llm(
        system=PROFILE_PARSE_SYSTEM,
        messages=[{"role": "user", "content": text}],
        model="claude-haiku-4-5-20251001",
        operation="parse_resume",
        application_id=application_id,
        db_conn=db_conn,
        max_tokens=4096,
        use_cache=True,
    )

    data = parse_llm_json(response_text)

    try:
        return ParsedProfile.model_validate(data), usage_info
    except ValidationError as exc:
        raise LLMInvalidJSONError(
            f"LLM returned JSON that failed schema validation: {exc}"
        ) from exc
