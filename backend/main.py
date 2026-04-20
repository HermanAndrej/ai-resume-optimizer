from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes.profile import router as profile_router

app = FastAPI(title="Resume Optimizer")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.include_router(profile_router)
