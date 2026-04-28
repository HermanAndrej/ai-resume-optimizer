"""Unit tests for tailored_repo."""
import sqlite3
from pathlib import Path

import pytest

from backend.db import run_migrations
from backend.models import (
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
    ValidationIssue,
    ValidationResult,
)
from backend.services import application_repo, tailored_repo
from backend.services.compat_runner import compute_profile_hash


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    run_migrations(db_path)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def _seed_app(db: sqlite3.Connection) -> str:
    return application_repo.create_application(
        db,
        job_title="Backend Engineer",
        company="Acme",
        jd="JD text",
        analysis_json='{"keyword_overlap":{"matched":[],"missing":[],"jd_only":[],"match_pct":0.0},"compatibility_score":{"overall_fit_score":5,"strengths":[],"gaps":[],"recommendations":[]}}',
        profile_hash="seed_hash",
    )


def _make_tailored() -> TailoredResume:
    return TailoredResume(
        summary="Tailored summary text.",
        experience=[
            TailoredExperience(
                company="Acme Corp",
                title="Senior Engineer",
                start_date="2020",
                end_date="Present",
                bullets=[
                    TailoredBullet(text="Shipped feature X", source_bullet_id=1),
                ],
            )
        ],
        skills=["python", "fastapi"],
        selected_projects=["my-project"],
    )


def _make_validation(*, errors: int = 0, warnings: int = 0) -> ValidationResult:
    issues = []
    for i in range(errors):
        issues.append(ValidationIssue(severity="error", category="unknown_company", message=f"err{i}", location=f"experience[{i}]"))
    for i in range(warnings):
        issues.append(ValidationIssue(severity="warning", category="unknown_skill", message=f"warn{i}", location=f"skills[{i}]"))
    return ValidationResult(issues=issues)


class TestCreateTailored:
    def test_returns_id(self, db):
        app_id = _seed_app(db)
        new_id = tailored_repo.create_tailored(
            db,
            application_id=app_id,
            content=_make_tailored(),
            validation=_make_validation(),
            profile_hash="abc123",
            model="claude-sonnet-4-6",
            cost_cents=1.5,
        )
        assert isinstance(new_id, int)
        assert new_id > 0

    def test_assigns_incrementing_versions(self, db):
        app_id = _seed_app(db)
        for _ in range(3):
            tailored_repo.create_tailored(
                db,
                application_id=app_id,
                content=_make_tailored(),
                validation=_make_validation(),
                profile_hash="h",
                model="m",
                cost_cents=0.0,
            )
        rows = tailored_repo.list_for_application(db, app_id)
        versions = sorted(r.version for r in rows)
        assert versions == [1, 2, 3]


class TestGetLatest:
    def test_returns_none_when_empty(self, db):
        app_id = _seed_app(db)
        assert tailored_repo.get_latest_for_application(db, app_id) is None

    def test_returns_most_recent(self, db):
        app_id = _seed_app(db)
        tailored_repo.create_tailored(
            db, application_id=app_id, content=_make_tailored(),
            validation=_make_validation(), profile_hash="h1",
            model="m", cost_cents=0.0,
        )
        # Second insertion with distinguishable summary
        second = TailoredResume(summary="Second version summary")
        tailored_repo.create_tailored(
            db, application_id=app_id, content=second,
            validation=_make_validation(), profile_hash="h2",
            model="m", cost_cents=0.0,
        )
        latest = tailored_repo.get_latest_for_application(db, app_id)
        assert latest.version == 2
        assert latest.content.summary == "Second version summary"

    def test_round_trip_content_and_validation(self, db):
        app_id = _seed_app(db)
        content = _make_tailored()
        validation = _make_validation(errors=1, warnings=2)
        tailored_repo.create_tailored(
            db, application_id=app_id, content=content,
            validation=validation, profile_hash="hh",
            model="claude-sonnet-4-6", cost_cents=2.5,
        )
        latest = tailored_repo.get_latest_for_application(db, app_id)
        assert latest.content.summary == "Tailored summary text."
        assert latest.content.experience[0].company == "Acme Corp"
        assert latest.content.experience[0].bullets[0].source_bullet_id == 1
        assert latest.validation.error_count == 1
        assert latest.validation.warning_count == 2
        assert latest.model == "claude-sonnet-4-6"
        assert latest.cost_cents == 2.5


class TestStaleness:
    def test_fresh_when_hash_matches(self, db):
        app_id = _seed_app(db)
        current_hash = compute_profile_hash(db)
        tailored_repo.create_tailored(
            db, application_id=app_id, content=_make_tailored(),
            validation=_make_validation(), profile_hash=current_hash,
            model="m", cost_cents=0.0,
        )
        latest = tailored_repo.get_latest_for_application(db, app_id)
        assert latest.is_stale is False

    def test_stale_when_profile_changes(self, db):
        app_id = _seed_app(db)
        current_hash = compute_profile_hash(db)
        tailored_repo.create_tailored(
            db, application_id=app_id, content=_make_tailored(),
            validation=_make_validation(), profile_hash=current_hash,
            model="m", cost_cents=0.0,
        )
        db.execute("UPDATE profile SET summary = 'changed' WHERE id = 1")
        db.commit()
        latest = tailored_repo.get_latest_for_application(db, app_id)
        assert latest.is_stale is True


class TestCascadeDelete:
    def test_deleting_application_removes_tailored(self, db):
        app_id = _seed_app(db)
        tailored_repo.create_tailored(
            db, application_id=app_id, content=_make_tailored(),
            validation=_make_validation(), profile_hash="h",
            model="m", cost_cents=0.0,
        )
        db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        db.commit()
        rows = tailored_repo.list_for_application(db, app_id)
        assert rows == []


class TestGetTailored:
    def test_get_by_id(self, db):
        app_id = _seed_app(db)
        new_id = tailored_repo.create_tailored(
            db, application_id=app_id, content=_make_tailored(),
            validation=_make_validation(), profile_hash="h",
            model="m", cost_cents=0.0,
        )
        row = tailored_repo.get_tailored(db, new_id)
        assert row is not None
        assert row.id == new_id

    def test_get_unknown_returns_none(self, db):
        assert tailored_repo.get_tailored(db, 99999) is None
