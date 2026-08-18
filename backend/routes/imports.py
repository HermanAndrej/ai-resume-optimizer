import json

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..db import get_db
from ..services.extraction import extract_text
from ..services.llm_client import LLMError
from ..services.profile_parser import parse_resume

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _r(request: Request, name: str, ctx: dict | None = None) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx or {})


@router.get("/profile/import", response_class=HTMLResponse)
async def import_page(request: Request) -> HTMLResponse:
    return _r(request, "import/upload.html")


@router.post("/profile/import/upload", response_class=HTMLResponse)
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    db=Depends(get_db),
) -> HTMLResponse:
    content = await file.read()

    if len(content) > _MAX_BYTES:
        return _r(request, "import/upload.html", {"error": "File too large (max 10 MB)."})

    try:
        text = extract_text(content, file.filename or "resume.pdf")
    except (ValueError, RuntimeError) as exc:
        return _r(request, "import/upload.html", {"error": str(exc)})

    if len(text.strip()) < 100:
        return _r(request, "import/upload.html", {
            "error": "Could not extract enough text from this file. "
                     "Try a text-based PDF or DOCX instead."
        })

    try:
        parsed = parse_resume(text, db_conn=db)
    except LLMError as exc:
        return _r(request, "import/upload.html", {"error": f"LLM parsing failed: {exc}"})

    return _r(request, "import/review.html", {
        "parsed": parsed,
        "profile_json": json.dumps(parsed),
        "filename": file.filename,
    })


@router.post("/profile/import/apply")
async def apply_import(request: Request, db=Depends(get_db)) -> RedirectResponse:
    form = await request.form()
    raw = form.get("profile_json", "{}")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid profile data.")

    _write_profile(parsed, db)
    return RedirectResponse(url="/profile", status_code=303)


def _write_profile(data: dict, db) -> None:
    """Overwrite all profile tables with imported data."""
    pi = data.get("personal_info", {})

    db.execute(
        "UPDATE profile SET full_name=?, email=?, phone=?, location=?, summary=?, "
        "updated_at=CURRENT_TIMESTAMP WHERE id=1",
        (
            pi.get("full_name") or None,
            pi.get("email") or None,
            pi.get("phone") or None,
            pi.get("location") or None,
            data.get("summary") or None,
        ),
    )

    db.execute("DELETE FROM profile_links WHERE profile_id=1")
    for i, link in enumerate(pi.get("links", [])):
        db.execute(
            "INSERT INTO profile_links (profile_id, label, url, display_order) VALUES (1,?,?,?)",
            (link.get("label", ""), link.get("url", ""), i),
        )

    db.execute("DELETE FROM experience WHERE profile_id=1")
    for i, exp in enumerate(data.get("experience", [])):
        cur = db.execute(
            "INSERT INTO experience "
            "(profile_id, company, title, location, start_date, end_date, description, display_order) "
            "VALUES (1,?,?,?,?,?,?,?)",
            (
                exp.get("company") or None,
                exp.get("title") or None,
                exp.get("location") or None,
                exp.get("start_date") or None,
                exp.get("end_date") or None,
                exp.get("description") or None,
                i,
            ),
        )
        for j, bullet in enumerate(exp.get("bullets", [])):
            db.execute(
                "INSERT INTO experience_bullets (experience_id, text, display_order) VALUES (?,?,?)",
                (cur.lastrowid, bullet, j),
            )

    db.execute("DELETE FROM education WHERE profile_id=1")
    for i, edu in enumerate(data.get("education", [])):
        db.execute(
            "INSERT INTO education "
            "(profile_id, institution, degree, field, start_date, end_date, gpa, highlights, display_order) "
            "VALUES (1,?,?,?,?,?,?,?,?)",
            (
                edu.get("institution") or None,
                edu.get("degree") or None,
                edu.get("field") or None,
                edu.get("start_date") or None,
                edu.get("end_date") or None,
                edu.get("gpa") or None,
                json.dumps(edu.get("highlights", [])),
                i,
            ),
        )

    db.execute("DELETE FROM skills WHERE profile_id=1")
    order = 0
    for group in data.get("skills", []):
        for skill in group.get("skills", []):
            db.execute(
                "INSERT INTO skills (profile_id, category, skill, display_order) VALUES (1,?,?,?)",
                (group.get("category", "General"), skill, order),
            )
            order += 1

    db.execute("DELETE FROM projects WHERE profile_id=1")
    for i, proj in enumerate(data.get("projects", [])):
        db.execute(
            "INSERT INTO projects "
            "(profile_id, name, description, tech_stack, url, bullets, display_order) "
            "VALUES (1,?,?,?,?,?,?)",
            (
                proj.get("name") or None,
                proj.get("description") or None,
                json.dumps(proj.get("tech_stack", [])),
                proj.get("url") or None,
                json.dumps(proj.get("bullets", [])),
                i,
            ),
        )

    db.execute("DELETE FROM certifications WHERE profile_id=1")
    for i, cert in enumerate(data.get("certifications", [])):
        db.execute(
            "INSERT INTO certifications "
            "(profile_id, name, issuer, date, url, display_order) "
            "VALUES (1,?,?,?,?,?)",
            (
                cert.get("name") or None,
                cert.get("issuer") or None,
                cert.get("date") or None,
                cert.get("url") or None,
                i,
            ),
        )

    db.commit()
