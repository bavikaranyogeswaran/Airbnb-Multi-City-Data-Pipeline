"""
Host cluster profiling and naming — Step 25.

Loads host_clustering_labels.parquet, computes per-cluster statistics across
all 13 host features, assigns a human-readable segment name using
data-driven rules, and saves the profile CSV.

Outputs:
  reports/model_results/host_clustering_profile_{city}.csv
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data" / "processed"
OUT  = ROOT / "reports" / "model_results"


def _name_cluster(row: Mapping[str, float], price_rank: int) -> str:
    """
    Assign a segment name from a cluster's aggregated host statistics.

    Uses the column names produced by the agg() call:
      pct_superhost, mean_listing_count, mean_reviews_per_month,
      mean_response_rate, mean_acceptance_rate, mean_pct_entire_home,
      mean_availability

    Priority order:
      1. Low response + low acceptance → disengaged hosts not really operating
      2. Majority superhost + multi-listing → organised professional operators
      3. High superhost rate + very actively booked → active operators even if smaller
      4. Mostly entire-home + low availability + rarely booked → occasional apartment renters
      5. Low availability otherwise → general occasional hosts
      6. Price-rank fallback
    """
    pct_sh = row["pct_superhost"]          # 0–100
    n_list = row["mean_listing_count"]
    rpm    = row["mean_reviews_per_month"]
    resp   = row["mean_response_rate"]     # 0–1 fraction
    accept = row["mean_acceptance_rate"]   # 0–1 fraction
    pct_eh = row["mean_pct_entire_home"]   # 0–100
    avail  = row["mean_availability"]

    # Very low response AND very low acceptance — hosts who list but don't engage
    if resp < 0.70 and accept < 0.50:
        return "Passive Listers"

    # Professional scale: majority are superhosts and hold multiple listings
    if pct_sh >= 50 and n_list >= 2:
        return "Professional Superhosts"

    # Actively booked superhosts even without large portfolios
    if pct_sh >= 40 and rpm > 1.5:
        return "Active Superhost Operators"

    # Entire-home owners who rarely open their calendar — holiday-home pattern
    if pct_eh > 80 and avail < 120 and rpm < 0.5:
        return "Part-Time Apartment Hosts"

    # Single listing, responsive but limited availability — casual side-income
    if avail < 120:
        return "Occasional Hosts"

    tiers = ["Budget Hosts", "Mid-Range Hosts", "Premium Hosts", "Luxury Hosts"]
    return tiers[min(price_rank - 1, len(tiers) - 1)]


def profile(city: str = "london") -> dict:
    """Build and save the host cluster profile for one city."""
    OUT.mkdir(parents=True, exist_ok=True)

    src = DATA / city / "host_clustering_labels.parquet"
    if not src.exists():
        return {
            "status": "error",
            "message": f"host_clustering_labels.parquet not found for {city}. "
                       "Run cluster_hosts.py first.",
        }

    df = pd.read_parquet(src)

    # ── Per-cluster aggregate statistics ──────────────────────────────────────
    agg = df.groupby("cluster").agg(
        n                       =("cluster",                  "count"),
        median_listing_count    =("listing_count",            "median"),
        mean_listing_count      =("listing_count",            "mean"),
        median_avg_price        =("avg_price",                "median"),
        mean_avg_price          =("avg_price",                "mean"),
        pct_superhost           =("host_is_superhost",        "mean"),
        mean_tenure             =("host_tenure_years",        "mean"),
        mean_response_rate      =("host_response_rate",       "mean"),
        mean_acceptance_rate    =("host_acceptance_rate",     "mean"),
        mean_availability       =("avg_availability_365",     "mean"),
        mean_rating             =("avg_review_scores_rating", "mean"),
        mean_reviews_per_month  =("avg_reviews_per_month",   "mean"),
        mean_accommodates       =("avg_accommodates",         "mean"),
        mean_pct_entire_home    =("pct_entire_home",          "mean"),
        mean_neighbourhood_count=("neighbourhood_count",      "mean"),
    ).round(3)

    # Scale pct_superhost to 0–100
    agg["pct_superhost"] = (agg["pct_superhost"] * 100).round(1)
    agg["pct_of_city"]   = (agg["n"] / len(df) * 100).round(1)

    # ── Assign cluster names ───────────────────────────────────────────────────
    # Rank by median portfolio price: 1 = cheapest, N = most expensive
    price_ranks = agg["median_avg_price"].rank(method="first").astype(int).to_dict()

    names = {}
    for cluster_id, row in agg.iterrows():
        names[cluster_id] = _name_cluster(row.to_dict(), price_ranks[cluster_id])

    agg["cluster_name"] = pd.Series(names)

    # ── Save ──────────────────────────────────────────────────────────────────
    out_path = OUT / f"host_clustering_profile_{city}.csv"
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
    print(f"  {city.upper()} — {result['k']} host clusters")
    print(f"{'='*65}")

    cols = ["cluster", "cluster_name", "n", "pct_of_city",
            "median_avg_price", "median_listing_count", "pct_superhost",
            "mean_response_rate", "mean_acceptance_rate",
            "mean_availability", "mean_reviews_per_month",
            "mean_pct_entire_home", "mean_tenure"]

    df_out = pd.DataFrame(result["profiles"])[cols]
    df_out = df_out.sort_values("median_avg_price")

    for _, row in df_out.iterrows():
        print(f"\n  Cluster {int(row['cluster'])} — \"{row['cluster_name']}\"")
        print(f"    n={int(row['n']):>6,}  ({row['pct_of_city']:.1f}%)  "
              f"median_price={row['median_avg_price']:.0f}  "
              f"listings={row['median_listing_count']:.0f}")
        print(f"    superhost={row['pct_superhost']:.0f}%  "
              f"response={row['mean_response_rate']*100:.0f}%  "
              f"acceptance={row['mean_acceptance_rate']*100:.0f}%")
        print(f"    avail={row['mean_availability']:.0f}d  "
              f"reviews/mo={row['mean_reviews_per_month']:.2f}  "
              f"entire_home={row['mean_pct_entire_home']:.0f}%  "
              f"tenure={row['mean_tenure']:.1f}yr")
