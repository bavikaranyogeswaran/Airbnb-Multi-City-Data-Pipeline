"""Unit tests for the listings clean() function.

Covers: invalid coordinate rejection, missing ID rejection,
duplicate ID rejection, and valid row pass-through.
All inputs are minimal in-memory DataFrames — no file I/O.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.cleaning.listings import clean


def _minimal_row(**overrides) -> dict:
    """Return a valid base row; caller can override any field."""
    base = {
        "id":                   1,
        "name":                 "Test listing",
        "price":                "$100.00",
        "latitude":             51.5074,
        "longitude":            -0.1278,
        "room_type":            "Entire home/apt",
        "minimum_nights":       2,
        "maximum_nights":       365,
        "availability_365":     180,
        "number_of_reviews":    10,
        "host_id":              42,
        "host_is_superhost":    "t",
        "host_response_rate":   "90%",
        "review_scores_rating": 4.8,
        "neighbourhood_cleansed": "Westminster",
    }
    base.update(overrides)
    return base


# ── Valid rows ─────────────────────────────────────────────────────────────────

def test_valid_row_passes_through():
    df = pd.DataFrame([_minimal_row()])
    clean_df, rejected = clean(df)
    assert len(clean_df) == 1
    assert len(rejected) == 0


def test_price_parsed_correctly():
    df = pd.DataFrame([_minimal_row(price="$1,250.00")])
    clean_df, _ = clean(df)
    assert clean_df["price_numeric"].iloc[0] == pytest.approx(1250.00)


# ── Invalid coordinate rejection ───────────────────────────────────────────────

def test_invalid_latitude_is_rejected():
    # Latitude 200 is outside [-90, 90] — must be quarantined.
    df = pd.DataFrame([_minimal_row(latitude=200.0)])
    clean_df, rejected = clean(df)
    assert len(rejected) == 1
    assert len(clean_df) == 0
    assert "invalid_latitude" in rejected["rejection_reason"].iloc[0]


def test_invalid_longitude_is_rejected():
    df = pd.DataFrame([_minimal_row(longitude=300.0)])
    clean_df, rejected = clean(df)
    assert len(rejected) == 1
    assert "invalid_longitude" in rejected["rejection_reason"].iloc[0]


def test_negative_latitude_is_rejected():
    # -91 is below -90.
    df = pd.DataFrame([_minimal_row(latitude=-91.0)])
    clean_df, rejected = clean(df)
    assert len(rejected) == 1


# ── Required column validation ─────────────────────────────────────────────────

def test_missing_listing_id_is_rejected():
    df = pd.DataFrame([_minimal_row(id=None)])
    clean_df, rejected = clean(df)
    assert len(rejected) == 1
    assert "missing_listing_id" in rejected["rejection_reason"].iloc[0]


def test_rows_without_id_are_quarantined_rows_with_id_pass():
    rows = [_minimal_row(id=None), _minimal_row(id=2)]
    df = pd.DataFrame(rows)
    clean_df, rejected = clean(df)
    assert len(rejected) == 1
    assert len(clean_df) == 1
    assert clean_df["id"].iloc[0] == 2


# ── Duplicate key detection ────────────────────────────────────────────────────

def test_duplicate_listing_id_both_rejected():
    # Both rows sharing the same id must be quarantined (keep=False semantics).
    rows = [_minimal_row(id=99), _minimal_row(id=99, name="Copy")]
    df = pd.DataFrame(rows)
    clean_df, rejected = clean(df)
    assert len(rejected) == 2
    assert len(clean_df) == 0
    assert all("duplicate_listing_key" in r for r in rejected["rejection_reason"])


def test_unique_ids_all_pass():
    rows = [_minimal_row(id=1), _minimal_row(id=2), _minimal_row(id=3)]
    df = pd.DataFrame(rows)
    clean_df, rejected = clean(df)
    assert len(clean_df) == 3
    assert len(rejected) == 0


# ── Pipeline stage execution (minimal invocation) ─────────────────────────────

def test_clean_runs_on_larger_dataframe():
    # Smoke test: clean() processes 50 rows without error.
    rows = [_minimal_row(id=i) for i in range(50)]
    df = pd.DataFrame(rows)
    clean_df, rejected = clean(df)
    assert len(clean_df) + len(rejected) == 50
