"""Resume tailor: structured profile context + LLM generation with no-fabrication prompt."""
import json
import sqlite3
from typing import Any

from pydantic import ValidationError

from backend.models import TailoredResume
from backend.prompts.resume_tailor import TAILOR_SYSTEM
from backend.services.compat_runner import compute_profile_hash
from backend.services.llm_client import LLMInvalidJSONError, call_llm, parse_llm_json

PROFILE_ID = 1
TAILOR_MODEL = "claude-sonnet-4-6"


def build_profile_context(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build a structured JSON view of the source profile for the LLM.

    Includes bullet IDs so the model can cite them via source_bullet_id.
    """
    profile = conn.execute(
        "SELECT full_name, email, phone, location, summary FROM profile WHERE id = ?",
        (PROFILE_ID,),
    ).fetchone()

    personal = {
        "full_name": (profile["full_name"] if profile else "") or "",
        "email": (profile["email"] if profile else "") or "",
        "phone": (profile["phone"] if profile else "") or "",
        "location": (profile["location"] if profile else "") or "",
    }
    summary = (profile["summary"] if profile else "") or ""

    experiences: list[dict[str, Any]] = []
    exp_rows = conn.execute(
        """
        SELECT id, company, title, location, start_date, end_date, description
        FROM experience
        WHERE profile_id = ?
        ORDER BY display_order ASC, id ASC
        """,
        (PROFILE_ID,),
    ).fetchall()
    for exp in exp_rows:
        bullet_rows = conn.execute(
            """
            SELECT id, text FROM experience_bullets
            WHERE experience_id = ?
            ORDER BY display_order ASC, id ASC
            """,
            (exp["id"],),
        ).fetchall()
        experiences.append({
            "id": exp["id"],
            "company": exp["company"] or "",
            "title": exp["title"] or "",
            "location": exp["location"] or "",
            "start_date": exp["start_date"] or "",
            "end_date": exp["end_date"] or "",
            "description": exp["description"] or "",
            "bullets": [
                {"id": b["id"], "text": b["text"] or ""}
                for b in bullet_rows
            ],
        })

    education = [
        {
            "institution": r["institution"] or "",
            "degree": r["degree"] or "",
            "field": r["field"] or "",
            "start_date": r["start_date"] or "",
            "end_date": r["end_date"] or "",
            "gpa": r["gpa"] or "",
            "highlights": r["highlights"] or "",
        }
        for r in conn.execute(
            "SELECT institution, degree, field, start_date, end_date, gpa, highlights "
            "FROM education WHERE profile_id = ? ORDER BY display_order ASC, id ASC",
            (PROFILE_ID,),
        ).fetchall()
    ]

    skills = [
        {"category": r["category"] or "", "skill": r["skill"] or ""}
        for r in conn.execute(
            "SELECT category, skill FROM skills WHERE profile_id = ? "
            "ORDER BY display_order ASC, id ASC",
            (PROFILE_ID,),
        ).fetchall()
        if (r["skill"] or "").strip()
    ]

    projects = [
        {
            "name": r["name"] or "",
            "description": r["description"] or "",
            "tech_stack": r["tech_stack"] or "",
            "url": r["url"] or "",
            "bullets": r["bullets"] or "",
        }
        for r in conn.execute(
            "SELECT name, description, tech_stack, url, bullets FROM projects "
            "WHERE profile_id = ? ORDER BY display_order ASC, id ASC",
            (PROFILE_ID,),
        ).fetchall()
    ]

    certifications = [
        {
            "name": r["name"] or "",
            "issuer": r["issuer"] or "",
            "date": r["date"] or "",
            "url": r["url"] or "",
        }
        for r in conn.execute(
            "SELECT name, issuer, date, url FROM certifications "
            "WHERE profile_id = ? ORDER BY display_order ASC, id ASC",
            (PROFILE_ID,),
        ).fetchall()
    ]

    return {
        "personal": personal,
        "summary": summary,
        "experience": experiences,
        "education": education,
        "skills": skills,
        "projects": projects,
        "certifications": certifications,
    }


def generate_tailored_resume(
    conn: sqlite3.Connection,
    jd_text: str,
    application_id: str | None = None,
) -> tuple[TailoredResume, str, dict[str, Any]]:
    """Generate a tailored resume from the source profile + JD.

    Returns (TailoredResume, profile_hash, usage_info).
    Raises LLMInvalidJSONError if the LLM returns malformed JSON or
    a schema-mismatched response.
    """
    profile_context = build_profile_context(conn)
    profile_hash = compute_profile_hash(conn)

    user_message = (
        f"SOURCE PROFILE (JSON):\n{json.dumps(profile_context, indent=2)}\n\n"
        f"TARGET JOB DESCRIPTION:\n{jd_text}\n\n"
        f"Produce the tailored resume JSON now."
    )

    response_text, usage_info = call_llm(
        system=TAILOR_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
        model=TAILOR_MODEL,
        operation="resume_tailor",
        application_id=application_id,
        db_conn=conn,
        max_tokens=4096,
        use_cache=True,
    )

    data = parse_llm_json(response_text)

    try:
        tailored = TailoredResume.model_validate(data)
    except (ValidationError, TypeError) as exc:
        raise LLMInvalidJSONError(
            f"LLM response did not match TailoredResume schema: {exc}"
        ) from exc

    return tailored, profile_hash, usage_info
