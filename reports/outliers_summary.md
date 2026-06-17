# Outliers and Rule Violations

City: **london** · Snapshot: **2025-09-14**

Sentinel rows (e.g. `maximum_nights = 2^31 - 1`, A-018) are stripped before IQR is computed; they are counted separately in `sentinel_int_max_rows` so they aren't conflated with real outliers.

## 1. Domain-rule violations

| File | Rule | Violations |
|---|---|---:|
| `listings.csv.gz` | `price_negative` | 0 |
| `listings.csv.gz` | `price_zero` | 0 |
| `listings.csv.gz` | `latitude_out_of_range` | 0 |
| `listings.csv.gz` | `longitude_out_of_range` | 0 |
| `listings.csv.gz` | `latitude_outside_london_bbox` | 0 |
| `listings.csv.gz` | `longitude_outside_london_bbox` | 0 |
| `listings.csv.gz` | `minimum_nights_le_zero` | 0 |
| `listings.csv.gz` | `minimum_nights_ge_365` | 120 |
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
| `calendar.csv.gz` | `minimum_nights_ge_365` | 41,137 |
| `calendar.csv.gz` | `maximum_nights_int_max_sentinel` | 4,708 |

## 2. IQR outliers (sentinels removed first)

| File | Column | Non-null | Lower | Upper | Low outliers | High outliers | Sentinel rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `listings.csv.gz` | `accommodates` | 96,871 | -1.0 | 7.0 | 0 | 4,705 | 0 |
| `listings.csv.gz` | `bathrooms` | 62,025 | 0.25 | 2.25 | 356 | 4,852 | 0 |
| `listings.csv.gz` | `bedrooms` | 84,096 | -0.5 | 3.5 | 0 | 4,512 | 0 |
| `listings.csv.gz` | `beds` | 61,951 | -0.5 | 3.5 | 0 | 7,147 | 0 |
| `listings.csv.gz` | `minimum_nights` | 96,871 | -3.5 | 8.5 | 0 | 7,136 | 0 |
| `listings.csv.gz` | `maximum_nights` | 96,871 | -945.0 | 1735.0 | 0 | 7 | 0 |
| `listings.csv.gz` | `availability_30` | 96,871 | -27.0 | 45.0 | 0 | 0 | 0 |
| `listings.csv.gz` | `availability_60` | 96,871 | -67.5 | 112.5 | 0 | 0 | 0 |
| `listings.csv.gz` | `availability_90` | 96,871 | -109.5 | 182.5 | 0 | 0 | 0 |
| `listings.csv.gz` | `availability_365` | 96,871 | -432.0 | 720.0 | 0 | 0 | 0 |
| `listings.csv.gz` | `number_of_reviews` | 96,871 | -27.5 | 48.5 | 0 | 11,446 | 0 |
| `listings.csv.gz` | `number_of_reviews_ltm` | 96,871 | -9.0 | 15.0 | 0 | 11,039 | 0 |
| `listings.csv.gz` | `review_scores_rating` | 72,749 | 3.95 | 5.63 | 3,081 | 0 | 0 |
| `listings.csv.gz` | `reviews_per_month` | 72,749 | -1.56 | 3.0 | 0 | 5,502 | 0 |
| `listings.csv.gz` | `calculated_host_listings_count` | 96,871 | -9.5 | 18.5 | 0 | 15,601 | 0 |
| `listings.csv.gz` | `estimated_occupancy_l365d` | 96,871 | -90.0 | 150.0 | 0 | 11,309 | 0 |
| `listings.csv.gz` | `estimated_revenue_l365d` | 61,963 | -18375.0 | 30625.0 | 0 | 5,257 | 0 |
| `calendar.csv.gz` | `minimum_nights` | 35,357,974 | -3.5 | 8.5 | 0 | 3,006,207 | 0 |
| `calendar.csv.gz` | `maximum_nights` | 35,353,266 | -1462.5 | 2677.5 | 0 | 1,748 | 4,708 |

## 3. Phase 2.2 implications

- IQR "outliers" on bounded columns (`availability_*`, `review_scores_rating`) are statistical artifacts of the long tail at zero — not data errors. They should NOT be quarantined.
- Domain-rule violations on `latitude`/`longitude` *would* be quarantined, but London passes them all.
- Sentinel rows in `maximum_nights` map to NULL in Phase 2.2 (`cap_sentinel_intmax`).
- Listings with `minimum_nights >= 365` flow into `is_de_facto_inactive` in Phase 2.3 (A-019).