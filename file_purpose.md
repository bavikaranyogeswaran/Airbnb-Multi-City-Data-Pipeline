# File Purpose

City: **London** · Snapshot: **2025-09-14** · Source: [Inside Airbnb](https://insideairbnb.com/get-the-data/)

This document records what one row of each raw file represents, the
candidate primary key, foreign-key links, and any non-obvious behaviour
worth flagging before profiling. Column counts and row counts are taken
from [`dataset_inventory.csv`](dataset_inventory.csv).

---

## 1. `listings.csv.gz` — Listings (detailed)

- **Rows:** 96,871 · **Columns:** 79
- **Grain:** one row per Airbnb listing as observed at the snapshot date (`last_scraped` field).
- **Candidate primary key:** `id`. Uniqueness will be tested in Step 8.
- **Foreign keys:** `host_id` → host (no separate host table; hosts are denormalised here), `neighbourhood_cleansed` → `neighbourhoods.neighbourhood`.
- **Columns are grouped into logical clusters:**
  - Identity / scrape: `id`, `listing_url`, `scrape_id`, `last_scraped`, `source`
  - Marketing copy: `name`, `description`, `neighborhood_overview`, `picture_url`
  - Host attributes (denormalised): `host_id`, `host_url`, `host_name`, `host_since`, `host_location`, `host_response_time`, `host_response_rate`, `host_acceptance_rate`, `host_is_superhost`, `host_listings_count`, `host_total_listings_count`, `host_verifications`, `host_identity_verified`
  - Geography: `neighbourhood`, `neighbourhood_cleansed`, `neighbourhood_group_cleansed`, `latitude`, `longitude`
  - Physical: `property_type`, `room_type`, `accommodates`, `bathrooms`, `bathrooms_text`, `bedrooms`, `beds`, `amenities`
  - Pricing / stay rules: `price`, `minimum_nights`, `maximum_nights`, plus six `*_minimum_*` / `*_maximum_*` derivatives
  - Forward-looking availability: `has_availability`, `availability_30/60/90/365`, `availability_eoy`, `calendar_last_scraped`
  - Backward-looking activity: `number_of_reviews`, `number_of_reviews_ltm`, `number_of_reviews_l30d`, `number_of_reviews_ly`, `estimated_occupancy_l365d`, `estimated_revenue_l365d`, `first_review`, `last_review`, `reviews_per_month`
  - Review scores: `review_scores_rating` plus six sub-scores
  - Regulatory: `license`, `instant_bookable`
  - Pre-computed host portfolio: `calculated_host_listings_count` and three room-type splits

> ⚠️ Several fields are Inside Airbnb's own derivatives, not raw platform data. In particular `estimated_occupancy_l365d`, `estimated_revenue_l365d`, and `reviews_per_month` are pre-computed and rest on the same blocked-vs-booked ambiguity called out in [`data_limitations.md`](#) (to be written in Step 11). We will recompute our own occupancy and revenue proxies in Phase 2.3 rather than trust these.

---

## 2. `listings.csv` — Listings (visualisations / summary)

- **Rows:** 96,871 · **Columns:** 18
- **Grain:** same as the detailed file — one row per listing at the snapshot date.
- **Candidate primary key:** `id`.
- **Relationship to the detailed file:** same row count, same `id`. Inside Airbnb publishes this file as a slimmed-down map-ready subset.
- **Schema drift worth noting:** column names differ from the detailed file.
  - `neighbourhood_group` (here) ↔ `neighbourhood_group_cleansed` (detailed)
  - `neighbourhood` (here) ↔ `neighbourhood_cleansed` (detailed)
  - `last_review` and `number_of_reviews` are present, but the lifetime/30d/yearly review breakouts are not.
- **Decision:** the detailed file is the source of truth for Phase 2. The summary file is kept only for cross-checking row counts and `id` parity.

---

## 3. `calendar.csv.gz` — Calendar

- **Rows:** 35,357,974 · **Columns:** 7
- **Grain:** one row per `(listing_id, date)` for ~365 days forward of the snapshot. Calendar = 96,871 listings × ~365 days = 35.36M, which matches almost exactly.
- **Candidate composite primary key:** `(listing_id, date)`. Uniqueness will be tested in Step 8.
- **Foreign key:** `listing_id` → `listings.id`.
- **Columns:**
  - `listing_id`, `date`
  - `available` — single-character `t` or `f`. **Critical interpretation:** `f` means the date is not bookable on the snapshot day; it does *not* confirm a booking. The host may have blocked it, paused the listing, or set a minimum-stay rule that excludes that date. This is the single most important caveat in the entire dataset and is the basis of assumption A-002.
  - `price` — host's posted nightly price for that date (string with currency symbol).
  - `adjusted_price` — Inside Airbnb's clean-up of `price`. Frequently identical; sometimes different when the source had formatting issues.
  - `minimum_nights`, `maximum_nights` — stay rules for that specific date, which can differ from the listing-level defaults.

---

## 4. `reviews.csv.gz` — Reviews (detailed)

- **Rows:** 2,097,996 · **Columns:** 6
- **Grain:** one row per guest review.
- **Candidate primary key:** `id`.
- **Foreign key:** `listing_id` → `listings.id`. Orphan reviews (listing no longer in the snapshot) are expected and must be counted in Step 8.
- **Columns:** `listing_id`, `id`, `date`, `reviewer_id`, `reviewer_name`, `comments`.
- **Multi-line text:** `comments` contains embedded newlines and unescaped quotes in some rows. A naive line-count of the file does not equal the row count. All row counting must go through a real CSV parser.
- **Usage:** review activity timeline (for demand proxies), NLP source (Section 7 of the brief).

---

## 5. `reviews.csv` — Reviews (visualisations / summary)

- **Rows:** 2,097,996 · **Columns:** 2
- **Grain:** same as the detailed file — one row per review.
- **Columns:** `listing_id`, `date`.
- **Purpose:** lightweight review activity stream without the comment text. Useful for quick time-series cross-checks against the detailed file.
- **Decision:** detailed reviews are the source of truth. The summary file is used only to verify the review count parity.

---

## 6. `neighbourhoods.csv` — Neighbourhood reference

- **Rows:** 33 · **Columns:** 2
- **Grain:** one row per administrative neighbourhood (= London borough in this snapshot).
- **Candidate primary key:** `neighbourhood`.
- **Columns:** `neighbourhood_group`, `neighbourhood`.
- **London-specific observation:** `neighbourhood_group` is **null for all 33 rows**. London does not use a sub-borough grouping in Inside Airbnb's schema — the 33 entries are the boroughs themselves. Cross-city pipelines must allow `neighbourhood_group` to be null without treating it as an error.
- **Joins to:** `listings.neighbourhood_cleansed`.

---

## 7. `neighbourhoods.geojson` — Neighbourhood boundaries

- **Features:** 33 · **Geometry type:** MultiPolygon
- **Grain:** one feature per neighbourhood, matching the CSV.
- **Properties:** `neighbourhood`, `neighbourhood_group` (null in London, as above).
- **CRS:** WGS 84 (EPSG:4326), latitude/longitude in degrees — to be verified when loading with GeoPandas in Phase 2.
- **Usage:** spatial joins (point-in-polygon for listings whose `neighbourhood_cleansed` is missing or ambiguous), choropleth mapping, neighbourhood-area calculation for listing density.

---

## Relationship summary

```
listings.csv.gz  (id, host_id, neighbourhood_cleansed)
   ├── calendar.csv.gz       (listing_id, date)              one-to-many (~365 per listing)
   ├── reviews.csv.gz        (listing_id, id)                one-to-many
   └── neighbourhoods.csv    (neighbourhood)                 many-to-one

neighbourhoods.csv  ←→  neighbourhoods.geojson               one-to-one on `neighbourhood`

listings.csv (summary)  ←→  listings.csv.gz (detailed)       one-to-one on `id`
reviews.csv  (summary)  ←→  reviews.csv.gz  (detailed)       one-to-one on (listing_id, date) tuples (verify in Step 8)
```

Host is *not* a separate file. Host attributes live denormalised inside `listings.csv.gz`. A `dim_host` will be derived in Phase 2.4 by extracting distinct `host_id` rows.
