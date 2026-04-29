"""Unit tests for suggestion_apply.apply_suggestion."""
import pytest

from backend.models import (
    Suggestion,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)
from backend.services.suggestion_apply import apply_suggestion


def _make_tailored() -> TailoredResume:
    return TailoredResume(
        summary="Original summary.",
        experience=[
            TailoredExperience(
                company="Acme Corp",
                title="SWE",
                bullets=[
                    TailoredBullet(text="First bullet", source_bullet_id=1),
                    TailoredBullet(text="Second bullet", source_bullet_id=2),
                ],
            ),
            TailoredExperience(
                company="Beta Inc",
                title="Junior SWE",
                bullets=[
                    TailoredBullet(text="Only bullet", source_bullet_id=3),
                ],
            ),
        ],
        skills=["Python", "FastAPI", "Docker"],
        selected_projects=["my-project"],
    )


def _suggestion(stype: str, target: str, proposed: str) -> Suggestion:
    return Suggestion(
        id=1,
        application_id="app-1",
        message_id=1,
        suggestion_type=stype,
        target_section=target,
        proposed_value=proposed,
    )


class TestReplaceSummary:
    def test_replaces_summary(self):
        t = _make_tailored()
        s = _suggestion("replace_summary", "summary", "New summary text.")
        result = apply_suggestion(t, s)
        assert result.summary == "New summary text."

    def test_does_not_mutate_original(self):
        t = _make_tailored()
        apply_suggestion(t, _suggestion("replace_summary", "summary", "Changed"))
        assert t.summary == "Original summary."

    def test_other_fields_unchanged(self):
        t = _make_tailored()
        result = apply_suggestion(t, _suggestion("replace_summary", "summary", "New"))
        assert result.skills == t.skills
        assert len(result.experience) == len(t.experience)


class TestRephraseBullet:
    def test_replaces_bullet_text(self):
        t = _make_tailored()
        s = _suggestion("rephrase_bullet", "experience[0].bullets[1]", "Improved second bullet")
        result = apply_suggestion(t, s)
        assert result.experience[0].bullets[1].text == "Improved second bullet"

    def test_preserves_source_bullet_id(self):
        t = _make_tailored()
        s = _suggestion("rephrase_bullet", "experience[0].bullets[0]", "Rephrased first bullet")
        result = apply_suggestion(t, s)
        assert result.experience[0].bullets[0].source_bullet_id == 1

    def test_other_bullets_unchanged(self):
        t = _make_tailored()
        s = _suggestion("rephrase_bullet", "experience[0].bullets[0]", "Changed")
        result = apply_suggestion(t, s)
        assert result.experience[0].bullets[1].text == "Second bullet"

    def test_second_experience(self):
        t = _make_tailored()
        s = _suggestion("rephrase_bullet", "experience[1].bullets[0]", "Better only bullet")
        result = apply_suggestion(t, s)
        assert result.experience[1].bullets[0].text == "Better only bullet"
        assert result.experience[1].bullets[0].source_bullet_id == 3

    def test_does_not_mutate_original(self):
        t = _make_tailored()
        apply_suggestion(t, _suggestion("rephrase_bullet", "experience[0].bullets[0]", "X"))
        assert t.experience[0].bullets[0].text == "First bullet"

    def test_experience_index_out_of_range_raises(self):
        t = _make_tailored()
        s = _suggestion("rephrase_bullet", "experience[5].bullets[0]", "X")
        with pytest.raises(ValueError, match="experience index"):
            apply_suggestion(t, s)

    def test_bullet_index_out_of_range_raises(self):
        t = _make_tailored()
        s = _suggestion("rephrase_bullet", "experience[0].bullets[99]", "X")
        with pytest.raises(ValueError, match="bullets index"):
            apply_suggestion(t, s)

    def test_invalid_target_format_raises(self):
        t = _make_tailored()
        s = _suggestion("rephrase_bullet", "bullets[0]", "X")
        with pytest.raises(ValueError, match="rephrase_bullet target"):
            apply_suggestion(t, s)


class TestSwapSkill:
    def test_swaps_skill(self):
        t = _make_tailored()
        s = _suggestion("swap_skill", "skills[1]", "Kubernetes")
        result = apply_suggestion(t, s)
        assert result.skills[1] == "Kubernetes"

    def test_other_skills_unchanged(self):
        t = _make_tailored()
        s = _suggestion("swap_skill", "skills[0]", "Go")
        result = apply_suggestion(t, s)
        assert result.skills[1] == "FastAPI"
        assert result.skills[2] == "Docker"

    def test_does_not_mutate_original(self):
        t = _make_tailored()
        apply_suggestion(t, _suggestion("swap_skill", "skills[0]", "Go"))
        assert t.skills[0] == "Python"

    def test_index_out_of_range_raises(self):
        t = _make_tailored()
        s = _suggestion("swap_skill", "skills[99]", "Go")
        with pytest.raises(ValueError, match="skills index"):
            apply_suggestion(t, s)

    def test_invalid_target_format_raises(self):
        t = _make_tailored()
        s = _suggestion("swap_skill", "skill[0]", "Go")
        with pytest.raises(ValueError, match="swap_skill target"):
            apply_suggestion(t, s)


class TestUnknownType:
    def test_unknown_type_raises(self):
        t = _make_tailored()
        s = Suggestion(
            id=1,
            application_id="app-1",
            message_id=1,
            suggestion_type="rephrase_bullet",  # valid for construction
            target_section="experience[0].bullets[0]",
            proposed_value="x",
        )
        # Manually override to simulate an unexpected type reaching apply_suggestion
        object.__setattr__(s, "suggestion_type", "make_up_content")
        with pytest.raises(ValueError, match="Unknown suggestion_type"):
            apply_suggestion(t, s)
