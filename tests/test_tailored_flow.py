"""End-to-end TestClient tests for the tailored-resume routes (mocked LLM)."""
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
)


CANNED_ANALYSIS = CompatibilityAnalysis(
    keyword_overlap=KeywordOverlap(matched=["python"], missing=[], match_pct=100.0),
    compatibility_score=CompatibilityScore(
        overall_fit_score=8, strengths=["python"], gaps=[], recommendations=[],
    ),
)
CANNED_HASH = "abcd1234abcd1234"
CANNED_USAGE = {"cost_cents": 0.30, "model": "claude-sonnet-4-6"}

JD_TEXT = "Looking for a backend engineer with Python and Kubernetes."


@pytest.fixture
def client(tmp_path):
    from backend.db import get_connection, get_db, run_migrations
    from backend.main import app

    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    # Seed a real profile so build_source_index has content to work with
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE profile SET full_name=?, summary=? WHERE id=1",
        ("Jane Doe", "Backend engineer with 8 years of Python."),
    )
    cur = conn.execute(
        "INSERT INTO experience (profile_id, company, title, description) "
        "VALUES (1, 'Acme Corp', 'Senior Engineer', 'Backend services')"
    )
    exp_id = cur.lastrowid
    conn.execute(
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
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


def _create_application(client) -> str:
    """Create an application and return its id."""
    with patch(
        "backend.routes.applications.run_analysis",
        return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
    ):
        resp = client.post(
            "/applications",
            data={"job_title": "Backend Engineer", "company": "Hireable", "jd_text": JD_TEXT},
        )
    return resp.headers["location"].split("/")[-1].split("?")[0]


def _clean_tailored() -> TailoredResume:
    return TailoredResume(
        summary="Backend engineer with 8 years of Python.",
        experience=[
            TailoredExperience(
                company="Acme Corp",
                title="Senior Engineer",
                bullets=[TailoredBullet(text="Cut p99 latency 40%", source_bullet_id=None)],
            )
        ],
        skills=["Python", "Kubernetes"],
        selected_projects=[],
    )


def _fabricated_tailored() -> TailoredResume:
    return TailoredResume(
        summary="Backend engineer.",
        experience=[
            TailoredExperience(
                company="Fictitious Inc",  # ← unknown_company error
                title="Senior Engineer",
                bullets=[TailoredBullet(text="Saved $99M last year", source_bullet_id=None)],  # ← unverified_metric warning
            )
        ],
        skills=["Python", "Rust"],  # ← Rust = unknown_skill warning
        selected_projects=[],
    )


class TestTailorRoute:
    def test_post_redirects_to_tailored_page(self, client):
        app_id = _create_application(client)
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            return_value=(_clean_tailored(), CANNED_HASH, CANNED_USAGE),
        ):
            resp = client.post(f"/applications/{app_id}/tailor")
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/applications/{app_id}/tailored"

    def test_unknown_app_redirects_to_list(self, client):
        resp = client.post("/applications/doesnotexist/tailor")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/applications"

    def test_llm_error_redirects_to_show(self, client):
        from backend.services.llm_client import LLMError
        app_id = _create_application(client)
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            side_effect=LLMError("API down"),
        ):
            resp = client.post(f"/applications/{app_id}/tailor")
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/applications/{app_id}"


class TestTailoredShow:
    def test_no_tailored_yet_renders_empty_state(self, client):
        app_id = _create_application(client)
        resp = client.get(f"/applications/{app_id}/tailored")
        assert resp.status_code == 200
        assert "No tailored resume yet" in resp.text
        assert "Generate tailored resume" in resp.text

    def test_clean_tailored_renders_validation_clean(self, client):
        app_id = _create_application(client)
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            return_value=(_clean_tailored(), CANNED_HASH, CANNED_USAGE),
        ):
            client.post(f"/applications/{app_id}/tailor")
        resp = client.get(f"/applications/{app_id}/tailored")
        assert resp.status_code == 200
        assert "Validation clean" in resp.text
        assert "Acme Corp" in resp.text
        assert "Senior Engineer" in resp.text
        assert "Cut p99 latency 40%" in resp.text

    def test_fabricated_tailored_renders_issues(self, client):
        app_id = _create_application(client)
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            return_value=(_fabricated_tailored(), CANNED_HASH, CANNED_USAGE),
        ):
            client.post(f"/applications/{app_id}/tailor")
        resp = client.get(f"/applications/{app_id}/tailored")
        assert resp.status_code == 200
        assert "Needs review" in resp.text
        # The fictitious company should be flagged
        assert "Fictitious Inc" in resp.text
        assert "is not in the source profile" in resp.text
        # And the fake $99M too
        assert "$99M" in resp.text or "99m" in resp.text.lower()
        # Rust is a warning skill flag
        assert "Rust" in resp.text

    def test_unknown_application_returns_404(self, client):
        resp = client.get("/applications/doesnotexist/tailored")
        assert resp.status_code == 404

    def test_show_page_has_generate_button(self, client):
        app_id = _create_application(client)
        resp = client.get(f"/applications/{app_id}")
        assert "Generate tailored resume" in resp.text
        assert f"/applications/{app_id}/tailor" in resp.text


class TestTailoredVersioning:
    def test_regenerate_keeps_old_version(self, client):
        app_id = _create_application(client)
        # First generation
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            return_value=(_clean_tailored(), CANNED_HASH, CANNED_USAGE),
        ):
            client.post(f"/applications/{app_id}/tailor")
        # Second generation with distinguishable summary
        v2 = _clean_tailored()
        v2.summary = "Distinct second-version summary."
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            return_value=(v2, CANNED_HASH, CANNED_USAGE),
        ):
            client.post(f"/applications/{app_id}/tailor")
        # Latest should be v2
        resp = client.get(f"/applications/{app_id}/tailored")
        assert "Distinct second-version summary" in resp.text
        assert "Version 2" in resp.text


class TestStaleness:
    def test_stale_banner_shown_when_profile_changes(self, client, tmp_path):
        from backend.db import get_connection
        app_id = _create_application(client)
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            return_value=(_clean_tailored(), "stale_hash_will_not_match", CANNED_USAGE),
        ):
            client.post(f"/applications/{app_id}/tailor")
        resp = client.get(f"/applications/{app_id}/tailored")
        assert "profile has changed" in resp.text.lower()
