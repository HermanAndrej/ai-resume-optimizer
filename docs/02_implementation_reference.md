# Implementation Reference

## Dependencies

```
# requirements.txt
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
jinja2>=3.1.0
python-multipart>=0.0.9
anthropic>=0.40.0
pydantic>=2.6.0
pdfminer.six>=20231228
python-docx>=1.1.0
pytesseract>=0.3.10      # OCR fallback (optional)
pdf2image>=1.17.0        # OCR fallback (optional)
scikit-learn>=1.4.0
python-dotenv>=1.0.0
weasyprint>=61.0         # PDF export
```

SQLite is in the stdlib.

**System-level optional dependencies** (OCR only, graceful degrade if missing):
- `tesseract` (e.g., `apt install tesseract-ocr` or `brew install tesseract`)
- `poppler` (e.g., `apt install poppler-utils` or `brew install poppler`)
- `pdflatex` for direct LaTeX-to-PDF compilation (`texlive` on Linux, MacTeX on macOS)

## Entry Point (run.py)

Designed so anyone can clone-and-run. Handles setup in order: env check → data dir → DB migrations → server start → browser open.

```python
# run.py
import os
import sys
import sqlite3
import webbrowser
from pathlib import Path
from threading import Timer
from dotenv import load_dotenv

load_dotenv()

# --- Env check ---
if not os.getenv("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY is not set.")
    print("Copy .env.example to .env and add your key, then try again.")
    sys.exit(1)

# --- Data directory ---
from backend.paths import get_data_dir
data_dir = get_data_dir()
data_dir.mkdir(parents=True, exist_ok=True)

# --- Database migrations ---
from backend.db import run_migrations
db_path = data_dir / "app.db"
run_migrations(db_path)

# --- Browser open after server starts ---
HOST = "127.0.0.1"
PORT = 8765
def open_browser():
    webbrowser.open(f"http://{HOST}:{PORT}")
Timer(1.5, open_browser).start()

# --- Start server ---
import uvicorn
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
```

## App data directory (backend/paths.py)

```python
# backend/paths.py
import os
import sys
from pathlib import Path


def get_data_dir() -> Path:
    """Return the OS-appropriate app data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "resume_optimizer"
    elif sys.platform == "win32":
        return Path(os.getenv("APPDATA", Path.home())) / "resume_optimizer"
    else:  # Linux, BSD, etc.
        xdg = os.getenv("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        return base / "resume_optimizer"


def get_db_path() -> Path:
    return get_data_dir() / "app.db"


def get_latex_templates_dir() -> Path:
    """User's custom LaTeX templates live here. Created if missing."""
    d = get_data_dir() / "latex_templates"
    d.mkdir(parents=True, exist_ok=True)
    return d
```

## Database layer with auto-migrations (backend/db.py)

```python
# backend/db.py
import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version (version) VALUES (1);

CREATE TABLE profile (
    id INTEGER PRIMARY KEY,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    location TEXT,
    summary TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE profile_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    label TEXT,
    url TEXT,
    display_order INTEGER
);

CREATE TABLE experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    company TEXT,
    title TEXT,
    location TEXT,
    start_date TEXT,
    end_date TEXT,
    description TEXT,
    display_order INTEGER
);

CREATE TABLE experience_bullets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experience_id INTEGER REFERENCES experience(id) ON DELETE CASCADE,
    text TEXT,
    tags TEXT,
    display_order INTEGER
);

CREATE TABLE education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    institution TEXT,
    degree TEXT,
    field TEXT,
    start_date TEXT,
    end_date TEXT,
    gpa TEXT,
    highlights TEXT,
    display_order INTEGER
);

CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    category TEXT,
    skill TEXT,
    display_order INTEGER
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    tech_stack TEXT,
    url TEXT,
    bullets TEXT,
    display_order INTEGER
);

CREATE TABLE certifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT,
    issuer TEXT,
    date TEXT,
    url TEXT,
    display_order INTEGER
);

CREATE TABLE custom_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profile(id) ON DELETE CASCADE,
    name TEXT,
    content TEXT,
    display_order INTEGER
);

CREATE TABLE mini_projects (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    job_title TEXT,
    company TEXT,
    job_description TEXT,
    compatibility_analysis TEXT,
    profile_snapshot_hash TEXT,
    selected_model TEXT DEFAULT 'claude-sonnet-4-5-20250929',
    archived INTEGER DEFAULT 0
);

CREATE TABLE tailored_resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES mini_projects(id) ON DELETE CASCADE,
    version INTEGER,
    content TEXT,
    generation_notes TEXT,
    source TEXT,  -- 'generation', 'applied_suggestion', 'restore', 'manual_edit'
    parent_version INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES mini_projects(id) ON DELETE CASCADE,
    role TEXT,
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents REAL,
    model TEXT
);

CREATE TABLE pending_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES mini_projects(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    suggestion_type TEXT,
    target_section TEXT,
    current_value TEXT,
    proposed_value TEXT,
    rationale TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_memory (
    id INTEGER PRIMARY KEY DEFAULT 1,
    preferences TEXT,
    recurring_context TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (id = 1)
);

CREATE TABLE usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    project_id TEXT,
    operation TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents REAL
);

-- Seed profile row
INSERT INTO profile (id) VALUES (1);
"""


MIGRATIONS = {1: SCHEMA_V1}
# Future migrations: {2: "ALTER TABLE ...", 3: "..."}


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(db_path: Path) -> None:
    """Auto-run any unapplied migrations."""
    conn = get_connection(db_path)
    try:
        # Check if schema_version table exists
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()

        if not row:
            # Fresh DB — apply v1
            conn.executescript(SCHEMA_V1)
            conn.commit()
            current_version = 1
        else:
            current_version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0

        # Apply any newer migrations
        for version, sql in sorted(MIGRATIONS.items()):
            if version > current_version:
                conn.executescript(sql)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                conn.commit()
    finally:
        conn.close()


def get_db():
    """FastAPI dependency for DB access."""
    from .paths import get_db_path
    conn = get_connection(get_db_path())
    try:
        yield conn
    finally:
        conn.close()
```

## LLM client with typed errors and retries

```python
# backend/services/llm_client.py
import os
import time
import anthropic
from typing import Optional, Iterator
import sqlite3


client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL_PRICING = {
    # VERIFY at https://docs.claude.com/en/docs/about-claude/pricing
    "claude-haiku-4-5-20251001":   {"input": 1.00,  "output": 5.00},
    "claude-sonnet-4-5-20250929":  {"input": 3.00,  "output": 15.00},
}

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
VALIDATION_MODEL = "claude-haiku-4-5-20251001"


# --- Typed errors ---
class LLMError(Exception): pass
class LLMAuthError(LLMError): pass
class LLMRateLimitError(LLMError): pass
class LLMBudgetError(LLMError): pass
class LLMInvalidJSONError(LLMError):
    def __init__(self, raw_response: str):
        super().__init__(f"Invalid JSON in LLM response: {raw_response[:200]}...")
        self.raw_response = raw_response


def calculate_cost_cents(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return (input_cost + output_cost) * 100


def _log_usage(db_conn, project_id, operation, model, input_tokens, output_tokens):
    if not db_conn:
        return
    cost = calculate_cost_cents(model, input_tokens, output_tokens)
    db_conn.execute(
        """INSERT INTO usage_log (project_id, operation, model, input_tokens, output_tokens, cost_cents)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (project_id, operation, model, input_tokens, output_tokens, cost),
    )
    db_conn.commit()
    return cost


def call_llm(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    operation: str = "chat",
    project_id: Optional[str] = None,
    db_conn: Optional[sqlite3.Connection] = None,
    max_retries: int = 3,
) -> tuple[str, dict]:
    """Non-streaming call. Returns (response_text, usage_info)."""
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            in_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens
            cost = _log_usage(db_conn, project_id, operation, model, in_tok, out_tok)
            return response.content[0].text, {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_cents": cost,
                "model": model,
            }
        except anthropic.AuthenticationError:
            raise LLMAuthError("Invalid or missing API key. Check your .env file.")
        except anthropic.RateLimitError as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise LLMRateLimitError("Rate limit exceeded after retries. Try again shortly.")
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e).lower():
                raise LLMBudgetError("Your Anthropic account has insufficient credit.")
            raise LLMError(str(e))
        except anthropic.APIError as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise LLMError(str(e))

    raise LLMError(f"LLM call failed after {max_retries} retries: {last_error}")


def stream_llm(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 2048,
    operation: str = "chat",
    project_id: Optional[str] = None,
    db_conn: Optional[sqlite3.Connection] = None,
) -> Iterator[tuple[str, Optional[dict]]]:
    """
    Streaming call. Yields (text_chunk, usage_info).
    usage_info is None for intermediate chunks, dict on the final chunk.
    """
    try:
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text, None

            # Final message contains usage info
            final = stream.get_final_message()
            in_tok = final.usage.input_tokens
            out_tok = final.usage.output_tokens
            cost = _log_usage(db_conn, project_id, operation, model, in_tok, out_tok)
            yield "", {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cost_cents": cost,
                "model": model,
            }
    except anthropic.AuthenticationError:
        raise LLMAuthError("Invalid or missing API key.")
    except anthropic.RateLimitError:
        raise LLMRateLimitError("Rate limit exceeded.")
    except anthropic.APIError as e:
        raise LLMError(str(e))


def parse_llm_json(text: str) -> dict:
    """Parse JSON response, handling markdown fences and embedded blocks."""
    import json
    import re

    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        raise LLMInvalidJSONError(text)
```

## Profile hashing (for re-analysis)

```python
# backend/services/profile_hash.py
import hashlib
import json


def profile_hash(profile: dict) -> str:
    """Stable hash of the profile for detecting changes."""
    # Serialize with sorted keys for determinism
    serialized = json.dumps(profile, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def is_profile_stale(current_profile: dict, snapshot_hash: str) -> bool:
    return profile_hash(current_profile) != snapshot_hash
```

## Fabrication validation layer

```python
# backend/services/fabrication_check.py
import json
from .llm_client import call_llm, parse_llm_json, VALIDATION_MODEL


FABRICATION_CHECK_SYSTEM = """You are validating that a tailored resume contains only information traceable to the user's profile.

Compare the tailored resume against the profile. Identify any specific claims in the tailored resume that cannot be traced to the profile: skills, technologies, companies, job titles, dates, numbers, metrics, percentages, achievements.

Minor rewording of existing profile content is NOT a fabrication. Only flag items where the underlying fact/claim is absent from the profile.

Return ONLY valid JSON in this format:

{
  "fabricated_items": [
    {
      "item": "the specific claim that isn't in the profile",
      "location": "where in the resume it appears (e.g., 'experience[0].bullets[2]')",
      "reason": "brief explanation of what's missing from the profile"
    }
  ]
}

If nothing is fabricated, return: {"fabricated_items": []}
"""


def check_fabrication(profile: dict, tailored_resume: dict, db_conn, project_id: str = None) -> list[dict]:
    """Validation check. Returns list of fabricated items (empty if clean)."""
    user_msg = f"""PROFILE (ground truth):
{json.dumps(profile, indent=2)}

TAILORED RESUME (to validate):
{json.dumps(tailored_resume, indent=2)}

Check for fabrications."""

    text, _ = call_llm(
        model=VALIDATION_MODEL,  # Haiku — fast and cheap
        system=FABRICATION_CHECK_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=1024,
        operation="validation",
        project_id=project_id,
        db_conn=db_conn,
    )

    result = parse_llm_json(text)
    return result.get("fabricated_items", [])
```

## Export — PDF (weasyprint)

```python
# backend/services/export/pdf.py
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


_env = Environment(loader=FileSystemLoader("frontend/templates/resume"))


def export_pdf(resume: dict, template_name: str = "default.html") -> bytes:
    """Render resume to HTML then to PDF bytes."""
    template = _env.get_template(template_name)
    html_content = template.render(resume=resume)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
```

A minimal `frontend/templates/resume/default.html` template uses clean single-column layout optimized for ATS parsing (no tables, no multi-column, standard headings).

## Export — DOCX (python-docx)

```python
# backend/services/export/docx.py
from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches


def export_docx(resume: dict) -> bytes:
    doc = Document()

    # Margins
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Name
    personal = resume.get("personal_info", {})
    name_para = doc.add_paragraph()
    name_run = name_para.add_run(personal.get("full_name", ""))
    name_run.bold = True
    name_run.font.size = Pt(18)

    # Contact line
    contact_parts = []
    if personal.get("email"): contact_parts.append(personal["email"])
    if personal.get("phone"): contact_parts.append(personal["phone"])
    if personal.get("location"): contact_parts.append(personal["location"])
    for link in personal.get("links", []):
        contact_parts.append(link["url"])
    doc.add_paragraph(" | ".join(contact_parts))

    # Summary
    if resume.get("summary"):
        doc.add_heading("Summary", level=2)
        doc.add_paragraph(resume["summary"])

    # Experience
    if resume.get("experience"):
        doc.add_heading("Experience", level=2)
        for exp in resume["experience"]:
            p = doc.add_paragraph()
            p.add_run(f"{exp['title']}, {exp['company']}").bold = True
            dates = f"{exp.get('start_date', '')} – {exp.get('end_date', '')}"
            p.add_run(f"  |  {dates}")
            if exp.get("location"):
                p.add_run(f"  |  {exp['location']}")
            if exp.get("description"):
                doc.add_paragraph(exp["description"])
            for bullet in exp.get("bullets", []):
                doc.add_paragraph(bullet, style="List Bullet")

    # Education
    if resume.get("education"):
        doc.add_heading("Education", level=2)
        for edu in resume["education"]:
            p = doc.add_paragraph()
            p.add_run(f"{edu['degree']} in {edu['field']}, {edu['institution']}").bold = True
            dates = f"{edu.get('start_date', '')} – {edu.get('end_date', '')}"
            p.add_run(f"  |  {dates}")
            if edu.get("gpa"):
                p.add_run(f"  |  GPA: {edu['gpa']}")

    # Skills
    skills = resume.get("skills", {})
    if skills.get("categorized"):
        doc.add_heading("Skills", level=2)
        for category, skill_list in skills["categorized"].items():
            p = doc.add_paragraph()
            p.add_run(f"{category}: ").bold = True
            p.add_run(", ".join(skill_list))

    # Projects, certifications, custom sections — same pattern

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

## Export — LaTeX

Placeholder for now — needs the user's template attached.

```python
# backend/services/export/latex.py
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import subprocess
import tempfile


# Custom Jinja env with LaTeX-safe delimiters
# (default {{ }} conflicts with LaTeX, so we use << >>)
_latex_env = Environment(
    block_start_string="<%",
    block_end_string="%>",
    variable_start_string="<<",
    variable_end_string=">>",
    comment_start_string="<#",
    comment_end_string="#>",
    loader=FileSystemLoader("templates/latex"),
    autoescape=False,
)

# Add LaTeX-escape filter
def latex_escape(text: str) -> str:
    """Escape characters that have special meaning in LaTeX."""
    if not isinstance(text, str):
        return str(text)
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "^": r"\^{}",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "%": r"\%",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


_latex_env.filters["e"] = latex_escape


def export_latex(resume: dict, template_name: str = "default.tex") -> str:
    """Render the resume into a .tex file."""
    template = _latex_env.get_template(template_name)
    return template.render(resume=resume)


def compile_latex_to_pdf(tex_content: str) -> bytes:
    """Optional — shell out to pdflatex. Raises if pdflatex isn't installed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(tex_content)

        # Run pdflatex twice for refs
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, str(tex_path)],
                capture_output=True, text=True
            )
        if result.returncode != 0:
            raise RuntimeError(f"pdflatex failed:\n{result.stdout}")

        pdf_path = Path(tmpdir) / "resume.pdf"
        return pdf_path.read_bytes()
```

Once you attach the LaTeX example, we'll add:
- `templates/latex/default.tex` matching the user's format
- Specific variable placeholders (`<<resume.personal_info.full_name | e>>`, etc.)

## Streaming chat endpoint (FastAPI)

```python
# backend/routes/chat.py
from fastapi import APIRouter, Depends, Form
from fastapi.responses import StreamingResponse
from ..db import get_db
from ..services import chat_service
import json

router = APIRouter(prefix="/api/projects")


@router.post("/{project_id}/chat/stream")
async def chat_stream(project_id: str, message: str = Form(...), db=Depends(get_db)):
    """Stream chat response. Saves full message + suggestions on completion."""

    def event_stream():
        full_response = ""
        usage = None

        try:
            for chunk, chunk_usage in chat_service.chat_stream(project_id, message, db):
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                if chunk_usage:
                    usage = chunk_usage

            # After stream ends, parse suggestions and save everything
            suggestions = chat_service.extract_and_save_suggestions(
                project_id, full_response, usage, db
            )
            yield f"data: {json.dumps({'type': 'done', 'suggestions': suggestions, 'usage': usage})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Frontend (HTMX or vanilla JS) consumes the SSE stream and appends chunks to the chat display.

## Restore version (creates new version, non-destructive)

```python
# backend/routes/versions.py
@router.post("/{project_id}/versions/{version_id}/restore")
async def restore_version(project_id: str, version_id: int, db=Depends(get_db)):
    old_version = db.execute(
        "SELECT content, version FROM tailored_resumes WHERE id = ? AND project_id = ?",
        (version_id, project_id)
    ).fetchone()
    if not old_version:
        raise HTTPException(404, "Version not found")

    max_v = db.execute(
        "SELECT MAX(version) FROM tailored_resumes WHERE project_id = ?", (project_id,)
    ).fetchone()[0] or 0

    db.execute(
        """INSERT INTO tailored_resumes (project_id, version, content, source, parent_version)
           VALUES (?, ?, ?, 'restore', ?)""",
        (project_id, max_v + 1, old_version["content"], old_version["version"])
    )
    db.commit()
    return {"new_version": max_v + 1}
```

## Profile gap nudge

The analysis result surfaces missing skills. The UI shows:

> "The job description requires: Docker, AWS, Kubernetes. Your profile doesn't list these. If you actually have this experience, add it to your profile — we won't make anything up."
>
> [Add to Profile] button → opens the profile editor pre-filled with the missing skills as a quick-add form.

Implementation:

```python
# backend/routes/profile.py
@router.post("/quick_add_skills")
async def quick_add_skills(
    skills: list[str] = Body(...),
    category: str = Body(default="Uncategorized"),
    db=Depends(get_db),
):
    """Add skills from the gap nudge."""
    profile = db.execute("SELECT id FROM profile LIMIT 1").fetchone()
    profile_id = profile["id"]

    max_order = db.execute(
        "SELECT COALESCE(MAX(display_order), 0) FROM skills WHERE profile_id = ?",
        (profile_id,)
    ).fetchone()[0]

    for i, skill in enumerate(skills):
        db.execute(
            "INSERT INTO skills (profile_id, category, skill, display_order) VALUES (?, ?, ?, ?)",
            (profile_id, category, skill, max_order + i + 1)
        )
    db.commit()
    return {"added": len(skills)}
```

## Tests

```python
# tests/test_keyword_analyzer.py
from backend.services.keyword_analyzer import analyze_keywords


def test_missing_keywords_detected():
    profile = "Python developer with 5 years of ML experience"
    jd = "Looking for Python developer with AWS and Kubernetes"
    result = analyze_keywords(profile, jd)
    missing = [k["keyword"] for k in result["missing_keywords"]]
    assert "aws" in missing
    assert "kubernetes" in missing


def test_matched_keywords():
    profile = "Python developer"
    jd = "Python developer needed"
    result = analyze_keywords(profile, jd)
    assert result["keyword_score"] > 50
    matched = [k["keyword"] for k in result["matched_keywords"]]
    assert "python" in matched
```

```python
# tests/test_suggestion_apply.py
from backend.services.suggestion_apply import apply_suggestion


def test_rewrite_summary():
    resume = {"summary": "Old", "experience": []}
    s = {"type": "rewrite_summary", "target": "summary", "current": "Old", "proposed": "New"}
    result = apply_suggestion(resume, s)
    assert result["summary"] == "New"
    # Original not mutated
    assert resume["summary"] == "Old"


def test_replace_bullet_nested_path():
    resume = {
        "experience": [
            {"bullets": ["old bullet", "other"]},
        ]
    }
    s = {
        "type": "replace_bullet",
        "target": "experience[0].bullets[0]",
        "current": "old bullet",
        "proposed": "new bullet"
    }
    result = apply_suggestion(resume, s)
    assert result["experience"][0]["bullets"][0] == "new bullet"
    assert result["experience"][0]["bullets"][1] == "other"
```

```python
# tests/test_llm_json_parse.py
from backend.services.llm_client import parse_llm_json, LLMInvalidJSONError
import pytest


def test_plain_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_markdown_fenced():
    text = '```json\n{"a": 1}\n```'
    assert parse_llm_json(text) == {"a": 1}


def test_embedded_json():
    text = 'Here is the result:\n```\n{"a": 1}\n```\nHope this helps.'
    assert parse_llm_json(text) == {"a": 1}


def test_invalid_raises():
    with pytest.raises(LLMInvalidJSONError):
        parse_llm_json("not json at all")
```

## .env.example

```
# Copy this file to .env and fill in your values
ANTHROPIC_API_KEY=your_api_key_here
```

## .gitignore

```
.env
*.db
__pycache__/
*.pyc
.venv/
venv/
dist/
*.egg-info/
.pytest_cache/
data/
```

## README structure (sketch)

```markdown
# Resume Optimizer

Local personal app for tailoring resumes to job postings using your Anthropic API key.

## Setup

1. Clone: `git clone <repo>`
2. Install: `pip install -r requirements.txt`
3. Copy env: `cp .env.example .env`
4. Add your `ANTHROPIC_API_KEY` to `.env`
5. Run: `python run.py`

Browser opens automatically at http://127.0.0.1:8765.

## Optional: OCR support for scanned PDFs
Install tesseract and poppler (see OS instructions below).

## Optional: Direct LaTeX-to-PDF compilation
Install a TeX distribution (texlive / MacTeX).
```
