"""Chat routes: POST message, SSE stream, GET chat page."""
import json
import logging
import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

from backend.db import get_db
from backend.services import application_repo, chat_repo, tailored_repo
from backend.services.chat_service import build_chat_context, parse_suggestions
from backend.services.llm_client import LLMError, stream_llm
from backend.services.resume_validator import build_source_index, validate_tailored_resume
from backend.services.suggestion_apply import apply_suggestion
from backend.templating import templates

router = APIRouter(prefix="/applications")
log = logging.getLogger(__name__)

CHAT_MODEL = "claude-sonnet-4-6"


@router.post("/{app_id}/chat", response_class=HTMLResponse)
async def post_chat_message(
    app_id: str,
    message: str = Form(default=""),
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return RedirectResponse(url="/applications", status_code=303)

    if not message.strip():
        return RedirectResponse(url=f"/applications/{app_id}/chat", status_code=303)

    tailored_row = tailored_repo.get_latest_for_application(db, app_id)
    if tailored_row is None:
        return RedirectResponse(url=f"/applications/{app_id}/tailored", status_code=303)

    message_id = chat_repo.create_message(
        db,
        application_id=app_id,
        role="user",
        content=message.strip(),
    )

    return RedirectResponse(
        url=f"/applications/{app_id}/chat?streaming={message_id}",
        status_code=303,
    )


@router.get("/{app_id}/chat/stream/{message_id}")
def stream_chat(
    app_id: str,
    message_id: int,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        def _not_found():
            yield f"event: error\ndata: {json.dumps('Application not found')}\n\n"
        return StreamingResponse(_not_found(), media_type="text/event-stream")

    user_msg = chat_repo.get_message(db, message_id)
    if user_msg is None:
        def _msg_not_found():
            yield f"event: error\ndata: {json.dumps('Message not found')}\n\n"
        return StreamingResponse(_msg_not_found(), media_type="text/event-stream")

    tailored_row = tailored_repo.get_latest_for_application(db, app_id)
    if tailored_row is None:
        def _no_tailored():
            yield f"event: error\ndata: {json.dumps('No tailored resume found')}\n\n"
        return StreamingResponse(_no_tailored(), media_type="text/event-stream")

    history = chat_repo.list_messages(db, app_id)
    # Exclude the current user message from history (it's the new message)
    history = [m for m in history if m.id != message_id]

    def generate():
        try:
            system, messages_list = build_chat_context(
                application, tailored_row, history, user_msg.content
            )

            full_text = ""
            usage_info: dict = {}

            for event in stream_llm(
                system,
                messages_list,
                model=CHAT_MODEL,
                operation="chat_message",
                application_id=app_id,
                db_conn=db,
                max_tokens=2048,
                use_cache=True,
            ):
                if event.type == "token":
                    full_text += event.text
                    yield f"event: token\ndata: {json.dumps(event.text)}\n\n"
                elif event.type == "done":
                    usage_info = event.usage_info

            # Persist assistant message
            assistant_mid = chat_repo.create_message(
                db,
                application_id=app_id,
                role="assistant",
                content=full_text,
                model=usage_info.get("model", CHAT_MODEL),
                input_tokens=usage_info.get("input_tokens", 0),
                output_tokens=usage_info.get("output_tokens", 0),
                cost_cents=usage_info.get("cost_cents", 0.0),
            )

            # Parse and persist suggestions
            suggestions = parse_suggestions(full_text)
            log.info(
                "chat: app=%s assistant_chars=%d parsed_suggestions=%d has_marker=%s",
                app_id,
                len(full_text),
                len(suggestions),
                "<<<SUGGESTIONS>>>" in full_text,
            )
            suggestion_count = 0
            for s in suggestions:
                chat_repo.create_suggestion(
                    db,
                    application_id=app_id,
                    message_id=assistant_mid,
                    suggestion_type=s["type"],
                    target_section=s["target"],
                    current_value="",
                    proposed_value=s["proposed"],
                    rationale=s.get("rationale", ""),
                )
                suggestion_count += 1

            yield (
                f"event: done\ndata: {json.dumps({'message_id': assistant_mid, 'suggestion_count': suggestion_count})}\n\n"
            )

        except LLMError as exc:
            yield f"event: error\ndata: {json.dumps(str(exc))}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{app_id}/chat", response_class=HTMLResponse)
async def show_chat(
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
    history = chat_repo.list_messages(db, app_id)
    pending = chat_repo.list_pending_suggestions(db, app_id)

    streaming_param = request.query_params.get("streaming")
    try:
        streaming_message_id = int(streaming_param) if streaming_param else None
    except ValueError:
        streaming_message_id = None

    chat_cost_cents = db.execute(
        "SELECT COALESCE(SUM(cost_cents), 0) FROM chat_messages WHERE application_id = ?",
        (app_id,),
    ).fetchone()[0]

    applied_version = request.query_params.get("applied")

    return templates.TemplateResponse(
        request,
        "applications/chat.html",
        {
            "active": "applications",
            "application": application,
            "tailored_row": tailored_row,
            "history": history,
            "pending": pending,
            "streaming_message_id": streaming_message_id,
            "chat_cost_cents": chat_cost_cents,
            "applied_version": applied_version,
        },
    )


@router.post("/{app_id}/suggestions/{sid}/apply", response_class=HTMLResponse)
async def apply_suggestion_route(
    app_id: str,
    sid: int,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return RedirectResponse(url="/applications", status_code=303)

    suggestion = chat_repo.get_suggestion(db, sid)
    if suggestion is None or suggestion.application_id != app_id:
        return RedirectResponse(url=f"/applications/{app_id}/chat", status_code=303)

    current = tailored_repo.get_latest_for_application(db, app_id)
    if current is None:
        return RedirectResponse(url=f"/applications/{app_id}/tailored", status_code=303)

    try:
        new_content = apply_suggestion(current.content, suggestion)
    except ValueError:
        return RedirectResponse(url=f"/applications/{app_id}/chat", status_code=303)

    source_index = build_source_index(db)
    new_validation = validate_tailored_resume(new_content, source_index)

    new_id = tailored_repo.create_tailored(
        db,
        application_id=app_id,
        content=new_content,
        validation=new_validation,
        profile_hash=current.profile_hash,
        model=current.model,
        cost_cents=0.0,
        source="chat-edit",
        parent_version=current.version,
    )

    new_row = tailored_repo.get_tailored(db, new_id)
    chat_repo.set_suggestion_status(db, sid, "applied")

    return RedirectResponse(
        url=f"/applications/{app_id}/chat?applied={new_row.version if new_row else ''}",
        status_code=303,
    )


@router.post("/{app_id}/suggestions/{sid}/reject", response_class=HTMLResponse)
async def reject_suggestion_route(
    app_id: str,
    sid: int,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    application = application_repo.get_application(db, app_id)
    if application is None:
        return RedirectResponse(url="/applications", status_code=303)

    suggestion = chat_repo.get_suggestion(db, sid)
    if suggestion is not None and suggestion.application_id == app_id:
        chat_repo.set_suggestion_status(db, sid, "rejected")

    return RedirectResponse(url=f"/applications/{app_id}/chat", status_code=303)
