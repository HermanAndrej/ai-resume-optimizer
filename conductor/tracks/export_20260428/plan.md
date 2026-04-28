# Implementation Plan: Resume Export — PDF and DOCX

**Track ID:** `export_20260428`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-28
**Status:** [ ] Not Started

## Overview

Four phases. Phase 1 builds a single shared `ExportResume` model + builder so both renderers consume identical data. Phase 2 adds the print-friendly HTML preview (PDF via browser). Phase 3 adds the DOCX renderer + streaming download route. Phase 4 wires the buttons into `tailored.html` and adds end-to-end tests.

---

## Phase 1: Renderable resume model + builder

### Tasks

- [ ] 1.1: Add `ExportResume` dataclass / Pydantic model in `backend/models.py`: `personal: PersonalInfo`, `summary: str`, `experience: list[ExportExperience]` (company, title, location, start_date, end_date, bullets[str]), `skills_grouped: list[ExportSkillGroup]` (category + items), `projects: list[ExportProject]` (full entries, filtered by `selected_projects`), `education: list[EducationEntry]`, `certifications: list[CertificationEntry]`.
- [ ] 1.2: Create `backend/services/export_builder.py` with `build_export_resume(conn, application, tailored_content) -> ExportResume`. Reads personal info + education + certifications + matching projects from the profile repos; pulls summary/experience(rows)/skills from tailored content. Skills are grouped by their original profile category when possible (lookup by skill name), else `"Skills"`.
- [ ] 1.3: Add `sanitize_filename(name: str, fallback: str) -> str` helper in `export_builder.py`: strips `<>:"/\|?*` and control chars, trims whitespace, returns fallback if empty.
- [ ] 1.4: Tests in `tests/test_export_builder.py`: builder pulls personal + education + certs from profile; filters projects by `selected_projects` list; preserves tailored summary/experience/skills; missing sections produce empty lists; filename sanitization (special chars, empty input, unicode preserved).

### Verification

- [ ] `pytest tests/test_export_builder.py` passes
- [ ] Full suite green

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
