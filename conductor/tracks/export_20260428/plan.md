# Implementation Plan: Resume Export — PDF and DOCX

**Track ID:** `export_20260428`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-28
**Status:** [~] In Progress

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

- [ ] 2.1: Create `backend/templates/applications/print.html` — a standalone HTML page (no `layout.html` shell). Renders ExportResume into a single-column ATS-safe layout. Includes a small on-screen instructions banner ("Press Ctrl+P / Cmd+P to save as PDF") that is hidden via `@media print`.
- [ ] 2.2: Add inline `<style>` block (or new `static/print.css`) with: 0.75in margins, Calibri/Arial fallback, 11pt body, 14pt section headers, `@media print` rules to hide the instructions banner and force exact margins/font sizes; `page-break-inside: avoid` on experience cards.
- [ ] 2.3: Add `GET /applications/{app_id}/tailored/print` route in `routes/applications.py`: loads application + latest tailored row; if no tailored, redirect to `/applications/{app_id}/tailored`; calls `build_export_resume`; renders `print.html`. 404 if application unknown.
- [ ] 2.4: Smoke test in `tests/test_export_flow.py`: route returns 200; page contains personal info + summary + tailored experience text; print stylesheet present; redirect when no tailored exists.

### Verification

- [ ] `pytest tests/test_export_flow.py::TestPrintRoute` passes
- [ ] Manual: open print page in browser → Ctrl+P → preview is single column, no sidebar visible, fits on 1-2 pages

---

## Phase 3: DOCX export

### Tasks

- [ ] 3.1: Create `backend/services/docx_export.py` with `render_docx(export_resume) -> bytes`. Uses `python-docx`: builds Document, sets default font to Calibri 11pt, 0.75" margins. Renders sections in fixed order (personal → summary → experience → skills → projects → education → certifications). Each section omitted if empty.
- [ ] 3.2: Implement section renderers as private functions: `_render_personal(doc, personal)` writes name as 18pt bold + contact line; `_render_section_heading(doc, text)` adds 14pt bold heading with 6pt space above; `_render_experience(doc, items)` writes each role as `Title — Company` bold + dates italic + bullet list using `List Bullet` style; `_render_skills(doc, groups)` writes each group as `Category: comma, separated, items` paragraph; etc.
- [ ] 3.3: Add `GET /applications/{app_id}/tailored/download.docx` route: loads application + latest tailored row; if no tailored, redirect to `/applications/{app_id}/tailored`; builds `ExportResume`, calls `render_docx`, returns `Response(content=bytes, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{sanitized}.docx"'})`. Filename: `sanitize_filename(f"{full_name} - {company} - {job_title}", fallback="tailored-resume") + ".docx"`.
- [ ] 3.4: Tests in `tests/test_export_flow.py::TestDocxRoute`: route returns 200 with `application/vnd.openxmlformats-...` content type; `Content-Disposition` header has expected filename; response body starts with zip magic bytes (`PK\x03\x04`); using `python-docx` to open the bytes and assert the document contains expected text (full name, summary, experience company name).
- [ ] 3.5: Unit test in `tests/test_docx_export.py`: `render_docx` on an empty ExportResume returns valid bytes; on a populated one, contains all expected text via `Document(BytesIO(...))` round-trip.

### Verification

- [ ] `pytest tests/test_docx_export.py tests/test_export_flow.py::TestDocxRoute` passes
- [ ] Manual: download .docx, open in Word/LibreOffice, verify ATS-safe layout (single column, no tables, standard font)

---

## Phase 4: UI integration + polish

### Tasks

- [ ] 4.1: Add export action row to `applications/tailored.html` (above or below `tailored-actions`): "Print / Save as PDF" link opens `/applications/{id}/tailored/print` in a new tab; "Download DOCX" link to `/applications/{id}/tailored/download.docx`.
- [ ] 4.2: If `validation.error_count > 0`, show a small warning next to the export buttons: "⚠ This resume has unresolved validation errors — review before submitting." Does not block the download.
- [ ] 4.3: Add CSS in `style.css` for the export action row (`.export-actions`), download buttons (download icon-style), and the warning text. Add `print.html`-specific styles (the inline / static stylesheet covered in 2.2).
- [ ] 4.4: Final end-to-end flow test in `tests/test_export_flow.py`: create app → mock-generate tailored → GET `/print` returns 200; GET `/download.docx` returns valid DOCX; tailored.html contains both download links.

### Verification

- [ ] `pytest tests/test_export_flow.py` passes
- [ ] Full suite green
- [ ] Manual end-to-end: open a tailored resume → click "Download DOCX" → file opens correctly in Word; click "Print / Save as PDF" → browser print dialog shows clean single-column page

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] `pytest tests/` green
- [ ] Manual end-to-end: tailored resume → DOCX download opens in Word; print preview saves cleanly to PDF
- [ ] No regression in `resume-tailor_20260427` flows
- [ ] No new dependencies added (python-docx already pinned, no reportlab)

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._
