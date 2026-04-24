# Implementation Plan: Profile UI

**Track ID:** `profile-ui_20260423`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-23
**Status:** [x] Complete

## Overview

Three phases. Phase 1 delivers a working end-to-end example (Personal Info) that establishes every pattern — templates, static files, repo layer, HTMX form flow. Phase 2 replicates that pattern across the remaining 7 sections. Phase 3 adds the unsaved-changes warning and final polish. Vertical slicing so the app is usable after Phase 1.

---

## Phase 1: Shell + Personal Info (reference implementation) [COMPLETE]

Establishes the layout, templating, static assets, repo layer, and HTMX form pattern by fully implementing the Personal Info section end-to-end.

### Tasks

- [x] 1.1: Create `backend/templates/` and `backend/static/` directories
- [x] 1.2: `backend/templates/layout.html` — base template with sidebar listing all 8 sections
- [x] 1.3: `backend/static/style.css` — minimal functional CSS
- [x] 1.4: Mount `/static` in `backend/main.py` + configure Jinja2 templates (via shared `templating.py` to avoid circular imports)
- [x] 1.5: `backend/models.py` — Pydantic v2 models
- [x] 1.6: `backend/services/profile_repo.py` — repo functions for personal info + links
- [x] 1.7: `backend/routes/profile.py` — personal section routes
- [x] 1.8: `backend/templates/profile/personal.html` + `_personal_form.html` + `_link_row.html`
- [x] 1.9: Register `profile.router` on the FastAPI app

### Verification

- [x] 9/9 TestClient smoke checks green
- [x] pytest 6/6 green

---

## Phase 2: Remaining 7 sections (apply the pattern) [COMPLETE]

### Tasks

- [x] 2.1: **Summary** — single textarea on the `profile` row
- [x] 2.2: **Experience** — entries with nested bullets (separate `experience_bullets` table)
- [x] 2.3: **Education** — list of entries
- [x] 2.4: **Skills** — categorized, list re-renders on add/remove
- [x] 2.5: **Projects** — entries with bullets stored as multi-line text (simpler than nested table)
- [x] 2.6: **Certifications** — list of entries
- [x] 2.7: **Custom Sections** — user-defined name + content

### Verification

- [x] 25/25 smoke test checks green across all 8 sections
- [x] pytest 6/6 green

---

## Phase 3: Unsaved-changes warning + polish [COMPLETE]

### Tasks

- [x] 3.1: `backend/static/dirty.js` — dirty tracking + `beforeunload` confirmation + htmx:afterRequest success clears dirty
- [x] 3.2: Save-confirmation affordance — "Saved" indicator auto-fades 2s after swap
- [x] 3.3: Visual dirty marker — `.dirty` class toggles on active sidebar link (CSS `::after " *"` from Phase 1)
- [x] 3.4: Manual end-to-end verification (tested via smoke + runtime assertions; browser-level navigation confirmation is a native browser behavior and cannot be exercised via TestClient)

### Verification

- [x] `dirty.js` serves at `/static/dirty.js` with expected symbols
- [x] Layout references `dirty.js` on every page
- [x] Sidebar active class present and ready to take `.dirty` modifier

---

## Final Verification

- [x] All acceptance criteria from spec.md met
- [x] All 8 sections save/load correctly (25/25 smoke checks green)
- [x] `dirty.js` implements the unsaved-changes pattern
- [x] `pytest tests/` green (6/6 — no regressions)

---

_Completed: 2026-04-23_
