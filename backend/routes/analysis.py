from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..db import get_db
from ..services.profile_loader import load_full_profile
from ..services.analyzer import run_analysis
from ..services.llm_client import (
    LLMError, LLMAuthError, LLMRateLimitError, LLMInvalidJSONError,
)

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def _r(request: Request, name: str, ctx: dict | None = None) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx or {})


@router.get("/analyze", response_class=HTMLResponse)
async def analyze_get(request: Request):
    return _r(request, "analyze/new.html", {})


@router.post("/analyze", response_class=HTMLResponse)
async def analyze_post(request: Request, db=Depends(get_db)):
    form = await request.form()
    jd = (form.get("job_description") or "").strip()

    if len(jd) < 50:
        return _r(request, "analyze/new.html", {
            "error": "Job description is too short. Paste the full job posting.",
            "job_description": jd,
        })

    profile = load_full_profile(db)

    has_content = (
        (profile.get("personal_info") or {}).get("full_name")
        or profile.get("summary")
        or profile.get("experience")
        or profile.get("skills")
    )
    if not has_content:
        return _r(request, "analyze/new.html", {
            "error": "Your profile is empty. Fill in your profile or import a resume before running analysis.",
            "job_description": jd,
        })

    try:
        result = run_analysis(profile, jd, db_conn=db)
    except LLMAuthError as e:
        return _r(request, "analyze/new.html", {
            "error": f"API key error: {e}", "job_description": jd,
        })
    except LLMRateLimitError:
        return _r(request, "analyze/new.html", {
            "error": "Rate limited. Try again in a moment.", "job_description": jd,
        })
    except LLMInvalidJSONError:
        return _r(request, "analyze/new.html", {
            "error": "Analysis returned an unexpected format. Try again.", "job_description": jd,
        })
    except LLMError as e:
        return _r(request, "analyze/new.html", {
            "error": f"Analysis failed: {e}", "job_description": jd,
        })

    return _r(request, "analyze/results.html", {
        "result": result,
        "job_description": jd,
    })
