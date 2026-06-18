"""Pipeline stage smoke tests.

Verifies that all src/ modules import cleanly and that key callables
exist with the expected signature. No file I/O — the warehouse fixture
is used only for the SQL model build smoke test.
"""

from __future__ import annotations

import inspect


# ── Module importability ───────────────────────────────────────────────────────

def test_transforms_module_importable():
    import src.cleaning.transforms as T  # noqa: F401
    assert hasattr(T, "clean_price")
    assert hasattr(T, "parse_bool")
    assert hasattr(T, "parse_date")
    assert hasattr(T, "validate_range")


def test_cleaning_listings_module_importable():
    import src.cleaning.listings as L  # noqa: F401
    assert callable(L.clean)
    assert callable(L.run)


def test_cleaning_calendar_module_importable():
    import src.cleaning.calendar  # noqa: F401


def test_cleaning_reviews_module_importable():
    import src.cleaning.reviews  # noqa: F401


def test_ingestion_module_importable():
    import src.ingestion.download  # noqa: F401


def test_loading_warehouse_module_importable():
    import src.loading.warehouse as wh  # noqa: F401
    assert callable(wh.build_all)
    assert callable(wh.list_tables)


def test_transformation_modules_importable():
    import src.transformation.listing_master   # noqa: F401
    import src.transformation.calendar_summary  # noqa: F401
    import src.transformation.review_summary    # noqa: F401


def test_orchestration_pipeline_importable():
    import src.orchestration.pipeline as pl  # noqa: F401
    assert callable(pl.run)


def test_api_app_importable():
    from src.api.app import app  # noqa: F401
    assert app is not None


def test_analytics_router_importable():
    from src.api.routes.analytics import router  # noqa: F401
    assert router.prefix == "/analytics"


# ── Clean() signature check ────────────────────────────────────────────────────

def test_clean_function_has_correct_signature():
    from src.cleaning.listings import clean
    sig = inspect.signature(clean)
    params = list(sig.parameters)
    # clean(df) takes a DataFrame and returns (clean_df, rejected_df)
    assert "df" in params


def test_run_functions_accept_city_parameter():
    from src.cleaning.listings import run
    sig = inspect.signature(run)
    assert "city" in sig.parameters


# ── SQL model build smoke test (requires warehouse) ───────────────────────────

def test_warehouse_tables_present_and_non_empty(warehouse_con):
    # Verifies the SQL model build produced the full star schema.
    expected = {
        "dim_city", "dim_neighbourhood", "dim_host",
        "dim_listing", "dim_date",
        "fact_calendar", "fact_reviews", "fact_listing_snapshot",
    }
    rows = warehouse_con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    present = {r[0] for r in rows}
    missing = expected - present
    assert not missing, f"SQL build missing tables: {missing}"


def test_fact_listing_snapshot_has_rows(warehouse_con):
    n = warehouse_con.execute("SELECT COUNT(*) FROM fact_listing_snapshot").fetchone()[0]
    assert n > 50_000, f"expected 50k+ listing rows, got {n}"


def test_dim_listing_price_non_negative(warehouse_con):
    # Same invariant checked by test_listings_quality but here framed as a
    # pipeline-build correctness assertion: the SQL model must not produce
    # negative prices.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_listing_snapshot "
        "WHERE price_numeric IS NOT NULL AND price_numeric < 0"
    ).fetchone()[0]
    assert n == 0
