"""Analytics read-only endpoints.

Serves pre-computed EDA and statistical analysis artifacts from
reports/tables/ and supports live parquet queries via DuckDB.

GET endpoints are read-only. POST /analytics/ml/predict is the one
write-path endpoint — it loads the trained LightGBM pipeline and runs
live inference. All other ML endpoints serve pre-computed CSVs/JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import duckdb
import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..helpers import csv_to_records, markdown_response, must_exist, read_json
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
        "ml": {
            "model_card":        "GET /analytics/ml/model-card?city=london",
            "model_comparison":  "GET /analytics/ml/model-comparison?city=london",
            "cv_results":        "GET /analytics/ml/cv-results?city=london",
            "feature_importance":"GET /analytics/ml/feature-importance?city=london&method=permutation",
            "residuals":         "GET /analytics/ml/residuals?city=london&limit=100",
            "residuals_segment": "GET /analytics/ml/residuals/by-segment?city=london&segment=neighbourhood",
            "predict":           "POST /analytics/ml/predict",
        },
        "clustering": {
            "profile":  "GET /analytics/clustering/profile?city=london",
            "elbow":    "GET /analytics/clustering/elbow?city=london",
            "labels":   "GET /analytics/clustering/labels?city=london&cluster=0&limit=100",
            "assign":   "POST /analytics/clustering/assign",
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


# ── ML model endpoints ─────────────────────────────────────────────────────────
#
# All ML results come from the LightGBM price prediction pipeline trained in
# src/models/train_price_model.py (Steps 7–11).  The POST /predict endpoint is
# the only one that loads the model at runtime; everything else reads CSVs/JSON
# written to reports/model_results/.

MODEL_RESULTS = ROOT / "reports" / "model_results"
MODELS_DIR    = ROOT / "models"

# Module-level cache so the model is loaded only once per process lifetime.
_model_cache: dict = {}

_VALID_SEGMENT_COLS = {
    "neighbourhood": "neighbourhood_error_analysis",
    "room_type":     "room_type_error_analysis",
    "price_band":    "price_band_error_analysis",
    "property_type": "property_type_error_analysis",
    "host_segment":  "host_segment_error_analysis",
}


def _model_results_path(name: str, city: str) -> Path:
    return MODEL_RESULTS / f"{name}_{city}.csv"


def _get_model(city: str):
    """Load and cache the trained pipeline for a city."""
    if city not in _model_cache:
        path = MODELS_DIR / f"{city}_price_model.joblib"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No trained model found for '{city}'. Run train_price_model.py first.",
            )
        _model_cache[city] = joblib.load(path)
    return _model_cache[city]


# ── 1. Model card ──────────────────────────────────────────────────────────────

@router.get("/ml/model-card", summary="Full model card: metrics, hyperparameters, bias findings")
def ml_model_card(
    city: Annotated[str, Query()] = "london",
) -> dict:
    """Returns the comprehensive model metadata JSON written during Step 11."""
    return read_json(MODELS_DIR / f"{city}_model_metadata.json")


# ── 2. Model comparison ────────────────────────────────────────────────────────

@router.get("/ml/model-comparison", summary="All models vs baselines — MAE, MAPE, R², within-20%")
def ml_model_comparison(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    """
    Returns the full model comparison table (baselines + Ridge + Random Forest
    + Gradient Boosting) with log-scale R² alongside currency metrics.
    """
    return csv_to_records(_model_results_path("full_model_comparison", city))


# ── 3. Cross-validation results ────────────────────────────────────────────────

@router.get("/ml/cv-results", summary="5-fold grouped CV results — MAE, R², overfit gap")
def ml_cv_results(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    return csv_to_records(_model_results_path("cross_validation_results", city))


# ── 4. Feature importance ──────────────────────────────────────────────────────

@router.get("/ml/feature-importance", summary="Feature importance via permutation or SHAP")
def ml_feature_importance(
    city:   Annotated[str, Query()] = "london",
    method: Annotated[str, Query(description="permutation or shap")] = "permutation",
    top_n:  Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[dict]:
    """
    Returns ranked feature importance.

    - `method=permutation`: increase in MAE when a feature is shuffled (36 original features)
    - `method=shap`: mean |SHAP value| per feature in log-price units (43 transformed features)
    """
    if method not in ("permutation", "shap"):
        raise HTTPException(status_code=400, detail="method must be 'permutation' or 'shap'")
    rows = csv_to_records(_model_results_path(f"feature_importance_{method}", city))
    return rows[:top_n]


# ── 5. Residuals ───────────────────────────────────────────────────────────────

@router.get("/ml/residuals", summary="Test-set residuals with price band, room type, neighbourhood")
def ml_residuals(
    city:          Annotated[str, Query()] = "london",
    room_type:     Annotated[str | None, Query()] = None,
    neighbourhood: Annotated[str | None, Query()] = None,
    price_band:    Annotated[str | None, Query()] = None,
    limit:         Annotated[int, Query(ge=1, le=5000)] = 500,
    offset:        Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    """
    Returns enriched test-set residuals (actual price, predicted price, error,
    room type, neighbourhood, price band, host segment).

    Optional filters: room_type, neighbourhood (substring), price_band.
    Pagination: limit + offset.
    """
    rows = csv_to_records(_model_results_path("residuals_enriched", city))

    if room_type:
        rows = [r for r in rows if str(r.get("room_type", "")).lower() == room_type.lower()]
    if neighbourhood:
        rows = [r for r in rows if neighbourhood.lower() in str(r.get("neighbourhood_cleansed", "")).lower()]
    if price_band:
        rows = [r for r in rows if str(r.get("price_band", "")).lower() == price_band.lower()]

    return rows[offset: offset + limit]


# ── 6. Residuals by segment ────────────────────────────────────────────────────

@router.get("/ml/residuals/by-segment", summary="Aggregated error metrics per segment group")
def ml_residuals_by_segment(
    city:    Annotated[str, Query()] = "london",
    segment: Annotated[str, Query(
        description="One of: neighbourhood, room_type, price_band, property_type, host_segment"
    )] = "neighbourhood",
) -> list[dict]:
    """
    Returns pre-computed MAE, median residual, and within-20% accuracy grouped
    by the requested segment.  These are the Step-9 deep residual analysis tables.
    """
    if segment not in _VALID_SEGMENT_COLS:
        raise HTTPException(
            status_code=400,
            detail=f"segment must be one of: {', '.join(_VALID_SEGMENT_COLS)}",
        )
    return csv_to_records(_model_results_path(_VALID_SEGMENT_COLS[segment], city))


# ── 7. Live price prediction ───────────────────────────────────────────────────

class PredictRequest(BaseModel):
    city:                          str   = Field("london", description="City whose model to use")
    # Required inputs — the two most important features
    accommodates:                  int   = Field(..., ge=1, le=20,  description="Number of guests")
    room_type:                     str   = Field(..., description="entire_home | private_room | shared_room | hotel_room")
    neighbourhood_cleansed:        str   = Field(..., description="London borough (e.g. 'Camden')")
    # Capacity
    bedrooms:            Optional[float] = Field(None, ge=0)
    beds:                Optional[float] = Field(None, ge=0)
    bathroom_count:      Optional[float] = Field(None, ge=0)
    bathroom_is_shared:  Optional[int]   = Field(None, ge=0, le=1)
    # Stay rules
    minimum_nights:      Optional[int]   = Field(None, ge=1)
    availability_365:    Optional[int]   = Field(None, ge=0, le=365)
    # Host profile
    host_tenure_years:   Optional[float] = Field(None, ge=0)
    host_response_rate:  Optional[float] = Field(None, ge=0, le=100)
    host_is_superhost:   Optional[int]   = Field(None, ge=0, le=1)
    instant_bookable:    Optional[int]   = Field(None, ge=0, le=1)
    calculated_host_listings_count: Optional[int] = Field(None, ge=1)
    # Location
    latitude:            Optional[float] = None
    longitude:           Optional[float] = None
    # Review scores
    review_scores_rating:      Optional[float] = Field(None, ge=0, le=5)
    review_scores_cleanliness: Optional[float] = Field(None, ge=0, le=5)
    review_scores_location:    Optional[float] = Field(None, ge=0, le=5)
    reviews_per_month_calc:    Optional[float] = Field(None, ge=0)
    number_of_reviews:         Optional[int]   = Field(None, ge=0)
    # Property type
    property_type_bucket: Optional[str] = Field(None, description="apartment | house | hotel | unique | other")
    # Amenities (0/1 flags)
    has_wifi:            Optional[int] = Field(None, ge=0, le=1)
    has_kitchen:         Optional[int] = Field(None, ge=0, le=1)
    has_air_conditioning:Optional[int] = Field(None, ge=0, le=1)
    has_washer:          Optional[int] = Field(None, ge=0, le=1)
    has_parking:         Optional[int] = Field(None, ge=0, le=1)
    has_pool:            Optional[int] = Field(None, ge=0, le=1)
    has_workspace:       Optional[int] = Field(None, ge=0, le=1)
    has_gym:             Optional[int] = Field(None, ge=0, le=1)
    has_elevator:        Optional[int] = Field(None, ge=0, le=1)
    has_tv:              Optional[int] = Field(None, ge=0, le=1)
    has_bathtub:         Optional[int] = Field(None, ge=0, le=1)
    has_dishwasher:      Optional[int] = Field(None, ge=0, le=1)
    amenity_count:       Optional[int] = Field(None, ge=0)


class PredictResponse(BaseModel):
    predicted_price_gbp: float
    model_used:          str
    city:                str
    warning:             Optional[str] = None


@router.post(
    "/ml/predict",
    summary="Live price prediction — POST listing features, get GBP price estimate",
    response_model=PredictResponse,
)
def ml_predict(body: PredictRequest) -> PredictResponse:
    """
    Run the trained LightGBM pipeline on user-supplied listing features.

    Only `accommodates`, `room_type`, and `neighbourhood_cleansed` are required.
    All other features are optional — the pipeline's median imputer fills gaps
    using training-set medians, so partial inputs still produce valid estimates.

    `beds_per_guest` is derived automatically from `beds` / `accommodates` when
    `beds` is provided; otherwise the imputer handles it.

    **Limitations**:
    - Luxury listings (> £500) are systematically underpredicted (Step-9 finding).
    - `hotel_room` type has very few training examples — predictions are unreliable.
    - Unseen neighbourhoods fall back to the global training mean via TargetEncoder shrinkage.
    """
    model = _get_model(body.city)

    # Derive beds_per_guest if possible
    beds_per_guest = None
    if body.beds is not None and body.accommodates > 0:
        beds_per_guest = body.beds / body.accommodates

    # Build a single-row DataFrame matching the 36-feature schema
    row = {
        "accommodates":                    body.accommodates,
        "bedrooms":                        body.bedrooms,
        "beds":                            body.beds,
        "bathroom_count":                  body.bathroom_count,
        "minimum_nights":                  body.minimum_nights,
        "host_tenure_years":               body.host_tenure_years,
        "host_response_rate":              body.host_response_rate,
        "latitude":                        body.latitude,
        "longitude":                       body.longitude,
        "availability_365":                body.availability_365,
        "review_scores_rating":            body.review_scores_rating,
        "review_scores_cleanliness":       body.review_scores_cleanliness,
        "review_scores_location":          body.review_scores_location,
        "reviews_per_month_calc":          body.reviews_per_month_calc,
        "calculated_host_listings_count":  body.calculated_host_listings_count,
        "number_of_reviews":               body.number_of_reviews,
        "beds_per_guest":                  beds_per_guest,
        "host_is_superhost":               body.host_is_superhost,
        "instant_bookable":                body.instant_bookable,
        "bathroom_is_shared":              body.bathroom_is_shared,
        "has_wifi":                        body.has_wifi,
        "has_kitchen":                     body.has_kitchen,
        "has_air_conditioning":            body.has_air_conditioning,
        "has_washer":                      body.has_washer,
        "has_parking":                     body.has_parking,
        "has_pool":                        body.has_pool,
        "has_workspace":                   body.has_workspace,
        "has_gym":                         body.has_gym,
        "has_elevator":                    body.has_elevator,
        "has_tv":                          body.has_tv,
        "has_bathtub":                     body.has_bathtub,
        "has_dishwasher":                  body.has_dishwasher,
        "amenity_count":                   body.amenity_count,
        "room_type":                       body.room_type,
        "property_type_bucket":            body.property_type_bucket,
        "neighbourhood_cleansed":          body.neighbourhood_cleansed,
    }
    X = pd.DataFrame([row])

    try:
        log_pred = model.predict(X)
        price    = float(np.expm1(log_pred[0]))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")

    # Warn when the prediction is likely unreliable
    warning = None
    if price > 500:
        warning = (
            "Luxury range (>£500): model systematically underpredicts at this price tier "
            "(Step-9 finding: median residual +£376). Treat as a lower-bound estimate."
        )
    elif body.room_type == "hotel_room":
        warning = (
            "hotel_room has very few training examples (n=17 in test set). "
            "Prediction reliability is low for this room type."
        )

    metadata = read_json(MODELS_DIR / f"{body.city}_model_metadata.json")

    return PredictResponse(
        predicted_price_gbp=round(price, 2),
        model_used=metadata.get("model_type", "Gradient Boosting (LightGBM)"),
        city=body.city,
        warning=warning,
    )


# ── Clustering helpers ─────────────────────────────────────────────────────────

DATA_DIR = ROOT / "data" / "processed"

# City-centre coordinates (same as clustering_features.py)
_CLUSTER_CENTRES: dict[str, tuple[float, float]] = {
    "london":    (51.5080, -0.1281),
    "amsterdam": (52.3732,  4.8932),
}

# Features and skewed cols must match the order used during K-Means training
_CLUSTER_FEATURES = [
    "log_price", "accommodates", "bedrooms", "minimum_nights",
    "availability_365", "review_scores_rating", "reviews_per_month_calc",
    "distance_to_centre_km", "amenity_count",
]
_LOG1P_CLUSTER_COLS = ["minimum_nights", "bedrooms", "reviews_per_month_calc"]

_cluster_model_cache:   dict = {}
_cluster_profile_cache: dict = {}   # city -> {cluster_id: name}
_cluster_medians_cache: dict = {}   # city -> {feature: median}


def _get_cluster_model(city: str) -> dict:
    if city not in _cluster_model_cache:
        path = MODELS_DIR / f"{city}_kmeans.joblib"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No K-Means model for '{city}'. Run cluster_listings.py first.",
            )
        _cluster_model_cache[city] = joblib.load(path)
    return _cluster_model_cache[city]


def _get_cluster_profile(city: str) -> dict[int, str]:
    """Returns {cluster_id: cluster_name} loaded once per process."""
    if city not in _cluster_profile_cache:
        path = MODEL_RESULTS / f"clustering_profile_{city}.csv"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No cluster profile for '{city}'. Run cluster_profiles.py first.",
            )
        df = pd.read_csv(path)
        _cluster_profile_cache[city] = dict(
            zip(df["cluster"].astype(int), df["cluster_name"])
        )
    return _cluster_profile_cache[city]


def _get_cluster_medians(city: str) -> dict[str, float]:
    """Load training-set column medians from clustering_features.parquet (cached)."""
    if city not in _cluster_medians_cache:
        path = DATA_DIR / city / "clustering_features.parquet"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"clustering_features.parquet not found for '{city}'.",
            )
        df = pd.read_parquet(path)
        _cluster_medians_cache[city] = df.median(numeric_only=True).to_dict()
    return _cluster_medians_cache[city]


def _haversine_scalar(lat: float, lon: float, centre_lat: float, centre_lon: float) -> float:
    """Haversine distance in km for a single point."""
    R = 6371.0
    dlat = np.radians(centre_lat - lat)
    dlon = np.radians(centre_lon - lon)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat)) * np.cos(np.radians(centre_lat)) * np.sin(dlon / 2) ** 2
    )
    return float(R * 2 * np.arcsin(np.sqrt(a)))


# ── 8. Cluster profiles ────────────────────────────────────────────────────────

@router.get(
    "/clustering/profile",
    summary="Cluster profiles — per-segment statistics and names",
)
def clustering_profile(
    city: Annotated[str, Query(description="london or amsterdam")] = "london",
) -> list[dict]:
    """
    Returns the Step-21 cluster profiles for one city.

    Each record includes: cluster_id, cluster_name, n, pct_of_city,
    median_price, mean feature statistics, room-type breakdown, top_neighbourhood.
    """
    return csv_to_records(must_exist(MODEL_RESULTS / f"clustering_profile_{city}.csv"))


# ── 9. Elbow scores ────────────────────────────────────────────────────────────

@router.get(
    "/clustering/elbow",
    summary="Elbow sweep — inertia and silhouette for k=2..10",
)
def clustering_elbow(
    city: Annotated[str, Query()] = "london",
) -> list[dict]:
    """Returns the Step-20 elbow sweep table used to select optimal k."""
    return csv_to_records(must_exist(MODEL_RESULTS / f"elbow_scores_{city}.csv"))


# ── 10. Cluster labels (paginated) ─────────────────────────────────────────────

@router.get(
    "/clustering/labels",
    summary="Labelled listings — cluster assignment + key features, paginated",
)
def clustering_labels(
    city:          Annotated[str, Query()] = "london",
    cluster:       Annotated[Optional[int], Query(ge=0, description="Filter to a single cluster ID")] = None,
    room_type:     Annotated[Optional[str], Query(description="Exact match on room_type")] = None,
    neighbourhood: Annotated[Optional[str], Query(description="Substring match on neighbourhood_cleansed")] = None,
    limit:         Annotated[int, Query(ge=1, le=500)] = 100,
    offset:        Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """
    Returns listing IDs, cluster assignments, and key features.

    Pagination via `limit` (max 500) and `offset`. Optional filters:
    `cluster` (exact ID), `room_type` (exact), `neighbourhood` (substring).
    """
    path = DATA_DIR / city / "clustering_labels.parquet"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"clustering_labels.parquet not found for '{city}'. Run cluster_listings.py first.",
        )

    # Build DuckDB WHERE clauses (use forward slashes — DuckDB on Windows)
    pq_path = str(path).replace("\\", "/")
    where_parts: list[str] = []
    if cluster is not None:
        where_parts.append(f"cluster = {cluster}")
    if room_type:
        safe_rt = room_type.replace("'", "''")
        where_parts.append(f"LOWER(room_type) = LOWER('{safe_rt}')")
    if neighbourhood:
        safe_nb = neighbourhood.replace("'", "''")
        where_parts.append(f"LOWER(neighbourhood_cleansed) LIKE LOWER('%{safe_nb}%')")

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    data_sql = (
        f"SELECT id, cluster, room_type, neighbourhood_cleansed, price_numeric, "
        f"accommodates, bedrooms, availability_365, distance_to_centre_km "
        f"FROM read_parquet('{pq_path}') {where_sql} "
        f"ORDER BY cluster, id LIMIT {limit} OFFSET {offset}"
    )
    count_sql = (
        f"SELECT COUNT(*) AS total FROM read_parquet('{pq_path}') {where_sql}"
    )

    conn = duckdb.connect()
    try:
        rows  = conn.execute(data_sql).fetchdf().to_dict(orient="records")
        total = conn.execute(count_sql).fetchone()[0]  # type: ignore[index]
    finally:
        conn.close()

    return {"city": city, "total": total, "limit": limit, "offset": offset, "rows": rows}


# ── 11. Live cluster assignment ────────────────────────────────────────────────

class ClusterAssignRequest(BaseModel):
    city: str = Field("london", description="london or amsterdam")
    # Price — provide price_numeric OR log_price (price_numeric takes precedence)
    price_numeric:          Optional[float] = Field(None, ge=0,  description="Nightly price in local currency → log1p applied internally")
    log_price:              Optional[float] = Field(None,         description="log1p(price_numeric) — use when you have the log value directly")
    # Location — provide lat/lon OR distance_to_centre_km (lat/lon takes precedence)
    latitude:               Optional[float] = None
    longitude:              Optional[float] = None
    distance_to_centre_km:  Optional[float] = Field(None, ge=0)
    # Remaining clustering features (all optional — missing values use training medians)
    accommodates:           Optional[int]   = Field(None, ge=1,  le=20)
    bedrooms:               Optional[float] = Field(None, ge=0)
    minimum_nights:         Optional[int]   = Field(None, ge=1)
    availability_365:       Optional[int]   = Field(None, ge=0,  le=365)
    review_scores_rating:   Optional[float] = Field(None, ge=0,  le=5)
    reviews_per_month_calc: Optional[float] = Field(None, ge=0)
    amenity_count:          Optional[int]   = Field(None, ge=0)


class ClusterAssignResponse(BaseModel):
    cluster_id:       int
    cluster_name:     str
    city:             str
    imputed_features: list[str]         # features that were missing and filled from training medians
    features_used:    dict[str, float]  # final feature vector sent to the model


@router.post(
    "/clustering/assign",
    summary="Assign a new listing to a market segment using the saved K-Means model",
    response_model=ClusterAssignResponse,
)
def clustering_assign(body: ClusterAssignRequest) -> ClusterAssignResponse:
    """
    Predict which market segment a new listing belongs to.

    Only `city` is required — every other field is optional. Missing features
    are filled from training-set column medians so even a minimal request
    returns a valid cluster (though more inputs give a more accurate result).

    **Derived inputs:**
    - `price_numeric` → `log_price` via log1p (takes precedence over `log_price`)
    - `latitude` + `longitude` → `distance_to_centre_km` via haversine (takes precedence over `distance_to_centre_km`)

    The `imputed_features` field in the response lists every feature that was
    filled from training medians so you can see how much was inferred.
    """
    artifact   = _get_cluster_model(body.city)
    scaler     = artifact["scaler"]
    kmeans     = artifact["kmeans"]
    log1p_cols: list[str] = artifact["log1p_cols"]
    features:   list[str] = artifact["features"]

    medians  = _get_cluster_medians(body.city)
    name_map = _get_cluster_profile(body.city)

    # ── Resolve log_price ──────────────────────────────────────────────────────
    log_price = body.log_price
    if body.price_numeric is not None:
        log_price = float(np.log1p(body.price_numeric))

    # ── Resolve distance_to_centre_km ──────────────────────────────────────────
    distance = body.distance_to_centre_km
    if body.latitude is not None and body.longitude is not None:
        if body.city not in _CLUSTER_CENTRES:
            raise HTTPException(400, detail=f"No city centre defined for '{body.city}'.")
        clat, clon = _CLUSTER_CENTRES[body.city]
        distance = _haversine_scalar(body.latitude, body.longitude, clat, clon)

    # ── Collect raw values (None = missing, will be imputed) ──────────────────
    raw: dict[str, Optional[float]] = {
        "log_price":              log_price,
        "accommodates":           float(body.accommodates) if body.accommodates is not None else None,
        "bedrooms":               body.bedrooms,
        "minimum_nights":         float(body.minimum_nights) if body.minimum_nights is not None else None,
        "availability_365":       float(body.availability_365) if body.availability_365 is not None else None,
        "review_scores_rating":   body.review_scores_rating,
        "reviews_per_month_calc": body.reviews_per_month_calc,
        "distance_to_centre_km":  distance,
        "amenity_count":          float(body.amenity_count) if body.amenity_count is not None else None,
    }

    # Impute missing features from training medians
    imputed: list[str] = []
    filled: dict[str, float] = {}
    for feat in features:
        val = raw.get(feat)
        if val is None:
            filled[feat] = medians.get(feat, 0.0)
            imputed.append(feat)
        else:
            filled[feat] = val

    # Apply log1p to skewed features (same transform used during K-Means training)
    for col in log1p_cols:
        if col in filled:
            filled[col] = float(np.log1p(filled[col]))

    # ── Scale and predict ──────────────────────────────────────────────────────
    # Use a DataFrame so StandardScaler sees the column names it was fitted on
    X = pd.DataFrame([[filled[f] for f in features]], columns=features)
    X_scaled   = scaler.transform(X)       # type: ignore[attr-defined]
    cluster_id = int(kmeans.predict(X_scaled)[0])  # type: ignore[attr-defined]

    return ClusterAssignResponse(
        cluster_id=cluster_id,
        cluster_name=name_map.get(cluster_id, f"Cluster {cluster_id}"),
        city=body.city,
        imputed_features=imputed,
        features_used={k: round(v, 4) for k, v in filled.items()},
    )
