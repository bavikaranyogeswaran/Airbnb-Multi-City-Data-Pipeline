"""Clean calendar.csv.gz → calendar_clean.parquet + rejected_calendar.parquet.

Per A-005, `price` and `adjusted_price` are 100% null in this snapshot
and are dropped entirely from the clean layer. The remaining columns
are: listing_id, date, available, minimum_nights, maximum_nights.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.cleaning import transforms as T

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
PROCESSED_BASE = ROOT / "data" / "processed"

DROP_COLUMNS = {"price", "adjusted_price"}  # A-005

USECOLS = ["listing_id", "date", "available", "minimum_nights", "maximum_nights"]


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["date"] = T.parse_date(df["date"])
    df["available"] = T.parse_bool(df["available"])
    df["minimum_nights"] = T.cap_sentinel_intmax(df["minimum_nights"])
    df["maximum_nights"] = T.cap_sentinel_intmax(df["maximum_nights"])

    # Quarantine rules
    rejection_mask = (
        df["listing_id"].isna()
        | df["date"].isna()
        | df["available"].isna()
        | df.duplicated(subset=["listing_id", "date"], keep=False)
    )
    rejected = df[rejection_mask].copy()
    if not rejected.empty:
        rejected["rejection_reason"] = "invalid_or_duplicate_calendar_key"
    clean_df = df[~rejection_mask].copy()
    return clean_df, rejected


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]

        raw = RAW_BASE / city / city_cfg["files"]["calendar"]["name"]
        out_dir = PROCESSED_BASE / city
        out_dir.mkdir(parents=True, exist_ok=True)

        df = pd.read_csv(raw, compression="gzip", usecols=USECOLS, low_memory=False)
        clean_df, rejected = clean(df)

        clean_out = out_dir / "calendar_clean.parquet"
        rejected_out = out_dir / "rejected_calendar.parquet"
        # Parquet write of 35M rows: pyarrow handles this.
        clean_df.to_parquet(clean_out, index=False)
        rejected.to_parquet(rejected_out, index=False)

    return make_result(
        step="cleaning.calendar",
        outputs=[clean_out, rejected_out],
        summary={
            "city": city,
            "input_rows": int(len(df)),
            "clean_rows": int(len(clean_df)),
            "rejected_rows": int(len(rejected)),
            "dropped_columns": sorted(DROP_COLUMNS),
            "kept_columns": list(clean_df.columns),
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
