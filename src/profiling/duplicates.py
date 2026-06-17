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


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]
        raw_dir = RAW_BASE / city
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        exact_counts: dict[str, dict[str, int]] = {}
        for key, file_cfg in city_cfg["files"].items():
            name = file_cfg["name"]
            path = raw_dir / name
            if not path.exists() or name.endswith(".geojson"):
                continue
            if name == "reviews.csv.gz":
                df = pd.read_csv(path, compression="gzip",
                                 usecols=["id", "listing_id", "date", "reviewer_id"],
                                 low_memory=False)
            else:
                df = pd.read_csv(path,
                                 compression="gzip" if file_cfg.get("compressed") else None,
                                 low_memory=False)
            exact_counts[name] = {
                "row_count": int(len(df)),
                "exact_dup_count": exact_duplicates(df),
            }

        fuzzy = fuzzy_listing_duplicates(raw_dir / "listings.csv.gz")
        fuzzy_out = REPORTS_DIR / "duplicate_listings.csv"
        if not fuzzy.empty:
            fuzzy.to_csv(fuzzy_out, index=False)

        dup_text_rows, template_count, top = review_comment_templates(raw_dir / "reviews.csv.gz")
        templates_out = REPORTS_DIR / "duplicate_review_comments.csv"
        top.to_csv(templates_out, index=False)

        # markdown
        lines = ["# Duplicate Findings", "",
                 f"City: **{city}** · Snapshot: **{city_cfg['source']['snapshot_date']}**", "",
                 "## 1. Exact row duplicates (per file)", "",
                 "| File | Rows | Exact dup rows |",
                 "|---|---:|---:|"]
        for name, stats in exact_counts.items():
            lines.append(f"| `{name}` | {stats['row_count']:,} | {stats['exact_dup_count']:,} |")
        lines += ["", "## 2. Fuzzy listing duplicates", ""]
        if fuzzy.empty:
            lines.append("No candidate duplicate listings found under the blocking key.")
        else:
            lines += [
                f"- Rows in candidate-dup blocks: **{len(fuzzy):,}**",
                "- Blocking key: `(neighbourhood_cleansed, host_id, round(latitude, 3), round(longitude, 3), normalised(name))`",
                "- Action: flagged in `duplicate_listings.csv`, **not** deleted (A-030 principle extended to listings).",
            ]
        lines += ["", "## 3. Review comment templates", "",
                  f"- Reviews whose comment text matches at least one other review: **{dup_text_rows:,}**",
                  f"- Distinct duplicate-text templates: **{template_count:,}**",
                  f"- Top {len(top)} templates by occurrence written to `duplicate_review_comments.csv`.",
                  "- Action: flagged for NLP deduplication (A-030); raw `fact_reviews` keeps all rows.", ""]
        summary_out = REPORTS_DIR / "duplicates_summary.md"
        summary_out.write_text("\n".join(lines), encoding="utf-8")

    return make_result(
        step="ingestion.duplicates",
        outputs=[summary_out, fuzzy_out, templates_out],
        summary={
            "city": city,
            "exact_per_file": exact_counts,
            "fuzzy_listing_rows": int(len(fuzzy)),
            "review_text_duplicate_rows": int(dup_text_rows),
            "review_distinct_templates": int(template_count),
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
