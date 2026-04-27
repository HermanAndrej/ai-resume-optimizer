"""Reusable compatibility analysis pipeline.

Used by both the create-application route and the re-analyze route to ensure
identical behavior across both flows.
"""
import hashlib
import sqlite3
from typing import Any

from backend.models import CompatibilityAnalysis
from backend.services.compat_scorer import score_compatibility
from backend.services.keyword_analysis import compute_overlap, flatten_profile


def compute_profile_hash(conn: sqlite3.Connection) -> str:
    profile_text = flatten_profile(conn)
    return hashlib.sha256(profile_text.encode()).hexdigest()[:16]


def run_analysis(
    conn: sqlite3.Connection,
    jd_text: str,
    application_id: str | None = None,
) -> tuple[CompatibilityAnalysis, str, dict[str, Any]]:
    """Run the full keyword + LLM analysis pipeline.

    Returns (analysis, profile_hash, usage_info).
    """
    profile_text = flatten_profile(conn)
    profile_hash = hashlib.sha256(profile_text.encode()).hexdigest()[:16]

    keyword_overlap = compute_overlap(jd_text, profile_text)
    compat_score, usage_info = score_compatibility(
        profile_text, jd_text, db_conn=conn, application_id=application_id
    )

    analysis = CompatibilityAnalysis(
        keyword_overlap=keyword_overlap,
        compatibility_score=compat_score,
    )
    return analysis, profile_hash, usage_info
