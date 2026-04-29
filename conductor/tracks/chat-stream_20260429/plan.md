# Implementation Plan: Chat with Streaming — Suggestion Apply/Reject

**Track ID:** `chat-stream_20260429`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-29
**Status:** [ ] Not Started

## Overview

Five phases. Phase 1 lays down models + repo for chat messages and pending suggestions. Phase 2 adds streaming support to `llm_client` and writes the chat service (prompt builder, suggestion parser). Phase 3 wires the SSE endpoint + chat UI. Phase 4 implements `apply_suggestion` and the apply/reject routes with versioning. Phase 5 polishes the UX (entry point on tailored page, history truncation, stale notice, cost surfacing) and adds end-to-end flow tests.

---

## Phase 1: Models + chat repo

### Tasks

- [ ] 1.1: Add Pydantic models in `backend/models.py`: `ChatMessage` (id, application_id, role, content, timestamp, input_tokens, output_tokens, cost_cents, model), `Suggestion` (id, application_id, message_id, suggestion_type, target_section, current_value, proposed_value, rationale, status, created_at). Add `SUGGESTION_TYPES = ("rephrase_bullet", "replace_summary", "swap_skill")` and `SUGGESTION_STATUSES = ("pending", "applied", "rejected")` constants.
- [ ] 1.2: Create `backend/services/chat_repo.py` with: `create_message(conn, *, application_id, role, content, model="", input_tokens=0, output_tokens=0, cost_cents=0.0) -> int`; `list_messages(conn, application_id) -> list[ChatMessage]` (chronological); `get_message(conn, message_id) -> ChatMessage | None`; `create_suggestion(conn, *, application_id, message_id, **fields) -> int`; `list_pending_suggestions(conn, application_id) -> list[Suggestion]`; `get_suggestion(conn, suggestion_id) -> Suggestion | None`; `set_suggestion_status(conn, suggestion_id, status) -> bool` (validates against SUGGESTION_STATUSES).
- [ ] 1.3: Tests in `tests/test_chat_repo.py`: round-trip create/list messages chronologically; FK cascade on application delete; create_suggestion + list_pending excludes applied/rejected; set_suggestion_status validates; unknown ids return None.

### Verification

- [ ] `pytest tests/test_chat_repo.py` passes
- [ ] Full suite green

---

## Phase 2: Streaming LLM client + chat service

### Tasks

- [ ] 2.1: Extend `llm_client.py` with `stream_llm(system, messages, *, model, operation, application_id, db_conn, max_tokens, use_cache) -> Iterator[StreamEvent]`. Yields `StreamEvent(type="token", text="...")` per text delta and `StreamEvent(type="done", usage_info=...)` once. Logs usage to `usage_log` on completion. Translates SDK errors to typed `LLMError` subclasses (same as `call_llm`).
- [ ] 2.2: Add `backend/prompts/chat.py::CHAT_SYSTEM` — instructs Claude to: act as a resume editor, ground all suggestions in the source profile (NEVER fabricate, same rules as TAILOR_SYSTEM but condensed), respond conversationally, and end with an optional `<<<SUGGESTIONS>>> [...] <<<END>>>` JSON block when proposing concrete edits. Schema for each suggestion: `{type, target, proposed, rationale}`.
- [ ] 2.3: Create `backend/services/chat_service.py` with `build_chat_context(conn, application, tailored_row, history, new_user_message) -> tuple[str, list[dict]]` — returns `(system_prompt, messages)` ready for `stream_llm`. System prompt contains the JD + tailored resume snapshot. Messages = last 20 history entries + new user message. (Profile not included; chat operates on the tailored snapshot.)
- [ ] 2.4: Add `parse_suggestions(assistant_text) -> list[dict]` — extracts the `<<<SUGGESTIONS>>>...<<<END>>>` block, parses JSON, validates each item has `type ∈ SUGGESTION_TYPES` + `target` + `proposed`. Skips malformed entries silently (logs but doesn't raise). Returns the parsed list (possibly empty).
- [ ] 2.5: Tests in `tests/test_chat_service.py`: mocked `stream_llm` yields token chunks then a final usage event; `build_chat_context` includes JD + tailored snapshot in system prompt + truncates history to 20; `parse_suggestions` handles missing block (returns []), malformed JSON (returns []), valid JSON (returns parsed), filters out invalid types.

### Verification

- [ ] `pytest tests/test_chat_service.py` passes
- [ ] Full suite green

---

## Phase 3: SSE endpoint + chat UI

### Tasks

- [ ] 3.1: Add `POST /applications/{app_id}/chat` route in `routes/applications.py` (or new `routes/chat.py`). Accepts form field `message` (str). Validates application exists + a tailored resume exists. Persists user message via `chat_repo.create_message`. Returns 303 redirect to `/applications/{app_id}/chat?streaming=<message_id>` so the browser then GETs the chat page which auto-opens an SSE connection for the new message.
- [ ] 3.2: Add `GET /applications/{app_id}/chat/stream/{message_id}` SSE route. Returns `StreamingResponse(generator(), media_type="text/event-stream")`. The generator: builds context, calls `stream_llm`, yields `event: token\ndata: <chunk>\n\n` per text delta. On stream end: persists the assistant message + parsed suggestions to DB, then yields `event: done\ndata: {message_id, suggestion_count}\n\n`. On error: yields `event: error\ndata: <message>\n\n` and returns.
- [ ] 3.3: Add `GET /applications/{app_id}/chat` route renders `applications/chat.html` with full message history + pending suggestions panel + input form. If `?streaming=N` is present, the template includes an SSE container that auto-connects to the stream endpoint for that message.
- [ ] 3.4: Create `backend/templates/applications/chat.html` — layout shell, message bubbles (user vs assistant styled), suggestion cards with apply/reject forms, input textarea + submit. Includes HTMX SSE extension via CDN script tag and a tiny inline JS (~30 lines) handling: live-append tokens to the streaming bubble; on `done`, fetch suggestions panel via HTMX swap; on `error`, show inline alert.
- [ ] 3.5: Add CSS in `style.css` for chat layout: message-list, message bubbles (`.msg-user`, `.msg-assistant`), `.suggestion-card`, `.chat-input`, the streaming-cursor blink animation while waiting.

### Verification

- [ ] Manual: open chat page, send a message, watch the response stream in token-by-token, see suggestion cards appear at the end
- [ ] No automated test for SSE in this phase (covered in Phase 5 with mocked stream)

---

## Phase 4: Suggestion apply/reject + versioned tailored save

### Tasks

- [ ] 4.1: Create `backend/services/suggestion_apply.py` with pure function `apply_suggestion(tailored: TailoredResume, suggestion: Suggestion) -> TailoredResume`. Dispatches by `suggestion_type`:
  - `rephrase_bullet`: parse `experience[i].bullets[j]` index, replace `text`, preserve `source_bullet_id`
  - `replace_summary`: set `summary`
  - `swap_skill`: replace `skills[i]`
  Raises `ValueError` for unknown type or out-of-range index.
- [ ] 4.2: Add `POST /applications/{app_id}/suggestions/{sid}/apply` route. Loads suggestion + latest tailored row + application; calls `apply_suggestion`; runs validator on the new content; calls `tailored_repo.create_tailored(..., source="chat-edit", parent_version=current.version)`; sets suggestion `status='applied'`; 303 redirect to `/applications/{app_id}/chat`.
- [ ] 4.3: Add `POST /applications/{app_id}/suggestions/{sid}/reject` route. Sets suggestion `status='rejected'`; 303 redirect to `/applications/{app_id}/chat`.
- [ ] 4.4: Tests in `tests/test_suggestion_apply.py` (unit): `apply_suggestion` for each of the 3 types — happy path + out-of-range index → ValueError + unknown type → ValueError + `source_bullet_id` preserved on rephrase.
- [ ] 4.5: Tests in `tests/test_chat_flow.py::TestApplyReject`: apply route creates a new tailored row with `parent_version` + `source='chat-edit'` + suggestion marked applied; reject route marks suggestion rejected without touching tailored rows; suggestions for unknown application 303-redirect.

### Verification

- [ ] `pytest tests/test_suggestion_apply.py tests/test_chat_flow.py::TestApplyReject` passes
- [ ] Full suite green

---

## Phase 5: UX polish + end-to-end flow tests

### Tasks

- [ ] 5.1: Add "Discuss this resume" button to `applications/tailored.html` near the regenerate button → links to `/applications/{id}/chat`.
- [ ] 5.2: On chat.html, show a stale notice when `tailored_row.is_stale` (mirrors the existing pattern from tailored.html). Show a "Resume updated to v{N}" success banner after an apply (read from `?applied=N` query param).
- [ ] 5.3: Surface the cumulative chat cost on the chat page (sum of `cost_cents` from this application's chat_messages).
- [ ] 5.4: End-to-end flow test in `tests/test_chat_flow.py` (TestClient + mocked `stream_llm`): create app → generate tailored → POST chat message → assert user message persisted + redirect to streaming URL; mock stream emits prose + suggestion block → GET stream URL collects events → assistant message persisted, 1 suggestion in pending list. Apply suggestion → new tailored row, suggestion applied. GET chat page renders both messages + suggestion is no longer in pending.
- [ ] 5.5: Test the suggestion parser against several real-world-shaped responses (in `tests/test_chat_service.py`): no suggestions block, malformed JSON, mixed valid + invalid types, extra prose after the END marker.

### Verification

- [ ] `pytest tests/test_chat_flow.py` passes
- [ ] Full suite green
- [ ] Manual end-to-end: open chat, send "make my Python bullet punchier" → see streamed response → apply the suggestion → see new version on tailored page

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] `pytest tests/` green
- [ ] Manual end-to-end: tailored resume → chat → streamed response with suggestions → apply → new versioned tailored row → exported DOCX reflects the change
- [ ] No regression in `resume-tailor_20260427`, `app-workspace_20260427`, or `export_20260428` flows
- [ ] No new dependencies (Anthropic SDK already supports streaming; HTMX SSE extension is a CDN script tag)
- [ ] Costs logged for chat operations + visible on the chat page

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
