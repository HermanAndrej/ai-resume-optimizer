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
