"""Enriched listing master table.

Joins:
  listings_clean       (96k base)
  review_summary       (per-listing review aggregates)
  calendar_summary     (availability rate, occupancy proxy)
  neighbourhood_summary (borough-level context — listing_count etc.)

Derives:
  host_tenure_years          = snapshot_date - host_since
  price_per_bedroom          = price / bedrooms      (bedrooms >= 1)
  reviews_per_month_calc     = review_count_l12m / 12
  host_portfolio_size        = calculated_host_listings_count
  is_professional_host       = host_portfolio_size >= 5
  revenue_proxy_gbp          = price_numeric * unavailable_days      (A-002, A-005, A-011)
  active_supply              = has_availability AND NOT is_de_facto_inactive

Output: data/processed/<city>/listing_master.parquet
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

        d = PROCESSED_BASE / city
        out_path = d / "listing_master.parquet"

        con = duckdb.connect()
        con.execute(f"""
            COPY (
                WITH l   AS (SELECT * FROM read_parquet('{(d/"listings_clean.parquet").as_posix()}')),
                     rs  AS (SELECT * FROM read_parquet('{(d/"review_summary.parquet").as_posix()}')),
                     cs  AS (SELECT * FROM read_parquet('{(d/"calendar_summary.parquet").as_posix()}')),
                     ns  AS (SELECT * FROM read_parquet('{(d/"neighbourhood_summary.parquet").as_posix()}'))
                SELECT
                    l.*,
                    rs.review_count_calc,
                    rs.first_review_calc,
                    rs.last_review_calc,
                    rs.unique_reviewer_count,
                    rs.review_count_l12m,
                    rs.review_count_l30d,
                    rs.avg_comment_length,
                    rs.duplicate_comment_count,
                    cs.calendar_days,
                    cs.available_days,
                    cs.unavailable_days,
                    cs.availability_rate,
                    cs.occupancy_proxy,
                    cs.weekend_available_days,
                    cs.weekday_available_days,
                    ns.listing_count          AS neighbourhood_listing_count,
                    ns.median_price_gbp       AS neighbourhood_median_price_gbp,
                    ns.listings_per_km2       AS neighbourhood_density_per_km2,
                    DATE_DIFF('day', l.host_since, DATE '{snapshot}') / 365.25
                        AS host_tenure_years,
                    CASE WHEN l.bedrooms IS NULL OR l.bedrooms = 0 THEN NULL
                         ELSE l.price_numeric / l.bedrooms END
                        AS price_per_bedroom_gbp,
                    rs.review_count_l12m / 12.0 AS reviews_per_month_calc,
                    l.calculated_host_listings_count AS host_portfolio_size,
                    l.calculated_host_listings_count >= 5 AS is_professional_host,
                    l.price_numeric * cs.unavailable_days
                        AS revenue_proxy_gbp,
                    (l.has_availability AND NOT l.is_de_facto_inactive)
                        AS is_active_supply
                FROM l
                LEFT JOIN rs ON l.id = rs.listing_id
                LEFT JOIN cs ON l.id = cs.listing_id
                LEFT JOIN ns ON l.neighbourhood_cleansed = ns.neighbourhood
            ) TO '{out_path.as_posix()}' (FORMAT PARQUET);
        """)
        summary_row = con.execute(f"""
            SELECT
                COUNT(*)                                                    AS row_count,
                SUM(CASE WHEN is_active_supply THEN 1 ELSE 0 END)           AS active_listings,
                SUM(CASE WHEN is_professional_host THEN 1 ELSE 0 END)       AS professional_host_listings,
                MEDIAN(price_numeric) FILTER (WHERE price_numeric IS NOT NULL) AS median_price_gbp,
                SUM(revenue_proxy_gbp) FILTER (WHERE revenue_proxy_gbp IS NOT NULL) AS total_revenue_proxy_gbp,
                MEDIAN(occupancy_proxy) FILTER (WHERE occupancy_proxy IS NOT NULL) AS median_occupancy_proxy
            FROM read_parquet('{out_path.as_posix()}');
        """).fetchone()
        con.close()

    assert summary_row is not None
    (row_count, active, pro_host, median_price, total_revenue, median_occ) = summary_row
    return make_result(
        step="enrichment.listing_master",
        outputs=[out_path],
        summary={
            "city": city,
            "snapshot_date": snapshot,
            "rows": int(row_count),
            "active_supply": int(active or 0),
            "professional_host_listings": int(pro_host or 0),
            "median_price_gbp": float(median_price) if median_price is not None else None,
            "total_revenue_proxy_gbp": float(total_revenue) if total_revenue is not None else None,
            "median_occupancy_proxy": float(median_occ) if median_occ is not None else None,
            "caveat": "revenue_proxy_gbp uses listing-level price * unavailable_days; upper bound (A-002, A-005, A-011).",
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
