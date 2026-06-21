"""Pipeline orchestration endpoints.

Single entry point to run the full pipeline; metadata reads to inspect
prior runs, registered snapshots, and lineage.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.orchestration import incremental
from src.orchestration import metadata as meta
from src.orchestration import pipeline as pipe

from ..helpers import markdown_response
from ..paths import REPORTS_DIR

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.get("", summary="Orchestration index — endpoints available")
def orchestration_index() -> dict:
    return {
        "area": "Pipeline Orchestration & Metadata",
        "stages": list(pipe.STAGE_STEPS.keys()),
        "reads": {
            "runs":              "GET  /orchestration/runs?city=london&limit=20",
            "run_detail":        "GET  /orchestration/runs/{run_id}?city=london",
            "dataset_versions":  "GET  /orchestration/dataset-versions?city=london",
            "incremental_diff":  "GET  /orchestration/incremental-diff?city=london",
            "incremental_archives": "GET /orchestration/incremental-archives?city=london",
            "lineage":           "GET  /orchestration/lineage  (Markdown)",
            "decisions":         "GET  /orchestration/engineering-decisions  (Markdown)",
        },
        "triggers": {
            "run":              "POST /orchestration/run?city=london&stages=all&force=false",
            "run_diff":         "POST /orchestration/incremental-diff?city=london&old_snapshot=2025-09-14&new_snapshot=2025-12-01",
        },
    }


@router.get("/runs", summary="Recent pipeline runs")
def list_runs(city: str = Query("london"), limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    return meta.list_runs(city, limit)


@router.get("/runs/{run_id}", summary="Run detail with stage breakdown")
def get_run(run_id: str, city: str = Query("london")) -> dict:
    row = meta.get_run(city, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"run_id '{run_id}' not found")
    return row


@router.get("/dataset-versions", summary="Registered snapshot versions")
def list_versions(city: str = Query("london")) -> list[dict]:
    return meta.list_dataset_versions(city)


@router.get("/lineage", summary="Source → warehouse data lineage (Markdown)")
def get_lineage():
    return markdown_response(REPORTS_DIR / "lineage.md")


@router.get("/engineering-decisions", summary="Engineering decision log (Markdown)")
def get_engineering_decisions():
    # Every non-trivial architectural choice with Reason / Trade-offs / Future.
    return markdown_response(REPORTS_DIR / "engineering_decisions.md")


@router.get("/incremental-diff", summary="Latest incremental diff summary for a city")
def get_incremental_diff(city: str = Query("london")) -> dict:
    """
    Returns counts of new/removed listings and price/status changes from the
    most recent snapshot comparison stored in the warehouse.

    The diff is computed automatically when a new snapshot is processed via
    `POST /orchestration/run`. Use the POST variant below to trigger a
    manual diff between two specific snapshot dates.
    """
    return incremental.latest_diff_summary(city)


@router.get("/incremental-archives", summary="List archived snapshots available for diffing")
def list_incremental_archives(city: str = Query("london")) -> dict:
    """Returns the snapshot dates for which a listing_master archive exists."""
    return {"city": city, "archives": incremental.list_archives(city)}


@router.post("/incremental-diff", summary="Run incremental diff between two snapshots")
def run_incremental_diff(
    city: str = Query("london"),
    old_snapshot: str = Query(..., description="Previous snapshot date (YYYY-MM-DD)"),
    new_snapshot: str = Query(..., description="New snapshot date (YYYY-MM-DD)"),
) -> dict:
    """
    Manually trigger a change-detection diff between two snapshot dates.

    Requires that `old_snapshot` has been archived under
    `data/processed/{city}/snapshots/listing_master_{old_snapshot}.parquet`
    and that the current `listing_master.parquet` corresponds to `new_snapshot`.

    Returns per-category change counts and writes the full diff to
    `reports/incremental/{city}_diff_{old}_to_{new}.csv`.
    """
    result = incremental.detect_changes(city, old_snapshot, new_snapshot)
    if result.get("status") == "no_baseline":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/run", summary="Run the pipeline (sync). Empty stages → all.")
def trigger_run(
    city: str = Query("london"),
    stages: str = Query("all", description="Comma-separated. 'all' or any of: ingest, profile, clean, transform, load, report."),
    force: bool = Query(False),
) -> dict:
    stages_list = [s.strip() for s in stages.split(",") if s.strip()]
    if stages_list == ["all"]:
        stages_list = None
    try:
        return pipe.run(city=city, stages=stages_list, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
