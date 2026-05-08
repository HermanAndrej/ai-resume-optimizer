"""Unit tests for word_diff in backend/services/text_diff.py."""
import pytest

from backend.services.text_diff import word_diff


class TestWordDiff:
    def test_single_word_change(self):
        result = str(word_diff("Reduced latency by 40%", "Reduced latency by 50%"))
        assert "40%" in result
        assert "50%" in result
        assert "diff-del" in result
        assert "diff-ins" in result

    def test_unchanged_text_has_no_markup(self):
        result = str(word_diff("exactly the same", "exactly the same"))
        assert "diff-del" not in result
        assert "diff-ins" not in result
        assert "exactly" in result
        assert "same" in result

    def test_multi_word_insert(self):
        result = str(word_diff("Led team", "Led cross-functional team of engineers"))
        assert "diff-ins" in result
        assert "diff-del" not in result

    def test_multi_word_delete(self):
        result = str(word_diff("Improved system reliability and uptime metrics daily", "Improved reliability"))
        assert "diff-del" in result

    def test_html_escapes_user_text(self):
        result = str(word_diff("<script>alert(1)</script>", "<b>safe</b>"))
        assert "<script>" not in result
        assert "&lt;script&gt;" in result or "script" not in result or "diff-del" in result
        # Crucially, no raw <script> tag in output
        assert "<script>" not in result

    def test_html_escapes_proposed_text(self):
        result = str(word_diff("normal text", "<img src=x onerror=alert(1)>"))
        assert "<img" not in result
        assert "&lt;img" in result or "diff-ins" in result

    def test_returns_markup_safe_type(self):
        from markupsafe import Markup
        result = word_diff("old text", "new text")
        assert isinstance(result, Markup)

    def test_empty_old_is_pure_addition(self):
        result = str(word_diff("", "brand new text"))
        assert "diff-ins" in result
        assert "diff-del" not in result

    def test_empty_new_is_pure_deletion(self):
        result = str(word_diff("some old text", ""))
        assert "diff-del" in result
        assert "diff-ins" not in result

    def test_both_empty_returns_empty(self):
        result = str(word_diff("", ""))
        assert result.strip() == ""
