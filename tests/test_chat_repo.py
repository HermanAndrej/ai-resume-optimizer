"""Unit tests for chat_repo."""
import sqlite3
from pathlib import Path

import pytest

from backend.db import run_migrations
from backend.services import application_repo
from backend.services import chat_repo


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
        job_title="SWE",
        company="Corp",
        jd="job description",
        analysis_json=(
            '{"keyword_overlap":{"matched":[],"missing":[],"jd_only":[],"match_pct":0.0},'
            '"compatibility_score":{"overall_fit_score":5,"strengths":[],"gaps":[],"recommendations":[]}}'
        ),
        profile_hash="h",
    )


class TestCreateListMessages:
    def test_round_trip(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(
            db,
            application_id=app_id,
            role="user",
            content="Hello",
            model="claude-haiku-4-5",
            input_tokens=10,
            output_tokens=0,
            cost_cents=0.01,
        )
        assert isinstance(mid, int) and mid > 0
        msgs = chat_repo.list_messages(db, app_id)
        assert len(msgs) == 1
        m = msgs[0]
        assert m.role == "user"
        assert m.content == "Hello"
        assert m.model == "claude-haiku-4-5"
        assert m.input_tokens == 10
        assert m.cost_cents == pytest.approx(0.01)

    def test_chronological_order(self, db):
        app_id = _seed_app(db)
        chat_repo.create_message(db, application_id=app_id, role="user", content="first")
        chat_repo.create_message(db, application_id=app_id, role="assistant", content="second")
        msgs = chat_repo.list_messages(db, app_id)
        assert [m.content for m in msgs] == ["first", "second"]

    def test_get_message(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(db, application_id=app_id, role="user", content="hi")
        msg = chat_repo.get_message(db, mid)
        assert msg is not None
        assert msg.id == mid

    def test_get_unknown_returns_none(self, db):
        assert chat_repo.get_message(db, 99999) is None


class TestCascadeDelete:
    def test_deleting_app_removes_messages(self, db):
        app_id = _seed_app(db)
        chat_repo.create_message(db, application_id=app_id, role="user", content="hi")
        db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        db.commit()
        assert chat_repo.list_messages(db, app_id) == []

    def test_deleting_app_removes_suggestions(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(db, application_id=app_id, role="user", content="hi")
        chat_repo.create_suggestion(
            db,
            application_id=app_id,
            message_id=mid,
            suggestion_type="rephrase_bullet",
            target_section="experience[0].bullets[0]",
            proposed_value="Better bullet",
        )
        db.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        db.commit()
        assert chat_repo.list_pending_suggestions(db, app_id) == []


class TestSuggestions:
    def test_create_and_list_pending(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(db, application_id=app_id, role="user", content="fix it")
        sid = chat_repo.create_suggestion(
            db,
            application_id=app_id,
            message_id=mid,
            suggestion_type="replace_summary",
            target_section="summary",
            proposed_value="New summary",
            rationale="More punchy",
        )
        assert isinstance(sid, int) and sid > 0
        pending = chat_repo.list_pending_suggestions(db, app_id)
        assert len(pending) == 1
        s = pending[0]
        assert s.suggestion_type == "replace_summary"
        assert s.proposed_value == "New summary"

    def test_list_pending_excludes_applied_and_rejected(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(db, application_id=app_id, role="user", content="x")
        sid_a = chat_repo.create_suggestion(
            db, application_id=app_id, message_id=mid,
            suggestion_type="rephrase_bullet", target_section="experience[0].bullets[0]",
        )
        sid_r = chat_repo.create_suggestion(
            db, application_id=app_id, message_id=mid,
            suggestion_type="swap_skill", target_section="skills[1]",
        )
        sid_p = chat_repo.create_suggestion(
            db, application_id=app_id, message_id=mid,
            suggestion_type="replace_summary", target_section="summary",
        )
        chat_repo.set_suggestion_status(db, sid_a, "applied")
        chat_repo.set_suggestion_status(db, sid_r, "rejected")
        pending = chat_repo.list_pending_suggestions(db, app_id)
        assert len(pending) == 1
        assert pending[0].id == sid_p

    def test_get_suggestion(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(db, application_id=app_id, role="user", content="x")
        sid = chat_repo.create_suggestion(
            db, application_id=app_id, message_id=mid,
            suggestion_type="swap_skill", target_section="skills[0]",
        )
        s = chat_repo.get_suggestion(db, sid)
        assert s is not None
        assert s.id == sid

    def test_get_suggestion_unknown_returns_none(self, db):
        assert chat_repo.get_suggestion(db, 99999) is None


class TestSetSuggestionStatus:
    def test_set_status(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(db, application_id=app_id, role="user", content="x")
        sid = chat_repo.create_suggestion(
            db, application_id=app_id, message_id=mid,
            suggestion_type="rephrase_bullet", target_section="experience[0].bullets[0]",
        )
        result = chat_repo.set_suggestion_status(db, sid, "applied")
        assert result is True
        s = chat_repo.get_suggestion(db, sid)
        assert s.status == "applied"

    def test_invalid_status_raises(self, db):
        app_id = _seed_app(db)
        mid = chat_repo.create_message(db, application_id=app_id, role="user", content="x")
        sid = chat_repo.create_suggestion(
            db, application_id=app_id, message_id=mid,
            suggestion_type="swap_skill", target_section="skills[0]",
        )
        with pytest.raises(ValueError, match="status must be one of"):
            chat_repo.set_suggestion_status(db, sid, "bogus")

    def test_unknown_id_returns_false(self, db):
        result = chat_repo.set_suggestion_status(db, 99999, "applied")
        assert result is False
