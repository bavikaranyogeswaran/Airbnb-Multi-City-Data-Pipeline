"""Star-schema warehouse builder.

Output: data/processed/<city>/warehouse.duckdb

Schema (star around listing-day and listing-snapshot facts):

  dim_city            (city_key, city_code, city_name, country_code, currency_code, timezone)
  dim_neighbourhood   (neighbourhood_key, city_key, neighbourhood_name, area_km2,
                       centroid_latitude, centroid_longitude)
  dim_host            (host_key, source_host_id, host_since, host_is_superhost,
                       host_response_rate, host_acceptance_rate,
                       valid_from, valid_to, is_current)        -- SCD-2 ready
  dim_listing         (listing_key, source_listing_id, host_key, neighbourhood_key,
                       room_type, property_type, property_type_bucket,
                       accommodates, bedrooms, beds,
                       bathroom_count, bathroom_is_shared,
                       latitude, longitude, license_present,
                       instant_bookable, is_de_facto_inactive)
  dim_date            (date_key INT yyyymmdd, date, year, quarter, month, day,
                       day_of_week, is_weekend, iso_week, month_name)

  fact_calendar       (listing_key, date_key, available, available_int,
                       minimum_nights, maximum_nights)         -- 35M rows
  fact_reviews        (review_id, listing_key, date_key, reviewer_id,
                       comment_length, comment_is_duplicate)   -- 2.1M rows
  fact_listing_snapshot (listing_key, snapshot_date_key, neighbourhood_key, host_key,
                       price_numeric, availability_365, number_of_reviews,
                       review_scores_rating, has_availability, is_active_supply,
                       revenue_proxy_gbp, occupancy_proxy)     -- 96.9k rows

All FKs use natural-ish surrogate keys: source_listing_id, source_host_id,
neighbourhood_name and yyyymmdd date_key. This is correct for a single-snapshot
warehouse; the SCD-2 columns on dim_host are placeholders for multi-snapshot use.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
PROCESSED_BASE = ROOT / "data" / "processed"


def _con(city: str):
    db_path = PROCESSED_BASE / city / "warehouse.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path)), db_path


def build_dimensions(city: str) -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]
        snapshot = city_cfg["source"]["snapshot_date"]
        d = PROCESSED_BASE / city

        con, db_path = _con(city)

        # --- dim_city ---
        con.execute("DROP TABLE IF EXISTS dim_city;")
        con.execute(f"""
            CREATE TABLE dim_city AS
            SELECT
                1                                 AS city_key,
                '{city_cfg["code"]}'              AS city_code,
                '{city_cfg["name"]}'              AS city_name,
                '{city_cfg["country_code"]}'      AS country_code,
                '{city_cfg["currency_code"]}'     AS currency_code,
                '{city_cfg["timezone"]}'          AS timezone;
        """)

        # --- dim_neighbourhood ---
        con.execute("DROP TABLE IF EXISTS dim_neighbourhood;")
        con.execute(f"""
            CREATE TABLE dim_neighbourhood AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY neighbourhood)  AS neighbourhood_key,
                1                                           AS city_key,
                neighbourhood                               AS neighbourhood_name,
                area_km2,
                centroid_latitude,
                centroid_longitude
            FROM read_parquet('{(d/"neighbourhoods_clean.parquet").as_posix()}')
            ORDER BY neighbourhood;
        """)

        # --- dim_host ---
        con.execute("DROP TABLE IF EXISTS dim_host;")
        con.execute(f"""
            CREATE TABLE dim_host AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY host_id)        AS host_key,
                host_id                                     AS source_host_id,
                ANY_VALUE(host_since)                       AS host_since,
                ANY_VALUE(host_is_superhost)                AS host_is_superhost,
                ANY_VALUE(host_response_time)               AS host_response_time,
                ANY_VALUE(host_response_rate)               AS host_response_rate,
                ANY_VALUE(host_acceptance_rate)             AS host_acceptance_rate,
                ANY_VALUE(host_identity_verified)           AS host_identity_verified,
                MAX(calculated_host_listings_count)         AS host_portfolio_size,
                ANY_VALUE(host_since)                       AS valid_from,
                CAST(NULL AS DATE)                          AS valid_to,
                TRUE                                        AS is_current
            FROM read_parquet('{(d/"listings_clean.parquet").as_posix()}')
            GROUP BY host_id;
        """)

        # --- dim_listing ---
        con.execute("DROP TABLE IF EXISTS dim_listing;")
        con.execute(f"""
            CREATE TABLE dim_listing AS
            WITH l AS (
                SELECT * FROM read_parquet('{(d/"listings_clean.parquet").as_posix()}')
            )
            SELECT
                l.id                                AS listing_key,
                l.id                                AS source_listing_id,
                dh.host_key                         AS host_key,
                dn.neighbourhood_key                AS neighbourhood_key,
                l.room_type,
                l.property_type,
                l.property_type_bucket,
                l.accommodates,
                l.bedrooms,
                l.beds,
                l.bathroom_count,
                l.bathroom_is_shared,
                l.latitude,
                l.longitude,
                l.instant_bookable,
                l.is_de_facto_inactive
            FROM l
            LEFT JOIN dim_host          dh ON dh.source_host_id = l.host_id
            LEFT JOIN dim_neighbourhood dn ON dn.neighbourhood_name = l.neighbourhood_cleansed;
        """)

        # --- dim_date ---
        # Some London listings have first_review back to 2009-12; start in 2008
        # to leave a small safety margin. End in 2027 covers the calendar window.
        con.execute("DROP TABLE IF EXISTS dim_date;")
        con.execute("""
            CREATE TABLE dim_date AS
            WITH days AS (
                SELECT UNNEST(GENERATE_SERIES(DATE '2008-01-01', DATE '2027-01-01', INTERVAL 1 DAY)) AS d
            )
            SELECT
                CAST(STRFTIME(d, '%Y%m%d') AS INT)   AS date_key,
                d                                    AS date,
                EXTRACT(YEAR    FROM d)              AS year,
                EXTRACT(QUARTER FROM d)              AS quarter,
                EXTRACT(MONTH   FROM d)              AS month,
                EXTRACT(DAY     FROM d)              AS day,
                EXTRACT(DOW     FROM d)              AS day_of_week,
                EXTRACT(DOW FROM d) IN (0, 6)        AS is_weekend,
                EXTRACT(WEEK    FROM d)              AS iso_week,
                STRFTIME(d, '%B')                    AS month_name
            FROM days
            ORDER BY d;
        """)

        counts = {}
        for table in ["dim_city", "dim_neighbourhood", "dim_host", "dim_listing", "dim_date"]:
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0]) if row else 0
        con.close()

    return make_result(
        step="warehouse.dimensions",
        outputs=[db_path],
        summary={"city": city, "snapshot_date": snapshot, "row_counts": counts},
        elapsed_seconds=elapsed(),
    )


def build_facts(city: str) -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        snapshot = cfg["cities"][city]["source"]["snapshot_date"]
        snapshot_key = int(snapshot.replace("-", ""))
        d = PROCESSED_BASE / city

        con, db_path = _con(city)

        # --- fact_calendar ---
        con.execute("DROP TABLE IF EXISTS fact_calendar;")
        con.execute(f"""
            CREATE TABLE fact_calendar AS
            SELECT
                c.listing_id                                          AS listing_key,
                CAST(STRFTIME(c.date, '%Y%m%d') AS INT)               AS date_key,
                c.available,
                CASE WHEN c.available THEN 1 ELSE 0 END               AS available_int,
                c.minimum_nights,
                c.maximum_nights
            FROM read_parquet('{(d/"calendar_clean.parquet").as_posix()}') c;
        """)

        # --- fact_reviews ---
        con.execute("DROP TABLE IF EXISTS fact_reviews;")
        con.execute(f"""
            CREATE TABLE fact_reviews AS
            SELECT
                r.id                                                  AS review_id,
                r.listing_id                                          AS listing_key,
                CAST(STRFTIME(r.date, '%Y%m%d') AS INT)               AS date_key,
                r.reviewer_id,
                r.comment_length,
                r.comment_is_duplicate
            FROM read_parquet('{(d/"reviews_clean.parquet").as_posix()}') r;
        """)

        # --- fact_listing_snapshot ---
        con.execute("DROP TABLE IF EXISTS fact_listing_snapshot;")
        con.execute(f"""
            CREATE TABLE fact_listing_snapshot AS
            SELECT
                m.id                                  AS listing_key,
                {snapshot_key}                        AS snapshot_date_key,
                dn.neighbourhood_key,
                dh.host_key,
                m.price_numeric,
                m.currency_code,
                m.availability_365,
                m.number_of_reviews,
                m.review_scores_rating,
                m.has_availability,
                m.is_active_supply,
                m.is_professional_host,
                m.host_tenure_years,
                m.price_per_bedroom_gbp,
                m.reviews_per_month_calc,
                m.revenue_proxy_gbp,
                m.occupancy_proxy,
                m.availability_rate
            FROM read_parquet('{(d/"listing_master.parquet").as_posix()}') m
            LEFT JOIN dim_host          dh ON dh.source_host_id = m.host_id
            LEFT JOIN dim_neighbourhood dn ON dn.neighbourhood_name = m.neighbourhood_cleansed;
        """)

        counts = {}
        for table in ["fact_calendar", "fact_reviews", "fact_listing_snapshot"]:
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0]) if row else 0
        con.close()

    return make_result(
        step="warehouse.facts",
        outputs=[db_path],
        summary={"city": city, "snapshot_date": snapshot, "row_counts": counts},
        elapsed_seconds=elapsed(),
    )


def build_all(city: str) -> list[dict]:
    return [build_dimensions(city), build_facts(city)]


def list_tables(city: str) -> list[dict]:
    con, _ = _con(city)
    rows = con.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main' ORDER BY table_name;
    """).fetchall()
    out = []
    for (name,) in rows:
        row = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
        n = int(row[0]) if row else 0
        out.append({"table": name, "row_count": n})
    con.close()
    return out


def run_query(city: str, sql: str) -> list[dict]:
    con, _ = _con(city)
    df = con.execute(sql).fetchdf()
    con.close()
    df = df.where(df.notna(), None)  # type: ignore
    return df.astype("object").to_dict(orient="records")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    parser.add_argument("--stage", choices=["dimensions", "facts", "all"], default="all")
    args = parser.parse_args()
    if args.stage == "dimensions":
        print(build_dimensions(args.city))
    elif args.stage == "facts":
        print(build_facts(args.city))
    else:
        for r in build_all(args.city):
            print(r)


if __name__ == "__main__":
    main()
