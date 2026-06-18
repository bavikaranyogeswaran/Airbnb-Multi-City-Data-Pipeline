"""Pytest-driven data-quality runner.

Wraps `pytest.main` so a single `run(city)` call:
  1. Executes every test under `tests/`
  2. Captures per-test outcomes via a pytest plugin
  3. Persists the results into `data_quality_result` inside warehouse.duckdb
  4. Returns the standard make_result() shape

The same `run()` is called by the orchestrator's `test` stage and by
the FastAPI endpoint.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import uuid
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "tests"
PROCESSED_BASE = ROOT / "data" / "processed"

# rule_category heuristics — map test name fragments to a category for reporting.
_RULE_CATEGORIES = [
    (re.compile(r"unique"),           "uniqueness"),
    (re.compile(r"_not_null"),        "non_null"),
    (re.compile(r"referential"),      "referential"),
    (re.compile(r"_in_range|bounds"), "range"),
    (re.compile(r"valid"),            "domain"),
    (re.compile(r"matches"),          "shape"),
    (re.compile(r"present"),          "shape"),
    (re.compile(r"positive"),         "range"),
    (re.compile(r"non_negative"),     "range"),
    (re.compile(r"monotonic"),        "structural"),
    (re.compile(r"zero_or_one"),      "domain"),
]

# target_table heuristics — derive from test module filename.
_TABLE_FROM_MODULE = {
    "test_listings_quality":  "dim_listing + fact_listing_snapshot",
    "test_calendar_quality":  "fact_calendar",
    "test_reviews_quality":   "fact_reviews",
    "test_warehouse_quality": "dim_neighbourhood + dim_host + dim_date",
}

# DDL for the results table; idempotent.
_DDL = """
CREATE TABLE IF NOT EXISTS data_quality_result (
    run_id            VARCHAR,
    test_id           VARCHAR,
    test_module       VARCHAR,
    test_name         VARCHAR,
    target_table      VARCHAR,
    rule_category     VARCHAR,
    status            VARCHAR,
    duration_seconds  DOUBLE,
    failure_message   VARCHAR,
    recorded_at       TIMESTAMP
);
"""


def _categorize(test_name: str) -> str:
    # Match the first heuristic that fits the test name.
    for pat, label in _RULE_CATEGORIES:
        if pat.search(test_name):
            return label
    return "other"


class _ResultCollector:
    """Pytest plugin that records one entry per executed test."""

    def __init__(self):
        self.records: list[dict] = []

    # Pytest invokes this for setup, call, and teardown phases.
    # We only keep the "call" phase, which is the test body itself.
    def pytest_runtest_logreport(self, report):
        if report.when != "call" and report.outcome != "skipped":
            return
        # nodeid looks like "tests/test_x_quality.py::test_foo"
        node = report.nodeid
        module_part = node.split("::", 1)[0]
        module_stem = Path(module_part).stem
        test_name = node.split("::", 1)[1] if "::" in node else node

        failure_msg = None
        if report.failed:
            failure_msg = str(report.longreprtext)[:4000]

        self.records.append({
            "test_id":           node,
            "test_module":       module_stem,
            "test_name":         test_name,
            "target_table":      _TABLE_FROM_MODULE.get(module_stem, "unknown"),
            "rule_category":     _categorize(test_name),
            "status":            report.outcome,            # "passed" | "failed" | "skipped"
            "duration_seconds":  round(getattr(report, "duration", 0.0), 3),
            "failure_message":   failure_msg,
        })


def _con(city: str):
    db_path = PROCESSED_BASE / city / "warehouse.duckdb"
    return duckdb.connect(str(db_path))


def _persist(city: str, run_id: str, records: list[dict]) -> None:
    """Insert collected results into data_quality_result."""
    con = _con(city)
    con.execute(_DDL)
    now = dt.datetime.now(dt.UTC).replace(microsecond=0, tzinfo=None)
    for r in records:
        con.execute("""
            INSERT INTO data_quality_result
                (run_id, test_id, test_module, test_name, target_table,
                 rule_category, status, duration_seconds, failure_message, recorded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?);
        """, [run_id, r["test_id"], r["test_module"], r["test_name"],
              r["target_table"], r["rule_category"], r["status"],
              r["duration_seconds"], r["failure_message"], now])
    con.close()


def run(city: str = "london", run_id: str | None = None) -> dict:
    """Execute the test suite and persist results."""
    from src.api.result import make_result, timed

    # Caller (the orchestrator) may pass its own run_id so test results
    # link back to the pipeline run that triggered them.
    rid = run_id or f"qa-{uuid.uuid4().hex[:10]}"
    collector = _ResultCollector()

    with timed() as elapsed:
        # Capture pytest's exit code so we can report status.
        exit_code = pytest.main(
            [str(TESTS_DIR), "-q", "--no-header", "--tb=short"],
            plugins=[collector],
        )
        _persist(city, rid, collector.records)

    by_status: dict[str, int] = {}
    for r in collector.records:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    failed = by_status.get("failed", 0)
    return make_result(
        step="quality.tests",
        outputs=[PROCESSED_BASE / city / "warehouse.duckdb"],
        summary={
            "city": city,
            "run_id": rid,
            "pytest_exit_code": int(exit_code),
            "total_tests": len(collector.records),
            "by_status": by_status,
            "failed_test_ids": [r["test_id"] for r in collector.records if r["status"] == "failed"],
        },
        elapsed_seconds=elapsed(),
        status="ok" if failed == 0 else "error",
        error=f"{failed} tests failed" if failed else None,
    )


def _records(df: pd.DataFrame) -> list[dict]:
    return [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in df.astype("object").to_dict(orient="records")
    ]


def list_runs(city: str, limit: int = 20) -> list[dict]:
    """Distinct run_ids with pass/fail counts, latest first."""
    con = _con(city)
    con.execute(_DDL)
    df = con.execute("""
        SELECT
            run_id,
            MAX(recorded_at)                                   AS recorded_at,
            COUNT(*)                                           AS total,
            SUM(CASE WHEN status='passed'  THEN 1 ELSE 0 END)  AS passed,
            SUM(CASE WHEN status='failed'  THEN 1 ELSE 0 END)  AS failed,
            SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END)  AS skipped
        FROM data_quality_result
        GROUP BY run_id
        ORDER BY recorded_at DESC
        LIMIT ?;
    """, [limit]).fetchdf()
    con.close()
    return _records(df)


def get_results(city: str, run_id: str) -> list[dict]:
    """All test records for a single run."""
    con = _con(city)
    con.execute(_DDL)
    df = con.execute("""
        SELECT * FROM data_quality_result
        WHERE run_id = ?
        ORDER BY test_module, test_name
    """, [run_id]).fetchdf()
    con.close()
    return _records(df)


def latest(city: str) -> list[dict]:
    """Convenience: results from the most recent run."""
    runs = list_runs(city, limit=1)
    if not runs:
        return []
    return get_results(city, runs[0]["run_id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()
    print(run(city=args.city))


if __name__ == "__main__":
    main()
