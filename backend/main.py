from fastapi import FastAPI

app = FastAPI(title="AI Resume Optimizer")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
