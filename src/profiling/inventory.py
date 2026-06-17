"""Build a dataset inventory for a single city's raw snapshot.

Reads `config/cities.yml`, walks the configured files in
`data/raw/<city>/`, and writes `reports/dataset_inventory.csv` with the
columns required by the familiarization plan.
"""

from __future__ import annotations

import argparse
import gzip
import json
import struct
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
REPORTS_DIR = ROOT / "reports"

CHUNK_ROWS = 100_000


def gzip_uncompressed_size(path: Path) -> int:
    """Read the gzip trailer to get the uncompressed size (mod 2^32)."""
    with path.open("rb") as f:
        f.seek(-4, 2)
        (size,) = struct.unpack("<I", f.read(4))
    return size


def detect_type(name: str) -> str:
    if name.endswith(".csv.gz"):
        return "GZIP"
    if name.endswith(".geojson"):
        return "GeoJSON"
    if name.endswith(".csv"):
        return "CSV"
    return "UNKNOWN"


def count_csv_rows_and_cols(path: Path, compressed: bool) -> tuple[int, int]:
    """Stream the CSV in chunks. Returns (row_count, column_count)."""
    opener = lambda: pd.read_csv(
        path,
        compression="gzip" if compressed else None,
        chunksize=CHUNK_ROWS,
        low_memory=False,
        dtype=str,
    )
    total = 0
    cols = 0
    for chunk in opener():
        if cols == 0:
            cols = chunk.shape[1]
        total += len(chunk)
    return total, cols


def count_geojson_features(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8") as f:
        doc = json.load(f)
    features = doc.get("features", [])
    sample_props = features[0].get("properties", {}) if features else {}
    return len(features), len(sample_props)


def build_rows(city: str, city_cfg: dict) -> Iterable[dict]:
    raw_dir = RAW_BASE / city
    snapshot = city_cfg["source"]["snapshot_date"]

    for key, file_cfg in city_cfg["files"].items():
        name = file_cfg["name"]
        compressed = bool(file_cfg.get("compressed", False))
        path = raw_dir / name

        row = {
            "city": city,
            "snapshot_date": snapshot,
            "file_key": key,
            "file_name": name,
            "file_type": detect_type(name),
            "compressed_size_mb": None,
            "uncompressed_size_mb": None,
            "row_count": None,
            "column_count": None,
            "load_status": "missing",
            "notes": "",
        }

        if not path.exists():
            yield row
            continue

        size_bytes = path.stat().st_size
        row["compressed_size_mb"] = round(size_bytes / 1_048_576, 2)

        try:
            if name.endswith(".csv.gz"):
                row["uncompressed_size_mb"] = round(
                    gzip_uncompressed_size(path) / 1_048_576, 2
                )
                rows, cols = count_csv_rows_and_cols(path, compressed=True)
            elif name.endswith(".csv"):
                row["uncompressed_size_mb"] = row["compressed_size_mb"]
                rows, cols = count_csv_rows_and_cols(path, compressed=False)
            elif name.endswith(".geojson"):
                row["uncompressed_size_mb"] = row["compressed_size_mb"]
                rows, cols = count_geojson_features(path)
                row["notes"] = "rows = feature count; cols = property count"
            else:
                rows, cols = 0, 0
                row["notes"] = "unknown file type"

            row["row_count"] = rows
            row["column_count"] = cols
            row["load_status"] = "ok"
        except Exception as exc:
            row["load_status"] = "error"
            row["notes"] = f"{type(exc).__name__}: {exc}"

        yield row


def run(city: str = "london") -> dict:
    """Build the dataset inventory for `city`.

    Returns the shared `make_result` dict shape (see src.api.result).
    """
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]
        rows = list(build_rows(city, city_cfg))

        df = pd.DataFrame(rows)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / "dataset_inventory.csv"
        df.to_csv(out, index=False)

    by_status = df["load_status"].value_counts().to_dict()
    total_rows = int(df["row_count"].fillna(0).sum())

    return make_result(
        step="familiarization.inventory",
        outputs=[out],
        summary={
            "city": city,
            "files_inventoried": len(df),
            "load_status_counts": by_status,
            "total_raw_rows": total_rows,
        },
        elapsed_seconds=elapsed(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()
    result = run(city=args.city)
    print(result)


if __name__ == "__main__":
    main()
