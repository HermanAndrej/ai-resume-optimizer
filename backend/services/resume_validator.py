"""Deterministic validator for tailored resumes — flags fabrications.

Strategy: build a "source index" of allowed claims from the profile (companies,
titles, skills, project names, bullet texts), then walk the tailored resume
and emit ValidationIssue records for anything that can't be traced back.
"""
import re
import sqlite3
from dataclasses import dataclass, field

from backend.models import (
    TailoredResume,
    ValidationIssue,
    ValidationResult,
)

PROFILE_ID = 1


def _norm(s: str) -> str:
    return (s or "").strip().lower()


@dataclass
class SourceIndex:
    """Allowed-claim sets derived from the profile, all normalized to lowercase."""
    companies: set[str] = field(default_factory=set)
    titles: set[str] = field(default_factory=set)
    skills: set[str] = field(default_factory=set)
    project_names: set[str] = field(default_factory=set)
    bullet_texts_by_id: dict[int, str] = field(default_factory=dict)
    all_source_text: str = ""  # concatenated lowercase text for numeric substring checks


def build_source_index(conn: sqlite3.Connection) -> SourceIndex:
    idx = SourceIndex()
    text_parts: list[str] = []

    profile = conn.execute(
        "SELECT summary FROM profile WHERE id = ?", (PROFILE_ID,)
    ).fetchone()
    if profile and profile["summary"]:
        text_parts.append(profile["summary"])

    for r in conn.execute(
        "SELECT company, title, description FROM experience WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchall():
        if r["company"]:
            idx.companies.add(_norm(r["company"]))
            text_parts.append(r["company"])
        if r["title"]:
            idx.titles.add(_norm(r["title"]))
            text_parts.append(r["title"])
        if r["description"]:
            text_parts.append(r["description"])

    for r in conn.execute(
        "SELECT id, text FROM experience_bullets "
        "WHERE experience_id IN (SELECT id FROM experience WHERE profile_id = ?)",
        (PROFILE_ID,),
    ).fetchall():
        text = r["text"] or ""
        idx.bullet_texts_by_id[r["id"]] = text
        if text:
            text_parts.append(text)

    for r in conn.execute(
        "SELECT skill FROM skills WHERE profile_id = ?", (PROFILE_ID,)
    ).fetchall():
        if r["skill"]:
            idx.skills.add(_norm(r["skill"]))
            text_parts.append(r["skill"])

    for r in conn.execute(
        "SELECT name, description, tech_stack, bullets FROM projects WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchall():
        if r["name"]:
            idx.project_names.add(_norm(r["name"]))
            text_parts.append(r["name"])
        for col in ("description", "tech_stack", "bullets"):
            if r[col]:
                text_parts.append(r[col])

    idx.all_source_text = "\n".join(text_parts).lower()
    return idx


# Numeric claim patterns — anything that looks like a quantitative claim
# in a bullet must trace to the source text or it's flagged.
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")
_CURRENCY_RE = re.compile(r"\$\s*\d[\d,]*(?:\.\d+)?\s*[kKmMbB]?")
_MULTIPLIER_RE = re.compile(r"\b\d+(?:\.\d+)?\s*[xX]\b")
_YEAR_RANGE_RE = re.compile(r"\b(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|now)\b", re.I)
_LARGE_INT_RE = re.compile(r"\b\d{2,}(?:\+|\b)")  # integers with 2+ digits (e.g. 12, 100, 5000)


def extract_numeric_claims(text: str) -> list[str]:
    """Pull out quantitative tokens that should be verifiable in the source.

    Returns lowercased, normalized tokens (whitespace stripped inside).
    """
    if not text:
        return []
    tokens: list[str] = []
    for regex in (_PERCENT_RE, _CURRENCY_RE, _MULTIPLIER_RE, _YEAR_RANGE_RE, _LARGE_INT_RE):
        for match in regex.findall(text):
            tok = re.sub(r"\s+", "", match).lower()
            tokens.append(tok)
    # Dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _normalized_source_for_numeric(source_text: str) -> str:
    """Strip whitespace inside numeric source tokens so '40 %' matches '40%'."""
    return re.sub(r"\s+", "", source_text)


def validate_tailored_resume(
    tailored: TailoredResume, index: SourceIndex
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    compact_source = _normalized_source_for_numeric(index.all_source_text)

    # Experience: company + title + bullets
    for exp_idx, exp in enumerate(tailored.experience):
        loc_exp = f"experience[{exp_idx}]"

        if exp.company and _norm(exp.company) not in index.companies:
            issues.append(ValidationIssue(
                severity="error",
                category="unknown_company",
                message=f"Company {exp.company!r} is not in the source profile",
                location=f"{loc_exp}.company",
            ))

        if exp.title and _norm(exp.title) not in index.titles:
            issues.append(ValidationIssue(
                severity="error",
                category="unknown_title",
                message=f"Title {exp.title!r} is not in the source profile",
                location=f"{loc_exp}.title",
            ))

        for b_idx, bullet in enumerate(exp.bullets):
            loc_b = f"{loc_exp}.bullets[{b_idx}]"

            if bullet.source_bullet_id is not None:
                if bullet.source_bullet_id not in index.bullet_texts_by_id:
                    issues.append(ValidationIssue(
                        severity="error",
                        category="unknown_bullet_ref",
                        message=(
                            f"source_bullet_id={bullet.source_bullet_id} does not match "
                            "any bullet in the source profile"
                        ),
                        location=loc_b,
                    ))

            for token in extract_numeric_claims(bullet.text):
                if token not in compact_source:
                    issues.append(ValidationIssue(
                        severity="warning",
                        category="unverified_metric",
                        message=f"Numeric claim {token!r} not found in source profile",
                        location=loc_b,
                    ))

    # Skills
    for s_idx, skill in enumerate(tailored.skills):
        if skill and _norm(skill) not in index.skills:
            issues.append(ValidationIssue(
                severity="warning",
                category="unknown_skill",
                message=f"Skill {skill!r} is not listed in the source profile",
                location=f"skills[{s_idx}]",
            ))

    # Selected projects
    for p_idx, name in enumerate(tailored.selected_projects):
        if name and _norm(name) not in index.project_names:
            issues.append(ValidationIssue(
                severity="error",
                category="unknown_project",
                message=f"Project {name!r} is not in the source profile",
                location=f"selected_projects[{p_idx}]",
            ))

    # Summary numeric claims
    for token in extract_numeric_claims(tailored.summary):
        if token not in compact_source:
            issues.append(ValidationIssue(
                severity="warning",
                category="unverified_metric",
                message=f"Numeric claim {token!r} in summary not found in source profile",
                location="summary",
            ))

    return ValidationResult(issues=issues)
