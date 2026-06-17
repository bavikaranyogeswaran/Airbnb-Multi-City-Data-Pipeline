-- Superhost vs non-superhost: price, review score, occupancy proxy.
-- A-025 caveat: superhost status is point-in-time; do not infer causality from
-- historical review scores to current status.
SELECT
    COALESCE(dh.host_is_superhost::TEXT, 'unknown')         AS superhost_status,
    COUNT(*)                                                AS listing_count,
    ROUND(MEDIAN(fs.price_numeric), 2)                      AS median_price_gbp,
    ROUND(AVG(fs.price_numeric), 2)                         AS mean_price_gbp,
    ROUND(AVG(fs.review_scores_rating), 3)                  AS mean_review_score,
    ROUND(AVG(fs.occupancy_proxy), 4)                       AS mean_occupancy_proxy,
    ROUND(AVG(fs.host_tenure_years), 2)                     AS mean_host_tenure_years
FROM fact_listing_snapshot fs
JOIN dim_host dh USING (host_key)
GROUP BY dh.host_is_superhost
ORDER BY median_price_gbp DESC NULLS LAST;
