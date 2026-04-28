"""Unit tests for export_builder: ExportResume builder + filename sanitizer."""
import sqlite3
from pathlib import Path

import pytest

from backend.db import run_migrations
from backend.models import (
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)
from backend.services.export_builder import (
    build_export_resume,
    sanitize_filename,
)


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    run_migrations(db_path)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def _seed(db: sqlite3.Connection) -> None:
    db.execute(
        "UPDATE profile SET full_name=?, email=?, phone=?, location=?, summary=? WHERE id=1",
        ("Jane Doe", "jane@example.com", "555-1212", "Berlin", "Original profile summary"),
    )
    db.execute(
        "INSERT INTO experience (profile_id, company, title) "
        "VALUES (1, 'Old Job Inc', 'Junior Dev')"
    )
    db.execute(
        "INSERT INTO skills (profile_id, category, skill) VALUES "
        "(1, 'Languages', 'Python'), (1, 'Languages', 'Go'), "
        "(1, 'Cloud', 'Kubernetes'), (1, 'Cloud', 'AWS')"
    )
    db.execute(
        "INSERT INTO education (profile_id, institution, degree, field) "
        "VALUES (1, 'TU Berlin', 'BSc', 'Computer Science')"
    )
    db.execute(
        "INSERT INTO certifications (profile_id, name, issuer) "
        "VALUES (1, 'AWS SAA', 'Amazon')"
    )
    db.execute(
        "INSERT INTO projects (profile_id, name, description, tech_stack) VALUES "
        "(1, 'logsift', 'CLI for log analysis', 'Python'), "
        "(1, 'extra-thing', 'Not selected', 'Rust')"
    )
    db.commit()


def _tailored() -> TailoredResume:
    return TailoredResume(
        summary="Tailored summary text.",
        experience=[
            TailoredExperience(
                company="Acme Corp",
                title="Senior Engineer",
                location="Remote",
                start_date="2020",
                end_date="Present",
                bullets=[
                    TailoredBullet(text="Shipped feature X"),
                    TailoredBullet(text=""),  # blank → filtered
                    TailoredBullet(text="Reduced latency 40%"),
                ],
            )
        ],
        skills=["Python", "Kubernetes", "Rust"],  # Rust unknown → goes to "Skills"
        selected_projects=["logsift"],
    )


class TestBuildExportResume:
    def test_uses_tailored_summary_not_profile_summary(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        assert resume.summary == "Tailored summary text."
        assert "Original profile summary" not in resume.summary

    def test_personal_info_from_live_profile(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        assert resume.personal.full_name == "Jane Doe"
        assert resume.personal.email == "jane@example.com"
        assert resume.personal.location == "Berlin"

    def test_experience_from_tailored_only(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        # Old Job Inc is in profile but not in tailored — must NOT appear
        companies = [e.company for e in resume.experience]
        assert "Old Job Inc" not in companies
        assert "Acme Corp" in companies

    def test_experience_bullets_filter_blanks(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        bullets = resume.experience[0].bullets
        assert len(bullets) == 2
        assert "" not in bullets

    def test_skills_grouped_by_profile_category(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        cats = {g.category: g.items for g in resume.skills_grouped}
        assert "Languages" in cats
        assert "Python" in cats["Languages"]
        assert "Cloud" in cats
        assert "Kubernetes" in cats["Cloud"]

    def test_unknown_skill_lands_in_default_group(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        cats = {g.category: g.items for g in resume.skills_grouped}
        # Rust isn't in profile → "Skills" fallback group
        assert "Skills" in cats
        assert "Rust" in cats["Skills"]

    def test_skills_not_included_omitted_from_groups(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        all_skills = [s for g in resume.skills_grouped for s in g.items]
        # Go is in profile but not in tailored.skills — must NOT appear
        assert "Go" not in all_skills
        # AWS is in profile but not in tailored.skills — must NOT appear
        assert "AWS" not in all_skills

    def test_projects_filtered_by_selected_names(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        names = [p.name for p in resume.projects]
        assert "logsift" in names
        assert "extra-thing" not in names

    def test_projects_full_entries_pulled_from_profile(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        proj = resume.projects[0]
        # Full entry — description and tech_stack present even though tailored only has the name
        assert proj.description == "CLI for log analysis"
        assert proj.tech_stack == "Python"

    def test_projects_empty_when_no_selection(self, db):
        _seed(db)
        tailored = _tailored()
        tailored.selected_projects = []
        resume = build_export_resume(db, tailored)
        assert resume.projects == []

    def test_project_match_case_insensitive(self, db):
        _seed(db)
        tailored = _tailored()
        tailored.selected_projects = ["LOGSIFT"]
        resume = build_export_resume(db, tailored)
        assert len(resume.projects) == 1

    def test_education_and_certs_from_live_profile(self, db):
        _seed(db)
        resume = build_export_resume(db, _tailored())
        assert any(e.institution == "TU Berlin" for e in resume.education)
        assert any(c.name == "AWS SAA" for c in resume.certifications)

    def test_empty_tailored_produces_empty_sections(self, db):
        _seed(db)
        empty = TailoredResume()
        resume = build_export_resume(db, empty)
        assert resume.summary == ""
        assert resume.experience == []
        assert resume.skills_grouped == []
        assert resume.projects == []


class TestSanitizeFilename:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Jane Doe - Acme - Senior Engineer", "Jane Doe - Acme - Senior Engineer"),
            ("Bad/path\\name", "Badpathname"),
            ("Has<>:bad?chars*", "Hasbadchars"),
            ("  spaced out  ", "spaced out"),
            ("with\nnewline", "withnewline"),
            ("trailing dots...", "trailing dots"),
            ("Unicode — café résumé 你好", "Unicode — café résumé 你好"),
        ],
    )
    def test_sanitize_cases(self, raw, expected):
        assert sanitize_filename(raw, "fallback") == expected

    def test_empty_returns_fallback(self):
        assert sanitize_filename("", "tailored-resume") == "tailored-resume"

    def test_only_bad_chars_returns_fallback(self):
        assert sanitize_filename("///***???", "fallback") == "fallback"

    def test_only_whitespace_returns_fallback(self):
        assert sanitize_filename("   ", "fallback") == "fallback"
