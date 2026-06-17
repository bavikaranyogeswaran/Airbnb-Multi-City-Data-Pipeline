"""Data Enrichment & Joining endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.transformation import calendar_summary as cal_mod
from src.transformation import listing_master as master_mod
from src.transformation import neighbourhood_summary as neigh_mod
from src.transformation import review_summary as rev_mod

from ..paths import ROOT

router = APIRouter(prefix="/enrichment", tags=["enrichment"])

PROCESSED_BASE = ROOT / "data" / "processed"


@router.get("", summary="Enrichment index — all available endpoints")
def enrichment_index() -> dict:
    return {
        "area": "Data Enrichment & Joining",
        "reads": {
            "manifest":            "GET  /enrichment/manifest?city=london",
            "review_summary":      "GET  /enrichment/review-summary?city=london&n=5",
            "calendar_summary":    "GET  /enrichment/calendar-summary?city=london&n=5",
            "neighbourhood_summary": "GET  /enrichment/neighbourhood-summary?city=london",
            "listing_master":      "GET  /enrichment/listing-master?city=london&n=5",
            "top_neighbourhoods":  "GET  /enrichment/top-neighbourhoods?city=london&by=listing_count&n=10",
        },
        "triggers": {
            "review_summary":        "POST /enrichment/review-summary:run",
            "calendar_summary":      "POST /enrichment/calendar-summary:run",
            "neighbourhood_summary": "POST /enrichment/neighbourhood-summary:run",
            "listing_master":        "POST /enrichment/listing-master:run",
            "all":                   "POST /enrichment/all  (chain in dependency order)",
        },
    }


def _path(city: str, name: str):
    return PROCESSED_BASE / city / name


@router.get("/manifest", summary="Cleaned + enriched Parquet inventory")
def manifest(city: str = Query("london")) -> list[dict]:
    import pyarrow.parquet as pq

    files = [
        "listings_clean.parquet", "calendar_clean.parquet",
        "reviews_clean.parquet", "neighbourhoods_clean.parquet",
        "review_summary.parquet", "calendar_summary.parquet",
        "neighbourhood_summary.parquet", "listing_master.parquet",
    ]
    rows = []
    for name in files:
        p = _path(city, name)
        row: dict[str, object] = {
            "artifact": name,
            "exists": p.exists(),
            "size_mb": round(p.stat().st_size / 1_048_576, 2) if p.exists() else None,
            "row_count": None,
        }
        if p.exists():
            try:
                row["row_count"] = int(pq.ParquetFile(p).metadata.num_rows)
            except Exception:
                pass
        rows.append(row)
    return rows


def _preview(path, n: int) -> list[dict]:
    import pandas as pd
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{path.name} not generated yet.")
    df = pd.read_parquet(path).head(n)
    df = df.where(pd.notna(df), None)  # type: ignore[arg-type]
    return df.astype("object").to_dict(orient="records")


@router.get("/review-summary")
def get_review_summary(city: str = Query("london"), n: int = Query(5, ge=1, le=50)):
    return _preview(_path(city, "review_summary.parquet"), n)


@router.get("/calendar-summary")
def get_calendar_summary(city: str = Query("london"), n: int = Query(5, ge=1, le=50)):
    return _preview(_path(city, "calendar_summary.parquet"), n)


@router.get("/neighbourhood-summary")
def get_neighbourhood_summary(city: str = Query("london")):
    return _preview(_path(city, "neighbourhood_summary.parquet"), 50)


@router.get("/listing-master")
def get_listing_master(city: str = Query("london"), n: int = Query(5, ge=1, le=50)):
    return _preview(_path(city, "listing_master.parquet"), n)


@router.get("/top-neighbourhoods", summary="Top N neighbourhoods, sortable")
def top_neighbourhoods(
    city: str = Query("london"),
    by: str = Query("listing_count", description="One of: listing_count, median_price_gbp, listings_per_km2, superhost_share, avg_review_score"),
    n: int = Query(10, ge=1, le=33),
):
    import pandas as pd
    p = _path(city, "neighbourhood_summary.parquet")
    if not p.exists():
        raise HTTPException(status_code=404, detail="neighbourhood_summary not generated yet")
    allowed = {"listing_count", "median_price_gbp", "listings_per_km2",
               "superhost_share", "avg_review_score", "mean_price_gbp",
               "avg_review_score", "avg_availability_365"}
    if by not in allowed:
        raise HTTPException(status_code=400, detail=f"'by' must be one of {sorted(allowed)}")
    df = pd.read_parquet(p).sort_values(by, ascending=False).head(n)
    df = df.where(pd.notna(df), None)  # type: ignore[arg-type]
    return df.astype("object").to_dict(orient="records")


# ---------- triggers ----------

@router.post("/review-summary:run")
def trigger_review_summary(city: str = Query("london")) -> dict:
    return rev_mod.run(city=city)


@router.post("/calendar-summary:run")
def trigger_calendar_summary(city: str = Query("london")) -> dict:
    return cal_mod.run(city=city)


@router.post("/neighbourhood-summary:run")
def trigger_neighbourhood_summary(city: str = Query("london")) -> dict:
    return neigh_mod.run(city=city)


@router.post("/listing-master:run")
def trigger_listing_master(city: str = Query("london")) -> dict:
    return master_mod.run(city=city)


@router.post("/all", summary="Chain: review → calendar → neighbourhood → master")
def trigger_all(city: str = Query("london")) -> list[dict]:
    return [
        rev_mod.run(city=city),
        cal_mod.run(city=city),
        neigh_mod.run(city=city),
        master_mod.run(city=city),
    ]
