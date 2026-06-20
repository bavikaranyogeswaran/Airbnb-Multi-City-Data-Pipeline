"""
Cluster profiling and naming — Step 21.

Loads clustering_labels.parquet, computes per-cluster statistics across
all 9 features plus room-type distribution, assigns a human-readable
segment name using data-driven rules, and saves the profile CSV.

Outputs:
  reports/model_results/clustering_profile_{city}.csv
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data" / "processed"
OUT  = ROOT / "reports" / "model_results"

CLUSTER_FEATURES = [
    "log_price", "accommodates", "bedrooms", "minimum_nights",
    "availability_365", "review_scores_rating", "reviews_per_month_calc",
    "distance_to_centre_km", "amenity_count",
]


def _name_cluster(row: Mapping[str, float], price_rank: int) -> str:
    """
    Assign a segment name from the cluster's aggregated feature values.

    Uses the column names produced by the agg() call:
      mean_review_scores_rating, mean_reviews_per_month, mean_availability_365,
      mean_accommodates, mean_distance_km, pct_entire_home, median_minimum_nights.

    Priority order:
      1. Unreviewed / zero-score listings (mean_review_scores_rating < 3.5)
      2. High-turnover (> 3 reviews/month — very frequently booked)
      3. Part-time hosts (< 80 days available per year)
      4. Large group homes (> 4.5 guests mean, > 90% entire home)
      5. Outer-city rooms (> 9 km from centre, majority private room)
      6. Well-available standard apartments (> 250 days, mostly entire)
      7. Weekly-stay apartments (median minimum_nights > 6, mostly entire)
      8. Price-rank fallback
    """
    rating    = row["mean_review_scores_rating"]
    rpm       = row["mean_reviews_per_month"]
    avail     = row["mean_availability_365"]
    accomm    = row["mean_accommodates"]
    dist      = row["mean_distance_km"]
    pct_entire= row["pct_entire_home"]
    min_nights= row["median_minimum_nights"]

    # Inflated ratings on Airbnb are 4.5–5.0; anything below 4.0 indicates
    # new listings imputed with 0 scores or genuinely poorly-reviewed properties
    if rating < 4.0:
        return "New & Unreviewed Listings"

    # Frequently booked (reviews proxy bookings): 2.5+ reviews/month
    if rpm > 2.5:
        return "High-Turnover City Lets" if pct_entire >= 50 else "High-Turnover Private Rooms"

    if avail < 80:
        return "Part-Time City Apartments"

    if accomm > 4.0 and pct_entire >= 90:
        return "Spacious Family Homes" if price_rank <= 4 else "Premium Spacious Apartments"

    if dist > 9 and pct_entire < 50:
        return "Outer City Budget Rooms"

    if avail > 250 and pct_entire >= 70:
        return "Well-Available City Apartments"

    # Standard central apartments: near centre, mostly entire home, moderate availability
    if dist < 7 and pct_entire >= 65 and avail < 200:
        return "Standard City Apartments"

    if min_nights > 6 and pct_entire >= 60:
        return "Weekly-Stay Apartments"

    tiers = [
        "Budget Rooms",
        "Economy Apartments",
        "Standard Apartments",
        "Premium Apartments",
        "Luxury Listings",
    ]
    return tiers[min(price_rank - 1, len(tiers) - 1)]


def profile(city: str = "london") -> dict:
    """Build and save the cluster profile for one city."""
    OUT.mkdir(parents=True, exist_ok=True)

    src = DATA / city / "clustering_labels.parquet"
    if not src.exists():
        return {
            "status": "error",
            "message": f"clustering_labels.parquet not found for {city}.",
        }

    df = pd.read_parquet(src)

    # ── Per-cluster aggregate statistics ────────────────────────────────────
    agg = df.groupby("cluster").agg(
        n                        =("cluster",                 "count"),
        median_price             =("price_numeric",           "median"),
        mean_price               =("price_numeric",           "mean"),
        mean_log_price           =("log_price",               "mean"),
        mean_accommodates        =("accommodates",            "mean"),
        mean_bedrooms            =("bedrooms",                "mean"),
        median_minimum_nights    =("minimum_nights",          "median"),
        mean_minimum_nights      =("minimum_nights",          "mean"),
        mean_availability_365    =("availability_365",        "mean"),
        mean_review_scores_rating=("review_scores_rating",    "mean"),
        mean_reviews_per_month   =("reviews_per_month_calc",  "mean"),
        mean_distance_km         =("distance_to_centre_km",   "mean"),
        mean_amenity_count       =("amenity_count",            "mean"),
    ).round(2)

    # Room-type breakdown
    for rt in ["entire_home", "private_room", "shared_room", "hotel_room"]:
        agg[f"pct_{rt}"] = (
            df.groupby("cluster")["room_type"]
            .apply(lambda x, r=rt: round((x == r).mean() * 100, 1))
        )

    agg["dominant_room_type"] = (
        df.groupby("cluster")["room_type"]
        .apply(lambda x: x.value_counts().index[0])
    )

    # Top neighbourhood (most common listing location in each cluster)
    if "neighbourhood_cleansed" in df.columns:
        agg["top_neighbourhood"] = (
            df.groupby("cluster")["neighbourhood_cleansed"]
            .apply(lambda x: x.value_counts().index[0])
        )

    agg["pct_of_city"] = (agg["n"] / len(df) * 100).round(1)

    # ── Assign cluster names ─────────────────────────────────────────────────
    # Rank by median price: 1 = cheapest, 5 = most expensive
    price_ranks = agg["median_price"].rank(method="first").astype(int).to_dict()

    names = {}
    for cluster_id, row in agg.iterrows():
        # build a flat dict the naming function can use
        flat = row.to_dict()
        flat["pct_entire_home"] = flat.get("pct_entire_home", 0)
        names[cluster_id] = _name_cluster(flat, price_ranks[cluster_id])

    agg["cluster_name"] = pd.Series(names)

    # ── Save ────────────────────────────────────────────────────────────────
    out_path = OUT / f"clustering_profile_{city}.csv"
    agg.reset_index().to_csv(out_path, index=False)

    return {
        "status":   "ok",
        "city":     city,
        "k":        len(agg),
        "profiles": agg.reset_index().to_dict(orient="records"),
        "output":   str(out_path),
    }


def run(city: str = "london") -> dict:
    return profile(city)


if __name__ == "__main__":
    import sys
    city = sys.argv[1] if len(sys.argv) > 1 else "london"
    result = run(city)
    if result["status"] != "ok":
        print("ERROR:", result["message"])
        raise SystemExit(1)

    print(f"\n{'='*65}")
    print(f"  {city.upper()} — {result['k']} clusters")
    print(f"{'='*65}")

    cols = ["cluster", "cluster_name", "n", "pct_of_city", "median_price",
            "mean_accommodates", "median_minimum_nights",
            "mean_availability_365", "mean_review_scores_rating",
            "mean_reviews_per_month", "mean_distance_km", "mean_amenity_count",
            "pct_entire_home", "dominant_room_type"]

    df_out = pd.DataFrame(result["profiles"])[cols]
    df_out = df_out.sort_values("median_price")

    for _, row in df_out.iterrows():
        print(f"\n  Cluster {int(row['cluster'])} — \"{row['cluster_name']}\"")
        print(f"    n={row['n']:>6,}  ({row['pct_of_city']:.1f}%)  "
              f"median=£/€{row['median_price']:.0f}  "
              f"guests={row['mean_accommodates']:.1f}  "
              f"min_nights={row['median_minimum_nights']:.0f}  "
              f"avail={row['mean_availability_365']:.0f}d  "
              f"rating={row['mean_review_scores_rating']:.2f}  "
              f"reviews/mo={row['mean_reviews_per_month']:.2f}")
        print(f"    entire={row['pct_entire_home']:.0f}%  "
              f"dist={row['mean_distance_km']:.1f}km  "
              f"amenities={row['mean_amenity_count']:.0f}")
