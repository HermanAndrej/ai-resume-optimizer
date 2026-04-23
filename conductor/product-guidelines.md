# Product Guidelines

## Voice and Tone

**Concise and honest.** Factual, no hype. Every piece of copy — UI labels, feedback messages, error states — should match the grounded ethos of the product. Do not oversell outcomes. Do not soften bad news. Tell the user exactly what is happening and why.

Examples:
- Bad: "Your resume is looking great! Just a few tweaks and you'll be unstoppable."
- Good: "3 required keywords missing. ATS match: 62%. See gaps below."

## Design Principles

### Truthfulness over impressiveness
Never fabricate skills or metrics. Every generated resume is validated against the user's profile. Suggestions that would introduce content not present in the source profile are flagged and rejected before applying. If a suggestion is rejected, explain why.

### Simplicity over features
One profile. Per-job applications — each a self-contained workspace with analysis, chat, and versioning. No complexity. Every feature must directly serve tailoring or transparency — if it does neither, it does not belong in the product.

### Transparency
Show exactly:
- What keywords match and what gaps exist
- What changed in each resume version (diff view)
- Why a suggestion was rejected (when it would fabricate)
- The full version history — nothing disappears, everything is recoverable

## Domain Constraints (IT/SWE/AI specialization)

The tool is purpose-built for tech roles. All tailoring logic, ATS scoring, and advice must account for the following established domain knowledge. Full sources: [ATS Domain Knowledge](./domain/ats_domain_knowledge.md) and [Tech Resume Playbook 2026](./domain/tech_resume_playbook_2026.md).

### ATS behavior the tool must model correctly
- ATS systems **rank**, they do not auto-reject (the "75% rejection" myth is false)
- Only **knockout questions** (binary yes/no on application forms) truly auto-reject
- Keyword matching is exact-string first, then fuzzy (~2 Levenshtein edits); "CRM" won't match "customer relationship management"
- Advanced platforms (Workday, Greenhouse) use semantic matching (BERT-family embeddings) — the tool should flag both exact gaps and semantic gaps
- Typical ATS scoring weights: 40% skills, 20% experience years, 20% title similarity, 10% education, 10% location
- Target keyword match rate: **75%** (success can occur at 65%)
- Recruiter first-scan time: **7–11 seconds** — the above-the-fold content is what gets read

### Format rules for IT/SWE resumes
- **Single-column PDF** is the 2026 default — never suggest two-column or design-heavy templates
- Tables, text boxes, and headers/footers break Taleo and Workday parsers — never recommend them
- Design-tool PDFs (Canva, Illustrator) embed text as graphics — must warn against this
- Standard section headings only ("Work Experience," not "My Journey")

### AI/ML role-specific rules
- The **AI Engineer vs ML Engineer bifurcation** is real and consequential — do not conflate them
  - AI Engineer: LLM APIs, RAG, agents, evals, prompt pipelines
  - ML Engineer: training, fine-tuning, serving, MLOps, feature stores
- Warn users when their resume straddles both roles without committing (weakens both)
- AI experience inflation is actively screened: vague "built an AI agent" bullets are penalized — require specifics (stack, eval methodology, metrics with denominators)

### Authenticity guardrails
- Flag AI-generated language clichés: "spearheaded," "leveraged," "orchestrated," "pivotal," "intricate," "showcasing," "delve," "results-driven professional"
- Prompt injection hacks (hidden white text) are detected by Greenhouse Real Talent and Workday FAD — never suggest or generate them
- Enforce the XYZ bullet formula: Accomplished [X] as measured by [Y] by doing [Z]
- Metrics require denominators: "1M requests/day" not "1M requests"; "p95 480ms → 220ms" not "improved performance 50%"
