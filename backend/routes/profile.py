import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from backend.db import get_db
from backend.models import PersonalInfo, ProfileLink
from backend.services import profile_repo
from backend.templating import templates

router = APIRouter()


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/profile/personal", status_code=307)


@router.get("/profile/personal", response_class=HTMLResponse)
async def personal_get(request: Request, db: sqlite3.Connection = Depends(get_db)) -> Response:
    info = profile_repo.get_personal_info(db)
    links = profile_repo.list_links(db)
    return templates.TemplateResponse(
        request,
        "profile/personal.html",
        {
            "active": "personal",
            "info": info,
            "links": links,
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
    info = PersonalInfo.model_construct(
        full_name=full_name.strip(),
        email=email.strip(),
        phone=phone.strip(),
        location=location.strip(),
    )
    try:
        info = PersonalInfo(
            full_name=info.full_name,
            email=info.email,
            phone=info.phone,
            location=info.location,
        )
    except ValidationError as exc:
        for err in exc.errors():
            field = err["loc"][0] if err["loc"] else ""
            errors[str(field)] = err["msg"]

    if not errors:
        profile_repo.save_personal_info(db, info)

    links = profile_repo.list_links(db)
    return templates.TemplateResponse(
        request,
        "profile/personal.html",
        {
            "active": "personal",
            "info": info,
            "links": links,
            "errors": errors,
            "saved": not errors,
        },
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
    return templates.TemplateResponse(
        request,
        "profile/_link_row.html",
        {"link": saved},
    )


@router.delete("/profile/personal/links/{link_id}")
async def delete_link(
    link_id: int, db: sqlite3.Connection = Depends(get_db)
) -> Response:
    profile_repo.delete_link(db, link_id)
    return Response(status_code=200)
