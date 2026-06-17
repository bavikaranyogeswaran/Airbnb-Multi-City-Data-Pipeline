-- Median nightly price (GBP) by room type, on the non-null-price cohort (A-012).
SELECT
    dl.room_type,
    COUNT(*)                                                AS listing_count,
    COUNT(fs.price_numeric)                                 AS priced_listing_count,
    ROUND(MEDIAN(fs.price_numeric), 2)                      AS median_price_gbp,
    ROUND(AVG(fs.price_numeric), 2)                         AS mean_price_gbp,
    ROUND(STDDEV_SAMP(fs.price_numeric), 2)                 AS std_price_gbp
FROM fact_listing_snapshot fs
JOIN dim_listing dl USING (listing_key)
GROUP BY dl.room_type
ORDER BY median_price_gbp DESC NULLS LAST;
