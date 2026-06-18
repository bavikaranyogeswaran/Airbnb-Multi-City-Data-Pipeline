"""Key uniqueness, composite-key duplicate, and orphan-record checks.

Loads only the columns needed for each check so calendar (35M rows) does
not pin 2+ GB of RAM. Writes `reports/key_integrity.md`.

NO mutation: no duplicate is dropped, no orphan is deleted. This step
only counts and documents per the familiarization plan.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"

def _raw(city: str) -> Path:
    return ROOT / "data" / "raw" / city


def md_kv(label: str, value) -> str:
    return f"- **{label}:** {value}"


def check_listings(raw: Path = None) -> dict:
    if raw is None:
        raw = _raw("london")
    df = pd.read_csv(
        raw / "listings.csv.gz",
        compression="gzip",
        usecols=["id", "host_id", "neighbourhood_cleansed"],
        low_memory=False,
    )
    n = len(df)
    return {
        "row_count": n,
        "id_unique": bool(df["id"].is_unique),
        "id_null_count": int(df["id"].isna().sum()),
        "host_id_null_count": int(df["host_id"].isna().sum()),
        "distinct_host_count": int(df["host_id"].nunique(dropna=True)),
        "neighbourhood_null_count": int(df["neighbourhood_cleansed"].isna().sum()),
        "distinct_neighbourhood_count": int(df["neighbourhood_cleansed"].nunique(dropna=True)),
        "_df": df,
    }


def check_reviews(listings_ids: pd.Series, raw: Path = None) -> dict:
    if raw is None:
        raw = _raw("london")
    df = pd.read_csv(
        raw / "reviews.csv.gz",
        compression="gzip",
        usecols=["id", "listing_id"],
        low_memory=False,
    )
    n = len(df)
    is_unique = bool(df["id"].is_unique)
    dup_count = int(df["id"].duplicated().sum())
    distinct_listings_in_reviews = int(df["listing_id"].nunique(dropna=True))

    orphan_mask = ~df["listing_id"].isin(listings_ids)
    orphan_row_count = int(orphan_mask.sum())
    orphan_listing_count = int(df.loc[orphan_mask, "listing_id"].nunique())

    return {
        "row_count": n,
        "id_unique": is_unique,
        "id_duplicate_row_count": dup_count,
        "distinct_listing_id_in_reviews": distinct_listings_in_reviews,
        "orphan_review_row_count": orphan_row_count,
        "orphan_listing_count": orphan_listing_count,
        "orphan_pct": round(orphan_row_count / n * 100, 4) if n else 0.0,
    }


def check_calendar(listings_ids: pd.Series, raw: Path = None) -> dict:
    if raw is None:
        raw = _raw("london")
    df = pd.read_csv(
        raw / "calendar.csv.gz",
        compression="gzip",
        usecols=["listing_id", "date"],
        low_memory=False,
    )
    n = len(df)
    composite_dup_count = int(df.duplicated(subset=["listing_id", "date"]).sum())
    distinct_listings_in_calendar = int(df["listing_id"].nunique(dropna=True))

    orphan_mask = ~df["listing_id"].isin(listings_ids)
    orphan_row_count = int(orphan_mask.sum())
    orphan_listing_count = int(df.loc[orphan_mask, "listing_id"].nunique())

    missing = set(listings_ids.tolist()) - set(df["listing_id"].unique().tolist())

    return {
        "row_count": n,
        "composite_key_duplicate_count": composite_dup_count,
        "distinct_listing_id_in_calendar": distinct_listings_in_calendar,
        "orphan_calendar_row_count": orphan_row_count,
        "orphan_listing_count": orphan_listing_count,
        "listings_with_no_calendar_count": len(missing),
        "orphan_pct": round(orphan_row_count / n * 100, 4) if n else 0.0,
    }


def check_neighbourhoods(listings_neigh: pd.Series, raw: Path = None) -> dict:
    if raw is None:
        raw = _raw("london")
    csv = pd.read_csv(raw / "neighbourhoods.csv")
    with (raw / "neighbourhoods.geojson").open("r", encoding="utf-8") as f:
        gj = json.load(f)
    gj_names = pd.Series(
        [feat["properties"].get("neighbourhood") for feat in gj["features"]]
    )

    csv_pk_unique = bool(csv["neighbourhood"].is_unique)
    csv_names = set(csv["neighbourhood"].dropna())
    gj_names_set = set(gj_names.dropna())

    listings_neigh_set = set(listings_neigh.dropna())
    fk_orphans = listings_neigh_set - csv_names

    return {
        "csv_row_count": len(csv),
        "csv_pk_unique": csv_pk_unique,
        "geojson_feature_count": len(gj["features"]),
        "csv_geojson_parity": csv_names == gj_names_set,
        "csv_only": sorted(csv_names - gj_names_set),
        "geojson_only": sorted(gj_names_set - csv_names),
        "listings_neighbourhood_orphans": sorted(fk_orphans),
    }


def render_markdown(L: dict, R: dict, C: dict, N: dict) -> str:
    ok = "✓"
    fail = "✗"

    def flag(b: bool) -> str:
        return ok if b else fail

    lines = []
    lines.append("# Key Integrity Report")
    lines.append("")
    lines.append("City: **London** · Snapshot: **2025-09-14**")
    lines.append("")
    lines.append("All checks below are read-only. No duplicates were dropped, no orphans deleted. Phase 2 will decide whether to quarantine or repair each finding.")
    lines.append("")

    # Listings
    lines.append("## 1. Listings primary key")
    lines.append("")
    lines.append(md_kv("Row count", f"{L['row_count']:,}"))
    lines.append(md_kv(f"`id` is unique {flag(L['id_unique'])}", L["id_unique"]))
    lines.append(md_kv("`id` null count", L["id_null_count"]))
    lines.append(md_kv("`host_id` null count", L["host_id_null_count"]))
    lines.append(md_kv("Distinct hosts", f"{L['distinct_host_count']:,}"))
    lines.append(md_kv("Distinct neighbourhoods (cleansed)", L["distinct_neighbourhood_count"]))
    lines.append(md_kv("Listings with null neighbourhood_cleansed", L["neighbourhood_null_count"]))
    lines.append("")

    # Reviews
    lines.append("## 2. Reviews primary key + FK")
    lines.append("")
    lines.append(md_kv("Row count", f"{R['row_count']:,}"))
    lines.append(md_kv(f"`id` is unique {flag(R['id_unique'])}", R["id_unique"]))
    lines.append(md_kv("`id` duplicate row count", R["id_duplicate_row_count"]))
    lines.append(md_kv("Distinct `listing_id` referenced", f"{R['distinct_listing_id_in_reviews']:,}"))
    lines.append(md_kv("Orphan review rows (listing_id not in listings)", f"{R['orphan_review_row_count']:,}"))
    lines.append(md_kv("Distinct orphan listing_ids", f"{R['orphan_listing_count']:,}"))
    lines.append(md_kv("Orphan rate", f"{R['orphan_pct']}%"))
    lines.append("")

    # Calendar
    lines.append("## 3. Calendar composite key + FK")
    lines.append("")
    lines.append(md_kv("Row count", f"{C['row_count']:,}"))
    lines.append(md_kv(f"`(listing_id, date)` duplicate count {flag(C['composite_key_duplicate_count']==0)}", f"{C['composite_key_duplicate_count']:,}"))
    lines.append(md_kv("Distinct `listing_id` in calendar", f"{C['distinct_listing_id_in_calendar']:,}"))
    lines.append(md_kv("Orphan calendar rows (listing_id not in listings)", f"{C['orphan_calendar_row_count']:,}"))
    lines.append(md_kv("Distinct orphan listing_ids", f"{C['orphan_listing_count']:,}"))
    lines.append(md_kv("Listings present in listings.csv.gz but absent from calendar", f"{C['listings_with_no_calendar_count']:,}"))
    lines.append(md_kv("Orphan rate", f"{C['orphan_pct']}%"))
    lines.append("")

    # Neighbourhoods
    lines.append("## 4. Neighbourhoods reference integrity")
    lines.append("")
    lines.append(md_kv("CSV row count", N["csv_row_count"]))
    lines.append(md_kv(f"CSV PK (`neighbourhood`) unique {flag(N['csv_pk_unique'])}", N["csv_pk_unique"]))
    lines.append(md_kv("GeoJSON feature count", N["geojson_feature_count"]))
    lines.append(md_kv(f"CSV ↔ GeoJSON name parity {flag(N['csv_geojson_parity'])}", N["csv_geojson_parity"]))
    if N["csv_only"]:
        lines.append(md_kv("CSV-only names", N["csv_only"]))
    if N["geojson_only"]:
        lines.append(md_kv("GeoJSON-only names", N["geojson_only"]))
    lines.append(md_kv(
        f"listings.neighbourhood_cleansed values not in neighbourhoods.csv {flag(not N['listings_neighbourhood_orphans'])}",
        N["listings_neighbourhood_orphans"] or "none",
    ))
    lines.append("")

    # Summary table
    lines.append("## 5. Summary table")
    lines.append("")
    lines.append("| Check | Result |")
    lines.append("|---|---|")
    lines.append(f"| listings.id unique | {flag(L['id_unique'])} |")
    lines.append(f"| reviews.id unique | {flag(R['id_unique'])} |")
    lines.append(f"| calendar (listing_id, date) unique | {flag(C['composite_key_duplicate_count']==0)} |")
    lines.append(f"| reviews orphan rows | {R['orphan_review_row_count']:,} ({R['orphan_pct']}%) |")
    lines.append(f"| calendar orphan rows | {C['orphan_calendar_row_count']:,} ({C['orphan_pct']}%) |")
    lines.append(f"| neighbourhoods CSV ↔ GeoJSON parity | {flag(N['csv_geojson_parity'])} |")
    lines.append(f"| listings → neighbourhoods FK clean | {flag(not N['listings_neighbourhood_orphans'])} |")
    lines.append("")

    lines.append("## 6. Decisions deferred to Phase 2")
    lines.append("")
    lines.append("- Whether to drop orphan reviews / orphan calendar rows or to keep them with a `_orphan` flag.")
    lines.append("- How to handle listings that appear in `listings.csv.gz` but not in `calendar.csv.gz`.")
    lines.append("- How to treat listings whose `neighbourhood_cleansed` does not match the borough CSV (point-in-polygon repair via GeoPandas, or quarantine).")

    return "\n".join(lines)


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    raw = _raw(city)
    with timed() as elapsed:
        L = check_listings(raw)
        listings_ids = L.pop("_df")["id"]
        R = check_reviews(listings_ids, raw)
        C = check_calendar(listings_ids, raw)
        df_n = pd.read_csv(
            raw / "listings.csv.gz",
            compression="gzip",
            usecols=["neighbourhood_cleansed"],
            low_memory=False,
        )
        N = check_neighbourhoods(df_n["neighbourhood_cleansed"], raw)

        md = render_markdown(L, R, C, N)
        out = REPORTS_DIR / "key_integrity.md"
        out.write_text(md, encoding="utf-8")

    return make_result(
        step="familiarization.key_integrity",
        outputs=[out],
        summary={
            "listings_id_unique": L["id_unique"],
            "reviews_id_unique": R["id_unique"],
            "calendar_composite_duplicates": C["composite_key_duplicate_count"],
            "reviews_orphan_rows": R["orphan_review_row_count"],
            "calendar_orphan_rows": C["orphan_calendar_row_count"],
            "listings_absent_from_calendar": C["listings_with_no_calendar_count"],
            "distinct_hosts": L["distinct_host_count"],
            "csv_geojson_parity": N["csv_geojson_parity"],
        },
        elapsed_seconds=elapsed(),
    )


def main() -> None:
    print(run())


if __name__ == "__main__":
    main()
