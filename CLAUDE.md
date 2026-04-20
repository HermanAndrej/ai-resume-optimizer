# Resume Optimizer

Local personal Python app for tailoring resumes to job postings. A centralized structured profile is the source of truth; per-job "mini-projects" produce compatibility analysis, tailored resumes, and chat-based iteration. Every generated resume must use only profile data — no fabrication, validated by a second-pass LLM check.

## Tech stack

- Python 3.11+, FastAPI + uvicorn bound to 127.0.0.1 only
- SQLite via stdlib `sqlite3` with auto-migrations on startup
- Jinja2 + HTMX frontend (no build step, no React)
- Anthropic SDK — streaming for chat, non-streaming for structured JSON tasks
- Models: Sonnet 4.6 default, Haiku 4.5 for validation/extraction, Opus 4.6 optional for chat
- weasyprint (PDF), python-docx (DOCX), Jinja2 with LaTeX-safe delimiters (LaTeX)
- scikit-learn TfidfVectorizer, Pydantic v2, pdfminer.six, python-docx
- pytesseract + pdf2image for OCR fallback (optional, graceful degrade)

Do NOT introduce new deps without reason. Do NOT add spaCy, sentence-transformers, or skills taxonomies.

## Architecture rules

- Profile is the source of truth; all generated content must trace to it
- All LLM calls go through `backend/services/llm_client.py` — single place for API calls, usage logging, typed errors (`LLMAuthError`, `LLMRateLimitError`, `LLMInvalidJSONError`, `LLMBudgetError`)
- "No fabrication" system prompt is non-negotiable on every resume-related call
- Fabrication validation runs after every generation and applied suggestion (Haiku)
- Every apply/regen/restore creates a new immutable resume version; restore ≠ overwrite
- Profile hash stored per mini-project for staleness detection + re-analysis
- User memory capped at ~2000 chars, manually edited only (no auto-learning in v1)
- Explicit save on profile edits with unsaved-changes warning (no autosave)
- Streaming only for chat endpoint; analysis/generation/validation need complete JSON
- SQLite in OS app data dir (`~/.local/share/resume_optimizer/` etc.), never in repo

## Code style

- Type hints on all function signatures including return types
- Pydantic v2 models for any data crossing a boundary (API I/O, LLM responses, DB rows)
- Prefer plain functions over classes unless state is carried
- `pathlib` over `os.path`
- Docstrings on public functions
- Never silently swallow errors; surface typed exceptions to the UI

## Reference documentation

Detailed specs live in `docs/`. Read only the files relevant to the current task:

- @docs/01_architecture.md — data model, SQLite schema, app flow, build order
- @docs/02_implementation_reference.md — canonical code patterns for every module
- @docs/03_ats_domain_knowledge.md — how real ATS platforms parse and score
- @docs/05_latex_template.md — Jinja2 template matching my LaTeX resume format
- @docs/06_tech_resume_2026.md — SWE/AI resume best practices for content quality

## Setup must stay trivial

Someone cloning this repo should be able to: `git clone` → `cp .env.example .env` → add API key → `pip install -r requirements.txt` → `python run.py`. Browser opens automatically. No manual DB setup. No config beyond the key.

## Build order

Follow the 15-step order in `docs/01_architecture.md`. Don't skip ahead. Verify each step works before the next. Current step: **4 — Resume Import**

Completed:
- Step 1: Project scaffolding (`.env.example`, `.gitignore`, `requirements.txt`, `pyproject.toml`, `README.md`, `run.py`)
- Step 2: Database layer (`backend/paths.py`, `backend/db.py` — schema v1, auto-migrations, seed profile row)
- Step 3: Profile UI (`backend/models.py`, `backend/routes/profile.py`, `frontend/` — all 8 sections with explicit save, unsaved-changes warning, HTMX navigation)

## Verification commands

- `python run.py` — starts server on http://127.0.0.1:8765
- `pytest tests/` — runs tests
- `sqlite3 ~/.local/share/resume_optimizer/app.db ".schema"` — inspect DB schema (Linux/Mac)