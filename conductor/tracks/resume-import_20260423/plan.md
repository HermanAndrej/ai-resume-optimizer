# Implementation Plan: Resume Import

**Track ID:** `resume-import_20260423`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-23
**Status:** [~] In Progress

## Overview

Four phases. Phase 1 builds the reusable LLM client — foundational for every subsequent LLM track. Phase 2 adds text extraction. Phase 3 wires up the parser + DB apply. Phase 4 delivers the upload/review UI.

---

## Phase 1: LLM client foundation

Reusable Anthropic wrapper. Used by every subsequent LLM track.

### Tasks

- [x] 1.1: `backend/services/llm_client.py` — typed errors (`LLMError`, `LLMAuthError`, `LLMRateLimitError`, `LLMBudgetError`, `LLMInvalidJSONError`), `MODEL_PRICING` dict (Haiku 4.5 + Sonnet 4.6, with "verify at…" comment), `calculate_cost_cents()`, `_log_usage()` writing to `usage_log`
- [x] 1.2: `call_llm(system, messages, model, operation, application_id, db_conn, max_tokens, use_cache)` → `(text, usage_info)`; prompt caching via `cache_control={"type":"ephemeral"}` on the system block; retry with exponential backoff (1s/2s/4s) on rate limits; translate SDK exceptions to typed errors
- [x] 1.3: `parse_llm_json(text)` — strips markdown fences, handles JSON embedded in prose, raises `LLMInvalidJSONError` on failure
- [x] 1.4: `tests/test_llm_client.py` — `parse_llm_json` edge cases (plain, fenced, embedded, invalid) + `calculate_cost_cents` math

### Verification

- [x] `pytest tests/test_llm_client.py` passes
- [x] Existing 6 tests still green

---

## Phase 2: Text extraction

### Tasks

- [x] 2.1: `backend/services/extraction.py` — `extract_pdf(data: bytes) -> str` via `pdfminer.six`, `extract_docx(data: bytes) -> str` via `python-docx` (paragraphs + tables)
- [x] 2.2: `extract_text(filename: str, data: bytes) -> str` dispatcher — routes by extension; raises `ValueError` for unsupported types; raises `ValueError` if extracted text < 50 chars (likely scanned/image PDF)
- [x] 2.3: `tests/test_extraction.py` — round-trip through a tiny generated DOCX (build in-memory via `python-docx`); include a skipped-by-default PDF fixture if in-memory PDF generation is fragile on this platform

### Verification

- [x] `pytest tests/test_extraction.py` passes
- [x] Full suite green

---

## Phase 3: Profile parser + DB apply

### Tasks

- [x] 3.1: `backend/models.py` — add `ParsedProfile` nested Pydantic model matching all 8 sections
- [x] 3.2: `backend/prompts/__init__.py` + `backend/prompts/profile_parse.py` — system prompt with JSON schema, strict "only facts present in text" rule, example output
- [x] 3.3: `backend/services/profile_parser.py` — `parse_resume_text(text, db_conn) -> ParsedProfile`; uses Haiku; returns parsed model or raises `LLMInvalidJSONError`
- [x] 3.4: `backend/services/profile_repo.py::apply_parsed_profile(conn, parsed)` — single transaction: clear list tables for `profile_id=1`, update `profile` row, re-insert parsed entries with correct `display_order`

### Verification

- [x] Unit test: mock the LLM to return canned JSON, call `parse_resume_text()` + `apply_parsed_profile()`, confirm `list_*()` returns the expected data
- [x] Full suite green

---

## Phase 4: Upload UI + review flow

### Tasks

- [ ] 4.1: Add "Import resume" link at the top of Personal Info page (small, unobtrusive)
- [ ] 4.2: `backend/templates/profile/import.html` — upload form with `<input type="file" accept=".pdf,.docx">`; warning banner if current profile is non-empty
- [ ] 4.3: `GET /profile/import` + `POST /profile/import` — upload handler: validates extension, calls `extract_text`, calls `parse_resume_text`, renders review page with parsed JSON in a hidden field + human-readable preview; errors surface inline
- [ ] 4.4: `backend/templates/profile/import_review.html` — parsed sections at-a-glance + "Apply to profile" button POSTing to `/profile/import/apply`
- [ ] 4.5: `POST /profile/import/apply` — reads hidden JSON, validates as `ParsedProfile`, calls `apply_parsed_profile()`, 303-redirects to `/profile/personal`; handles `ValidationError` gracefully

### Verification

- [ ] End-to-end TestClient: upload a generated DOCX, mock the parser to return canned data, confirm review page renders, POST to apply, confirm DB is populated, confirm redirect
- [ ] Manual browser test with a real resume once the LLM path is live
- [ ] Full suite green

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] Real end-to-end with a real resume: upload → parse → review → apply → navigate through profile sections → see populated data
- [ ] `pytest tests/` green (migration, paths, llm_client, extraction, parser/apply)
- [ ] Cost of a typical import logged in `usage_log` and roughly within expectation (~$0.01–0.02)

---

_Tasks will be marked [~] in progress and [x] complete during implementation._
