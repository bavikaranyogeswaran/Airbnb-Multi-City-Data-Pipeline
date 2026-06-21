"""Data-quality test endpoints.

Triggers run the pytest suite in-process and persist results into the
warehouse's data_quality_result table. Reads expose past runs.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.validation import ge_runner, quality_tests

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("", summary="Quality index — endpoints available")
def quality_index() -> dict:
    return {
        "area": "Data Quality Checks as Code",
        "reads": {
            "runs":             "GET  /quality/runs?city=london&limit=20",
            "run_results":      "GET  /quality/runs/{run_id}?city=london",
            "latest":           "GET  /quality/latest?city=london",
            "ge_summary":       "GET  /quality/ge-summary?city=london",
            "ge_results":       "GET  /quality/ge-results?city=london",
        },
        "triggers": {
            "run":              "POST /quality/run?city=london",
            "ge_validate":      "POST /quality/ge-validate?city=london",
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


@router.post(
    "/ge-validate",
    summary="Run Great Expectations validation on processed parquets",
)
def ge_validate(city: str = Query("london")) -> dict:
    """
    Validates listing_master.parquet, calendar_clean.parquet, and
    reviews_clean.parquet against pre-defined expectation suites using
    an ephemeral Great Expectations context (no project files needed).

    Results are written to reports/ge_validation/{city}_results.json and
    reports/ge_validation/{city}_summary.json.
    """
    return ge_runner.run(city=city)


@router.get("/ge-summary", summary="Latest GE validation summary for a city")
def ge_summary(city: str = Query("london")) -> dict:
    """Returns the compact pass/fail counts from the last GE run."""
    result = ge_runner.get_latest_summary(city)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No GE results found for city={city}. "
                   "Run POST /quality/ge-validate first.",
        )
    return result


@router.get("/ge-results", summary="Full per-expectation GE results for a city")
def ge_results(city: str = Query("london")) -> dict:
    """Returns the full per-expectation detail from the last GE run."""
    result = ge_runner.get_full_results(city)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No GE results found for city={city}. "
                   "Run POST /quality/ge-validate first.",
        )
    return result
