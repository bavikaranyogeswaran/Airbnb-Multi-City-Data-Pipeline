-- Weekend vs weekday availability rates from fact_calendar joined to dim_date.
-- A-005 prevents weekend-vs-weekday PRICE comparison; availability lift is the
-- only honest weekend signal in this snapshot.
SELECT
    CASE WHEN dd.is_weekend THEN 'weekend' ELSE 'weekday' END  AS day_segment,
    COUNT(*)                                                   AS calendar_rows,
    SUM(fc.available_int)                                      AS available_rows,
    ROUND(AVG(fc.available_int) * 100, 2)                      AS availability_pct,
    ROUND(AVG(fc.minimum_nights), 2)                           AS avg_minimum_nights
FROM fact_calendar fc
JOIN dim_date dd USING (date_key)
GROUP BY dd.is_weekend
ORDER BY day_segment;
