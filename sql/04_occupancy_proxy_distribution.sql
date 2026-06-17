-- Occupancy proxy distribution decile by decile. A-002 caveat: this is an upper
-- bound because `f` in the calendar means "unavailable" not "booked".
WITH deciled AS (
    SELECT
        occupancy_proxy,
        price_numeric,
        revenue_proxy_gbp,
        NTILE(10) OVER (ORDER BY occupancy_proxy) AS decile
    FROM fact_listing_snapshot
    WHERE occupancy_proxy IS NOT NULL
)
SELECT
    decile,
    COUNT(*)                                AS listings,
    ROUND(MIN(occupancy_proxy), 4)          AS min_in_decile,
    ROUND(MAX(occupancy_proxy), 4)          AS max_in_decile,
    ROUND(AVG(occupancy_proxy), 4)          AS mean_in_decile,
    ROUND(AVG(price_numeric), 2)            AS mean_price_gbp,
    ROUND(AVG(revenue_proxy_gbp), 2)        AS mean_revenue_proxy_gbp
FROM deciled
GROUP BY decile
ORDER BY decile;
