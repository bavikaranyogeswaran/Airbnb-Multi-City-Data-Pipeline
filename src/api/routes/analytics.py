"""Analytics read-only endpoints.

Serves pre-computed EDA and statistical analysis artifacts from
reports/tables/ and supports live parquet queries via DuckDB.

All endpoints are GET-only — no pipeline mutations happen here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import duckdb
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..helpers import csv_to_records, markdown_response, must_exist
from ..paths import ROOT

router = APIRouter(prefix="/analytics", tags=["analytics"])

# ── Artifact paths ─────────────────────────────────────────────────────────────
TABLES  = ROOT / "reports" / "tables"
REPORTS = ROOT / "reports"

# City-aware path helpers — never hardcode a city name at module level
def _parquet(city: str) -> Path:
    return ROOT / "data" / "processed" / city / "listing_master.parquet"

def _warehouse(city: str) -> Path:
    return ROOT / "data" / "processed" / city / "warehouse.duckdb"

# City-aware table path helper.
# London EDA artifacts live directly in reports/tables/ (notebook output location).
# Other cities use a reports/tables/<city>/ subfolder — created when that city's EDA runs.
def _t(name: str, city: str = "london") -> Path:
    if city == "london":
        return TABLES / name
    return TABLES / city / name


# ── Index ──────────────────────────────────────────────────────────────────────

@router.get("", summary="Analytics index — all available endpoints")
def analytics_index() -> dict:
    return {
        "area": "EDA + Statistical Analysis Results",
        "note": "All endpoints are read-only. Run the EDA notebook first to generate artifacts.",
        "listings": {
            "numerical_summary":    "GET /analytics/listings/numerical-summary",
            "price_by_room_type":   "GET /analytics/listings/price-by-room-type",
            "price_by_neighbourhood": "GET /analytics/listings/price-by-neighbourhood?top_n=20",
            "availability_bands":   "GET /analytics/listings/availability-bands",
            "search":               "GET /analytics/listings/search?room_type=entire_home&max_price=200&limit=20",
            "detail":               "GET /analytics/listings/{listing_id}",
        },
        "hosts": {
            "segments":       "GET /analytics/hosts/segments",
            "tenure":         "GET /analytics/hosts/tenure",
            "response_rates": "GET /analytics/hosts/response-rates",
        },
        "market": {
            "concentration": "GET /analytics/market/concentration",
        },
        "geographic": {
            "density":           "GET /analytics/geographic/density",
            "price_by_distance": "GET /analytics/geographic/price-by-distance",
            "room_type_mix":     "GET /analytics/geographic/room-type-mix",
        },
        "temporal": {
            "availability":     "GET /analytics/temporal/availability",
            "reviews":          "GET /analytics/temporal/reviews",
            "minimum_nights":   "GET /analytics/temporal/minimum-nights",
            "weekday_weekend":  "GET /analytics/temporal/weekday-vs-weekend",
            "seasonal":         "GET /analytics/temporal/seasonal",
        },
        "reviews": {
            "summary":       "GET /analytics/reviews/summary",
            "subdimensions": "GET /analytics/reviews/subdimensions",
            "anomalies":     "GET /analytics/reviews/anomalies?limit=50",
        },
        "stats": {
            "hypothesis_tests":        "GET /analytics/stats/hypothesis-tests",
            "regression_coefficients": "GET /analytics/stats/regression/coefficients",
            "regression_summary":      "GET /analytics/stats/regression/summary",
        },
        "comparison": {
            "cities":      "GET /analytics/comparison/cities",
            "room_types":  "GET /analytics/comparison/room-types",
        },
        "reports": {
            "eda_findings": "GET /analytics/reports/eda-findings",
        },
    }


# ── Listing endpoints ──────────────────────────────────────────────────────────

@router.get("/listings/numerical-summary", summary="Descriptive stats for all numeric columns")
def listings_numerical_summary(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("numerical_summary.csv", city))


@router.get("/listings/price-by-room-type", summary="Price metrics per room type")
def price_by_room_type(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("price_by_room_type.csv", city))


@router.get("/listings/price-by-neighbourhood", summary="Price metrics per borough (sorted by median)")
def price_by_neighbourhood(
    city:  Annotated[str, Query()] = "london",
    top_n: Annotated[int, Query(ge=1, le=50)] = 33,
) -> list[dict]:
    rows = csv_to_records(_t("price_by_neighbourhood.csv", city))
    # Sort by median descending so the caller gets the most expensive boroughs first
    rows.sort(key=lambda r: r.get("median_price") or 0, reverse=True)
    return rows[:top_n]


@router.get("/listings/availability-bands", summary="Listings grouped by annual availability band")
def availability_bands(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("availability_band_summary.csv", city))


@router.get("/listings/search", summary="Live parquet search with optional filters")
def search_listings(
    city:           Annotated[str, Query()] = "london",
    room_type:      Annotated[str | None, Query()] = None,
    neighbourhood:  Annotated[str | None, Query()] = None,
    min_price:      Annotated[float | None, Query(ge=0)] = None,
    max_price:      Annotated[float | None, Query(ge=0)] = None,
    min_rating:     Annotated[float | None, Query(ge=0, le=5)] = None,
    superhost:      Annotated[bool | None, Query()] = None,
    limit:          Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[dict]:
    """Filter listing_master.parquet via DuckDB. Returns up to `limit` rows."""
    parquet = _parquet(city)
    must_exist(parquet)

    # Build WHERE clause with positional ? placeholders for safe parameterisation
    clauses: list[str] = []
    params: list = []

    if room_type:
        clauses.append("room_type = ?")
        params.append(room_type)
    if neighbourhood:
        clauses.append("neighbourhood_cleansed ILIKE ?")
        params.append(f"%{neighbourhood}%")
    if min_price is not None:
        clauses.append("price_numeric >= ?")
        params.append(min_price)
    if max_price is not None:
        clauses.append("price_numeric <= ?")
        params.append(max_price)
    if min_rating is not None:
        clauses.append("review_scores_rating >= ?")
        params.append(min_rating)
    if superhost is not None:
        # host_is_superhost stored as object with Python True/False values;
        # DuckDB reads the parquet column as BOOLEAN
        clauses.append("TRY_CAST(host_is_superhost AS BOOLEAN) = ?")
        params.append(superhost)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    cols = (
        "id, host_id, name, room_type, neighbourhood_cleansed, "
        "price_numeric, review_scores_rating, number_of_reviews, "
        "availability_365, host_is_superhost, latitude, longitude"
    )
    parquet_str = str(parquet).replace("\\", "/")
    sql = f"SELECT {cols} FROM read_parquet('{parquet_str}') {where} LIMIT {limit}"

    try:
        conn = duckdb.connect()
        df = conn.execute(sql, params).df()
        conn.close()
        return [
            {k: v if pd.notna(v) else None for k, v in r.items()}
            for r in df.to_dict(orient="records")
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.get("/listings/{listing_id}", summary="Single listing detail from parquet")
def get_listing(
    listing_id: int,
    city: Annotated[str, Query()] = "london",
) -> dict:
    """Fetch one listing by its Inside Airbnb numeric ID."""
    parquet = _parquet(city)
    must_exist(parquet)
    try:
        conn = duckdb.connect()
        parquet_str = str(parquet).replace("\\", "/")
        df = conn.execute(
            f"SELECT * FROM read_parquet('{parquet_str}') WHERE id = ? LIMIT 1",
            [listing_id],
        ).df()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found.")
    return {k: v if pd.notna(v) else None for k, v in df.iloc[0].to_dict().items()}


# ── Host endpoints ─────────────────────────────────────────────────────────────

@router.get("/hosts/segments", summary="Host segment distribution (solo / multi / professional)")
def host_segments(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("host_segment_summary.csv", city))


@router.get("/hosts/tenure", summary="Host tenure distribution by registration year bucket")
def host_tenure(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("host_tenure_summary.csv", city))


@router.get("/hosts/response-rates", summary="Host response rate distribution by segment")
def host_response_rates(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("response_rate_summary.csv", city))


# ── Market endpoints ───────────────────────────────────────────────────────────

@router.get("/market/concentration", summary="Market concentration — Gini and top-N host share")
def market_concentration(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("market_concentration.csv", city))


# ── Geographic endpoints ───────────────────────────────────────────────────────

@router.get("/geographic/density", summary="Listing density and price per borough")
def geographic_density(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("neighbourhood_density.csv", city))


@router.get("/geographic/price-by-distance", summary="Median price by distance band from city centre")
def price_by_distance(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("price_by_distance_band.csv", city))


@router.get("/geographic/room-type-mix", summary="Room-type share per borough")
def room_type_mix(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("room_type_by_neighbourhood.csv", city))


# ── Temporal endpoints ─────────────────────────────────────────────────────────

@router.get("/temporal/availability", summary="Monthly availability rate across the year")
def temporal_availability(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("monthly_availability.csv", city))


@router.get("/temporal/reviews", summary="Monthly review volume (proxy for bookings)")
def temporal_reviews(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("monthly_review_volume.csv", city))


@router.get("/temporal/minimum-nights", summary="Monthly minimum-nights requirement trends")
def temporal_minimum_nights(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("minimum_nights_monthly.csv", city))


@router.get("/temporal/weekday-vs-weekend", summary="Weekday vs weekend availability rates")
def temporal_weekday_weekend(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("weekday_weekend_availability.csv", city))


@router.get("/temporal/seasonal", summary="Seasonal availability and review summary per listing")
def temporal_seasonal(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("temporal_summary.csv", city))


# ── Review endpoints ───────────────────────────────────────────────────────────

@router.get("/reviews/summary", summary="Review score summary statistics")
def reviews_summary(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("review_summary.csv", city))


@router.get("/reviews/subdimensions", summary="Subdimension review score medians by room type")
def reviews_subdimensions(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("review_subdimension_summary.csv", city))


@router.get("/reviews/anomalies", summary="High-review / low-score anomaly listings")
def reviews_anomalies(
    city:  Annotated[str, Query()] = "london",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[dict]:
    rows = csv_to_records(_t("high_review_low_score_listings.csv", city))
    return rows[:limit]


# ── Statistical analysis endpoints ────────────────────────────────────────────

@router.get("/stats/hypothesis-tests", summary="All five hypothesis test results")
def hypothesis_tests(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("hypothesis_test_results.csv", city))


@router.get("/stats/regression/coefficients", summary="OLS regression coefficients with CI")
def regression_coefficients(
    city:                  Annotated[str, Query()] = "london",
    exclude_neighbourhood: Annotated[bool, Query()] = False,
) -> list[dict]:
    rows = csv_to_records(_t("regression_coefficients.csv", city))
    if exclude_neighbourhood:
        rows = [r for r in rows if not str(r.get("Unnamed: 0", "")).startswith("C(neighbourhood")]
    return rows


@router.get("/stats/regression/summary", summary="OLS model-level fit metrics (R², F-stat, n)")
def regression_summary(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_t("regression_summary.csv", city))


# ── City comparison endpoints ──────────────────────────────────────────────────

@router.get("/comparison/cities", summary="London vs Amsterdam key metric comparison")
def comparison_cities() -> list[dict]:
    return csv_to_records(_t("city_comparison_summary.csv"))


@router.get("/comparison/room-types", summary="Room-type share comparison across both cities")
def comparison_room_types() -> list[dict]:
    return csv_to_records(_t("room_type_city_comparison.csv"))


# ── Report endpoints ───────────────────────────────────────────────────────────

@router.get(
    "/reports/eda-findings",
    summary="EDA findings report (Markdown)",
    response_class=PlainTextResponse,
)
def eda_findings_report() -> PlainTextResponse:
    return markdown_response(REPORTS / "eda_findings.md")
