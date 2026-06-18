"""Pipeline orchestration endpoints.

Single entry point to run the full pipeline; metadata reads to inspect
prior runs, registered snapshots, and lineage.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

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
            "runs":             "GET  /orchestration/runs?city=london&limit=20",
            "run_detail":       "GET  /orchestration/runs/{run_id}?city=london",
            "dataset_versions": "GET  /orchestration/dataset-versions?city=london",
            "lineage":          "GET  /orchestration/lineage  (Markdown)",
        },
        "triggers": {
            "run":              "POST /orchestration/run?city=london&stages=all&force=false",
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
