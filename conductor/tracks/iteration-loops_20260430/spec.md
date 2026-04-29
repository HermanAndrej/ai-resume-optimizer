# Specification: Iteration loops — version history, suggestion diffs, validator actions

**Track ID:** `iteration-loops_20260430`
**Type:** Feature
**Created:** 2026-04-30
**Status:** Draft

## Summary

Three small features that close iteration loops in the existing flows: (1) a version history page so users can see and revert tailored-resume edits, (2) current-vs-proposed diffs on suggestion cards before Apply, and (3) "Discuss this" links on validator flags so warnings become actionable instead of passive.

## Context

After `chat-stream_20260429` shipped, three rough edges became obvious:

- **Apply creates new versions with no way to see them.** `tailored_repo` already stores `source` and `parent_version` on each row, and applying a chat suggestion creates a new row with `source="chat-edit"`. But the UI only ever loads `get_latest_for_application`, so users can't view or revert prior versions. If a chat-edit makes the resume worse, the only recovery is to regenerate from scratch (losing other good edits).
- **Suggestion Apply is blind.** Cards show `proposed_value` + `rationale` but not the current text being replaced. A "rephrase_bullet" suggestion that quietly drops a metric looks identical to one that improves it. The `pending_suggestions.current_value` column already exists in the schema — we just never populate it.
- **Validator flags are passive.** When the validator flags `unverified_metric` or `unknown_skill`, the user sees a warning but has no path to action. They'd have to manually open chat, describe the issue, and hope Claude proposes the right fix. A "Discuss this" link that pre-fills a chat message turns the warning panel into actionable items, reusing the existing chat-edit + Apply infrastructure.

All three improvements ride on existing primitives (tailored versions, suggestion cards, validator output). No new LLM calls, no schema changes, no new dependencies.

## User Story

As a candidate iterating on a tailored resume, I want to see prior versions and revert bad edits, see what each suggestion will replace before I Apply it, and click "Discuss" on a validator warning to get a grounded fix — so that I can iterate confidently without being stuck with bad LLM output or having to manually phrase fix-up requests.

## Acceptance Criteria

### Version history
- [ ] On the tailored-resume page, a "Versions" link/badge shows the count of stored versions (e.g. "Versions (3)")
- [ ] Clicking it opens `/applications/{id}/tailored/versions` listing every row from `tailored_resumes`, newest first
- [ ] Each row shows: version #, source label ("Generated" / "Chat edit" / "Reverted from v{N}"), created_at, validation summary (clean / N errors / N warnings), and a link to view that exact version
- [ ] Each non-latest row has a "Revert to this version" button that creates a new tailored row by copying the old one (`source="reverted"`, `parent_version=<old_version>`)
- [ ] Reverting redirects to `/applications/{id}/tailored` showing the new latest

### Suggestion diff preview
- [ ] When the SSE stream persists a suggestion, `current_value` is populated by reading the relevant target from the latest tailored content
- [ ] Suggestion cards render `current_value` and `proposed_value` side-by-side or stacked (current with strikethrough, proposed in green tint)
- [ ] For `replace_summary` (long text), a word-level inline diff highlights additions and deletions
- [ ] For `swap_skill` (single token), the chip-style swap is visually obvious
- [ ] Existing pending suggestions in DB without `current_value` still render — they just show only the proposed value (no diff)

### Validator actions
- [ ] Each validation issue on the tailored page has a "Discuss this" link
- [ ] Clicking it navigates to the chat page with `?prefill=<message>` query param
- [ ] The chat textarea is pre-filled with a message tailored to the issue category (e.g. "The metric 'saved $99M' on experience[0].bullets[0] isn't grounded in my profile — propose a rephrasing without that figure")
- [ ] Empty chat history + a prefill still shows the prefilled textarea ready to send (one click to fire)
- [ ] Prefill is escaped properly (no XSS via crafted issue messages)

## Dependencies

Depends on existing code:

- `tailored_repo.create_tailored / get_tailored / list_for_application` (resume-tailor)
- `pending_suggestions.current_value` column (V1 schema, never used until now)
- `chat_repo.create_suggestion` (chat-stream — extending to populate current_value)
- `validate_tailored_resume` output structure (resume-tailor)
- Chat page + suggestion card template (chat-stream)

## Out of Scope

- Branching version trees / merging two versions (revert is linear: copy old → new latest)
- Hard delete of versions (revert preserves history)
- Multi-suggestion bulk Apply or "Apply all"
- Inline editing of `proposed_value` before Apply (still all-or-nothing)
- Auto-fix without chat (every fix still routes through Claude → suggestion → Apply)
- Diff visualization beyond word-level (no character/syntax-aware diff)
- Validator-driven auto-suggestions (no proactive LLM calls; user must click Discuss)
- Per-version export buttons on the versions page (export still pulls latest only)

## Technical Notes

### Version history — revert pattern

`apply_suggestion` already establishes the lineage pattern (`source="chat-edit"`, `parent_version=N`). Revert reuses it: when the user reverts to v3, we call `tailored_repo.create_tailored` with `content=<copy of v3 content>`, `source="reverted"`, `parent_version=3`. This makes the revert visible in history and preserves the previously-latest version.

### current_value computation

The chat stream route already loads `tailored_row` to build context. After parsing suggestions, for each one:

- `replace_summary` → `current_value = tailored.summary`
- `rephrase_bullet` → parse `experience[i].bullets[j]` → `current_value = tailored.experience[i].bullets[j].text` (empty string if out of range; still persist so the user sees what's being added)
- `swap_skill` → parse `skills[i]` → `current_value = tailored.skills[i]`

Same regex parsers already used in `apply_suggestion.py` — refactor the index parsing into a shared helper.

### Diff rendering

For `replace_summary`, use `difflib.ndiff` server-side; render with `<ins>` and `<del>` tags. For `rephrase_bullet`, same approach. For `swap_skill`, no diff needed (chip → chip).

### Validator prefill messages

A small helper `build_prefill_message(issue) -> str` lives in `chat_service.py`, dispatched by `issue.category`:

- `unverified_metric` → "The number in '{location}' isn't in my source profile. Propose a rephrasing without that figure."
- `unknown_skill` → "The skill '{location}' isn't in my profile. Propose swapping it for a real skill from my list."
- `unknown_company` / `unknown_title` / `unknown_project` → "'{location}' references something not in my profile. Propose a fix grounded in real content."
- `bullet_reference` → "The bullet at '{location}' has a stale source reference. Propose a rephrasing tied to my actual experience."

The chat GET route reads `?prefill=` and passes it to the template; the textarea uses it as the default value.

---

_Generated by Conductor. Review and edit as needed._
