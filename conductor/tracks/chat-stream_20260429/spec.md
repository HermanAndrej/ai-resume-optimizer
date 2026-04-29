# Specification: Chat with Streaming — Suggestion Apply/Reject

**Track ID:** `chat-stream_20260429`
**Type:** Feature
**Created:** 2026-04-29
**Status:** Draft

## Summary

Per-application chat with the tailored resume as context. Claude responds with streamed prose plus optional structured suggestions (rephrase a bullet, swap a skill, replace the summary). Each suggestion appears as a card with Apply / Reject buttons. Applying a suggestion mutates the latest tailored resume in-memory, re-runs the validator, and saves a new versioned row preserving lineage to the prior version.

## Context

This is build-order step #9 from `workflow.md`, the last MVP feature. With tailored resumes generated and validated (`resume-tailor_20260427`) and exported (`export_20260428`), the user now needs an iteration loop: "this bullet feels weak — can we punchier-up the metric?" or "swap Kubernetes for the AWS one — that's more relevant to this JD." Without chat, the only way to iterate is to regenerate from scratch, which discards everything good in the current draft.

The schema is already in place from `scaffolding-db_20260423`:

- `chat_messages (id, application_id, role, content, timestamp, input_tokens, output_tokens, cost_cents, model)`
- `pending_suggestions (id, application_id, message_id, suggestion_type, target_section, current_value, proposed_value, rationale, status, created_at)`

`tech-stack.md` constrains the approach: streaming enabled for chat only, Sonnet 4.6 model, HTMX for the dynamic UI (no JS framework). The HTMX `sse` extension is the cleanest path — a single small script tag and `hx-ext="sse"` on the chat container.

## User Story

As a tech job applicant iterating on a tailored resume, I want to chat with the assistant about specific lines / phrasing / metric framing, and have the assistant propose targeted edits I can accept or reject one-by-one, so that I can refine the resume conversationally without losing my place.

## Acceptance Criteria

- [ ] On the tailored-resume page there is a "Discuss this resume" link/button leading to `/applications/{id}/chat`
- [ ] `/applications/{id}/chat` renders the full chat history for this application + an input box
- [ ] Submitting a message persists the user message to `chat_messages`, then streams the assistant response token-by-token to the browser via SSE
- [ ] The streaming response uses Anthropic SDK streaming + Sonnet 4.6 + prompt caching for the system prompt and resume snapshot
- [ ] At stream end the assistant message is persisted with cost/token metadata, and any structured suggestions in the response are parsed and saved as `pending_suggestions` rows
- [ ] Each pending suggestion appears as a card with Apply / Reject buttons; clicking either updates `pending_suggestions.status` and refreshes the UI
- [ ] Apply: mutates the latest tailored resume content in-memory based on the suggestion's `suggestion_type` + `target_section`, re-runs `validate_tailored_resume`, saves a new `tailored_resumes` row with `parent_version` set, and `source = "chat-edit"`
- [ ] After Apply, the chat page shows a "Resume updated to v{N}" notice with a link to `/applications/{id}/tailored`
- [ ] Reject: marks the suggestion `status='rejected'` and removes the card; resume is unchanged
- [ ] If profile changes after the chat began, the chat page shows a stale notice (existing pattern)
- [ ] All chat costs are logged to `usage_log` and aggregated into the application's total
- [ ] All flows have tests with mocked streaming (no real Anthropic calls)

## Dependencies

Depends on existing code:

- `tailored_repo.create_tailored / get_latest_for_application` (resume-tailor)
- `resume_validator.validate_tailored_resume / build_source_index` (resume-tailor)
- `application_repo.get_application` (app-workspace)
- `llm_client` (will be extended to support streaming)
- `chat_messages`, `pending_suggestions` schema (V1 — already present)

## Out of Scope

- Multi-turn tool use / function calling (we use plain text + a fenced JSON block for suggestions)
- Edits to the source profile from chat (chat operates on the tailored resume only; profile edits remain in `/profile/*`)
- Suggestion preview/diff before Apply (Apply commits immediately; user can regenerate or revert via the version list — versioning UI is its own future track)
- Multi-suggestion bulk apply / "apply all"
- Branching conversation threads — the chat is a flat per-application history
- Voice input, file attachments, code execution
- Real-time collaborative editing
- Cancellation mid-stream (let the stream finish; cost is logged either way)

## Technical Notes

### Suggestion shape

In v1 we support three suggestion types — covering the most common iteration moves:

| `suggestion_type` | `target_section` example | `proposed_value` example |
|---|---|---|
| `rephrase_bullet` | `experience[0].bullets[2]` | `"Cut p99 latency 40% by adding a Redis cache layer"` |
| `replace_summary` | `summary` | `"Backend engineer with 8 years of Python, focused on API performance and cost reduction."` |
| `swap_skill` | `skills[3]` | `"Kubernetes"` |

Suggestion parsing: the assistant emits free prose followed by an optional fenced block:

```
<<<SUGGESTIONS>>>
[
  {"type": "rephrase_bullet", "target": "experience[0].bullets[2]", "proposed": "...", "rationale": "..."},
  {"type": "swap_skill", "target": "skills[3]", "proposed": "Kubernetes", "rationale": "JD requires container orchestration"}
]
<<<END>>>
```

The block is parsed AFTER the stream completes (we render the prose live; suggestion cards appear once the stream finishes).

### Streaming via SSE

- New endpoint `GET /applications/{id}/chat/stream?message_id=N` returns `StreamingResponse(media_type="text/event-stream")`
- The Anthropic SDK's streaming iterator yields content blocks; we re-emit each text delta as `event: token\ndata: {chunk}\n\n`
- The HTMX `sse` extension on the chat container handles message append; a small inline script (~20 lines) finalizes the message + reloads suggestions on `event: done`
- HTMX SSE extension via CDN: `<script src="https://unpkg.com/htmx.org@1.9.12/dist/ext/sse.js"></script>`

### Apply mutation logic

For each suggestion type, a small pure function `apply_suggestion(tailored, suggestion) -> TailoredResume`:

- `rephrase_bullet` — parse the location index, replace `tailored.experience[i].bullets[j].text`. Set `source_bullet_id` from the original (so validator's bullet-ref check still passes). Return new TailoredResume.
- `replace_summary` — set `tailored.summary = proposed`.
- `swap_skill` — replace `tailored.skills[i]` with proposed.

Then re-run validator → save new tailored row with `parent_version = current.version`, `source = "chat-edit"`.

### Cost tracking

Streaming responses still report final usage in the SDK's MessageDeltaEvent. We log to `usage_log` once on stream completion, with `operation = "chat_message"`. Same prompt-caching pattern as the rest of the app.

### History truncation

If a chat exceeds ~20 messages we keep only the last 20 in the conversation context (older messages remain visible in the UI, just not sent to the model). Avoids unbounded cost growth on long chats. v1 ceiling is generous; we can tune later.

---

_Generated by Conductor. Review and edit as needed._
