"""Shared pytest fixtures.

The fixtures point at the warehouse DuckDB file. Tests that need raw
parquet read it directly. All tests are read-only — they never write
to the warehouse.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE_PATH = ROOT / "data" / "processed" / "london" / "warehouse.duckdb"


@pytest.fixture(scope="session")
def warehouse_con():
    # Skip the whole suite cleanly if the warehouse hasn't been built yet.
    if not WAREHOUSE_PATH.exists():
        pytest.skip(f"warehouse not built at {WAREHOUSE_PATH}; run the load stage first")
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    yield con
    con.close()


@pytest.fixture(scope="session")
def city() -> str:
    # Single-city for now; cross-city tests would parametrize this.
    return "london"
