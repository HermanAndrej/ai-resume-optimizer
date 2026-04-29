"""Unit tests for chat_service: build_chat_context, parse_suggestions, and stream_llm."""
import sqlite3
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.db import run_migrations
from backend.models import (
    Application,
    ChatMessage,
    CompatibilityAnalysis,
    CompatibilityScore,
    KeywordOverlap,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
    TailoredResumeRow,
    ValidationResult,
)
from backend.services.chat_service import build_chat_context, parse_suggestions
from backend.services.llm_client import LLMAuthError, StreamEvent, stream_llm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_application(jd: str = "Python backend role") -> Application:
    return Application(
        id="app-1",
        job_title="Backend Engineer",
        company="Acme",
        jd=jd,
        analysis=CompatibilityAnalysis(
            keyword_overlap=KeywordOverlap(matched=[], missing=[], jd_only=[], match_pct=0.0),
            compatibility_score=CompatibilityScore(
                overall_fit_score=7, strengths=[], gaps=[], recommendations=[]
            ),
        ),
    )


def _make_tailored_row(summary: str = "Great summary") -> TailoredResumeRow:
    return TailoredResumeRow(
        id=1,
        application_id="app-1",
        version=1,
        content=TailoredResume(
            summary=summary,
            experience=[
                TailoredExperience(
                    company="Acme Corp",
                    title="SWE",
                    bullets=[TailoredBullet(text="Did stuff", source_bullet_id=1)],
                )
            ],
            skills=["Python", "FastAPI"],
            selected_projects=[],
        ),
        validation=ValidationResult(),
        profile_hash="h",
        model="claude-sonnet-4-6",
        cost_cents=1.0,
        created_at="2026-04-29",
    )


def _make_messages(n: int) -> list[ChatMessage]:
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(ChatMessage(id=i + 1, application_id="app-1", role=role, content=f"msg-{i}"))
    return msgs


# ---------------------------------------------------------------------------
# stream_llm
# ---------------------------------------------------------------------------


class _MockFinalMessage:
    class usage:
        input_tokens = 100
        output_tokens = 50
        cache_creation_input_tokens = 10
        cache_read_input_tokens = 20


class _MockMessageStream:
    def __init__(self, chunks: list[str]):
        self.text_stream = iter(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def get_final_message(self):
        return _MockFinalMessage()


class TestStreamLLM:
    def test_yields_token_events_then_done(self):
        mock_stream = _MockMessageStream(["Hello", ", ", "world"])

        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        with patch("backend.services.llm_client.anthropic.Anthropic", return_value=mock_client):
            events = list(stream_llm("sys", [{"role": "user", "content": "hi"}]))

        token_events = [e for e in events if e.type == "token"]
        done_events = [e for e in events if e.type == "done"]

        assert [e.text for e in token_events] == ["Hello", ", ", "world"]
        assert len(done_events) == 1

    def test_done_event_has_usage_info(self):
        mock_stream = _MockMessageStream(["chunk"])
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        with patch("backend.services.llm_client.anthropic.Anthropic", return_value=mock_client):
            events = list(stream_llm("sys", [{"role": "user", "content": "hi"}]))

        done = next(e for e in events if e.type == "done")
        assert "input_tokens" in done.usage_info
        assert "cost_cents" in done.usage_info
        assert done.usage_info["input_tokens"] == 100
        assert done.usage_info["output_tokens"] == 50

    def test_auth_error_translates_to_llm_auth_error(self):
        import anthropic as sdk

        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = sdk.AuthenticationError(
            message="bad key", response=MagicMock(status_code=401), body={}
        )

        with patch("backend.services.llm_client.anthropic.Anthropic", return_value=mock_client):
            with pytest.raises(LLMAuthError):
                list(stream_llm("sys", [{"role": "user", "content": "hi"}]))

    def test_logs_usage_to_db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        run_migrations(db_path)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row

        mock_stream = _MockMessageStream(["token"])
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream

        with patch("backend.services.llm_client.anthropic.Anthropic", return_value=mock_client):
            list(
                stream_llm(
                    "sys",
                    [{"role": "user", "content": "hi"}],
                    operation="chat_message",
                    db_conn=conn,
                )
            )

        row = conn.execute("SELECT * FROM usage_log WHERE operation = 'chat_message'").fetchone()
        assert row is not None
        conn.close()


# ---------------------------------------------------------------------------
# build_chat_context
# ---------------------------------------------------------------------------


class TestBuildChatContext:
    def test_system_prompt_contains_jd(self):
        app = _make_application(jd="Unique JD text for testing 12345")
        row = _make_tailored_row()
        system, msgs = build_chat_context(app, row, [], "hi")
        assert "Unique JD text for testing 12345" in system

    def test_system_prompt_contains_tailored_snapshot(self):
        app = _make_application()
        row = _make_tailored_row(summary="Snapshot summary marker XYZ")
        system, msgs = build_chat_context(app, row, [], "hi")
        assert "Snapshot summary marker XYZ" in system

    def test_new_user_message_appended(self):
        app = _make_application()
        row = _make_tailored_row()
        _, msgs = build_chat_context(app, row, [], "What should I improve?")
        assert msgs[-1] == {"role": "user", "content": "What should I improve?"}

    def test_history_included_in_messages(self):
        app = _make_application()
        row = _make_tailored_row()
        history = _make_messages(4)
        _, msgs = build_chat_context(app, row, history, "new msg")
        assert len(msgs) == 5  # 4 history + 1 new
        assert msgs[0]["content"] == "msg-0"

    def test_history_truncated_to_20(self):
        app = _make_application()
        row = _make_tailored_row()
        history = _make_messages(25)
        _, msgs = build_chat_context(app, row, history, "new msg")
        assert len(msgs) == 21  # last 20 history + 1 new
        # last history message before new msg should be msg-24
        assert msgs[-2]["content"] == "msg-24"

    def test_empty_history_works(self):
        app = _make_application()
        row = _make_tailored_row()
        _, msgs = build_chat_context(app, row, [], "first message")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"


# ---------------------------------------------------------------------------
# parse_suggestions
# ---------------------------------------------------------------------------


class TestParseSuggestions:
    def test_no_block_returns_empty(self):
        assert parse_suggestions("Just some prose here.") == []

    def test_malformed_json_returns_empty(self):
        text = "Some text.\n<<<SUGGESTIONS>>>\nnot valid json\n<<<END>>>"
        assert parse_suggestions(text) == []

    def test_valid_single_suggestion(self):
        text = (
            "Here is my suggestion.\n"
            "<<<SUGGESTIONS>>>\n"
            '[{"type": "replace_summary", "target": "summary", '
            '"proposed": "New summary text", "rationale": "clearer"}]\n'
            "<<<END>>>"
        )
        result = parse_suggestions(text)
        assert len(result) == 1
        assert result[0]["type"] == "replace_summary"
        assert result[0]["proposed"] == "New summary text"

    def test_valid_multiple_suggestions(self):
        text = (
            "Prose.\n<<<SUGGESTIONS>>>\n"
            '[{"type": "rephrase_bullet", "target": "experience[0].bullets[0]", "proposed": "Better bullet", "rationale": "x"},'
            '{"type": "swap_skill", "target": "skills[1]", "proposed": "Kubernetes", "rationale": "y"}]\n'
            "<<<END>>>"
        )
        result = parse_suggestions(text)
        assert len(result) == 2
        assert result[0]["type"] == "rephrase_bullet"
        assert result[1]["type"] == "swap_skill"

    def test_filters_out_invalid_type(self):
        text = (
            "<<<SUGGESTIONS>>>\n"
            '[{"type": "invalid_type", "target": "summary", "proposed": "x"},'
            '{"type": "replace_summary", "target": "summary", "proposed": "valid"}]\n'
            "<<<END>>>"
        )
        result = parse_suggestions(text)
        assert len(result) == 1
        assert result[0]["type"] == "replace_summary"

    def test_filters_out_missing_target(self):
        text = (
            "<<<SUGGESTIONS>>>\n"
            '[{"type": "replace_summary", "proposed": "x"}]\n'
            "<<<END>>>"
        )
        assert parse_suggestions(text) == []

    def test_filters_out_missing_proposed(self):
        text = (
            "<<<SUGGESTIONS>>>\n"
            '[{"type": "replace_summary", "target": "summary"}]\n'
            "<<<END>>>"
        )
        assert parse_suggestions(text) == []

    def test_extra_prose_after_end_marker(self):
        text = (
            "Prose before.\n"
            "<<<SUGGESTIONS>>>\n"
            '[{"type": "swap_skill", "target": "skills[0]", "proposed": "Go"}]\n'
            "<<<END>>>\n"
            "Some extra prose after the block."
        )
        result = parse_suggestions(text)
        assert len(result) == 1

    def test_mixed_valid_and_invalid_types(self):
        text = (
            "<<<SUGGESTIONS>>>\n"
            '['
            '{"type": "rephrase_bullet", "target": "experience[0].bullets[0]", "proposed": "A"}, '
            '{"type": "make_up_content", "target": "x", "proposed": "B"}, '
            '{"type": "replace_summary", "target": "summary", "proposed": "C"}'
            ']\n'
            "<<<END>>>"
        )
        result = parse_suggestions(text)
        assert len(result) == 2
        types = [r["type"] for r in result]
        assert "rephrase_bullet" in types
        assert "replace_summary" in types
