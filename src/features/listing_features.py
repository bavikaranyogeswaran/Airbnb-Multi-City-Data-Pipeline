"""
Build a ML-ready feature matrix from listing_master.parquet.

Output:  data/processed/{city}/feature_matrix.parquet
         Columns: id, host_id, all feature columns, log_price, price_numeric
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data" / "processed"

# Amenity keyword → output column name.
# Use lowercase substring match against each amenity item.
AMENITY_FLAGS: dict[str, str] = {
    "wifi":               "has_wifi",
    "kitchen":            "has_kitchen",
    "air conditioning":   "has_air_conditioning",
    "washer":             "has_washer",
    "parking":            "has_parking",
    "pool":               "has_pool",
    "dedicated workspace":"has_workspace",
    "gym":                "has_gym",
    "elevator":           "has_elevator",
    " tv":                "has_tv",        # space-prefixed to avoid "activity" matches
    "bathtub":            "has_bathtub",
    "dishwasher":         "has_dishwasher",
}

# Numeric columns that feed directly into the model
NUMERIC_FEATURES: list[str] = [
    "accommodates",
    "bedrooms",
    "beds",
    "bathroom_count",
    "minimum_nights",
    "host_tenure_years",
    "host_response_rate",
    "latitude",
    "longitude",
    "availability_365",
    "review_scores_rating",
    "review_scores_cleanliness",
    "review_scores_location",
    "reviews_per_month_calc",
    "calculated_host_listings_count",
    "number_of_reviews",
]

# Categorical columns (label-encoded or one-hot in the model pipeline)
CATEGORICAL_FEATURES: list[str] = [
    "room_type",
    "neighbourhood_cleansed",
    "property_type_bucket",
]

# Boolean / flag columns (stored as 't'/'f', bool, or 0/1)
BINARY_FEATURES: list[str] = [
    "host_is_superhost",
    "instant_bookable",
    "bathroom_is_shared",
]


def _parse_amenities(raw: str) -> list[str]:
    """Parse an amenities JSON array string to a list of lowercase strings."""
    try:
        items = json.loads(raw)
        return [item.lower() for item in items if isinstance(item, str)]
    except (json.JSONDecodeError, TypeError):
        return []


def _add_amenity_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add one binary flag column per amenity keyword plus an amenity count."""
    parsed = df["amenities"].fillna("[]").apply(_parse_amenities)

    for keyword, col_name in AMENITY_FLAGS.items():
        df[col_name] = parsed.apply(
            lambda items, kw=keyword: int(any(kw in item for item in items))
        )

    df["amenity_count"] = parsed.apply(len)
    return df


def _coerce_binary(series: pd.Series) -> pd.Series:
    """Normalise bool / 't'/'f' string / 1/0 to integer 0 or 1."""
    if series.dtype == bool or series.dtype == "boolean":
        return series.fillna(False).astype(int)
    if series.dtype == object:
        return (
            series.map({"t": 1, "f": 0, "True": 1, "False": 0, True: 1, False: 0})
            .fillna(0)
            .astype(int)
        )
    return series.fillna(0).astype(int)


def build_feature_matrix(city: str = "london") -> dict:
    """
    Load listing_master.parquet, engineer all features, and save
    feature_matrix.parquet to data/processed/{city}/.

    Returns a result dict with row count, feature count, and output path.
    """
    src = DATA / city / "listing_master.parquet"
    if not src.exists():
        return {
            "status": "error",
            "message": f"listing_master.parquet not found at {src}",
        }

    df = pd.read_parquet(src)

    # Keep only rows with a valid positive price
    df = df[df["price_numeric"].notna() & df["price_numeric"].gt(0)].copy()

    # Log-transform the price target (reduces skew from luxury outliers)
    df["log_price"] = np.log1p(df["price_numeric"])

    # Derived numeric features
    df["beds_per_guest"] = df["beds"] / df["accommodates"].replace(0, np.nan)

    # Amenity flags from the amenities JSON column
    if "amenities" in df.columns:
        df = _add_amenity_flags(df)

    # Normalise binary columns to int 0/1
    for col in BINARY_FEATURES:
        if col in df.columns:
            df[col] = _coerce_binary(df[col])

    # Assemble column lists (only columns that actually exist in this city's data)
    amenity_cols = list(AMENITY_FLAGS.values()) + ["amenity_count"]
    derived_cols = ["beds_per_guest"]

    feature_cols = (
        [c for c in NUMERIC_FEATURES if c in df.columns]
        + [c for c in derived_cols if c in df.columns]
        + [c for c in BINARY_FEATURES if c in df.columns]
        + [c for c in CATEGORICAL_FEATURES if c in df.columns]
        + [c for c in amenity_cols if c in df.columns]
    )

    # Meta columns kept alongside features for splitting and analysis
    meta_cols = [c for c in ["id", "host_id"] if c in df.columns]
    output_cols = meta_cols + feature_cols + ["log_price", "price_numeric"]

    feature_matrix = df[output_cols].copy()

    out = DATA / city / "feature_matrix.parquet"
    feature_matrix.to_parquet(out, index=False)

    return {
        "status": "ok",
        "city": city,
        "rows": len(feature_matrix),
        "features": len(feature_cols),
        "feature_names": feature_cols,
        "output": str(out),
    }


def run(city: str = "london") -> dict:
    return build_feature_matrix(city)


if __name__ == "__main__":
    import sys

    city = sys.argv[1] if len(sys.argv) > 1 else "london"
    result = run(city)
    print(result)
