# Implementation Plan: Project Scaffolding & Database Layer

**Track ID:** `scaffolding-db_20260423`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-23
**Status:** [x] Complete

## Overview

Three phases — repo files, entry point, database layer. Each phase is independently verifiable. No LLM calls, no routes beyond `/health`, no UI.

---

## Phase 1: Repo Skeleton

Create the static files that define the project.

### Tasks

- [x] 1.1: `requirements.txt` — all MVP dependencies pinned
- [x] 1.2: `pyproject.toml` — project metadata and pytest config
- [x] 1.3: `.env.example` — template with `ANTHROPIC_API_KEY=`
- [x] 1.4: `.gitignore` — covers `.env`, `*.db`, `__pycache__`, `.venv`, `data/`
- [x] 1.5: `.vscode/extensions.json` — recommend `ms-python.python`, `ms-python.pylance`
- [x] 1.6: `README.md` — setup instructions: clone → add key → install → run

### Verification

- [x] All files exist in repo root
- [x] `.gitignore` correctly ignores `.env` and `*.db`

---

## Phase 2: Entry Point

`run.py` — single command to start the app.

### Tasks

- [x] 2.1: Load `.env` via `python-dotenv`
- [x] 2.2: Check `ANTHROPIC_API_KEY` — print clear error and `sys.exit(1)` if missing
- [x] 2.3: Call `get_data_dir()` and create directory with `mkdir(parents=True, exist_ok=True)`
- [x] 2.4: Call `run_migrations(db_path)` to apply pending DB migrations
- [x] 2.5: Schedule browser open after 1.5s via `threading.Timer`
- [x] 2.6: Start uvicorn on `127.0.0.1:8765`
- [x] 2.7: `backend/__init__.py` (empty)
- [x] 2.8: `backend/main.py` — bare FastAPI app, single `/health` route returning `{"status": "ok"}`

### Verification

- [x] `python run.py` with valid key: server starts, browser opens, `/health` returns 200
- [x] `python run.py` with `ANTHROPIC_API_KEY` unset: clear error printed, exits with code 1

---

## Phase 3: Database Layer

`backend/paths.py` and `backend/db.py`.

### Tasks

- [x] 3.1: `backend/paths.py` — `get_data_dir()` for Windows/macOS/Linux, `get_db_path()`
- [x] 3.2: `backend/db.py` — `get_connection()` with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- [x] 3.3: `backend/db.py` — `SCHEMA_V1` SQL string with all tables:
  - `schema_version`
  - `profile`, `profile_links`
  - `experience`, `experience_bullets`
  - `education`, `skills`, `projects`, `certifications`, `custom_sections`
  - `applications`, `tailored_resumes`
  - `chat_messages`, `pending_suggestions`
  - `usage_log`
  - Seed: `INSERT INTO profile (id) VALUES (1)`
- [x] 3.4: `backend/db.py` — `run_migrations()` — checks `schema_version`, applies unapplied versions in order
- [x] 3.5: `backend/db.py` — `get_db()` FastAPI dependency — yields connection, closes on exit

### Verification

- [x] First run: `app.db` created in OS data dir, all tables present
- [x] Second run: no errors, no duplicate tables
- [x] Profile seed row `id=1` present after first run

---

## Final Verification

- [x] All acceptance criteria from spec.md checked off
- [x] Delete DB, re-run: DB recreated cleanly
- [x] Missing API key: exits with code 1 and clear message
- [x] `pip install -r requirements.txt` completes without conflicts

---

_Completed: 2026-04-23_
