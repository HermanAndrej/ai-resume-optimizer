# Implementation Plan: Application Workspace

**Track ID:** `app-workspace_20260427`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-27
**Status:** [~] In Progress

## Overview

Four phases. Phase 1 is schema + repo plumbing (migration, new fields, helpers, stale detection). Phase 2 surfaces JD, metadata, and the stale banner on the show page. Phase 3 wires the edit / archive / re-analyze actions. Phase 4 polishes the list page (status badges + archived toggle).

---

## Phase 1: Schema + repo + analysis helper

### Tasks

- [x] 1.1: Add `SCHEMA_V2` migration in `backend/db.py` adding `status TEXT DEFAULT 'analyzed'`, `notes TEXT`, `source_url TEXT` columns to `applications`. Register in `MIGRATIONS` dict.
- [x] 1.2: Extend `Application` and `ApplicationSummary` models in `backend/models.py` with `status: str = "analyzed"`, `notes: str = ""`, `source_url: str = ""`, `is_stale: bool = False`, `updated_at: str = ""`. Add `STATUS_VALUES` constant.
- [x] 1.3: Extract reusable `run_analysis(db, jd_text) -> tuple[CompatibilityAnalysis, str, dict]` helper in `backend/services/compat_runner.py` that calls `flatten_profile`, `compute_overlap`, `score_compatibility`, computes profile_hash, and returns analysis + profile_hash + usage_info. Use it from POST /applications and the new re-analyze route.
- [x] 1.4: Extend `application_repo.py`: `compute_profile_hash(conn) -> str` (SHA-256 first 16 of flattened profile); `is_stale_for(conn, application_id) -> bool`; `update_metadata(conn, id, *, status, notes, source_url, jd) -> bool`; `set_archived(conn, id, archived: bool) -> bool`; `update_analysis(conn, id, analysis_json, profile_hash) -> bool` (also bumps `updated_at`); change `list_applications` to accept `include_archived: bool = False`; return new fields in `Application`/`ApplicationSummary`.
- [x] 1.5: Tests in `tests/test_application_repo.py` covering migration, new columns default values, all new repo functions, and `is_stale_for` (fresh when hash matches, stale when profile changes).

### Verification

- [ ] `pytest tests/test_application_repo.py` passes
- [ ] `pytest tests/test_migrations.py` still passes (V2 idempotent)
- [ ] Full suite green

---

## Phase 2: Show page enhancements

### Tasks

- [x] 2.1: Update `applications/show.html`: add a collapsed "Job Description" panel with `<details>` toggle showing the full saved JD; render status badge, notes (rendered as plain text), and source URL link near the header.
- [x] 2.2: Update `routes/applications.py::show_application` to populate `is_stale` (via `is_stale_for`) and pass to template.
- [x] 2.3: Add stale-analysis banner block in `show.html` that renders when `application.is_stale` is true, with a POST form to `/applications/{id}/reanalyze`.
- [x] 2.4: Add CSS in `style.css` for status badges (analyzed/applied/interviewing/rejected/offer color swatches), stale banner, JD panel.

### Verification

- [ ] Manual: existing applications still render; saved JD visible on expand; status badge shows "analyzed" by default
- [ ] Full suite green

---

## Phase 3: Edit, archive, re-analyze actions

### Tasks

- [ ] 3.1: Add edit form on `show.html` (HTMX-friendly but also works without): editable status `<select>`, notes `<textarea>`, source_url `<input>`, JD `<textarea>`. POSTs to `/applications/{id}/edit`.
- [ ] 3.2: Route `POST /applications/{id}/edit` in `routes/applications.py` — validates status against `STATUS_VALUES`, calls `update_metadata`, 303-redirects to /applications/{id}. Returns 422 with re-rendered form on validation error.
- [ ] 3.3: Route `POST /applications/{id}/archive` and `POST /applications/{id}/unarchive` — toggle the archived flag, 303-redirect (archive → /applications, unarchive → /applications/{id}).
- [ ] 3.4: Route `POST /applications/{id}/reanalyze` — calls `run_analysis`, then `update_analysis`, 303-redirects to /applications/{id} with the new analysis cost in the query string (so the show page can show "re-analysis cost").
- [ ] 3.5: Add archive button on show page (small, secondary styling); add unarchive link visible only when viewing an archived application.
- [ ] 3.6: Tests in `tests/test_applications_flow.py` for edit (happy path + invalid status), archive/unarchive flow, and reanalyze (mock LLM, assert analysis updated and hash refreshed).

### Verification

- [ ] `pytest tests/test_applications_flow.py` passes
- [ ] Full suite green
- [ ] Manual: edit → save → see updated values; archive → disappears from list; re-analyze → new score, stale banner gone

---

## Phase 4: List page polish

### Tasks

- [ ] 4.1: Update `applications/list.html` to show status badge column; add "Show archived" toggle (link with `?archived=1` query param).
- [ ] 4.2: Update `GET /applications` route to read `archived` query param and pass `include_archived` to `list_applications`.
- [ ] 4.3: Update `list_applications` summary rows to flag stale rows (small "stale" indicator) — compute hash once and reuse for all rows.
- [ ] 4.4: Tests for list filtering (active-only default, ?archived=1 shows archived) and stale indicator rendering.

### Verification

- [ ] `pytest tests/test_applications_flow.py` passes
- [ ] Full suite green
- [ ] Manual: archived toggle works; status badges visible; stale rows flagged

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] `pytest tests/` green
- [ ] Manual end-to-end: create → edit metadata → archive → unarchive → modify profile → see stale banner → re-analyze → score updates
- [ ] No regression in `compat-analysis_20260426` flows

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
