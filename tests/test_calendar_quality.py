"""Calendar quality checks against fact_calendar (35.4M rows).

All checks use SQL aggregations so the table never leaves DuckDB.
"""


def test_listing_key_not_null(warehouse_con):
    # Every calendar row must point at a listing.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_calendar WHERE listing_key IS NULL"
    ).fetchone()[0]
    assert n == 0, f"{n} calendar rows with NULL listing_key"


def test_date_key_not_null(warehouse_con):
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_calendar WHERE date_key IS NULL"
    ).fetchone()[0]
    assert n == 0, f"{n} calendar rows with NULL date_key"


def test_composite_key_unique(warehouse_con):
    # (listing_key, date_key) is the composite PK; must hold across 35M rows.
    total, distinct = warehouse_con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT (listing_key, date_key)) FROM fact_calendar"
    ).fetchone()
    assert total == distinct, f"{total - distinct} duplicate (listing_key, date_key) rows"


def test_available_int_is_zero_or_one(warehouse_con):
    # available_int is derived from a boolean — only 0 or 1 expected.
    bad = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_calendar WHERE available_int NOT IN (0, 1)"
    ).fetchone()[0]
    assert bad == 0, f"{bad} calendar rows have available_int not in (0, 1)"


def test_referential_integrity_to_dim_listing(warehouse_con):
    # No orphan calendar rows allowed.
    orphans = warehouse_con.execute("""
        SELECT COUNT(*) FROM fact_calendar fc
        WHERE NOT EXISTS (
            SELECT 1 FROM dim_listing dl WHERE dl.listing_key = fc.listing_key
        )
    """).fetchone()[0]
    assert orphans == 0, f"{orphans} calendar rows reference a missing listing_key"


def test_referential_integrity_to_dim_date(warehouse_con):
    # date_key must resolve to a dim_date row (built 2010-01-01 to 2027-01-01).
    orphans = warehouse_con.execute("""
        SELECT COUNT(*) FROM fact_calendar fc
        WHERE NOT EXISTS (
            SELECT 1 FROM dim_date dd WHERE dd.date_key = fc.date_key
        )
    """).fetchone()[0]
    assert orphans == 0, f"{orphans} calendar rows reference a missing date_key"
