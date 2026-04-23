# Workflow

## MVP Scope

Build the smallest thing that delivers the core value: **paste your profile + a JD, get a truthful tailored resume**.

### In scope for MVP

1. Profile setup — manual entry or import from PDF/DOCX
2. Compatibility analysis — keyword gap + LLM scoring vs a JD
3. Tailored resume generation — with fabrication guardrail
4. Export — PDF and DOCX (ATS-safe format)
5. Per-job chat — iterate on the tailored resume
6. Resume versioning — every apply/regen creates a new version, any version is restorable

### Explicitly out of scope for MVP

- Version diff view (side-by-side comparison)
- User memory / cross-project preferences editor
- Usage dashboard / cost tracking UI (log to DB silently; no UI)
- LaTeX export
- OCR fallback for scanned PDFs
- Re-analyze stale projects (profile hash comparison banner)
- Model selection per project
- Archive / filter on project list

Add these only after the MVP works end-to-end.

## TDD Policy

**Flexible** — tests for logic with real failure modes, skip for CRUD and UI.

Write tests for:
- Fabrication detection logic
- Keyword/ATS scoring
- Suggestion apply (nested path mutations)
- `parse_llm_json` (handles markdown fences, embedded blocks, invalid input)

Skip tests for:
- Simple CRUD endpoints
- UI templates
- DB migrations (verify manually on first run)

## Commit Strategy

**Conventional Commits:**

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `chore`, `refactor`, `test`

## Code Review

Solo project — self-review only. Before marking a task done:
- Does it match the task spec?
- Is the fabrication guardrail intact?
- No regression in previously working features?

## Verification

**After each task**, verify manually:

1. `python run.py` — server starts, browser opens
2. Exercise the happy path for the task in the browser
3. Check one edge case
4. Confirm no regression

A task is **Done** only after this passes.

## Task Lifecycle

```
Planned → In Progress → Implemented → Verified → Done
```

## Branch Strategy

Commit directly to `main`. Feature branches only for changes spanning multiple sessions.

## Build Order

Follow this sequence. Do not skip ahead. Each step produces a working increment.

1. Project scaffolding — repo, `.env.example`, `.gitignore`, `run.py`, README
2. Database layer — schema, auto-migrations, OS data dir
3. Profile UI — all sections, explicit save, unsaved-changes warning
4. Resume import — PDF/DOCX extraction + LLM parsing → profile
5. Compatibility analysis — TF-IDF keyword gap + LLM scoring + gap nudge
6. Applications — persist job workspace (JD, analysis, profile hash)
7. Tailored resume generation — no-fabrication prompt + validation layer
8. Export — PDF and DOCX
9. Chat with streaming — suggestion parse, apply/reject flow
10. Versioning UI — version list, restore
