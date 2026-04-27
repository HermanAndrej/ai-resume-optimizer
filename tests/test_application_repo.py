"""Unit tests for application_repo + compat_runner helpers."""
import json
import sqlite3
from pathlib import Path

import pytest

from backend.db import run_migrations
from backend.models import CompatibilityAnalysis, CompatibilityScore, KeywordOverlap
from backend.services import application_repo
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


def _make_analysis_json(score: int = 7) -> str:
    analysis = CompatibilityAnalysis(
        keyword_overlap=KeywordOverlap(matched=["python"], missing=["kubernetes"], match_pct=50.0),
        compatibility_score=CompatibilityScore(
            overall_fit_score=score,
            strengths=["Strong Python"],
            gaps=["Missing K8s"],
            recommendations=["Add K8s exposure"],
        ),
    )
    return analysis.model_dump_json()


def _seed_app(db: sqlite3.Connection, *, profile_hash: str = "abc123", source_url: str = "") -> str:
    return application_repo.create_application(
        db,
        job_title="Senior Engineer",
        company="Acme",
        jd="JD text",
        analysis_json=_make_analysis_json(),
        profile_hash=profile_hash,
        source_url=source_url,
    )


class TestProfileHash:
    def test_returns_consistent_hash(self, db):
        h1 = compute_profile_hash(db)
        h2 = compute_profile_hash(db)
        assert h1 == h2
        assert len(h1) == 16

    def test_changes_when_profile_changes(self, db):
        h1 = compute_profile_hash(db)
        db.execute("UPDATE profile SET summary = 'New content here' WHERE id = 1")
        db.commit()
        h2 = compute_profile_hash(db)
        assert h1 != h2


class TestGetApplication:
    def test_returns_app_with_new_fields(self, db):
        app_id = _seed_app(db, source_url="https://jobs.example.com/123")
        app = application_repo.get_application(db, app_id)
        assert app is not None
        assert app.status == "analyzed"
        assert app.notes == ""
        assert app.source_url == "https://jobs.example.com/123"
        assert app.archived is False

    def test_is_stale_when_hash_mismatches(self, db):
        app_id = _seed_app(db, profile_hash="stale_hash_value")
        app = application_repo.get_application(db, app_id)
        assert app.is_stale is True

    def test_is_fresh_when_hash_matches(self, db):
        current_hash = compute_profile_hash(db)
        app_id = _seed_app(db, profile_hash=current_hash)
        app = application_repo.get_application(db, app_id)
        assert app.is_stale is False


class TestIsStaleFor:
    def test_fresh_when_hash_matches(self, db):
        current_hash = compute_profile_hash(db)
        app_id = _seed_app(db, profile_hash=current_hash)
        assert application_repo.is_stale_for(db, app_id) is False

    def test_stale_when_profile_changes(self, db):
        current_hash = compute_profile_hash(db)
        app_id = _seed_app(db, profile_hash=current_hash)
        db.execute("UPDATE profile SET summary = 'Different content' WHERE id = 1")
        db.commit()
        assert application_repo.is_stale_for(db, app_id) is True

    def test_unknown_id_returns_false(self, db):
        assert application_repo.is_stale_for(db, "nonexistent") is False


class TestUpdateMetadata:
    def test_updates_all_fields(self, db):
        app_id = _seed_app(db)
        ok = application_repo.update_metadata(
            db, app_id,
            status="applied",
            notes="Submitted via referral",
            source_url="https://jobs.example.com/abc",
            jd="Updated JD text",
        )
        assert ok
        app = application_repo.get_application(db, app_id)
        assert app.status == "applied"
        assert app.notes == "Submitted via referral"
        assert app.source_url == "https://jobs.example.com/abc"
        assert app.jd == "Updated JD text"

    def test_invalid_status_raises(self, db):
        app_id = _seed_app(db)
        with pytest.raises(ValueError):
            application_repo.update_metadata(
                db, app_id,
                status="not_a_real_status",
                notes="", source_url="", jd="x",
            )

    def test_unknown_id_returns_false(self, db):
        ok = application_repo.update_metadata(
            db, "nonexistent",
            status="applied", notes="", source_url="", jd="x",
        )
        assert ok is False


class TestSetArchived:
    def test_archive_then_unarchive(self, db):
        app_id = _seed_app(db)
        assert application_repo.set_archived(db, app_id, True)
        app = application_repo.get_application(db, app_id)
        assert app.archived is True

        assert application_repo.set_archived(db, app_id, False)
        app = application_repo.get_application(db, app_id)
        assert app.archived is False


class TestUpdateAnalysis:
    def test_updates_analysis_and_hash(self, db):
        app_id = _seed_app(db, profile_hash="old_hash")
        new_analysis = _make_analysis_json(score=9)
        ok = application_repo.update_analysis(db, app_id, new_analysis, "new_hash")
        assert ok
        app = application_repo.get_application(db, app_id)
        assert app.analysis.compatibility_score.overall_fit_score == 9
        assert app.profile_hash == "new_hash"


class TestListApplications:
    def test_excludes_archived_by_default(self, db):
        active_id = _seed_app(db)
        archived_id = _seed_app(db)
        application_repo.set_archived(db, archived_id, True)

        rows = application_repo.list_applications(db)
        ids = [r.id for r in rows]
        assert active_id in ids
        assert archived_id not in ids

    def test_includes_archived_when_flag_set(self, db):
        active_id = _seed_app(db)
        archived_id = _seed_app(db)
        application_repo.set_archived(db, archived_id, True)

        rows = application_repo.list_applications(db, include_archived=True)
        ids = [r.id for r in rows]
        assert active_id in ids
        assert archived_id in ids

    def test_summary_has_status_and_stale(self, db):
        app_id = _seed_app(db, profile_hash="stale")
        rows = application_repo.list_applications(db)
        assert rows[0].id == app_id
        assert rows[0].status == "analyzed"
        assert rows[0].is_stale is True
