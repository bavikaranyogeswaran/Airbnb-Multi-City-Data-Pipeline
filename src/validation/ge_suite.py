"""Great Expectations expectation suites for each processed dataset.

Suites are defined as plain functions that return a list of Expectation
objects. ge_runner.run() imports them and registers them with an ephemeral
GE context — no project files, no YAML, no GE Cloud required.

Three suites are defined:
  listing_master_expectations()  — the enriched listing parquet
  calendar_clean_expectations()  — the cleaned calendar parquet
  reviews_clean_expectations()   — the cleaned reviews parquet
"""

from __future__ import annotations

import datetime as dt

from great_expectations import expectations as gxe


# ── Listing master ─────────────────────────────────────────────────────────────

def listing_master_expectations() -> list:
    return [
        # ── Table-level ───────────────────────────────────────────────────────
        gxe.ExpectTableRowCountToBeBetween(min_value=1_000, max_value=200_000),
        gxe.ExpectTableColumnsToMatchSet(
            column_set=[
                "id", "host_id", "neighbourhood_cleansed",
                "latitude", "longitude", "room_type",
                "accommodates", "availability_365",
                "price_numeric", "currency_code",
                "is_de_facto_inactive", "is_active_supply",
            ],
            exact_match=False,  # allow additional columns
        ),

        # ── Primary key ───────────────────────────────────────────────────────
        gxe.ExpectColumnToExist(column="id"),
        gxe.ExpectColumnValuesToNotBeNull(column="id"),
        gxe.ExpectColumnValuesToBeUnique(column="id"),

        # ── Foreign keys / required identifiers ───────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="host_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="neighbourhood_cleansed"),

        # ── Geography ─────────────────────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="latitude"),
        gxe.ExpectColumnValuesToBeBetween(
            column="latitude", min_value=-90.0, max_value=90.0,
        ),
        gxe.ExpectColumnValuesToNotBeNull(column="longitude"),
        gxe.ExpectColumnValuesToBeBetween(
            column="longitude", min_value=-180.0, max_value=180.0,
        ),

        # ── Room type ─────────────────────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="room_type"),
        gxe.ExpectColumnValuesToBeInSet(
            column="room_type",
            value_set=["entire_home", "private_room", "shared_room", "hotel_room"],
        ),

        # ── Capacity ─────────────────────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="accommodates"),
        gxe.ExpectColumnValuesToBeBetween(
            column="accommodates", min_value=1, max_value=100,
        ),
        gxe.ExpectColumnValuesToBeBetween(
            column="minimum_nights", min_value=1, max_value=None, mostly=0.99,
        ),

        # ── Availability ─────────────────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="availability_365"),
        gxe.ExpectColumnValuesToBeBetween(
            column="availability_365", min_value=0, max_value=365,
        ),

        # ── Price (nullable — 36–44% missing depending on city) ──────────────
        gxe.ExpectColumnValuesToBeBetween(
            column="price_numeric", min_value=0.01, max_value=50_000,
            mostly=0.99,   # allow a tiny fraction of extreme values
        ),
        gxe.ExpectColumnValuesToBeBetween(
            column="price_numeric", min_value=0.01, max_value=None,
            mostly=0.55,   # at least 55% of rows have a non-null positive price
        ),

        # ── Review scores (nullable for listings with no reviews) ─────────────
        gxe.ExpectColumnValuesToBeBetween(
            column="review_scores_rating", min_value=1.0, max_value=5.0,
            mostly=0.99,
        ),

        # ── Derived / enriched columns ────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="is_de_facto_inactive"),
        gxe.ExpectColumnValuesToBeInSet(
            column="is_de_facto_inactive", value_set=[True, False],
        ),
        gxe.ExpectColumnValuesToNotBeNull(column="currency_code"),
        gxe.ExpectColumnValuesToBeBetween(
            column="host_tenure_years", min_value=0.0, max_value=25.0,
            mostly=0.99,
        ),
        gxe.ExpectColumnValuesToBeBetween(
            column="occupancy_proxy", min_value=0.0, max_value=1.0,
        ),
    ]


# ── Calendar clean ─────────────────────────────────────────────────────────────

def calendar_clean_expectations() -> list:
    return [
        # ── Table-level ───────────────────────────────────────────────────────
        gxe.ExpectTableRowCountToBeBetween(min_value=365_000, max_value=40_000_000),
        gxe.ExpectTableColumnsToMatchSet(
            column_set=["listing_id", "date", "available",
                        "minimum_nights", "maximum_nights"],
            exact_match=True,
        ),

        # ── Required columns ──────────────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="listing_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="date"),
        gxe.ExpectColumnValuesToNotBeNull(column="available"),

        # ── Date range (calendar covers 1 year from snapshot) ─────────────────
        gxe.ExpectColumnValuesToBeBetween(
            column="date",
            min_value=dt.datetime(2025, 1, 1),
            max_value=dt.datetime(2027, 12, 31),
        ),

        # ── Available is boolean ──────────────────────────────────────────────
        gxe.ExpectColumnValuesToBeInSet(
            column="available", value_set=[True, False],
        ),

        # ── Stay-rule fields (nullable after INT_MAX sentinel removal) ─────────
        gxe.ExpectColumnValuesToBeBetween(
            column="minimum_nights", min_value=1, max_value=365,
            mostly=0.99,
        ),
        gxe.ExpectColumnValuesToBeBetween(
            column="maximum_nights", min_value=1, max_value=None,
            mostly=0.99,
        ),
    ]


# ── Reviews clean ──────────────────────────────────────────────────────────────

def reviews_clean_expectations() -> list:
    return [
        # ── Table-level ───────────────────────────────────────────────────────
        gxe.ExpectTableRowCountToBeBetween(min_value=1_000, max_value=5_000_000),
        gxe.ExpectTableColumnsToMatchSet(
            column_set=["id", "listing_id", "date", "reviewer_id",
                        "reviewer_name", "comments",
                        "comment_length", "comment_is_duplicate"],
            exact_match=True,
        ),

        # ── Primary / foreign keys ────────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="id"),
        gxe.ExpectColumnValuesToBeUnique(column="id"),
        gxe.ExpectColumnValuesToNotBeNull(column="listing_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="reviewer_id"),

        # ── Date ─────────────────────────────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="date"),
        gxe.ExpectColumnValuesToBeBetween(
            column="date",
            min_value=dt.datetime(2008, 1, 1),
            max_value=dt.datetime(2026, 12, 31),
        ),

        # ── Derived text-quality columns ──────────────────────────────────────
        gxe.ExpectColumnValuesToNotBeNull(column="comment_length"),
        gxe.ExpectColumnValuesToBeBetween(
            column="comment_length", min_value=0, max_value=50_000,
        ),
        gxe.ExpectColumnValuesToNotBeNull(column="comment_is_duplicate"),
        gxe.ExpectColumnValuesToBeInSet(
            column="comment_is_duplicate", value_set=[True, False],
        ),
    ]
