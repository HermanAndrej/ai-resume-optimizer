"""Unit tests for resume_tailor: profile context builder + generation."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.db import run_migrations
from backend.models import TailoredResume
from backend.prompts.resume_tailor import TAILOR_SYSTEM
from backend.services import resume_tailor
from backend.services.llm_client import LLMError, LLMInvalidJSONError


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    run_migrations(db_path)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def _seed_profile(db: sqlite3.Connection) -> dict[str, int]:
    """Returns dict mapping logical labels to DB ids for assertion."""
    db.execute(
        "UPDATE profile SET full_name=?, email=?, summary=? WHERE id=1",
        ("Jane Doe", "jane@example.com", "Senior backend engineer with 8 years of Python."),
    )
    cur = db.execute(
        "INSERT INTO experience (profile_id, company, title, location, start_date, end_date, description) "
        "VALUES (1, 'Acme Corp', 'Senior Engineer', 'Remote', '2020', 'Present', 'Backend services team')"
    )
    exp_id = cur.lastrowid
    cur = db.execute(
        "INSERT INTO experience_bullets (experience_id, text) VALUES (?, 'Reduced p99 latency by 40% via caching')",
        (exp_id,),
    )
    bullet1 = cur.lastrowid
    cur = db.execute(
        "INSERT INTO experience_bullets (experience_id, text) VALUES (?, 'Migrated 12 services to Kubernetes')",
        (exp_id,),
    )
    bullet2 = cur.lastrowid
    db.execute(
        "INSERT INTO skills (profile_id, category, skill) VALUES (1, 'Languages', 'Python'), (1, 'Languages', 'Go'), (1, 'Cloud', 'Kubernetes')"
    )
    db.execute(
        "INSERT INTO projects (profile_id, name, description) VALUES (1, 'logsift', 'CLI for log analysis')"
    )
    db.commit()
    return {"experience": exp_id, "bullet1": bullet1, "bullet2": bullet2}


CANNED_LLM_RESPONSE = json.dumps({
    "summary": "Backend engineer with 8 years of Python experience.",
    "experience": [
        {
            "company": "Acme Corp",
            "title": "Senior Engineer",
            "location": "Remote",
            "start_date": "2020",
            "end_date": "Present",
            "bullets": [
                {"text": "Cut p99 latency 40% with a caching layer", "source_bullet_id": None}
            ],
        }
    ],
    "skills": ["Python", "Kubernetes"],
    "selected_projects": ["logsift"],
})


class TestBuildProfileContext:
    def test_returns_personal_summary_and_top_level_keys(self, db):
        _seed_profile(db)
        ctx = resume_tailor.build_profile_context(db)
        assert ctx["personal"]["full_name"] == "Jane Doe"
        assert ctx["personal"]["email"] == "jane@example.com"
        assert "8 years of Python" in ctx["summary"]
        assert set(ctx.keys()) >= {
            "personal", "summary", "experience", "education", "skills", "projects", "certifications",
        }

    def test_experience_includes_bullets_with_ids(self, db):
        ids = _seed_profile(db)
        ctx = resume_tailor.build_profile_context(db)
        assert len(ctx["experience"]) == 1
        exp = ctx["experience"][0]
        assert exp["company"] == "Acme Corp"
        assert exp["id"] == ids["experience"]
        bullet_ids = [b["id"] for b in exp["bullets"]]
        assert ids["bullet1"] in bullet_ids
        assert ids["bullet2"] in bullet_ids

    def test_skills_present_filtered_for_blanks(self, db):
        _seed_profile(db)
        ctx = resume_tailor.build_profile_context(db)
        skills = [s["skill"] for s in ctx["skills"]]
        assert "Python" in skills
        assert "Kubernetes" in skills

    def test_projects_present(self, db):
        _seed_profile(db)
        ctx = resume_tailor.build_profile_context(db)
        names = [p["name"] for p in ctx["projects"]]
        assert "logsift" in names


class TestSystemPrompt:
    def test_prompt_forbids_fabrication(self):
        # The prompt MUST contain explicit no-fabrication language.
        # This is a guardrail — if someone weakens the prompt, this test catches it.
        for required in ["NEVER invent", "fabrication", "MUST come from the source profile"]:
            assert required in TAILOR_SYSTEM, f"Missing required phrase: {required!r}"

    def test_prompt_specifies_source_bullet_id(self):
        assert "source_bullet_id" in TAILOR_SYSTEM


class TestGenerateTailoredResume:
    def test_happy_path_returns_parsed_resume(self, db):
        _seed_profile(db)
        with patch(
            "backend.services.resume_tailor.call_llm",
            return_value=(CANNED_LLM_RESPONSE, {"cost_cents": 1.5, "model": "claude-sonnet-4-6"}),
        ):
            tailored, profile_hash, usage = resume_tailor.generate_tailored_resume(
                db, "JD: looking for Python and Kubernetes."
            )
        assert isinstance(tailored, TailoredResume)
        assert tailored.experience[0].company == "Acme Corp"
        assert "Python" in tailored.skills
        assert profile_hash != ""
        assert usage["cost_cents"] == 1.5

    def test_passes_profile_context_to_llm(self, db):
        _seed_profile(db)
        with patch(
            "backend.services.resume_tailor.call_llm",
            return_value=(CANNED_LLM_RESPONSE, {"cost_cents": 0.0, "model": "m"}),
        ) as mock_call:
            resume_tailor.generate_tailored_resume(db, "JD text here")
        kwargs = mock_call.call_args.kwargs
        # System prompt is the no-fabrication template
        assert kwargs["system"] == TAILOR_SYSTEM
        # User message contains both profile JSON and the JD
        user_msg = kwargs["messages"][0]["content"]
        assert "SOURCE PROFILE" in user_msg
        assert "Acme Corp" in user_msg
        assert "JD text here" in user_msg
        # Caching enabled, Sonnet model
        assert kwargs["use_cache"] is True
        assert kwargs["model"] == "claude-sonnet-4-6"

    def test_invalid_json_raises_invalid_json_error(self, db):
        _seed_profile(db)
        with patch(
            "backend.services.resume_tailor.call_llm",
            return_value=("not json at all", {"cost_cents": 0.0, "model": "m"}),
        ):
            with pytest.raises(LLMInvalidJSONError):
                resume_tailor.generate_tailored_resume(db, "JD")

    def test_schema_mismatch_raises_invalid_json_error(self, db):
        _seed_profile(db)
        # Valid JSON but wrong shape (skills should be list[str], not list[int])
        bad = json.dumps({"summary": "x", "experience": [], "skills": [123, 456]})
        with patch(
            "backend.services.resume_tailor.call_llm",
            return_value=(bad, {"cost_cents": 0.0, "model": "m"}),
        ):
            with pytest.raises(LLMInvalidJSONError):
                resume_tailor.generate_tailored_resume(db, "JD")

    def test_llm_error_propagates(self, db):
        _seed_profile(db)
        with patch(
            "backend.services.resume_tailor.call_llm",
            side_effect=LLMError("API down"),
        ):
            with pytest.raises(LLMError):
                resume_tailor.generate_tailored_resume(db, "JD")
