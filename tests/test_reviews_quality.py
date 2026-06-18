"""Reviews quality checks against fact_reviews."""


def test_review_id_unique(warehouse_con):
    # review_id is the PK; must be unique across 2.1M rows.
    total, distinct = warehouse_con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT review_id) FROM fact_reviews"
    ).fetchone()
    assert total == distinct, f"{total - distinct} duplicate review_id rows"


def test_listing_key_not_null(warehouse_con):
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_reviews WHERE listing_key IS NULL"
    ).fetchone()[0]
    assert n == 0, f"{n} reviews with NULL listing_key"


def test_date_key_not_null(warehouse_con):
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_reviews WHERE date_key IS NULL"
    ).fetchone()[0]
    assert n == 0, f"{n} reviews with NULL date_key"


def test_referential_integrity_to_dim_listing(warehouse_con):
    # Phase 1 Step 8 confirmed 0 orphan reviews; this guards regressions.
    orphans = warehouse_con.execute("""
        SELECT COUNT(*) FROM fact_reviews fr
        WHERE NOT EXISTS (
            SELECT 1 FROM dim_listing dl WHERE dl.listing_key = fr.listing_key
        )
    """).fetchone()[0]
    assert orphans == 0, f"{orphans} reviews reference a missing listing_key"


def test_referential_integrity_to_dim_date(warehouse_con):
    orphans = warehouse_con.execute("""
        SELECT COUNT(*) FROM fact_reviews fr
        WHERE NOT EXISTS (
            SELECT 1 FROM dim_date dd WHERE dd.date_key = fr.date_key
        )
    """).fetchone()[0]
    assert orphans == 0, f"{orphans} reviews reference a missing date_key"


def test_comment_length_non_negative(warehouse_con):
    # comment_length is computed from string length; sanity guard.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_reviews "
        "WHERE comment_length IS NOT NULL AND comment_length < 0"
    ).fetchone()[0]
    assert n == 0, f"{n} reviews have negative comment_length"
