import os
import sys
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
