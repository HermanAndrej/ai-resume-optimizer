"""Pure function for applying a chat suggestion to a TailoredResume."""
import re

from ..models import Suggestion, TailoredBullet, TailoredResume

_RE_BULLET = re.compile(r"experience\[(\d+)\]\.bullets\[(\d+)\]")
_RE_SKILL = re.compile(r"skills\[(\d+)\]")


def parse_target_index(target: str, suggestion_type: str) -> tuple[int, ...]:
    """Parse the target_section string into integer indices.

    Returns:
        ()      for "replace_summary" (no indices needed)
        (i,)    for "swap_skill" — skills[i]
        (i, j)  for "rephrase_bullet" — experience[i].bullets[j]

    Raises ValueError if the target format does not match the suggestion type
    or if indices are non-numeric.
    """
    if suggestion_type == "replace_summary":
        return ()
    if suggestion_type == "rephrase_bullet":
        m = _RE_BULLET.fullmatch(target)
        if not m:
            raise ValueError(
                f"rephrase_bullet target must match 'experience[i].bullets[j]', got: {target!r}"
            )
        return int(m.group(1)), int(m.group(2))
    if suggestion_type == "swap_skill":
        m = _RE_SKILL.fullmatch(target)
        if not m:
            raise ValueError(
                f"swap_skill target must match 'skills[i]', got: {target!r}"
            )
        return (int(m.group(1)),)
    raise ValueError(f"Unknown suggestion_type: {suggestion_type!r}")


def apply_suggestion(tailored: TailoredResume, suggestion: Suggestion) -> TailoredResume:
    """Return a new TailoredResume with the suggestion applied.

    Raises ValueError for unknown suggestion_type or out-of-range indices.
    The original tailored object is never mutated.
    """
    stype = suggestion.suggestion_type
    proposed = suggestion.proposed_value
    indices = parse_target_index(suggestion.target_section, stype)

    if stype == "replace_summary":
        return tailored.model_copy(update={"summary": proposed})

    if stype == "rephrase_bullet":
        i, j = indices
        if i >= len(tailored.experience):
            raise ValueError(
                f"experience index {i} out of range (len={len(tailored.experience)})"
            )
        exp = tailored.experience[i]
        if j >= len(exp.bullets):
            raise ValueError(
                f"bullets index {j} out of range (len={len(exp.bullets)})"
            )
        original_bullet = exp.bullets[j]
        new_bullet = TailoredBullet(
            text=proposed,
            source_bullet_id=original_bullet.source_bullet_id,
        )
        new_bullets = list(exp.bullets)
        new_bullets[j] = new_bullet
        new_exp = exp.model_copy(update={"bullets": new_bullets})
        new_experience = list(tailored.experience)
        new_experience[i] = new_exp
        return tailored.model_copy(update={"experience": new_experience})

    if stype == "swap_skill":
        (i,) = indices
        if i >= len(tailored.skills):
            raise ValueError(
                f"skills index {i} out of range (len={len(tailored.skills)})"
            )
        new_skills = list(tailored.skills)
        new_skills[i] = proposed
        return tailored.model_copy(update={"skills": new_skills})

    raise ValueError(f"Unknown suggestion_type: {stype!r}")
