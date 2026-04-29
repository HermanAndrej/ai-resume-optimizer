"""Integration tests for chat apply/reject routes."""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.models import (
    CompatibilityAnalysis,
    CompatibilityScore,
    KeywordOverlap,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
    ValidationResult,
)

CANNED_ANALYSIS = CompatibilityAnalysis(
    keyword_overlap=KeywordOverlap(matched=["python"], missing=[], match_pct=100.0),
    compatibility_score=CompatibilityScore(
        overall_fit_score=8, strengths=["python"], gaps=[], recommendations=[],
    ),
)
CANNED_HASH = "abc123"
CANNED_USAGE = {"cost_cents": 0.10, "model": "claude-sonnet-4-6"}


@pytest.fixture
def client(tmp_path):
    from backend.db import get_connection, get_db, run_migrations
    from backend.main import app

    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    conn.execute(
        "UPDATE profile SET full_name=?, summary=? WHERE id=1",
        ("Jane Doe", "Senior backend engineer."),
    )
    cur = conn.execute(
        "INSERT INTO experience (profile_id, company, title, description) "
        "VALUES (1, 'Acme Corp', 'Senior Engineer', 'Backend services')"
    )
    exp_id = cur.lastrowid
    bullet_cur = conn.execute(
        "INSERT INTO experience_bullets (experience_id, text) VALUES (?, ?)",
        (exp_id, "Reduced p99 latency by 40%"),
    )
    conn.execute(
        "INSERT INTO skills (profile_id, category, skill) VALUES "
        "(1, 'Languages', 'Python'), (1, 'Cloud', 'Kubernetes')"
    )
    conn.commit()
    conn.close()

    def override_get_db():
        c = get_connection(db_path)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, follow_redirects=False), db_path
    app.dependency_overrides.clear()


def _create_app_with_tailored(client_fixture) -> tuple[str, int]:
    """Returns (app_id, tailored_id)."""
    tc, db_path = client_fixture
    from backend.db import get_connection
    from backend.services import application_repo, tailored_repo

    # Create application via the route
    with patch(
        "backend.routes.applications.run_analysis",
        return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
    ):
        resp = tc.post(
            "/applications",
            data={"job_title": "Backend Engineer", "company": "Corp", "jd_text": "Python role"},
        )
    app_id = resp.headers["location"].split("/")[-1].split("?")[0]

    # Seed a tailored resume directly (bypass LLM)
    conn = get_connection(db_path)
    tailored = TailoredResume(
        summary="Senior backend engineer.",
        experience=[
            TailoredExperience(
                company="Acme Corp",
                title="Senior Engineer",
                bullets=[TailoredBullet(text="Cut latency 40%", source_bullet_id=None)],
            )
        ],
        skills=["Python", "Kubernetes"],
        selected_projects=[],
    )
    tid = tailored_repo.create_tailored(
        conn,
        application_id=app_id,
        content=tailored,
        validation=ValidationResult(),
        profile_hash=CANNED_HASH,
        model="claude-sonnet-4-6",
        cost_cents=0.5,
        source="generated",
    )
    conn.close()
    return app_id, tid


def _seed_suggestion(db_path, app_id: str, stype: str, target: str, proposed: str) -> int:
    from backend.db import get_connection
    from backend.services import chat_repo

    conn = get_connection(db_path)
    mid = chat_repo.create_message(conn, application_id=app_id, role="user", content="fix it")
    sid = chat_repo.create_suggestion(
        conn,
        application_id=app_id,
        message_id=mid,
        suggestion_type=stype,
        target_section=target,
        proposed_value=proposed,
        rationale="test",
    )
    conn.close()
    return sid


class TestApplyReject:
    def test_apply_creates_new_tailored_row(self, client):
        tc, db_path = client
        app_id, _ = _create_app_with_tailored(client)
        sid = _seed_suggestion(db_path, app_id, "replace_summary", "summary", "New summary.")

        resp = tc.post(f"/applications/{app_id}/suggestions/{sid}/apply")
        assert resp.status_code == 303
        assert f"/applications/{app_id}/chat" in resp.headers["location"]

    def test_apply_sets_parent_version_and_source(self, client):
        tc, db_path = client
        app_id, _ = _create_app_with_tailored(client)
        sid = _seed_suggestion(db_path, app_id, "replace_summary", "summary", "New summary.")

        tc.post(f"/applications/{app_id}/suggestions/{sid}/apply")

        from backend.db import get_connection
        from backend.services import tailored_repo
        conn = get_connection(db_path)
        rows = tailored_repo.list_for_application(conn, app_id)
        conn.close()

        assert len(rows) == 2
        new_row = min(rows, key=lambda r: r.version)  # v1 = original; v2 = chat-edit... wait
        # Actually the latest version is the new one
        new_row = max(rows, key=lambda r: r.version)
        # Check via raw DB since TailoredResumeRow doesn't expose source/parent_version
        from backend.db import get_connection
        conn = get_connection(db_path)
        raw = conn.execute(
            "SELECT source, parent_version FROM tailored_resumes WHERE application_id = ? ORDER BY version DESC LIMIT 1",
            (app_id,),
        ).fetchone()
        conn.close()
        assert raw["source"] == "chat-edit"
        assert raw["parent_version"] == 1

    def test_apply_marks_suggestion_applied(self, client):
        tc, db_path = client
        app_id, _ = _create_app_with_tailored(client)
        sid = _seed_suggestion(db_path, app_id, "replace_summary", "summary", "New.")

        tc.post(f"/applications/{app_id}/suggestions/{sid}/apply")

        from backend.db import get_connection
        from backend.services import chat_repo
        conn = get_connection(db_path)
        s = chat_repo.get_suggestion(conn, sid)
        conn.close()
        assert s.status == "applied"

    def test_apply_applied_version_in_redirect(self, client):
        tc, db_path = client
        app_id, _ = _create_app_with_tailored(client)
        sid = _seed_suggestion(db_path, app_id, "replace_summary", "summary", "New.")

        resp = tc.post(f"/applications/{app_id}/suggestions/{sid}/apply")
        assert "applied=" in resp.headers["location"]

    def test_reject_marks_suggestion_rejected(self, client):
        tc, db_path = client
        app_id, _ = _create_app_with_tailored(client)
        sid = _seed_suggestion(db_path, app_id, "swap_skill", "skills[0]", "Go")

        resp = tc.post(f"/applications/{app_id}/suggestions/{sid}/reject")
        assert resp.status_code == 303
        assert f"/applications/{app_id}/chat" in resp.headers["location"]

        from backend.db import get_connection
        from backend.services import chat_repo
        conn = get_connection(db_path)
        s = chat_repo.get_suggestion(conn, sid)
        conn.close()
        assert s.status == "rejected"

    def test_reject_does_not_create_new_tailored_row(self, client):
        tc, db_path = client
        app_id, _ = _create_app_with_tailored(client)
        sid = _seed_suggestion(db_path, app_id, "swap_skill", "skills[0]", "Go")

        tc.post(f"/applications/{app_id}/suggestions/{sid}/reject")

        from backend.db import get_connection
        from backend.services import tailored_repo
        conn = get_connection(db_path)
        rows = tailored_repo.list_for_application(conn, app_id)
        conn.close()
        assert len(rows) == 1

    def test_apply_unknown_application_redirects(self, client):
        tc, _ = client
        resp = tc.post("/applications/doesnotexist/suggestions/1/apply")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/applications"

    def test_reject_unknown_application_redirects(self, client):
        tc, _ = client
        resp = tc.post("/applications/doesnotexist/suggestions/1/reject")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/applications"

    def test_apply_unknown_suggestion_redirects_to_chat(self, client):
        tc, db_path = client
        app_id, _ = _create_app_with_tailored(client)
        resp = tc.post(f"/applications/{app_id}/suggestions/99999/apply")
        assert resp.status_code == 303
        assert f"/applications/{app_id}/chat" in resp.headers["location"]
