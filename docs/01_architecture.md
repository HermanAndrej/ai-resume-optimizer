# Resume Optimizer App — System Architecture

## What this is

A local personal Python app for building tailored resumes from a centralized profile. User maintains a structured profile once (or imports from an existing resume), then for each job posting creates a "mini-project" that generates a tailored resume, shows compatibility analysis, and provides a chat for further iteration — all grounded strictly in profile data (no fabrication).

## Core principles

1. **Single source of truth** — the user profile. Every generated resume pulls only from profile data.
2. **No fabrication** — the LLM is explicitly constrained to use only profile content. It can reword, reorder, emphasize, or omit — but never invent. Output is validated by a second-pass LLM check before saving.
3. **Per-job-posting workspaces** — each job description becomes a mini-project with its own tailored resume, compatibility analysis, and chat history.
4. **Suggest-then-apply editing** — chat proposes changes, user reviews and approves before anything is written.
5. **Local-first, easy setup** — clone the repo, add your API key, run. No other configuration.

## Setup philosophy

The goal is that anyone cloning the GitHub repo can start using the app by:

1. `git clone <repo>`
2. `cp .env.example .env` and pasting their Anthropic API key
3. `pip install -r requirements.txt`
4. `python run.py` (or equivalent)

That's it. No database setup, no migrations to run manually, no config files to edit. The app:

- Auto-creates the SQLite database on first run
- Auto-runs schema migrations if the DB exists but is outdated
- Auto-creates the data directory at `~/.local/share/resume_optimizer/` (or platform equivalent)
- Validates the API key on startup with a clear error message if missing/invalid
- Opens the browser to the local URL automatically

## Security (for a local app)

Even though it's local-only, a few non-negotiables:

- **API key in `.env`**, never committed. `.gitignore` includes `.env`, `*.db`, `data/`.
- **`.env.example`** provided in the repo as a template.
- **Bind to `127.0.0.1` only** — never `0.0.0.0`. Other devices on the network should not access the app.
- **SQLite file stored outside the repo** in the user's app data directory, so `git clean` or re-cloning doesn't wipe user data.
- **No telemetry, no external calls** other than to the Anthropic API.

## Data model

### User Profile (the source of truth)

Structured into editable sections that mirror resume anatomy:

```
Profile
├── Personal Info
│   ├── full_name
│   ├── email
│   ├── phone
│   ├── location (city, country)
│   └── links: [{label, url}]  # LinkedIn, GitHub, portfolio, etc.
│
├── Summary / Introduction
│   └── text (free-form; can be multiple variants for different role types)
│
├── Experience [list of entries]
│   ├── company
│   ├── title
│   ├── location
│   ├── start_date, end_date (or "present")
│   ├── description (optional brief context)
│   └── bullets: [list of achievement bullets]
│       └── each bullet has: text, tags (optional skill tags for filtering)
│
├── Education [list of entries]
│   ├── institution
│   ├── degree
│   ├── field
│   ├── start_date, end_date
│   ├── gpa (optional)
│   └── highlights (optional bullets)
│
├── Skills
│   ├── categorized: {category_name: [skill_list]}  # e.g. "Languages": ["Python", "Go"]
│   └── flat: [skill_list]  # alternative flat view
│
├── Projects [list of entries]
│   ├── name
│   ├── description
│   ├── tech_stack
│   ├── url (optional)
│   └── bullets: [achievement bullets]
│
├── Certifications [list]
│   ├── name
│   ├── issuer
│   ├── date
│   └── url (optional)
│
└── Additional Sections [user-defined]
    ├── name (e.g., "Publications", "Speaking", "Volunteer Work")
    └── content
```

### Mini-Project (per job posting)

Each job posting the user analyzes becomes a mini-project with persistent state:

```
MiniProject
├── id
├── created_at, updated_at
├── profile_snapshot_hash     # hash of the profile when analysis was run
├── job_title
├── company
├── job_description (raw text)
├── compatibility_analysis    # see below
├── tailored_resume_versions  # list of versions (each apply = new version)
├── chat_history
├── pending_suggestions
├── archived (boolean)
└── settings
    └── selected_model
```

The `profile_snapshot_hash` enables the "re-analyze this project" feature — if the current profile hash differs from the stored hash, we know the profile has changed and the analysis is stale.

### User Memory (cross-project, lightweight)

Small, curated context persisted across all mini-projects. Manually edited by the user only — no auto-learning in v1.

```
UserMemory
├── preferences
│   ├── preferred_tone (e.g., "concise and results-focused")
│   ├── preferred_bullet_style (e.g., "action verb + metric + impact")
│   ├── resume_length_preference (e.g., "one page" or "two pages")
│   └── writing_style_notes (free-form)
│
└── recurring_context
    ├── target_roles: [list]
    ├── industries_of_interest: [list]
    └── deal_breakers (things user never wants in resume)
```

Strict size cap: target ~2000 characters (~500 tokens) max when serialized. Included in every chat system prompt.

### Token/Cost Tracking

```
UsageLog
├── timestamp
├── project_id (or null for profile-level operations)
├── operation ("analysis", "chat", "resume_generation", "profile_parse", "validation", "re_analysis")
├── model
├── input_tokens
├── output_tokens
└── cost_cents
```

## Storage: SQLite

SQLite is the right choice for a local personal tool — single file, zero config, handles all the relational needs, and Python has it built-in.

**Key schema design decisions:**

- **Profile tables normalized** — each section (experience, education, skills, etc.) is its own table. This makes editing individual items clean without serializing/deserializing huge JSON blobs.
- **Mini-project data as JSON blobs** — compatibility analysis, resume versions, and chat messages are read together and rarely queried by internal fields. Storing as JSON is simpler than over-normalizing.
- **Single-row memory table** — `CHECK (id = 1)` constraint guarantees there's only ever one memory record.
- **Migration tracking** — a `schema_version` table so the app can auto-upgrade DBs across releases.

Full schema is in the implementation reference doc.

## App flow

### First-time setup
1. User runs the app, opens browser → lands on an onboarding screen if profile is empty
2. Two options: (a) fill in manually through forms, or (b) upload existing resume (PDF/DOCX/TEX) → LLM parses into profile structure → user reviews and edits
3. Profile is saved to SQLite

### Creating a mini-project
1. User clicks "New Job Analysis"
2. Pastes job description (or uploads file)
3. Profile + JD → backend:
   - Classical: TF-IDF keyword gap analysis (exact keywords)
   - LLM call: parse JD, compare to profile, compute scores, generate explanation
4. Mini-project created with compatibility analysis stored + profile hash snapshotted
5. User sees dashboard: overall score, keyword gaps, skill matches, and a "Profile Gap Nudge" panel listing skills/experiences the JD requires that are missing from profile — with a button "I have this experience — add to profile"

### Re-analyzing a stale project
1. User opens an older mini-project
2. If current profile hash ≠ snapshot hash, banner appears: "Your profile has changed since this analysis was run. [Re-analyze]"
3. Click Re-analyze → fresh compatibility analysis runs → snapshot hash updated
4. Old analysis is preserved in an `analysis_history` table for reference (optional, nice-to-have)

### Generating tailored resume
1. User clicks "Generate Tailored Resume" within the mini-project
2. Backend sends profile + JD + compatibility analysis to LLM with strict "no fabrication" system prompt
3. LLM returns structured resume JSON
4. **Validation pass** — second LLM call compares tailored resume against profile and flags any facts/skills/metrics not traceable to the profile
5. If validation flags issues, user sees a warning with the flagged items; can accept anyway, request a regeneration, or edit manually
6. Once approved, resume saved as version 1
7. User can view/edit/export

### Chat within mini-project
1. User types a question or request
2. Chat context includes: user memory (compact) + profile (compact) + current tailored resume + JD + recent chat history
3. Response is streamed to the UI (if streaming enabled)
4. If user asked for a change, LLM response contains a structured suggestion JSON block
5. Suggestion appears in the "Pending Suggestions" panel with Apply / Reject / Modify buttons
6. **On Apply** → validation check runs on just the proposed change → if clean, creates a new resume version with the change → suggestion marked applied
7. Version history available in the UI; any previous version can be restored (restore = new version with previous content)

### Profile editing
- **Explicit save button** per section with "unsaved changes" warning on navigation
- Not doing autosave — explicit save is more predictable and prevents accidental overwrites

### Export
- Resume can be exported to **PDF**, **DOCX**, and **LaTeX (.tex)**
- LaTeX export uses a user-provided template file (stored in the app config) — see "LaTeX Template" section below
- PDF and DOCX use clean built-in templates (single-column, ATS-friendly)
- Export button available on any resume version

## LaTeX export

Since the user writes resumes in LaTeX, this is a first-class feature:

- **Template-driven** — user supplies their preferred LaTeX template as a file in `templates/latex/` (e.g., `default.tex`)
- **Placeholder-based rendering** — the template uses Jinja2 or string-substitution placeholders for sections (`{{ summary }}`, `{{ experience }}`, etc.)
- Multiple templates supported — dropdown in export UI
- Default template will be based on the user's example (to be attached)
- Export button generates the filled `.tex` file; user can compile locally or the app can optionally shell out to `pdflatex` to produce PDF directly

**Important design rule**: LaTeX export should preserve the exact structure/styling of the user's template. The app fills in content, doesn't redesign layout.

## LLM prompt strategy — the "no fabrication" rule

The most important architectural constraint. Every LLM call that touches resume content must enforce this.

**System prompt template for all resume-related calls:**

```
You are helping the user tailor their resume for a specific job posting.

STRICT RULES:
1. You may ONLY use information that exists in the user's profile (provided below).
2. You may NEVER invent, assume, or extrapolate details not present in the profile.
3. You MAY: reword existing content, reorder items, emphasize specific achievements, omit irrelevant sections, suggest using the JD's exact terminology when the profile mentions a synonym.
4. You MAY NOT: add technologies the user hasn't listed, invent metrics or percentages not in the profile, fabricate job responsibilities, or inflate timelines.
5. If the JD requires something the profile doesn't contain, explicitly flag it as a gap — do not try to cover it up with creative wording.

If asked for a change that would require inventing facts, refuse and explain what profile data would be needed.
```

## Fabrication validation layer

After every generation or applied suggestion, a validation check runs:

```
System prompt: "You are validating that a tailored resume contains only information from the user's profile. Compare the two documents. Return a JSON list of any facts, skills, technologies, companies, dates, metrics, or achievements that appear in the tailored resume but cannot be traced to the profile. If everything checks out, return an empty list."

Input: profile JSON + tailored resume JSON
Output: [{"item": "...", "location_in_resume": "...", "reason": "not found in profile"}, ...]
```

- Uses Haiku by default (fast, cheap — this is a constrained verification task)
- Cost is minor (~$0.001 per check) relative to the generation call
- If validation fails, user sees warnings before saving
- Can be toggled off in settings for speed, but on by default

## Streaming

Streaming is used for the chat endpoint. The Anthropic SDK's `messages.stream()` returns the same response object at the end (including full token counts), so **streaming does NOT increase cost** — same input tokens, same output tokens, same pricing. It only changes when tokens are delivered to the client.

Only concern: if the user closes the browser mid-stream, the API call still completes on Anthropic's side and bills normally. This is equivalent to non-streaming — no special concern.

→ **Streaming is enabled by default for chat.**

Non-chat calls (analysis, resume generation, validation) don't stream — they return structured JSON which needs to be complete before parsing.

## Rate limits and error handling

All LLM calls go through `services/llm_client.py` with:

- **Exponential backoff retry** for rate limits (3 retries: 1s, 2s, 4s)
- **Typed exceptions** raised for specific failure modes:
  - `LLMRateLimitError` → UI shows "rate limited, try again in a moment"
  - `LLMAuthError` → UI shows "check your API key in settings"
  - `LLMInvalidJSONError` → UI shows raw response + retry button
  - `LLMBudgetError` → UI shows "check your Anthropic account billing"
- **User-visible error panel** — persistent, dismissible, with retry action when applicable
- **Never silently swallow errors** — all failures surface to the UI with actionable messages

## Context management for chat

Each chat turn sends to the LLM:
1. System prompt (with "no fabrication" rule)
2. User memory (compact, ~500 tokens)
3. Profile summary (compact representation, ~1500 tokens)
4. Job description (~500-1500 tokens)
5. Current tailored resume (~1000 tokens)
6. Last N chat messages (sliding window, keep under ~2000 tokens)

Approximate context budget: 5000-7000 tokens per turn, leaving plenty of room in the 200k window.

When approaching limits: summarize older chat history into a single "conversation summary so far" message rather than truncating blindly.

## UI structure

Single-page app with main views:

1. **Profile View** — sidebar listing sections, main panel shows editable form. "Import from resume" button at top. Explicit save per section.

2. **Projects View** — list of all mini-projects (with filter: active/archived) and scores at a glance.

3. **Mini-Project View** — three panels:
   - Left: job description (collapsible)
   - Center: tabs for "Analysis" | "Tailored Resume" | "Chat"
   - Right: pending suggestions queue + version history
   - Top: "Re-analyze" button if profile hash has changed + export dropdown

4. **Settings / Usage** — model preferences, user memory editor, usage stats with cost breakdown, LaTeX template manager.

## Versioning and undo

- Every applied suggestion creates a new resume version (cheap storage, full history)
- Every regeneration creates a new version
- Version history panel in the mini-project UI shows all versions with timestamps and generation notes
- "Restore this version" button creates a new version with the restored content (restore is non-destructive)
- Users can diff two versions side-by-side

## Technology stack

- **Backend**: FastAPI (Python 3.11+) + uvicorn
- **Database**: SQLite via `sqlite3` stdlib + auto-migrations
- **Frontend**: FastAPI + Jinja2 templates + HTMX (no build step, no React)
- **LLM**: Anthropic Claude API via `anthropic` SDK, streaming for chat
- **Text extraction**: pdfminer.six (PDF), python-docx (DOCX)
- **OCR fallback** (for image-based PDFs): pytesseract + pdf2image — optional dependency, gracefully degraded if system `tesseract` is not installed
- **Keyword analysis**: scikit-learn TfidfVectorizer
- **Data models**: Pydantic v2
- **Export**:
  - PDF: weasyprint (HTML → PDF)
  - DOCX: python-docx
  - LaTeX: Jinja2 for template rendering, optional `pdflatex` shell-out for PDF compilation

## File structure

```
resume_optimizer/
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── db.py                   # SQLite connection, migrations
│   ├── paths.py                # App data directory resolution per OS
│   ├── models.py               # Pydantic models
│   ├── schemas.py              # Request/response schemas
│   ├── routes/
│   │   ├── profile.py          # CRUD for profile sections
│   │   ├── projects.py         # Mini-project endpoints
│   │   ├── analysis.py         # Compatibility analysis endpoint
│   │   ├── resume_gen.py       # Tailored resume generation
│   │   ├── chat.py             # Chat endpoint with streaming
│   │   ├── suggestions.py      # Apply/reject pending suggestions
│   │   ├── versions.py         # Version history and restore
│   │   ├── export.py           # PDF/DOCX/LaTeX export
│   │   ├── memory.py           # User memory CRUD
│   │   └── usage.py            # Usage stats
│   ├── services/
│   │   ├── extraction.py       # PDF/DOCX/TEX text extraction + OCR fallback
│   │   ├── profile_parser.py   # LLM-based resume → profile parsing
│   │   ├── keyword_analyzer.py # TF-IDF gap detection
│   │   ├── analyzer.py         # Compatibility analysis orchestration
│   │   ├── resume_generator.py # Tailored resume generation
│   │   ├── fabrication_check.py # Validation layer
│   │   ├── chat_service.py     # Chat orchestration
│   │   ├── suggestion_parser.py # Extract suggestions from chat responses
│   │   ├── suggestion_apply.py # Apply suggestions to resume
│   │   ├── export/
│   │   │   ├── pdf.py
│   │   │   ├── docx.py
│   │   │   └── latex.py
│   │   ├── llm_client.py       # Anthropic API wrapper + usage logging
│   │   └── pricing.py          # Model pricing lookup
│   └── prompts/
│       ├── system_base.py
│       ├── profile_parse.py
│       ├── analysis.py
│       ├── resume_gen.py
│       ├── fabrication_check.py
│       └── chat.py
├── frontend/
│   ├── templates/
│   └── static/
├── templates/
│   └── latex/
│       └── default.tex         # User's LaTeX template goes here
├── tests/
│   ├── test_keyword_analyzer.py
│   ├── test_suggestion_apply.py
│   └── test_llm_json_parse.py
├── run.py                      # Entry point — starts uvicorn, opens browser
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Model pricing (for cost tracking)

Always verify current pricing in Anthropic docs before shipping — these drift:

```python
MODEL_PRICING = {
    # Per 1M tokens, input / output in USD
    # VERIFY at https://docs.claude.com/en/docs/about-claude/pricing
    "claude-haiku-4-5-20251001":   {"input": 1.00,  "output": 5.00},
    "claude-sonnet-4-5-20250929":  {"input": 3.00,  "output": 15.00},
}
```

## Build order

1. **Project scaffolding** — repo structure, `.env.example`, `.gitignore`, `run.py` entry script, README with clone-and-go instructions
2. **Database layer** — schema, auto-migrations, app data directory resolution per OS
3. **Profile UI** — forms for each section, explicit save with unsaved-changes warning
4. **Resume import** — PDF/DOCX/TEX extraction + LLM parsing → profile
5. **Compatibility analysis** — TF-IDF + LLM analysis + profile-gap nudge
6. **Mini-projects** — persist analysis with job description + profile hash
7. **Tailored resume generation** — with no-fabrication prompt + validation layer
8. **Export** — PDF, DOCX, LaTeX with user's template
9. **Chat with streaming** — suggestion parsing and apply/reject flow
10. **Versioning UI** — version history, restore, diff view
11. **Re-analyze stale projects** — compare profile hashes, trigger re-run
12. **User memory** — editor UI and injection into chat context
13. **Usage tracking** — dashboard with costs by model/operation/day
14. **Model selection** — per-project dropdown for chat
15. **Polish** — keyboard shortcuts, archive flow, project list filtering

Each step produces a usable increment.
