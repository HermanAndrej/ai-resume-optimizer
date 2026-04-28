import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.db import get_db
from backend.models import STATUS_VALUES
from backend.services import application_repo, tailored_repo
from backend.services.compat_runner import run_analysis
from backend.services.llm_client import LLMError
from backend.services.resume_tailor import TAILOR_MODEL, generate_tailored_resume
from backend.services.resume_validator import build_source_index, validate_tailored_resume
from backend.templating import templates

router = APIRouter(prefix="/applications")


def _total_cost_cents(db: sqlite3.Connection) -> float:
    return db.execute(
        "SELECT COALESCE(SUM(cost_cents), 0) FROM usage_log"
    ).fetchone()[0]


@router.get("", response_class=HTMLResponse)
async def list_applications(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    include_archived = request.query_params.get("archived") == "1"
    applications = application_repo.list_applications(db, include_archived=include_archived)
    return templates.TemplateResponse(
        request,
        "applications/list.html",
        {
            "active": "applications",
            "applications": applications,
            "include_archived": include_archived,
            "status_values": STATUS_VALUES,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_application(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    return templates.TemplateResponse(
        request,
        "applications/new.html",
        {
            "active": "applications",
            "error": None,
            "total_cost_cents": _total_cost_cents(db),
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_application(
    request: Request,
    job_title: str = Form(default=""),
    company: str = Form(default=""),
    jd_text: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    errors: list[str] = []
    if not job_title.strip():
        errors.append("Job title is required.")
    if not jd_text.strip():
        errors.append("Job description is required.")

    if errors:
        return templates.TemplateResponse(
            request,
            "applications/new.html",
            {
                "active": "applications",
                "error": " ".join(errors),
                "job_title": job_title,
                "company": company,
                "jd_text": jd_text,
                "total_cost_cents": _total_cost_cents(db),
            },
            status_code=422,
        )

    try:
        analysis, profile_hash, usage_info = run_analysis(db, jd_text)
    except LLMError as exc:
        return templates.TemplateResponse(
            request,
            "applications/new.html",
            {
                "active": "applications",
                "error": f"AI analysis failed: {exc}",
                "job_title": job_title,
                "company": company,
                "jd_text": jd_text,
                "total_cost_cents": _total_cost_cents(db),
            },
            status_code=500,
        )

    parse_cost = usage_info.get("cost_cents", 0.0)

    app_id = application_repo.create_application(
        db,
        job_title=job_title.strip(),
        company=company.strip(),
        jd=jd_text.strip(),
        analysis_json=analysis.model_dump_json(),
        profile_hash=profile_hash,
    )

    return RedirectResponse(
        url=f"/applications/{app_id}?parse_cost={parse_cost:.4f}",
        status_code=303,
    )


def _show_context(
    request: Request,
    db: sqlite3.Connection,
    application,
    *,
    parse_cost: float = 0,
    edit_error: str | None = None,
) -> dict:
    analysis = application.analysis
    keyword_gaps = set(analysis.keyword_overlap.missing)
    llm_gaps = set(analysis.compatibility_score.gaps)
    return {
        "active": "applications",
        "not_found": False,
        "application": application,
        "analysis": analysis,
        "combined_gaps": sorted(keyword_gaps | llm_gaps),
        "parse_cost_cents": parse_cost,
        "total_cost_cents": _total_cost_cents(db),
        "status_values": STATUS_VALUES,
        "edit_error": edit_error,
    }


@router.get("/{app_id}", response_class=HTMLResponse)
async def show_application(
    app_id: str,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return templates.TemplateResponse(
            request,
            "applications/show.html",
            {"active": "applications", "not_found": True},
            status_code=404,
        )

    parse_cost = float(request.query_params.get("parse_cost", 0))
    return templates.TemplateResponse(
        request,
        "applications/show.html",
        _show_context(request, db, application, parse_cost=parse_cost),
    )


@router.post("/{app_id}/edit", response_class=HTMLResponse)
async def edit_application(
    app_id: str,
    request: Request,
    status: str = Form(default=""),
    notes: str = Form(default=""),
    source_url: str = Form(default=""),
    jd_text: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return templates.TemplateResponse(
            request,
            "applications/show.html",
            {"active": "applications", "not_found": True},
            status_code=404,
        )

    if status not in STATUS_VALUES:
        return templates.TemplateResponse(
            request,
            "applications/show.html",
            _show_context(request, db, application, edit_error=f"Invalid status: {status!r}"),
            status_code=422,
        )

    application_repo.update_metadata(
        db, app_id,
        status=status,
        notes=notes,
        source_url=source_url,
        jd=jd_text,
    )
    return RedirectResponse(url=f"/applications/{app_id}", status_code=303)


@router.post("/{app_id}/archive", response_class=HTMLResponse)
async def archive_application(
    app_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application_repo.set_archived(db, app_id, True)
    return RedirectResponse(url="/applications", status_code=303)


@router.post("/{app_id}/unarchive", response_class=HTMLResponse)
async def unarchive_application(
    app_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application_repo.set_archived(db, app_id, False)
    return RedirectResponse(url=f"/applications/{app_id}", status_code=303)


@router.post("/{app_id}/status", response_class=HTMLResponse)
async def update_status(
    app_id: str,
    request: Request,
    status: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    if status in STATUS_VALUES:
        application = application_repo.get_application(db, app_id)
        if application is not None:
            application_repo.update_metadata(
                db, app_id,
                status=status,
                notes=application.notes,
                source_url=application.source_url,
                jd=application.jd,
            )
    referer = request.headers.get("referer", "/applications")
    return RedirectResponse(url=referer, status_code=303)


@router.post("/{app_id}/reanalyze", response_class=HTMLResponse)
async def reanalyze_application(
    app_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return RedirectResponse(url="/applications", status_code=303)

    try:
        analysis, profile_hash, usage_info = run_analysis(db, application.jd)
    except LLMError:
        return RedirectResponse(url=f"/applications/{app_id}", status_code=303)

    application_repo.update_analysis(db, app_id, analysis.model_dump_json(), profile_hash)
    parse_cost = usage_info.get("cost_cents", 0.0)
    return RedirectResponse(
        url=f"/applications/{app_id}?parse_cost={parse_cost:.4f}",
        status_code=303,
    )


@router.post("/{app_id}/tailor", response_class=HTMLResponse)
async def tailor_resume(
    app_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return RedirectResponse(url="/applications", status_code=303)

    try:
        tailored, profile_hash, usage_info = generate_tailored_resume(
            db, application.jd, application_id=app_id
        )
    except LLMError:
        return RedirectResponse(url=f"/applications/{app_id}", status_code=303)

    source_index = build_source_index(db)
    validation = validate_tailored_resume(tailored, source_index)

    tailored_repo.create_tailored(
        db,
        application_id=app_id,
        content=tailored,
        validation=validation,
        profile_hash=profile_hash,
        model=usage_info.get("model", TAILOR_MODEL),
        cost_cents=usage_info.get("cost_cents", 0.0),
    )

    return RedirectResponse(url=f"/applications/{app_id}/tailored", status_code=303)


def _index_issues_by_location(issues) -> dict:
    """Group ValidationIssue list by location for inline template lookup."""
    out: dict = {}
    for issue in issues:
        out.setdefault(issue.location, []).append(issue)
    return out


@router.get("/{app_id}/tailored", response_class=HTMLResponse)
async def show_tailored(
    app_id: str,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return templates.TemplateResponse(
            request,
            "applications/show.html",
            {"active": "applications", "not_found": True},
            status_code=404,
        )

    tailored_row = tailored_repo.get_latest_for_application(db, app_id)

    return templates.TemplateResponse(
        request,
        "applications/tailored.html",
        {
            "active": "applications",
            "application": application,
            "tailored_row": tailored_row,
            "issues_by_loc": (
                _index_issues_by_location(tailored_row.validation.issues)
                if tailored_row else {}
            ),
            "total_cost_cents": _total_cost_cents(db),
        },
    )
