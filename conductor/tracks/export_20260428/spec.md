# Specification: Resume Export — PDF and DOCX

**Track ID:** `export_20260428`
**Type:** Feature
**Created:** 2026-04-28
**Status:** Draft

## Summary

Export a tailored resume as either a one-click DOCX file (server-rendered via `python-docx`) or a print-optimized HTML page that the user saves to PDF via the browser's print dialog. Both outputs use an ATS-safe single-column layout drawn from the user's profile + the latest tailored content for the application.

## Context

This is build-order step #8 from `workflow.md`. With tailored resumes generated and validated (`resume-tailor_20260427`), the user now needs a way to actually submit the file with their application. ATS-safe formatting matters — a fancy multi-column resume is less useful than a plain single-column one that parses cleanly.

`tech-stack.md` explicitly constrains the PDF approach: **no `reportlab` or `weasyprint`** in the MVP — render a print-friendly HTML preview and let the browser produce the PDF via Ctrl+P. This keeps the install story zero-config across Windows/macOS/Linux. `python-docx>=1.1.0` is already pinned and is used for the DOCX export.

## User Story

As a tech job applicant, after I generate a tailored resume for an application, I want one-click DOCX download and a clean print-friendly preview I can save as PDF, so that I can submit a properly formatted file to ATS systems without manual reformatting.

## Acceptance Criteria

- [ ] On the tailored-resume page, there are two clear actions: **Print / Save as PDF** (opens print preview in a new tab) and **Download DOCX** (streams the file)
- [ ] DOCX export streams a valid `.docx` file with `Content-Disposition: attachment; filename="..."` — the filename is `{full_name} - {company} - {job_title}.docx`, sanitized
- [ ] The PDF print preview is a dedicated `/print` page with no sidebar / chrome, single-column ATS-safe layout, and a `@media print` stylesheet ensuring page breaks, no nav, and proper margins
- [ ] Both formats render identical content: full name + contact, tailored summary, tailored experience (only the bullets in the tailored output), tailored skills, selected projects (full project entries pulled from profile, filtered by `selected_projects`), education (full from profile), certifications (full from profile)
- [ ] DOCX uses standard ATS-safe styling: Calibri 11pt body, bold section headers (Calibri 14pt), bullet character `•`, no tables for layout, no images, no headers/footers
- [ ] If the latest tailored resume has validation errors, a warning is shown next to the download buttons (does not block download)
- [ ] If no tailored resume exists yet, the export buttons direct the user to generate one first
- [ ] DOCX export route is covered by a smoke test that asserts the response is a valid zip-format file (DOCX = zip) with the expected filename and content type

## Dependencies

Depends on existing code:
- `tailored_repo.get_latest_for_application` (resume-tailor track)
- Profile repos for personal info, education, certifications, projects (referenced by name from `selected_projects`)
- `application_repo.get_application`

`python-docx>=1.1.0` is already in `tech-stack.md` dependencies — no new packages required.

## Out of Scope

- Server-side PDF generation via `reportlab` / `weasyprint` (explicitly forbidden by tech-stack.md for MVP)
- Choosing between resume versions on the export page (always exports the latest version; older versions out of scope)
- Cover letter export
- Custom resume templates / theme picker
- LinkedIn-style export to JSON Resume / HRJSON formats
- Direct upload to ATS / one-click apply
- Watermarks, headers, footers, page numbers
- Inline preview of the DOCX (offered after download via OS app)

## Technical Notes

- **Renderable resume model** (`ExportResume`): a single dataclass holding everything both renderers need — personal info, summary, experience entries (each with bullets), skills, projects (full entries filtered by `selected_projects` list), education, certifications. Built from `(profile rows + tailored content)` in one place to avoid drift between the print HTML and the DOCX.
- **PDF path**: route `GET /applications/{app_id}/tailored/print` returns a minimal HTML page (separate template, no layout.html shell). A `print.css` stylesheet (or inline `<style>`) sets margins, fonts, page breaks, and `@media screen` adds an instructions banner with a "Print this page" button that calls `window.print()`.
- **DOCX path**: route `GET /applications/{app_id}/tailored/download.docx` builds an `ExportResume`, calls `render_docx() -> bytes`, returns `Response(content=..., media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": ...})`.
- **Filename sanitization**: strip filesystem-unsafe characters (`<>:"/\|?*` and control chars), trim whitespace, fall back to `tailored-resume.docx` if all components are empty.
- **DOCX styling rules** (ATS-safe, hard-coded — no theme picker):
  - Body: Calibri 11pt, single line spacing, 0.75" margins all sides
  - Section headers: Calibri 14pt bold, 6pt space above, no underline/border
  - Bullet character: `•` followed by tab; built-in `List Bullet` style
  - Personal info: name as 18pt bold, contact line below as 10pt regular
  - No tables, no text boxes, no inline images
- **Empty fields**: omit sections entirely if empty (e.g. no education → no Education heading at all)
- **No persistence**: exports are generated on demand. We do not save the bytes anywhere.

---

_Generated by Conductor. Review and edit as needed._
