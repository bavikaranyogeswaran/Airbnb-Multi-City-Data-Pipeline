"""Unit tests for src/cleaning/transforms.py.

Covers: price parsing, boolean parsing, date parsing, coordinate validation,
sentinel-int capping, room-type normalisation, percentage cleaning.
No file I/O — all inputs are constructed in-memory.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.cleaning.transforms import (
    INT_MAX_SENTINEL,
    cap_sentinel_intmax,
    clean_percentage,
    clean_price,
    normalize_room_type,
    parse_bool,
    parse_date,
    validate_range,
)


# ── Price parsing ──────────────────────────────────────────────────────────────

def test_clean_price_strips_currency_symbols():
    # Both $ (Amsterdam) and £ (London) must be stripped; thousands separator too.
    series = pd.Series(["$1,250.00", "£99.50", "200.00"])
    result = clean_price(series)
    assert result.iloc[0] == pytest.approx(1250.00)
    assert result.iloc[1] == pytest.approx(99.50)
    assert result.iloc[2] == pytest.approx(200.00)


def test_clean_price_null_passthrough():
    series = pd.Series([None, "$50.00", np.nan])
    result = clean_price(series)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(50.00)
    assert pd.isna(result.iloc[2])


def test_clean_price_invalid_string_becomes_null():
    series = pd.Series(["not_a_price", "FREE", ""])
    result = clean_price(series)
    assert all(pd.isna(result))


# ── Boolean parsing ────────────────────────────────────────────────────────────

def test_parse_bool_t_f_variants():
    # All case/shorthand variants that London and Amsterdam use.
    series = pd.Series(["t", "f", "true", "false", "yes", "no", "1", "0"])
    result = parse_bool(series)
    expected = [True, False, True, False, True, False, True, False]
    assert result.tolist() == expected


def test_parse_bool_uppercase_variants():
    series = pd.Series(["T", "F", "TRUE", "FALSE", "YES", "NO"])
    result = parse_bool(series)
    expected = [True, False, True, False, True, False]
    assert result.tolist() == expected


def test_parse_bool_unknown_becomes_null():
    # Values not in the BOOLEAN_MAP must produce NA, never auto-False (A-017).
    series = pd.Series(["maybe", "x", "na", "null"])
    result = parse_bool(series)
    assert all(pd.isna(v) for v in result)


def test_parse_bool_null_input_stays_null():
    series = pd.Series([None, "t", np.nan])
    result = parse_bool(series)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == True
    assert pd.isna(result.iloc[2])


# ── Date parsing ───────────────────────────────────────────────────────────────

def test_parse_date_valid_iso_string():
    series = pd.Series(["2023-01-15", "2024-06-01"])
    result = parse_date(series)
    assert result.iloc[0] == pd.Timestamp("2023-01-15")
    assert result.iloc[1] == pd.Timestamp("2024-06-01")


def test_parse_date_invalid_becomes_nat():
    series = pd.Series(["not-a-date", "99-99-9999", ""])
    result = parse_date(series)
    assert all(pd.isna(result))


def test_parse_date_null_stays_null():
    series = pd.Series([None, "2023-01-01", np.nan])
    result = parse_date(series)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pd.Timestamp("2023-01-01")
    assert pd.isna(result.iloc[2])


# ── Coordinate / range validation ─────────────────────────────────────────────

def test_validate_range_keeps_values_inside_bounds():
    series = pd.Series([0.0, 50.0, 90.0])
    result = validate_range(series, lo=-90, hi=90)
    assert list(result) == [0.0, 50.0, 90.0]


def test_validate_range_nullifies_out_of_bounds():
    # Latitudes > 90 or < -90 are physically impossible.
    series = pd.Series([-91.0, 0.0, 91.0, 200.0])
    result = validate_range(series, lo=-90, hi=90)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.0)
    assert pd.isna(result.iloc[2])
    assert pd.isna(result.iloc[3])


def test_validate_range_longitude_bounds():
    series = pd.Series([-181.0, -0.1281, 300.0])
    result = validate_range(series, lo=-180, hi=180)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(-0.1281)
    assert pd.isna(result.iloc[2])


# ── Sentinel-int capping ───────────────────────────────────────────────────────

def test_cap_sentinel_intmax_caps_large_values():
    # maximum_nights >= 2^30 is a platform sentinel, not a real constraint (A-018).
    sentinel = INT_MAX_SENTINEL
    series = pd.Series([7, 30, sentinel, sentinel + 1])
    result = cap_sentinel_intmax(series)
    assert result.iloc[0] == 7
    assert result.iloc[1] == 30
    assert pd.isna(result.iloc[2])
    assert pd.isna(result.iloc[3])


def test_cap_sentinel_intmax_preserves_normal_values():
    series = pd.Series([1, 14, 365, 730])
    result = cap_sentinel_intmax(series)
    assert list(result) == [1, 14, 365, 730]


# ── Room-type normalisation ────────────────────────────────────────────────────

def test_normalize_room_type_maps_display_names():
    # Amsterdam raw data uses display names; London raw also uses them before mapping.
    series = pd.Series(["Entire home/apt", "Private room", "Shared room", "Hotel room"])
    result = normalize_room_type(series)
    assert list(result) == ["entire_home", "private_room", "shared_room", "hotel_room"]


def test_normalize_room_type_unknown_becomes_null():
    series = pd.Series(["Glamping tent", "Submarine"])
    result = normalize_room_type(series)
    assert all(pd.isna(result))


# ── Percentage cleaning ────────────────────────────────────────────────────────

def test_clean_percentage_divides_by_100():
    series = pd.Series(["88%", "100%", "0%"])
    result = clean_percentage(series)
    assert result.iloc[0] == pytest.approx(0.88)
    assert result.iloc[1] == pytest.approx(1.00)
    assert result.iloc[2] == pytest.approx(0.00)


def test_clean_percentage_null_passthrough():
    series = pd.Series([None, "50%"])
    result = clean_percentage(series)
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.50)
