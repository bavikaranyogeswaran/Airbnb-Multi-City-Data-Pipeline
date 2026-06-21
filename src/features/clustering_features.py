"""
Build the clustering feature set for listing segmentation.

Loads feature_matrix.parquet (already cleaned and filtered to price > 0),
computes distance_to_centre_km from lat/lon, selects the 9 clustering features,
imputes the few remaining NAs with column medians, and saves
clustering_features.parquet to data/processed/{city}/.

Clustering features (Step 19 spec):
  log_price, accommodates, bedrooms, minimum_nights, availability_365,
  review_scores_rating, reviews_per_month_calc, distance_to_centre_km,
  amenity_count

Meta columns kept alongside (for cluster profiling, not used in K-Means):
  id, host_id, neighbourhood_cleansed, room_type, price_numeric
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pandas as pd

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data" / "processed"

# 9 features that go into K-Means (in this order)
CLUSTER_FEATURES: list[str] = [
    "log_price",
    "accommodates",
    "bedrooms",
    "minimum_nights",
    "availability_365",
    "review_scores_rating",
    "reviews_per_month_calc",
    "distance_to_centre_km",
    "amenity_count",
]

# City centre coordinates used to compute distance_to_centre_km
_CITY_CENTRES: dict[str, tuple[float, float]] = {
    "london":    (51.5080, -0.1281),   # Trafalgar Square
    "amsterdam": (52.3732,  4.8932),   # Dam Square
    "new_york":  (40.7580, -73.9855),  # Times Square
    "berlin":    (52.5163,  13.3777),  # Brandenburg Gate
}


def _haversine_km(
    lat: npt.NDArray[np.floating],
    lon: npt.NDArray[np.floating],
    centre_lat: float,
    centre_lon: float,
) -> npt.NDArray[np.floating]:
    """Vectorised haversine distance in kilometres."""
    R = 6371.0
    dlat = np.radians(centre_lat - lat)
    dlon = np.radians(centre_lon - lon)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat)) * np.cos(np.radians(centre_lat)) * np.sin(dlon / 2) ** 2
    )
    return R * 2 * np.arcsin(np.sqrt(a))


def build_clustering_features(city: str = "london") -> dict:
    """
    Build and save clustering_features.parquet for one city.

    Returns a result dict with row count, feature stats, and output path.
    """
    src = DATA / city / "feature_matrix.parquet"
    if not src.exists():
        return {
            "status": "error",
            "message": f"feature_matrix.parquet not found for {city}. "
                       "Run listing_features.py first.",
        }

    df = pd.read_parquet(src)

    # Compute distance to city centre from lat/lon
    if city not in _CITY_CENTRES:
        return {
            "status": "error",
            "message": f"No city centre defined for '{city}'. "
                       "Add it to _CITY_CENTRES in clustering_features.py.",
        }

    centre_lat, centre_lon = _CITY_CENTRES[city]
    distances = _haversine_km(
        np.asarray(df["latitude"], dtype=np.float64),
        np.asarray(df["longitude"], dtype=np.float64),
        centre_lat,
        centre_lon,
    ).round(3)
    df["distance_to_centre_km"] = distances.tolist()

    # Check all 9 features are available
    missing = [c for c in CLUSTER_FEATURES if c not in df.columns]
    if missing:
        return {
            "status": "error",
            "message": f"Missing clustering features: {missing}",
        }

    # Meta columns kept for profiling (never passed to K-Means)
    meta_cols = [c for c in ["id", "host_id", "neighbourhood_cleansed",
                              "room_type", "price_numeric"] if c in df.columns]

    out_df = df[meta_cols + CLUSTER_FEATURES].copy()

    # Impute residual NAs with column medians (pipeline already imputed most)
    na_counts_before = out_df[CLUSTER_FEATURES].isna().sum()
    for col in CLUSTER_FEATURES:
        if out_df[col].isna().any():
            out_df[col] = out_df[col].fillna(out_df[col].median())

    out = DATA / city / "clustering_features.parquet"
    out_df.to_parquet(out, index=False)

    # Distribution summary for each feature
    stats = {}
    for col in CLUSTER_FEATURES:
        s = out_df[col]
        stats[col] = {
            "mean":   round(s.mean(), 3),
            "median": round(s.median(), 3),
            "std":    round(s.std(), 3),
            "min":    round(float(s.min()), 3),
            "max":    round(float(s.max()), 3),
            "p25":    round(s.quantile(0.25), 3),
            "p75":    round(s.quantile(0.75), 3),
            "na_imputed": int(na_counts_before[col]),
        }

    return {
        "status":   "ok",
        "city":     city,
        "rows":     len(out_df),
        "features": CLUSTER_FEATURES,
        "output":   str(out),
        "stats":    stats,
    }


def run(city: str = "london") -> dict:
    return build_clustering_features(city)


if __name__ == "__main__":
    import sys
    city = sys.argv[1] if len(sys.argv) > 1 else "london"
    result = run(city)
    if result["status"] != "ok":
        print("ERROR:", result["message"])
    else:
        print(f"city      : {result['city']}")
        print(f"rows      : {result['rows']:,}")
        print(f"output    : {result['output']}")
        print()
        print(f"{'Feature':<28}  {'mean':>8}  {'median':>8}  {'std':>8}  {'min':>8}  {'max':>10}  imputed")
        print("-" * 90)
        for feat, s in result["stats"].items():
            print(
                f"  {feat:<26}  {s['mean']:>8.2f}  {s['median']:>8.2f}  "
                f"{s['std']:>8.2f}  {s['min']:>8.2f}  {s['max']:>10.2f}  {s['na_imputed']}"
            )
