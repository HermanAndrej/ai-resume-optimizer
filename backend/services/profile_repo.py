import sqlite3

from backend.models import (
    CertificationEntry,
    CustomSectionEntry,
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    ParsedProfile,
    PersonalInfo,
    ProfileLink,
    ProjectEntry,
    Skill,
    Summary,
)

PROFILE_ID = 1


# ---------- Personal info ----------

def get_personal_info(conn: sqlite3.Connection) -> PersonalInfo:
    row = conn.execute(
        "SELECT full_name, email, phone, location FROM profile WHERE id = ?",
        (PROFILE_ID,),
    ).fetchone()
    if not row:
        return PersonalInfo()
    return PersonalInfo(
        full_name=row["full_name"] or "",
        email=row["email"] or "",
        phone=row["phone"] or "",
        location=row["location"] or "",
    )


def save_personal_info(conn: sqlite3.Connection, info: PersonalInfo) -> None:
    conn.execute(
        """
        UPDATE profile
        SET full_name = ?, email = ?, phone = ?, location = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (info.full_name, info.email, info.phone, info.location, PROFILE_ID),
    )
    conn.commit()


# ---------- Summary ----------

def get_summary(conn: sqlite3.Connection) -> Summary:
    row = conn.execute(
        "SELECT summary FROM profile WHERE id = ?", (PROFILE_ID,)
    ).fetchone()
    return Summary(text=(row["summary"] if row and row["summary"] else ""))


def save_summary(conn: sqlite3.Connection, summary: Summary) -> None:
    conn.execute(
        "UPDATE profile SET summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (summary.text, PROFILE_ID),
    )
    conn.commit()


# ---------- Links ----------

def list_links(conn: sqlite3.Connection) -> list[ProfileLink]:
    rows = conn.execute(
        """
        SELECT id, label, url FROM profile_links
        WHERE profile_id = ? ORDER BY display_order, id
        """,
        (PROFILE_ID,),
    ).fetchall()
    return [ProfileLink(id=r["id"], label=r["label"], url=r["url"]) for r in rows]


def add_link(conn: sqlite3.Connection, link: ProfileLink) -> ProfileLink:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM profile_links WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO profile_links (profile_id, label, url, display_order) VALUES (?, ?, ?, ?)",
        (PROFILE_ID, link.label, link.url, next_order),
    )
    conn.commit()
    return ProfileLink(id=cursor.lastrowid, label=link.label, url=link.url)


def delete_link(conn: sqlite3.Connection, link_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM profile_links WHERE id = ? AND profile_id = ?",
        (link_id, PROFILE_ID),
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- Experience ----------

def list_experience(conn: sqlite3.Connection) -> list[ExperienceEntry]:
    rows = conn.execute(
        """
        SELECT id, company, title, location, start_date, end_date, description
        FROM experience
        WHERE profile_id = ? ORDER BY display_order, id
        """,
        (PROFILE_ID,),
    ).fetchall()
    entries = []
    for r in rows:
        bullets = conn.execute(
            """
            SELECT id, text FROM experience_bullets
            WHERE experience_id = ? ORDER BY display_order, id
            """,
            (r["id"],),
        ).fetchall()
        entries.append(
            ExperienceEntry(
                id=r["id"],
                company=r["company"],
                title=r["title"],
                location=r["location"] or "",
                start_date=r["start_date"] or "",
                end_date=r["end_date"] or "",
                description=r["description"] or "",
                bullets=[ExperienceBullet(id=b["id"], text=b["text"]) for b in bullets],
            )
        )
    return entries


def add_experience(conn: sqlite3.Connection) -> ExperienceEntry:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM experience WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchone()["n"]
    cursor = conn.execute(
        """
        INSERT INTO experience (profile_id, company, title, display_order)
        VALUES (?, '', '', ?)
        """,
        (PROFILE_ID, next_order),
    )
    conn.commit()
    return ExperienceEntry(id=cursor.lastrowid, company="", title="")


def update_experience(conn: sqlite3.Connection, entry: ExperienceEntry) -> None:
    conn.execute(
        """
        UPDATE experience
        SET company = ?, title = ?, location = ?, start_date = ?, end_date = ?, description = ?
        WHERE id = ? AND profile_id = ?
        """,
        (
            entry.company,
            entry.title,
            entry.location,
            entry.start_date,
            entry.end_date,
            entry.description,
            entry.id,
            PROFILE_ID,
        ),
    )
    conn.commit()


def delete_experience(conn: sqlite3.Connection, entry_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM experience WHERE id = ? AND profile_id = ?",
        (entry_id, PROFILE_ID),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_experience_entry(conn: sqlite3.Connection, entry_id: int) -> ExperienceEntry | None:
    row = conn.execute(
        """
        SELECT id, company, title, location, start_date, end_date, description
        FROM experience WHERE id = ? AND profile_id = ?
        """,
        (entry_id, PROFILE_ID),
    ).fetchone()
    if not row:
        return None
    bullets = conn.execute(
        "SELECT id, text FROM experience_bullets WHERE experience_id = ? ORDER BY display_order, id",
        (entry_id,),
    ).fetchall()
    return ExperienceEntry(
        id=row["id"],
        company=row["company"],
        title=row["title"],
        location=row["location"] or "",
        start_date=row["start_date"] or "",
        end_date=row["end_date"] or "",
        description=row["description"] or "",
        bullets=[ExperienceBullet(id=b["id"], text=b["text"]) for b in bullets],
    )


def add_experience_bullet(
    conn: sqlite3.Connection, experience_id: int, text: str
) -> ExperienceBullet:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM experience_bullets WHERE experience_id = ?",
        (experience_id,),
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO experience_bullets (experience_id, text, display_order) VALUES (?, ?, ?)",
        (experience_id, text, next_order),
    )
    conn.commit()
    return ExperienceBullet(id=cursor.lastrowid, text=text)


def delete_experience_bullet(conn: sqlite3.Connection, bullet_id: int) -> bool:
    cursor = conn.execute("DELETE FROM experience_bullets WHERE id = ?", (bullet_id,))
    conn.commit()
    return cursor.rowcount > 0


# ---------- Education ----------

def list_education(conn: sqlite3.Connection) -> list[EducationEntry]:
    rows = conn.execute(
        """
        SELECT id, institution, degree, field, start_date, end_date, gpa, highlights
        FROM education WHERE profile_id = ? ORDER BY display_order, id
        """,
        (PROFILE_ID,),
    ).fetchall()
    return [
        EducationEntry(
            id=r["id"],
            institution=r["institution"],
            degree=r["degree"] or "",
            field=r["field"] or "",
            start_date=r["start_date"] or "",
            end_date=r["end_date"] or "",
            gpa=r["gpa"] or "",
            highlights=r["highlights"] or "",
        )
        for r in rows
    ]


def add_education(conn: sqlite3.Connection) -> EducationEntry:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM education WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO education (profile_id, institution, display_order) VALUES (?, '', ?)",
        (PROFILE_ID, next_order),
    )
    conn.commit()
    return EducationEntry(id=cursor.lastrowid, institution="")


def update_education(conn: sqlite3.Connection, entry: EducationEntry) -> None:
    conn.execute(
        """
        UPDATE education SET institution = ?, degree = ?, field = ?,
               start_date = ?, end_date = ?, gpa = ?, highlights = ?
        WHERE id = ? AND profile_id = ?
        """,
        (
            entry.institution,
            entry.degree,
            entry.field,
            entry.start_date,
            entry.end_date,
            entry.gpa,
            entry.highlights,
            entry.id,
            PROFILE_ID,
        ),
    )
    conn.commit()


def delete_education(conn: sqlite3.Connection, entry_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM education WHERE id = ? AND profile_id = ?", (entry_id, PROFILE_ID)
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- Skills ----------

def list_skills_grouped(conn: sqlite3.Connection) -> dict[str, list[Skill]]:
    rows = conn.execute(
        """
        SELECT id, category, skill FROM skills
        WHERE profile_id = ? ORDER BY category, display_order, id
        """,
        (PROFILE_ID,),
    ).fetchall()
    grouped: dict[str, list[Skill]] = {}
    for r in rows:
        cat = r["category"]
        grouped.setdefault(cat, []).append(
            Skill(id=r["id"], category=cat, skill=r["skill"])
        )
    return grouped


def add_skill(conn: sqlite3.Connection, category: str, skill_name: str) -> Skill:
    next_order = conn.execute(
        """
        SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM skills
        WHERE profile_id = ? AND category = ?
        """,
        (PROFILE_ID, category),
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO skills (profile_id, category, skill, display_order) VALUES (?, ?, ?, ?)",
        (PROFILE_ID, category, skill_name, next_order),
    )
    conn.commit()
    return Skill(id=cursor.lastrowid, category=category, skill=skill_name)


def delete_skill(conn: sqlite3.Connection, skill_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM skills WHERE id = ? AND profile_id = ?", (skill_id, PROFILE_ID)
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- Projects ----------

def list_projects(conn: sqlite3.Connection) -> list[ProjectEntry]:
    rows = conn.execute(
        """
        SELECT id, name, description, tech_stack, url, bullets
        FROM projects WHERE profile_id = ? ORDER BY display_order, id
        """,
        (PROFILE_ID,),
    ).fetchall()
    return [
        ProjectEntry(
            id=r["id"],
            name=r["name"],
            description=r["description"] or "",
            tech_stack=r["tech_stack"] or "",
            url=r["url"] or "",
            bullets=r["bullets"] or "",
        )
        for r in rows
    ]


def add_project(conn: sqlite3.Connection) -> ProjectEntry:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM projects WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO projects (profile_id, name, display_order) VALUES (?, '', ?)",
        (PROFILE_ID, next_order),
    )
    conn.commit()
    return ProjectEntry(id=cursor.lastrowid, name="")


def update_project(conn: sqlite3.Connection, entry: ProjectEntry) -> None:
    conn.execute(
        """
        UPDATE projects SET name = ?, description = ?, tech_stack = ?, url = ?, bullets = ?
        WHERE id = ? AND profile_id = ?
        """,
        (
            entry.name,
            entry.description,
            entry.tech_stack,
            entry.url,
            entry.bullets,
            entry.id,
            PROFILE_ID,
        ),
    )
    conn.commit()


def delete_project(conn: sqlite3.Connection, entry_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM projects WHERE id = ? AND profile_id = ?", (entry_id, PROFILE_ID)
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- Certifications ----------

def list_certifications(conn: sqlite3.Connection) -> list[CertificationEntry]:
    rows = conn.execute(
        """
        SELECT id, name, issuer, date, url FROM certifications
        WHERE profile_id = ? ORDER BY display_order, id
        """,
        (PROFILE_ID,),
    ).fetchall()
    return [
        CertificationEntry(
            id=r["id"],
            name=r["name"],
            issuer=r["issuer"] or "",
            date=r["date"] or "",
            url=r["url"] or "",
        )
        for r in rows
    ]


def add_certification(conn: sqlite3.Connection) -> CertificationEntry:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM certifications WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO certifications (profile_id, name, display_order) VALUES (?, '', ?)",
        (PROFILE_ID, next_order),
    )
    conn.commit()
    return CertificationEntry(id=cursor.lastrowid, name="")


def update_certification(conn: sqlite3.Connection, entry: CertificationEntry) -> None:
    conn.execute(
        """
        UPDATE certifications SET name = ?, issuer = ?, date = ?, url = ?
        WHERE id = ? AND profile_id = ?
        """,
        (entry.name, entry.issuer, entry.date, entry.url, entry.id, PROFILE_ID),
    )
    conn.commit()


def delete_certification(conn: sqlite3.Connection, entry_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM certifications WHERE id = ? AND profile_id = ?",
        (entry_id, PROFILE_ID),
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- Custom sections ----------

def list_custom_sections(conn: sqlite3.Connection) -> list[CustomSectionEntry]:
    rows = conn.execute(
        """
        SELECT id, name, content FROM custom_sections
        WHERE profile_id = ? ORDER BY display_order, id
        """,
        (PROFILE_ID,),
    ).fetchall()
    return [
        CustomSectionEntry(id=r["id"], name=r["name"], content=r["content"] or "")
        for r in rows
    ]


def add_custom_section(conn: sqlite3.Connection) -> CustomSectionEntry:
    next_order = conn.execute(
        "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM custom_sections WHERE profile_id = ?",
        (PROFILE_ID,),
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO custom_sections (profile_id, name, display_order) VALUES (?, '', ?)",
        (PROFILE_ID, next_order),
    )
    conn.commit()
    return CustomSectionEntry(id=cursor.lastrowid, name="")


def update_custom_section(conn: sqlite3.Connection, entry: CustomSectionEntry) -> None:
    conn.execute(
        """
        UPDATE custom_sections SET name = ?, content = ?
        WHERE id = ? AND profile_id = ?
        """,
        (entry.name, entry.content, entry.id, PROFILE_ID),
    )
    conn.commit()


def delete_custom_section(conn: sqlite3.Connection, entry_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM custom_sections WHERE id = ? AND profile_id = ?",
        (entry_id, PROFILE_ID),
    )
    conn.commit()
    return cursor.rowcount > 0


# ---------- Apply parsed profile (resume import) ----------

def apply_parsed_profile(conn: sqlite3.Connection, parsed: ParsedProfile) -> None:
    """Replace the entire profile with data from a parsed resume.

    Runs as a single transaction: clears all list tables, updates the profile
    row, then re-inserts every parsed entry with sequential display_order.
    """
    conn.execute("BEGIN")
    try:
        # Update scalar fields on the profile row
        conn.execute(
            """
            UPDATE profile
            SET full_name = ?, email = ?, phone = ?, location = ?, summary = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                parsed.full_name,
                parsed.email,
                parsed.phone,
                parsed.location,
                parsed.summary,
                PROFILE_ID,
            ),
        )

        # Clear all list-type tables (experience_bullets cascades from experience)
        for table in (
            "profile_links",
            "experience",
            "education",
            "skills",
            "projects",
            "certifications",
            "custom_sections",
        ):
            conn.execute(f"DELETE FROM {table} WHERE profile_id = ?", (PROFILE_ID,))

        # Re-insert links
        for order, link in enumerate(parsed.links):
            conn.execute(
                "INSERT INTO profile_links (profile_id, label, url, display_order) VALUES (?, ?, ?, ?)",
                (PROFILE_ID, link.label, link.url, order),
            )

        # Re-insert experience + bullets
        for order, exp in enumerate(parsed.experience):
            cursor = conn.execute(
                """
                INSERT INTO experience
                    (profile_id, company, title, location, start_date, end_date, description, display_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PROFILE_ID,
                    exp.company,
                    exp.title,
                    exp.location,
                    exp.start_date,
                    exp.end_date,
                    exp.description,
                    order,
                ),
            )
            exp_id = cursor.lastrowid
            for b_order, bullet in enumerate(exp.bullets):
                conn.execute(
                    "INSERT INTO experience_bullets (experience_id, text, display_order) VALUES (?, ?, ?)",
                    (exp_id, bullet.text, b_order),
                )

        # Re-insert education
        for order, edu in enumerate(parsed.education):
            conn.execute(
                """
                INSERT INTO education
                    (profile_id, institution, degree, field, start_date, end_date, gpa, highlights, display_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PROFILE_ID,
                    edu.institution,
                    edu.degree,
                    edu.field,
                    edu.start_date,
                    edu.end_date,
                    edu.gpa,
                    edu.highlights,
                    order,
                ),
            )

        # Re-insert skills
        for order, skill in enumerate(parsed.skills):
            conn.execute(
                "INSERT INTO skills (profile_id, category, skill, display_order) VALUES (?, ?, ?, ?)",
                (PROFILE_ID, skill.category, skill.skill, order),
            )

        # Re-insert projects
        for order, proj in enumerate(parsed.projects):
            conn.execute(
                """
                INSERT INTO projects
                    (profile_id, name, description, tech_stack, url, bullets, display_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PROFILE_ID,
                    proj.name,
                    proj.description,
                    proj.tech_stack,
                    proj.url,
                    proj.bullets,
                    order,
                ),
            )

        # Re-insert certifications
        for order, cert in enumerate(parsed.certifications):
            conn.execute(
                "INSERT INTO certifications (profile_id, name, issuer, date, url, display_order) VALUES (?, ?, ?, ?, ?, ?)",
                (PROFILE_ID, cert.name, cert.issuer, cert.date, cert.url, order),
            )

        # Re-insert custom sections
        for order, section in enumerate(parsed.custom_sections):
            conn.execute(
                "INSERT INTO custom_sections (profile_id, name, content, display_order) VALUES (?, ?, ?, ?)",
                (PROFILE_ID, section.name, section.content, order),
            )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
