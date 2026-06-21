"""Single pipeline orchestrator.

Stages, in dependency order:
  ingest     → manifest + raw files present
  profile    → extended profile + duplicates + outliers
  clean      → 4 cleaned parquet files
  transform  → 4 enriched parquet files
  load       → DuckDB warehouse (dims + facts)
  report     → bundled HTML quality report

Idempotency:
  * Each invocation gets a run_id and is recorded in pipeline_run +
    pipeline_stage_run inside warehouse.duckdb.
  * If a snapshot is already registered in dataset_version, the run is
    a no-op unless force=True.

Retries:
  * Network retries live inside src.ingestion.download (exponential
    backoff with abort on 4xx). Schema/validation errors are NOT
    retried — they propagate, fail the stage, halt the pipeline.

Sub-stage selection:
  * `stages` is a list. "all" expands to every stage in order. Pass a
    subset like ["clean", "transform"] to re-run only those.
"""

from __future__ import annotations

import argparse
import logging
import traceback
from collections.abc import Callable
from pathlib import Path

import yaml

from src.cleaning import calendar as clean_calendar
from src.cleaning import listings as clean_listings
from src.cleaning import neighbourhoods as clean_neighbourhoods
from src.cleaning import reviews as clean_reviews
from src.ingestion import download as ingest
from src.loading import warehouse as wh
from src.profiling import duplicates, extended_profile, outliers
from src.transformation import (
    calendar_summary,
    listing_master,
    neighbourhood_summary,
    review_summary,
)
from src.validation import quality_report, quality_tests
from src.orchestration import metadata as meta
from src.orchestration import incremental

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
LOGS_DIR = ROOT / "logs"

log = logging.getLogger("pipeline")


def _setup_logging(run_id: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOGS_DIR / f"pipeline_{run_id.replace(':', '-')}.log",
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    ))
    log.handlers = [handler, logging.StreamHandler()]
    log.setLevel(logging.INFO)


# Each stage is a list of (step_name, callable) pairs.
# Callables take (city, force) and return either one result dict or a list of them.
STAGE_STEPS: dict[str, list[tuple[str, Callable]]] = {
    "ingest":    [("download", lambda city, force: ingest.run(city=city, force=force))],
    "profile":   [
        ("extended_profile", lambda city, force: extended_profile.run(city=city)),
        ("duplicates",       lambda city, force: duplicates.run(city=city)),
        ("outliers",         lambda city, force: outliers.run(city=city)),
    ],
    "clean":     [
        ("neighbourhoods",   lambda city, force: clean_neighbourhoods.run(city=city)),
        ("listings",         lambda city, force: clean_listings.run(city=city)),
        ("calendar",         lambda city, force: clean_calendar.run(city=city)),
        ("reviews",          lambda city, force: clean_reviews.run(city=city)),
    ],
    "transform": [
        ("review_summary",        lambda city, force: review_summary.run(city=city)),
        ("calendar_summary",      lambda city, force: calendar_summary.run(city=city)),
        ("neighbourhood_summary", lambda city, force: neighbourhood_summary.run(city=city)),
        ("listing_master",        lambda city, force: listing_master.run(city=city)),
    ],
    "load":      [
        ("dimensions",       lambda city, force: wh.build_dimensions(city)),
        ("facts",            lambda city, force: wh.build_facts(city)),
    ],
    # Test stage runs the pytest suite against the freshly-loaded warehouse
    # and persists per-test results into data_quality_result.
    "test":      [
        ("quality_tests",    lambda city, force: quality_tests.run(city=city)),
    ],
    "report":    [
        ("quality_report",   lambda city, force: quality_report.run(city=city)),
    ],
}

DEFAULT_STAGES = list(STAGE_STEPS.keys())


def _expand_stages(stages: list[str] | None) -> list[str]:
    if not stages or stages == ["all"]:
        return DEFAULT_STAGES
    unknown = [s for s in stages if s not in STAGE_STEPS]
    if unknown:
        raise ValueError(f"unknown stage(s): {unknown}; valid: {DEFAULT_STAGES}")
    return stages


def run(city: str = "london", stages: list[str] | None = None, force: bool = False) -> dict:
    """Run the orchestrator end-to-end (or just selected stages)."""
    with CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    snapshot = cfg["cities"][city]["source"]["snapshot_date"]

    requested = _expand_stages(stages)
    run_id = meta.new_run_id(city, snapshot)
    _setup_logging(run_id)

    meta.ensure_tables(city)
    incremental.ensure_diff_table(city)

    # Capture the most recently registered snapshot date before this run.
    # Used later to archive the old listing_master and compute the diff.
    prev_versions = meta.list_dataset_versions(city)
    prev_snapshot = str(prev_versions[0]["snapshot_date"]) if prev_versions else None

    # Archive the current listing_master.parquet (old snapshot data) so that
    # detect_changes() can compare it against the newly processed snapshot.
    if prev_snapshot and prev_snapshot != snapshot and "transform" in requested:
        archived = incremental.archive_current(city, prev_snapshot)
        if archived:
            log.info("archived previous listing_master for %s @ %s → %s",
                     city, prev_snapshot, archived)

    # Idempotency gate
    if not force and requested == DEFAULT_STAGES and meta.is_snapshot_registered(city, snapshot):
        log.info("snapshot %s already registered for %s; skipping (use force=true)", snapshot, city)
        return {
            "run_id": run_id, "city": city, "snapshot_date": snapshot,
            "status": "skipped", "reason": "snapshot already registered",
            "stages_requested": ",".join(requested),
        }

    start = meta.now_utc()
    log.info("PIPELINE START run_id=%s city=%s snapshot=%s stages=%s force=%s",
             run_id, city, snapshot, requested, force)

    seq = 0
    ok_count = 0
    err_count = 0
    aborted = False
    last_error = None

    for stage in requested:
        for step_name, fn in STAGE_STEPS[stage]:
            if aborted:
                break
            seq += 1
            step_start = meta.now_utc()
            log.info("STEP %d START %s.%s", seq, stage, step_name)
            try:
                result = fn(city, force)
                step_end = meta.now_utc()
                meta.insert_stage(city, {
                    "run_id": run_id, "seq": seq, "stage": stage, "step": step_name,
                    "status": result.get("status", "ok"),
                    "started_at": step_start, "finished_at": step_end,
                    "elapsed_seconds": result.get("elapsed_seconds"),
                    "outputs": result.get("outputs", []),
                    "summary": result.get("summary", {}),
                    "error": result.get("error"),
                })
                if result.get("status") == "ok":
                    ok_count += 1
                else:
                    err_count += 1
                    aborted = True
                    last_error = result.get("error")
                log.info("STEP %d END   %s.%s status=%s elapsed=%.2fs",
                         seq, stage, step_name, result.get("status"),
                         result.get("elapsed_seconds") or 0)
            except Exception as e:
                step_end = meta.now_utc()
                err_msg = f"{type(e).__name__}: {e}"
                log.exception("STEP %d FAILED %s.%s: %s", seq, stage, step_name, err_msg)
                meta.insert_stage(city, {
                    "run_id": run_id, "seq": seq, "stage": stage, "step": step_name,
                    "status": "error",
                    "started_at": step_start, "finished_at": step_end,
                    "elapsed_seconds": None, "outputs": [], "summary": {},
                    "error": err_msg + "\n" + traceback.format_exc(limit=3),
                })
                err_count += 1
                aborted = True
                last_error = err_msg

    finish = meta.now_utc()
    elapsed = round((finish - start).total_seconds(), 2)
    status = "ok" if err_count == 0 else "error"

    meta.insert_run(city, {
        "run_id": run_id, "city": city, "snapshot_date": snapshot,
        "stages_requested": ",".join(requested), "force_flag": force,
        "started_at": start, "finished_at": finish, "elapsed_seconds": elapsed,
        "status": status, "stage_count": seq,
        "ok_count": ok_count, "error_count": err_count, "error": last_error,
    })

    if status == "ok" and requested == DEFAULT_STAGES:
        # Run incremental diff before registering the new version so that
        # list_dataset_versions() still returns only the previous snapshot.
        if prev_snapshot and prev_snapshot != snapshot:
            diff = incremental.detect_changes(city, prev_snapshot, snapshot)
            log.info(
                "incremental diff %s → %s: %d new, %d removed, %d price, %d status",
                prev_snapshot, snapshot,
                diff.get("new_listings", 0), diff.get("removed_listings", 0),
                diff.get("price_changes", 0), diff.get("status_changes", 0),
            )

        sha = meta.register_dataset_version(city, snapshot, run_id)
        log.info("dataset version registered: %s @ %s (sha256=%s...)",
                 city, snapshot, sha[:10])

    log.info("PIPELINE END   run_id=%s status=%s ok=%d err=%d elapsed=%.2fs",
             run_id, status, ok_count, err_count, elapsed)

    return {
        "run_id": run_id, "city": city, "snapshot_date": snapshot,
        "stages_requested": ",".join(requested), "force_flag": force,
        "status": status, "elapsed_seconds": elapsed,
        "stage_count": seq, "ok_count": ok_count, "error_count": err_count,
        "error": last_error,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    parser.add_argument("--stage", action="append", default=None,
                        help="Repeat to select multiple stages, or omit for all.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(run(city=args.city, stages=args.stage, force=args.force))


if __name__ == "__main__":
    main()
