# Implementation Plan: Compatibility Analysis

**Track ID:** `compat-analysis_20260426`
**Spec:** [spec.md](./spec.md)
**Created:** 2026-04-26
**Status:** [x] Complete

## Overview

Four phases. Phase 1 builds the deterministic keyword analysis (TF-IDF). Phase 2 adds the LLM scoring layer. Phase 3 wires the application persistence + analysis route. Phase 4 delivers the UI templates and gap nudge presentation.

---

## Phase 1: Keyword analysis (TF-IDF)

Pure Python; no LLM, no DB writes. Deterministic and fast.

### Tasks

- [x] 1.1: `backend/services/keyword_analysis.py` — `flatten_profile(conn) -> str` joining summary + all experience bullets + skills + project descriptions + education highlights into one document; `extract_keywords(text, top_k=30) -> list[(term, score)]` via `TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, max_features=200)`; `compute_overlap(jd_text, profile_text) -> KeywordOverlap` returning matched, missing, jd_only, match_pct
- [x] 1.2: `KeywordOverlap` Pydantic model in `backend/models.py` (matched: list[str], missing: list[str], match_pct: float)
- [x] 1.3: `tests/test_keyword_analysis.py` — flatten covers all sections; overlap math correct on a synthetic JD/profile pair; English stopwords removed; bigram capture (e.g. "machine learning"); empty profile returns 0% match without crash

### Verification

- [ ] `pytest tests/test_keyword_analysis.py` passes
- [ ] Full suite green

---

## Phase 2: LLM scoring

Reuses `call_llm` from `backend/services/llm_client.py`.

### Tasks

- [x] 2.1: `backend/prompts/compatibility.py` — `COMPATIBILITY_SYSTEM` prompt with strict JSON schema; "score from profile evidence only — no fabricated achievements or unstated skills" rule; example output with realistic scores and 2–3 strengths/gaps/recommendations
- [x] 2.2: `CompatibilityScore` Pydantic model in `backend/models.py` — `overall_fit_score: int (0–10)`, `strengths: list[str]`, `gaps: list[str]`, `recommendations: list[str]`
- [x] 2.3: `backend/services/compat_scorer.py::score_compatibility(profile_text, jd_text, db_conn=None, application_id=None) -> tuple[CompatibilityScore, dict]` — uses Sonnet 4.6, prompt caching enabled, returns parsed model + usage_info; raises `LLMInvalidJSONError` on bad JSON or schema mismatch
- [x] 2.4: `tests/test_compat_scorer.py` — mocked LLM round-trip returns valid `CompatibilityScore`; invalid-JSON path raises; schema-mismatch path raises

### Verification

- [ ] `pytest tests/test_compat_scorer.py` passes
- [ ] Full suite green

---

## Phase 3: Applications repo + analysis route

### Tasks

- [x] 3.1: `backend/services/application_repo.py` — `create_application(conn, *, job_title, company, jd, analysis_json, profile_hash) -> str` (returns id via `secrets.token_urlsafe(8)`); `get_application(conn, id) -> Application | None`; `list_applications(conn) -> list[ApplicationSummary]` (id, job_title, company, score, created_at)
- [x] 3.2: `Application` and `ApplicationSummary` and `CompatibilityAnalysis` Pydantic models in `backend/models.py`. `CompatibilityAnalysis` wraps `KeywordOverlap` + `CompatibilityScore` for clean serialization
- [x] 3.3: `backend/routes/applications.py` — `GET /applications` (list page), `GET /applications/new` (form), `POST /applications` (validates inputs, runs keyword + LLM analysis, persists via `application_repo`, 303-redirects to results), `GET /applications/{id}` (results page; 404 if missing)
- [x] 3.4: Wire `applications.router` into `backend/main.py`; add "Applications" link to the sidebar in `backend/templates/layout.html` (above or below the profile section group, with active-state handling)

### Verification

- [ ] Manual: routes resolve, list page renders, posting a JD redirects to the results page
- [ ] Full suite green

---

## Phase 4: UI templates + gap nudge

### Tasks

- [x] 4.1: `backend/templates/applications/list.html` — table of past analyses (job title, company, fit score, created date); empty-state message when none; "Analyze new JD" button at top
- [x] 4.2: `backend/templates/applications/new.html` — form with `job_title`, `company`, `jd_text` (textarea, large); reuse the analyzing-spinner pattern from `profile/import.html` (button → "Analyzing…", spinner + "this usually takes 15–30 seconds" hint)
- [x] 4.3: `backend/templates/applications/show.html` — score header with fit-score badge; keyword overlap section (matched chips + missing chips); LLM strengths list; LLM gaps list; combined **Gap nudge** section (keyword gaps ∪ LLM gaps, deduped); recommendations list; AI cost line at the bottom
- [x] 4.4: `tests/test_applications_flow.py` — TestClient end-to-end: mock LLM, POST JD, follow redirect to result, assert overall score and a known gap term render; list page lists the new application

### Verification

- [ ] `pytest tests/test_applications_flow.py` passes
- [ ] Full suite green
- [ ] Manual browser test: paste a real JD, see analysis populate, gap nudge renders, cost logged

---

## Final Verification

- [ ] All acceptance criteria from spec.md met
- [ ] `pytest tests/` green (keyword_analysis, compat_scorer, applications_flow + existing suites)
- [ ] Manual end-to-end with a real JD: paste → see fit score → see keyword overlap → see LLM analysis → see gap nudge → see cost in `usage_log`
- [ ] Cost of a typical analysis logged and within expectation (~$0.01–0.03 with Sonnet)

---

_Tasks will be marked [~] in progress and [x] complete during implementation._
