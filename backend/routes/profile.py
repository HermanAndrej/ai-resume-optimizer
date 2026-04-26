import json
import sqlite3

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from backend.db import get_db
from backend.models import (
    CertificationEntry,
    CustomSectionEntry,
    EducationEntry,
    ExperienceEntry,
    ParsedProfile,
    PersonalInfo,
    ProfileLink,
    ProjectEntry,
    Summary,
)
from backend.services import profile_repo
from backend.services.extraction import extract_text
from backend.services.llm_client import LLMError, LLMInvalidJSONError
from backend.services.profile_parser import parse_resume_text
from backend.templating import templates

router = APIRouter()


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/profile/personal", status_code=307)


# ==================== Personal ====================

@router.get("/profile/personal", response_class=HTMLResponse)
async def personal_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/personal.html",
        {
            "active": "personal",
            "info": profile_repo.get_personal_info(db),
            "links": profile_repo.list_links(db),
            "errors": {},
            "saved": False,
        },
    )


@router.post("/profile/personal", response_class=HTMLResponse)
async def personal_save(
    request: Request,
    full_name: str = Form(default=""),
    email: str = Form(default=""),
    phone: str = Form(default=""),
    location: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    errors: dict[str, str] = {}
    raw = {
        "full_name": full_name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "location": location.strip(),
    }
    info = PersonalInfo.model_construct(**raw)
    try:
        info = PersonalInfo(**raw)
    except ValidationError as exc:
        for err in exc.errors():
            field = err["loc"][0] if err["loc"] else ""
            errors[str(field)] = err["msg"]

    if not errors:
        profile_repo.save_personal_info(db, info)

    return templates.TemplateResponse(
        request,
        "profile/_personal_form.html",
        {"info": info, "errors": errors, "saved": not errors},
    )


@router.post("/profile/personal/links", response_class=HTMLResponse)
async def add_link(
    request: Request,
    label: str = Form(...),
    url: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    try:
        link = ProfileLink(label=label.strip(), url=url.strip())
    except ValidationError:
        return HTMLResponse(status_code=400, content="Label and URL are required.")
    saved = profile_repo.add_link(db, link)
    return templates.TemplateResponse(request, "profile/_link_row.html", {"link": saved})


@router.delete("/profile/personal/links/{link_id}")
async def delete_link(link_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    profile_repo.delete_link(db, link_id)
    return Response(status_code=200)


# ==================== Summary ====================

@router.get("/profile/summary", response_class=HTMLResponse)
async def summary_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/summary.html",
        {
            "active": "summary",
            "summary": profile_repo.get_summary(db),
            "saved": False,
        },
    )


@router.post("/profile/summary", response_class=HTMLResponse)
async def summary_save(
    request: Request,
    text: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    summary = Summary(text=text.strip())
    profile_repo.save_summary(db, summary)
    return templates.TemplateResponse(
        request,
        "profile/_summary_form.html",
        {"summary": summary, "saved": True},
    )


# ==================== Experience ====================

@router.get("/profile/experience", response_class=HTMLResponse)
async def experience_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/experience.html",
        {"active": "experience", "entries": profile_repo.list_experience(db)},
    )


@router.post("/profile/experience", response_class=HTMLResponse)
async def experience_add(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    entry = profile_repo.add_experience(db)
    return templates.TemplateResponse(
        request, "profile/_experience_entry.html", {"entry": entry, "saved": False}
    )


@router.post("/profile/experience/{entry_id}", response_class=HTMLResponse)
async def experience_update(
    entry_id: int,
    request: Request,
    company: str = Form(default=""),
    title: str = Form(default=""),
    location: str = Form(default=""),
    start_date: str = Form(default=""),
    end_date: str = Form(default=""),
    description: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    entry = ExperienceEntry(
        id=entry_id,
        company=company.strip(),
        title=title.strip(),
        location=location.strip(),
        start_date=start_date.strip(),
        end_date=end_date.strip(),
        description=description.strip(),
    )
    profile_repo.update_experience(db, entry)
    # Reload with bullets so the form re-renders fully
    reloaded = profile_repo.get_experience_entry(db, entry_id) or entry
    return templates.TemplateResponse(
        request, "profile/_experience_entry.html", {"entry": reloaded, "saved": True}
    )


@router.delete("/profile/experience/{entry_id}")
async def experience_delete(entry_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    profile_repo.delete_experience(db, entry_id)
    return Response(status_code=200)


@router.post("/profile/experience/{entry_id}/bullets", response_class=HTMLResponse)
async def experience_bullet_add(
    entry_id: int,
    request: Request,
    text: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    text = text.strip()
    if not text:
        return HTMLResponse(status_code=400, content="Bullet text is required.")
    bullet = profile_repo.add_experience_bullet(db, entry_id, text)
    return templates.TemplateResponse(
        request, "profile/_experience_bullet.html", {"bullet": bullet}
    )


@router.delete("/profile/experience/bullets/{bullet_id}")
async def experience_bullet_delete(
    bullet_id: int, db: sqlite3.Connection = Depends(get_db)
) -> Response:
    profile_repo.delete_experience_bullet(db, bullet_id)
    return Response(status_code=200)


# ==================== Education ====================

@router.get("/profile/education", response_class=HTMLResponse)
async def education_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/education.html",
        {"active": "education", "entries": profile_repo.list_education(db)},
    )


@router.post("/profile/education", response_class=HTMLResponse)
async def education_add(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    entry = profile_repo.add_education(db)
    return templates.TemplateResponse(
        request, "profile/_education_entry.html", {"entry": entry, "saved": False}
    )


@router.post("/profile/education/{entry_id}", response_class=HTMLResponse)
async def education_update(
    entry_id: int,
    request: Request,
    institution: str = Form(default=""),
    degree: str = Form(default=""),
    field: str = Form(default=""),
    start_date: str = Form(default=""),
    end_date: str = Form(default=""),
    gpa: str = Form(default=""),
    highlights: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    entry = EducationEntry(
        id=entry_id,
        institution=institution.strip() ,
        degree=degree.strip(),
        field=field.strip(),
        start_date=start_date.strip(),
        end_date=end_date.strip(),
        gpa=gpa.strip(),
        highlights=highlights.strip(),
    )
    profile_repo.update_education(db, entry)
    return templates.TemplateResponse(
        request, "profile/_education_entry.html", {"entry": entry, "saved": True}
    )


@router.delete("/profile/education/{entry_id}")
async def education_delete(entry_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    profile_repo.delete_education(db, entry_id)
    return Response(status_code=200)


# ==================== Skills ====================

@router.get("/profile/skills", response_class=HTMLResponse)
async def skills_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/skills.html",
        {"active": "skills", "grouped": profile_repo.list_skills_grouped(db)},
    )


@router.post("/profile/skills", response_class=HTMLResponse)
async def skills_add(
    request: Request,
    category: str = Form(...),
    skill: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    category = category.strip()
    skill_name = skill.strip()
    if not category or not skill_name:
        return HTMLResponse(status_code=400, content="Category and skill are required.")
    profile_repo.add_skill(db, category, skill_name)
    # Return the full grouped skills view so categories reflow if a new one was added
    return templates.TemplateResponse(
        request,
        "profile/_skills_list.html",
        {"grouped": profile_repo.list_skills_grouped(db)},
    )


@router.delete("/profile/skills/{skill_id}", response_class=HTMLResponse)
async def skills_delete(
    skill_id: int, request: Request, db: sqlite3.Connection = Depends(get_db)
) -> Response:
    profile_repo.delete_skill(db, skill_id)
    return templates.TemplateResponse(
        request,
        "profile/_skills_list.html",
        {"grouped": profile_repo.list_skills_grouped(db)},
    )


# ==================== Projects ====================

@router.get("/profile/projects", response_class=HTMLResponse)
async def projects_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/projects.html",
        {"active": "projects", "entries": profile_repo.list_projects(db)},
    )


@router.post("/profile/projects", response_class=HTMLResponse)
async def projects_add(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    entry = profile_repo.add_project(db)
    return templates.TemplateResponse(
        request, "profile/_project_entry.html", {"entry": entry, "saved": False}
    )


@router.post("/profile/projects/{entry_id}", response_class=HTMLResponse)
async def projects_update(
    entry_id: int,
    request: Request,
    name: str = Form(default=""),
    description: str = Form(default=""),
    tech_stack: str = Form(default=""),
    url: str = Form(default=""),
    bullets: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    entry = ProjectEntry(
        id=entry_id,
        name=name.strip() ,
        description=description.strip(),
        tech_stack=tech_stack.strip(),
        url=url.strip(),
        bullets=bullets,
    )
    profile_repo.update_project(db, entry)
    return templates.TemplateResponse(
        request, "profile/_project_entry.html", {"entry": entry, "saved": True}
    )


@router.delete("/profile/projects/{entry_id}")
async def projects_delete(entry_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    profile_repo.delete_project(db, entry_id)
    return Response(status_code=200)


# ==================== Certifications ====================

@router.get("/profile/certifications", response_class=HTMLResponse)
async def certifications_get(
    request: Request, db: sqlite3.Connection = Depends(get_db)
) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/certifications.html",
        {"active": "certifications", "entries": profile_repo.list_certifications(db)},
    )


@router.post("/profile/certifications", response_class=HTMLResponse)
async def certifications_add(
    request: Request, db: sqlite3.Connection = Depends(get_db)
) -> Response:
    entry = profile_repo.add_certification(db)
    return templates.TemplateResponse(
        request, "profile/_certification_entry.html", {"entry": entry, "saved": False}
    )


@router.post("/profile/certifications/{entry_id}", response_class=HTMLResponse)
async def certifications_update(
    entry_id: int,
    request: Request,
    name: str = Form(default=""),
    issuer: str = Form(default=""),
    date: str = Form(default=""),
    url: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    entry = CertificationEntry(
        id=entry_id,
        name=name.strip() ,
        issuer=issuer.strip(),
        date=date.strip(),
        url=url.strip(),
    )
    profile_repo.update_certification(db, entry)
    return templates.TemplateResponse(
        request, "profile/_certification_entry.html", {"entry": entry, "saved": True}
    )


@router.delete("/profile/certifications/{entry_id}")
async def certifications_delete(
    entry_id: int, db: sqlite3.Connection = Depends(get_db)
) -> Response:
    profile_repo.delete_certification(db, entry_id)
    return Response(status_code=200)


# ==================== Custom sections ====================

@router.get("/profile/custom", response_class=HTMLResponse)
async def custom_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/custom.html",
        {"active": "custom", "entries": profile_repo.list_custom_sections(db)},
    )


@router.post("/profile/custom", response_class=HTMLResponse)
async def custom_add(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    entry = profile_repo.add_custom_section(db)
    return templates.TemplateResponse(
        request, "profile/_custom_entry.html", {"entry": entry, "saved": False}
    )


@router.post("/profile/custom/{entry_id}", response_class=HTMLResponse)
async def custom_update(
    entry_id: int,
    request: Request,
    name: str = Form(default=""),
    content: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    entry = CustomSectionEntry(
        id=entry_id,
        name=name.strip() ,
        content=content,
    )
    profile_repo.update_custom_section(db, entry)
    return templates.TemplateResponse(
        request, "profile/_custom_entry.html", {"entry": entry, "saved": True}
    )


@router.delete("/profile/custom/{entry_id}")
async def custom_delete(entry_id: int, db: sqlite3.Connection = Depends(get_db)) -> Response:
    profile_repo.delete_custom_section(db, entry_id)
    return Response(status_code=200)


# ==================== Import ====================

def _profile_has_data(db: sqlite3.Connection) -> bool:
    info = profile_repo.get_personal_info(db)
    if info.full_name or info.email:
        return True
    return len(profile_repo.list_experience(db)) > 0 or len(profile_repo.list_education(db)) > 0


def _total_cost_cents(db: sqlite3.Connection) -> float:
    row = db.execute("SELECT COALESCE(SUM(cost_cents), 0) FROM usage_log").fetchone()
    return row[0] if row else 0.0


@router.get("/profile/import", response_class=HTMLResponse)
async def import_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "profile/import.html",
        {
            "active": "personal",
            "profile_has_data": _profile_has_data(db),
            "error": None,
            "total_cost_cents": _total_cost_cents(db),
        },
    )


@router.post("/profile/import", response_class=HTMLResponse)
async def import_post(
    request: Request,
    resume_file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    def _error(msg: str) -> Response:
        return templates.TemplateResponse(
            request,
            "profile/import.html",
            {
                "active": "personal",
                "profile_has_data": _profile_has_data(db),
                "error": msg,
                "total_cost_cents": _total_cost_cents(db),
            },
            status_code=422,
        )

    filename = resume_file.filename or ""
    if not filename.lower().endswith((".pdf", ".docx")):
        return _error("Only .pdf and .docx files are supported.")

    data = await resume_file.read()

    try:
        text = extract_text(filename, data)
    except ValueError as exc:
        return _error(str(exc))

    try:
        parsed, usage_info = parse_resume_text(text, db_conn=db)
    except LLMInvalidJSONError as exc:
        return _error(f"Could not parse resume: {exc}")
    except LLMError as exc:
        return _error(f"LLM error: {exc}")

    parsed_json = parsed.model_dump_json()

    return templates.TemplateResponse(
        request,
        "profile/import_review.html",
        {
            "active": "personal",
            "parsed": parsed,
            "parsed_json": parsed_json,
            "parse_cost_cents": usage_info.get("cost_cents", 0.0),
            "total_cost_cents": _total_cost_cents(db),
        },
    )


@router.post("/profile/import/apply")
async def import_apply(
    parsed_json: str = Form(...),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    try:
        data = json.loads(parsed_json)
        parsed = ParsedProfile.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return RedirectResponse(url="/profile/import", status_code=303)

    profile_repo.apply_parsed_profile(db, parsed)
    return RedirectResponse(url="/profile/personal", status_code=303)
