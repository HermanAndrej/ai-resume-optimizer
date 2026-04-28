"""Build a renderer-agnostic ExportResume from tailored content + profile."""
import re
import sqlite3

from backend.models import (
    ExportExperience,
    ExportResume,
    ExportSkillGroup,
    ProjectEntry,
    Skill,
    TailoredResume,
)
from backend.services import profile_repo

_FILENAME_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, fallback: str) -> str:
    """Strip filesystem-unsafe characters; return fallback when empty.

    Removes <>:"/\\|?* and control chars. Collapses whitespace. Strips
    leading/trailing dots and spaces (Windows hates trailing dots).
    """
    if not name:
        return fallback
    cleaned = _FILENAME_BAD_CHARS.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or fallback


def _group_skills_by_category(
    profile_skills: dict[str, list[Skill]],
    tailored_skills: list[str],
) -> list[ExportSkillGroup]:
    """Group tailored skill names by their profile category, preserving order.

    A skill not found in the profile is placed in "Skills" so it's still
    rendered (even if the validator flagged it).
    """
    # Build a lowercased lookup: skill_name -> category
    name_to_category: dict[str, str] = {}
    for category, skills in profile_skills.items():
        for s in skills:
            if s.skill:
                name_to_category[s.skill.strip().lower()] = category

    groups_in_order: list[str] = []
    grouped: dict[str, list[str]] = {}
    for raw in tailored_skills:
        if not raw:
            continue
        cat = name_to_category.get(raw.strip().lower(), "Skills")
        if cat not in grouped:
            grouped[cat] = []
            groups_in_order.append(cat)
        grouped[cat].append(raw)

    return [ExportSkillGroup(category=c, items=grouped[c]) for c in groups_in_order]


def _filter_projects(
    all_projects: list[ProjectEntry], selected_names: list[str]
) -> list[ProjectEntry]:
    """Return profile projects whose names match selected_projects (case-insensitive)."""
    if not selected_names:
        return []
    wanted = {n.strip().lower() for n in selected_names if n}
    return [p for p in all_projects if (p.name or "").strip().lower() in wanted]


def build_export_resume(
    conn: sqlite3.Connection, tailored: TailoredResume
) -> ExportResume:
    """Build an ExportResume by combining tailored content + live profile data.

    Personal info, education, certifications, and project bodies come from
    the live profile (not the tailored snapshot). Summary, experience, and
    skills come from the tailored content. Skills are re-grouped by their
    profile category for ATS-friendly section rendering.
    """
    personal = profile_repo.get_personal_info(conn)

    experience = [
        ExportExperience(
            company=exp.company,
            title=exp.title,
            location=exp.location,
            start_date=exp.start_date,
            end_date=exp.end_date,
            bullets=[b.text for b in exp.bullets if b.text],
        )
        for exp in tailored.experience
    ]

    skills_grouped = _group_skills_by_category(
        profile_repo.list_skills_grouped(conn), tailored.skills
    )
    projects = _filter_projects(profile_repo.list_projects(conn), tailored.selected_projects)
    education = profile_repo.list_education(conn)
    certifications = profile_repo.list_certifications(conn)

    return ExportResume(
        personal=personal,
        summary=tailored.summary,
        experience=experience,
        skills_grouped=skills_grouped,
        projects=projects,
        education=education,
        certifications=certifications,
    )
