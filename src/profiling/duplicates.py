"""Exact and fuzzy duplicate detection.

Exact: row-level full-row duplicates per file. (PK-level duplicates are
covered separately in key_integrity.md.)

Fuzzy listings: block by (neighbourhood_cleansed, host_id,
round(latitude, 3), round(longitude, 3)) and consider listings in the
same block with the same name (lowercased, whitespace-normalised) as a
candidate duplicate pair. Reported, never deleted (A-030 principle for
listings).

Fuzzy reviews: report the count of comment-text exact-duplicates within
reviews. Distinct review.id, so PK is fine; this is content-level
duplication. The number was first seen in Step 6 (3.5%); recomputed here
with the cohort of listings that hold most of them.

Outputs:
  reports/duplicates_summary.md
  reports/duplicate_listings.csv  (one row per candidate-dup pair)
  reports/duplicate_review_comments.csv  (top-N comment templates)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
RAW_BASE = ROOT / "data" / "raw"
REPORTS_DIR = ROOT / "reports"

NAME_NORMALISE_RE = re.compile(r"\s+")


def normalise_name(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return NAME_NORMALISE_RE.sub(" ", str(s).strip().lower())


def exact_duplicates(df: pd.DataFrame) -> int:
    return int(df.duplicated().sum())


def fuzzy_listing_duplicates(listings_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        listings_path,
        compression="gzip",
        usecols=["id", "host_id", "name", "neighbourhood_cleansed",
                 "latitude", "longitude", "room_type", "property_type"],
        low_memory=False,
    )
    df["name_norm"] = df["name"].apply(normalise_name)
    df["lat_blk"] = df["latitude"].round(3)
    df["lon_blk"] = df["longitude"].round(3)

    block_cols = ["neighbourhood_cleansed", "host_id", "lat_blk", "lon_blk", "name_norm"]
    df = df[df["name_norm"] != ""]

    grouped = df.groupby(block_cols, dropna=False)
    sizes = grouped.size()
    dup_blocks = sizes[sizes > 1].index

    if len(dup_blocks) == 0:
        return pd.DataFrame()

    keep = grouped.filter(lambda g: len(g) > 1).copy()
    keep["block_size"] = keep.groupby(block_cols, dropna=False)["id"].transform("size")
    keep = keep.sort_values(["block_size", "neighbourhood_cleansed", "host_id", "name_norm"], ascending=[False, True, True, True])
    return keep[["block_size", "id", "host_id", "neighbourhood_cleansed",
                 "name", "latitude", "longitude", "room_type", "property_type"]]


def review_comment_templates(reviews_path: Path, top_n: int = 20) -> tuple[int, int, pd.DataFrame]:
    df = pd.read_csv(
        reviews_path,
        compression="gzip",
        usecols=["id", "listing_id", "comments"],
        low_memory=False,
    )
    df["comments"] = df["comments"].fillna("")
    df["comment_norm"] = df["comments"].str.strip().str.lower()

    counts = df["comment_norm"].value_counts()
    duplicate_text_rows = int((df["comment_norm"].map(counts) > 1).sum())
    distinct_template_count = int((counts > 1).sum())

    top_dups = counts.head(top_n).reset_index()
    top_dups.columns = ["comment_norm", "occurrences"]
    top_dups["preview"] = top_dups["comment_norm"].str.slice(0, 100)
    top_dups = top_dups[["occurrences", "preview"]]
    return duplicate_text_rows, distinct_template_count, top_dups


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()

    with CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    city_cfg = cfg["cities"][args.city]
    raw_dir = RAW_BASE / args.city
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("-> exact duplicates (per file)")
    exact_counts: dict[str, dict[str, int]] = {}
    for key, file_cfg in city_cfg["files"].items():
        name = file_cfg["name"]
        path = raw_dir / name
        if not path.exists():
            continue
        if name.endswith(".geojson"):
            continue  # GeoJSON dup-row notion is not meaningful here.

        # For calendar reviews comments we only need a subset to detect dups cheaply.
        if name == "calendar.csv.gz":
            df = pd.read_csv(path, compression="gzip", low_memory=False)
        elif name == "reviews.csv.gz":
            df = pd.read_csv(path, compression="gzip", usecols=["id", "listing_id", "date", "reviewer_id"], low_memory=False)
        elif name == "listings.csv.gz":
            df = pd.read_csv(path, compression="gzip", low_memory=False)
        else:
            df = pd.read_csv(path, compression="gzip" if file_cfg.get("compressed") else None, low_memory=False)

        n_dup = exact_duplicates(df)
        exact_counts[name] = {"row_count": int(len(df)), "exact_dup_count": n_dup}
        print(f"  {name:28} {n_dup:>10,} exact dups in {len(df):>12,} rows")

    print("\n-> fuzzy listing duplicates (block by neigh/host/lat3/lon3/name)")
    fuzzy = fuzzy_listing_duplicates(raw_dir / "listings.csv.gz")
    print(f"  candidate-dup blocks: {fuzzy.groupby(['host_id','name'], dropna=False).ngroups if not fuzzy.empty else 0}")
    print(f"  rows in candidate-dup blocks: {len(fuzzy)}")
    if not fuzzy.empty:
        fuzzy.to_csv(REPORTS_DIR / "duplicate_listings.csv", index=False)
        print(f"  wrote reports/duplicate_listings.csv")

    print("\n-> review comment templates")
    dup_text_rows, template_count, top = review_comment_templates(raw_dir / "reviews.csv.gz")
    print(f"  reviews with a duplicate-text twin: {dup_text_rows:,}")
    print(f"  distinct templates (text shared by 2+ reviews): {template_count:,}")
    top.to_csv(REPORTS_DIR / "duplicate_review_comments.csv", index=False)
    print(f"  wrote reports/duplicate_review_comments.csv")

    # Summary markdown
    lines = []
    lines.append("# Duplicate Findings")
    lines.append("")
    lines.append(f"City: **{args.city}** · Snapshot: **{city_cfg['source']['snapshot_date']}**")
    lines.append("")
    lines.append("## 1. Exact row duplicates (per file)")
    lines.append("")
    lines.append("| File | Rows | Exact dup rows |")
    lines.append("|---|---:|---:|")
    for name, stats in exact_counts.items():
        lines.append(f"| `{name}` | {stats['row_count']:,} | {stats['exact_dup_count']:,} |")
    lines.append("")
    lines.append("## 2. Fuzzy listing duplicates")
    lines.append("")
    if fuzzy.empty:
        lines.append("No candidate duplicate listings found under the blocking key.")
    else:
        lines.append(f"- Rows in candidate-dup blocks: **{len(fuzzy):,}**")
        lines.append(f"- Blocking key: `(neighbourhood_cleansed, host_id, round(latitude, 3), round(longitude, 3), normalised(name))`")
        lines.append("- Action: flagged in `duplicate_listings.csv`, **not** deleted (A-030 principle extended to listings).")
    lines.append("")
    lines.append("## 3. Review comment templates")
    lines.append("")
    lines.append(f"- Reviews whose comment text matches at least one other review: **{dup_text_rows:,}**")
    lines.append(f"- Distinct duplicate-text templates: **{template_count:,}**")
    lines.append(f"- Top {len(top)} templates by occurrence written to `duplicate_review_comments.csv`.")
    lines.append("- Action: flagged for NLP deduplication (A-030); raw `fact_reviews` keeps all rows.")
    lines.append("")

    (REPORTS_DIR / "duplicates_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\nwrote reports/duplicates_summary.md")


if __name__ == "__main__":
    main()
