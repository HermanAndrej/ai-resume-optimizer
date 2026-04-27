import hashlib
import json
import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from backend.db import get_db
from backend.models import CompatibilityAnalysis
from backend.services import application_repo
from backend.services.compat_scorer import score_compatibility
from backend.services.keyword_analysis import compute_overlap, flatten_profile
from backend.services.llm_client import LLMError
from backend.templating import templates

router = APIRouter(prefix="/applications")


def _total_cost_cents(db: sqlite3.Connection) -> float:
    return db.execute(
        "SELECT COALESCE(SUM(cost_cents), 0) FROM usage_log"
    ).fetchone()[0]


@router.get("", response_class=HTMLResponse)
async def list_applications(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    applications = application_repo.list_applications(db)
    return templates.TemplateResponse(
        request,
        "applications/list.html",
        {"active": "applications", "applications": applications},
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
        profile_text = flatten_profile(db)
        keyword_overlap = compute_overlap(jd_text, profile_text)
        compat_score, usage_info = score_compatibility(profile_text, jd_text, db_conn=db)
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

    analysis = CompatibilityAnalysis(
        keyword_overlap=keyword_overlap,
        compatibility_score=compat_score,
    )
    profile_hash = hashlib.sha256(profile_text.encode()).hexdigest()[:16]
    analysis_json = analysis.model_dump_json()
    parse_cost = usage_info.get("cost_cents", 0.0)

    app_id = application_repo.create_application(
        db,
        job_title=job_title.strip(),
        company=company.strip(),
        jd=jd_text.strip(),
        analysis_json=analysis_json,
        profile_hash=profile_hash,
    )

    return RedirectResponse(
        url=f"/applications/{app_id}?parse_cost={parse_cost:.4f}",
        status_code=303,
    )


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
    total_cost = _total_cost_cents(db)

    analysis = application.analysis
    keyword_gaps = set(analysis.keyword_overlap.missing)
    llm_gaps = set(analysis.compatibility_score.gaps)
    combined_gaps = sorted(keyword_gaps | llm_gaps)

    return templates.TemplateResponse(
        request,
        "applications/show.html",
        {
            "active": "applications",
            "not_found": False,
            "application": application,
            "analysis": analysis,
            "combined_gaps": combined_gaps,
            "parse_cost_cents": parse_cost,
            "total_cost_cents": total_cost,
        },
    )
