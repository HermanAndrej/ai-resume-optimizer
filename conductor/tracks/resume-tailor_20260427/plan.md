# Implementation Plan: Tailored Resume Generation

**Track ID:** `resume-tailor_20260427`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-27
**Status:** [~] In Progress

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

- [ ] 2.1: Create `backend/services/resume_tailor.py` with `build_profile_context(conn) -> dict` that produces a structured JSON view of the source profile (personal info, summary, experiences with bullet IDs, education, skills, projects, certifications). Bullet IDs come from the DB so the LLM can cite them.
- [ ] 2.2: Add `TAILOR_SYSTEM_PROMPT` constant — strict no-fabrication instructions: only use facts from the supplied profile; do not invent companies, titles, technologies, metrics, dates; you may reorder, omit, rephrase, and emphasize; for every tailored bullet, set `source_bullet_id` to the original bullet's id when one applies.
- [ ] 2.3: Add `generate_tailored_resume(conn, jd_text, application_id) -> tuple[TailoredResume, dict]`. Calls `call_llm` with Sonnet, structured-output schema = `TailoredResume`, profile cached as a separate user block (reuses `llm_client` cache plumbing). Returns parsed model + usage_info dict (cost, model, tokens).
- [ ] 2.4: Tests in `tests/test_resume_tailor.py` with mocked `call_llm`: profile context contains expected fields and bullet IDs; system prompt contains "never fabricate" / "do not invent" language; generation returns parsed `TailoredResume`; LLMError surfaces.

### Verification

- [ ] `pytest tests/test_resume_tailor.py` passes
- [ ] Full suite green

---

## Phase 3: Validation service

### Tasks

- [ ] 3.1: Create `backend/services/resume_validator.py` with `build_source_index(conn) -> SourceIndex` — a dataclass holding: `companies: set[str]`, `titles: set[str]`, `schools: set[str]`, `certs: set[str]`, `project_names: set[str]`, `skills: set[str]` (all lowercased+trimmed), `bullet_texts_by_id: dict[int, str]`, `all_bullet_text: str` (concatenated). Pulls from existing repos (experience, education, skills, projects, certifications).
- [ ] 3.2: Add `validate_tailored_resume(tailored: TailoredResume, index: SourceIndex) -> ValidationResult`. Walks the tailored resume:
  - Each `TailoredExperience.company` → must be in `index.companies` else `error/unknown_company`
  - Each `TailoredExperience.title` → must be in `index.titles` else `error/unknown_title`
  - Each `TailoredBullet.source_bullet_id` (if set) → must be in `bullet_texts_by_id` else `error/unknown_bullet_ref`
  - Each tailored skill → must be in `index.skills` else `warning/unknown_skill`
  - Each `selected_projects` entry → must be in `index.project_names` else `error/unknown_project`
- [ ] 3.3: Add `extract_numeric_claims(text: str) -> list[str]` (regex for `\d+%`, `\$\d+`, `\d+x`, year-ranges, integer counts ≥ 2). Per tailored bullet, every extracted token must appear in `index.all_bullet_text` (case-insensitive substring). Missing → `warning/unverified_metric` with bullet location.
- [ ] 3.4: Tests in `tests/test_resume_validator.py`: source index built from a fixture profile; happy-path tailored resume validates clean; injected fake company → error; fake skill → warning; fabricated number → warning; valid `source_bullet_id` passes; bad id → error.

### Verification

- [ ] `pytest tests/test_resume_validator.py` passes
- [ ] Full suite green

---

## Phase 4: Routes + UI

### Tasks

- [ ] 4.1: Add `POST /applications/{app_id}/tailor` route in `routes/applications.py` (or new `routes/tailored.py`): loads application, calls `generate_tailored_resume`, runs validator, persists via `tailored_repo.create_tailored`, 303-redirects to `/applications/{app_id}/tailored`. Wraps LLM errors → flash error → redirect back.
- [ ] 4.2: Add `GET /applications/{app_id}/tailored` route: loads latest tailored resume + validation; passes through to template; computes `is_stale` via profile hash comparison; 404 if none yet.
- [ ] 4.3: Create `backend/templates/applications/tailored.html` rendering the resume (summary + experience cards + skills chips + projects), the validation banner (count of errors/warnings + per-issue list with location), and a "Regenerate" button. CSS-styled.
- [ ] 4.4: Add "Generate tailored resume" button on `applications/show.html` (visible always; if a tailored version already exists, show "View tailored" link too).
- [ ] 4.5: Add CSS in `style.css` for: validation banner (error vs warning swatches), tailored-resume rendering (summary, experience cards, bullet rows), inline `[unverified]` markers next to flagged bullets/items.
- [ ] 4.6: Tests in `tests/test_tailored_flow.py` (TestClient + mocked generation): `POST /tailor` happy path → redirects; tailored page renders summary + experience; validation issues panel renders when issues exist; LLM error path → graceful redirect; stale banner shown when profile changes after generation.

### Verification

- [ ] `pytest tests/test_tailored_flow.py` passes
- [ ] Full suite green
- [ ] Manual end-to-end: open an application → click "Generate tailored resume" → see output + clean validation panel; modify a profile field → reopen tailored page → stale banner appears; force a fabrication (e.g., manually edit `content_json` to add a fake company) → reload → error issue listed

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] `pytest tests/` green
- [ ] Manual end-to-end: profile + JD → generate → validate → render with issues; regenerate produces a new row, old rows preserved
- [ ] No regression in `compat-analysis_20260426` or `app-workspace_20260427` flows
- [ ] System prompt visibly contains explicit no-fabrication rules (grep test)

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
