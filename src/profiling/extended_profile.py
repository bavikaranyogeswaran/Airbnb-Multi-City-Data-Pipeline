"""Extended per-file profile: numeric stats, top-N values, completeness classes.

Goes beyond Phase 1's schema_documentation.csv by adding:
  - mean, median, std, q25, q75 for numerics
  - top-5 frequent values for low-cardinality string columns
  - completeness class (critical / important / optional) per the plan

Writes `reports/extended_profile.json` (per-file, per-column entries).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
REPORTS_DIR = ROOT / "reports"

TOP_N = 5
CATEGORICAL_MAX_CARDINALITY = 200

# Completeness classes per the plan.
CRITICAL_FIELDS = {
    "listings.csv.gz": {
        "id", "host_id", "latitude", "longitude", "last_scraped",
        "neighbourhood_cleansed", "room_type",
    },
    "calendar.csv.gz": {"listing_id", "date", "available"},
    "reviews.csv.gz": {"id", "listing_id", "date"},
    "neighbourhoods.csv": {"neighbourhood"},
    "neighbourhoods.geojson": {"neighbourhood"},
}
IMPORTANT_FIELDS = {
    "listings.csv.gz": {
        "price", "property_type", "accommodates", "bedrooms", "beds",
        "minimum_nights", "maximum_nights", "host_is_superhost",
        "host_since", "review_scores_rating", "amenities",
        "availability_365", "number_of_reviews", "instant_bookable",
    },
    "calendar.csv.gz": {"minimum_nights", "maximum_nights"},
    "reviews.csv.gz": {"reviewer_id", "comments"},
}


def classify(source: str, column: str) -> str:
    if column in CRITICAL_FIELDS.get(source, set()):
        return "critical"
    if column in IMPORTANT_FIELDS.get(source, set()):
        return "important"
    return "optional"


def profile_column(series: pd.Series, source: str) -> dict[str, Any]:
    name = series.name
    non_null = series.dropna()
    dtype = str(series.dtype)
    is_numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)

    out: dict[str, Any] = {
        "column": name,
        "detected_dtype": dtype,
        "completeness_class": classify(source, name),
        "row_count": int(len(series)),
        "null_count": int(series.isna().sum()),
        "null_percentage": round(float(series.isna().mean()) * 100, 4),
        "unique_count": int(non_null.nunique()) if len(non_null) else 0,
        "cardinality_ratio": (
            round(non_null.nunique() / len(non_null), 6) if len(non_null) else 0.0
        ),
    }

    if is_numeric and len(non_null):
        arr = non_null.to_numpy()
        out["numeric_stats"] = {
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
            "mean": float(np.nanmean(arr)),
            "median": float(np.nanmedian(arr)),
            "std": float(np.nanstd(arr, ddof=1)) if len(arr) > 1 else 0.0,
            "q25": float(np.nanpercentile(arr, 25)),
            "q75": float(np.nanpercentile(arr, 75)),
        }

    # top-N for low-cardinality strings/categories
    if out["unique_count"] and out["unique_count"] <= CATEGORICAL_MAX_CARDINALITY:
        top = non_null.value_counts().head(TOP_N)
        out["top_values"] = [
            {"value": str(v), "count": int(c)} for v, c in top.items()
        ]

    # sample for everything (helps narrate the field even when no top-N)
    out["sample_values"] = non_null.astype(str).head(3).tolist()
    return out


def profile_file(path: Path, source_name: str, compressed: bool) -> dict[str, Any]:
    if source_name.endswith(".geojson"):
        with path.open("r", encoding="utf-8") as f:
            doc = json.load(f)
        features = doc.get("features", [])
        props = pd.DataFrame([feat.get("properties", {}) or {} for feat in features])
        df = props.copy()
        df["geometry_type"] = [feat.get("geometry", {}).get("type") for feat in features]
    else:
        df = pd.read_csv(
            path,
            compression="gzip" if compressed else None,
            low_memory=False,
        )

    columns = [profile_column(df[c], source_name) for c in df.columns]

    return {
        "source_file": source_name,
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1_048_576, 2),
        "columns": columns,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()

    with CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    city_cfg = cfg["cities"][args.city]

    raw_dir = RAW_BASE / args.city
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    profile = {
        "city": args.city,
        "snapshot_date": city_cfg["source"]["snapshot_date"],
        "files": [],
    }

    for key, file_cfg in city_cfg["files"].items():
        path = raw_dir / file_cfg["name"]
        if not path.exists():
            print(f"skip {file_cfg['name']} (missing)")
            continue
        print(f"profile {file_cfg['name']} ...", flush=True)
        prof = profile_file(path, file_cfg["name"], bool(file_cfg.get("compressed")))
        profile["files"].append(prof)
        print(f"  done: {prof['row_count']:,} rows x {prof['column_count']} cols")

    out = REPORTS_DIR / "extended_profile.json"
    out.write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
