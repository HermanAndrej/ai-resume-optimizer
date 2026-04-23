import os
import sys
import webbrowser
from threading import Timer

from dotenv import load_dotenv

HOST = "127.0.0.1"
PORT = 8765


def main() -> None:
    load_dotenv()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        print("Copy .env.example to .env and add your key, then try again.")
        sys.exit(1)

    # Deferred imports so a missing API key exits fast without loading heavy deps.
    from backend.paths import get_data_dir, get_db_path
    from backend.db import run_migrations

    get_data_dir().mkdir(parents=True, exist_ok=True)
    run_migrations(get_db_path())

    Timer(1.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()

    import uvicorn
    from backend.main import app

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
