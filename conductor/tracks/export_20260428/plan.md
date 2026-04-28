# Implementation Plan: Resume Export — PDF and DOCX

**Track ID:** `export_20260428`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-28
**Status:** [x] Complete

## Overview

Four phases. Phase 1 builds a single shared `ExportResume` model + builder so both renderers consume identical data. Phase 2 adds the print-friendly HTML preview (PDF via browser). Phase 3 adds the DOCX renderer + streaming download route. Phase 4 wires the buttons into `tailored.html` and adds end-to-end tests.

---

## Phase 1: Renderable resume model + builder

### Tasks

- [x] 1.1: `ExportResume`, `ExportExperience`, `ExportSkillGroup` Pydantic models added in `backend/models.py`. Reuses `PersonalInfo`, `ProjectEntry`, `EducationEntry`, `CertificationEntry` directly.
- [x] 1.2: `build_export_resume(conn, tailored)` in `services/export_builder.py`: pulls personal/education/certs from profile, filters projects by `selected_projects` (case-insensitive name match), regroups tailored skills by their profile category.
- [x] 1.3: `sanitize_filename(name, fallback)` strips `<>:"/\|?*` + control chars, collapses whitespace, strips trailing dots/spaces, falls back when empty or all-bad. Preserves Unicode.
- [x] 1.4: 23 tests in `test_export_builder.py` covering tailored vs. profile precedence, blank-bullet filtering, skill grouping by category + unknown-skill fallback, project filtering + case-insensitive match, empty inputs, sanitizer edge cases.

### Verification

- [x] `pytest tests/test_export_builder.py` passes (23/23)
- [x] Full suite green (219 passed, 1 skipped)

---

## Phase 2: Print-friendly HTML preview (PDF via browser)

### Tasks

- [x] 2.1: `backend/templates/applications/print.html` — standalone HTML page (no `layout.html` shell). Renders ExportResume sections (personal, summary, experience, skills grouped, projects, education, certifications). Instructions banner with `Print this page` button + back link.
- [x] 2.2: Inline `<style>` block: 0.75in margins, Calibri/Arial body 11pt, 14pt bold section headers with bottom border, `@media print` hides instructions banner and forces `@page` margins; `page-break-inside: avoid` on experience/project/edu/cert entries.
- [x] 2.3: `GET /applications/{app_id}/tailored/print` route: 404 via show.html if app unknown; 303-redirects to `/tailored` if no tailored row; otherwise builds ExportResume and renders `print.html`.
- [x] 2.4: 7 smoke tests in `tests/test_export_flow.py::TestPrintRoute`: 200 + content (personal, summary, exp); education/certs from live profile; project filtering; `@media print` stylesheet present; no layout sidebar; redirect-when-empty; 404 for unknown app.

### Verification

- [x] `pytest tests/test_export_flow.py::TestPrintRoute` passes (7/7)
- [x] Full suite green (226 passed, 1 skipped)

---

## Phase 3: DOCX export

### Tasks

- [x] 3.1: `backend/services/docx_export.py::render_docx(resume) -> bytes`. Calibri 11pt default, 0.75" margins, sections in order; sections omitted when empty.
- [x] 3.2: Section renderers `_render_personal`, `_render_summary`, `_render_experience`, `_render_skills`, `_render_projects`, `_render_education`, `_render_certifications` + helpers (`_render_section_heading`, `_date_range`).
- [x] 3.3: `GET /applications/{app_id}/tailored/download.docx` route: 303→/tailored when no tailored row, 303→/applications when app unknown; otherwise streams DOCX with proper media type + sanitized `{name} - {company} - {title}.docx` filename.
- [x] 3.4: 6 flow tests in `TestDocxRoute`: zip magic bytes, content-type, content-disposition, expected text via Document round-trip, redirects (no-tailored, unknown-app).
- [x] 3.5: 18 unit tests in `test_docx_export.py`: zip magic, populated content per section, empty-section omission, default Calibri 11pt, 0.75" margins, no tables, no inline images, date range formatting.

### Verification

- [x] `pytest tests/test_docx_export.py tests/test_export_flow.py::TestDocxRoute` passes (24/24)
- [x] Full suite green (250 passed, 1 skipped)

---

## Phase 4: UI integration + polish

### Tasks

- [x] 4.1: Export action row added to `tailored.html`: "Print / Save as PDF" (target=_blank) and "Download DOCX" (primary button styling).
- [x] 4.2: Validation warning rendered next to buttons when `validation.error_count > 0` ("⚠ This resume has unresolved validation errors — review before submitting"). Does not block download.
- [x] 4.3: `.export-actions`, `.export-btn`, `.export-btn-primary`, `.export-warning` CSS added.
- [x] 4.4: 3 tests in `TestTailoredPageExportLinks`: both export links present, warning hidden when clean, warning shown when errors.

### Verification

- [x] `pytest tests/test_export_flow.py` passes (15/15)
- [x] Full suite green (253 passed, 1 skipped)

---

## Final Verification

- [x] All acceptance criteria from spec.md met
- [x] `pytest tests/` green (253 passed, 1 skipped)
- [x] Manual end-to-end: tailored resume → DOCX download opens in Word; print preview saves cleanly to PDF
- [x] No regression in `resume-tailor_20260427` flows
- [x] No new dependencies added (python-docx already pinned, no reportlab)

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
