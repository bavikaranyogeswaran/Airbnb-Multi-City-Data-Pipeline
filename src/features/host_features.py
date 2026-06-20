"""
Build the host-level feature matrix for host segmentation.

Aggregates listing_master.parquet from listing level to host level,
producing one row per host with 13 features capturing listing-count,
tenure, responsiveness, portfolio pricing, availability, review quality,
and property-type mix.

Host features (Step 23 spec):
  listing_count, host_tenure_years, host_response_rate,
  host_acceptance_rate, host_is_superhost, avg_price,
  avg_availability_365, avg_review_scores_rating, avg_reviews_per_month,
  avg_accommodates, avg_minimum_nights, pct_entire_home,
  neighbourhood_count

Output:
  data/processed/{city}/host_features.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data" / "processed"

# 13 features that go into host K-Means (in this order)
HOST_FEATURES: list[str] = [
    "listing_count",
    "host_tenure_years",
    "host_response_rate",
    "host_acceptance_rate",
    "host_is_superhost",
    "avg_price",
    "avg_availability_365",
    "avg_review_scores_rating",
    "avg_reviews_per_month",
    "avg_accommodates",
    "avg_minimum_nights",
    "pct_entire_home",
    "neighbourhood_count",
]


def build_host_features(city: str = "london") -> dict:
    """
    Aggregate listing_master.parquet to host level and save host_features.parquet.

    Returns a result dict with host count, feature stats, and output path.
    """
    src = DATA / city / "listing_master.parquet"
    if not src.exists():
        return {
            "status": "error",
            "message": f"listing_master.parquet not found for {city}. "
                       "Run the enrichment pipeline first.",
        }

    df = pd.read_parquet(src)

    # Convert bool-like object column to numeric so .first() returns a float
    df["_superhost_num"] = df["host_is_superhost"].map({True: 1.0, False: 0.0})
    # Binary flag: 1 if listing is entire_home, 0 otherwise
    df["_entire_home"] = (df["room_type"] == "entire_home").astype(float)

    # ── Aggregate to host level ────────────────────────────────────────────────
    # host_id, tenure, response rate, acceptance rate, superhost are host-level
    # constants — all listings for a host share the same value, so .first() is correct.
    # Price, availability, reviews, capacity, minimum_nights are averaged
    # across a host's portfolio.
    agg = (
        df.groupby("host_id", sort=False)
        .agg(
            listing_count            =("host_id",                "count"),
            host_tenure_years        =("host_tenure_years",      "first"),
            host_response_rate       =("host_response_rate",     "first"),
            host_acceptance_rate     =("host_acceptance_rate",   "first"),
            host_is_superhost        =("_superhost_num",         "first"),
            avg_price                =("price_numeric",          "mean"),
            avg_availability_365     =("availability_365",       "mean"),
            avg_review_scores_rating =("review_scores_rating",   "mean"),
            avg_reviews_per_month    =("reviews_per_month_calc", "mean"),
            avg_accommodates         =("accommodates",           "mean"),
            avg_minimum_nights       =("minimum_nights",         "mean"),
            pct_entire_home          =("_entire_home",           "mean"),
            neighbourhood_count      =("neighbourhood_cleansed", "nunique"),
        )
        .reset_index()
    )

    # Scale pct_entire_home from 0–1 to 0–100
    agg["pct_entire_home"] = (agg["pct_entire_home"] * 100).round(2)

    # ── Impute residual NAs with column medians ────────────────────────────────
    # host_response_rate (~57% NA in London) and host_acceptance_rate (~50% NA)
    # are the main gaps — hosts who never responded have no rate recorded.
    na_counts_before = agg[HOST_FEATURES].isna().sum()
    for col in HOST_FEATURES:
        if agg[col].isna().any():
            agg[col] = agg[col].fillna(agg[col].median())

    out = DATA / city / "host_features.parquet"
    agg.to_parquet(out, index=False)

    # ── Feature distribution summary ──────────────────────────────────────────
    stats = {}
    for col in HOST_FEATURES:
        s = agg[col]
        stats[col] = {
            "mean":       round(s.mean(), 3),
            "median":     round(s.median(), 3),
            "std":        round(s.std(), 3),
            "min":        round(float(s.min()), 3),
            "max":        round(float(s.max()), 3),
            "p25":        round(s.quantile(0.25), 3),
            "p75":        round(s.quantile(0.75), 3),
            "na_imputed": int(na_counts_before[col]),
        }

    return {
        "status":   "ok",
        "city":     city,
        "hosts":    len(agg),
        "features": HOST_FEATURES,
        "output":   str(out),
        "stats":    stats,
    }


def run(city: str = "london") -> dict:
    return build_host_features(city)


if __name__ == "__main__":
    import sys
    city = sys.argv[1] if len(sys.argv) > 1 else "london"
    result = run(city)
    if result["status"] != "ok":
        print("ERROR:", result["message"])
        raise SystemExit(1)

    print(f"city    : {result['city']}")
    print(f"hosts   : {result['hosts']:,}")
    print(f"output  : {result['output']}")
    print()
    print(f"  {'Feature':<28}  {'mean':>8}  {'median':>8}  {'std':>8}  "
          f"{'min':>8}  {'max':>10}  imputed")
    print("  " + "-" * 86)
    for feat, s in result["stats"].items():
        print(
            f"  {feat:<28}  {s['mean']:>8.2f}  {s['median']:>8.2f}  "
            f"{s['std']:>8.2f}  {s['min']:>8.2f}  {s['max']:>10.2f}  {s['na_imputed']}"
        )
