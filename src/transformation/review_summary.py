"""Per-listing review aggregates from reviews_clean.parquet.

Uses DuckDB so the 2M-row reviews file never needs to enter pandas
memory in full. Output: data/processed/<city>/review_summary.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
PROCESSED_BASE = ROOT / "data" / "processed"


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        snapshot = cfg["cities"][city]["source"]["snapshot_date"]

        in_path = PROCESSED_BASE / city / "reviews_clean.parquet"
        out_path = PROCESSED_BASE / city / "review_summary.parquet"

        con = duckdb.connect()
        con.execute(f"""
            COPY (
                SELECT
                    listing_id,
                    COUNT(*)                              AS review_count_calc,
                    MIN(date)                             AS first_review_calc,
                    MAX(date)                             AS last_review_calc,
                    COUNT(DISTINCT reviewer_id)           AS unique_reviewer_count,
                    SUM(CASE WHEN date >= DATE '{snapshot}' - INTERVAL 12 MONTH THEN 1 ELSE 0 END)
                        AS review_count_l12m,
                    SUM(CASE WHEN date >= DATE '{snapshot}' - INTERVAL 30 DAY  THEN 1 ELSE 0 END)
                        AS review_count_l30d,
                    AVG(comment_length)::DOUBLE           AS avg_comment_length,
                    SUM(CASE WHEN comment_is_duplicate THEN 1 ELSE 0 END)
                        AS duplicate_comment_count
                FROM read_parquet('{in_path.as_posix()}')
                GROUP BY listing_id
            ) TO '{out_path.as_posix()}' (FORMAT PARQUET);
        """)
        row = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{out_path.as_posix()}')"
        ).fetchone()
        assert row is not None
        row_count = row[0]
        con.close()

    return make_result(
        step="enrichment.review_summary",
        outputs=[out_path],
        summary={
            "city": city,
            "snapshot_date": snapshot,
            "listings_with_reviews": int(row_count),
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
