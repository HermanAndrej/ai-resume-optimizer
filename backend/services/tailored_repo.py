import json
import sqlite3

from backend.models import (
    TailoredResume,
    TailoredResumeRow,
    ValidationResult,
)
from backend.services.compat_runner import compute_profile_hash


def _next_version(conn: sqlite3.Connection, application_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM tailored_resumes WHERE application_id = ?",
        (application_id,),
    ).fetchone()
    return (row[0] or 0) + 1


def create_tailored(
    conn: sqlite3.Connection,
    *,
    application_id: str,
    content: TailoredResume,
    validation: ValidationResult,
    profile_hash: str,
    model: str,
    cost_cents: float,
    source: str = "generated",
    parent_version: int | None = None,
) -> int:
    version = _next_version(conn, application_id)
    cursor = conn.execute(
        """
        INSERT INTO tailored_resumes
            (application_id, version, content, validation_json,
             profile_snapshot_hash, model, cost_cents, source, parent_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            version,
            content.model_dump_json(),
            validation.model_dump_json(),
            profile_hash,
            model,
            cost_cents,
            source,
            parent_version,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def _row_to_tailored(conn: sqlite3.Connection, row: sqlite3.Row) -> TailoredResumeRow:
    content = TailoredResume.model_validate(json.loads(row["content"] or "{}"))
    validation_raw = row["validation_json"] or '{"issues": []}'
    validation = ValidationResult.model_validate(json.loads(validation_raw))
    current_hash = compute_profile_hash(conn)
    return TailoredResumeRow(
        id=row["id"],
        application_id=row["application_id"],
        version=row["version"],
        content=content,
        validation=validation,
        profile_hash=row["profile_snapshot_hash"] or "",
        model=row["model"] or "",
        cost_cents=row["cost_cents"] or 0.0,
        created_at=row["created_at"] or "",
        is_stale=(row["profile_snapshot_hash"] or "") != current_hash,
    )


def get_latest_for_application(
    conn: sqlite3.Connection, application_id: str
) -> TailoredResumeRow | None:
    row = conn.execute(
        """
        SELECT id, application_id, version, content, validation_json,
               profile_snapshot_hash, model, cost_cents, created_at
        FROM tailored_resumes
        WHERE application_id = ?
        ORDER BY created_at DESC, version DESC
        LIMIT 1
        """,
        (application_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_tailored(conn, row)


def list_for_application(
    conn: sqlite3.Connection, application_id: str
) -> list[TailoredResumeRow]:
    rows = conn.execute(
        """
        SELECT id, application_id, version, content, validation_json,
               profile_snapshot_hash, model, cost_cents, created_at
        FROM tailored_resumes
        WHERE application_id = ?
        ORDER BY created_at DESC, version DESC
        """,
        (application_id,),
    ).fetchall()
    return [_row_to_tailored(conn, r) for r in rows]


def get_tailored(conn: sqlite3.Connection, tailored_id: int) -> TailoredResumeRow | None:
    row = conn.execute(
        """
        SELECT id, application_id, version, content, validation_json,
               profile_snapshot_hash, model, cost_cents, created_at
        FROM tailored_resumes WHERE id = ?
        """,
        (tailored_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_tailored(conn, row)
