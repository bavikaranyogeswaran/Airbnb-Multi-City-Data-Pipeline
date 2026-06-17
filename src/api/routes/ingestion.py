"""Data Ingestion and Profiling endpoints.

Triggers call `run()` in-process. Heavy steps (calendar profile, IQR on
35M rows) may block for 1–2 minutes.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.ingestion import download as download_mod
from src.profiling import duplicates as dup_mod
from src.profiling import extended_profile as profile_mod
from src.profiling import outliers as outliers_mod
from src.validation import quality_report as report_mod

from ..helpers import csv_to_records, html_response, markdown_response, read_json
from ..paths import MANIFEST_PATH, REPORTS_DIR

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("", summary="Ingestion + profiling index — all available endpoints")
def ingestion_index() -> dict:
    return {
        "area": "Data Ingestion & Profiling",
        "reads": {
            "manifest":           "GET  /ingestion/manifest",
            "extended_profile":   "GET  /ingestion/profile",
            "duplicates":         "GET  /ingestion/duplicates",
            "duplicate_listings": "GET  /ingestion/duplicates/listings",
            "review_templates":   "GET  /ingestion/duplicates/review-templates",
            "outliers":           "GET  /ingestion/outliers",
            "outliers_iqr":       "GET  /ingestion/outliers/iqr",
            "outliers_domain":    "GET  /ingestion/outliers/domain",
            "quality_report":     "GET  /ingestion/quality-report  (HTML)",
        },
        "triggers": {
            "ingest":         "POST /ingestion/ingest",
            "profile":        "POST /ingestion/profile:run",
            "duplicates":     "POST /ingestion/duplicates:run",
            "outliers":       "POST /ingestion/outliers:run",
            "quality_report": "POST /ingestion/quality-report:rebuild",
            "all":            "POST /ingestion/all  (run every step in order)",
        },
    }


# ---------- read ----------

@router.get("/manifest", summary="Ingestion manifest (CSV → JSON)")
def get_manifest() -> list[dict]:
    return csv_to_records(MANIFEST_PATH)


@router.get("/profile", summary="Extended per-file profile (JSON)")
def get_profile():
    return read_json(REPORTS_DIR / "extended_profile.json")


@router.get("/duplicates", summary="Duplicate findings (Markdown)")
def get_duplicates_summary():
    return markdown_response(REPORTS_DIR / "duplicates_summary.md")


@router.get("/duplicates/listings", summary="Candidate fuzzy-duplicate listings (CSV → JSON)")
def get_duplicate_listings() -> list[dict]:
    return csv_to_records(REPORTS_DIR / "duplicate_listings.csv")


@router.get("/duplicates/review-templates", summary="Top duplicate review-comment templates (CSV → JSON)")
def get_review_templates() -> list[dict]:
    return csv_to_records(REPORTS_DIR / "duplicate_review_comments.csv")


@router.get("/outliers", summary="Outliers summary (Markdown)")
def get_outliers_summary():
    return markdown_response(REPORTS_DIR / "outliers_summary.md")


@router.get("/outliers/iqr", summary="IQR table (CSV → JSON)")
def get_outliers_iqr() -> list[dict]:
    return csv_to_records(REPORTS_DIR / "outliers_iqr.csv")


@router.get("/outliers/domain", summary="Domain-rule violations (CSV → JSON)")
def get_outliers_domain() -> list[dict]:
    return csv_to_records(REPORTS_DIR / "outliers_domain.csv")


@router.get("/quality-report", summary="Bundled data-quality HTML report")
def get_quality_report():
    return html_response(REPORTS_DIR / "data_quality_report.html")


# ---------- triggers ----------

@router.post("/ingest", summary="Step 1+2 — verify/download raw files, update manifest")
def trigger_ingest(city: str = Query("london"), force: bool = Query(False)) -> dict:
    return download_mod.run(city=city, force=force)


@router.post("/profile:run", summary="Step 3 — extended profile (slow: calendar full scan)")
def trigger_profile(city: str = Query("london")) -> dict:
    return profile_mod.run(city=city)


@router.post("/duplicates:run", summary="Steps 4+5 — exact + fuzzy + review templates")
def trigger_duplicates(city: str = Query("london")) -> dict:
    return dup_mod.run(city=city)


@router.post("/outliers:run", summary="Step 7 — IQR + domain rules (sentinel-aware)")
def trigger_outliers(city: str = Query("london")) -> dict:
    return outliers_mod.run(city=city)


@router.post("/quality-report:rebuild", summary="Step 8 — re-render the HTML report")
def trigger_quality_report(city: str = Query("london")) -> dict:
    return report_mod.run(city=city)


@router.post("/all", summary="Run ingest → profile → duplicates → outliers → quality report")
def trigger_all(city: str = Query("london"), force: bool = Query(False)) -> list[dict]:
    results = [
        download_mod.run(city=city, force=force),
        profile_mod.run(city=city),
        dup_mod.run(city=city),
        outliers_mod.run(city=city),
        report_mod.run(city=city),
    ]
    return results
