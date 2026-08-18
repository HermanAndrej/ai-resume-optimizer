from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes.profile import router as profile_router
from .routes.imports import router as imports_router
from .routes.analysis import router as analysis_router

app = FastAPI(title="Resume Optimizer")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.include_router(profile_router)
app.include_router(imports_router)
app.include_router(analysis_router)
