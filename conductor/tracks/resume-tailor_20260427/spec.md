# Specification: Tailored Resume Generation

**Track ID:** `resume-tailor_20260427`
**Type:** Feature
**Created:** 2026-04-27
**Status:** Draft

## Summary

Generate a job-specific tailored resume from the user's profile and a saved application's JD, using a strict no-fabrication system prompt and a deterministic validation layer that flags any claim in the output not traceable to the source profile.

## Context

This track delivers the headline product capability called out in `product.md`:

> **Goal 1**: Enable honest, grounded resume tailoring. Let job seekers tailor resumes to specific job descriptions by reordering, potentially adding, emphasizing, and omitting profile content — but never fabricating. Every generated resume is validated to ensure it stays truthful.

Profile data and applications already exist (`compat-analysis_20260426`, `app-workspace_20260427`). We now need a service that produces tailored versions per application and a validator that catches hallucinations before the user sees them as "approved" output.

## User Story

As a tech job applicant, I want to click a button on an application's page and get a tailored version of my resume that emphasizes JD-relevant experience, with any unverifiable claim clearly flagged, so that I can submit honest, targeted applications without rewriting from scratch.

## Acceptance Criteria

- [ ] On an application's show page, a "Generate tailored resume" action runs an LLM generation using the profile + saved JD
- [ ] The system prompt explicitly forbids inventing companies, titles, skills, technologies, metrics, dates, or achievements not present in the source profile
- [ ] LLM output is structured (Pydantic) with a tailored summary, reordered/rephrased experience entries (each bullet optionally carrying a `source_bullet_id`), an ordered skills list, and selected projects
- [ ] A validation layer checks every company, title, school, certification, project, and skill in the output against the source profile and flags any unverifiable item as an error
- [ ] Numeric/percentage/dollar claims in tailored bullets are extracted and flagged (warning) if they don't appear in any source bullet text
- [ ] Tailored resumes are saved per-application in a new `tailored_resumes` table with a foreign key to applications; multiple versions per application are kept (not overwritten)
- [ ] The latest tailored resume is rendered on its own page with a clear "needs review" banner listing every flagged issue (error or warning) with a span/locator
- [ ] Generation cost is logged via `usage_log` and shown on the page like other AI calls
- [ ] If the source profile changes after generation, the tailored resume is marked stale (same hash mechanism as compatibility analysis)

## Dependencies

Depends on existing code:
- `flatten_profile` and full profile repos (from `compat-analysis_20260426`)
- `call_llm` from `backend/services/llm_client.py`
- `compute_profile_hash` from `compat_runner.py`
- Application data (`application_repo`)

## Out of Scope

- PDF / DOCX export of the tailored resume (separate track)
- Inline editing of generated resume fields (read-only initially; user can regenerate)
- Cover letter generation
- Per-bullet regeneration / partial regeneration
- Side-by-side diff view of multiple versions
- LLM-based validator (a "verifier" second LLM pass) — v1 uses deterministic checks only
- Auto-publishing tailored content back into the source profile

## Technical Notes

- **Generation model**: Sonnet 4.6 (quality task, like compatibility scoring). Reuses prompt-cache plumbing already in `llm_client`.
- **Validation strategy** (v1, deterministic only):
  - Build an "allowed claim index" from `flatten_profile` + raw entry rows: companies, titles, schools, certifications, project names, skills (case-insensitive set membership)
  - Each tailored experience entry: company + title + dates must match a source experience entry exactly (case-insensitive, trimmed). Date drift is a warning, identity mismatch is an error.
  - Each tailored skill must appear in source skills (warning if not — could be a synonym, but flag it)
  - Each tailored bullet: extract numbers (`\d+(?:\.\d+)?%?`, currency, year ranges) and verify each numeric token appears in *some* source bullet's text or in the experience description. Missing numerics → warning.
  - `source_bullet_id` (when provided) is verified against actual bullet IDs in the database
- **Storage**: New `tailored_resumes` table, `content_json` (TailoredResume), `validation_json` (list[ValidationIssue]), `profile_hash`, `created_at`, `cost_cents`. Multiple rows per application, ordered by created_at DESC.
- **Stale detection**: Same SHA-256 profile hash as compatibility analysis — reuse `compute_profile_hash` and `is_stale_for` patterns.
- **Output structure**:
  ```python
  class TailoredBullet(BaseModel):
      text: str
      source_bullet_id: int | None = None
  class TailoredExperience(BaseModel):
      company: str
      title: str
      location: str = ""
      start_date: str = ""
      end_date: str = ""
      bullets: list[TailoredBullet]
  class TailoredResume(BaseModel):
      summary: str
      experience: list[TailoredExperience]
      skills: list[str]
      selected_projects: list[str] = Field(default_factory=list)
  class ValidationIssue(BaseModel):
      severity: str  # "error" | "warning"
      category: str  # "unknown_company" | "unknown_title" | ...
      message: str
      location: str  # e.g. "experience[0].bullets[2]"
  ```

---

_Generated by Conductor. Review and edit as needed._
