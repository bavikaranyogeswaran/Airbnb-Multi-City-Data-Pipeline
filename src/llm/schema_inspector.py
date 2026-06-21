"""
Read the DuckDB warehouse schema for one city and serialise it into a
compact text block suitable for injection into an LLM SQL-generation prompt.

Includes:
  - Column names and DuckDB data types for each analytics table
  - Distinct sample values for low-cardinality VARCHAR columns
  - Brief join-key annotations so the LLM can build correct JOINs

System/pipeline tables are excluded (they are irrelevant to analytics queries).
"""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"

# Tables relevant to analytics — system tables excluded
_ANALYTICS_TABLES = [
    "fact_listing_snapshot",
    "fact_calendar",
    "fact_reviews",
    "dim_listing",
    "dim_host",
    "dim_neighbourhood",
    "dim_date",
    "dim_city",
]

# Brief note appended after each table name — tells the LLM what the table is for
_TABLE_NOTES: dict[str, str] = {
    "fact_listing_snapshot": "one row per listing — primary analytics fact table",
    "fact_calendar":         "daily availability per listing (join on listing_key)",
    "fact_reviews":          "one row per review (join on listing_key)",
    "dim_listing":           "listing attributes: room type, size, location (join on listing_key)",
    "dim_host":              "host profile: superhost status, response rate (join on host_key)",
    "dim_neighbourhood":     "neighbourhood names and area (join on neighbourhood_key)",
    "dim_date":              "date dimension for calendar/review joins (join on date_key)",
    "dim_city":              "city metadata: currency code (join on city_key)",
}

# Columns where distinct values are worth showing (low-cardinality enums)
_SAMPLE_COLS: set[str] = {
    "room_type", "property_type_bucket", "currency_code",
    "host_response_time", "is_weekend", "available",
}

# Max distinct values to list inline
_MAX_DISTINCT = 8


def _get_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str]]:
    return con.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """).fetchall()


def _get_sample_values(con: duckdb.DuckDBPyConnection, table: str, col: str) -> list[str]:
    try:
        rows = con.execute(f"""
            SELECT DISTINCT CAST({col} AS VARCHAR)
            FROM {table}
            WHERE {col} IS NOT NULL
            LIMIT {_MAX_DISTINCT}
        """).fetchall()
        return [r[0] for r in rows if r[0] is not None]
    except Exception:
        return []


def get_schema(city: str) -> str:
    """
    Return a formatted schema string for the city's warehouse.
    Raises FileNotFoundError if the warehouse does not exist.
    """
    db_path = DATA / city / "warehouse.duckdb"
    if not db_path.exists():
        raise FileNotFoundError(
            f"Warehouse not found for '{city}'. "
            "Run the pipeline load stage first."
        )

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        lines: list[str] = [
            f"DuckDB warehouse — city: {city}",
            "=" * 60,
            "",
            "KEY RELATIONSHIPS:",
            "  fact_listing_snapshot.listing_key  -> dim_listing.listing_key",
            "  fact_listing_snapshot.host_key      -> dim_host.host_key",
            "  fact_listing_snapshot.neighbourhood_key -> dim_neighbourhood.neighbourhood_key",
            "  fact_calendar.listing_key           -> dim_listing.listing_key",
            "  fact_calendar.date_key              -> dim_date.date_key",
            "  fact_reviews.listing_key            -> dim_listing.listing_key",
            "  fact_reviews.date_key               -> dim_date.date_key",
            "",
        ]

        for table in _ANALYTICS_TABLES:
            note = _TABLE_NOTES.get(table, "")
            lines.append(f"TABLE {table}  [{note}]")

            columns = _get_columns(con, table)
            for col_name, data_type in columns:
                line = f"  {col_name:<35} {data_type}"
                if col_name in _SAMPLE_COLS:
                    vals = _get_sample_values(con, table, col_name)
                    if vals:
                        line += f"  -- e.g. {', '.join(vals[:_MAX_DISTINCT])}"
                lines.append(line)

            lines.append("")

        return "\n".join(lines)
    finally:
        con.close()
