"""
Build compact, factual context dicts from existing analytical outputs.

Each function reads pre-computed files (parquet, CSV, JSON) and returns a
plain Python dict that gets serialised into an LLM prompt.  No LLM calls
happen here — this module is pure data loading.

Token budget: keep each serialised context under ~1500 tokens.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"
MODEL_RESULTS = REPORTS / "model_results"
DATA = ROOT / "data" / "processed"

# Currency symbol per city
_CURRENCY: dict[str, str] = {
    "london":    "GBP (£)",
    "amsterdam": "EUR (€)",
    "madrid":    "EUR (€)",
    "berlin":    "EUR (€)",
}


def _safe_round(value: Any, decimals: int = 1) -> Any:
    """Round floats; pass through non-numeric values unchanged."""
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return value


def _load_model_metadata(city: str) -> dict:
    """Load model metadata and normalise the two different shapes."""
    path = MODELS_DIR / f"{city}_model_metadata.json"
    if not path.exists():
        return {}
    mc = json.loads(path.read_text(encoding="utf-8"))

    # London / Amsterdam shape: nested test_metrics + top_features_permutation
    if "test_metrics" in mc:
        tm = mc["test_metrics"]
        top = [f["feature"] for f in mc.get("top_features_permutation", [])[:5]]

        # bias_findings may be dict{band -> dict|list} or a plain list — normalise to
        # a list of short strings so downstream code never touches the nested shape
        raw_bias = mc.get("bias_findings", {})
        if isinstance(raw_bias, dict):
            bias = list(raw_bias.keys())[:2]   # just the band names
        elif isinstance(raw_bias, list):
            bias = [str(b) for b in raw_bias[:2]]
        else:
            bias = []

        return {
            "algorithm":   mc.get("algorithm", mc.get("model_type", "?")),
            "mae":         _safe_round(tm.get("mae")),
            "rmse":        _safe_round(tm.get("rmse")),
            "r2_log":      _safe_round(tm.get("r2_log"), 3),
            "within_20pct": _safe_round(tm.get("within_20pct")),
            "train_rows":  mc.get("train_rows"),
            "test_rows":   mc.get("test_rows"),
            "feature_count": mc.get("feature_count"),
            "top_features": top,
            "bias_findings": bias,
        }

    # Madrid / Berlin shape: flat keys
    return {
        "algorithm":    mc.get("best_model", "?"),
        "mae":          _safe_round(mc.get("test_mae")),
        "rmse":         None,
        "r2_log":       None,
        "within_20pct": None,
        "train_rows":   mc.get("train_rows"),
        "test_rows":    mc.get("test_rows"),
        "feature_count": mc.get("feature_count"),
        "top_features": [],
        "bias_findings": [],
    }


def build_city_context(city: str) -> dict:
    """
    City overview — headline stats drawn from listing_master and city_comparison_summary.
    Gives the LLM enough to write a market snapshot paragraph.
    """
    master_path = DATA / city / "listing_master.parquet"
    if not master_path.exists():
        raise FileNotFoundError(f"listing_master.parquet not found for {city}")

    df = pd.read_parquet(master_path)
    priced = df[df["price_numeric"] > 0]

    # Room type mix
    rt = df["room_type"].value_counts(normalize=True).mul(100).round(1).to_dict()

    # Top 5 neighbourhoods by listing count
    top_nbhd = (
        df["neighbourhood_cleansed"]
        .value_counts()
        .head(5)
        .to_dict()
    )

    # Superhost rate
    superhost_rate = round(
        (df["host_is_superhost"] == True).sum() / len(df) * 100, 1
    )

    # Availability distribution
    avail = df["availability_365"]

    return {
        "city": city,
        "currency": _CURRENCY.get(city, "?"),
        "total_listings": len(df),
        "unique_hosts": df["host_id"].nunique(),
        "price_eligible": (df["price_numeric"] > 0).sum(),
        "price_null_pct": round(df["price_numeric"].isna().sum() / len(df) * 100, 1),
        "median_price": _safe_round(priced["price_numeric"].median()),
        "mean_price":   _safe_round(priced["price_numeric"].mean()),
        "p25_price":    _safe_round(priced["price_numeric"].quantile(0.25)),
        "p75_price":    _safe_round(priced["price_numeric"].quantile(0.75)),
        "p95_price":    _safe_round(priced["price_numeric"].quantile(0.95)),
        "room_type_mix_pct": rt,
        "superhost_rate_pct": superhost_rate,
        "median_availability_365": _safe_round(avail.median()),
        "pct_high_availability": round((avail > 270).sum() / len(df) * 100, 1),
        "median_reviews": _safe_round(df["number_of_reviews"].median()),
        "median_rating":  _safe_round(df["review_scores_rating"].median(), 2),
        "top_5_neighbourhoods": top_nbhd,
    }


def build_model_context(city: str) -> dict:
    """
    Price model findings — algorithm, accuracy metrics, top features, bias.
    Gives the LLM enough to explain model performance in plain English.
    """
    mc = _load_model_metadata(city)
    if not mc:
        raise FileNotFoundError(f"Model metadata not found for {city}")

    # Cross-city context: how does this city's MAE compare to others?
    all_maes: dict[str, float] = {}
    for c in ["london", "amsterdam", "madrid", "berlin"]:
        m = _load_model_metadata(c)
        if m.get("mae") is not None:
            all_maes[c] = m["mae"]

    return {
        "city": city,
        "currency": _CURRENCY.get(city, "?"),
        **mc,
        "mae_rank_among_cities": sorted(all_maes, key=lambda c: all_maes[c]).index(city) + 1
                                 if city in all_maes else None,
        "all_city_maes": all_maes,
    }


def build_cluster_context(city: str) -> dict:
    """
    Listing segmentation — one row per segment with key descriptors.
    Gives the LLM enough to write a market narrative across price tiers.
    """
    path = MODEL_RESULTS / f"clustering_profile_{city}.csv"
    if not path.exists():
        raise FileNotFoundError(f"clustering_profile_{city}.csv not found")

    df = pd.read_csv(path)

    keep_cols = [
        "cluster", "cluster_name", "n", "pct_of_city",
        "median_price", "mean_accommodates", "mean_bedrooms",
        "mean_availability_365", "mean_distance_km",
        "pct_entire_home", "dominant_room_type", "top_neighbourhood",
        "mean_reviews_per_month",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]

    segments = []
    for _, row in df.sort_values("median_price").iterrows():
        seg: dict[str, Any] = {}
        for col in df.columns:
            val = row[col]
            seg[col] = _safe_round(val) if isinstance(val, float) else val
        segments.append(seg)

    return {
        "city": city,
        "currency": _CURRENCY.get(city, "?"),
        "k": len(segments),
        "segments": segments,
    }


def build_host_context(city: str) -> dict:
    """
    Host segmentation — one row per host cluster with portfolio descriptors.
    Gives the LLM enough to characterise host behaviour patterns.
    """
    path = MODEL_RESULTS / f"host_clustering_profile_{city}.csv"
    if not path.exists():
        raise FileNotFoundError(f"host_clustering_profile_{city}.csv not found")

    df = pd.read_csv(path)

    keep_cols = [
        "cluster", "cluster_name", "n", "pct_of_city",
        "median_avg_price", "pct_superhost", "mean_tenure",
        "mean_response_rate", "mean_acceptance_rate",
        "mean_availability", "mean_reviews_per_month",
        "median_listing_count",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]

    segments = []
    for _, row in df.sort_values("pct_of_city", ascending=False).iterrows():
        seg: dict[str, Any] = {}
        for col in df.columns:
            val = row[col]
            seg[col] = _safe_round(val) if isinstance(val, float) else val
        segments.append(seg)

    return {
        "city": city,
        "currency": _CURRENCY.get(city, "?"),
        "k": len(segments),
        "segments": segments,
    }


def build_cross_city_context() -> dict:
    """
    Four-city comparison — one row per city from city_comparison_summary.csv.
    Gives the LLM enough to write a comparative market analysis.
    """
    path = TABLES / "city_comparison_summary.csv"
    if not path.exists():
        raise FileNotFoundError("city_comparison_summary.csv not found")

    df = pd.read_csv(path, index_col=0)

    keep_cols = [
        "city", "total_listings", "unique_hosts", "price_eligible",
        "median_price", "price_null_pct", "median_avail_365",
        "superhost_rate_pct", "pct_entire_home", "pct_commercial",
        "median_rating",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]

    # Attach model MAE per city
    model_maes: dict[str, Any] = {}
    model_algos: dict[str, Any] = {}
    for city in ["london", "amsterdam", "madrid", "berlin"]:
        m = _load_model_metadata(city)
        model_maes[city]  = m.get("mae")
        model_algos[city] = m.get("algorithm")

    cities = []
    city_order = ["london", "amsterdam", "madrid", "berlin"]
    currency_map = {"london": "GBP", "amsterdam": "EUR", "madrid": "EUR", "berlin": "EUR"}
    for _, row in df.iterrows():
        city = row["city"]
        entry: dict[str, Any] = {c: _safe_round(row[c]) if isinstance(row[c], float) else row[c]
                                  for c in df.columns}
        entry["currency"]      = currency_map.get(city, "EUR")
        entry["model_mae"]     = model_maes.get(city)
        entry["model_algo"]    = model_algos.get(city)
        cities.append(entry)

    # Sort by city_order
    cities.sort(key=lambda r: city_order.index(r["city"]) if r["city"] in city_order else 99)

    return {
        "cities": cities,
        "city_order": city_order,
    }
