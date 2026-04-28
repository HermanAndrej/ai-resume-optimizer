"""Unit tests for resume_validator — the fabrication-detection layer."""
import sqlite3
from pathlib import Path

import pytest

from backend.db import run_migrations
from backend.models import (
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)
from backend.services.resume_validator import (
    SourceIndex,
    build_source_index,
    extract_numeric_claims,
    validate_tailored_resume,
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


def _seed(db: sqlite3.Connection) -> dict[str, int]:
    db.execute(
        "UPDATE profile SET full_name=?, summary=? WHERE id=1",
        ("Jane Doe", "Backend engineer with 8 years of Python."),
    )
    cur = db.execute(
        "INSERT INTO experience (profile_id, company, title, description) "
        "VALUES (1, 'Acme Corp', 'Senior Engineer', 'Backend services team')"
    )
    exp_id = cur.lastrowid
    cur = db.execute(
        "INSERT INTO experience_bullets (experience_id, text) VALUES (?, ?)",
        (exp_id, "Reduced p99 latency by 40% via caching"),
    )
    bullet1 = cur.lastrowid
    cur = db.execute(
        "INSERT INTO experience_bullets (experience_id, text) VALUES (?, ?)",
        (exp_id, "Migrated 12 services to Kubernetes"),
    )
    bullet2 = cur.lastrowid
    db.execute(
        "INSERT INTO skills (profile_id, category, skill) VALUES "
        "(1, 'Languages', 'Python'), (1, 'Cloud', 'Kubernetes')"
    )
    db.execute(
        "INSERT INTO projects (profile_id, name, description) VALUES "
        "(1, 'logsift', 'CLI for log analysis')"
    )
    db.commit()
    return {"experience": exp_id, "bullet1": bullet1, "bullet2": bullet2}


def _clean_tailored(ids: dict[str, int]) -> TailoredResume:
    return TailoredResume(
        summary="Backend engineer with 8 years of Python.",
        experience=[
            TailoredExperience(
                company="Acme Corp",
                title="Senior Engineer",
                bullets=[
                    TailoredBullet(text="Cut p99 latency 40% with caching", source_bullet_id=ids["bullet1"]),
                    TailoredBullet(text="Migrated 12 services to K8s", source_bullet_id=ids["bullet2"]),
                ],
            )
        ],
        skills=["Python", "Kubernetes"],
        selected_projects=["logsift"],
    )


class TestBuildSourceIndex:
    def test_indexes_companies_titles_skills_projects(self, db):
        _seed(db)
        idx = build_source_index(db)
        assert "acme corp" in idx.companies
        assert "senior engineer" in idx.titles
        assert "python" in idx.skills
        assert "kubernetes" in idx.skills
        assert "logsift" in idx.project_names

    def test_bullet_texts_keyed_by_id(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        assert ids["bullet1"] in idx.bullet_texts_by_id
        assert "40%" in idx.bullet_texts_by_id[ids["bullet1"]]

    def test_all_source_text_lowercased(self, db):
        _seed(db)
        idx = build_source_index(db)
        assert "acme corp" in idx.all_source_text
        assert "Acme Corp" not in idx.all_source_text
        assert "40%" in idx.all_source_text


class TestExtractNumericClaims:
    def test_extracts_percentages(self):
        assert "40%" in extract_numeric_claims("Reduced latency by 40% overall")

    def test_extracts_currency(self):
        out = extract_numeric_claims("Saved $5K and $1.2M")
        assert any("5k" in t.lower() or "$5k" in t for t in out)

    def test_extracts_multipliers(self):
        out = extract_numeric_claims("Achieved 10x speedup")
        assert "10x" in out

    def test_extracts_year_ranges(self):
        out = extract_numeric_claims("Worked there 2020-2023")
        assert any("2020-2023" in t.replace("–", "-") for t in out)

    def test_extracts_large_integers(self):
        out = extract_numeric_claims("Migrated 12 services and 100 endpoints")
        assert "12" in out
        assert "100" in out

    def test_skips_single_digit(self):
        # Single-digit integers like "1", "2", "5" are too noisy to flag
        out = extract_numeric_claims("led 3 teams and 5 reports")
        # 3 and 5 should NOT be in the output (single digits filtered)
        assert "3" not in out
        assert "5" not in out

    def test_dedupes(self):
        out = extract_numeric_claims("40% and 40% again with 40%")
        assert out.count("40%") == 1

    def test_empty_string(self):
        assert extract_numeric_claims("") == []


class TestValidateClean:
    def test_clean_resume_has_no_issues(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        result = validate_tailored_resume(_clean_tailored(ids), idx)
        assert result.is_clean
        assert result.error_count == 0
        assert result.warning_count == 0


class TestUnknownCompany:
    def test_fake_company_is_error(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.experience[0].company = "Fictitious Inc"
        result = validate_tailored_resume(bad, idx)
        assert result.error_count >= 1
        assert any(i.category == "unknown_company" for i in result.issues)


class TestUnknownTitle:
    def test_fake_title_is_error(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.experience[0].title = "VP of Engineering"
        result = validate_tailored_resume(bad, idx)
        assert any(
            i.category == "unknown_title" and i.severity == "error"
            for i in result.issues
        )


class TestUnknownSkill:
    def test_fake_skill_is_warning_not_error(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.skills.append("Rust")
        result = validate_tailored_resume(bad, idx)
        assert any(
            i.category == "unknown_skill" and i.severity == "warning"
            for i in result.issues
        )
        # No error for the same issue
        assert not any(
            i.category == "unknown_skill" and i.severity == "error"
            for i in result.issues
        )


class TestUnknownProject:
    def test_fake_project_is_error(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.selected_projects.append("rocket-science-thingy")
        result = validate_tailored_resume(bad, idx)
        assert any(
            i.category == "unknown_project" and i.severity == "error"
            for i in result.issues
        )


class TestBulletReference:
    def test_valid_source_bullet_id_passes(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        result = validate_tailored_resume(_clean_tailored(ids), idx)
        assert not any(i.category == "unknown_bullet_ref" for i in result.issues)

    def test_invalid_source_bullet_id_is_error(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.experience[0].bullets[0].source_bullet_id = 99999
        result = validate_tailored_resume(bad, idx)
        assert any(
            i.category == "unknown_bullet_ref" and i.severity == "error"
            for i in result.issues
        )

    def test_null_source_bullet_id_does_not_flag(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.experience[0].bullets[0].source_bullet_id = None
        result = validate_tailored_resume(bad, idx)
        assert not any(i.category == "unknown_bullet_ref" for i in result.issues)


class TestNumericClaims:
    def test_fabricated_percentage_is_warning(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.experience[0].bullets[0].text = "Reduced costs 87% with magic"
        result = validate_tailored_resume(bad, idx)
        assert any(
            i.category == "unverified_metric" and "87%" in i.message
            for i in result.issues
        )

    def test_genuine_metric_passes(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        clean = _clean_tailored(ids)
        # 40% appears in source bullet
        clean.experience[0].bullets[0].text = "Achieved 40% reduction in latency"
        result = validate_tailored_resume(clean, idx)
        assert not any(i.category == "unverified_metric" for i in result.issues)

    def test_fabricated_summary_metric_is_warning(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.summary = "Engineer with 99 years of experience and $9M in revenue"
        result = validate_tailored_resume(bad, idx)
        flagged = [i for i in result.issues if i.location == "summary"]
        assert len(flagged) >= 1


class TestCaseInsensitive:
    def test_company_match_is_case_insensitive(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.experience[0].company = "ACME CORP"
        result = validate_tailored_resume(bad, idx)
        assert not any(i.category == "unknown_company" for i in result.issues)

    def test_skill_match_is_case_insensitive(self, db):
        ids = _seed(db)
        idx = build_source_index(db)
        bad = _clean_tailored(ids)
        bad.skills = ["python", "KUBERNETES"]
        result = validate_tailored_resume(bad, idx)
        assert not any(i.category == "unknown_skill" for i in result.issues)
