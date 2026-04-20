import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version (version) VALUES (1);

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
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    label TEXT,
    url TEXT,
    display_order INTEGER
);

CREATE TABLE experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    company TEXT,
    title TEXT,
    location TEXT,
    start_date TEXT,
    end_date TEXT,
    description TEXT,
    display_order INTEGER
);

CREATE TABLE experience_bullets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experience_id INTEGER REFERENCES experience(id) ON DELETE CASCADE,
    text TEXT,
    tags TEXT,
    display_order INTEGER
);

CREATE TABLE education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    institution TEXT,
    degree TEXT,
    field TEXT,
    start_date TEXT,
    end_date TEXT,
    gpa TEXT,
    highlights TEXT,
    display_order INTEGER
);

CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    category TEXT,
    skill TEXT,
    display_order INTEGER
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    tech_stack TEXT,
    url TEXT,
    bullets TEXT,
    display_order INTEGER
);

CREATE TABLE certifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT,
    issuer TEXT,
    date TEXT,
    url TEXT,
    display_order INTEGER
);

CREATE TABLE custom_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT,
    content TEXT,
    display_order INTEGER
);

CREATE TABLE mini_projects (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    job_title TEXT,
    company TEXT,
    job_description TEXT,
    compatibility_analysis TEXT,
    profile_snapshot_hash TEXT,
    selected_model TEXT DEFAULT 'claude-sonnet-4-6',
    archived INTEGER DEFAULT 0
);

CREATE TABLE tailored_resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES mini_projects(id) ON DELETE CASCADE,
    version INTEGER,
    content TEXT,
    generation_notes TEXT,
    source TEXT,
    parent_version INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES mini_projects(id) ON DELETE CASCADE,
    role TEXT,
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents REAL,
    model TEXT
);

CREATE TABLE pending_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES mini_projects(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    suggestion_type TEXT,
    target_section TEXT,
    current_value TEXT,
    proposed_value TEXT,
    rationale TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_memory (
    id INTEGER PRIMARY KEY DEFAULT 1,
    preferences TEXT,
    recurring_context TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (id = 1)
);

CREATE TABLE usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    project_id TEXT,
    operation TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents REAL
);

INSERT INTO profile (id) VALUES (1);
"""

MIGRATIONS: dict[int, str] = {1: SCHEMA_V1}


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(db_path: Path) -> None:
    """Auto-run any unapplied migrations."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()

        if not row:
            conn.executescript(SCHEMA_V1)
            conn.commit()
            current_version = 1
        else:
            current_version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0

        for version, sql in sorted(MIGRATIONS.items()):
            if version > current_version:
                conn.executescript(sql)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                conn.commit()
    finally:
        conn.close()


def get_db():
    """FastAPI dependency for DB access."""
    from .paths import get_db_path
    conn = get_connection(get_db_path())
    try:
        yield conn
    finally:
        conn.close()
