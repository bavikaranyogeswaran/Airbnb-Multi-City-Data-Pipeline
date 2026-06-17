"""IQR outlier detection + domain-rule violations.

Critical: domain-rule sentinels (e.g. maximum_nights = 2**31 - 1, see
A-018) are reported as a separate category so they don't get conflated
with real outliers.

Outputs:
  reports/outliers_summary.md
  reports/outliers_iqr.csv         (per-column boundaries + counts)
  reports/outliers_domain.csv      (per-rule violation counts)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
REPORTS_DIR = ROOT / "reports"

INT_MAX_SENTINEL = 2 ** 30  # anything >= this is treated as the INT_MAX sentinel pattern.


# Numeric columns where IQR is meaningful. Skip identifiers, lat/lon, sentinel-heavy fields.
LISTINGS_IQR_COLS = [
    "accommodates", "bathrooms", "bedrooms", "beds",
    "minimum_nights", "maximum_nights",
    "availability_30", "availability_60", "availability_90", "availability_365",
    "number_of_reviews", "number_of_reviews_ltm",
    "review_scores_rating", "reviews_per_month",
    "calculated_host_listings_count",
    "estimated_occupancy_l365d", "estimated_revenue_l365d",
]

CALENDAR_IQR_COLS = ["minimum_nights", "maximum_nights"]


def iqr_bounds(series: pd.Series) -> tuple[float, float, int, int]:
    """Return (lower, upper, low_outlier_count, high_outlier_count)."""
    s = series.dropna().astype(float)
    if len(s) < 4:
        return float("nan"), float("nan"), 0, 0
    q1, q3 = np.nanpercentile(s, [25, 75])
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    low_n = int((s < lower).sum())
    high_n = int((s > upper).sum())
    return float(lower), float(upper), low_n, high_n


def iqr_for_file(df: pd.DataFrame, source: str, columns: list[str]) -> pd.DataFrame:
    rows = []
    for col in columns:
        if col not in df.columns:
            continue
        s = df[col]

        # Strip the INT_MAX sentinel before IQR for stay-rule columns (A-018).
        flagged_sentinel = 0
        if col in ("maximum_nights", "minimum_maximum_nights", "maximum_maximum_nights"):
            if pd.api.types.is_numeric_dtype(s):
                sentinel_mask = s >= INT_MAX_SENTINEL
                flagged_sentinel = int(sentinel_mask.sum())
                s = s.where(~sentinel_mask)

        lower, upper, low_n, high_n = iqr_bounds(s)
        rows.append({
            "source_file": source,
            "column": col,
            "non_null": int(s.dropna().shape[0]),
            "iqr_lower": round(lower, 4) if not np.isnan(lower) else "",
            "iqr_upper": round(upper, 4) if not np.isnan(upper) else "",
            "low_outliers": low_n,
            "high_outliers": high_n,
            "sentinel_int_max_rows": flagged_sentinel,
        })
    return pd.DataFrame(rows)


def domain_rules_listings(listings_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        listings_path,
        compression="gzip",
        usecols=["id", "price", "latitude", "longitude",
                 "minimum_nights", "maximum_nights",
                 "availability_30", "availability_60", "availability_90", "availability_365",
                 "number_of_reviews", "accommodates", "bedrooms", "beds"],
        low_memory=False,
    )

    # Parse price for the rule.
    price_num = (
        df["price"].astype("string").str.replace(r"[^0-9.\-]", "", regex=True)
    )
    price_num = pd.to_numeric(price_num, errors="coerce")

    rules = [
        ("price_negative",                  (price_num < 0).sum()),
        ("price_zero",                      (price_num == 0).sum()),
        ("latitude_out_of_range",           (~df["latitude"].between(-90, 90)).sum()),
        ("longitude_out_of_range",          (~df["longitude"].between(-180, 180)).sum()),
        ("latitude_outside_london_bbox",    (~df["latitude"].between(51.2, 51.8)).sum()),
        ("longitude_outside_london_bbox",   (~df["longitude"].between(-0.55, 0.35)).sum()),
        ("minimum_nights_le_zero",          (df["minimum_nights"] <= 0).sum()),
        ("minimum_nights_ge_365",           (df["minimum_nights"] >= 365).sum()),   # A-019 sentinel
        ("maximum_nights_int_max_sentinel", (df["maximum_nights"] >= INT_MAX_SENTINEL).sum()),
        ("availability_30_out_of_range",    (~df["availability_30"].between(0, 30)).sum()),
        ("availability_60_out_of_range",    (~df["availability_60"].between(0, 60)).sum()),
        ("availability_90_out_of_range",    (~df["availability_90"].between(0, 90)).sum()),
        ("availability_365_out_of_range",   (~df["availability_365"].between(0, 365)).sum()),
        ("number_of_reviews_negative",      (df["number_of_reviews"] < 0).sum()),
        ("accommodates_le_zero",            (df["accommodates"] <= 0).sum()),
        ("bedrooms_negative",               (df["bedrooms"] < 0).sum()),
        ("beds_negative",                   (df["beds"] < 0).sum()),
    ]
    return pd.DataFrame(
        [{"source_file": "listings.csv.gz", "rule": name, "violation_count": int(n)} for name, n in rules]
    )


def domain_rules_calendar(calendar_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        calendar_path,
        compression="gzip",
        usecols=["listing_id", "available", "minimum_nights", "maximum_nights"],
        low_memory=False,
    )
    rules = [
        ("available_not_in_t_f",            (~df["available"].isin(["t", "f"])).sum()),
        ("minimum_nights_le_zero",          (df["minimum_nights"] <= 0).sum()),
        ("minimum_nights_ge_365",           (df["minimum_nights"] >= 365).sum()),
        ("maximum_nights_int_max_sentinel", (df["maximum_nights"] >= INT_MAX_SENTINEL).sum()),
    ]
    return pd.DataFrame(
        [{"source_file": "calendar.csv.gz", "rule": name, "violation_count": int(n)} for name, n in rules]
    )


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]
        raw_dir = RAW_BASE / city
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        listings = pd.read_csv(raw_dir / "listings.csv.gz", compression="gzip", low_memory=False)
        iqr_l = iqr_for_file(listings, "listings.csv.gz", LISTINGS_IQR_COLS)
        del listings

        calendar = pd.read_csv(
            raw_dir / "calendar.csv.gz",
            compression="gzip",
            usecols=CALENDAR_IQR_COLS,
            low_memory=False,
        )
        iqr_c = iqr_for_file(calendar, "calendar.csv.gz", CALENDAR_IQR_COLS)
        del calendar

        iqr_df = pd.concat([iqr_l, iqr_c], ignore_index=True)
        iqr_out = REPORTS_DIR / "outliers_iqr.csv"
        iqr_df.to_csv(iqr_out, index=False)

        dom_l = domain_rules_listings(raw_dir / "listings.csv.gz")
        dom_c = domain_rules_calendar(raw_dir / "calendar.csv.gz")
        dom_df = pd.concat([dom_l, dom_c], ignore_index=True)
        dom_out = REPORTS_DIR / "outliers_domain.csv"
        dom_df.to_csv(dom_out, index=False)

        lines = ["# Outliers and Rule Violations", "",
                 f"City: **{city}** · Snapshot: **{city_cfg['source']['snapshot_date']}**", "",
                 "Sentinel rows (e.g. `maximum_nights = 2^31 - 1`, A-018) are stripped before IQR is computed; they are counted separately in `sentinel_int_max_rows` so they aren't conflated with real outliers.", "",
                 "## 1. Domain-rule violations", "",
                 "| File | Rule | Violations |", "|---|---|---:|"]
        for _, r in dom_df.iterrows():
            lines.append(f"| `{r['source_file']}` | `{r['rule']}` | {r['violation_count']:,} |")
        lines += ["", "## 2. IQR outliers (sentinels removed first)", "",
                  "| File | Column | Non-null | Lower | Upper | Low outliers | High outliers | Sentinel rows |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"]
        for _, r in iqr_df.iterrows():
            lines.append(
                f"| `{r['source_file']}` | `{r['column']}` | {r['non_null']:,} | "
                f"{r['iqr_lower']} | {r['iqr_upper']} | "
                f"{r['low_outliers']:,} | {r['high_outliers']:,} | {r['sentinel_int_max_rows']:,} |"
            )
        lines += ["", "## 3. Phase 2.2 implications", "",
                  "- IQR \"outliers\" on bounded columns (`availability_*`, `review_scores_rating`) are statistical artifacts of the long tail at zero — not data errors. They should NOT be quarantined.",
                  "- Domain-rule violations on `latitude`/`longitude` *would* be quarantined, but London passes them all.",
                  "- Sentinel rows in `maximum_nights` map to NULL in Phase 2.2 (`cap_sentinel_intmax`).",
                  "- Listings with `minimum_nights >= 365` flow into `is_de_facto_inactive` in Phase 2.3 (A-019)."]
        summary_out = REPORTS_DIR / "outliers_summary.md"
        summary_out.write_text("\n".join(lines), encoding="utf-8")

    violations_triggered = int((dom_df["violation_count"] > 0).sum())
    return make_result(
        step="ingestion.outliers",
        outputs=[iqr_out, dom_out, summary_out],
        summary={
            "city": city,
            "iqr_columns": int(len(iqr_df)),
            "domain_rules_checked": int(len(dom_df)),
            "domain_rules_triggered": violations_triggered,
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
