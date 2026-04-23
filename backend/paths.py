import os
import sys
from pathlib import Path


def get_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "resume_optimizer"
    elif sys.platform == "win32":
        return Path(os.getenv("APPDATA", str(Path.home()))) / "resume_optimizer"
    else:
        xdg = os.getenv("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        return base / "resume_optimizer"


def get_db_path() -> Path:
    return get_data_dir() / "app.db"
