import json
import secrets
import sqlite3

from backend.models import Application, ApplicationSummary, CompatibilityAnalysis


def create_application(
    conn: sqlite3.Connection,
    *,
    job_title: str,
    company: str,
    jd: str,
    analysis_json: str,
    profile_hash: str,
) -> str:
    app_id = secrets.token_urlsafe(8)
    conn.execute(
        """
        INSERT INTO applications
            (id, job_title, company, job_description, compatibility_analysis, profile_snapshot_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (app_id, job_title, company, jd, analysis_json, profile_hash),
    )
    conn.commit()
    return app_id


def get_application(conn: sqlite3.Connection, app_id: str) -> Application | None:
    row = conn.execute(
        """
        SELECT id, job_title, company, job_description, compatibility_analysis,
               profile_snapshot_hash, created_at
        FROM applications WHERE id = ?
        """,
        (app_id,),
    ).fetchone()
    if not row:
        return None

    analysis = CompatibilityAnalysis.model_validate(json.loads(row["compatibility_analysis"]))
    return Application(
        id=row["id"],
        job_title=row["job_title"] or "",
        company=row["company"] or "",
        jd=row["job_description"] or "",
        analysis=analysis,
        profile_hash=row["profile_snapshot_hash"] or "",
        created_at=row["created_at"] or "",
    )


def list_applications(conn: sqlite3.Connection) -> list[ApplicationSummary]:
    rows = conn.execute(
        """
        SELECT id, job_title, company, compatibility_analysis, created_at
        FROM applications WHERE archived = 0 ORDER BY created_at DESC
        """,
    ).fetchall()
    results = []
    for row in rows:
        score = 0
        try:
            data = json.loads(row["compatibility_analysis"] or "{}")
            score = data.get("compatibility_score", {}).get("overall_fit_score", 0)
        except (json.JSONDecodeError, AttributeError):
            pass
        results.append(
            ApplicationSummary(
                id=row["id"],
                job_title=row["job_title"] or "",
                company=row["company"] or "",
                score=score,
                created_at=row["created_at"] or "",
            )
        )
    return results
