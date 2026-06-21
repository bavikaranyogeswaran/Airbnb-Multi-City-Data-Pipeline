"""FastAPI endpoint tests using TestClient (no running server needed).

Covers: health check, 404 on unknown routes, analytics index, and
spot-checks on several analytics endpoints that read pre-built artifacts.

The analytics endpoints read from reports/tables/ — tests skip cleanly
if those artifacts have not been generated yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app, raise_server_exceptions=True)

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "reports" / "tables"


# ── Meta / health ──────────────────────────────────────────────────────────────

def test_health_returns_200():
    r = client.get("/health")
    assert r.status_code == 200


def test_health_body_contains_ok():
    r = client.get("/health")
    assert r.json() == {"status": "ok"}


def test_root_redirects_to_docs():
    # Root redirects to /docs (302 by default from RedirectResponse).
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert "/docs" in r.headers.get("location", "")


def test_index_lists_all_routers():
    r = client.get("/index")
    assert r.status_code == 200
    body = r.json()
    assert "analytics" in body["routers"]
    assert "orchestration" in body["routers"]


# ── 404 behaviour ──────────────────────────────────────────────────────────────

def test_unknown_route_returns_404():
    r = client.get("/this/route/does/not/exist")
    assert r.status_code == 404


def test_unknown_listing_id_returns_404():
    # listing_id 0 cannot exist in the dataset.
    r = client.get("/analytics/listings/0")
    assert r.status_code == 404


# ── Analytics index ────────────────────────────────────────────────────────────

def test_analytics_index_returns_200():
    r = client.get("/analytics")
    assert r.status_code == 200


def test_analytics_index_has_expected_sections():
    r = client.get("/analytics")
    body = r.json()
    for section in ("listings", "hosts", "market", "geographic", "temporal",
                    "reviews", "stats", "comparison", "reports"):
        assert section in body, f"missing section: {section}"


# ── Listing analytics (requires pre-built artifacts) ──────────────────────────

@pytest.mark.skipif(
    not (_p := TABLES / "price_by_room_type.csv").exists(),
    reason=f"artifact not built: {TABLES / 'price_by_room_type.csv'}",
)
def test_price_by_room_type_has_4_rows():
    r = client.get("/analytics/listings/price-by-room-type")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 4


@pytest.mark.skipif(
    not (TABLES / "price_by_neighbourhood.csv").exists(),
    reason="artifact not built",
)
def test_price_by_neighbourhood_respects_top_n():
    r = client.get("/analytics/listings/price-by-neighbourhood?top_n=5")
    assert r.status_code == 200
    assert len(r.json()) == 5


@pytest.mark.skipif(
    not (TABLES / "availability_band_summary.csv").exists(),
    reason="artifact not built",
)
def test_availability_bands_returns_list():
    r = client.get("/analytics/listings/availability-bands")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Host analytics ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not (TABLES / "host_segment_summary.csv").exists(),
    reason="artifact not built",
)
def test_host_segments_returns_list():
    r = client.get("/analytics/hosts/segments")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0


# ── Statistical analysis ───────────────────────────────────────────────────────

@pytest.mark.skipif(
    not (TABLES / "hypothesis_test_results.csv").exists(),
    reason="artifact not built: run 04_statistical_analysis.ipynb first",
)
def test_hypothesis_tests_has_5_rows():
    r = client.get("/analytics/stats/hypothesis-tests")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5


@pytest.mark.skipif(
    not (TABLES / "regression_summary.csv").exists(),
    reason="artifact not built",
)
def test_regression_summary_contains_r_squared():
    r = client.get("/analytics/stats/regression/summary")
    assert r.status_code == 200
    metrics = {row["metric"] for row in r.json()}
    assert "R²" in metrics


@pytest.mark.skipif(
    not (TABLES / "regression_coefficients.csv").exists(),
    reason="artifact not built",
)
def test_regression_coefficients_exclude_neighbourhood_flag():
    r = client.get("/analytics/stats/regression/coefficients?exclude_neighbourhood=true")
    assert r.status_code == 200
    data = r.json()
    # When neighbourhood is excluded, no row should have neighbourhood in its index key
    for row in data:
        key = row.get("Unnamed: 0", "")
        assert "neighbourhood_cleansed" not in key


# ── City comparison ────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not (TABLES / "city_comparison_summary.csv").exists(),
    reason="artifact not built",
)
def test_city_comparison_returns_four_cities():
    r = client.get("/analytics/comparison/cities")
    assert r.status_code == 200
    assert len(r.json()) == 4


# ── Reports ────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not (ROOT / "reports" / "eda_findings.md").exists(),
    reason="artifact not built",
)
def test_eda_findings_returns_markdown():
    r = client.get("/analytics/reports/eda-findings")
    assert r.status_code == 200
    # Content-type should be text/markdown or text/plain
    assert "text/" in r.headers.get("content-type", "")
    assert len(r.text) > 1000   # sanity: not empty

# ── Live search (requires parquet) ────────────────────────────────────────────

@pytest.mark.skipif(
    not (ROOT / "data" / "processed" / "london" / "listing_master.parquet").exists(),
    reason="listing_master.parquet not built",
)
def test_listing_search_returns_list():
    r = client.get("/analytics/listings/search?room_type=entire_home&limit=5")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5


@pytest.mark.skipif(
    not (ROOT / "data" / "processed" / "london" / "listing_master.parquet").exists(),
    reason="listing_master.parquet not built",
)
def test_listing_search_filters_room_type():
    r = client.get("/analytics/listings/search?room_type=shared_room&limit=10")
    assert r.status_code == 200
    for row in r.json():
        assert row["room_type"] == "shared_room"
