import sqlite3

from ..models import ChatMessage, Suggestion, SUGGESTION_STATUSES


def create_message(
    conn: sqlite3.Connection,
    *,
    application_id: str,
    role: str,
    content: str,
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_cents: float = 0.0,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO chat_messages
            (application_id, role, content, model, input_tokens, output_tokens, cost_cents)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (application_id, role, content, model, input_tokens, output_tokens, cost_cents),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def list_messages(conn: sqlite3.Connection, application_id: str) -> list[ChatMessage]:
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE application_id = ? ORDER BY id ASC",
        (application_id,),
    ).fetchall()
    return [_row_to_message(r) for r in rows]


def get_message(conn: sqlite3.Connection, message_id: int) -> ChatMessage | None:
    row = conn.execute(
        "SELECT * FROM chat_messages WHERE id = ?", (message_id,)
    ).fetchone()
    return _row_to_message(row) if row else None


def create_suggestion(
    conn: sqlite3.Connection,
    *,
    application_id: str,
    message_id: int,
    suggestion_type: str,
    target_section: str,
    current_value: str = "",
    proposed_value: str = "",
    rationale: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO pending_suggestions
            (application_id, message_id, suggestion_type, target_section,
             current_value, proposed_value, rationale, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """,
        (
            application_id,
            message_id,
            suggestion_type,
            target_section,
            current_value,
            proposed_value,
            rationale,
        ),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def list_pending_suggestions(
    conn: sqlite3.Connection, application_id: str
) -> list[Suggestion]:
    rows = conn.execute(
        """
        SELECT * FROM pending_suggestions
        WHERE application_id = ? AND status = 'pending'
        ORDER BY id ASC
        """,
        (application_id,),
    ).fetchall()
    return [_row_to_suggestion(r) for r in rows]


def get_suggestion(conn: sqlite3.Connection, suggestion_id: int) -> Suggestion | None:
    row = conn.execute(
        "SELECT * FROM pending_suggestions WHERE id = ?", (suggestion_id,)
    ).fetchone()
    return _row_to_suggestion(row) if row else None


def set_suggestion_status(
    conn: sqlite3.Connection, suggestion_id: int, status: str
) -> bool:
    if status not in SUGGESTION_STATUSES:
        raise ValueError(f"status must be one of {SUGGESTION_STATUSES}")
    cur = conn.execute(
        "UPDATE pending_suggestions SET status = ? WHERE id = ?",
        (status, suggestion_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_to_message(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        application_id=row["application_id"],
        role=row["role"],
        content=row["content"],
        timestamp=row["timestamp"] or "",
        input_tokens=row["input_tokens"] or 0,
        output_tokens=row["output_tokens"] or 0,
        cost_cents=row["cost_cents"] or 0.0,
        model=row["model"] or "",
    )


def _row_to_suggestion(row: sqlite3.Row) -> Suggestion:
    return Suggestion(
        id=row["id"],
        application_id=row["application_id"],
        message_id=row["message_id"],
        suggestion_type=row["suggestion_type"] or "",
        target_section=row["target_section"] or "",
        current_value=row["current_value"] or "",
        proposed_value=row["proposed_value"] or "",
        rationale=row["rationale"] or "",
        status=row["status"] or "pending",
        created_at=row["created_at"] or "",
    )
