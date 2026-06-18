"""Cross-table warehouse integrity checks (dims + structural).

These cover the dim tables that don't have dedicated test files, plus
shape and continuity invariants of the warehouse as a whole.
"""


def test_dim_neighbourhood_key_unique(warehouse_con):
    total, distinct = warehouse_con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT neighbourhood_key) FROM dim_neighbourhood"
    ).fetchone()
    assert total == distinct, "neighbourhood_key not unique"


def test_dim_neighbourhood_area_positive(warehouse_con):
    # Area must be positive — zero means the GeoJSON join failed.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM dim_neighbourhood WHERE area_km2 IS NULL OR area_km2 <= 0"
    ).fetchone()[0]
    assert n == 0, f"{n} neighbourhoods have non-positive area_km2"


def test_dim_neighbourhood_count_matches_source(warehouse_con):
    # London has exactly 33 boroughs in this snapshot (A-028).
    n = warehouse_con.execute("SELECT COUNT(*) FROM dim_neighbourhood").fetchone()[0]
    assert n == 33, f"expected 33 boroughs, got {n}"


def test_dim_host_unique_source_id(warehouse_con):
    # source_host_id must be unique across dim_host (one row per host).
    total, distinct = warehouse_con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT source_host_id) FROM dim_host"
    ).fetchone()
    assert total == distinct, f"{total - distinct} duplicate source_host_id"


def test_dim_date_monotonic(warehouse_con):
    # dim_date must cover an unbroken date range (no gaps).
    min_d, max_d, n = warehouse_con.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) FROM dim_date"
    ).fetchone()
    expected = (max_d - min_d).days + 1
    assert n == expected, f"dim_date has gaps: {expected - n} missing days"


def test_dim_date_year_bounds(warehouse_con):
    # Sanity guard on coverage years.
    min_y, max_y = warehouse_con.execute(
        "SELECT MIN(year), MAX(year) FROM dim_date"
    ).fetchone()
    assert min_y <= 2010 and max_y >= 2026, f"year coverage too narrow: [{min_y}, {max_y}]"


def test_dim_date_key_unique(warehouse_con):
    total, distinct = warehouse_con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT date_key) FROM dim_date"
    ).fetchone()
    assert total == distinct, "date_key not unique in dim_date"


def test_warehouse_tables_present(warehouse_con):
    # Every expected table must exist after a successful load.
    rows = warehouse_con.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main'
    """).fetchall()
    present = {r[0] for r in rows}
    expected = {
        "dim_city", "dim_neighbourhood", "dim_host", "dim_listing", "dim_date",
        "fact_calendar", "fact_reviews", "fact_listing_snapshot",
    }
    missing = expected - present
    assert not missing, f"missing warehouse tables: {missing}"
