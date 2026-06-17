"""Data Cleaning and Standardization endpoints.

Each trigger calls a file-specific cleaner's `run()` in-process. Reads
serve the resulting Parquet files as JSON previews (head + counts).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.cleaning import calendar as calendar_mod
from src.cleaning import listings as listings_mod
from src.cleaning import neighbourhoods as neighbourhoods_mod
from src.cleaning import reviews as reviews_mod

from ..paths import ROOT

router = APIRouter(prefix="/cleaning", tags=["cleaning"])

PROCESSED_BASE = ROOT / "data" / "processed"


@router.get("", summary="Cleaning index — all available endpoints")
def cleaning_index() -> dict:
    return {
        "area": "Data Cleaning & Standardization",
        "reads": {
            "manifest":         "GET  /cleaning/manifest",
            "listings_preview": "GET  /cleaning/listings?city=london&n=5",
            "calendar_preview": "GET  /cleaning/calendar?city=london&n=5",
            "reviews_preview":  "GET  /cleaning/reviews?city=london&n=5",
            "neighbourhoods_preview": "GET  /cleaning/neighbourhoods?city=london",
        },
        "triggers": {
            "listings":       "POST /cleaning/listings:run",
            "calendar":       "POST /cleaning/calendar:run  (slow: 35M rows)",
            "reviews":        "POST /cleaning/reviews:run   (slow: 2M rows + dedup)",
            "neighbourhoods": "POST /cleaning/neighbourhoods:run",
            "all":            "POST /cleaning/all  (chain in dependency order)",
        },
    }


def _outputs_for(city: str) -> dict:
    out_dir = PROCESSED_BASE / city
    return {
        "listings_clean":         out_dir / "listings_clean.parquet",
        "rejected_listings":      out_dir / "rejected_listings.parquet",
        "calendar_clean":         out_dir / "calendar_clean.parquet",
        "rejected_calendar":      out_dir / "rejected_calendar.parquet",
        "reviews_clean":          out_dir / "reviews_clean.parquet",
        "rejected_reviews":       out_dir / "rejected_reviews.parquet",
        "neighbourhoods_clean":   out_dir / "neighbourhoods_clean.parquet",
        "neighbourhoods_geo":     out_dir / "neighbourhoods_geo.parquet",
    }


@router.get("/manifest", summary="Listing of cleaned Parquet outputs (paths, exist, size, rows)")
def manifest(city: str = Query("london")) -> list[dict]:
    import pyarrow.parquet as pq

    out = _outputs_for(city)
    rows = []
    for key, path in out.items():
        entry = {
            "artifact": key,
            "path": str(path.relative_to(ROOT)),
            "exists": path.exists(),
            "size_mb": round(path.stat().st_size / 1_048_576, 2) if path.exists() else None,
            "row_count": None,
        }
        if path.exists():
            try:
                entry["row_count"] = int(pq.ParquetFile(path).metadata.num_rows)
            except Exception:
                pass
        rows.append(entry)
    return rows


def _preview(path, n: int) -> list[dict]:
    import pandas as pd

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{path.name} not generated yet.")
    df = pd.read_parquet(path).head(n)
    df = df.where(pd.notna(df), None)
    return df.astype("object").to_dict(orient="records")


@router.get("/listings", summary="Preview cleaned listings (first n rows)")
def preview_listings(city: str = Query("london"), n: int = Query(5, ge=1, le=50)) -> list[dict]:
    return _preview(_outputs_for(city)["listings_clean"], n)


@router.get("/calendar", summary="Preview cleaned calendar (first n rows)")
def preview_calendar(city: str = Query("london"), n: int = Query(5, ge=1, le=50)) -> list[dict]:
    return _preview(_outputs_for(city)["calendar_clean"], n)


@router.get("/reviews", summary="Preview cleaned reviews (first n rows; comments may be long)")
def preview_reviews(city: str = Query("london"), n: int = Query(5, ge=1, le=50)) -> list[dict]:
    return _preview(_outputs_for(city)["reviews_clean"], n)


@router.get("/neighbourhoods", summary="Cleaned neighbourhood reference (all 33 rows)")
def preview_neighbourhoods(city: str = Query("london")) -> list[dict]:
    return _preview(_outputs_for(city)["neighbourhoods_clean"], 50)


# ---------- triggers ----------

@router.post("/listings:run", summary="Clean listings.csv.gz")
def trigger_listings(city: str = Query("london")) -> dict:
    return listings_mod.run(city=city)


@router.post("/calendar:run", summary="Clean calendar.csv.gz (slow)")
def trigger_calendar(city: str = Query("london")) -> dict:
    return calendar_mod.run(city=city)


@router.post("/reviews:run", summary="Clean reviews.csv.gz (slow; dedup pass)")
def trigger_reviews(city: str = Query("london")) -> dict:
    return reviews_mod.run(city=city)


@router.post("/neighbourhoods:run", summary="Clean neighbourhoods (CSV + GeoJSON)")
def trigger_neighbourhoods(city: str = Query("london")) -> dict:
    return neighbourhoods_mod.run(city=city)


@router.post("/all", summary="Clean every file: neighbourhoods → listings → calendar → reviews")
def trigger_all(city: str = Query("london")) -> list[dict]:
    return [
        neighbourhoods_mod.run(city=city),
        listings_mod.run(city=city),
        calendar_mod.run(city=city),
        reviews_mod.run(city=city),
    ]
