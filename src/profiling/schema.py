"""Column-level schema profile for every raw file of a city snapshot.

Output: reports/schema_documentation.csv
Columns:
  source_file, column_name, detected_dtype, row_count, null_count,
  null_percentage, unique_count, min_value, max_value, sample_values,
  expected_type, business_meaning, cleaning_requirement

The last three columns are left empty for the human pass in Step 7.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
REPORTS_DIR = ROOT / "reports"

SAMPLE_N = 3


def profile_dataframe(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        series = df[column]
        non_null = series.dropna()
        dtype = series.dtype
        is_numeric = pd.api.types.is_numeric_dtype(dtype) and not pd.api.types.is_bool_dtype(dtype)

        min_val: object = ""
        max_val: object = ""
        if is_numeric and len(non_null):
            min_val = float(np.nanmin(non_null.values))
            max_val = float(np.nanmax(non_null.values))

        rows.append(
            {
                "source_file": source_file,
                "column_name": column,
                "detected_dtype": str(dtype),
                "row_count": len(df),
                "null_count": int(series.isna().sum()),
                "null_percentage": round(float(series.isna().mean()) * 100, 2),
                "unique_count": int(series.nunique(dropna=True)),
                "min_value": min_val,
                "max_value": max_val,
                "sample_values": non_null.astype(str).head(SAMPLE_N).tolist(),
                "expected_type": "",
                "business_meaning": "",
                "cleaning_requirement": "",
            }
        )
    return pd.DataFrame(rows)


def profile_geojson(path: Path, source_file: str) -> pd.DataFrame:
    """Profile a GeoJSON FeatureCollection: properties + geometry type."""
    with path.open("r", encoding="utf-8") as f:
        doc = json.load(f)
    features = doc.get("features", [])
    props = pd.DataFrame([feat.get("properties", {}) or {} for feat in features])
    geom_types = pd.Series([feat.get("geometry", {}).get("type") for feat in features], name="geometry_type")
    df = pd.concat([props, geom_types], axis=1)
    return profile_dataframe(df, source_file)


def load_csv(path: Path, compressed: bool) -> pd.DataFrame:
    return pd.read_csv(
        path,
        compression="gzip" if compressed else None,
        low_memory=False,
    )


def iter_file_profiles(city: str, city_cfg: dict) -> Iterable[pd.DataFrame]:
    raw_dir = RAW_BASE / city
    for key, file_cfg in city_cfg["files"].items():
        name = file_cfg["name"]
        path = raw_dir / name
        compressed = bool(file_cfg.get("compressed", False))
        if not path.exists():
            print(f"  skip   {name} (missing)")
            continue

        print(f"  load   {name}")
        if name.endswith(".geojson"):
            profile = profile_geojson(path, source_file=name)
        else:
            df = load_csv(path, compressed)
            profile = profile_dataframe(df, source_file=name)
            del df
        print(f"  done   {name}: {len(profile)} columns profiled")
        yield profile


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]

        profiles = list(iter_file_profiles(city, city_cfg))
        schema = pd.concat(profiles, ignore_index=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / "schema_documentation.csv"
        schema.to_csv(out, index=False)

    rows_per_file = schema.groupby("source_file").size().to_dict()
    return make_result(
        step="familiarization.schema",
        outputs=[out],
        summary={
            "city": city,
            "total_columns": int(len(schema)),
            "rows_per_file": rows_per_file,
        },
        elapsed_seconds=elapsed(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()
    print(run(city=args.city))


if __name__ == "__main__":
    main()
