"""Shared primitive cleaners used by every file-specific cleaner.

Each function takes a pandas Series and returns a transformed Series of
the appropriate dtype, with NULL preserved (never coerced to a default).
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Booleans: anything not in this map becomes NULL (never auto-False; A-017).
BOOLEAN_MAP = {
    "t": True, "true": True, "1": True, "yes": True, "y": True,
    "f": False, "false": False, "0": False, "no": False, "n": False,
}

ROOM_TYPE_MAP = {
    "entire home/apt": "entire_home",
    "private room": "private_room",
    "shared room": "shared_room",
    "hotel room": "hotel_room",
}

# INT_MAX sentinel pattern for maximum_nights and related (A-018).
INT_MAX_SENTINEL = 2 ** 30

_NAME_RE = re.compile(r"[^a-z0-9]+")
_PRICE_RE = re.compile(r"[^\d.\-]")
_NUM_RE = re.compile(r"([\d.]+)")


def standardize_column_name(column: str) -> str:
    out = _NAME_RE.sub("_", column.strip().lower())
    return out.strip("_")


def clean_price(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.replace(_PRICE_RE, "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def clean_percentage(series: pd.Series) -> pd.Series:
    """`88%` -> 0.88."""
    cleaned = series.astype("string").str.replace("%", "", regex=False)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    return numeric / 100.0


def parse_bool(series: pd.Series) -> pd.Series:
    """Map t/f/true/false/yes/no/1/0 → BooleanArray; everything else → NA."""
    norm = series.astype("string").str.strip().str.lower()
    out = norm.map(BOOLEAN_MAP)
    return out.astype("boolean")


def parse_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def cap_sentinel_intmax(series: pd.Series, threshold: int = INT_MAX_SENTINEL) -> pd.Series:
    """Replace values >= threshold with NA (A-018)."""
    s = pd.to_numeric(series, errors="coerce")
    s = s.where(s < threshold)
    return s.astype("Int64")


def normalize_room_type(series: pd.Series) -> pd.Series:
    return (
        series.astype("string").str.strip().str.lower()
        .map(ROOM_TYPE_MAP)
        .astype("category")
    )


def bucket_property_type(series: pd.Series) -> pd.Series:
    """5-bucket coarse property type (A-021), preserving raw alongside."""
    s = series.astype("string").str.lower().fillna("")

    def _bucket(value: str) -> str:
        if not value:
            return "other"
        if any(w in value for w in ("apartment", "condo", "loft", "studio", "rental unit")):
            return "apartment"
        if any(w in value for w in ("house", "home", "townhouse", "cottage", "bungalow", "villa")):
            return "house"
        if any(w in value for w in ("hotel", "hostel", "bed and breakfast", "aparthotel")):
            return "hotel"
        if any(w in value for w in ("boat", "tent", "yurt", "treehouse", "barn", "cave",
                                    "tipi", "tower", "camper", "rv", "casa particular",
                                    "earthen", "windmill", "lighthouse", "shepherd")):
            return "unique"
        return "other"

    return s.map(_bucket).astype("category")


def parse_bathrooms_text(series: pd.Series) -> pd.DataFrame:
    """Return a DataFrame with columns: bathroom_count (float), bathroom_is_shared (bool/NA)."""
    s = series.astype("string").str.strip().str.lower()

    is_shared = s.str.contains("shared", na=False)
    is_private = s.str.contains("private", na=False)

    nums = s.str.extract(_NUM_RE.pattern, expand=False)
    count = pd.to_numeric(nums, errors="coerce")
    # Catch "half-bath" / "half bath"
    half_mask = count.isna() & s.str.contains("half", na=False)
    count = count.where(~half_mask, 0.5)

    is_shared_or_private = (is_shared | is_private)
    shared = pd.Series(pd.NA, index=s.index, dtype="boolean")
    shared = shared.where(~is_shared_or_private, is_shared)

    return pd.DataFrame({
        "bathroom_count": count.astype("Float64"),
        "bathroom_is_shared": shared,
    })


def trim(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def validate_range(series: pd.Series, lo: float, hi: float) -> pd.Series:
    """Return values in [lo, hi]; outside-range → NA."""
    s = pd.to_numeric(series, errors="coerce")
    return s.where((s >= lo) & (s <= hi))
