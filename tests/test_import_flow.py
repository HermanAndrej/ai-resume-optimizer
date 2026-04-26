"""End-to-end TestClient tests for the resume import flow (Phase 4).

The LLM parser is mocked so no real API calls are made. File extraction
runs for real against an in-memory DOCX; PDF is not exercised here.
"""
import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.models import ParsedProfile


CANNED_PARSED = ParsedProfile.model_validate({
    "full_name": "Bob Dev",
    "email": "bob@example.com",
    "phone": "+1 555-9999",
    "location": "Austin, TX",
    "summary": "Full-stack developer with 8 years of experience.",
    "links": [{"label": "GitHub", "url": "https://github.com/bob"}],
    "experience": [
        {
            "company": "Initech",
            "title": "Lead Engineer",
            "location": "Remote",
            "start_date": "2019",
            "end_date": "Present",
            "description": "",
            "bullets": [{"text": "Shipped feature X."}, {"text": "Reduced costs 30%."}],
        }
    ],
    "education": [
        {
            "institution": "Tech University",
            "degree": "B.S.",
            "field": "CS",
            "start_date": "2012",
            "end_date": "2016",
            "gpa": "",
            "highlights": "",
        }
    ],
    "skills": [
        {"category": "Languages", "skill": "Python"},
        {"category": "Languages", "skill": "TypeScript"},
    ],
    "projects": [],
    "certifications": [],
    "custom_sections": [],
})


def _make_docx_bytes(content: str) -> bytes:
    """Build a minimal in-memory DOCX with the given paragraph content."""
    import docx

    doc = docx.Document()
    for line in content.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path):
    """TestClient wired to a fresh in-memory DB."""
    from pathlib import Path
    from backend.db import run_migrations, get_connection
    from backend import main as app_module
    from backend import db as db_module

    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    # Override get_db to use our temp DB
    import sqlite3
    from fastapi import FastAPI
    from backend.db import get_db
    from backend.main import app

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


class TestImportGet:
    def test_import_page_renders(self, client):
        resp = client.get("/profile/import")
        assert resp.status_code == 200
        assert "Import Resume" in resp.text
        assert 'type="file"' in resp.text

    def test_no_warning_when_profile_empty(self, client):
        resp = client.get("/profile/import")
        assert "Warning" not in resp.text

    def test_warning_shown_when_profile_has_data(self, client):
        # Populate personal info first
        client.post("/profile/personal", data={"full_name": "Alice", "email": "a@b.com"})
        resp = client.get("/profile/import")
        assert "Warning" in resp.text
        assert "overwrite" in resp.text


class TestImportPost:
    def _docx_upload(self, client, content: str):
        data = _make_docx_bytes(content)
        with patch("backend.routes.profile.parse_resume_text", return_value=(CANNED_PARSED, {"cost_cents": 0.05})):
            resp = client.post(
                "/profile/import",
                files={"resume_file": ("resume.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        return resp

    def test_successful_upload_shows_review(self, client):
        long_content = "Bob Dev\nFull-stack developer\nbob@example.com\nAustin TX\n" * 5
        resp = self._docx_upload(client, long_content)
        assert resp.status_code == 200
        assert "Review Parsed Resume" in resp.text
        assert "Bob Dev" in resp.text

    def test_review_has_hidden_json_field(self, client):
        long_content = "Bob Dev\nFull-stack developer\n" * 5
        resp = self._docx_upload(client, long_content)
        assert 'name="parsed_json"' in resp.text

    def test_unsupported_extension_returns_error(self, client):
        resp = client.post(
            "/profile/import",
            files={"resume_file": ("resume.txt", b"some text", "text/plain")},
        )
        assert resp.status_code == 422
        assert "Only .pdf and .docx" in resp.text

    def test_too_short_content_returns_error(self, client):
        data = _make_docx_bytes("Hi")
        resp = client.post(
            "/profile/import",
            files={"resume_file": ("resume.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 422
        assert "too short" in resp.text

    def test_llm_error_returns_error_page(self, client):
        from backend.services.llm_client import LLMError
        long_content = "Bob Dev\nFull-stack developer\n" * 5
        data = _make_docx_bytes(long_content)
        with patch("backend.routes.profile.parse_resume_text", side_effect=LLMError("oops")):
            resp = client.post(
                "/profile/import",
                files={"resume_file": ("resume.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        assert resp.status_code == 422
        assert "LLM error" in resp.text

    def test_review_shows_experience(self, client):
        long_content = "Bob Dev\nFull-stack developer\n" * 5
        resp = self._docx_upload(client, long_content)
        assert "Initech" in resp.text
        assert "Lead Engineer" in resp.text

    def test_review_shows_skills(self, client):
        long_content = "Bob Dev\nFull-stack developer\n" * 5
        resp = self._docx_upload(client, long_content)
        assert "Python" in resp.text


class TestImportApply:
    def test_apply_redirects_to_personal(self, client):
        parsed_json = CANNED_PARSED.model_dump_json()
        resp = client.post("/profile/import/apply", data={"parsed_json": parsed_json})
        assert resp.status_code == 303
        assert resp.headers["location"] == "/profile/personal"

    def test_apply_populates_db(self, client):
        parsed_json = CANNED_PARSED.model_dump_json()
        client.post("/profile/import/apply", data={"parsed_json": parsed_json})
        # Verify personal page now shows the imported name
        resp = client.get("/profile/personal")
        assert "Bob Dev" in resp.text

    def test_apply_bad_json_redirects_to_import(self, client):
        resp = client.post("/profile/import/apply", data={"parsed_json": "not json at all"})
        assert resp.status_code == 303
        assert "/profile/import" in resp.headers["location"]

    def test_apply_invalid_schema_redirects_to_import(self, client):
        bad = json.dumps({"experience": "wrong type"})
        resp = client.post("/profile/import/apply", data={"parsed_json": bad})
        assert resp.status_code == 303
        assert "/profile/import" in resp.headers["location"]
