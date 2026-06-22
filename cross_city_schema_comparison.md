# Cross-City Schema Comparison

| | London | Amsterdam |
|---|---|---|
| Country | United Kingdom | Netherlands |
| Snapshot | 2025-09-14 | 2025-09-11 |
| Currency | GBP | EUR |
| Source file | `listings.csv.gz` (79 cols) | `listings.csv.gz` (79 cols) |

---

## 1. Column presence

| Metric | Count |
|---|---|
| Columns in both cities | **79** |
| Only in London | 0 |
| Only in Amsterdam | 0 |

Both cities expose **identical column sets** in their `listings.csv.gz` files at this snapshot. This confirms Inside Airbnb's schema is standardised across cities.

---

## 2. Inferred dtype differences

| Column | london dtype | amsterdam dtype |
|---|---|---|
| `license` | `float64` | `str` |

---

## 3. Null-rate comparison (> 10 pp divergence)

| Column | london null % | amsterdam null % | Δ |
|---|---|---|---|
| `bedrooms` | 16.6% | 4.0% | 12.6 pp |
| `description` | 18.0% | 4.0% | 14.0 pp |
| `first_review` | 12.0% | 1.2% | 10.8 pp |
| `host_about` | 11.1% | 25.4% | 14.3 pp |
| `host_neighbourhood` | 13.3% | 32.1% | 18.8 pp |
| `last_review` | 12.0% | 1.2% | 10.8 pp |
| `license` | 100.0% | 0.1% | 99.9 pp |
| `neighborhood_overview` | 32.2% | 19.9% | 12.3 pp |
| `neighbourhood` | 32.2% | 19.9% | 12.3 pp |
| `review_scores_accuracy` | 12.2% | 1.2% | 11.0 pp |
| `review_scores_checkin` | 12.2% | 1.2% | 11.0 pp |
| `review_scores_cleanliness` | 12.2% | 1.3% | 10.9 pp |
| `review_scores_communication` | 12.2% | 1.2% | 11.0 pp |
| `review_scores_location` | 12.2% | 1.2% | 11.0 pp |
| `review_scores_rating` | 12.0% | 1.2% | 10.8 pp |
| `review_scores_value` | 12.2% | 1.2% | 11.0 pp |
| `reviews_per_month` | 12.0% | 1.2% | 10.8 pp |

---

## 4. Full per-column comparison

| Column | london null % | amsterdam null % | london card | amsterdam card |
|---|---|---|---|---|
| `accommodates` | 0.0% | 0.0% | 15 | 12 |
| `amenities` | 0.0% | 0.0% | 1888 | 1988 |
| `availability_30` | 0.0% | 0.0% | 31 | 31 |
| `availability_365` | 0.0% | 0.0% | 320 | 331 |
| `availability_60` | 0.0% | 0.0% | 61 | 61 |
| `availability_90` | 0.0% | 0.0% | 91 | 91 |
| `availability_eoy` | 0.0% | 0.0% | 110 | 113 |
| `bathrooms` | 43.2% | 49.8% | 10 | 10 |
| `bathrooms_text` | 1.9% | 0.0% | 18 | 19 |
| `bedrooms` | 16.6% | 4.0% | 10 | 9 |
| `beds` | 42.8% | 49.8% | 10 | 17 |
| `calculated_host_listings_count` | 0.0% | 0.0% | 26 | 11 |
| `calculated_host_listings_count_entire_homes` | 0.0% | 0.0% | 27 | 9 |
| `calculated_host_listings_count_private_rooms` | 0.0% | 0.0% | 11 | 9 |
| `calculated_host_listings_count_shared_rooms` | 0.0% | 0.0% | 2 | 2 |
| `calendar_last_scraped` | 0.0% | 0.0% | 5 | 1 |
| `calendar_updated` | 100.0% | 100.0% | 0 | 0 |
| `description` | 18.0% | 4.0% | 1622 | 1909 |
| `estimated_occupancy_l365d` | 0.0% | 0.0% | 70 | 79 |
| `estimated_revenue_l365d` | 42.5% | 49.8% | 674 | 703 |
| `first_review` | 12.0% | 1.2% | 1048 | 1070 |
| `has_availability` | 5.9% | 2.4% | 1 | 1 |
| `host_about` | 11.1% | 25.4% | 1473 | 1375 |
| `host_acceptance_rate` | 36.8% | 31.0% | 83 | 90 |
| `host_has_profile_pic` | 0.0% | 0.0% | 2 | 2 |
| `host_id` | 0.0% | 0.0% | 1695 | 1885 |
| `host_identity_verified` | 0.0% | 0.0% | 2 | 2 |
| `host_is_superhost` | 0.7% | 0.8% | 2 | 2 |
| `host_listings_count` | 0.0% | 0.0% | 30 | 17 |
| `host_location` | 4.8% | 1.8% | 121 | 51 |
| `host_name` | 0.1% | 0.0% | 1071 | 1238 |
| `host_neighbourhood` | 13.3% | 32.1% | 155 | 53 |
| `host_picture_url` | 0.0% | 0.0% | 1694 | 1885 |
| `host_response_rate` | 40.8% | 42.4% | 38 | 35 |
| `host_response_time` | 40.8% | 42.4% | 4 | 4 |
| `host_since` | 0.0% | 0.0% | 870 | 1226 |
| `host_thumbnail_url` | 0.0% | 0.0% | 1694 | 1885 |
| `host_total_listings_count` | 0.0% | 0.0% | 43 | 21 |
| `host_url` | 0.0% | 0.0% | 1695 | 1885 |
| `host_verifications` | 0.0% | 0.0% | 6 | 5 |
| `id` | 0.0% | 0.0% | 2000 | 2000 |
| `instant_bookable` | 0.0% | 0.0% | 2 | 2 |
| `last_review` | 12.0% | 1.2% | 894 | 771 |
| `last_scraped` | 0.0% | 0.0% | 5 | 1 |
| `latitude` | 0.0% | 0.0% | 1893 | 1709 |
| `license` | 100.0% | 0.1% | 0 | 1875 |
| `listing_url` | 0.0% | 0.0% | 2000 | 2000 |
| `longitude` | 0.0% | 0.0% | 1939 | 1850 |
| `maximum_maximum_nights` | 0.0% | 0.0% | 90 | 74 |
| `maximum_minimum_nights` | 0.0% | 0.0% | 46 | 34 |
| `maximum_nights` | 0.0% | 0.0% | 97 | 79 |
| `maximum_nights_avg_ntm` | 0.0% | 0.0% | 108 | 93 |
| `minimum_maximum_nights` | 0.0% | 0.0% | 91 | 73 |
| `minimum_minimum_nights` | 0.0% | 0.0% | 45 | 34 |
| `minimum_nights` | 0.0% | 0.0% | 44 | 38 |
| `minimum_nights_avg_ntm` | 0.0% | 0.0% | 145 | 91 |
| `name` | 0.0% | 0.0% | 1994 | 1991 |
| `neighborhood_overview` | 32.2% | 19.9% | 1302 | 1551 |
| `neighbourhood` | 32.2% | 19.9% | 1 | 26 |
| `neighbourhood_cleansed` | 0.0% | 0.0% | 33 | 22 |
| `neighbourhood_group_cleansed` | 100.0% | 100.0% | 0 | 0 |
| `number_of_reviews` | 0.0% | 0.0% | 360 | 460 |
| `number_of_reviews_l30d` | 0.0% | 0.0% | 9 | 12 |
| `number_of_reviews_ltm` | 0.0% | 0.0% | 73 | 100 |
| `number_of_reviews_ly` | 0.0% | 0.0% | 76 | 105 |
| `picture_url` | 0.0% | 0.0% | 2000 | 2000 |
| `price` | 42.5% | 49.8% | 305 | 373 |
| `property_type` | 0.0% | 0.0% | 35 | 42 |
| `review_scores_accuracy` | 12.2% | 1.2% | 93 | 75 |
| `review_scores_checkin` | 12.2% | 1.2% | 73 | 67 |
| `review_scores_cleanliness` | 12.2% | 1.3% | 122 | 109 |
| `review_scores_communication` | 12.2% | 1.2% | 74 | 58 |
| `review_scores_location` | 12.2% | 1.2% | 96 | 92 |
| `review_scores_rating` | 12.0% | 1.2% | 96 | 81 |
| `review_scores_value` | 12.2% | 1.2% | 98 | 98 |
| `reviews_per_month` | 12.0% | 1.2% | 283 | 401 |
| `room_type` | 0.0% | 0.0% | 4 | 4 |
| `scrape_id` | 0.0% | 0.0% | 1 | 1 |
| `source` | 0.0% | 0.0% | 2 | 2 |

---

## 5. Key observations

- **Schema is fully standardised.** Both London (snapshot 2025-09-14) and Amsterdam (snapshot 2025-09-11) expose the same 79 columns in `listings.csv.gz`.
- **Currency differs** (`GBP` vs `EUR`). Any cross-city price comparison requires FX conversion.
- The `price` column uses the `$X.XX` scraping format in both cities regardless of local currency — a known Inside Airbnb artefact (see D-015).
- Where null rates diverge, it reflects city-level data collection differences, not a schema bug.
- The pipeline's `src/cleaning/` modules are city-agnostic and can clean Amsterdam data without modification, aside from the `currency_code` override in `config/cities.yml`.