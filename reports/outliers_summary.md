# Outliers and Rule Violations

City: **amsterdam** · Snapshot: **2025-09-11**

Sentinel rows (e.g. `maximum_nights = 2^31 - 1`, A-018) are stripped before IQR is computed; they are counted separately in `sentinel_int_max_rows` so they aren't conflated with real outliers.

## 1. Domain-rule violations

| File | Rule | Violations |
|---|---|---:|
| `listings.csv.gz` | `price_negative` | 0 |
| `listings.csv.gz` | `price_zero` | 0 |
| `listings.csv.gz` | `latitude_out_of_range` | 0 |
| `listings.csv.gz` | `longitude_out_of_range` | 0 |
| `listings.csv.gz` | `latitude_outside_london_bbox` | 10,480 |
| `listings.csv.gz` | `longitude_outside_london_bbox` | 10,480 |
| `listings.csv.gz` | `minimum_nights_le_zero` | 0 |
| `listings.csv.gz` | `minimum_nights_ge_365` | 5 |
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
| `calendar.csv.gz` | `minimum_nights_ge_365` | 1,096 |
| `calendar.csv.gz` | `maximum_nights_int_max_sentinel` | 730 |

## 2. IQR outliers (sentinels removed first)

| File | Column | Non-null | Lower | Upper | Low outliers | High outliers | Sentinel rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `listings.csv.gz` | `accommodates` | 10,480 | -1.0 | 7.0 | 0 | 65 | 0 |
| `listings.csv.gz` | `bathrooms` | 5,932 | 0.25 | 2.25 | 57 | 219 | 0 |
| `listings.csv.gz` | `bedrooms` | 10,174 | -0.5 | 3.5 | 0 | 358 | 0 |
| `listings.csv.gz` | `beds` | 5,904 | -0.5 | 3.5 | 0 | 514 | 0 |
| `listings.csv.gz` | `minimum_nights` | 10,480 | -1.0 | 7.0 | 0 | 426 | 0 |
| `listings.csv.gz` | `maximum_nights` | 10,480 | -497.5 | 882.5 | 0 | 1,541 | 0 |
| `listings.csv.gz` | `availability_30` | 10,480 | -10.5 | 17.5 | 0 | 1,286 | 0 |
| `listings.csv.gz` | `availability_60` | 10,480 | -31.5 | 52.5 | 0 | 639 | 0 |
| `listings.csv.gz` | `availability_90` | 10,480 | -63.0 | 105.0 | 0 | 0 | 0 |
| `listings.csv.gz` | `availability_365` | 10,480 | -259.5 | 432.5 | 0 | 0 | 0 |
| `listings.csv.gz` | `number_of_reviews` | 10,480 | -37.5 | 70.5 | 0 | 1,482 | 0 |
| `listings.csv.gz` | `number_of_reviews_ltm` | 10,480 | -9.0 | 15.0 | 0 | 1,366 | 0 |
| `listings.csv.gz` | `review_scores_rating` | 9,383 | 4.475 | 5.315 | 527 | 0 | 0 |
| `listings.csv.gz` | `reviews_per_month` | 9,383 | -0.865 | 1.975 | 0 | 1,285 | 0 |
| `listings.csv.gz` | `calculated_host_listings_count` | 10,480 | 1.0 | 1.0 | 0 | 1,857 | 0 |
| `listings.csv.gz` | `estimated_occupancy_l365d` | 10,480 | -72.0 | 120.0 | 0 | 1,426 | 0 |
| `listings.csv.gz` | `estimated_revenue_l365d` | 5,874 | -26476.875 | 48480.125 | 0 | 414 | 0 |
| `calendar.csv.gz` | `minimum_nights` | 3,825,200 | -1.0 | 7.0 | 0 | 159,221 | 0 |
| `calendar.csv.gz` | `maximum_nights` | 3,824,470 | -1042.5 | 1793.5 | 0 | 0 | 730 |

## 3. Phase 2.2 implications

- IQR "outliers" on bounded columns (`availability_*`, `review_scores_rating`) are statistical artifacts of the long tail at zero — not data errors. They should NOT be quarantined.
- Domain-rule violations on `latitude`/`longitude` *would* be quarantined, but London passes them all.
- Sentinel rows in `maximum_nights` map to NULL in Phase 2.2 (`cap_sentinel_intmax`).
- Listings with `minimum_nights >= 365` flow into `is_de_facto_inactive` in Phase 2.3 (A-019).