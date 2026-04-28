import sqlite3
from pathlib import Path
from typing import Generator


# Each migration should only contain schema changes — never INSERT INTO schema_version.
# run_migrations() records the applied version itself after executing the script.
SCHEMA_V1 = """
CREATE TABLE profile (
    id INTEGER PRIMARY KEY,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    location TEXT,
    summary TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE profile_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    url TEXT NOT NULL,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    start_date TEXT,
    end_date TEXT,
    description TEXT,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE experience_bullets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experience_id INTEGER NOT NULL REFERENCES experience(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    tags TEXT,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    institution TEXT NOT NULL,
    degree TEXT,
    field TEXT,
    start_date TEXT,
    end_date TEXT,
    gpa TEXT,
    highlights TEXT,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    skill TEXT NOT NULL,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    tech_stack TEXT,
    url TEXT,
    bullets TEXT,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE certifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    issuer TEXT,
    date TEXT,
    url TEXT,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE custom_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    content TEXT,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE applications (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    job_title TEXT,
    company TEXT,
    job_description TEXT,
    compatibility_analysis TEXT,
    profile_snapshot_hash TEXT,
    archived INTEGER DEFAULT 0
);

CREATE TABLE tailored_resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    generation_notes TEXT,
    source TEXT NOT NULL,
    parent_version INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents REAL,
    model TEXT
);

CREATE TABLE pending_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    suggestion_type TEXT,
    target_section TEXT,
    current_value TEXT,
    proposed_value TEXT,
    rationale TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    application_id TEXT,
    operation TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents REAL
);

INSERT INTO profile (id) VALUES (1);
"""

SCHEMA_V2 = """
ALTER TABLE applications ADD COLUMN status TEXT DEFAULT 'analyzed';
ALTER TABLE applications ADD COLUMN notes TEXT;
ALTER TABLE applications ADD COLUMN source_url TEXT;
"""

SCHEMA_V3 = """
ALTER TABLE tailored_resumes ADD COLUMN validation_json TEXT;
ALTER TABLE tailored_resumes ADD COLUMN profile_snapshot_hash TEXT;
ALTER TABLE tailored_resumes ADD COLUMN model TEXT;
ALTER TABLE tailored_resumes ADD COLUMN cost_cents REAL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_application_created
    ON tailored_resumes (application_id, created_at DESC);
"""

MIGRATIONS: dict[int, str] = {1: SCHEMA_V1, 2: SCHEMA_V2, 3: SCHEMA_V3}


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(db_path: Path) -> None:
    """Apply any unapplied schema versions in order.

    Bootstraps the `schema_version` table on first run, then applies
    every migration whose version is greater than the current max.
    Each migration script is followed by an `INSERT INTO schema_version`
    — migrations themselves must NOT insert their own version row.
    """
    conn = get_connection(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        conn.commit()

        current = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0
        for version, sql in sorted(MIGRATIONS.items()):
            if version > current:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (version,)
                )
                conn.commit()
    finally:
        conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    from .paths import get_db_path

    conn = get_connection(get_db_path())
    try:
        yield conn
    finally:
        conn.close()
