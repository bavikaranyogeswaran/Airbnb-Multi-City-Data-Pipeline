"""Data-quality test endpoints.

Triggers run the pytest suite in-process and persist results into the
warehouse's data_quality_result table. Reads expose past runs.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.validation import quality_tests

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("", summary="Quality index — endpoints available")
def quality_index() -> dict:
    return {
        "area": "Data Quality Checks as Code",
        "reads": {
            "runs":          "GET  /quality/runs?city=london&limit=20",
            "run_results":   "GET  /quality/runs/{run_id}?city=london",
            "latest":        "GET  /quality/latest?city=london",
        },
        "triggers": {
            "run":           "POST /quality/run?city=london",
        },
    }


@router.get("/runs", summary="Past quality runs with pass/fail counts")
def list_runs(city: str = Query("london"), limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    return quality_tests.list_runs(city, limit=limit)


@router.get("/runs/{run_id}", summary="Per-test results for one run")
def get_run(run_id: str, city: str = Query("london")) -> list[dict]:
    rows = quality_tests.get_results(city, run_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"run_id '{run_id}' not found")
    return rows


@router.get("/latest", summary="Per-test results from the most recent run")
def latest(city: str = Query("london")) -> list[dict]:
    rows = quality_tests.latest(city)
    if not rows:
        raise HTTPException(status_code=404, detail="no quality runs recorded yet")
    return rows


@router.post("/run", summary="Run the pytest data-quality suite (sync)")
def trigger_run(city: str = Query("london")) -> dict:
    return quality_tests.run(city=city)
