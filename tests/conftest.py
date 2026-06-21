"""Shared pytest fixtures.

warehouse_con is parametrized over all known cities so every warehouse
test runs against London, Amsterdam, Madrid, and Berlin automatically. Tests that
need raw parquet read it directly. All tests are read-only.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]

# Minimum rows expected in fact_listing_snapshot per city.
# Lets warehouse row-count tests use a city-appropriate threshold.
MIN_LISTING_ROWS = {
    "london":    50_000,
    "amsterdam":  5_000,
    "madrid":    15_000,
    "berlin":     8_000,
}


def _warehouse_path(city: str) -> Path:
    return ROOT / "data" / "processed" / city / "warehouse.duckdb"


@pytest.fixture(scope="session", params=["london", "amsterdam", "madrid", "berlin"])
def city(request) -> str:
    return request.param


@pytest.fixture(scope="session")
def warehouse_con(city):
    """Open a read-only DuckDB connection for the given city's warehouse."""
    path = _warehouse_path(city)
    if not path.exists():
        pytest.skip(f"warehouse not built for {city}; run the load stage first")
    con = duckdb.connect(str(path), read_only=True)
    yield con
    con.close()
