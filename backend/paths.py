import os
import sys
from pathlib import Path


def get_data_dir() -> Path:
    """Return the OS-appropriate app data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "resume_optimizer"
    elif sys.platform == "win32":
        return Path(os.getenv("APPDATA", Path.home())) / "resume_optimizer"
    else:
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
