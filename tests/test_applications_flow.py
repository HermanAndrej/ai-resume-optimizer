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

    def test_show_page_has_status_badge(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert "status-analyzed" in resp.text

    def test_show_page_has_edit_form(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert 'name="status"' in resp.text
        assert 'name="notes"' in resp.text

    def test_show_page_has_jd_panel(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        resp = client.get(app_url)
        assert "Job Description" in resp.text
        assert "jd-panel" in resp.text


class TestEditApplication:
    def _app_url(self, client):
        redirect = _post_jd(client)
        return redirect.headers["location"].split("?")[0]

    def test_edit_happy_path_redirects(self, client):
        app_url = self._app_url(client)
        resp = client.post(
            f"{app_url}/edit",
            data={"status": "applied", "notes": "Via referral", "source_url": "", "jd_text": JD_TEXT},
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == app_url

    def test_edit_persists_values(self, client):
        app_url = self._app_url(client)
        client.post(
            f"{app_url}/edit",
            data={"status": "interviewing", "notes": "Phone screen done", "source_url": "https://example.com/job", "jd_text": JD_TEXT},
        )
        resp = client.get(app_url)
        assert "interviewing" in resp.text
        assert "Phone screen done" in resp.text
        assert "https://example.com/job" in resp.text

    def test_edit_invalid_status_returns_422(self, client):
        app_url = self._app_url(client)
        resp = client.post(
            f"{app_url}/edit",
            data={"status": "not_real", "notes": "", "source_url": "", "jd_text": JD_TEXT},
        )
        assert resp.status_code == 422

    def test_edit_unknown_id_returns_404(self, client):
        resp = client.post(
            "/applications/doesnotexist/edit",
            data={"status": "applied", "notes": "", "source_url": "", "jd_text": "x"},
        )
        assert resp.status_code == 404


class TestArchiveApplication:
    def _app_url(self, client):
        redirect = _post_jd(client)
        return redirect.headers["location"].split("?")[0]

    def test_archive_redirects_to_list(self, client):
        app_url = self._app_url(client)
        resp = client.post(f"{app_url}/archive")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/applications"

    def test_archived_app_not_in_default_list(self, client):
        _post_jd(client)
        redirect2 = _post_jd(client, job_title="ToArchive", company="Corp")
        app2_url = redirect2.headers["location"].split("?")[0]
        client.post(f"{app2_url}/archive")
        resp = client.get("/applications")
        assert "ToArchive" not in resp.text
        assert "Senior Python Developer" in resp.text

    def test_unarchive_redirects_to_show(self, client):
        app_url = self._app_url(client)
        client.post(f"{app_url}/archive")
        resp = client.post(f"{app_url}/unarchive")
        assert resp.status_code == 303
        assert resp.headers["location"] == app_url

    def test_unarchived_app_appears_in_list(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        client.post(f"{app_url}/archive")
        client.post(f"{app_url}/unarchive")
        resp = client.get("/applications")
        assert "Senior Python Developer" in resp.text


class TestReanalyzeApplication:
    def test_reanalyze_redirects_to_show(self, client):
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        with patch(
            "backend.routes.applications.run_analysis",
            return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
        ):
            resp = client.post(f"{app_url}/reanalyze")
        assert resp.status_code == 303
        assert resp.headers["location"].startswith(app_url)

    def test_reanalyze_updates_analysis(self, client):
        from backend.models import CompatibilityScore, KeywordOverlap, CompatibilityAnalysis
        new_score = CompatibilityScore(
            overall_fit_score=9,
            strengths=["Perfect match"],
            gaps=[],
            recommendations=[],
        )
        new_analysis = CompatibilityAnalysis(
            keyword_overlap=KeywordOverlap(matched=["python", "fastapi", "kubernetes"], missing=[], match_pct=100.0),
            compatibility_score=new_score,
        )
        redirect = _post_jd(client)
        app_url = redirect.headers["location"].split("?")[0]
        with patch(
            "backend.routes.applications.run_analysis",
            return_value=(new_analysis, "newhash123456789", CANNED_USAGE),
        ):
            client.post(f"{app_url}/reanalyze")
        resp = client.get(app_url)
        assert "9" in resp.text
        assert "Perfect match" in resp.text

    def test_reanalyze_unknown_id_redirects_to_list(self, client):
        resp = client.post("/applications/doesnotexist/reanalyze")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/applications"
