"""Per-neighbourhood (borough) aggregates with listing density.

Inputs:
  data/processed/<city>/listings_clean.parquet
  data/processed/<city>/neighbourhoods_clean.parquet  (carries area_km2)

Computes per neighbourhood: listing_count, unique hosts, median/mean
price (on non-null price subset, A-012), entire-home %, superhost %,
average rating, listing density per km^2.
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
            _ = yaml.safe_load(f)  # config currently unused beyond city resolution

        listings_path = PROCESSED_BASE / city / "listings_clean.parquet"
        neigh_path = PROCESSED_BASE / city / "neighbourhoods_clean.parquet"
        out_path = PROCESSED_BASE / city / "neighbourhood_summary.parquet"

        con = duckdb.connect()
        con.execute(f"""
            COPY (
                WITH l AS (
                    SELECT * FROM read_parquet('{listings_path.as_posix()}')
                ),
                n AS (
                    SELECT neighbourhood, area_km2 FROM read_parquet('{neigh_path.as_posix()}')
                ),
                agg AS (
                    SELECT
                        neighbourhood_cleansed AS neighbourhood,
                        COUNT(*)                                          AS listing_count,
                        COUNT(DISTINCT host_id)                           AS unique_host_count,
                        MEDIAN(price_numeric) FILTER (WHERE price_numeric IS NOT NULL) AS median_price_gbp,
                        AVG(price_numeric)    FILTER (WHERE price_numeric IS NOT NULL) AS mean_price_gbp,
                        SUM(CASE WHEN price_numeric IS NULL THEN 1 ELSE 0 END)::DOUBLE
                            / COUNT(*)                                    AS price_null_share,
                        AVG(CASE WHEN room_type = 'entire_home' THEN 1.0 ELSE 0.0 END) AS entire_home_share,
                        AVG(CASE WHEN host_is_superhost THEN 1.0 WHEN host_is_superhost = FALSE THEN 0.0 END)
                            AS superhost_share,
                        AVG(review_scores_rating) FILTER (WHERE review_scores_rating IS NOT NULL) AS avg_review_score,
                        AVG(availability_365)::DOUBLE                     AS avg_availability_365
                    FROM l
                    GROUP BY neighbourhood_cleansed
                )
                SELECT
                    agg.*,
                    n.area_km2,
                    agg.listing_count / NULLIF(n.area_km2, 0) AS listings_per_km2
                FROM agg LEFT JOIN n USING (neighbourhood)
                ORDER BY listing_count DESC
            ) TO '{out_path.as_posix()}' (FORMAT PARQUET);
        """)
        row = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{out_path.as_posix()}')"
        ).fetchone()
        assert row is not None
        row_count = row[0]
        con.close()

    return make_result(
        step="enrichment.neighbourhood_summary",
        outputs=[out_path],
        summary={"city": city, "rows": int(row_count)},
        elapsed_seconds=elapsed(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()
    print(run(city=args.city))


if __name__ == "__main__":
    main()
