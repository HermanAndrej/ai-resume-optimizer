# LaTeX Template Reference

This documents the user's preferred LaTeX resume format. The template lives at `templates/latex/default.tex` and is rendered using Jinja2 with LaTeX-safe delimiters (`<<var>>` for variables, `<% block %>` for control flow, `<# #>` for comments — chosen to avoid collision with LaTeX's own `{}` and `%`).

## Template structure

The user's resume follows this structure:

1. **Preamble** — A4 paper, `fullpage` + custom geometry (0.6in margins all sides), hyperref, fontenc, custom macros
2. **Custom commands**:
   - `\hl{#1}` — bold highlight (used for metrics, technologies, key phrases)
   - `\header{#1}` — section heading in small caps with a horizontal rule underneath
   - `\contact{#1}{#2}{#3}` — centered name + two contact lines
   - `\school`, `\schoolwithcourses`, `\employer` — helpers (though the user currently inlines education/experience)
3. **Sections** in this order:
   - Centered name + contact line
   - Professional Summary
   - Education
   - Work Experience (multiple entries, newest first)
   - Technical Skills (two-column `tabular`)
   - Projects

## Content patterns to preserve

### Experience entry pattern
```latex
\textbf{Company} \hfill Location\\
\textit{Title} \hfill Start -- End\\
\vspace{-1mm}
\begin{itemize} \itemsep 1pt
    \item First bullet with \hl{highlighted metrics} and context.
    \item Second bullet...
\end{itemize}
```

### Project entry pattern
```latex
\textbf{Project Name} \hl{{\sl Tech, Stack, Listed}} \hfill \href{url}{\hl{github.com/user/repo}}\\
\begin{itemize} \itemsep 1pt
    \item Bullet describing the project...
\end{itemize}
\vspace*{2mm}
```

### Skills table pattern
```latex
\begin{tabular}{ l l }
    \textbf{Category:} & Skill1, Skill2, Skill3 \\
    \textbf{Category:} & ... \\
\end{tabular}
```

## Jinja2-rendered template

File: `templates/latex/default.tex`

```latex
\documentclass[a4paper]{article}
\usepackage{fullpage}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{textcomp}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{hyperref}
\textheight=10in
\pagestyle{empty}
\raggedright
\usepackage[left=0.6in,right=0.6in,bottom=0.6in,top=0.6in]{geometry}

\newcommand{\hl}[1]{\textbf{#1}}

\def\bull{\vrule height 0.8ex width .7ex depth -.1ex }

\newcommand{\area} [2] {
    \vspace*{-9pt}
    \begin{verse}
        \textbf{#1}   #2
    \end{verse}
}

\newcommand{\lineunder} {
    \vspace*{-8pt} \\
    \hspace*{-18pt} \hrulefill \\
}

\newcommand{\header} [1] {
    {\hspace*{-18pt}\vspace*{6pt} \textsc{#1}}
    \vspace*{-6pt} \lineunder
}

\newcommand{\contact} [3] {
    \vspace*{-10pt}
    \begin{center}
        {\Huge \scshape {#1}}\\
        #2 \\ #3
    \end{center}
    \vspace*{-8pt}
}

\newenvironment{achievements}{
    \begin{list}
        {$\bullet$}{\topsep 0pt \itemsep -2pt}}{\vspace*{4pt}
    \end{list}
}

\begin{document}
\vspace*{-40pt}

<# ==== Contact header ==== #>
\vspace*{-10pt}
\begin{center}
    {\Huge \scshape {<< resume.personal_info.full_name | e >>}}\\
    << resume.personal_info.location | e >>
    <% if resume.personal_info.email %> $\cdot$ << resume.personal_info.email | e >><% endif %>
    <% if resume.personal_info.phone %> $\cdot$ << resume.personal_info.phone | e >><% endif %>
    <% for link in resume.personal_info.links %> $\cdot$ \href{<< link.url >>}{<< link.label | e >>}<% endfor %>\\
\end{center}

<# ==== Professional Summary ==== #>
<% if resume.summary %>
\header{Professional Summary}
\vspace{1mm}
<< resume.summary | e >>
\vspace{2mm}
<% endif %>

<# ==== Education ==== #>
<% if resume.education %>
\header{Education}
<% for edu in resume.education %>
\textbf{<< edu.institution | e >>}\hfill <% if edu.location %><< edu.location | e >><% endif %>\\
<< edu.degree | e %> in << edu.field | e >> \hfill
<% if edu.end_date %>Graduated: << edu.end_date | e >><% elif edu.start_date %>Started: << edu.start_date | e >><% endif %>\\
<% if edu.gpa %>GPA: << edu.gpa | e >>\\<% endif %>
<% if edu.highlights %>
\begin{itemize} \itemsep 1pt
<% for h in edu.highlights %>    \item << h | e >>
<% endfor %>
\end{itemize}
<% endif %>
\vspace{2mm}
<% endfor %>
<% endif %>

<# ==== Work Experience ==== #>
<% if resume.experience %>
\header{Work Experience}
\vspace{1mm}

<% for exp in resume.experience %>
\textbf{<< exp.company | e >>} \hfill <% if exp.location %><< exp.location | e >><% endif %>\\
\textit{<< exp.title | e >>} \hfill << exp.start_date | e >> -- << exp.end_date | e >>\\
<% if exp.description %><< exp.description | e >>\\<% endif %>
\vspace{-1mm}
<% if exp.bullets %>
\begin{itemize} \itemsep 1pt
<% for bullet in exp.bullets %>    \item << bullet | latex_highlight >>
<% endfor %>
\end{itemize}
<% endif %>

<% endfor %>
<% endif %>

<# ==== Technical Skills ==== #>
<% if resume.skills and resume.skills.categorized %>
\header{Technical Skills}
\begin{tabular}{ l l }
<% for category, skill_list in resume.skills.categorized.items() %>    \textbf{<< category | e >>:} & << skill_list | join(', ') | e >> \\
<% endfor %>
\end{tabular}
<% endif %>

<# ==== Projects ==== #>
<% if resume.projects %>
\header{Projects}

<% for proj in resume.projects %>
\textbf{<< proj.name | e >>}
<% if proj.tech_stack %> \hl{{\sl << proj.tech_stack | join(', ') | e >>}}<% endif %>
<% if proj.url %> \hfill \href{<< proj.url >>}{\hl{<< proj.url | strip_protocol | e >>}}<% endif %>\\
<% if proj.description %><< proj.description | e >>\\<% endif %>
<% if proj.bullets %>
\begin{itemize} \itemsep 1pt
<% for bullet in proj.bullets %>    \item << bullet | latex_highlight >>
<% endfor %>
\end{itemize}
<% endif %>
\vspace*{2mm}

<% endfor %>
<% endif %>

<# ==== Certifications ==== #>
<% if resume.certifications %>
\header{Certifications}
\begin{itemize} \itemsep 1pt
<% for cert in resume.certifications %>    \item \textbf{<< cert.name | e >>} -- << cert.issuer | e >><% if cert.date %> (<< cert.date | e >>)<% endif %>
<% endfor %>
\end{itemize}
<% endif %>

<# ==== Custom Sections ==== #>
<% for section in resume.custom_sections %>
\header{<< section.name | e >>}
<< section.content | e >>
\vspace{2mm}
<% endfor %>

\end{document}
```

## Required Jinja2 filters

The template uses three custom filters that must be registered on the environment:

### `e` — LaTeX escape
Escapes special LaTeX characters (`\`, `{`, `}`, `$`, `&`, `#`, `^`, `_`, `~`, `%`). Already shown in the implementation reference.

### `latex_highlight` — Automatic `\hl{}` wrapping for metrics/keywords
The user's existing resume uses `\hl{}` extensively to bold key phrases (e.g., `\hl{$\sim$2$\times$ workflow acceleration}`, `\hl{Python}`, `\hl{5,000 candidates/month}`). This filter takes a bullet string and wraps specific patterns in `\hl{}`:

```python
import re

HIGHLIGHT_PATTERNS = [
    # Percentages and numeric values with ~
    r"(\$?\~?\$?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:\\?%|\\times|x|/month|/week|\+)?)",
    # Technologies commonly highlighted (user-configurable list)
    # Add more as needed
]


def latex_highlight(text: str) -> str:
    """Wrap patterns like metrics and percentages in \\hl{}."""
    # First, escape LaTeX specials
    text = latex_escape(text)
    # Then wrap numeric patterns (already-escaped) in \hl{}
    # Note: this runs after escaping, so patterns must match escaped forms
    # This is a starting point — the LLM can also include \hl{} markers directly in profile data
    return text
```

**Important design note**: rather than trying to auto-detect what to highlight (fragile), the recommended approach is:
1. The LLM that generates the tailored resume is instructed to include `\hl{...}` markers directly in bullet text for emphasis
2. The filter just passes these through after escaping other LaTeX specials
3. The user's profile data can itself contain `\hl{}` markers which are preserved

This is simpler and gives the LLM control over emphasis based on the specific JD.

### `strip_protocol` — Display-friendly URLs
Takes `https://github.com/HermanAndrej/AI-Quiz-App` and returns `github.com/HermanAndrej/AI-Quiz-App` for display purposes. The `\href{}` still uses the full URL.

```python
def strip_protocol(url: str) -> str:
    return re.sub(r"^https?://(?:www\.)?", "", url)
```

## LaTeX-safe Jinja2 environment setup

```python
# backend/services/export/latex.py
from jinja2 import Environment, FileSystemLoader
import re


def latex_escape(text):
    """Escape LaTeX special characters. Preserves existing \\hl{} markers."""
    if not isinstance(text, str):
        return str(text)

    # Protect existing \hl{...} markers from escaping
    protected = []
    def protect(match):
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = re.sub(r"\\hl\{[^}]*\}", protect, text)

    # Escape specials
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

    # Restore protected \hl{} markers (but escape their contents properly)
    for i, hl_text in enumerate(protected):
        # Re-escape inside \hl{...} without the recursive protection
        inner = hl_text[4:-1]  # Strip \hl{ and }
        inner_escaped = inner
        for old, new in replacements.items():
            if old not in ["{", "}"]:  # Don't escape the braces we need
                inner_escaped = inner_escaped.replace(old, new)
        text = text.replace(f"\x00{i}\x00", f"\\hl{{{inner_escaped}}}")

    return text


def strip_protocol(url):
    return re.sub(r"^https?://(?:www\.)?", "", url)


def latex_highlight(text):
    """Passes through. LLM-provided \\hl{} markers are preserved by latex_escape."""
    return latex_escape(text)


def build_latex_env(template_dir: str):
    env = Environment(
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="<<",
        variable_end_string=">>",
        comment_start_string="<#",
        comment_end_string="#>",
        loader=FileSystemLoader(template_dir),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["e"] = latex_escape
    env.filters["strip_protocol"] = strip_protocol
    env.filters["latex_highlight"] = latex_highlight
    return env
```

## LLM prompt addition for LaTeX emphasis

When generating the tailored resume, the system prompt should include:

> "For bullets that will be rendered in LaTeX format, you may wrap specific metrics, technologies, or key phrases in `\hl{}` markers to emphasize them (e.g., `'Automated \hl{70%} of the sourcing lifecycle using \hl{Python} and \hl{Claude API}'`). Use this sparingly — only for the most impactful metrics and highest-priority keywords from the JD. Never over-highlight."

This keeps LaTeX-specific formatting logic in the LLM where it can be context-aware, rather than in fragile regex rules.

## Template variants

Keep one template as `default.tex` matching the user's existing style. Additional templates can live alongside:

- `default.tex` — user's current style (0.6in margins, small-caps headers, horizontal rules)
- `compact.tex` — tighter spacing for long resumes
- `traditional.tex` — more conservative formatting

User selects template in export UI; each is a Jinja2 template with the same variable interface so any resume data works with any template.

## Compilation notes

- User has `pdflatex` on their machine (implied by LaTeX workflow)
- App can offer "Export .tex" (always works) and "Export .pdf via pdflatex" (requires local TeX)
- If `pdflatex` fails, show the log output in the UI and offer the raw `.tex` for manual compilation
- Run `pdflatex` twice in sequence to resolve any references (standard LaTeX practice)

## Testing the template

A sanity test with the user's actual resume data should produce output matching the current PDF closely. Add a fixture test:

```python
# tests/test_latex_export.py
import json
from pathlib import Path
from backend.services.export.latex import export_latex

def test_user_resume_renders():
    fixture = json.loads(Path("tests/fixtures/andrej_resume.json").read_text())
    tex = export_latex(fixture, template_name="default.tex")
    assert "Andrej Herman" in tex
    assert "\\documentclass" in tex
    assert "\\hl{" in tex  # highlights preserved
    # Should compile cleanly (manual verification first time)
```
