"""End-to-end TestClient tests for export routes (print preview + DOCX)."""
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
JD_TEXT = "Backend engineer with Python."


@pytest.fixture
def client(tmp_path):
    from backend.db import get_connection, get_db, run_migrations
    from backend.main import app

    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    conn.execute(
        "UPDATE profile SET full_name=?, email=?, phone=?, location=?, summary=? WHERE id=1",
        ("Jane Doe", "jane@example.com", "555-1212", "Berlin", "Source summary"),
    )
    cur = conn.execute(
        "INSERT INTO experience (profile_id, company, title) "
        "VALUES (1, 'Acme Corp', 'Senior Engineer')"
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
    conn.execute(
        "INSERT INTO education (profile_id, institution, degree) "
        "VALUES (1, 'TU Berlin', 'BSc')"
    )
    conn.execute(
        "INSERT INTO certifications (profile_id, name, issuer) "
        "VALUES (1, 'AWS SAA', 'Amazon')"
    )
    conn.execute(
        "INSERT INTO projects (profile_id, name, description) "
        "VALUES (1, 'logsift', 'CLI for log analysis')"
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


def _create_app_id(client) -> str:
    with patch(
        "backend.routes.applications.run_analysis",
        return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
    ):
        resp = client.post(
            "/applications",
            data={"job_title": "Backend Engineer", "company": "Hireable", "jd_text": JD_TEXT},
        )
    return resp.headers["location"].split("/")[-1].split("?")[0]


def _generate_tailored(client, app_id: str) -> None:
    tailored = TailoredResume(
        summary="Tailored summary text.",
        experience=[
            TailoredExperience(
                company="Acme Corp",
                title="Senior Engineer",
                start_date="2020",
                end_date="Present",
                bullets=[TailoredBullet(text="Cut p99 latency 40%")],
            )
        ],
        skills=["Python", "Kubernetes"],
        selected_projects=["logsift"],
    )
    with patch(
        "backend.routes.applications.generate_tailored_resume",
        return_value=(tailored, CANNED_HASH, CANNED_USAGE),
    ):
        client.post(f"/applications/{app_id}/tailor")


class TestPrintRoute:
    def test_returns_200_with_resume_content(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/print")
        assert resp.status_code == 200
        assert "Jane Doe" in resp.text
        assert "Tailored summary text" in resp.text
        assert "Acme Corp" in resp.text
        assert "Cut p99 latency 40%" in resp.text

    def test_renders_education_and_certs_from_profile(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/print")
        assert "TU Berlin" in resp.text
        assert "AWS SAA" in resp.text

    def test_renders_filtered_project(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/print")
        assert "logsift" in resp.text
        assert "CLI for log analysis" in resp.text

    def test_print_stylesheet_present(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/print")
        # Must include @media print rule that hides the instructions banner
        assert "@media print" in resp.text
        assert "print-instructions" in resp.text

    def test_no_layout_chrome(self, client):
        """Print page must NOT include the sidebar/nav layout."""
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/print")
        # The main app's sidebar contains "Resume Optimizer" brand text
        assert "<nav class=\"sidebar\"" not in resp.text

    def test_redirects_when_no_tailored_yet(self, client):
        app_id = _create_app_id(client)
        # No tailored resume generated → redirect back to /tailored
        resp = client.get(f"/applications/{app_id}/tailored/print")
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/applications/{app_id}/tailored"

    def test_unknown_application_returns_404(self, client):
        resp = client.get("/applications/doesnotexist/tailored/print")
        assert resp.status_code == 404


class TestDocxRoute:
    DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_returns_valid_docx_with_correct_content_type(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/download.docx")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == self.DOCX_MEDIA_TYPE
        # DOCX = zip file → starts with PK magic bytes
        assert resp.content.startswith(b"PK\x03\x04")

    def test_content_disposition_filename(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/download.docx")
        cd = resp.headers["content-disposition"]
        assert "attachment" in cd
        assert ".docx" in cd
        # Filename should incorporate full name + company + job title
        assert "Jane Doe" in cd
        assert "Hireable" in cd
        assert "Backend Engineer" in cd

    def test_docx_contains_expected_text(self, client):
        from io import BytesIO
        from docx import Document

        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored/download.docx")
        assert resp.status_code == 200

        doc = Document(BytesIO(resp.content))
        all_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Jane Doe" in all_text
        assert "Tailored summary text" in all_text
        assert "Acme Corp" in all_text
        assert "Cut p99 latency 40%" in all_text
        # Section headings
        assert "Summary" in all_text
        assert "Experience" in all_text
        assert "Skills" in all_text

    def test_redirects_when_no_tailored_yet(self, client):
        app_id = _create_app_id(client)
        resp = client.get(f"/applications/{app_id}/tailored/download.docx")
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/applications/{app_id}/tailored"

    def test_unknown_application_redirects_to_list(self, client):
        resp = client.get("/applications/doesnotexist/tailored/download.docx")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/applications"


class TestTailoredPageExportLinks:
    def test_both_export_links_present_on_tailored_page(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored")
        assert resp.status_code == 200
        assert f"/applications/{app_id}/tailored/print" in resp.text
        assert f"/applications/{app_id}/tailored/download.docx" in resp.text
        assert "Print / Save as PDF" in resp.text
        assert "Download DOCX" in resp.text

    def test_validation_warning_hidden_when_clean(self, client):
        app_id = _create_app_id(client)
        _generate_tailored(client, app_id)
        resp = client.get(f"/applications/{app_id}/tailored")
        # Clean tailored (everything traces to source) → no warning
        assert "unresolved validation errors" not in resp.text

    def test_validation_warning_shown_when_errors(self, client):
        app_id = _create_app_id(client)
        # Generate a resume with a fabricated company → validator emits an error
        bad = TailoredResume(
            summary="Some summary",
            experience=[
                TailoredExperience(
                    company="Fictitious Inc",  # not in profile
                    title="Senior Engineer",
                    bullets=[TailoredBullet(text="Did something")],
                )
            ],
            skills=["Python"],
        )
        with patch(
            "backend.routes.applications.generate_tailored_resume",
            return_value=(bad, CANNED_HASH, CANNED_USAGE),
        ):
            client.post(f"/applications/{app_id}/tailor")
        resp = client.get(f"/applications/{app_id}/tailored")
        assert "unresolved validation errors" in resp.text
