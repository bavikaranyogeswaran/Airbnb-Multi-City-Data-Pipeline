# Outliers and Rule Violations

City: **madrid** · Snapshot: **2025-09-14**

Sentinel rows (e.g. `maximum_nights = 2^31 - 1`, A-018) are stripped before IQR is computed; they are counted separately in `sentinel_int_max_rows` so they aren't conflated with real outliers.

## 1. Domain-rule violations

| File | Rule | Violations |
|---|---|---:|
| `listings.csv.gz` | `price_negative` | 0 |
| `listings.csv.gz` | `price_zero` | 0 |
| `listings.csv.gz` | `latitude_out_of_range` | 0 |
| `listings.csv.gz` | `longitude_out_of_range` | 0 |
| `listings.csv.gz` | `latitude_outside_london_bbox` | 25,000 |
| `listings.csv.gz` | `longitude_outside_london_bbox` | 25,000 |
| `listings.csv.gz` | `minimum_nights_le_zero` | 0 |
| `listings.csv.gz` | `minimum_nights_ge_365` | 37 |
| `listings.csv.gz` | `maximum_nights_int_max_sentinel` | 0 |
| `listings.csv.gz` | `availability_30_out_of_range` | 0 |
| `listings.csv.gz` | `availability_60_out_of_range` | 0 |
| `listings.csv.gz` | `availability_90_out_of_range` | 0 |
| `listings.csv.gz` | `availability_365_out_of_range` | 0 |
| `listings.csv.gz` | `number_of_reviews_negative` | 0 |
| `listings.csv.gz` | `accommodates_le_zero` | 0 |
| `listings.csv.gz` | `bedrooms_negative` | 0 |
| `listings.csv.gz` | `beds_negative` | 0 |
| `calendar.csv.gz` | `available_not_in_t_f` | 0 |
| `calendar.csv.gz` | `minimum_nights_le_zero` | 0 |
| `calendar.csv.gz` | `minimum_nights_ge_365` | 13,703 |
| `calendar.csv.gz` | `maximum_nights_int_max_sentinel` | 0 |

## 2. IQR outliers (sentinels removed first)

| File | Column | Non-null | Lower | Upper | Low outliers | High outliers | Sentinel rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `listings.csv.gz` | `accommodates` | 25,000 | -1.0 | 7.0 | 0 | 862 | 0 |
| `listings.csv.gz` | `bathrooms` | 18,960 | 0.25 | 2.25 | 145 | 1,071 | 0 |
| `listings.csv.gz` | `bedrooms` | 22,488 | -0.5 | 3.5 | 0 | 684 | 0 |
| `listings.csv.gz` | `beds` | 18,965 | -0.5 | 3.5 | 0 | 2,135 | 0 |
| `listings.csv.gz` | `minimum_nights` | 25,000 | -3.5 | 8.5 | 0 | 4,742 | 0 |
| `listings.csv.gz` | `maximum_nights` | 25,000 | -862.5 | 2317.5 | 0 | 1 | 0 |
| `listings.csv.gz` | `availability_30` | 25,000 | -16.5 | 27.5 | 0 | 1,435 | 0 |
| `listings.csv.gz` | `availability_60` | 25,000 | -52.5 | 87.5 | 0 | 0 | 0 |
| `listings.csv.gz` | `availability_90` | 25,000 | -93.0 | 155.0 | 0 | 0 | 0 |
| `listings.csv.gz` | `availability_365` | 25,000 | -398.0 | 722.0 | 0 | 0 | 0 |
| `listings.csv.gz` | `number_of_reviews` | 25,000 | -81.5 | 138.5 | 0 | 2,812 | 0 |
| `listings.csv.gz` | `number_of_reviews_ltm` | 25,000 | -30.0 | 50.0 | 0 | 1,983 | 0 |
| `listings.csv.gz` | `review_scores_rating` | 19,853 | 3.945 | 5.505 | 955 | 0 | 0 |
| `listings.csv.gz` | `reviews_per_month` | 19,853 | -3.095 | 6.065 | 0 | 745 | 0 |
| `listings.csv.gz` | `calculated_host_listings_count` | 25,000 | -35.0 | 61.0 | 0 | 4,541 | 0 |
| `listings.csv.gz` | `estimated_occupancy_l365d` | 25,000 | -243.0 | 405.0 | 0 | 0 | 0 |
| `listings.csv.gz` | `estimated_revenue_l365d` | 18,953 | -28402.5 | 48457.5 | 0 | 809 | 0 |
| `calendar.csv.gz` | `minimum_nights` | 9,125,007 | -8.0 | 16.0 | 0 | 1,846,571 | 0 |
| `calendar.csv.gz` | `maximum_nights` | 9,125,007 | -775.0 | 2265.0 | 0 | 365 | 0 |

## 3. Phase 2.2 implications

- IQR "outliers" on bounded columns (`availability_*`, `review_scores_rating`) are statistical artifacts of the long tail at zero — not data errors. They should NOT be quarantined.
- Domain-rule violations on `latitude`/`longitude` *would* be quarantined, but London passes them all.
- Sentinel rows in `maximum_nights` map to NULL in Phase 2.2 (`cap_sentinel_intmax`).
- Listings with `minimum_nights >= 365` flow into `is_de_facto_inactive` in Phase 2.3 (A-019).