"""
K-Means host segmentation — Step 24.

Workflow:
  1. Load host_features.parquet (built by host_features.py)
  2. Apply log1p to right-skewed features before scaling
  3. StandardScaler on all 13 features
  4. Elbow + Silhouette sweep (k = 2..8) to find optimal k
  5. Fit final K-Means with chosen k
  6. Assign cluster labels back to hosts
  7. Save artifacts

Outputs:
  reports/model_results/host_elbow_scores_{city}.csv
  data/processed/{city}/host_clustering_labels.parquet
  models/{city}_host_kmeans.joblib   (dict: scaler + kmeans + metadata)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.features.host_features import HOST_FEATURES

ROOT   = Path(__file__).parent.parent.parent
DATA   = ROOT / "data" / "processed"
OUT    = ROOT / "reports" / "model_results"
MODELS = ROOT / "models"

# Right-skewed host features — apply log1p before StandardScaler
# listing_count: 80% of hosts have 1, max=500 (extreme right skew)
# avg_price: outlier hosts push max to £74k
# avg_minimum_nights: long-stay outliers push max to 1,125 nights
LOG1P_COLS: list[str] = ["listing_count", "avg_price", "avg_minimum_nights"]

# Silhouette is O(n²) — sample to keep runtime reasonable
_SILHOUETTE_SAMPLE = 5_000


def _preprocess(df: pd.DataFrame) -> tuple[np.ndarray, StandardScaler]:
    """Apply log1p to skewed cols then StandardScaler on all 13 features."""
    X = df[HOST_FEATURES].copy()
    for col in LOG1P_COLS:
        X[col] = np.log1p(X[col])
    scaler  = StandardScaler()
    X_scaled = np.asarray(scaler.fit_transform(X))
    return X_scaled, scaler


def _elbow_sweep(
    X_scaled: np.ndarray,
    k_range: range = range(2, 9),
    random_state: int = 42,
) -> pd.DataFrame:
    """Run K-Means for each k and collect inertia + silhouette."""
    rng = np.random.default_rng(random_state)
    n_sample   = min(_SILHOUETTE_SAMPLE, len(X_scaled))
    sample_idx = rng.choice(len(X_scaled), size=n_sample, replace=False)
    X_sample   = X_scaled[sample_idx]

    rows = []
    prev_inertia = None
    for k in k_range:
        km = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=random_state)
        labels = km.fit_predict(X_scaled)

        # pyrefly: ignore[bad-argument-type]
        sil  = silhouette_score(np.asarray(X_sample), labels[sample_idx])
        drop = None if prev_inertia is None else (prev_inertia - km.inertia_) / prev_inertia * 100

        rows.append({
            "k":                k,
            "inertia":          round(km.inertia_, 1),
            "inertia_pct_drop": round(drop, 2) if drop is not None else None,
            "silhouette":       round(sil, 4),
        })
        print(
            f"    k={k}  inertia={km.inertia_:>12,.0f}  "
            f"drop={str(round(drop, 1)) + '%':>7}  silhouette={sil:.4f}"
            if drop is not None else
            f"    k={k}  inertia={km.inertia_:>12,.0f}  drop=    N/A  silhouette={sil:.4f}"
        )
        prev_inertia = km.inertia_

    return pd.DataFrame(rows)


def _pick_k(elbow_df: pd.DataFrame) -> int:
    """
    Choose k at the elbow: first k where the marginal inertia drop
    falls below 50% of the drop at k=3. Falls back to max-silhouette k
    if the heuristic selects k=2 (degenerate).
    """
    drops     = elbow_df["inertia_pct_drop"].dropna()
    reference = float(drops.iloc[0])   # drop at k=3 relative to k=2
    threshold = reference * 0.50

    chosen = None
    for _, row in elbow_df[elbow_df["inertia_pct_drop"].notna()].iterrows():
        if row["inertia_pct_drop"] < threshold:
            chosen = int(row["k"])
            break

    if chosen is None or chosen <= 2:
        chosen = int(cast(float, elbow_df.loc[elbow_df["silhouette"].idxmax(), "k"]))

    return chosen


def cluster(city: str = "london", k: int | None = None) -> dict:
    """
    Full host clustering pipeline for one city.

    Parameters
    ----------
    city : City name (must have host_features.parquet built).
    k    : Override optimal-k selection. Pass None to auto-detect via elbow.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    src = DATA / city / "host_features.parquet"
    if not src.exists():
        return {
            "status": "error",
            "message": f"host_features.parquet not found for {city}. "
                       "Run host_features.py first.",
        }

    df = pd.read_parquet(src)
    print(f"  Loaded {len(df):,} hosts for {city}")

    # ── Preprocess ──────────────────────────────────────────────────────────
    X_scaled, scaler = _preprocess(df)

    # ── Elbow sweep ─────────────────────────────────────────────────────────
    print("  Elbow sweep (k = 2..8):")
    elbow_df = _elbow_sweep(X_scaled)
    elbow_df.to_csv(OUT / f"host_elbow_scores_{city}.csv", index=False)

    # ── Choose k ────────────────────────────────────────────────────────────
    optimal_k = k if k is not None else _pick_k(elbow_df)
    print(f"\n  Chosen k = {optimal_k}")

    # ── Fit final K-Means ───────────────────────────────────────────────────
    km_final = KMeans(n_clusters=optimal_k, init="k-means++", n_init=20, random_state=42)
    labels   = km_final.fit_predict(X_scaled)

    rng = np.random.default_rng(42)
    final_sample = rng.choice(
        len(X_scaled), size=min(_SILHOUETTE_SAMPLE, len(X_scaled)), replace=False
    )
    # pyrefly: ignore[bad-argument-type]
    final_sil = silhouette_score(X_scaled[final_sample], labels[final_sample])
    print(f"  Final K-Means  inertia={km_final.inertia_:,.0f}  silhouette={final_sil:.4f}")

    # ── Attach labels to host data ──────────────────────────────────────────
    df["cluster"] = labels.astype(int)

    out_labels = DATA / city / "host_clustering_labels.parquet"
    df.to_parquet(out_labels, index=False)

    # ── Cluster size summary ────────────────────────────────────────────────
    size_df = (
        df.groupby("cluster").size()
        .reset_index(name="count")
        .assign(pct=lambda d: (d["count"] / len(df) * 100).round(1))
    )
    print("\n  Cluster sizes:")
    for _, row in size_df.iterrows():
        bar = "#" * int(row["pct"] / 2)
        print(f"    cluster {int(row['cluster'])}  {row['count']:>6,}  ({row['pct']:>4.1f}%)  {bar}")

    # ── Save model artifact ─────────────────────────────────────────────────
    artifact = {
        "scaler":      scaler,
        "kmeans":      km_final,
        "log1p_cols":  LOG1P_COLS,
        "features":    HOST_FEATURES,
        "k":           optimal_k,
        "city":        city,
        "inertia":     km_final.inertia_,
        "silhouette":  final_sil,
    }
    model_path = MODELS / f"{city}_host_kmeans.joblib"
    joblib.dump(artifact, model_path)

    return {
        "status":        "ok",
        "city":          city,
        "k":             optimal_k,
        "inertia":       round(km_final.inertia_, 1),
        "silhouette":    round(final_sil, 4),
        "cluster_sizes": size_df.to_dict(orient="records"),
        "labels_path":   str(out_labels),
        "model_path":    str(model_path),
        "elbow_csv":     str(OUT / f"host_elbow_scores_{city}.csv"),
    }


def run(city: str = "london", k: int | None = None) -> dict:
    return cluster(city, k)


if __name__ == "__main__":
    import sys
    city  = sys.argv[1] if len(sys.argv) > 1 else "london"
    k_arg = int(sys.argv[2]) if len(sys.argv) > 2 else None
    result = run(city, k_arg)
    print(json.dumps(
        {kk: vv for kk, vv in result.items() if kk != "cluster_sizes"},
        indent=2,
    ))
