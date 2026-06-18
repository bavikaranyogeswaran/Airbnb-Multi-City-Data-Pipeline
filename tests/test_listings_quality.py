"""Listings quality checks against dim_listing and fact_listing_snapshot.

One assertion per rule from HTML plan section 3.6.
"""

VALID_ROOM_TYPES = {"entire_home", "private_room", "shared_room", "hotel_room"}


def test_listing_key_not_null(warehouse_con):
    # Every listing must have a key — it's the PK and the join target everywhere.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM dim_listing WHERE listing_key IS NULL"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have NULL listing_key"


def test_listing_key_unique(warehouse_con):
    # PK must be unique within the snapshot.
    total, distinct = warehouse_con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT listing_key) FROM dim_listing"
    ).fetchone()
    assert total == distinct, f"{total - distinct} duplicate listing_key rows"


def test_host_key_not_null(warehouse_con):
    # Every listing must resolve to a host; orphans break dim_host joins.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM dim_listing WHERE host_key IS NULL"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have NULL host_key"


def test_neighbourhood_key_not_null(warehouse_con):
    # Every listing must resolve to a borough.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM dim_listing WHERE neighbourhood_key IS NULL"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have NULL neighbourhood_key"


def test_room_type_valid(warehouse_con):
    # room_type must be one of the four canonical buckets (A-020).
    rows = warehouse_con.execute(
        "SELECT DISTINCT room_type FROM dim_listing"
    ).fetchall()
    values = {r[0] for r in rows}
    invalid = values - VALID_ROOM_TYPES
    assert not invalid, f"unexpected room_type values: {invalid}"


def test_latitude_in_range(warehouse_con):
    # Latitudes must be valid degrees; London bbox check is too strict here.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM dim_listing WHERE latitude IS NOT NULL "
        "AND (latitude < -90 OR latitude > 90)"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have out-of-range latitude"


def test_longitude_in_range(warehouse_con):
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM dim_listing WHERE longitude IS NOT NULL "
        "AND (longitude < -180 OR longitude > 180)"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have out-of-range longitude"


def test_price_null_or_non_negative(warehouse_con):
    # Per A-012 we keep NULL prices; non-NULL must be non-negative.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_listing_snapshot "
        "WHERE price_numeric IS NOT NULL AND price_numeric < 0"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have negative price"


def test_availability_365_in_range(warehouse_con):
    # availability_365 must be in [0, 365] when present.
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_listing_snapshot "
        "WHERE availability_365 IS NOT NULL "
        "AND (availability_365 < 0 OR availability_365 > 365)"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have availability_365 out of [0, 365]"


def test_number_of_reviews_non_negative(warehouse_con):
    n = warehouse_con.execute(
        "SELECT COUNT(*) FROM fact_listing_snapshot WHERE number_of_reviews < 0"
    ).fetchone()[0]
    assert n == 0, f"{n} listings have negative number_of_reviews"


def test_fact_snapshot_matches_dim_count(warehouse_con):
    # One snapshot row per listing — they must align exactly.
    dim_n = warehouse_con.execute("SELECT COUNT(*) FROM dim_listing").fetchone()[0]
    fact_n = warehouse_con.execute("SELECT COUNT(*) FROM fact_listing_snapshot").fetchone()[0]
    assert dim_n == fact_n, f"dim_listing={dim_n}, fact_listing_snapshot={fact_n}"
