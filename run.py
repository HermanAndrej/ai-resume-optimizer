import os
import sys
import webbrowser
from pathlib import Path
from threading import Timer

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY is not set.")
    print("Copy .env.example to .env and add your key, then try again.")
    sys.exit(1)

from backend.paths import get_data_dir, get_db_path
from backend.db import run_migrations

data_dir = get_data_dir()
data_dir.mkdir(parents=True, exist_ok=True)

run_migrations(get_db_path())

HOST = "127.0.0.1"
PORT = 8765


def _open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}")


Timer(1.5, _open_browser).start()

import uvicorn
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
