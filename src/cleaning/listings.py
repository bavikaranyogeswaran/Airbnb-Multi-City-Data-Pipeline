"""Clean listings.csv.gz → listings_clean.parquet + rejected_listings.parquet.

Applies the cleaning_requirement annotations from
reports/schema_documentation.csv, plus the column drops (33 cols) and
the listing-specific derivations:
  - price_raw + price_numeric + currency_code
  - bathroom_count + bathroom_is_shared from bathrooms_text
  - property_type_bucket from property_type
  - bedrooms_is_missing indicator
  - is_de_facto_inactive flag (A-019: minimum_nights >= 365)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.cleaning import transforms as T

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
PROCESSED_BASE = ROOT / "data" / "processed"

# Columns to drop entirely (per schema_documentation.csv 'drop' action).
DROP_COLUMNS = {
    "listing_url", "scrape_id", "picture_url", "host_url",
    "host_thumbnail_url", "host_picture_url",
    "calendar_updated", "neighbourhood", "neighbourhood_group_cleansed",
    "license",
    # bathrooms is redundant — bathroom_count from bathrooms_text replaces it.
    "bathrooms",
}

DATE_COLUMNS = [
    "last_scraped", "host_since", "calendar_last_scraped",
    "first_review", "last_review",
]

BOOL_COLUMNS = [
    "host_is_superhost", "host_has_profile_pic", "host_identity_verified",
    "has_availability", "instant_bookable",
]

PERCENT_COLUMNS = ["host_response_rate", "host_acceptance_rate"]

SENTINEL_INT_COLUMNS = [
    "minimum_nights", "maximum_nights",
    "minimum_minimum_nights", "maximum_minimum_nights",
    "minimum_maximum_nights", "maximum_maximum_nights",
]

STRING_TRIM_COLUMNS = [
    "name", "description", "neighborhood_overview", "host_name",
    "host_location", "host_about", "host_neighbourhood",
    "neighbourhood_cleansed",
]


def clean(df: pd.DataFrame, currency_code: str = "GBP") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean_df, rejected_df).

    currency_code: ISO 4217 code read from cities.yml; defaults to GBP for
    backward-compat but callers should always pass the city-specific value.
    """
    df = df.copy()

    # Drop columns
    for col in DROP_COLUMNS:
        if col in df.columns:
            df = df.drop(columns=col)

    # Price
    if "price" in df.columns:
        df["price_raw"] = df["price"].astype("string")
        df["price_numeric"] = T.clean_price(df["price"]).astype("Float64")
        df["currency_code"] = currency_code  # A-010: sourced from cities.yml
        df = df.drop(columns="price")

    # Dates
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = T.parse_date(df[col])

    # Booleans
    for col in BOOL_COLUMNS:
        if col in df.columns:
            df[col] = T.parse_bool(df[col])

    # Percentages
    for col in PERCENT_COLUMNS:
        if col in df.columns:
            df[col] = T.clean_percentage(df[col]).astype("Float64")

    # Sentinel-capped integers
    for col in SENTINEL_INT_COLUMNS:
        if col in df.columns:
            df[col] = T.cap_sentinel_intmax(df[col])

    # Categories
    if "room_type" in df.columns:
        df["room_type"] = T.normalize_room_type(df["room_type"])

    if "property_type" in df.columns:
        df["property_type_bucket"] = T.bucket_property_type(df["property_type"])

    # Bathrooms text -> two fields
    if "bathrooms_text" in df.columns:
        parsed = T.parse_bathrooms_text(df["bathrooms_text"])
        df["bathroom_count"] = parsed["bathroom_count"]
        df["bathroom_is_shared"] = parsed["bathroom_is_shared"]

    # Trim strings
    for col in STRING_TRIM_COLUMNS:
        if col in df.columns:
            df[col] = T.trim(df[col])

    # Missingness indicators
    if "bedrooms" in df.columns:
        df["bedrooms_is_missing"] = df["bedrooms"].isna()

    # Derived: de facto inactive (A-019)
    if "minimum_nights" in df.columns:
        df["is_de_facto_inactive"] = (df["minimum_nights"] >= 365).fillna(False)

    # Quarantine rules (per A-019-aware, lat/lon, price)
    rejection_reasons: list[pd.Series] = []
    if "price_numeric" in df.columns:
        rejection_reasons.append(
            (df["price_numeric"] < 0).fillna(False).rename("negative_price")
        )
    if "latitude" in df.columns:
        rejection_reasons.append(
            (~df["latitude"].between(-90, 90)).fillna(True).rename("invalid_latitude")
        )
    if "longitude" in df.columns:
        rejection_reasons.append(
            (~df["longitude"].between(-180, 180)).fillna(True).rename("invalid_longitude")
        )
    if "id" in df.columns:
        rejection_reasons.append(df["id"].isna().rename("missing_listing_id"))
        rejection_reasons.append(df["id"].duplicated(keep=False).rename("duplicate_listing_key"))

    if rejection_reasons:
        rejected_mask = pd.concat(rejection_reasons, axis=1).any(axis=1)
        rejected = df[rejected_mask].copy()
        if not rejected.empty:
            reasons = []
            for col in rejection_reasons:
                col_match = df[col.index.isin(df.index)] if False else None  # noop
            # build readable reason per row
            reason_df = pd.concat(rejection_reasons, axis=1)
            rejected["rejection_reason"] = reason_df.loc[rejected_mask].apply(
                lambda r: ",".join(c for c, v in r.items() if v), axis=1
            )
        clean_df = df[~rejected_mask].copy()
    else:
        rejected = df.iloc[0:0].copy()
        clean_df = df

    return clean_df, rejected


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]

        raw = RAW_BASE / city / city_cfg["files"]["listings_detailed"]["name"]
        out_dir = PROCESSED_BASE / city
        out_dir.mkdir(parents=True, exist_ok=True)

        currency_code = city_cfg.get("currency_code", "GBP")
        df = pd.read_csv(raw, compression="gzip", low_memory=False)
        original_cols = list(df.columns)
        clean_df, rejected = clean(df, currency_code=currency_code)

        clean_out = out_dir / "listings_clean.parquet"
        rejected_out = out_dir / "rejected_listings.parquet"
        clean_df.to_parquet(clean_out, index=False)
        rejected.to_parquet(rejected_out, index=False)

    rename_map = {c: T.standardize_column_name(c) for c in original_cols}
    renamed_count = sum(1 for k, v in rename_map.items() if k != v)

    return make_result(
        step="cleaning.listings",
        outputs=[clean_out, rejected_out],
        summary={
            "city": city,
            "input_rows": len(df),
            "input_columns": len(original_cols),
            "clean_rows": len(clean_df),
            "clean_columns": clean_df.shape[1],
            "rejected_rows": len(rejected),
            "dropped_columns": sorted(c for c in DROP_COLUMNS if c in original_cols),
            "derived_columns": [
                "price_raw", "price_numeric", "currency_code",
                "property_type_bucket", "bathroom_count", "bathroom_is_shared",
                "bedrooms_is_missing", "is_de_facto_inactive",
            ],
            "columns_renamed_by_standardization": renamed_count,
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
