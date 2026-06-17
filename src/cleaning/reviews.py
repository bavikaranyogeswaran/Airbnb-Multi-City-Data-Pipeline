"""Clean reviews.csv.gz → reviews_clean.parquet + rejected_reviews.parquet.

Adds:
  - date parsed
  - comments trimmed (whitespace only; do NOT alter text)
  - comment_is_duplicate flag (A-030)
  - comment_length numeric feature for downstream NLP gating
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


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["date"] = T.parse_date(df["date"])
    df["reviewer_name"] = T.trim(df["reviewer_name"])
    df["comments"] = df["comments"].fillna("").astype("string").str.strip()
    df["comment_length"] = df["comments"].str.len().astype("Int64")

    # Duplicate-text flag (A-030)
    counts = df["comments"].value_counts()
    df["comment_is_duplicate"] = df["comments"].map(counts).gt(1)

    # Quarantine rules
    rejection_mask = (
        df["id"].isna()
        | df["listing_id"].isna()
        | df["date"].isna()
        | df["id"].duplicated(keep=False)
    )
    rejected = df[rejection_mask].copy()
    if not rejected.empty:
        rejected["rejection_reason"] = "missing_or_duplicate_review_key"
    clean_df = df[~rejection_mask].copy()
    return clean_df, rejected


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]

        raw = RAW_BASE / city / city_cfg["files"]["reviews_detailed"]["name"]
        out_dir = PROCESSED_BASE / city
        out_dir.mkdir(parents=True, exist_ok=True)

        df = pd.read_csv(raw, compression="gzip", low_memory=False)
        clean_df, rejected = clean(df)

        clean_out = out_dir / "reviews_clean.parquet"
        rejected_out = out_dir / "rejected_reviews.parquet"
        clean_df.to_parquet(clean_out, index=False)
        rejected.to_parquet(rejected_out, index=False)

    dup_count = int(clean_df["comment_is_duplicate"].sum())
    return make_result(
        step="cleaning.reviews",
        outputs=[clean_out, rejected_out],
        summary={
            "city": city,
            "input_rows": int(len(df)),
            "clean_rows": int(len(clean_df)),
            "rejected_rows": int(len(rejected)),
            "derived_columns": ["comment_length", "comment_is_duplicate"],
            "comment_duplicate_flag_count": dup_count,
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
