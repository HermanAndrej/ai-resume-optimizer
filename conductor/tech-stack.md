# Tech Stack

## Language

**Python 3.11+** — single language, no frontend build step, no TypeScript, no npm.

## Backend

**FastAPI** + **uvicorn**

- Async-first, auto-docs at `/docs`
- Pydantic v2 for request/response validation
- Serves both the API and HTML templates from one process

## Frontend

**Jinja2 templates + HTMX**

No build step. No JavaScript framework. No separate server. HTML is rendered server-side; HTMX handles dynamic interactions (form submissions, partial page updates, streaming) with minimal JS. Plain CSS only — no Tailwind, no component libraries.

Rationale: this is a local personal tool. The UI needs to work, not impress. One server, one language, no coordination overhead.

## Database

**SQLite** via stdlib `sqlite3` (no ORM)

Single file, zero config, built into Python. Stored in the OS app data directory (not the repo) so `git clean` or re-cloning never wipes user data. Auto-migrated on startup via a `schema_version` table.

| Platform | Data path |
|---|---|
| Windows | `%APPDATA%\resume_optimizer\` |
| macOS | `~/Library/Application Support/resume_optimizer/` |
| Linux | `~/.local/share/resume_optimizer/` |

## AI / LLM

**Claude API** via `anthropic` SDK

| Model | Used for |
|---|---|
| `claude-sonnet-4-6` | Default — analysis, resume generation, chat |
| `claude-haiku-4-5-20251001` | Fabrication validation (fast, cheap) |

Streaming enabled for chat only. Analysis and generation return complete JSON.

**Prompt caching** — the system prompt and profile are sent on every call. Cache them with `cache_control: {"type": "ephemeral"}` to reduce costs. Profile + system prompt are the largest repeated context.

## Startup

Single command: `python run.py`

- Checks for `ANTHROPIC_API_KEY` in `.env`, exits with clear message if missing
- Creates data directory if it doesn't exist
- Runs any pending DB migrations
- Starts `uvicorn` on `http://127.0.0.1:8765`
- Opens browser automatically

## Dependencies

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
jinja2>=3.1.0
python-multipart>=0.0.9      # form uploads
anthropic>=0.40.0
pydantic>=2.6.0
pdfminer.six>=20231228       # PDF text extraction
python-docx>=1.1.0           # DOCX parsing + export
python-dotenv>=1.0.0
weasyprint>=61.0             # HTML → PDF export
scikit-learn>=1.4.0          # TF-IDF keyword analysis
```

SQLite is stdlib — no SQLAlchemy, no Alembic.

**Do not add** spaCy, sentence-transformers, Celery, Redis, or any frontend framework. If a dependency isn't in this list, justify it before adding.
