import sqlite3

from backend.models import PersonalInfo, ProfileLink

PROFILE_ID = 1


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


def list_links(conn: sqlite3.Connection) -> list[ProfileLink]:
    rows = conn.execute(
        """
        SELECT id, label, url
        FROM profile_links
        WHERE profile_id = ?
        ORDER BY display_order, id
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
    new_id = cursor.lastrowid
    return ProfileLink(id=new_id, label=link.label, url=link.url)


def delete_link(conn: sqlite3.Connection, link_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM profile_links WHERE id = ? AND profile_id = ?",
        (link_id, PROFILE_ID),
    )
    conn.commit()
    return cursor.rowcount > 0
