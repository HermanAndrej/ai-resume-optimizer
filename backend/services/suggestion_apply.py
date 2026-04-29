"""Pure function for applying a chat suggestion to a TailoredResume."""
import re

from ..models import Suggestion, TailoredBullet, TailoredResume


def apply_suggestion(tailored: TailoredResume, suggestion: Suggestion) -> TailoredResume:
    """Return a new TailoredResume with the suggestion applied.

    Raises ValueError for unknown suggestion_type or out-of-range indices.
    The original tailored object is never mutated.
    """
    stype = suggestion.suggestion_type
    target = suggestion.target_section
    proposed = suggestion.proposed_value

    if stype == "replace_summary":
        return tailored.model_copy(update={"summary": proposed})

    if stype == "rephrase_bullet":
        m = re.fullmatch(r"experience\[(\d+)\]\.bullets\[(\d+)\]", target)
        if not m:
            raise ValueError(
                f"rephrase_bullet target must match 'experience[i].bullets[j]', got: {target!r}"
            )
        i, j = int(m.group(1)), int(m.group(2))
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
        m = re.fullmatch(r"skills\[(\d+)\]", target)
        if not m:
            raise ValueError(
                f"swap_skill target must match 'skills[i]', got: {target!r}"
            )
        i = int(m.group(1))
        if i >= len(tailored.skills):
            raise ValueError(
                f"skills index {i} out of range (len={len(tailored.skills)})"
            )
        new_skills = list(tailored.skills)
        new_skills[i] = proposed
        return tailored.model_copy(update={"skills": new_skills})

    raise ValueError(f"Unknown suggestion_type: {stype!r}")
