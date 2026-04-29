# Implementation Plan: Iteration loops — version history, suggestion diffs, validator actions

**Track ID:** `iteration-loops_20260430`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-30
**Status:** [ ] Not Started

## Overview

Three independent phases. Each is shippable on its own — phase order matches impact (history closes the apply loop, then diffs make Apply safe, then validator actions feed the loop). No schema changes, no new dependencies, no new LLM calls.

---

## Phase 1: Tailored resume version history + revert

### Tasks

- [ ] 1.1: Extract a shared helper `_parse_target_index(target: str, kind: str) -> tuple[int, ...]` from `suggestion_apply.py` (used by Phase 2 too). Returns `(i,)` for `swap_skill`, `(i, j)` for `rephrase_bullet`, `()` for `summary`. Raises `ValueError` on bad format or non-numeric index. Update `apply_suggestion` to use it.
- [ ] 1.2: Add `GET /applications/{app_id}/tailored/versions` route in `routes/applications.py`. Loads the application + `tailored_repo.list_for_application` (already returns rows ordered newest-first). Renders new template `applications/versions.html`. Returns 404 if app missing.
- [ ] 1.3: Create `backend/templates/applications/versions.html` — table with columns: version #, source label, created_at, validation summary ("✓ clean" / "N errors" / "N warnings"), actions (View / Revert). The latest row is highlighted and shows no Revert button. Source label maps `generated → "Generated"`, `chat-edit → "Chat edit"`, `reverted → "Reverted from v{parent_version}"`, fallback to raw value.
- [ ] 1.4: Extend `tailored_repo._row_to_tailored` to expose `source` and `parent_version` fields on `TailoredResumeRow` (add to model). Update SELECT statements in `get_latest_for_application`, `list_for_application`, `get_tailored` to include those columns.
- [ ] 1.5: Add `GET /applications/{app_id}/tailored/{tailored_id}` route. Loads that specific row via `tailored_repo.get_tailored`, validates it belongs to the app, renders `applications/tailored.html` with that row instead of the latest. The template gets a `viewing_old=True` flag and shows a banner "Viewing v{N} — newer version exists" when not the latest.
- [ ] 1.6: Add `POST /applications/{app_id}/tailored/{tailored_id}/revert` route. Loads the target row, creates a new tailored row by copying its `content`/`validation`, with `source="reverted"`, `parent_version=<target.version>`, current `profile_hash`, `cost_cents=0`. 303 redirect to `/applications/{app_id}/tailored`.
- [ ] 1.7: Add "Versions ({count})" link to `applications/tailored.html` near the Regenerate / Discuss buttons. Count comes from a new `version_count` field in the show context.
- [ ] 1.8: Tests in `tests/test_versions_flow.py`: versions page renders all rows newest-first, reverting an old version creates a new latest with `source="reverted"` + `parent_version=<old>`, viewing an old version renders content from that row not the latest, view-old shows the "newer version exists" banner, unknown tailored_id 404s, revert redirects to /tailored.

### Verification

- [ ] `pytest tests/test_versions_flow.py` passes
- [ ] Full suite green
- [ ] Manual: generate → chat-edit → revert → confirm v1 content is now latest

---

## Phase 2: Diff preview on suggestion cards

### Tasks

- [ ] 2.1: Add `compute_current_value(tailored: TailoredResume, suggestion_type: str, target: str) -> str` helper in `chat_service.py`. Uses `_parse_target_index` from Phase 1 task 1.1. Returns the current text/skill being replaced, or `""` if out of range (no exception — soft fail; the diff will just look like a pure addition).
- [ ] 2.2: In the SSE stream route `routes/chat.py`, when persisting parsed suggestions, populate `current_value` via the helper. Pass the latest `tailored_row.content` (already loaded for context).
- [ ] 2.3: Add `word_diff(old: str, new: str) -> str` helper in `backend/services/text_diff.py`. Uses `difflib.ndiff` on whitespace-tokenized strings; emits an HTML-safe string with `<del class="diff-del">` and `<ins class="diff-ins">` spans for changed words and `<span>` for unchanged. Auto-escape via `markupsafe.escape` on each token before wrapping.
- [ ] 2.4: Update `applications/chat.html` suggestion card template: for `replace_summary` and `rephrase_bullet`, render `{{ word_diff(s.current_value, s.proposed_value) | safe }}` in a new `.suggestion-diff` block (replacing the plain `.suggestion-proposed`). For `swap_skill`, render `{{ s.current_value }} → {{ s.proposed_value }}` as a chip pair. If `current_value` is empty (older suggestions, or computed as empty), fall back to plain proposed-only rendering.
- [ ] 2.5: Add CSS rules in `style.css` for `.diff-ins` (green background tint, no underline) and `.diff-del` (red background tint, line-through).
- [ ] 2.6: Tests in `tests/test_text_diff.py` (unit): word_diff identifies single-word change, multi-word insert/delete, no change → all unchanged tokens, HTML-escapes user text (test with `<script>` in input).
- [ ] 2.7: Tests in `tests/test_chat_flow.py::TestSuggestionDiff`: stream test with mocked `stream_llm` populates `current_value` correctly for each suggestion type, chat page renders diff markup for new suggestions, chat page falls back gracefully for suggestions without current_value.

### Verification

- [ ] `pytest tests/test_text_diff.py tests/test_chat_flow.py::TestSuggestionDiff` passes
- [ ] Full suite green
- [ ] Manual: chat-edit a bullet, see strikethrough on the dropped phrase + green on the added phrase

---

## Phase 3: Inline fix-it actions on validator flags

### Tasks

- [ ] 3.1: Add `build_prefill_message(issue: ValidationIssue) -> str` helper in `chat_service.py`. Dispatches by `issue.category`:
  - `unverified_metric` → "The number in '{location}' isn't grounded in my source profile. Propose a rephrasing without that figure."
  - `unknown_skill` → "The skill at '{location}' isn't in my profile's skills list. Propose swapping it for a real skill from my list."
  - `unknown_company` / `unknown_title` / `unknown_project` → "'{location}' references something not in my profile ({issue.message}). Propose a fix grounded in real content."
  - `bullet_reference` → "The bullet at '{location}' has a stale source reference. Propose a rephrasing tied to my actual source bullets."
  - default → "Address the validation issue at '{location}': {issue.message}"
- [ ] 3.2: Update `applications/tailored.html` validation list: each `<li>` gets a "Discuss this" link with `href="/applications/{{ application.id }}/chat?prefill={{ build_prefill_message(issue) | urlencode }}"`. Expose `build_prefill_message` to the Jinja env via `templates.env.globals["build_prefill_message"] = build_prefill_message` in `templating.py` (or pass as a context var per-request — pick whichever matches the existing pattern).
- [ ] 3.3: Update `GET /{app_id}/chat` route in `routes/chat.py` to read `prefill = request.query_params.get("prefill", "")` (capped at 500 chars to prevent abuse) and pass it to the chat template.
- [ ] 3.4: Update `applications/chat.html` textarea: render `{{ prefill or '' }}` as the textarea content. If `prefill` is non-empty and history is empty, focus the textarea on page load via existing inline JS.
- [ ] 3.5: Add CSS for `.discuss-issue-link` (small inline link styled like a button, sits to the right of the issue message).
- [ ] 3.6: Tests in `tests/test_chat_service.py::TestBuildPrefillMessage`: each category produces an expected message containing the location, default fallback handles unknown category, message is non-empty.
- [ ] 3.7: Tests in `tests/test_tailored_flow.py::TestValidatorActions`: tailored page with a fabricated issue renders a "Discuss this" link with a `prefill=` query string, link points to chat page, link is properly URL-encoded (test with a quote in the issue message).
- [ ] 3.8: Tests in `tests/test_chat_flow.py::TestPrefill`: chat page with `?prefill=foo` renders "foo" in the textarea, prefill longer than 500 chars is truncated, prefill is HTML-escaped (no XSS).

### Verification

- [ ] `pytest tests/test_chat_service.py::TestBuildPrefillMessage tests/test_tailored_flow.py::TestValidatorActions tests/test_chat_flow.py::TestPrefill` passes
- [ ] Full suite green
- [ ] Manual: tailored resume with a fabricated metric → click "Discuss this" → chat opens with prefilled message → send → Claude proposes a rephrasing → Apply → validator now clean

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] `pytest tests/` green
- [ ] Manual end-to-end: regenerate → chat-edit → see diff → revert → versions page shows all three rows with correct sources → click validator flag → fix via chat
- [ ] No regression in `chat-stream_20260429`, `resume-tailor_20260427`, or `export_20260428` flows
- [ ] No new dependencies (difflib is stdlib; markupsafe ships with Jinja2)

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
