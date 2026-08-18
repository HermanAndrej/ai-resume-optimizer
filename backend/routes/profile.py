import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..db import get_db

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def _r(request: Request, name: str, ctx: dict | None = None) -> HTMLResponse:
    """Starlette 1.0 TemplateResponse wrapper."""
    return templates.TemplateResponse(request, name, ctx or {})


# ── DB read helpers ──────────────────────────────────────────────────────────

def _personal(conn) -> dict:
    row = dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
    row["links"] = [dict(r) for r in conn.execute(
        "SELECT * FROM profile_links WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]
    return row


def _experience(conn) -> list[dict]:
    entries = [dict(r) for r in conn.execute(
        "SELECT * FROM experience WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]
    for e in entries:
        e["bullets"] = [r["text"] for r in conn.execute(
            "SELECT text FROM experience_bullets WHERE experience_id=? ORDER BY display_order",
            (e["id"],)
        ).fetchall()]
    return entries


def _education(conn) -> list[dict]:
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM education WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]
    for r in rows:
        r["highlights"] = json.loads(r["highlights"]) if r.get("highlights") else []
    return rows


def _skills(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT category, skill FROM skills WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()
    groups: dict[str, list[str]] = {}
    for r in rows:
        groups.setdefault(r["category"] or "General", []).append(r["skill"])
    return [{"category": k, "skills": v} for k, v in groups.items()]


def _projects(conn) -> list[dict]:
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM projects WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]
    for r in rows:
        r["tech_stack"] = json.loads(r["tech_stack"]) if r.get("tech_stack") else []
        r["bullets"] = json.loads(r["bullets"]) if r.get("bullets") else []
    return rows


def _certifications(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM certifications WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]


def _custom_sections(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM custom_sections WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]


# ── Page routes ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/profile")


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return _r(request, "profile.html")


# ── Section fragment GET routes (HTMX loads these) ───────────────────────────

@router.get("/profile/sections/personal", response_class=HTMLResponse)
async def get_personal(request: Request, db=Depends(get_db)):
    return _r(request, "sections/personal.html", {"personal": _personal(db), "saved": False,
    })


@router.get("/profile/sections/summary", response_class=HTMLResponse)
async def get_summary(request: Request, db=Depends(get_db)):
    row = db.execute("SELECT summary FROM profile WHERE id=1").fetchone()
    return _r(request, "sections/summary.html", {"summary": row["summary"] or "", "saved": False,
    })


@router.get("/profile/sections/experience", response_class=HTMLResponse)
async def get_experience(request: Request, db=Depends(get_db)):
    return _r(request, "sections/experience.html", {"entries": _experience(db), "saved": False,
    })


@router.get("/profile/sections/education", response_class=HTMLResponse)
async def get_education(request: Request, db=Depends(get_db)):
    return _r(request, "sections/education.html", {"entries": _education(db), "saved": False,
    })


@router.get("/profile/sections/skills", response_class=HTMLResponse)
async def get_skills(request: Request, db=Depends(get_db)):
    return _r(request, "sections/skills.html", {"groups": _skills(db), "saved": False,
    })


@router.get("/profile/sections/projects", response_class=HTMLResponse)
async def get_projects(request: Request, db=Depends(get_db)):
    return _r(request, "sections/projects.html", {"entries": _projects(db), "saved": False,
    })


@router.get("/profile/sections/certifications", response_class=HTMLResponse)
async def get_certifications(request: Request, db=Depends(get_db)):
    return _r(request, "sections/certifications.html", {"entries": _certifications(db), "saved": False,
    })


@router.get("/profile/sections/custom", response_class=HTMLResponse)
async def get_custom(request: Request, db=Depends(get_db)):
    return _r(request, "sections/custom.html", {"sections": _custom_sections(db), "saved": False,
    })


# ── New-entry fragment routes (HTMX appends these) ───────────────────────────

_BLANK_EXP = {"id": None, "company": "", "title": "", "location": "",
              "start_date": "", "end_date": "", "description": "", "bullets": []}
_BLANK_EDU = {"id": None, "institution": "", "degree": "", "field": "",
              "start_date": "", "end_date": "", "gpa": "", "highlights": []}
_BLANK_PROJ = {"id": None, "name": "", "description": "", "tech_stack": [],
               "url": "", "bullets": []}
_BLANK_CERT = {"id": None, "name": "", "issuer": "", "date": "", "url": ""}
_BLANK_CUSTOM = {"id": None, "name": "", "content": ""}


@router.get("/profile/sections/experience/new-entry", response_class=HTMLResponse)
async def new_exp_entry(request: Request):
    return _r(request, "sections/partials/_exp_entry.html", {"entry": _BLANK_EXP, "expanded": True,
    })


@router.get("/profile/sections/education/new-entry", response_class=HTMLResponse)
async def new_edu_entry(request: Request):
    return _r(request, "sections/partials/_edu_entry.html", {"entry": _BLANK_EDU, "expanded": True,
    })


@router.get("/profile/sections/projects/new-entry", response_class=HTMLResponse)
async def new_proj_entry(request: Request):
    return _r(request, "sections/partials/_proj_entry.html", {"entry": _BLANK_PROJ, "expanded": True,
    })


@router.get("/profile/sections/certifications/new-entry", response_class=HTMLResponse)
async def new_cert_entry(request: Request):
    return _r(request, "sections/partials/_cert_entry.html", {"entry": _BLANK_CERT, "expanded": True,
    })


@router.get("/profile/sections/custom/new-entry", response_class=HTMLResponse)
async def new_custom_entry(request: Request):
    return _r(request, "sections/partials/_custom_entry.html", {"entry": _BLANK_CUSTOM, "expanded": True,
    })


@router.get("/profile/sections/skills/new-row", response_class=HTMLResponse)
async def new_skill_row(request: Request):
    return _r(request, "sections/partials/_skill_row.html", {"group": {"category": "", "skills": []},
    })


# ── Section PUT (save) routes ─────────────────────────────────────────────────

@router.put("/profile/sections/personal", response_class=HTMLResponse)
async def save_personal(request: Request, db=Depends(get_db)):
    form = await request.form()
    db.execute(
        "UPDATE profile SET full_name=?, email=?, phone=?, location=?, updated_at=CURRENT_TIMESTAMP WHERE id=1",
        (form.get("full_name") or None, form.get("email") or None,
         form.get("phone") or None, form.get("location") or None),
    )
    db.execute("DELETE FROM profile_links WHERE profile_id=1")
    labels = form.getlist("link_label")
    urls = form.getlist("link_url")
    for i, (label, url) in enumerate(zip(labels, urls)):
        if label.strip() or url.strip():
            db.execute(
                "INSERT INTO profile_links (profile_id, label, url, display_order) VALUES (1,?,?,?)",
                (label.strip(), url.strip(), i),
            )
    db.commit()
    return _r(request, "sections/personal.html", {"personal": _personal(db), "saved": True,
    })


@router.put("/profile/sections/summary", response_class=HTMLResponse)
async def save_summary(request: Request, db=Depends(get_db)):
    form = await request.form()
    summary = form.get("summary") or None
    db.execute(
        "UPDATE profile SET summary=?, updated_at=CURRENT_TIMESTAMP WHERE id=1", (summary,)
    )
    db.commit()
    return _r(request, "sections/summary.html", {"summary": summary or "", "saved": True,
    })


@router.put("/profile/sections/experience", response_class=HTMLResponse)
async def save_experience(request: Request, db=Depends(get_db)):
    form = await request.form()
    ids = form.getlist("exp_id")
    companies = form.getlist("company")
    titles = form.getlist("title")
    locations = form.getlist("exp_location")
    starts = form.getlist("start_date")
    ends = form.getlist("end_date")
    descs = form.getlist("description")
    bullets_raw = form.getlist("bullets")

    existing = {str(r["id"]) for r in db.execute(
        "SELECT id FROM experience WHERE profile_id=1"
    ).fetchall()}
    submitted = {eid for eid in ids if eid}
    for eid in existing - submitted:
        db.execute("DELETE FROM experience WHERE id=?", (eid,))

    for i, (eid, company, title) in enumerate(zip(ids, companies, titles)):
        if not company.strip() and not title.strip():
            continue
        loc = locations[i] if i < len(locations) else None
        start = starts[i] if i < len(starts) else None
        end = ends[i] if i < len(ends) else None
        desc = descs[i] if i < len(descs) else None
        bullets = [b.strip() for b in (bullets_raw[i] if i < len(bullets_raw) else "").splitlines() if b.strip()]

        if eid:
            db.execute(
                "UPDATE experience SET company=?,title=?,location=?,start_date=?,end_date=?,description=?,display_order=? WHERE id=?",
                (company.strip() or None, title.strip() or None, loc or None,
                 start or None, end or None, desc or None, i, int(eid)),
            )
            db.execute("DELETE FROM experience_bullets WHERE experience_id=?", (int(eid),))
            exp_id = int(eid)
        else:
            cur = db.execute(
                "INSERT INTO experience (profile_id,company,title,location,start_date,end_date,description,display_order) VALUES (1,?,?,?,?,?,?,?)",
                (company.strip() or None, title.strip() or None, loc or None,
                 start or None, end or None, desc or None, i),
            )
            exp_id = cur.lastrowid

        for j, text in enumerate(bullets):
            db.execute(
                "INSERT INTO experience_bullets (experience_id,text,display_order) VALUES (?,?,?)",
                (exp_id, text, j),
            )

    db.commit()
    return _r(request, "sections/experience.html", {"entries": _experience(db), "saved": True,
    })


@router.put("/profile/sections/education", response_class=HTMLResponse)
async def save_education(request: Request, db=Depends(get_db)):
    form = await request.form()
    ids = form.getlist("edu_id")
    institutions = form.getlist("institution")
    degrees = form.getlist("degree")
    fields = form.getlist("field")
    starts = form.getlist("start_date")
    ends = form.getlist("end_date")
    gpas = form.getlist("gpa")
    highlights_raw = form.getlist("highlights")

    existing = {str(r["id"]) for r in db.execute(
        "SELECT id FROM education WHERE profile_id=1"
    ).fetchall()}
    submitted = {eid for eid in ids if eid}
    for eid in existing - submitted:
        db.execute("DELETE FROM education WHERE id=?", (eid,))

    for i, (eid, inst, deg, fld) in enumerate(zip(ids, institutions, degrees, fields)):
        if not inst.strip() and not deg.strip():
            continue
        start = starts[i] if i < len(starts) else None
        end = ends[i] if i < len(ends) else None
        gpa = gpas[i] if i < len(gpas) else None
        highlights = json.dumps([h.strip() for h in (highlights_raw[i] if i < len(highlights_raw) else "").splitlines() if h.strip()])

        if eid:
            db.execute(
                "UPDATE education SET institution=?,degree=?,field=?,start_date=?,end_date=?,gpa=?,highlights=?,display_order=? WHERE id=?",
                (inst.strip() or None, deg.strip() or None, fld.strip() or None,
                 start or None, end or None, gpa or None, highlights, i, int(eid)),
            )
        else:
            db.execute(
                "INSERT INTO education (profile_id,institution,degree,field,start_date,end_date,gpa,highlights,display_order) VALUES (1,?,?,?,?,?,?,?,?)",
                (inst.strip() or None, deg.strip() or None, fld.strip() or None,
                 start or None, end or None, gpa or None, highlights, i),
            )

    db.commit()
    return _r(request, "sections/education.html", {"entries": _education(db), "saved": True,
    })


@router.put("/profile/sections/skills", response_class=HTMLResponse)
async def save_skills(request: Request, db=Depends(get_db)):
    form = await request.form()
    categories = form.getlist("skill_category")
    skill_lists = form.getlist("skill_list")

    db.execute("DELETE FROM skills WHERE profile_id=1")
    order = 0
    for category, skills_str in zip(categories, skill_lists):
        if not category.strip():
            continue
        for skill in [s.strip() for s in skills_str.split(",") if s.strip()]:
            db.execute(
                "INSERT INTO skills (profile_id,category,skill,display_order) VALUES (1,?,?,?)",
                (category.strip(), skill, order),
            )
            order += 1

    db.commit()
    return _r(request, "sections/skills.html", {"groups": _skills(db), "saved": True,
    })


@router.put("/profile/sections/projects", response_class=HTMLResponse)
async def save_projects(request: Request, db=Depends(get_db)):
    form = await request.form()
    ids = form.getlist("proj_id")
    names = form.getlist("proj_name")
    descs = form.getlist("proj_desc")
    techs = form.getlist("tech_stack")
    urls = form.getlist("proj_url")
    bullets_raw = form.getlist("bullets")

    existing = {str(r["id"]) for r in db.execute(
        "SELECT id FROM projects WHERE profile_id=1"
    ).fetchall()}
    submitted = {pid for pid in ids if pid}
    for pid in existing - submitted:
        db.execute("DELETE FROM projects WHERE id=?", (pid,))

    for i, (pid, name) in enumerate(zip(ids, names)):
        if not name.strip():
            continue
        desc = descs[i] if i < len(descs) else None
        tech = json.dumps([s.strip() for s in (techs[i] if i < len(techs) else "").split(",") if s.strip()])
        url = urls[i] if i < len(urls) else None
        bullets = json.dumps([b.strip() for b in (bullets_raw[i] if i < len(bullets_raw) else "").splitlines() if b.strip()])

        if pid:
            db.execute(
                "UPDATE projects SET name=?,description=?,tech_stack=?,url=?,bullets=?,display_order=? WHERE id=?",
                (name.strip(), desc or None, tech, url or None, bullets, i, int(pid)),
            )
        else:
            db.execute(
                "INSERT INTO projects (profile_id,name,description,tech_stack,url,bullets,display_order) VALUES (1,?,?,?,?,?,?)",
                (name.strip(), desc or None, tech, url or None, bullets, i),
            )

    db.commit()
    return _r(request, "sections/projects.html", {"entries": _projects(db), "saved": True,
    })


@router.put("/profile/sections/certifications", response_class=HTMLResponse)
async def save_certifications(request: Request, db=Depends(get_db)):
    form = await request.form()
    ids = form.getlist("cert_id")
    names = form.getlist("cert_name")
    issuers = form.getlist("issuer")
    dates = form.getlist("cert_date")
    urls = form.getlist("cert_url")

    existing = {str(r["id"]) for r in db.execute(
        "SELECT id FROM certifications WHERE profile_id=1"
    ).fetchall()}
    submitted = {cid for cid in ids if cid}
    for cid in existing - submitted:
        db.execute("DELETE FROM certifications WHERE id=?", (cid,))

    for i, (cid, name) in enumerate(zip(ids, names)):
        if not name.strip():
            continue
        issuer = issuers[i] if i < len(issuers) else ""
        date = dates[i] if i < len(dates) else None
        url = urls[i] if i < len(urls) else None

        if cid:
            db.execute(
                "UPDATE certifications SET name=?,issuer=?,date=?,url=?,display_order=? WHERE id=?",
                (name.strip(), issuer.strip() or None, date or None, url or None, i, int(cid)),
            )
        else:
            db.execute(
                "INSERT INTO certifications (profile_id,name,issuer,date,url,display_order) VALUES (1,?,?,?,?,?)",
                (name.strip(), issuer.strip() or None, date or None, url or None, i),
            )

    db.commit()
    return _r(request, "sections/certifications.html", {"entries": _certifications(db), "saved": True,
    })


@router.post("/profile/quick_add_skills")
async def quick_add_skills(request: Request, db=Depends(get_db)):
    """Add skills from the gap nudge panel on the analysis results page."""
    from fastapi.responses import RedirectResponse
    form = await request.form()
    skills_str = form.get("skills", "")
    category = (form.get("category") or "Gap Skills").strip()
    skills = [s.strip() for s in skills_str.split(",") if s.strip()]

    if skills:
        max_order = db.execute(
            "SELECT COALESCE(MAX(display_order), -1) FROM skills WHERE profile_id=1"
        ).fetchone()[0]
        for i, skill in enumerate(skills):
            db.execute(
                "INSERT INTO skills (profile_id, category, skill, display_order) VALUES (1,?,?,?)",
                (category, skill, max_order + i + 1),
            )
        db.commit()

    return RedirectResponse(url="/profile", status_code=303)


@router.put("/profile/sections/custom", response_class=HTMLResponse)
async def save_custom(request: Request, db=Depends(get_db)):
    form = await request.form()
    ids = form.getlist("section_id")
    names = form.getlist("section_name")
    contents = form.getlist("section_content")

    existing = {str(r["id"]) for r in db.execute(
        "SELECT id FROM custom_sections WHERE profile_id=1"
    ).fetchall()}
    submitted = {sid for sid in ids if sid}
    for sid in existing - submitted:
        db.execute("DELETE FROM custom_sections WHERE id=?", (sid,))

    for i, (sid, name) in enumerate(zip(ids, names)):
        if not name.strip():
            continue
        content = contents[i] if i < len(contents) else ""

        if sid:
            db.execute(
                "UPDATE custom_sections SET name=?,content=?,display_order=? WHERE id=?",
                (name.strip(), content.strip() or None, i, int(sid)),
            )
        else:
            db.execute(
                "INSERT INTO custom_sections (profile_id,name,content,display_order) VALUES (1,?,?,?)",
                (name.strip(), content.strip() or None, i),
            )

    db.commit()
    return _r(request, "sections/custom.html", {"sections": _custom_sections(db), "saved": True,
    })
