"""Pipeline metadata tables, written into the same DuckDB file as the warehouse.

Tables:
  pipeline_run        one row per orchestration invocation
  pipeline_stage_run  one row per (run, stage, step) execution
  dataset_version     one row per (city, snapshot_date) successfully completed
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_BASE = ROOT / "data" / "processed"
MANIFEST_PATH = ROOT / "data" / "raw" / "_manifest.csv"


def _con(city: str):
    db_path = PROCESSED_BASE / city / "warehouse.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).replace(tzinfo=None)


def new_run_id(city: str, snapshot: str) -> str:
    return f"{now_utc().isoformat()}Z-{city}-{snapshot}-{uuid.uuid4().hex[:6]}"


def ensure_tables(city: str) -> None:
    con = _con(city)
    con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_run (
            run_id            VARCHAR PRIMARY KEY,
            city              VARCHAR,
            snapshot_date     DATE,
            stages_requested  VARCHAR,
            force_flag        BOOLEAN,
            started_at        TIMESTAMP,
            finished_at       TIMESTAMP,
            elapsed_seconds   DOUBLE,
            status            VARCHAR,
            stage_count       INTEGER,
            ok_count          INTEGER,
            error_count       INTEGER,
            error             VARCHAR
        );
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_stage_run (
            run_id            VARCHAR,
            seq               INTEGER,
            stage             VARCHAR,
            step              VARCHAR,
            status            VARCHAR,
            started_at        TIMESTAMP,
            finished_at       TIMESTAMP,
            elapsed_seconds   DOUBLE,
            outputs           VARCHAR,
            summary_json      VARCHAR,
            error             VARCHAR
        );
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS dataset_version (
            city              VARCHAR,
            snapshot_date     DATE,
            sha256_manifest   VARCHAR,
            registered_at     TIMESTAMP,
            run_id            VARCHAR,
            PRIMARY KEY (city, snapshot_date)
        );
    """)
    con.close()


def insert_run(city: str, row: dict) -> None:
    con = _con(city)
    con.execute("""
        INSERT INTO pipeline_run
            (run_id, city, snapshot_date, stages_requested, force_flag,
             started_at, finished_at, elapsed_seconds, status,
             stage_count, ok_count, error_count, error)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);
    """, [row["run_id"], row["city"], row["snapshot_date"],
          row["stages_requested"], row["force_flag"],
          row["started_at"], row["finished_at"], row["elapsed_seconds"],
          row["status"], row["stage_count"], row["ok_count"],
          row["error_count"], row["error"]])
    con.close()


def insert_stage(city: str, row: dict) -> None:
    con = _con(city)
    con.execute("""
        INSERT INTO pipeline_stage_run
            (run_id, seq, stage, step, status, started_at, finished_at,
             elapsed_seconds, outputs, summary_json, error)
        VALUES (?,?,?,?,?,?,?,?,?,?,?);
    """, [row["run_id"], row["seq"], row["stage"], row["step"], row["status"],
          row["started_at"], row["finished_at"], row["elapsed_seconds"],
          json.dumps(row["outputs"]), json.dumps(row["summary"], default=str),
          row["error"]])
    con.close()


def register_dataset_version(city: str, snapshot: str, run_id: str) -> str:
    """Compute manifest hash and upsert into dataset_version."""
    sha = ""
    if MANIFEST_PATH.exists():
        sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    con = _con(city)
    con.execute("""
        INSERT INTO dataset_version (city, snapshot_date, sha256_manifest, registered_at, run_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (city, snapshot_date) DO UPDATE SET
            sha256_manifest = excluded.sha256_manifest,
            registered_at   = excluded.registered_at,
            run_id          = excluded.run_id;
    """, [city, snapshot, sha, now_utc(), run_id])
    con.close()
    return sha


def is_snapshot_registered(city: str, snapshot: str) -> bool:
    ensure_tables(city)
    con = _con(city)
    row = con.execute(
        "SELECT COUNT(*) FROM dataset_version WHERE city=? AND snapshot_date=?",
        [city, snapshot],
    ).fetchone()
    con.close()
    return row is not None and row[0] > 0


def list_runs(city: str, limit: int = 20) -> list[dict]:
    ensure_tables(city)
    con = _con(city)
    df = con.execute(
        "SELECT * FROM pipeline_run ORDER BY started_at DESC LIMIT ?", [limit]
    ).fetchdf()
    con.close()
    df = df.where(df.notna(), None)  # type: ignore[arg-type]
    return df.astype("object").to_dict(orient="records")


def get_run(city: str, run_id: str) -> dict | None:
    ensure_tables(city)
    con = _con(city)
    run_df = con.execute("SELECT * FROM pipeline_run WHERE run_id=?", [run_id]).fetchdf()
    stages_df = con.execute(
        "SELECT * FROM pipeline_stage_run WHERE run_id=? ORDER BY seq", [run_id]
    ).fetchdf()
    con.close()
    if len(run_df) == 0:
        return None
    run = run_df.where(run_df.notna(), None).astype("object").to_dict(orient="records")[0]  # type: ignore[arg-type]
    run["stages"] = stages_df.where(stages_df.notna(), None).astype("object").to_dict(orient="records")  # type: ignore[arg-type]
    return run


def list_dataset_versions(city: str) -> list[dict]:
    ensure_tables(city)
    con = _con(city)
    df = con.execute("SELECT * FROM dataset_version ORDER BY snapshot_date DESC").fetchdf()
    con.close()
    df = df.where(df.notna(), None)  # type: ignore[arg-type]
    return df.astype("object").to_dict(orient="records")
