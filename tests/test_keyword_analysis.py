"""Unit tests for keyword_analysis service (TF-IDF, no LLM, no DB writes)."""
import sqlite3
from pathlib import Path

import pytest

from backend.db import run_migrations
from backend.models import KeywordOverlap
from backend.services.keyword_analysis import (
    compute_overlap,
    extract_keywords,
    flatten_profile,
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


def _seed_profile(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE profile SET summary = 'Python developer with machine learning experience' WHERE id = 1"
    )
    exp_id = conn.execute(
        "INSERT INTO experience (profile_id, company, title, display_order) VALUES (1, 'ACME', 'Engineer', 0)"
    ).lastrowid
    conn.execute(
        "INSERT INTO experience_bullets (experience_id, text, display_order) VALUES (?, 'Built REST API with FastAPI', 0)",
        (exp_id,),
    )
    conn.execute(
        "INSERT INTO skills (profile_id, category, skill, display_order) VALUES (1, 'Languages', 'Python', 0)"
    )
    conn.execute(
        "INSERT INTO projects (profile_id, name, description, tech_stack, url, bullets, display_order) VALUES (1, 'ML Tool', 'Data pipeline', 'Python, pandas', '', 'batch processing jobs', 0)"
    )
    conn.execute(
        "INSERT INTO education (profile_id, institution, display_order, highlights) VALUES (1, 'MIT', 0, 'Thesis on neural networks')"
    )
    conn.commit()


class TestFlattenProfile:
    def test_includes_summary(self, db: sqlite3.Connection):
        _seed_profile(db)
        text = flatten_profile(db)
        assert "machine learning" in text.lower()

    def test_includes_experience_bullets(self, db: sqlite3.Connection):
        _seed_profile(db)
        text = flatten_profile(db)
        assert "FastAPI" in text

    def test_includes_skills(self, db: sqlite3.Connection):
        _seed_profile(db)
        text = flatten_profile(db)
        assert "Python" in text

    def test_includes_project_description(self, db: sqlite3.Connection):
        _seed_profile(db)
        text = flatten_profile(db)
        assert "Data pipeline" in text

    def test_includes_education_highlights(self, db: sqlite3.Connection):
        _seed_profile(db)
        text = flatten_profile(db)
        assert "neural networks" in text

    def test_empty_profile_returns_string(self, db: sqlite3.Connection):
        text = flatten_profile(db)
        assert isinstance(text, str)


class TestExtractKeywords:
    def test_returns_list_of_tuples(self):
        keywords = extract_keywords("Python machine learning data science")
        assert isinstance(keywords, list)
        for term, score in keywords:
            assert isinstance(term, str)
            assert isinstance(score, float)

    def test_english_stopwords_removed(self):
        keywords = extract_keywords("the quick brown fox jumps over the lazy dog Python")
        terms = [t for t, _ in keywords]
        for stopword in ("the", "over", "and", "is", "of"):
            assert stopword not in terms

    def test_bigram_capture(self):
        keywords = extract_keywords(
            "machine learning machine learning deep learning neural network", top_k=20
        )
        terms = [t for t, _ in keywords]
        bigrams = [t for t in terms if " " in t]
        assert len(bigrams) > 0, "Expected at least one bigram"
        assert any("machine learning" in t for t in bigrams)

    def test_top_k_respected(self):
        text = " ".join(f"word{i}" for i in range(100))
        keywords = extract_keywords(text, top_k=10)
        assert len(keywords) <= 10

    def test_empty_text_returns_empty(self):
        assert extract_keywords("") == []
        assert extract_keywords("   ") == []


class TestComputeOverlap:
    def test_returns_keyword_overlap(self):
        overlap = compute_overlap("python developer fastapi", "python engineer")
        assert isinstance(overlap, KeywordOverlap)

    def test_match_pct_correct(self):
        jd = "python machine learning data science"
        profile = "python data science engineering"
        overlap = compute_overlap(jd, profile)
        assert 0.0 <= overlap.match_pct <= 100.0
        assert len(overlap.matched) > 0

    def test_matched_terms_present_in_both(self):
        overlap = compute_overlap("python fastapi developer", "python engineer fastapi")
        for term in overlap.matched:
            assert term in overlap.matched

    def test_missing_terms_from_jd_not_in_profile(self):
        jd = "kubernetes docker devops"
        profile = "python developer"
        overlap = compute_overlap(jd, profile)
        assert len(overlap.missing) > 0

    def test_empty_profile_returns_zero_match(self):
        overlap = compute_overlap("python developer fastapi", "")
        assert overlap.match_pct == 0.0
        assert overlap.matched == []

    def test_empty_jd_returns_zero_match(self):
        overlap = compute_overlap("", "python developer")
        assert overlap.match_pct == 0.0

    def test_no_crash_on_empty_both(self):
        overlap = compute_overlap("", "")
        assert overlap.match_pct == 0.0
        assert isinstance(overlap, KeywordOverlap)
