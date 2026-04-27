import json
import secrets
import sqlite3

from backend.models import (
    STATUS_VALUES,
    Application,
    ApplicationSummary,
    CompatibilityAnalysis,
)
from backend.services.compat_runner import compute_profile_hash


def create_application(
    conn: sqlite3.Connection,
    *,
    job_title: str,
    company: str,
    jd: str,
    analysis_json: str,
    profile_hash: str,
    source_url: str = "",
) -> str:
    app_id = secrets.token_urlsafe(8)
    conn.execute(
        """
        INSERT INTO applications
            (id, job_title, company, job_description, compatibility_analysis,
             profile_snapshot_hash, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (app_id, job_title, company, jd, analysis_json, profile_hash, source_url),
    )
    conn.commit()
    return app_id


def get_application(conn: sqlite3.Connection, app_id: str) -> Application | None:
    row = conn.execute(
        """
        SELECT id, job_title, company, job_description, compatibility_analysis,
               profile_snapshot_hash, status, notes, source_url, archived,
               created_at, updated_at
        FROM applications WHERE id = ?
        """,
        (app_id,),
    ).fetchone()
    if not row:
        return None

    analysis = CompatibilityAnalysis.model_validate(json.loads(row["compatibility_analysis"]))
    current_hash = compute_profile_hash(conn)
    is_stale = (row["profile_snapshot_hash"] or "") != current_hash

    return Application(
        id=row["id"],
        job_title=row["job_title"] or "",
        company=row["company"] or "",
        jd=row["job_description"] or "",
        analysis=analysis,
        profile_hash=row["profile_snapshot_hash"] or "",
        status=row["status"] or "analyzed",
        notes=row["notes"] or "",
        source_url=row["source_url"] or "",
        archived=bool(row["archived"]),
        is_stale=is_stale,
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


def list_applications(
    conn: sqlite3.Connection, include_archived: bool = False
) -> list[ApplicationSummary]:
    if include_archived:
        sql = """
            SELECT id, job_title, company, compatibility_analysis,
                   profile_snapshot_hash, status, archived, created_at
            FROM applications ORDER BY archived ASC, created_at DESC
        """
        rows = conn.execute(sql).fetchall()
    else:
        sql = """
            SELECT id, job_title, company, compatibility_analysis,
                   profile_snapshot_hash, status, archived, created_at
            FROM applications WHERE archived = 0 ORDER BY created_at DESC
        """
        rows = conn.execute(sql).fetchall()

    current_hash = compute_profile_hash(conn) if rows else ""

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
                status=row["status"] or "analyzed",
                archived=bool(row["archived"]),
                is_stale=(row["profile_snapshot_hash"] or "") != current_hash,
                created_at=row["created_at"] or "",
            )
        )
    return results


def is_stale_for(conn: sqlite3.Connection, app_id: str) -> bool:
    row = conn.execute(
        "SELECT profile_snapshot_hash FROM applications WHERE id = ?", (app_id,)
    ).fetchone()
    if not row:
        return False
    return (row["profile_snapshot_hash"] or "") != compute_profile_hash(conn)


def update_metadata(
    conn: sqlite3.Connection,
    app_id: str,
    *,
    status: str,
    notes: str,
    source_url: str,
    jd: str,
) -> bool:
    if status not in STATUS_VALUES:
        raise ValueError(f"Invalid status: {status!r}; must be one of {STATUS_VALUES}")
    cursor = conn.execute(
        """
        UPDATE applications
        SET status = ?, notes = ?, source_url = ?, job_description = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, notes, source_url, jd, app_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def set_archived(conn: sqlite3.Connection, app_id: str, archived: bool) -> bool:
    cursor = conn.execute(
        "UPDATE applications SET archived = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (1 if archived else 0, app_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def update_analysis(
    conn: sqlite3.Connection,
    app_id: str,
    analysis_json: str,
    profile_hash: str,
) -> bool:
    cursor = conn.execute(
        """
        UPDATE applications
        SET compatibility_analysis = ?, profile_snapshot_hash = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (analysis_json, profile_hash, app_id),
    )
    conn.commit()
    return cursor.rowcount > 0
