from pydantic import BaseModel
from typing import Optional


class ProfileLink(BaseModel):
    id: Optional[int] = None
    label: str = ""
    url: str = ""
    display_order: int = 0


class ExperienceEntry(BaseModel):
    id: Optional[int] = None
    company: str = ""
    title: str = ""
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    bullets: list[str] = []
    display_order: int = 0


class EducationEntry(BaseModel):
    id: Optional[int] = None
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[str] = None
    highlights: list[str] = []
    display_order: int = 0


class SkillGroup(BaseModel):
    category: str = ""
    skills: list[str] = []


class ProjectEntry(BaseModel):
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    tech_stack: list[str] = []
    url: Optional[str] = None
    bullets: list[str] = []
    display_order: int = 0


class Certification(BaseModel):
    id: Optional[int] = None
    name: str = ""
    issuer: str = ""
    date: Optional[str] = None
    url: Optional[str] = None
    display_order: int = 0


class CustomSection(BaseModel):
    id: Optional[int] = None
    name: str = ""
    content: str = ""
    display_order: int = 0
