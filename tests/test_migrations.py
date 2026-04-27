from pathlib import Path

from backend.db import get_connection, run_migrations


EXPECTED_TABLES = {
    "schema_version",
    "profile",
    "profile_links",
    "experience",
    "experience_bullets",
    "education",
    "skills",
    "projects",
    "certifications",
    "custom_sections",
    "applications",
    "tailored_resumes",
    "chat_messages",
    "pending_suggestions",
    "usage_log",
}


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r["name"] for r in rows}


def test_fresh_db_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"

    run_migrations(db_path)

    assert db_path.exists()
    conn = get_connection(db_path)
    try:
        assert _tables(conn) == EXPECTED_TABLES
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert version == 2
        profile = conn.execute("SELECT id FROM profile").fetchone()
        assert profile["id"] == 1
        # V2 columns exist on applications
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(applications)").fetchall()}
        assert {"status", "notes", "source_url"}.issubset(cols)
    finally:
        conn.close()


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"

    run_migrations(db_path)
    run_migrations(db_path)

    conn = get_connection(db_path)
    try:
        assert _tables(conn) == EXPECTED_TABLES
        version_rows = conn.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        assert [r["version"] for r in version_rows] == [1, 2]
        profile_count = conn.execute("SELECT COUNT(*) AS n FROM profile").fetchone()["n"]
        assert profile_count == 1
    finally:
        conn.close()
