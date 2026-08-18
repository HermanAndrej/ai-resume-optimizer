import json
import sqlite3
from typing import Optional

from .keyword_analyzer import analyze_keywords
from .llm_client import call_llm, parse_llm_json, DEFAULT_MODEL
from ..prompts.analysis import ANALYSIS_SYSTEM


def _profile_to_text(profile: dict) -> str:
    """Flatten profile dict to plain text for TF-IDF keyword matching."""
    parts: list[str] = []

    pi = profile.get("personal_info") or {}
    if pi.get("full_name"):
        parts.append(pi["full_name"])

    if profile.get("summary"):
        parts.append(profile["summary"])

    for exp in profile.get("experience") or []:
        parts.extend(filter(None, [exp.get("title"), exp.get("company"), exp.get("description")]))
        for bullet in exp.get("bullets") or []:
            parts.append(str(bullet))

    for edu in profile.get("education") or []:
        parts.extend(filter(None, [edu.get("degree"), edu.get("field"), edu.get("institution")]))
        for h in edu.get("highlights") or []:
            parts.append(str(h))

    for group in profile.get("skills") or []:
        if group.get("category"):
            parts.append(group["category"])
        parts.extend(group.get("skills") or [])

    for proj in profile.get("projects") or []:
        parts.extend(filter(None, [proj.get("name"), proj.get("description")]))
        parts.extend(proj.get("tech_stack") or [])
        for bullet in proj.get("bullets") or []:
            parts.append(str(bullet))

    for cert in profile.get("certifications") or []:
        if cert.get("name"):
            parts.append(cert["name"])

    return " ".join(parts)


def run_analysis(
    profile: dict,
    jd_text: str,
    db_conn: Optional[sqlite3.Connection] = None,
) -> dict:
    """Run full compatibility analysis: TF-IDF keyword gap + LLM assessment.

    Returns a merged dict with keyword and LLM analysis results.
    """
    profile_text = _profile_to_text(profile)
    keyword_result = analyze_keywords(profile_text, jd_text)

    user_msg = f"""CANDIDATE PROFILE:
{json.dumps(profile, indent=2, ensure_ascii=False)}

JOB DESCRIPTION:
{jd_text}

KEYWORD PRE-ANALYSIS (TF-IDF):
Matched keywords: {[k["keyword"] for k in keyword_result["matched_keywords"][:15]]}
Missing keywords: {[k["keyword"] for k in keyword_result["missing_keywords"][:15]]}
Keyword match rate: {keyword_result["keyword_score"]}%

Analyze compatibility and return the JSON assessment."""

    text, usage = call_llm(
        model=DEFAULT_MODEL,
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=2048,
        operation="analysis",
        db_conn=db_conn,
    )

    llm_result = parse_llm_json(text)

    return {
        **keyword_result,
        **llm_result,
        "usage": usage,
    }
