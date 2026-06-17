-- Top 10 neighbourhoods (boroughs) by listing count, with median price and density.
SELECT
    dn.neighbourhood_name                                   AS neighbourhood,
    COUNT(*)                                                AS listing_count,
    ROUND(MEDIAN(fs.price_numeric), 2)                      AS median_price_gbp,
    ROUND(AVG(fs.review_scores_rating), 3)                  AS avg_review_score,
    ROUND(dn.area_km2, 2)                                   AS area_km2,
    ROUND(COUNT(*) / NULLIF(dn.area_km2, 0), 1)             AS listings_per_km2
FROM fact_listing_snapshot fs
JOIN dim_neighbourhood dn USING (neighbourhood_key)
GROUP BY dn.neighbourhood_name, dn.area_km2
ORDER BY listing_count DESC
LIMIT 10;
