# AI Resume Optimizer

A local-first tool for tech job applicants to tailor their resume to a specific job description — without fabrication. You maintain a single source-of-truth profile; the app generates per-job tailored resumes, scores them against the JD, and validates every claim against your profile before you submit.

> **The headline guarantee:** every generated resume is checked by a deterministic validator that flags any company, title, skill, project, or numeric claim that can't be traced back to your source profile. The LLM is also explicitly prompted with 10 absolute no-fabrication rules. A truthful "weaker" resume beats a fabricated "stronger" one.

## Who this is for

Tech job applicants — SWE, backend, full-stack, AI Engineer, ML Engineer — actively applying to roles. The keyword analysis, prompts, and scoring are tuned for the tech hiring landscape. It is not designed for non-technical resumes.

## What it does

A complete loop from raw profile to submission-ready file:

1. **Build / import a profile** — manual entry of personal info, summary, experience (with bullet-level edits), education, skills, projects, certifications. Or upload an existing PDF/DOCX resume and let Claude Haiku parse it into the structured profile.
2. **Save a job description** — paste a JD into a per-job workspace. Each application (job_title + company + JD) becomes a persistent record with status (analyzed / applied / interviewing / rejected / offer), notes, source URL, and editable archive flag.
3. **Compatibility analysis** — TF-IDF keyword overlap (matched/missing/JD-only) plus a Claude Sonnet rubric scoring fit 0–10 with strengths, gaps, and concrete recommendations.
4. **Generate a tailored resume** — Claude Sonnet produces a job-specific resume (summary, reordered experience with rephrased bullets, JD-relevant skills, selected projects). Each tailored bullet must cite its source bullet ID, anchoring it to your real profile.
5. **Validate** — a deterministic validator walks the output and flags anything that doesn't trace to your source profile: unknown companies/titles/projects (errors); unknown skills and unverified numeric claims like percentages or dollar amounts (warnings).
6. **Export** — one-click DOCX (ATS-safe Calibri 11pt, single-column, no tables/images) or print-friendly HTML preview that the browser saves to PDF.

Stale detection runs across the loop: if you edit your profile after an analysis or tailored resume was generated, the app shows a "needs re-analysis" banner so you never submit something out of date.

## How AI is used

| Stage | Model | Why this model |
|---|---|---|
| Resume parsing (PDF/DOCX import) | `claude-haiku-4-5-20251001` | Fast, cheap, structured-output extraction |
| Compatibility scoring | `claude-sonnet-4-6` | Rubric judgment + JD-grounded gap analysis |
| Tailored resume generation | `claude-sonnet-4-6` | Quality matters; this is the most user-visible output |
| Validation | none — deterministic | Reproducible, free, no hallucination loop |

**Prompt caching** is enabled on every call. The system prompt + structured profile context are the largest repeated payloads, so they're sent with `cache_control: ephemeral` to cut input cost dramatically across a session.

**Cost transparency** is built in. Every API call logs input/output tokens, cache hits, and computed cost in cents to a `usage_log` table. The UI surfaces both the cost of the most recent action and the cumulative project cost.

**No fabrication is enforced in two layers**:

1. **At generation time** — a strict system prompt with 10 absolute rules forbidding the model from inventing companies, titles, skills, technologies, metrics, dates, or achievements. The model must cite the source bullet ID for every tailored bullet.
2. **At verification time** — after generation, a deterministic validator checks every claim against an index built from your live profile. Companies, titles, project names, and source-bullet references that don't match → errors. Unknown skills and numeric claims (percentages, dollar amounts, year ranges, multipliers, integers ≥ 10) → warnings. Issues are surfaced inline next to the offending text and as a summary banner above the resume.

## Architecture

A single-process Python app — no frontend build, no separate API server, no JS framework.

```
┌────────────────────────────────────────────────────────────────────┐
│  Browser  (HTMX-enhanced HTML, plain CSS, no SPA)                  │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
                  HTTP / form posts
                           │
┌──────────────────────────▼─────────────────────────────────────────┐
│  FastAPI + Jinja2  (single uvicorn process on :8765)                │
│  ──────────────────────────────────────────────────────────────────│
│  routes/         profile.py · applications.py · resume.py           │
│  services/       profile_repo · application_repo · tailored_repo    │
│                  keyword_analysis · compat_runner · compat_scorer   │
│                  resume_tailor · resume_validator                   │
│                  export_builder · docx_export                       │
│                  llm_client (caching, retry, cost tracking)         │
│  templates/      profile/* · applications/* (list, show, tailored,  │
│                  print, edit, new)                                  │
│  prompts/        compatibility.py · profile_parse.py · resume_tailor│
└──────────┬─────────────────────────────────────┬───────────────────┘
           │                                     │
   sqlite3 (stdlib)                       anthropic SDK
           │                                     │
┌──────────▼──────────┐         ┌────────────────▼──────────────┐
│  SQLite (1 file)    │         │  Claude API                   │
│  in OS data dir     │         │  Haiku 4.5  (parsing)         │
│  auto-migrated      │         │  Sonnet 4.6 (analysis + tailor)│
└─────────────────────┘         └───────────────────────────────┘
```

**Key design choices**:

- **Single language, single process.** Python everywhere. No TypeScript, no npm, no build step.
- **Server-rendered HTML + HTMX.** Forms submit, the server returns updated HTML fragments. Plain CSS, no Tailwind, no component library.
- **SQLite via stdlib `sqlite3`** with no ORM. Schema versioned via a `schema_version` table and auto-migrated on startup. Stored in your OS app data directory (`%APPDATA%\resume_optimizer\` on Windows, `~/Library/Application Support/resume_optimizer/` on macOS, `~/.local/share/resume_optimizer/` on Linux) — `git clean` or recloning never touches your data.
- **Pydantic v2 throughout** for request validation, structured LLM output parsing, and internal data flow.
- **No PDF library.** PDF export is a print-friendly HTML preview — `Ctrl+P` → "Save as PDF". This avoids `reportlab` / `weasyprint` install pain on Windows and produces guaranteed text-based, ATS-safe PDFs via the browser's native renderer.
- **DOCX via `python-docx`.** Hard-coded ATS-safe styling: Calibri 11pt body, 14pt bold headers, 0.75" margins, no tables for layout, no inline images, no headers/footers.

## Setup

### Requirements

- **Python 3.11+**
- **An [Anthropic API key](https://console.anthropic.com/)**

### Install

```bash
git clone https://github.com/HermanAndrej/ai-resume-optimizer.git
cd ai-resume-optimizer

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Open .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...
```

### Run

```bash
python run.py
```

This:

1. Verifies `ANTHROPIC_API_KEY` is set (exits with a clear message if not)
2. Creates the OS data directory if it doesn't exist
3. Runs any pending DB migrations
4. Starts `uvicorn` on `http://127.0.0.1:8765`
5. Opens your browser

## Using the app

A typical flow:

1. **Set up your profile** — go to `/profile/personal`, fill in everything, OR go to `/profile/import` and upload an existing resume PDF/DOCX. Review and apply the parsed sections.
2. **Analyze a JD** — `/applications/new`, paste the job title + company + JD. The app runs keyword overlap + Claude scoring and lands you on the application page with a fit score, strengths, gaps, and gap nudge.
3. **Generate a tailored resume** — click **Generate tailored resume** on the application page. The output appears at `/applications/{id}/tailored` with the validation banner up top — green if clean, red/yellow with specific issues otherwise. Inline `[unverified]` flags mark any flagged spans.
4. **Export** — from the tailored page click **Print / Save as PDF** (opens a clean print preview in a new tab) or **Download DOCX**. The DOCX filename is auto-generated as `{Your Name} - {Company} - {Job Title}.docx`.
5. **Iterate** — if your profile changes, the application page shows a stale banner and a one-click re-analyze button. Each tailored generation produces a new version row — old versions are preserved.

## Project structure

```
.
├── run.py                            # Entry point — checks env, runs migrations, starts uvicorn
├── requirements.txt
├── backend/
│   ├── main.py                       # FastAPI app + route registration
│   ├── db.py                         # SQLite migrations (V1 → V2 → V3)
│   ├── models.py                     # All Pydantic models (profile, app, tailored, export, validation)
│   ├── paths.py                      # OS-specific data dir resolution
│   ├── templating.py                 # Jinja2Templates instance
│   ├── prompts/
│   │   ├── compatibility.py          # Sonnet rubric prompt for fit scoring
│   │   ├── profile_parse.py          # Haiku prompt for resume → ParsedProfile
│   │   └── resume_tailor.py          # Sonnet prompt with 10 no-fabrication rules
│   ├── routes/
│   │   ├── profile.py                # CRUD per profile section
│   │   └── applications.py           # All application + tailored + export routes
│   ├── services/
│   │   ├── llm_client.py             # call_llm with prompt caching, retries, cost tracking
│   │   ├── extraction.py             # PDF/DOCX → text
│   │   ├── profile_parser.py         # text + LLM → ParsedProfile
│   │   ├── profile_repo.py           # all profile CRUD
│   │   ├── application_repo.py       # application CRUD + staleness
│   │   ├── tailored_repo.py          # tailored resume rows + auto-versioning
│   │   ├── keyword_analysis.py       # TF-IDF overlap (scikit-learn)
│   │   ├── compat_scorer.py          # Sonnet fit-scoring service
│   │   ├── compat_runner.py          # composed pipeline + profile hash
│   │   ├── resume_tailor.py          # build_profile_context + generate_tailored_resume
│   │   ├── resume_validator.py       # SourceIndex + validate_tailored_resume
│   │   ├── export_builder.py         # ExportResume builder + filename sanitizer
│   │   └── docx_export.py            # python-docx renderer
│   ├── static/                       # style.css, dirty.js
│   └── templates/                    # Jinja2 templates (profile/, applications/)
├── tests/                            # pytest — 253 tests across all layers
└── conductor/                        # Project planning artifacts (specs + plans per track)
    ├── product.md
    ├── tech-stack.md
    ├── workflow.md
    └── tracks/                       # one folder per feature track
```

## Development

### Running tests

```bash
pytest                       # full suite (~50s including LLM-mocked flow tests)
pytest tests/test_resume_validator.py -v   # one file, verbose
pytest -k tailored           # match by name pattern
```

The suite covers:

- **Migration / repo layer** — every CRUD path, schema_version idempotency
- **LLM services** — `call_llm` with mocked `anthropic` client, JSON parsing edge cases, cost calculation
- **Keyword analysis** — TF-IDF overlap correctness
- **Validation logic** — every fabrication category + numeric extraction + case-insensitive matching
- **Flow tests** — end-to-end TestClient with `dependency_overrides[get_db]` and patched LLM calls
- **Prompt guardrails** — assertions that the no-fabrication system prompt still contains required phrases (catches accidental weakening)

### Project conventions

- **Conductor**-driven planning: each feature is a "track" with a `spec.md` (acceptance criteria) and a phased `plan.md` (tasks). After each phase, run the full suite and pause for review before the next phase.
- **Conventional Commits** — `feat`, `fix`, `chore`, `refactor`, `test`, `docs`. Direct commits to `main`.
- **Flexible TDD**: write tests for logic with real failure modes (validators, parsers, scorers); skip for trivial CRUD and pure UI templates.

## Status

**MVP loop complete.** From profile → JD → analysis → tailored resume → ATS-safe export, the full submission flow works end-to-end with the no-fabrication guardrails in place.

| # | Track | Status |
|---|---|---|
| 1 | Project scaffolding & DB layer | ✅ |
| 2 | Profile UI | ✅ |
| 3 | Resume import (PDF/DOCX → LLM parse) | ✅ |
| 4 | Compatibility analysis | ✅ |
| 5 | Application workspace | ✅ |
| 6 | Tailored resume generation + validator | ✅ |
| 7 | Export — PDF and DOCX | ✅ |
| 8 | Chat with streaming (suggestion apply/reject) | ⏳ planned |
| 9 | Versioning UI (list + restore) | ⏳ planned |

## Non-goals

The tech-stack is intentionally constrained. **Do not add** unless explicitly justified: spaCy, sentence-transformers, Celery, Redis, any frontend framework, ORM (SQLAlchemy / Alembic), `reportlab`, `weasyprint`. The single-process / single-language story is the design.

## License

Personal use. No license file — assume "all rights reserved" until one is added.
