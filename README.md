# AI Resume Optimizer

Local personal tool for tailoring resumes to job postings. One profile, per-job workspaces with compatibility analysis, chat-based iteration, and versioned tailored resumes. Every generated resume is validated against your profile — no fabrication.

## Setup

1. Clone the repo
2. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate    # Windows
   source .venv/bin/activate # macOS / Linux
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your Anthropic API key:
   ```
   cp .env.example .env
   ```
4. Run:
   ```
   python run.py
   ```

Browser opens automatically at `http://127.0.0.1:8765`. The database is created on first run — no manual setup required.

## Requirements

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)
