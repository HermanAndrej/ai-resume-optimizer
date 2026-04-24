# Implementation Plan: Profile UI

**Track ID:** `profile-ui_20260423`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-23
**Status:** [~] In Progress

## Overview

Three phases. Phase 1 delivers a working end-to-end example (Personal Info) that establishes every pattern — templates, static files, repo layer, HTMX form flow. Phase 2 replicates that pattern across the remaining 7 sections. Phase 3 adds the unsaved-changes warning and final polish. Vertical slicing so the app is usable after Phase 1.

---

## Phase 1: Shell + Personal Info (reference implementation)

Establishes the layout, templating, static assets, repo layer, and HTMX form pattern by fully implementing the Personal Info section end-to-end.

### Tasks

- [x] 1.1: Create `backend/templates/` and `backend/static/` directories
- [x] 1.2: `backend/templates/layout.html` — base template with sidebar listing all 8 sections (active section highlighted) and a content slot
- [x] 1.3: `backend/static/style.css` — minimal functional CSS (sidebar, forms, list rows, save button, error/saved states)
- [x] 1.4: Mount `/static` in `backend/main.py` and configure Jinja2 templates
- [x] 1.5: `backend/models.py` — Pydantic v2 models `PersonalInfo`, `ProfileLink` and any container types
- [x] 1.6: `backend/services/profile_repo.py` — `get_personal_info()`, `save_personal_info()`, `list_links()`, `add_link()`, `delete_link()`; list sync via delete-all-then-insert where needed
- [x] 1.7: `backend/routes/profile.py` — `GET /`, `GET /profile/personal`, `POST /profile/personal`, `POST /profile/personal/links` (add), `DELETE /profile/personal/links/{id}` (remove)
- [x] 1.8: `backend/templates/profile/personal.html` + `_link_row.html` — form + link list + HTMX add/remove; inline validation errors
- [x] 1.9: Register `profile.router` on the FastAPI app

### Verification

- [x] Smoke test via TestClient: GET / redirects, GET /profile/personal renders form + sidebar, POST saves, reload persists, invalid email surfaces error, add/remove link works, /static/style.css 200, /health still works
- [x] Full pytest suite still green (6/6)

---

## Phase 2: Remaining 7 sections (apply the pattern)

Each section below reuses Phase 1's pattern: Pydantic model → repo functions → route handlers → Jinja2 template.

### Tasks

- [ ] 2.1: **Summary** — single textarea on the `profile` row
- [ ] 2.2: **Experience** — entries with nested bullets (most complex; establishes nested-list patterns)
- [ ] 2.3: **Education** — list of entries
- [ ] 2.4: **Skills** — categorized (group by `category`, add skill to category, remove skill)
- [ ] 2.5: **Projects** — entries with bullets (reuses Experience pattern)
- [ ] 2.6: **Certifications** — list of entries
- [ ] 2.7: **Custom Sections** — user-defined name + content

### Verification

- [ ] Every section renders, saves, and reloads cleanly
- [ ] Experience + Projects: add/remove bullets inside an entry works
- [ ] Skills: adding a skill under a new category creates the category implicitly

---

## Phase 3: Unsaved-changes warning + polish

Cross-cutting client-side behavior and final UX affordances.

### Tasks

- [ ] 3.1: `backend/static/dirty.js` — marks page dirty on any `input`/`change` in the main form; sets `window.onbeforeunload` to show the browser's native confirmation; clears dirty flag on successful `htmx:afterRequest`
- [ ] 3.2: Save-confirmation affordance — brief "Saved" inline indicator after successful save (fades on next edit)
- [ ] 3.3: Visual dirty marker in the sidebar item of the currently-edited section (e.g., a `*`)
- [ ] 3.4: Manual end-to-end: edit each of the 8 sections, attempt navigation unsaved, save, confirm indicators behave correctly

### Verification

- [ ] Edit a field → attempt to navigate away → confirmation prompt shown
- [ ] Save → navigate → no prompt
- [ ] Close browser tab with unsaved changes → prompt shown

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] All 8 sections save/load correctly with no manual DB intervention
- [ ] No console errors in browser
- [ ] `pytest tests/` still green (no regressions in migration/paths tests)

---

_Tasks will be marked [~] in progress and [x] complete during implementation._
