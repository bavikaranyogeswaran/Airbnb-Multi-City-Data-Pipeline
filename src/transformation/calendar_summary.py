"""Per-listing calendar aggregates from calendar_clean.parquet.

Pure-DuckDB aggregation: 35M rows never enter pandas memory. Computes
availability rate, occupancy proxy, weekend-vs-weekday availability
split, and unavailable-day counts that the listing master later joins
with listing-level `price_numeric` to produce `revenue_proxy_gbp`.

NB: per A-002 the occupancy proxy is an upper bound (`f` ≠ booked).
Per A-005 calendar prices are 100% null, so no per-date price stats.

Output: data/processed/<city>/calendar_summary.parquet
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

        in_path = PROCESSED_BASE / city / "calendar_clean.parquet"
        out_path = PROCESSED_BASE / city / "calendar_summary.parquet"

        con = duckdb.connect()
        con.execute(f"""
            COPY (
                WITH base AS (
                    SELECT
                        listing_id,
                        date,
                        available,
                        minimum_nights,
                        maximum_nights,
                        EXTRACT(DOW FROM date) IN (0, 6) AS is_weekend
                    FROM read_parquet('{in_path.as_posix()}')
                )
                SELECT
                    listing_id,
                    COUNT(*)                                                  AS calendar_days,
                    SUM(CASE WHEN available           THEN 1 ELSE 0 END)      AS available_days,
                    SUM(CASE WHEN NOT available       THEN 1 ELSE 0 END)      AS unavailable_days,
                    SUM(CASE WHEN is_weekend                  THEN 1 ELSE 0 END) AS weekend_days,
                    SUM(CASE WHEN is_weekend AND available    THEN 1 ELSE 0 END) AS weekend_available_days,
                    SUM(CASE WHEN NOT is_weekend AND available THEN 1 ELSE 0 END) AS weekday_available_days,
                    SUM(CASE WHEN available THEN 1 ELSE 0 END)::DOUBLE
                        / NULLIF(COUNT(*), 0)                                 AS availability_rate,
                    1 - (SUM(CASE WHEN available THEN 1 ELSE 0 END)::DOUBLE
                        / NULLIF(COUNT(*), 0))                                AS occupancy_proxy,
                    MIN(date)                                                 AS first_calendar_date,
                    MAX(date)                                                 AS last_calendar_date,
                    AVG(minimum_nights)::DOUBLE                               AS avg_minimum_nights,
                    AVG(maximum_nights)::DOUBLE                               AS avg_maximum_nights
                FROM base
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
        step="enrichment.calendar_summary",
        outputs=[out_path],
        summary={
            "city": city,
            "snapshot_date": snapshot,
            "listings_with_calendar": int(row_count),
            "note": "occupancy_proxy is an upper bound (A-002, blocked != booked)",
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
