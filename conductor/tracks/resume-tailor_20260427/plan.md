# Implementation Plan: Tailored Resume Generation

**Track ID:** `resume-tailor_20260427`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-27
**Status:** [x] Complete

## Overview

Four phases. Phase 1 lays down schema + Pydantic models + repo. Phase 2 writes the no-fabrication generation service (LLM call → structured output). Phase 3 builds the deterministic validator that flags unverifiable claims. Phase 4 wires routes + UI on the application show page and adds a tailored-resume display page with the issues panel.

---

## Phase 1: Schema + models + repo

### Tasks

- [x] 1.1: Add `SCHEMA_V3` migration in `backend/db.py`. The `tailored_resumes` table already exists from V1 (id, application_id, version, content, generation_notes, source, parent_version, created_at) — V3 adds `validation_json`, `profile_snapshot_hash`, `model`, `cost_cents` columns plus index on `(application_id, created_at DESC)`. Register in `MIGRATIONS`.
- [x] 1.2: Add Pydantic models in `backend/models.py`: `TailoredBullet`, `TailoredExperience`, `TailoredResume`, `ValidationIssue`, `ValidationResult` (wraps `list[ValidationIssue]` + summary counts). Add `VALIDATION_SEVERITIES = ("error", "warning")`.
- [x] 1.3: Create `backend/services/tailored_repo.py` with: `create_tailored(conn, *, application_id, content, validation, profile_hash, model, cost_cents) -> int`; `get_latest_for_application(conn, application_id) -> TailoredResumeRow | None`; `list_for_application(conn, application_id) -> list[TailoredResumeRow]`; `get_tailored(conn, tailored_id)`; reuses `compute_profile_hash` for stale detection.
- [x] 1.4: Tests in `tests/test_tailored_repo.py`: migration creates table; create + get round-trips; multiple versions per application keep all rows in created_at DESC order; FK cascade on application delete.

### Verification

- [x] `pytest tests/test_tailored_repo.py` passes (10/10)
- [x] `pytest tests/test_migrations.py` confirms V3 idempotent (2/2)
- [x] Full suite green (151 passed, 1 skipped)

---

## Phase 2: Generation service (no-fabrication prompt)

### Tasks

- [x] 2.1: Create `backend/services/resume_tailor.py` with `build_profile_context(conn) -> dict` that produces a structured JSON view of the source profile (personal info, summary, experiences with bullet IDs, education, skills, projects, certifications). Bullet IDs come from the DB so the LLM can cite them.
- [x] 2.2: Add `TAILOR_SYSTEM` constant in `backend/prompts/resume_tailor.py` — 10 absolute rules forbidding fabrication of companies/titles/skills/metrics; instructs source_bullet_id citations; structured JSON output schema.
- [x] 2.3: Add `generate_tailored_resume(conn, jd_text, application_id) -> tuple[TailoredResume, str, dict]`. Calls `call_llm` with Sonnet 4.6, profile cached, parses + validates against `TailoredResume`. Returns (model, profile_hash, usage_info).
- [x] 2.4: Tests in `tests/test_resume_tailor.py` (11 tests): profile context with bullet IDs; prompt contains required no-fabrication phrases; generation happy path; LLM call kwargs assertion; invalid JSON / schema mismatch / LLMError propagation.

### Verification

- [x] `pytest tests/test_resume_tailor.py` passes (11/11)
- [x] Full suite green (162 passed, 1 skipped)

---

## Phase 3: Validation service

### Tasks

- [x] 3.1: Create `backend/services/resume_validator.py` with `build_source_index(conn) -> SourceIndex` — dataclass holding `companies`, `titles`, `skills`, `project_names` (lowercased sets), `bullet_texts_by_id` (dict), `all_source_text` (concatenated lowercase for numeric substring checks).
- [x] 3.2: Add `validate_tailored_resume(tailored, index) -> ValidationResult`. Walks tailored resume; emits errors for unknown company/title/project/bullet_ref and warnings for unknown_skill / unverified_metric.
- [x] 3.3: Add `extract_numeric_claims(text)` — regexes for percentages, currency (`$5K`, `$1.2M`), multipliers (`10x`), year ranges, integers ≥10 (single digits skipped to reduce noise). Per bullet, missing tokens → `warning/unverified_metric`.
- [x] 3.4: Tests in `tests/test_resume_validator.py` (24 tests): index building, numeric extraction (each pattern + dedupe + skip-single-digit), clean resume passes, fake company/title/project = error, fake skill = warning, valid/invalid source_bullet_id, fabricated metrics, case-insensitive matching.

### Verification

- [x] `pytest tests/test_resume_validator.py` passes (24/24)
- [x] Full suite green (186 passed, 1 skipped)

---

## Phase 4: Routes + UI

### Tasks

- [x] 4.1: Add `POST /applications/{app_id}/tailor` route in `routes/applications.py`: loads application, calls `generate_tailored_resume`, runs validator, persists via `tailored_repo.create_tailored`, 303-redirects to `/applications/{app_id}/tailored`. LLM errors → redirect to show page.
- [x] 4.2: Add `GET /applications/{app_id}/tailored` route: loads latest tailored row, builds `issues_by_loc` index, renders template; 404 via show.html if application not found; empty state if no tailored yet.
- [x] 4.3: Create `backend/templates/applications/tailored.html` — validation banner (error/warning/clean states), tailored summary, experience cards with bullets, skills chips, selected projects, version + cost meta, regenerate button.
- [x] 4.4: Add "Generate tailored resume" button + "View tailored resume" link in the score-header on `applications/show.html`.
- [x] 4.5: CSS in `style.css` for validation banner (3 swatches), tailored-section layout, experience cards, inline `[category]` flags with hover tooltip, score-actions row.
- [x] 4.6: 10 flow tests in `tests/test_tailored_flow.py`: tailor route happy path, unknown app + LLM error redirects, empty state, clean vs fabricated rendering, generate button on show page, version retention across regenerate, stale banner on profile change.

### Verification

- [x] `pytest tests/test_tailored_flow.py` passes (10/10)
- [x] Full suite green (196 passed, 1 skipped)

---

## Final Verification

- [x] All acceptance criteria from spec.md met
- [x] `pytest tests/` green (196 passed, 1 skipped)
- [x] Manual end-to-end: profile + JD → generate → validate → render with issues; regenerate produces a new row, old rows preserved
- [x] No regression in `compat-analysis_20260426` or `app-workspace_20260427` flows
- [x] System prompt visibly contains explicit no-fabrication rules (covered by `TestSystemPrompt` guardrail test)

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
