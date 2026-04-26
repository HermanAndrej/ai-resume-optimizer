"""Unit tests for profile_parser + apply_parsed_profile.

The LLM is mocked — no real API calls are made. Tests verify the full
parse → apply → query round-trip using an in-memory SQLite DB.
"""
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.db import run_migrations
from backend.models import ParsedProfile
from backend.services.llm_client import LLMInvalidJSONError
from backend.services.profile_parser import parse_resume_text
from backend.services.profile_repo import (
    apply_parsed_profile,
    list_certifications,
    list_education,
    list_experience,
    list_projects,
    list_skills_grouped,
    get_personal_info,
    get_summary,
    list_links,
    list_custom_sections,
)


CANNED_JSON = """{
  "full_name": "Alice Smith",
  "email": "alice@example.com",
  "phone": "+1 555-0100",
  "location": "San Francisco, CA",
  "summary": "Backend engineer with 5 years of Python experience.",
  "links": [
    { "label": "GitHub", "url": "https://github.com/alice" }
  ],
  "experience": [
    {
      "company": "Acme Corp",
      "title": "Senior SWE",
      "location": "Remote",
      "start_date": "Jan 2021",
      "end_date": "Present",
      "description": "",
      "bullets": [
        { "text": "Built distributed cache layer." },
        { "text": "Mentored 3 junior engineers." }
      ]
    }
  ],
  "education": [
    {
      "institution": "State University",
      "degree": "B.S.",
      "field": "Computer Science",
      "start_date": "2014",
      "end_date": "2018",
      "gpa": "3.8",
      "highlights": ""
    }
  ],
  "skills": [
    { "category": "Languages", "skill": "Python" },
    { "category": "Frameworks", "skill": "FastAPI" }
  ],
  "projects": [
    {
      "name": "OpenMetrics",
      "description": "Metrics aggregator",
      "tech_stack": "Python, Kafka",
      "url": "https://github.com/alice/openmetrics",
      "bullets": "1M events/sec ingestion.\\n500+ weekly downloads."
    }
  ],
  "certifications": [
    { "name": "AWS SAA", "issuer": "Amazon", "date": "2023", "url": "" }
  ],
  "custom_sections": [
    { "name": "Publications", "content": "ICML 2024 paper on ML systems." }
  ]
}"""


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    run_migrations(db_path)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


class TestParseResumeText:
    def test_returns_parsed_profile(self):
        with patch(
            "backend.services.profile_parser.call_llm",
            return_value=(CANNED_JSON, {}),
        ):
            result = parse_resume_text("dummy resume text")

        assert isinstance(result, ParsedProfile)
        assert result.full_name == "Alice Smith"
        assert result.email == "alice@example.com"

    def test_experience_parsed(self):
        with patch(
            "backend.services.profile_parser.call_llm",
            return_value=(CANNED_JSON, {}),
        ):
            result = parse_resume_text("dummy")

        assert len(result.experience) == 1
        assert result.experience[0].company == "Acme Corp"
        assert len(result.experience[0].bullets) == 2

    def test_invalid_json_raises(self):
        with patch(
            "backend.services.profile_parser.call_llm",
            return_value=("not json at all", {}),
        ):
            with pytest.raises(LLMInvalidJSONError):
                parse_resume_text("dummy")

    def test_invalid_schema_raises(self):
        # Valid JSON but wrong shape — experience should be a list, not a string
        bad_json = '{"experience": "wrong type"}'
        with patch(
            "backend.services.profile_parser.call_llm",
            return_value=(bad_json, {}),
        ):
            with pytest.raises(LLMInvalidJSONError):
                parse_resume_text("dummy")


class TestApplyParsedProfile:
    def _make_parsed(self) -> ParsedProfile:
        import json
        return ParsedProfile.model_validate(json.loads(CANNED_JSON))

    def test_personal_info_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        info = get_personal_info(db)
        assert info.full_name == "Alice Smith"
        assert info.email == "alice@example.com"
        assert info.location == "San Francisco, CA"

    def test_summary_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        summary = get_summary(db)
        assert "Python" in summary.text

    def test_links_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        links = list_links(db)
        assert len(links) == 1
        assert links[0].label == "GitHub"

    def test_experience_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        entries = list_experience(db)
        assert len(entries) == 1
        assert entries[0].company == "Acme Corp"
        assert entries[0].title == "Senior SWE"
        assert len(entries[0].bullets) == 2
        assert entries[0].bullets[0].text == "Built distributed cache layer."

    def test_education_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        entries = list_education(db)
        assert len(entries) == 1
        assert entries[0].institution == "State University"
        assert entries[0].gpa == "3.8"

    def test_skills_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        grouped = list_skills_grouped(db)
        assert "Languages" in grouped
        assert any(s.skill == "Python" for s in grouped["Languages"])
        assert "Frameworks" in grouped

    def test_projects_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        projects = list_projects(db)
        assert len(projects) == 1
        assert projects[0].name == "OpenMetrics"
        assert "Kafka" in projects[0].tech_stack

    def test_certifications_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        certs = list_certifications(db)
        assert len(certs) == 1
        assert certs[0].name == "AWS SAA"

    def test_custom_sections_written(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        sections = list_custom_sections(db)
        assert len(sections) == 1
        assert sections[0].name == "Publications"

    def test_apply_twice_does_not_duplicate(self, db: sqlite3.Connection):
        parsed = self._make_parsed()
        apply_parsed_profile(db, parsed)
        apply_parsed_profile(db, parsed)
        assert len(list_experience(db)) == 1
        assert len(list_skills_grouped(db)["Languages"]) == 1

    def test_display_order_sequential(self, db: sqlite3.Connection):
        apply_parsed_profile(db, self._make_parsed())
        rows = db.execute(
            "SELECT display_order FROM experience WHERE profile_id = 1 ORDER BY display_order"
        ).fetchall()
        orders = [r[0] for r in rows]
        assert orders == list(range(len(orders)))

    def test_rollback_on_error(self, db: sqlite3.Connection):
        parsed = self._make_parsed()
        # Corrupt the connection by closing it mid-flight is hard to simulate,
        # so instead verify the profile is unchanged if we pass bad data by
        # monkey-patching. We just confirm the original name stays on error.
        apply_parsed_profile(db, self._make_parsed())

        bad = ParsedProfile(full_name="Should Not Appear")
        bad.experience = "not a list"  # type: ignore[assignment]

        try:
            apply_parsed_profile(db, bad)
        except Exception:
            pass

        # Name from the first (successful) apply should still be there
        info = get_personal_info(db)
        assert info.full_name == "Alice Smith"
