"""Snapshot-to-snapshot incremental change detection.

Inside Airbnb publishes monthly snapshots. Each time a new snapshot is
processed, this module compares it against the previous one to surface:

  new_listings       listing_ids present in new snapshot but not old
  removed_listings   listing_ids present in old snapshot but not new
  price_changes      listings where price_numeric changed by > 5%
  status_changes     listings where room_type or is_de_facto_inactive changed

How archiving works
-------------------
pipeline.py calls archive_current() BEFORE the transform stage overwrites
listing_master.parquet. The archive is stored under:
  data/processed/{city}/snapshots/listing_master_{snapshot_date}.parquet

After a successful full run, pipeline.py calls detect_changes() to produce
the diff report. If no archive exists (first run for a city), an empty
baseline result is returned.

Outputs
-------
  reports/incremental/{city}_diff_{old}_to_{new}.csv   — per-row change log
  warehouse.snapshot_diff table                        — queryable via SQL
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_BASE = ROOT / "data" / "processed"
INCREMENTAL_DIR = ROOT / "reports" / "incremental"

PRICE_THRESHOLD = 0.05      # flag price changes > 5%
DIFF_COLS = ["listing_id", "price_numeric", "room_type", "is_de_facto_inactive"]


# ── Archive helpers ────────────────────────────────────────────────────────────

def _snapshot_dir(city: str) -> Path:
    d = PROCESSED_BASE / city / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def archive_current(city: str, snapshot_date: str) -> Path | None:
    """Copy current listing_master.parquet into the snapshot archive.

    Called by pipeline.py before the transform stage overwrites the file.
    Returns the archive path, or None if listing_master.parquet does not
    yet exist (i.e. this is the very first ingest for this city).
    """
    src = PROCESSED_BASE / city / "listing_master.parquet"
    if not src.exists():
        return None
    dest = _snapshot_dir(city) / f"listing_master_{snapshot_date}.parquet"
    shutil.copy2(src, dest)
    return dest


def list_archives(city: str) -> list[str]:
    """Return snapshot dates for which an archive exists, newest first."""
    archives = sorted(
        _snapshot_dir(city).glob("listing_master_*.parquet"), reverse=True
    )
    return [p.stem.replace("listing_master_", "") for p in archives]


# ── Change detection ───────────────────────────────────────────────────────────

def detect_changes(city: str, old_snapshot: str, new_snapshot: str) -> dict:
    """Compare an archived snapshot against the current listing_master.parquet.

    Args:
        city:          city code (london | amsterdam | madrid | berlin)
        old_snapshot:  snapshot date of the archived baseline (YYYY-MM-DD)
        new_snapshot:  snapshot date of the newly processed snapshot

    Returns a summary dict; also writes the full diff to CSV and DuckDB.
    """
    old_path = _snapshot_dir(city) / f"listing_master_{old_snapshot}.parquet"
    new_path = PROCESSED_BASE / city / "listing_master.parquet"

    if not old_path.exists():
        return {
            "status": "no_baseline",
            "city": city,
            "old_snapshot": old_snapshot,
            "new_snapshot": new_snapshot,
            "message": (
                f"No archived snapshot found for {city} @ {old_snapshot}. "
                "This is treated as the first registered snapshot — no diff available."
            ),
            "new_listings": 0,
            "removed_listings": 0,
            "price_changes": 0,
            "status_changes": 0,
            "total_changes": 0,
        }

    # Read only the columns needed for diffing
    old_cols = pd.read_parquet(old_path, columns=[]).columns.tolist()
    new_cols = pd.read_parquet(new_path, columns=[]).columns.tolist()
    cols = [c for c in DIFF_COLS if c in old_cols and c in new_cols]

    old_df = pd.read_parquet(old_path, columns=cols)
    new_df = pd.read_parquet(new_path, columns=cols)

    old_ids = set(old_df["listing_id"])
    new_ids = set(new_df["listing_id"])

    new_listings = sorted(new_ids - old_ids)
    removed_listings = sorted(old_ids - new_ids)

    # Compare common listings only
    common_ids = old_ids & new_ids
    old_c = old_df[old_df["listing_id"].isin(common_ids)].set_index("listing_id")
    new_c = new_df[new_df["listing_id"].isin(common_ids)].set_index("listing_id")

    # Price changes
    price_rows: list[dict] = []
    if "price_numeric" in old_c.columns:
        m = old_c[["price_numeric"]].join(
            new_c[["price_numeric"]], lsuffix="_old", rsuffix="_new"
        ).dropna()
        mask = (m["price_numeric_old"] > 0) & (
            (m["price_numeric_new"] - m["price_numeric_old"]).abs()
            / m["price_numeric_old"]
            > PRICE_THRESHOLD
        )
        changed = m[mask].copy()
        changed["pct_change"] = (
            (changed["price_numeric_new"] - changed["price_numeric_old"])
            / changed["price_numeric_old"]
            * 100
        ).round(1)
        for lid, row in changed.iterrows():
            price_rows.append({
                "change_type": "price_change",
                "listing_id": lid,
                "old_value": row["price_numeric_old"],
                "new_value": row["price_numeric_new"],
                "pct_change": row["pct_change"],
                "field": "price_numeric",
            })

    # Status changes (room_type, is_de_facto_inactive)
    status_rows: list[dict] = []
    status_cols = [c for c in ["room_type", "is_de_facto_inactive"] if c in old_c.columns]
    if status_cols:
        changed_mask = (old_c[status_cols] != new_c[status_cols]).any(axis=1)
        for lid in changed_mask[changed_mask].index:
            for col in status_cols:
                old_val = old_c.at[lid, col]
                new_val = new_c.at[lid, col]
                if old_val != new_val:
                    status_rows.append({
                        "change_type": "status_change",
                        "listing_id": lid,
                        "field": col,
                        "old_value": str(old_val),
                        "new_value": str(new_val),
                        "pct_change": None,
                    })

    # Additions / removals as rows
    addition_rows = [
        {"change_type": "new_listing", "listing_id": lid,
         "field": None, "old_value": None, "new_value": None, "pct_change": None}
        for lid in new_listings
    ]
    removal_rows = [
        {"change_type": "removed_listing", "listing_id": lid,
         "field": None, "old_value": None, "new_value": None, "pct_change": None}
        for lid in removed_listings
    ]

    all_rows = addition_rows + removal_rows + price_rows + status_rows
    diff_df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame(
        columns=["change_type", "listing_id", "field", "old_value", "new_value", "pct_change"]
    )

    # Write CSV
    INCREMENTAL_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = INCREMENTAL_DIR / f"{city}_diff_{old_snapshot}_to_{new_snapshot}.csv"
    diff_df.to_csv(csv_path, index=False)

    # Write to DuckDB
    _persist_diff(city, old_snapshot, new_snapshot, diff_df)

    summary = {
        "status": "ok",
        "city": city,
        "old_snapshot": old_snapshot,
        "new_snapshot": new_snapshot,
        "new_listings": len(new_listings),
        "removed_listings": len(removed_listings),
        "price_changes": len(price_rows),
        "status_changes": len(status_rows),
        "total_changes": len(all_rows),
        "diff_csv": str(csv_path.relative_to(ROOT)),
    }
    return summary


# ── Persistence ────────────────────────────────────────────────────────────────

def _con(city: str):
    db_path = PROCESSED_BASE / city / "warehouse.duckdb"
    return duckdb.connect(str(db_path))


def ensure_diff_table(city: str) -> None:
    con = _con(city)
    con.execute("""
        CREATE TABLE IF NOT EXISTS snapshot_diff (
            city           VARCHAR,
            old_snapshot   DATE,
            new_snapshot   DATE,
            change_type    VARCHAR,
            listing_id     BIGINT,
            field          VARCHAR,
            old_value      VARCHAR,
            new_value      VARCHAR,
            pct_change     DOUBLE
        );
    """)
    con.close()


def _persist_diff(
    city: str,
    old_snapshot: str,
    new_snapshot: str,
    diff_df: pd.DataFrame,
) -> None:
    ensure_diff_table(city)
    if diff_df.empty:
        return
    con = _con(city)
    # Remove any previous diff for this snapshot pair
    con.execute(
        "DELETE FROM snapshot_diff WHERE city=? AND old_snapshot=? AND new_snapshot=?",
        [city, old_snapshot, new_snapshot],
    )
    df = diff_df.copy()
    df.insert(0, "new_snapshot", new_snapshot)
    df.insert(0, "old_snapshot", old_snapshot)
    df.insert(0, "city", city)
    con.execute("INSERT INTO snapshot_diff SELECT * FROM df")
    con.close()


def latest_diff_summary(city: str) -> dict:
    """Return summary counts for the most recent diff stored in the warehouse."""
    ensure_diff_table(city)
    con = _con(city)
    row = con.execute("""
        SELECT old_snapshot, new_snapshot,
               COUNT(*) AS total_changes,
               COUNT(*) FILTER (WHERE change_type = 'new_listing')      AS new_listings,
               COUNT(*) FILTER (WHERE change_type = 'removed_listing')  AS removed_listings,
               COUNT(*) FILTER (WHERE change_type = 'price_change')     AS price_changes,
               COUNT(*) FILTER (WHERE change_type = 'status_change')    AS status_changes
        FROM snapshot_diff
        WHERE city = ?
        ORDER BY new_snapshot DESC
        LIMIT 1
    """, [city]).fetchone()
    con.close()
    if row is None:
        return {"status": "no_diff", "city": city,
                "message": "No incremental diff has been run yet for this city."}
    return {
        "status": "ok",
        "city": city,
        "old_snapshot": str(row[0]),
        "new_snapshot": str(row[1]),
        "total_changes": row[2],
        "new_listings": row[3],
        "removed_listings": row[4],
        "price_changes": row[5],
        "status_changes": row[6],
    }
