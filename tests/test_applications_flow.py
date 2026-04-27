"""End-to-end TestClient tests for the applications flow.

The compat_runner is mocked — no real LLM calls.
"""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.models import CompatibilityAnalysis, CompatibilityScore, KeywordOverlap


CANNED_SCORE = CompatibilityScore(
    overall_fit_score=7,
    strengths=["Strong Python background matches required language"],
    gaps=["No Kubernetes experience listed; JD requires container orchestration"],
    recommendations=["Add any Kubernetes or Docker Swarm exposure"],
)

CANNED_OVERLAP = KeywordOverlap(
    matched=["python", "fastapi"], missing=["kubernetes"], match_pct=66.7
)

CANNED_ANALYSIS = CompatibilityAnalysis(
    keyword_overlap=CANNED_OVERLAP, compatibility_score=CANNED_SCORE
)

CANNED_USAGE = {"cost_cents": 0.30, "model": "claude-sonnet-4-6"}
CANNED_HASH = "abcd1234abcd1234"

JD_TEXT = """
We are looking for a Senior Python Developer with experience in FastAPI and Kubernetes.
The role requires strong understanding of REST APIs, containerization, and machine learning.
Experience with PostgreSQL and cloud platforms (AWS, GCP) is required.
"""


@pytest.fixture
def client(tmp_path):
    from backend.db import get_connection, get_db, run_migrations
    from backend.main import app

    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


def _post_jd(client, job_title="Senior Python Developer", company="Acme", jd=JD_TEXT):
    with patch(
        "backend.routes.applications.run_analysis",
        return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
    ):
        return client.post(
            "/applications",
            data={"job_title": job_title, "company": company, "jd_text": jd},
        )


class TestApplicationsList:
    def test_list_page_renders(self, client):
        resp = client.get("/applications")
        assert resp.status_code == 200
        assert "Applications" in resp.text

    def test_empty_state_shown(self, client):
        resp = client.get("/applications")
        assert "No analyses yet" in resp.text

    def test_list_shows_created_application(self, client):
        resp = _post_jd(client)
        assert resp.status_code == 303
        resp2 = client.get("/applications")
        assert "Senior Python Developer" in resp2.text


class TestNewApplication:
    def test_new_page_renders(self, client):
        resp = client.get("/applications/new")
        assert resp.status_code == 200
        assert "Job Description" in resp.text
        assert "Analyze" in resp.text

    def test_new_page_has_form_fields(self, client):
        resp = client.get("/applications/new")
        assert 'name="job_title"' in resp.text
        assert 'name="company"' in resp.text
        assert 'name="jd_text"' in resp.text


class TestCreateApplication:
    def test_post_redirects_to_result(self, client):
        resp = _post_jd(client)
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/applications/")

    def test_missing_job_title_returns_422(self, client):
        with patch(
            "backend.routes.applications.run_analysis",
            return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
        ):
            resp = client.post(
                "/applications",
                data={"job_title": "", "company": "Acme", "jd_text": JD_TEXT},
            )
        assert resp.status_code == 422
        assert "required" in resp.text.lower()

    def test_missing_jd_returns_422(self, client):
        with patch(
            "backend.routes.applications.run_analysis",
            return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
        ):
            resp = client.post(
                "/applications",
                data={"job_title": "Dev", "company": "", "jd_text": ""},
            )
        assert resp.status_code == 422

    def test_llm_error_returns_500(self, client):
        from backend.services.llm_client import LLMError

        with patch(
            "backend.routes.applications.run_analysis",
            side_effect=LLMError("API unavailable"),
        ):
            resp = client.post(
                "/applications",
                data={"job_title": "Dev", "company": "Co", "jd_text": JD_TEXT},
            )
        assert resp.status_code == 500
        assert "AI analysis failed" in resp.text


class TestShowApplication:
    def test_result_page_shows_score(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert resp.status_code == 200
        assert "7" in resp.text

    def test_result_page_shows_gap_term(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert "Kubernetes" in resp.text

    def test_result_page_shows_strength(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert "Python" in resp.text

    def test_result_page_shows_job_title(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert "Senior Python Developer" in resp.text

    def test_unknown_id_returns_404(self, client):
        resp = client.get("/applications/doesnotexist")
        assert resp.status_code == 404

    def test_gap_nudge_section_renders(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert "Gap Nudge" in resp.text
