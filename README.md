# Resume Optimizer

Local personal app for tailoring resumes to job postings using your Anthropic API key. Maintains a structured profile as the source of truth; per-job mini-projects generate tailored resumes, compatibility analysis, and chat-based iteration — with zero fabrication.

## Setup

1. Clone: `git clone <repo>`
2. Install: `pip install -r requirements.txt`
3. Copy env: `cp .env.example .env`
4. Add your `ANTHROPIC_API_KEY` to `.env`
5. Run: `python run.py`

Browser opens automatically at http://127.0.0.1:8765.

Data is stored in your OS app data directory (never in the repo):
- Windows: `%APPDATA%\resume_optimizer\`
- macOS: `~/Library/Application Support/resume_optimizer/`
- Linux: `~/.local/share/resume_optimizer/`

## Optional: OCR support for scanned PDFs

Install [Tesseract](https://github.com/tesseract-ocr/tesseract) and [Poppler](https://poppler.freedesktop.org/):
- macOS: `brew install tesseract poppler`
- Ubuntu: `apt install tesseract-ocr poppler-utils`
- Windows: see the linked project pages

The app degrades gracefully if these are not installed.

## Optional: Direct LaTeX-to-PDF compilation

Install a TeX distribution:
- macOS: [MacTeX](https://www.tug.org/mactex/)
- Linux: `apt install texlive-full`
- Windows: [MiKTeX](https://miktex.org/)

## Development

```bash
pytest tests/          # run tests
python run.py          # start server on http://127.0.0.1:8765
```
