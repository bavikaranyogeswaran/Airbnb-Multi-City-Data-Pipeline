# Assumptions Log

City: **London** · Snapshot: **2025-09-14**

Every non-trivial choice the downstream pipeline depends on is recorded
here as a numbered assumption. Each entry states what is assumed, the
evidence supporting it, the risk if the assumption is wrong, and where
in the project the assumption is acted on.

Statuses:
- **verified** — confirmed against the data in an earlier step
- **inherited** — accepted from Inside Airbnb's methodology, not independently verified
- **provisional** — adopted for now, to be revisited in Phase 2 with stronger evidence
- **superseded** — replaced by a later assumption (keep the row for traceability)

---

## Identity and integrity

### A-001 · `listings.id` uniquely identifies a listing within a snapshot
- **Reason:** Verified in Step 8 — `is_unique = True`, 96,871 unique ids over 96,871 rows, 0 nulls.
- **Risk:** May differ across source versions or other cities; the test must run per snapshot, not be assumed.
- **Acted on in:** Phase 2.4 `dim_listing` PK; Phase 2.6 pytest assertion.
- **Status:** verified.

### A-007 · `reviews.id` uniquely identifies a review
- **Reason:** Verified in Step 8 — `is_unique = True`, 2,097,996 unique ids.
- **Risk:** Same as A-001.
- **Acted on in:** Phase 2.4 `fact_reviews` PK.
- **Status:** verified.

### A-008 · `(calendar.listing_id, calendar.date)` is a unique composite key
- **Reason:** Verified in Step 8 — 0 duplicates across 35,357,974 rows.
- **Risk:** A future snapshot could violate this if a listing is scraped twice in one batch.
- **Acted on in:** Phase 2.4 `fact_calendar` composite PK.
- **Status:** verified.

### A-009 · `neighbourhoods.csv.neighbourhood` is the canonical neighbourhood key
- **Reason:** Verified in Step 8 — PK unique, matches every distinct `listings.neighbourhood_cleansed`, and matches GeoJSON properties name-for-name (33 = 33).
- **Risk:** A future snapshot could introduce a borough rename or a missing geometry.
- **Acted on in:** Phase 2.4 `dim_neighbourhood` PK.
- **Status:** verified.

---

## Availability and occupancy

### A-002 · `calendar.available = "f"` means unavailable, not booked
- **Reason:** Source semantics are ambiguous (Inside Airbnb's [behind-the-data page](https://insideairbnb.com/behind-the-data/) acknowledges this).
- **Risk:** Any occupancy figure derived from this is an upper bound that overstates actual bookings, especially for higher-end listings whose hosts block frequently.
- **Acted on in:** Phase 2.3 `occupancy_proxy = 1 - availability_rate` is labelled "proxy" everywhere; Phase 2.4 `fact_calendar.available` is kept raw, never renamed to `is_booked`.
- **Status:** inherited.

### A-003 · `availability_30`, `_60`, `_90`, `_365` are correct as published
- **Reason:** They are nested aggregates over the same calendar; recomputing them in Phase 2.3 from `fact_calendar` will cross-check.
- **Risk:** Inside Airbnb's published values can lag the calendar by a day if the two files were scraped at different moments.
- **Acted on in:** Phase 2.3 sanity check; trust the recomputed value where they disagree.
- **Status:** provisional — confirm against Phase 2.3 cross-check.

### A-004 · `availability_365 = 0` means "fully unavailable for any reason", not "fully booked"
- **Reason:** Direct corollary of A-002.
- **Risk:** Stakeholders may interpret it as "fully booked" — must be called out in the report.
- **Acted on in:** Final report glossary; metric labels in the dashboard.
- **Status:** inherited.

---

## Pricing and revenue

### A-005 · `calendar.price` and `calendar.adjusted_price` are 100% null in this snapshot
- **Reason:** Verified in Step 5 — `100.00%` null across all 35,357,974 calendar rows; confirmed in Step 6 schema profile.
- **Risk:** Per-date pricing analysis (weekend lift, seasonality, dynamic pricing) is impossible. Hypothesis H5 in the assessment brief is unanswerable from this snapshot.
- **Acted on in:** Phase 2.2 drops both columns from the clean layer; Phase 2.3 falls back to listing-level `price`.
- **Status:** verified.

### A-010 · Listing prices are in GBP per night, excluding cleaning and service fees
- **Reason:** London is GBP-denominated. The `$` symbol stored in the file is a scraping artefact and does not indicate currency. Cleaning fees, service fees, and taxes are not exposed by Airbnb to Inside Airbnb's scraper.
- **Risk:** Any cross-city price comparison must FX-convert; any "total cost of stay" claim is wrong because fees are missing.
- **Acted on in:** Phase 2.2 hard-codes `currency_code = GBP` for London; Phase 2.4 `dim_city.currency_code` carries it.
- **Status:** inherited.

### A-011 · The listing-level `price` field represents a snapshot-day price
- **Reason:** It is one value per listing, not a time series; Airbnb prices are dynamic.
- **Risk:** Multiplying this price by 365 to estimate annual revenue is wrong; the proxy is an upper bound that ignores seasonality and host repricing.
- **Acted on in:** Phase 2.3 revenue figures are labelled "estimated revenue (upper-bound proxy)" and computed only on the non-null cohort.
- **Status:** inherited.

### A-012 · Listings with null `price` are excluded from price-based analyses, not imputed
- **Reason:** 36% null is too large a fraction to impute defensibly without knowing why prices are missing.
- **Risk:** The non-null cohort may not be representative — the null cohort needs a separate profile in Phase 2.1 to test this.
- **Acted on in:** Phase 2.2 keeps NULL explicit; Phase 2.3 reports compute on the non-null sample with the sample size called out.
- **Status:** provisional — revisit after Phase 2.1 null-cohort profiling.

### A-013 · Inside Airbnb's `estimated_revenue_l365d` and `estimated_occupancy_l365d` are kept for reference but not trusted
- **Reason:** They inherit A-002 (blocked-vs-booked) and A-011 (single-price assumption).
- **Risk:** None directly; using them as ground truth would inherit those risks.
- **Acted on in:** Phase 2.3 recomputes both proxies from raw calendar; the IA values are retained for cross-check in the final report.
- **Status:** inherited.

---

## Missingness

### A-014 · Missing `bedrooms` is left null, not imputed
- **Reason:** Imputation would invent data; the field became optional on the platform at some point, so missingness mixes "studio" with "host omitted it".
- **Risk:** `price_per_bedroom` and bedroom-conditioned models lose ~36% of rows.
- **Acted on in:** Phase 2.2 cleaning leaves NULL; Phase 2.3 derived fields handle NULL safely.
- **Status:** inherited.

### A-015 · The 24,122 listings with no reviews legitimately have null `review_scores_*`
- **Reason:** Verified in Step 8 — reviews has 72,749 distinct `listing_id` vs 96,871 listings; the 24,122 difference matches the review_scores null cohort.
- **Risk:** Modelling on review scores excludes these listings — they're the cohort most in need of scoring.
- **Acted on in:** Phase 2.3 keeps a `has_reviews` indicator alongside the scores.
- **Status:** verified.

### A-016 · `license` is 100% null in this snapshot; regulatory analysis is out of scope
- **Reason:** Verified in Step 6 schema profile.
- **Risk:** None for this assessment; future snapshots may populate the field and unlock compliance work.
- **Acted on in:** Phase 2.2 drops the column; final report does not claim anything about licensing.
- **Status:** verified.

### A-017 · `host_response_rate` / `host_acceptance_rate` nulls mean "no signal", not "0%"
- **Reason:** The field is null when the host received zero messages or requests in Airbnb's rolling window, per IA's data dictionary.
- **Risk:** Treating null as 0 would systematically penalise low-volume hosts.
- **Acted on in:** Phase 2.2 keeps NULL; modelling features ship with a `host_response_rate_known` indicator.
- **Status:** inherited.

---

## Schema and category handling

### A-018 · `maximum_nights >= 2^30` is a sentinel ("no maximum") and is mapped to NULL
- **Reason:** Verified in Step 6 — `maximum_nights` max value is 2,147,483,647 = 2^31 − 1 (INT_MAX). This is a classic sentinel pattern, not a real stay limit.
- **Risk:** Without this cleaning step, mean and median statistics on stay rules are meaningless (mean would be ~2 billion).
- **Acted on in:** Phase 2.2 `cap_sentinel_intmax` cleaner.
- **Status:** verified.

### A-019 · `minimum_nights >= 365` is a host's "do not book" signal, not a real minimum
- **Reason:** Verified in Step 6 — `minimum_nights` max is 1,125 (≈3 years). No real guest would book a 3-year minimum stay.
- **Risk:** Treating this listing as bookable inflates the active-supply count.
- **Acted on in:** Phase 2.3 derives `is_de_facto_inactive = minimum_nights >= 365` as a supply-side flag.
- **Status:** verified.

### A-020 · `room_type` is normalised to 4 canonical buckets
- **Reason:** Source has 4 distinct values (Step 6). Mapping to `{entire_home, private_room, shared_room, hotel_room}` is a lower-case-and-snake-case operation.
- **Risk:** None — the mapping is exhaustive for this snapshot.
- **Acted on in:** Phase 2.2 `normalize_category` for `room_type` using `ROOM_TYPE_MAP`.
- **Status:** verified.

### A-021 · `property_type` is coarsened to a 5-bucket dimension while preserving the raw value
- **Reason:** 91 distinct values (Step 6), long-tail distribution makes per-type analysis noisy.
- **Risk:** Coarsening hides genre-specific signals (e.g. houseboats); we keep `property_type_raw` to allow drill-down.
- **Acted on in:** Phase 2.2 derives `property_type_bucket ∈ {apartment, house, hotel, unique, other}`.
- **Status:** provisional — bucket boundaries finalised in Phase 2.2.

### A-022 · `bathrooms_text` is canonical; the numeric `bathrooms` field is derived from it
- **Reason:** `bathrooms_text` preserves the private-vs-shared distinction; `bathrooms` does not.
- **Risk:** Parsing the text introduces possible regex failures — these surface as NULL with an error flag.
- **Acted on in:** Phase 2.2 `parse_bathrooms_text` yields `(bathroom_count, bathroom_is_shared)`; the numeric `bathrooms` column is dropped after derivation.
- **Status:** provisional — parsing validated in Phase 2.2.

### A-023 · `neighbourhood_cleansed` is the canonical neighbourhood key; raw `neighbourhood` is dropped
- **Reason:** Verified in Step 8 — `neighbourhood_cleansed` matches the borough CSV exactly; raw `neighbourhood` is 57% null and inconsistent.
- **Risk:** Cross-city pipelines must check both — some cities populate one and not the other.
- **Acted on in:** Phase 2.4 `dim_listing.neighbourhood_key` joins via `neighbourhood_cleansed`.
- **Status:** verified.

### A-024 · `calculated_host_listings_count` is the canonical host portfolio size for the city
- **Reason:** `host_listings_count` is host-reported and can be stale; `host_total_listings_count` is global across cities; only `calculated_host_listings_count` reflects this city's active inventory.
- **Risk:** Treating a host with 30 listings worldwide and 2 in London as a "professional London operator" is wrong without the city-scoped count.
- **Acted on in:** Phase 2.3 derives `is_professional_host = calculated_host_listings_count >= 5`.
- **Status:** verified.

---

## Identity over time

### A-025 · `host_is_superhost` is interpreted as current status, not historical status
- **Reason:** Superhost programme membership is re-evaluated quarterly; the snapshot captures a single point in that cycle.
- **Risk:** Hypotheses comparing review scores by superhost status (H2 in the brief) must acknowledge that the programme rewards already-high scores — causality is ambiguous.
- **Acted on in:** Statistical analyses note the directionality; conclusions phrased as "associated with" not "caused by".
- **Status:** inherited.

### A-026 · A single snapshot supports no longitudinal claims about the market
- **Reason:** Inherent to having one file.
- **Risk:** Stakeholders may misread cross-sectional findings as trends.
- **Acted on in:** Final report uses "as of 2025-09-14" framing throughout.
- **Status:** inherited.

---

## Geography

### A-027 · Listing coordinates are rounded to ~150 m by Inside Airbnb
- **Reason:** Documented in Inside Airbnb's privacy methodology.
- **Risk:** Distance-from-landmark features inherit ~150 m noise — acceptable for neighbourhood-level work, not for "nearest tube" precision.
- **Acted on in:** Phase 2.3 distance features are bucketed at ≥ 200 m or omitted.
- **Status:** inherited.

### A-028 · London has no `neighbourhood_group`; cross-city pipelines must permit null
- **Reason:** Verified in Step 6 — 100% null in this snapshot.
- **Risk:** A schema check requiring `neighbourhood_group` non-null would break the pipeline for London.
- **Acted on in:** Phase 2.4 `dim_neighbourhood.neighbourhood_group` is nullable; validation tests accept NULL.
- **Status:** verified.

### A-029 · Geometric calculations use EPSG:27700 (British National Grid) for projected operations
- **Reason:** Distance and area calculations on WGS 84 degrees produce wrong numbers; London is at ~51° N where the longitude-degree distortion is ~37%.
- **Risk:** Using the raw GeoJSON coordinates for `density = listings / area` would distort area by the cosine of latitude.
- **Acted on in:** Phase 2.3 neighbourhood density reprojects to EPSG:27700 before computing area.
- **Status:** provisional — verified in Phase 2.3 GeoPandas test.

---

## Duplicate handling

### A-030 · The 3.5% duplicate review comments are flagged but not deleted
- **Reason:** Verified in Step 6 — 73,740 reviews share text with another review. Distinct `review.id` and `listing_id`s, so they are legitimate rows by source schema; the duplication is in the content layer (templates, copy-paste).
- **Risk:** Text-based NLP metrics (frequency, sentiment averages) double-count templates.
- **Acted on in:** Phase 2.1 fuzzy-duplicate detection flags `comment_is_duplicate`; Phase 7 NLP work deduplicates the corpus before topic modelling.
- **Status:** verified.

---

## Quick reference index

| ID | Topic | Status |
|---|---|---|
| A-001 | Listings PK uniqueness | verified |
| A-002 | Calendar `f` ≠ booked | inherited |
| A-003 | Availability windows trust | provisional |
| A-004 | `availability_365 = 0` interpretation | inherited |
| A-005 | Calendar prices 100% null | verified |
| A-006 | (reserved) | — |
| A-007 | Reviews PK uniqueness | verified |
| A-008 | Calendar composite PK uniqueness | verified |
| A-009 | Neighbourhoods PK uniqueness | verified |
| A-010 | Prices in GBP, fees excluded | inherited |
| A-011 | Single-price-per-listing snapshot | inherited |
| A-012 | Null prices not imputed | provisional |
| A-013 | IA pre-derived occupancy/revenue not trusted | inherited |
| A-014 | Missing bedrooms not imputed | inherited |
| A-015 | 24,122 review-less listings | verified |
| A-016 | License 100% null | verified |
| A-017 | Response/acceptance nulls = no signal | inherited |
| A-018 | maximum_nights INT_MAX sentinel | verified |
| A-019 | minimum_nights ≥ 365 sentinel | verified |
| A-020 | room_type 4-bucket normalisation | verified |
| A-021 | property_type 5-bucket coarsening | provisional |
| A-022 | bathrooms_text canonical | provisional |
| A-023 | neighbourhood_cleansed canonical | verified |
| A-024 | calculated_host_listings_count canonical | verified |
| A-025 | Superhost current-status only | inherited |
| A-026 | No longitudinal claims from one snapshot | inherited |
| A-027 | Coordinates rounded to ~150 m | inherited |
| A-028 | London has no neighbourhood_group | verified |
| A-029 | EPSG:27700 for projected geometry | provisional |
| A-030 | Duplicate review texts flagged, not deleted | verified |
