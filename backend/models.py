from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PersonalInfo(BaseModel):
    """Top-level fields on the profile row (excluding summary)."""

    full_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=50)
    location: str = Field(default="", max_length=200)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return v
        # Lightweight check — we don't want to reject unusual but valid addresses.
        if "@" not in v or "." not in v.split("@", 1)[1]:
            raise ValueError("Must be a valid email address")
        return v


class ProfileLink(BaseModel):
    id: int | None = None
    label: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=500)


class Summary(BaseModel):
    text: str = Field(default="", max_length=5000)


class ExperienceBullet(BaseModel):
    """New entries may start blank — only validated at generation time."""
    id: int | None = None
    text: str = Field(default="", max_length=1000)


class ExperienceEntry(BaseModel):
    id: int | None = None
    company: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    start_date: str = Field(default="", max_length=50)
    end_date: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=2000)
    bullets: list[ExperienceBullet] = Field(default_factory=list)


class EducationEntry(BaseModel):
    id: int | None = None
    institution: str = Field(default="", max_length=200)
    degree: str = Field(default="", max_length=200)
    field: str = Field(default="", max_length=200)
    start_date: str = Field(default="", max_length=50)
    end_date: str = Field(default="", max_length=50)
    gpa: str = Field(default="", max_length=50)
    highlights: str = Field(default="", max_length=2000)


class Skill(BaseModel):
    id: int | None = None
    category: str = Field(default="", max_length=100)
    skill: str = Field(default="", max_length=100)


class ProjectEntry(BaseModel):
    id: int | None = None
    name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    tech_stack: str = Field(default="", max_length=500)
    url: str = Field(default="", max_length=500)
    bullets: str = Field(default="", max_length=4000)


class CertificationEntry(BaseModel):
    id: int | None = None
    name: str = Field(default="", max_length=200)
    issuer: str = Field(default="", max_length=200)
    date: str = Field(default="", max_length=50)
    url: str = Field(default="", max_length=500)


class CustomSectionEntry(BaseModel):
    id: int | None = None
    name: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=5000)


# ---------------------------------------------------------------------------
# Parsed profile — output of the LLM resume parser
# All fields optional; only populate what the resume actually contains.
# ---------------------------------------------------------------------------


class ParsedLink(BaseModel):
    label: str = ""
    url: str = ""


class ParsedBullet(BaseModel):
    text: str = ""


class ParsedExperience(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    bullets: list[ParsedBullet] = Field(default_factory=list)


class ParsedEducation(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""
    highlights: str = ""


class ParsedSkill(BaseModel):
    category: str = ""
    skill: str = ""


class ParsedProject(BaseModel):
    name: str = ""
    description: str = ""
    tech_stack: str = ""
    url: str = ""
    bullets: str = ""


class ParsedCertification(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""
    url: str = ""


class ParsedCustomSection(BaseModel):
    name: str = ""
    content: str = ""


# ---------------------------------------------------------------------------
# Keyword analysis — TF-IDF overlap output
# ---------------------------------------------------------------------------


class KeywordOverlap(BaseModel):
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    jd_only: list[str] = Field(default_factory=list)
    match_pct: float = 0.0


class ParsedProfile(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    links: list[ParsedLink] = Field(default_factory=list)
    experience: list[ParsedExperience] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
    skills: list[ParsedSkill] = Field(default_factory=list)
    projects: list[ParsedProject] = Field(default_factory=list)
    certifications: list[ParsedCertification] = Field(default_factory=list)
    custom_sections: list[ParsedCustomSection] = Field(default_factory=list)
