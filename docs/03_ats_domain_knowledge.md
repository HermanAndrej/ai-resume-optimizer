# ATS Domain Knowledge — How Real Systems Work

This document provides the domain context for building the resume optimizer. It explains how actual Applicant Tracking Systems parse, score, and rank resumes, so the tool can give the user accurate and actionable advice.

## How ATS parsing works

### Text extraction pipeline

Every ATS processes resumes through: text extraction → section detection → field extraction → keyword indexing → scoring.

Most ATS vendors don't build their own parsers. They license from specialists:
- **Textkernel** (acquired Sovren): Processes 2B+ resumes/year across 29 languages. Recently added LLM-enhanced parsing reducing errors by ~30%.
- **DaXtra**: Powers Bullhorn. Strong multilingual support (40 languages).
- **RChilli and HireAbility**: Serve mid-market ATS platforms.
- **Workday and Greenhouse**: Use proprietary parsing engines.

### What gets parsed

Modern parsers extract up to 140 standardized fields per resume, stored as structured JSON/XML and indexed in Elasticsearch. Key fields: name, email, phone, job titles, employers, dates, education, degrees, skills, certifications, location.

### What breaks parsing

**File format matters enormously:**
- DOCX: Safest universal format. XML structure is directly readable.
- Text-based PDF (exported from Word/Google Docs): Works on modern systems.
- Design-tool PDF (Canva, Illustrator): Text often embedded as graphics — parsers get nothing or garbled output. This is the #1 cause of "invisible" applications.
- Scanned PDF: Requires OCR. Accuracy degrades with decorative fonts.

**Layout issues:**
- Single-column: Works everywhere.
- Two-column: Works on Greenhouse and Lever; breaks on Workday; fails on Taleo.
- Tables: Taleo scrambles cell contents. Workday merges cells into single strings. Even Greenhouse struggles with nested tables.
- Text boxes: Frequently ignored entirely.
- Headers/footers: Skipped by ~25% of platforms, including Workday and Taleo. Contact info placed in headers may never enter the system.

**Section headings:**
- Parsers match headings against dictionaries of known variants. "Work Experience," "Employment History," "Professional Experience" all map to the same category.
- Creative headers like "My Journey" or "Career Highlights" cause section detection failures, leaving content uncategorized and potentially unsearchable.

**Per Jobscan's testing: over 40% of resume rejections stem from formatting issues, not content.**

## How ATS scoring works

### Three mechanisms that coexist

**1. Knockout questions (binary pass/fail)**
- Attached to application forms, not resume content
- "Do you require visa sponsorship?" / "Do you have X years of experience?"
- Wrong answer → rejection folder. This is the ONLY mechanism that truly auto-rejects.

**2. Keyword matching (still the backbone)**
- Traditional: exact string matching — counts how many JD terms appear in the resume
- Fuzzy matching layer: Levenshtein distance within ~2 character edits, handles plurals and verb tenses
- Limitation: "customer relationship management" won't match "CRM." "Led" and "managed" are 5 edits apart and won't connect.

**3. Semantic matching (advanced platforms)**
- Transformer models (BERT, RoBERTa, Sentence-BERT) convert text to 768-dim vector embeddings
- Cosine similarity measures alignment between resume and JD vectors
- Understands that "P&L, budget allocation, resource planning, ROI" clusters with "financial management"
- Some systems build skill graphs that infer implicit competencies

### Typical scoring weights

Most systems use roughly:
- 40% skills match
- 20% years of experience
- 20% job title similarity
- 10% education/certifications
- 10% location/work authorization

Candidates receive scores on a 0-100 scale. Those scoring 70-100 typically advance to human review. Companies sometimes hire candidates with match rates as low as 40%.

### Keyword stuffing detection

Modern NLP-powered systems detect and penalize unnatural repetition. ResumeFlex testing (2025) confirmed that a resume with "project management" repeated 12 times scored LOWER than a natural version using contextual variations.

## The market landscape (2025-2026)

### Who uses what

97.8% of Fortune 500 companies use an ATS. Top 10 vendors control 51.1% of revenue.

**Enterprise (Fortune 500):**
- Workday: 39%+ market share
- SAP SuccessFactors: 13.2%
- iCIMS: 10.7%
- Oracle Taleo: declining but entrenched at legacy installations

**Broader market (12,000+ companies):**
- Greenhouse: 19.3% (dominant mid-market)
- Lever: 16.6%
- Workday: 15.9%
- iCIMS: 15.3%
- Ashby: fastest-growing challenger

### Platform-specific behaviors

**Taleo (Oracle)** — Strictest parser: DOCX only recommended, single column mandatory, no tables, no text boxes.

**Greenhouse** — Most forgiving: emphasizes human-driven evaluation via structured scorecards. Explicitly never uses AI to rate candidates or auto-reject.

**iCIMS** — Unique skill capture: extracts skills from entire document text, not just Skills section.

**Workday** — Expects standard section headings and chronological structure. Recently acquired Paradox for conversational AI.

**Lever** — CRM + ATS hybrid: manages both active "opportunities" and long-term "contacts."

### Identifying which ATS an employer uses

Career page URLs reveal the ATS:
- `[company].taleo.net` → Oracle Taleo
- `boards.greenhouse.io/[company]` → Greenhouse
- `[company].lever.co` → Lever
- `[company].icims.com` → iCIMS
- `[company].myworkdayjobs.com` → Workday
- `[company].smartrecruiters.com` → SmartRecruiters

## Myths vs reality

**MYTH: "75% of resumes are auto-rejected by ATS"**
REALITY: This statistic has no verifiable source. A November 2025 Enhancv study of 25 US recruiters found 92% confirmed their ATS does NOT auto-reject based on formatting, design, or content. ATS systems rank and sort — they don't reject. However, low-ranked candidates may never be reviewed when recruiters face 3× more applications per role than in 2022.

**MYTH: "ATS can't read PDFs"**
REALITY: All modern ATS systems can read text-based PDFs. The problem is design-tool PDFs where text is embedded as graphics. Test by selecting all text in the PDF, copying, and pasting into a text editor. If it's garbled, the ATS sees the same thing.

**MYTH: "You need special ATS resume templates"**
REALITY: Any clean, single-column resume with standard headings and no tables/text boxes works. The "template" industry is largely marketing.

**MYTH: "White text tricks fool ATS"**
REALITY: Most modern systems strip formatting and index raw text. Some explicitly detect and flag hidden text as manipulation.

## Key numbers for the tool

- Target keyword match rate: 75% (Jobscan recommendation; success can occur at 65%)
- Optimal prescreening questions before drop-off: ~6
- 46% of job seekers use ChatGPT to craft resumes (2025)
- 69% report higher response rates with AI-optimized resumes
- Average time recruiters spend on initial resume review: 6-7 seconds

## What makes advice actionable

When generating recommendations for the user, the most valuable output is:

1. **Specific missing keywords with context** — not just "add Python" but "the JD mentions 'Python' 3 times in the requirements section; your profile mentions it once in your skills list. Consider adding it to 1-2 bullet points in your experience section where you actually used it."

2. **Exact wording alignment** — "Your profile says 'data analysis' but the JD specifically asks for 'data analytics.' Use their exact term."

3. **Rewrite suggestions that stay truthful** — take an existing profile bullet and show how to naturally rephrase it using JD terminology without fabricating experience.

4. **Priority ranking** — required skills matter more than nice-to-haves. Hard skills (Python, AWS) matter more than soft skills (communication) for ATS scoring. Section placement matters — keywords in Experience are weighted more heavily than in a Skills list.

5. **Gap acknowledgment over gap hiding** — if the JD requires something the profile doesn't contain, explicitly flag it rather than trying to creatively paper over it. Honesty builds better applications than fabrication.
