from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.routes import profile

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AI Resume Optimizer")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(profile.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
