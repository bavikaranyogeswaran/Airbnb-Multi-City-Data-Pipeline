"""FastAPI application — the canonical interface to the pipeline.

From now on every phase step is built as a FastAPI endpoint. The CLI
wrappers (`python -m src.X.Y`) still exist for shell users; they call
the same `run()` functions.

Run:
    uvicorn src.api.app:app --reload --port 8000

Docs:
    http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .routes import cities, cleaning, familiarization, ingestion

app = FastAPI(
    title="Inside Airbnb · London Pipeline",
    version="0.3.0",
    description=(
        "FastAPI surface over Dataset Familiarization, Ingestion & "
        "Profiling, and Cleaning & Standardization. Read endpoints serve "
        "generated artifacts; trigger endpoints re-run the underlying "
        "`run()` functions in-process. Heavy steps may block 1–2 min."
    ),
)


app.include_router(cities.router)
app.include_router(familiarization.router)
app.include_router(ingestion.router)
app.include_router(cleaning.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["meta"], summary="Liveness check")
def health() -> dict:
    return {"status": "ok"}


@app.get("/index", tags=["meta"], summary="Service index — what's wired up")
def index() -> dict:
    return {
        "service": app.title,
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "routers": {
            "cities":            "/cities",
            "familiarization":   "/familiarization",
            "ingestion":         "/ingestion",
            "cleaning":          "/cleaning",
        },
    }
