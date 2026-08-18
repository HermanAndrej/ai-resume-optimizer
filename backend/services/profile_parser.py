from .llm_client import call_llm, parse_llm_json, DEFAULT_MODEL
from ..prompts.profile_parse import PROFILE_PARSE_SYSTEM


def parse_resume(text: str, db_conn=None) -> dict:
    """Parse resume plain text into a structured profile dict via LLM."""
    user_msg = f"Parse this resume:\n\n{text}"

    raw, _ = call_llm(
        model=DEFAULT_MODEL,
        system=PROFILE_PARSE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=4096,
        operation="profile_parse",
        db_conn=db_conn,
    )

    return parse_llm_json(raw)
