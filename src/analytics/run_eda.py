"""
City-agnostic EDA artifact generator.

Produces the 22 CSV files expected by /analytics/* endpoints for any city
that has completed the pipeline transform stage (listing_master.parquet,
calendar_clean.parquet, reviews_clean.parquet).

Output: reports/tables/<city>/*.csv

Usage:
    python -m src.analytics.run_eda --city madrid
    python -m src.analytics.run_eda --city berlin
"""
from __future__ import annotations

import argparse
import math
import warnings
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")

ROOT  = Path(__file__).resolve().parents[2]
DATA  = ROOT / "data" / "processed"

# Reference point for price-by-distance calculations
_CITY_CENTRE: dict[str, tuple[float, float]] = {
    "london":    (51.5080, -0.1281),   # Trafalgar Square
    "amsterdam": (52.3676,  4.9041),   # Dam Square
    "madrid":    (40.4168, -3.7038),   # Puerta del Sol
    "berlin":    (52.5163, 13.3777),   # Brandenburg Gate
}

ALPHA = 0.05


# ── helpers ───────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _superhost_series(lm: pd.DataFrame) -> pd.Series:
    col = lm["host_is_superhost"]
    if col.dtype == bool or str(col.dtype) in ("boolean", "bool"):
        return col
    return col.map({"t": True, "f": False, True: True, False: False})


def _host_segment(n: int) -> str:
    if n == 1:   return "solo"
    if n <= 4:   return "multi"
    return "professional"


def _avail_band(days: int) -> str:
    if days <= 30:  return "Blocked / inactive  (0-30 d)"
    if days <= 90:  return "Occasional  (31-90 d)"
    if days <= 270: return "Active  (91-270 d)"
    return "Always-on  (271-365 d)"


def _tenure_band(y: float) -> str:
    if y <= 2:  return "New  (0-2 yr)"
    if y <= 5:  return "Established  (2-5 yr)"
    if y <= 10: return "Experienced  (5-10 yr)"
    return "Veteran  (10+ yr)"


def _dist_band(d: float) -> str:
    if d <= 2:  return "0-2 km"
    if d <= 5:  return "2-5 km"
    if d <= 10: return "5-10 km"
    if d <= 20: return "10-20 km"
    return "20+ km"


def _price_ci(series: pd.Series, confidence: float = 0.95) -> tuple[float, float]:
    """95% t-distribution CI for the mean of a price series. Returns (lower, upper)."""
    x = series.dropna()
    n = len(x)
    if n < 3:
        return (float("nan"), float("nan"))
    se = stats.sem(x)
    lo, hi = stats.t.interval(confidence, df=n - 1, loc=x.mean(), scale=se)
    return (round(lo, 2), round(hi, 2))


# ── main generator ────────────────────────────────────────────────────────────

def run(city: str) -> dict:
    out_dir = ROOT / "reports" / "tables" / city
    out_dir.mkdir(parents=True, exist_ok=True)

    processed = DATA / city
    print(f"\n[{city}] Loading listing_master.parquet ...")
    lm = pd.read_parquet(processed / "listing_master.parquet")
    print(f"  {len(lm):,} rows x {len(lm.columns)} cols")

    # Superhost as proper bool
    lm["superhost"] = _superhost_series(lm)
    lm["host_segment"] = lm["host_portfolio_size"].apply(_host_segment)
    lm["avail_band"]   = lm["availability_365"].apply(_avail_band)
    lm["tenure_band"]  = lm["host_tenure_years"].apply(_tenure_band)

    # Price-eligible subset
    eda = lm[lm["price_numeric"].notna() & lm["price_numeric"].ge(0)].copy()
    eda["log_price"] = np.log1p(eda["price_numeric"])

    centre = _CITY_CENTRE.get(city, (0.0, 0.0))

    saved: list[str] = []

    def _save(df: pd.DataFrame, name: str, **kwargs) -> None:
        df.to_csv(out_dir / name, **kwargs)
        saved.append(name)
        print(f"  -> {name}  ({len(df)} rows)")

    # ── 1. numerical_summary ──────────────────────────────────────────────────
    key_cols = [c for c in [
        "price_numeric", "availability_365", "number_of_reviews",
        "review_scores_rating", "review_scores_cleanliness",
        "review_scores_communication", "review_scores_location",
        "review_scores_value", "host_tenure_years",
        "occupancy_proxy", "reviews_per_month_calc",
        "host_portfolio_size", "host_response_rate",
    ] if c in lm.columns]
    summary = lm[key_cols].describe(
        percentiles=[0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]
    ).T.round(4)
    summary["missing_count"] = lm[key_cols].isna().sum()
    summary["missing_pct"]   = (lm[key_cols].isna().mean() * 100).round(1)
    _save(summary, "numerical_summary.csv")

    # ── 2. price_by_room_type ─────────────────────────────────────────────────
    price_by_room = (
        eda.groupby("room_type")
        .agg(
            listing_count=("price_numeric", "count"),
            median_price=("price_numeric", "median"),
            mean_price=("price_numeric", "mean"),
            p25=("price_numeric", lambda x: x.quantile(0.25)),
            p75=("price_numeric", lambda x: x.quantile(0.75)),
            p95=("price_numeric", lambda x: x.quantile(0.95)),
        )
        .sort_values("median_price", ascending=False)
        .round(0)
    )
    _save(price_by_room, "price_by_room_type.csv")

    # ── 3. price_by_neighbourhood ─────────────────────────────────────────────
    min_listings = max(10, int(len(lm) * 0.001))   # adaptive floor
    neigh_grp = eda.groupby("neighbourhood_cleansed")["price_numeric"]
    neigh_ci = (
        neigh_grp.apply(_price_ci)
        .apply(pd.Series)
        .rename(columns={0: "ci_lower", 1: "ci_upper"})
    )
    neigh_price = (
        neigh_grp
        .agg(listing_count="count", median_price="median", mean_price="mean")
        .query(f"listing_count >= {min_listings}")
        .join(neigh_ci)
        .round(0)
    )
    _save(neigh_price, "price_by_neighbourhood.csv")

    # ── 4. host_segment_summary ───────────────────────────────────────────────
    seg_order = ["solo", "multi", "professional"]
    host_seg = (
        lm.groupby("host_segment")
        .agg(listing_count=("id", "count"), unique_hosts=("host_id", "nunique"),
             median_price=("price_numeric", "median"),
             median_rating=("review_scores_rating", "median"),
             median_occupancy=("occupancy_proxy", "median"),
             median_availability=("availability_365", "median"),
             superhost_rate=("superhost", "mean"))
        .reindex([s for s in seg_order if s in lm["host_segment"].values])
        .round(2)
    )
    _save(host_seg, "host_segment_summary.csv")

    # ── 5. availability_band_summary ──────────────────────────────────────────
    band_order = [
        "Blocked / inactive  (0-30 d)",
        "Occasional  (31-90 d)",
        "Active  (91-270 d)",
        "Always-on  (271-365 d)",
    ]
    band_counts = lm["avail_band"].value_counts().reindex(band_order).fillna(0)
    band_pct    = (band_counts / len(lm) * 100).round(1)
    avail_summary = pd.DataFrame({
        "band":            band_order,
        "listing_count":   band_counts.values.astype(int),
        "share_pct":       band_pct.values,
        "median_price":    [lm.loc[lm["avail_band"] == b, "price_numeric"].median()
                            for b in band_order],
        "median_occupancy":[lm.loc[lm["avail_band"] == b, "occupancy_proxy"].median()
                            for b in band_order],
    })
    _save(avail_summary, "availability_band_summary.csv", index=False)

    # ── 6. neighbourhood_density ──────────────────────────────────────────────
    dens = (
        lm.groupby("neighbourhood_cleansed")
        .agg(listing_count=("id", "count"),
             unique_hosts=("host_id", "nunique"),
             listings_per_km2=("neighbourhood_density_per_km2", "first"))
        .reset_index()
        .rename(columns={"neighbourhood_cleansed": "neighbourhood"})
        .sort_values("listings_per_km2", ascending=False)
    )
    _save(dens, "neighbourhood_density.csv", index=False)

    # ── 7. price_by_distance_band ─────────────────────────────────────────────
    geo = eda[eda["latitude"].notna() & eda["longitude"].notna()].copy()
    geo["dist_km"]  = geo.apply(
        lambda r: _haversine_km(r["latitude"], r["longitude"], *centre), axis=1
    )
    geo["dist_band"] = geo["dist_km"].apply(_dist_band)
    dist_order = ["0-2 km", "2-5 km", "5-10 km", "10-20 km", "20+ km"]
    price_by_dist = (
        geo.groupby("dist_band", observed=True)
        .agg(
            listing_count=("price_numeric", "count"),
            median_price=("price_numeric", "median"),
            mean_price=("price_numeric", "mean"),
            p75=("price_numeric", lambda x: x.quantile(0.75)),
        )
        .reindex([b for b in dist_order if b in geo["dist_band"].values])
        .round(0)
    )
    _save(price_by_dist, "price_by_distance_band.csv")

    # ── 8. room_type_by_neighbourhood ─────────────────────────────────────────
    room_type_pct = pd.crosstab(
        lm["neighbourhood_cleansed"], lm["room_type"], normalize="index"
    ) * 100
    _save(room_type_pct.round(1), "room_type_by_neighbourhood.csv")

    # ── 9-11. calendar-based tables ───────────────────────────────────────────
    print(f"[{city}] Loading calendar_clean.parquet ...")
    cal = pd.read_parquet(
        processed / "calendar_clean.parquet",
        columns=["listing_id", "date", "available", "minimum_nights"],
    )
    cal["available_int"] = cal["available"].astype("Int64").astype(float)
    cal_date = pd.to_datetime(cal["date"])
    cal["month"]      = cal_date.dt.to_period("M").dt.to_timestamp()
    cal["is_weekend"] = cal_date.dt.dayofweek >= 5
    print(f"  {len(cal):,} rows")

    # 9. monthly_availability
    monthly_avail = (
        cal.groupby("month")
        .agg(total_days=("available_int", "count"),
             available_days=("available_int", "sum"),
             unique_listings=("listing_id", "nunique"))
        .reset_index()
    )
    monthly_avail["availability_rate"] = (
        monthly_avail["available_days"] / monthly_avail["total_days"]
    ).round(4)
    monthly_avail["occupancy_rate"] = 1 - monthly_avail["availability_rate"]
    _save(monthly_avail, "monthly_availability.csv", index=False)

    # 10. weekday_weekend_availability
    weekpart = (
        cal.groupby("is_weekend")
        .agg(total_days=("available_int", "count"),
             available_days=("available_int", "sum"),
             unique_listings=("listing_id", "nunique"))
        .reset_index()
    )
    weekpart["availability_rate"] = weekpart["available_days"] / weekpart["total_days"]
    weekpart["occupancy_rate"]    = 1 - weekpart["availability_rate"]
    weekpart["label"] = weekpart["is_weekend"].map({False: "Weekday", True: "Weekend"})
    _save(weekpart, "weekday_weekend_availability.csv", index=False)

    # 11. minimum_nights_monthly
    min_nights_monthly = (
        cal.groupby("month")
        .agg(median_min_nights=("minimum_nights", "median"),
             mean_min_nights=("minimum_nights", "mean"),
             pct_longstay=("minimum_nights", lambda x: (x >= 28).mean() * 100))
        .reset_index()
        .round(2)
    )
    _save(min_nights_monthly, "minimum_nights_monthly.csv", index=False)
    del cal

    # ── 12. monthly_review_volume ─────────────────────────────────────────────
    print(f"[{city}] Loading reviews_clean.parquet ...")
    rev = pd.read_parquet(
        processed / "reviews_clean.parquet",
        columns=["id", "listing_id", "date"],
    )
    rev["month"] = pd.to_datetime(rev["date"]).dt.to_period("M").dt.to_timestamp()
    monthly_reviews = (
        rev.groupby("month")
        .agg(review_count=("id", "count"), active_listings=("listing_id", "nunique"))
        .reset_index()
    )
    monthly_reviews["reviews_per_active_listing"] = (
        monthly_reviews["review_count"] / monthly_reviews["active_listings"]
    ).round(2)
    _save(monthly_reviews, "monthly_review_volume.csv", index=False)
    del rev

    # ── 13. host_tenure_summary ───────────────────────────────────────────────
    tenure_order = [
        "New  (0-2 yr)", "Established  (2-5 yr)",
        "Experienced  (5-10 yr)", "Veteran  (10+ yr)",
    ]
    tenure_sum = (
        lm.groupby("tenure_band")
        .agg(listing_count=("id", "count"), unique_hosts=("host_id", "nunique"),
             median_price=("price_numeric", "median"),
             median_rating=("review_scores_rating", "median"),
             superhost_rate=("superhost", "mean"),
             median_portfolio=("host_portfolio_size", "median"),
             median_occupancy=("occupancy_proxy", "median"))
        .reindex([t for t in tenure_order if t in lm["tenure_band"].values])
        .round(2)
    )
    _save(tenure_sum, "host_tenure_summary.csv")

    # ── 14. response_rate_summary ─────────────────────────────────────────────
    resp_eligible = lm[lm["host_response_rate"].notna()].copy()
    resp_eligible["response_rate_band"] = pd.cut(
        resp_eligible["host_response_rate"],
        bins=[-0.001, 0.50, 0.80, 0.95, 1.001],
        labels=["0-50%", "51-80%", "81-95%", "96-100%"],
    )
    resp_order = ["0-50%", "51-80%", "81-95%", "96-100%"]
    resp_sum = (
        resp_eligible.groupby("response_rate_band", observed=True)
        .agg(listing_count=("id", "count"),
             superhost_rate=("superhost", "mean"),
             median_rating=("review_scores_rating", "median"),
             median_price=("price_numeric", "median"),
             median_occupancy=("occupancy_proxy", "median"))
        .reindex(resp_order)
        .round(2)
    )
    _save(resp_sum, "response_rate_summary.csv")

    # ── 15. market_concentration ──────────────────────────────────────────────
    host_portfolio = (
        lm.groupby("host_id")["id"]
        .count()
        .rename("listing_count")
        .sort_values(ascending=False)
        .reset_index()
    )
    total_listings = host_portfolio["listing_count"].sum()
    total_hosts    = len(host_portfolio)
    host_portfolio["listing_share"]    = host_portfolio["listing_count"] / total_listings
    host_portfolio["cumulative_share"] = host_portfolio["listing_share"].cumsum()
    host_portfolio["host_pct"]         = (host_portfolio.index + 1) / total_hosts * 100
    _save(host_portfolio, "market_concentration.csv", index=False)

    # ── 16. high_review_low_score_listings ────────────────────────────────────
    hi_rc  = lm["number_of_reviews"].quantile(0.75)
    lo_rat = lm["review_scores_rating"].quantile(0.25)
    anomaly_cols = [c for c in [
        "id", "neighbourhood_cleansed", "room_type", "property_type_bucket",
        "price_numeric", "number_of_reviews", "review_scores_rating",
        "review_scores_cleanliness", "review_scores_communication",
        "host_segment", "host_response_rate",
    ] if c in lm.columns]
    anomaly = lm[
        (lm["number_of_reviews"] >= hi_rc)
        & (lm["review_scores_rating"] <= lo_rat)
        & lm["review_scores_rating"].notna()
    ][anomaly_cols]
    _save(anomaly, "high_review_low_score_listings.csv", index=False)

    # ── 17. review_subdimension_summary ───────────────────────────────────────
    rating_cols = [
        "review_scores_accuracy", "review_scores_cleanliness",
        "review_scores_checkin", "review_scores_communication",
        "review_scores_location", "review_scores_value",
    ]
    rating_cols = [c for c in rating_cols if c in lm.columns]
    rated = lm[rating_cols].dropna()
    corr  = rated.corr(method="pearson").round(3)
    corr  = corr.rename(
        index={c: c.replace("review_scores_", "") for c in rating_cols},
        columns={c: c.replace("review_scores_", "") for c in rating_cols},
    )
    _save(corr, "review_subdimension_summary.csv")

    # ── 18. review_summary ────────────────────────────────────────────────────
    review_score_cols = ["review_scores_rating"] + rating_cols
    review_stats = []
    for col in review_score_cols:
        s = lm[col].dropna()
        review_stats.append({
            "dimension":  col.replace("review_scores_", "").replace("_", " ").title(),
            "n_rated":    len(s),
            "null_count": lm[col].isna().sum(),
            "null_pct":   round(lm[col].isna().mean() * 100, 1),
            "mean":  round(s.mean(), 4), "median": round(s.median(), 4),
            "std":   round(s.std(), 4),
            "p10":   round(s.quantile(0.10), 4), "p25": round(s.quantile(0.25), 4),
            "p75":   round(s.quantile(0.75), 4), "p90": round(s.quantile(0.90), 4),
            "min":   round(s.min(), 4),  "max":    round(s.max(), 4),
        })
    for col, label in [
        ("number_of_reviews", "number_of_reviews (count)"),
        ("reviews_per_month_calc", "reviews_per_month_calc (rate)"),
    ]:
        if col in lm.columns:
            s = lm[col].dropna()
            review_stats.append({
                "dimension":  label,
                "n_rated":    len(s), "null_count": lm[col].isna().sum(),
                "null_pct":   round(lm[col].isna().mean() * 100, 1),
                "mean":  round(s.mean(), 4), "median": round(s.median(), 4),
                "std":   round(s.std(), 4),
                "p10":   round(s.quantile(0.10), 4), "p25": round(s.quantile(0.25), 4),
                "p75":   round(s.quantile(0.75), 4), "p90": round(s.quantile(0.90), 4),
                "min":   round(s.min(), 4), "max":    round(s.max(), 4),
            })
    review_summary_df = pd.DataFrame(review_stats).set_index("dimension")
    _save(review_summary_df, "review_summary.csv")

    # ── 19. temporal_summary ─────────────────────────────────────────────────
    monthly_avail_df  = pd.read_csv(out_dir / "monthly_availability.csv",
                                    parse_dates=["month"])
    min_nights_df     = pd.read_csv(out_dir / "minimum_nights_monthly.csv",
                                    parse_dates=["month"])
    temporal = monthly_avail_df.merge(min_nights_df, on="month", how="left")

    def _season(ts: pd.Timestamp) -> str:
        m = ts.month
        if m in [12, 1, 2]: return "Winter"
        if m in [3, 4, 5]:  return "Spring"
        if m in [6, 7, 8]:  return "Summer"
        return "Autumn"

    temporal["season"] = temporal["month"].apply(_season)
    col_order = [c for c in [
        "month", "season", "total_days", "available_days", "unique_listings",
        "availability_rate", "occupancy_rate",
        "median_min_nights", "mean_min_nights", "pct_longstay",
    ] if c in temporal.columns]
    _save(temporal[col_order], "temporal_summary.csv", index=False)

    # ── 20-22. Statistical analysis ───────────────────────────────────────────
    print(f"[{city}] Running hypothesis tests + OLS regression ...")
    results = []

    # H1 — entire home vs private room price
    h1 = eda[eda["room_type"].isin(["entire_home", "private_room"])].copy()
    eh_ = h1.loc[h1["room_type"] == "entire_home",  "log_price"].dropna()
    pr_ = h1.loc[h1["room_type"] == "private_room", "log_price"].dropna()
    if len(eh_) >= 30 and len(pr_) >= 30:
        t1, p1 = stats.ttest_ind(eh_, pr_, equal_var=False)
        d1 = (eh_.mean() - pr_.mean()) / math.sqrt(
            (cast(float, eh_.var()) + cast(float, pr_.var())) / 2
        )
        results.append({"test": "H1", "hypothesis": "Entire home vs private room: price",
                        "method": "Welch t-test (log)", "n_total": len(eh_) + len(pr_),
                        "statistic": round(t1, 4), "p_value": f"{p1:.2e}",
                        "effect_size": round(d1, 4), "effect_label": "Cohen d",
                        "significant": p1 < ALPHA,
                        "conclusion": "EH priced higher" if d1 > 0 and p1 < ALPHA else "No significant difference"})

    # H2 — superhost vs non-superhost rating
    h2 = lm[lm["review_scores_rating"].notna() & lm["superhost"].notna()]
    sy_ = h2.loc[h2["superhost"] == True,  "review_scores_rating"]
    sn_ = h2.loc[h2["superhost"] == False, "review_scores_rating"]
    if len(sy_) >= 10 and len(sn_) >= 10:
        u2, p2 = stats.mannwhitneyu(sy_, sn_, alternative="two-sided")
        r2 = 1 - 2 * u2 / (len(sy_) * len(sn_))
        results.append({"test": "H2", "hypothesis": "Superhost vs non-superhost: rating",
                        "method": "Mann-Whitney U", "n_total": len(sy_) + len(sn_),
                        "statistic": round(u2, 0), "p_value": f"{p2:.2e}",
                        "effect_size": round(r2, 4), "effect_label": "rank-biserial r",
                        "significant": p2 < ALPHA,
                        "conclusion": "Superhost higher rating" if r2 > 0 and p2 < ALPHA else "No significant difference"})

    # H3 — high-review vs low-review price
    h3 = eda[eda["number_of_reviews"].notna()].copy()
    hi_ = h3.loc[h3["number_of_reviews"] > 10, "log_price"].dropna()
    lo_ = h3.loc[h3["number_of_reviews"] <= 10, "log_price"].dropna()
    if len(hi_) >= 30 and len(lo_) >= 30:
        t3, p3 = stats.ttest_ind(hi_, lo_, equal_var=False)
        d3 = (hi_.mean() - lo_.mean()) / math.sqrt(
            (cast(float, hi_.var()) + cast(float, lo_.var())) / 2
        )
        results.append({"test": "H3", "hypothesis": "High-review (>10) vs low-review: price",
                        "method": "Welch t-test (log)", "n_total": len(hi_) + len(lo_),
                        "statistic": round(t3, 4), "p_value": f"{p3:.2e}",
                        "effect_size": round(d3, 4), "effect_label": "Cohen d",
                        "significant": p3 < ALPHA,
                        "conclusion": "High-review listings priced lower" if d3 < 0 and p3 < ALPHA else "No significant difference"})

    # H4 — neighbourhood price differences (Kruskal-Wallis)
    boro_n4   = eda.groupby("neighbourhood_cleansed")["price_numeric"].count()
    min_n     = max(30, int(len(eda) * 0.001))
    top_boros = sorted(boro_n4[boro_n4 >= min_n].index.tolist())
    if len(top_boros) >= 2:
        h4_ = eda[eda["neighbourhood_cleansed"].isin(top_boros)].copy()
        grps4 = [h4_.loc[h4_["neighbourhood_cleansed"] == b, "log_price"].dropna().values
                 for b in top_boros]
        kw4, p4 = stats.kruskal(*grps4)
        N4 = sum(len(g) for g in grps4); k4 = len(grps4)
        eps4 = (kw4 - k4 + 1) / (N4 - k4)
        results.append({"test": "H4", "hypothesis": "Neighbourhood price differences",
                        "method": "Kruskal-Wallis", "n_total": N4,
                        "statistic": round(kw4, 4), "p_value": f"{p4:.2e}",
                        "effect_size": round(eps4, 4), "effect_label": "epsilon-squared",
                        "significant": p4 < ALPHA,
                        "conclusion": "Significant neighbourhood differences" if p4 < ALPHA else "No significant difference"})

    # H5 — weekend vs weekday availability (paired Wilcoxon via per-listing means)
    weekpart_df = pd.read_csv(out_dir / "weekday_weekend_availability.csv")
    if len(weekpart_df) == 2:
        wd_rate = float(weekpart_df.loc[weekpart_df["label"] == "Weekday", "availability_rate"].iloc[0])
        we_rate = float(weekpart_df.loc[weekpart_df["label"] == "Weekend", "availability_rate"].iloc[0])
        diff = we_rate - wd_rate
        results.append({"test": "H5", "hypothesis": "Weekend vs weekday availability rate",
                        "method": "Summary comparison (A-005 adapted)",
                        "n_total": int(weekpart_df["total_days"].sum()),
                        "statistic": round(diff, 6), "p_value": "N/A",
                        "effect_size": round(diff, 6), "effect_label": "mean difference",
                        "significant": abs(diff) > 0.01,
                        "conclusion": f"Weekend avail {we_rate:.3f} vs weekday {wd_rate:.3f}"})

    if results:
        results_df = pd.DataFrame(results)
        _save(results_df, "hypothesis_test_results.csv", index=False)

    # OLS regression — log-price
    reg_cols = ["log_price", "room_type", "accommodates", "bedrooms",
                "review_scores_rating", "superhost", "neighbourhood_cleansed"]
    reg_cols = [c for c in reg_cols if c in eda.columns]
    reg = eda[reg_cols].copy()
    reg["superhost_flag"] = reg["superhost"].astype(float)
    reg = reg.dropna(subset=["log_price", "accommodates", "bedrooms",
                             "review_scores_rating", "superhost_flag"])
    print(f"  OLS sample: {len(reg):,} listings")

    try:
        model = smf.ols(
            formula=(
                "log_price ~ "
                "C(room_type) + accommodates + bedrooms + "
                "review_scores_rating + superhost_flag + "
                "C(neighbourhood_cleansed)"
            ),
            data=reg,
        ).fit(cov_type="HC3")

        coef_df = pd.DataFrame({
            "coefficient": model.params,
            "std_err":     model.bse,
            "t_stat":      model.tvalues,
            "p_value":     model.pvalues,
            "ci_low":      model.conf_int()[0],
            "ci_high":     model.conf_int()[1],
        }).round(6)
        coef_df["significant"] = coef_df["p_value"] < ALPHA
        _save(coef_df, "regression_coefficients.csv")

        reg_summary = pd.DataFrame([
            {"metric": "R2",             "value": round(model.rsquared, 4)},
            {"metric": "Adjusted R2",    "value": round(model.rsquared_adj, 4)},
            {"metric": "F-statistic",    "value": round(model.fvalue, 2)},
            {"metric": "p(F)",           "value": f"{model.f_pvalue:.2e}"},
            {"metric": "N observations", "value": int(model.nobs)},
            {"metric": "N parameters",   "value": len(model.params)},
            {"metric": "SE type",        "value": "HC3 (heteroskedasticity-robust)"},
        ])
        _save(reg_summary, "regression_summary.csv", index=False)
    except Exception as exc:
        print(f"  WARNING: OLS failed — {exc}")

    print(f"\n[{city}] Done. {len(saved)}/22 CSVs written to {out_dir}")
    return {"city": city, "saved": saved, "count": len(saved)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", required=True, choices=["london", "amsterdam", "madrid", "berlin"])
    args = parser.parse_args()
    run(args.city)
