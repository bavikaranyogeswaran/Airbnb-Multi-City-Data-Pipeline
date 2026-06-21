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

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .routes import (
    analytics, cities, cleaning, enrichment, familiarization,
    ingestion, llm, orchestration, quality, warehouse,
)
from src.validation import completion_gate as _gate

app = FastAPI(
    title="Inside Airbnb · Multi-City Pipeline",
    version="2.0.0",
    description=(
        "FastAPI surface over Familiarization, Ingestion & Profiling, "
        "Cleaning, Enrichment, Warehouse, Quality Tests, Orchestration, "
        "the Analytics layer (EDA + statistical analysis), "
        "the ML layer (price prediction + live inference), "
        "the Clustering layer (K-Means market segmentation), "
        "and the LLM layer (natural-language summaries via Groq). "
        "Covers London, Amsterdam, Madrid, and Berlin. "
        "Read endpoints serve generated artifacts; trigger endpoints "
        "re-run the underlying `run()` functions in-process."
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(cities.router)
app.include_router(familiarization.router)
app.include_router(ingestion.router)
app.include_router(cleaning.router)
app.include_router(enrichment.router)
app.include_router(warehouse.router)
app.include_router(quality.router)
app.include_router(orchestration.router)
app.include_router(analytics.router)
app.include_router(llm.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["meta"], summary="Liveness check")
def health() -> dict:
    return {"status": "ok"}


@app.get("/completion-gate", tags=["meta"],
         summary="Single-city completion gate — all 13 checklist items")
def completion_gate_check(city: str = Query("london")) -> dict:
    """Run all 13 Section-26 checklist items and return pass/warn/fail per check.

    gate_open=true means the city is ready to scale to additional cities.
    The full markdown report is also written to reports/completion_gate_<city>.md.
    """
    return _gate.run(city=city)


@app.get("/index", tags=["meta"], summary="Service index — what's wired up")
def index() -> dict:
    return {
        "service": app.title,
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "routers": {
            "cities":                "/cities",
            "familiarization":       "/familiarization",
            "ingestion":             "/ingestion",
            "cleaning":              "/cleaning",
            "enrichment":            "/enrichment",
            "warehouse":             "/warehouse",
            "quality":               "/quality",
            "orchestration":         "/orchestration",
            "analytics":             "/analytics",
            "analytics_ml":          "/analytics/ml",
            "analytics_clustering":  "/analytics/clustering",
            "llm":                   "/analytics/llm",
        },
    }
