import json
import sqlite3


def load_full_profile(db: sqlite3.Connection) -> dict:
    """Load the complete profile from DB as a structured dict for LLM/analysis use."""
    row = db.execute("SELECT * FROM profile WHERE id=1").fetchone()
    if not row:
        return _empty_profile()

    p = dict(row)

    links = [dict(r) for r in db.execute(
        "SELECT label, url FROM profile_links WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]

    personal_info = {
        "full_name": p.get("full_name"),
        "email": p.get("email"),
        "phone": p.get("phone"),
        "location": p.get("location"),
        "links": links,
    }

    experience = []
    for exp_row in db.execute(
        "SELECT * FROM experience WHERE profile_id=1 ORDER BY display_order"
    ).fetchall():
        exp = dict(exp_row)
        exp["bullets"] = [r["text"] for r in db.execute(
            "SELECT text FROM experience_bullets WHERE experience_id=? ORDER BY display_order",
            (exp["id"],),
        ).fetchall()]
        experience.append(exp)

    education = []
    for edu_row in db.execute(
        "SELECT * FROM education WHERE profile_id=1 ORDER BY display_order"
    ).fetchall():
        edu = dict(edu_row)
        edu["highlights"] = json.loads(edu["highlights"]) if edu.get("highlights") else []
        education.append(edu)

    seen: dict[str, int] = {}
    skills: list[dict] = []
    for r in db.execute(
        "SELECT category, skill FROM skills WHERE profile_id=1 ORDER BY display_order"
    ).fetchall():
        cat = r["category"] or "General"
        if cat not in seen:
            seen[cat] = len(skills)
            skills.append({"category": cat, "skills": []})
        skills[seen[cat]]["skills"].append(r["skill"])

    projects = []
    for proj_row in db.execute(
        "SELECT * FROM projects WHERE profile_id=1 ORDER BY display_order"
    ).fetchall():
        proj = dict(proj_row)
        proj["tech_stack"] = json.loads(proj["tech_stack"]) if proj.get("tech_stack") else []
        proj["bullets"] = json.loads(proj["bullets"]) if proj.get("bullets") else []
        projects.append(proj)

    certifications = [dict(r) for r in db.execute(
        "SELECT * FROM certifications WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]

    custom_sections = [dict(r) for r in db.execute(
        "SELECT * FROM custom_sections WHERE profile_id=1 ORDER BY display_order"
    ).fetchall()]

    return {
        "personal_info": personal_info,
        "summary": p.get("summary"),
        "experience": experience,
        "education": education,
        "skills": skills,
        "projects": projects,
        "certifications": certifications,
        "custom_sections": custom_sections,
    }


def _empty_profile() -> dict:
    return {
        "personal_info": {
            "full_name": None, "email": None, "phone": None, "location": None, "links": [],
        },
        "summary": None,
        "experience": [],
        "education": [],
        "skills": [],
        "projects": [],
        "certifications": [],
        "custom_sections": [],
    }
