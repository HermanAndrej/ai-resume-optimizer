from pathlib import Path

from fastapi.templating import Jinja2Templates

from backend.services.text_diff import word_diff

TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["word_diff"] = word_diff
