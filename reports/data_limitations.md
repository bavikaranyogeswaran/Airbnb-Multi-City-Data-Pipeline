# Data Limitations

City: **London** · Snapshot: **2025-09-14**

This document records the constraints of the source data — what it
cannot tell us no matter how carefully we engineer it. Every limitation
is grounded in numbers from earlier steps. The corresponding individual
assumptions are recorded in [`assumptions_log.md`](assumptions_log.md);
the field-level interpretations are in
[`special_fields.md`](special_fields.md).

---

## 1. Snapshot limitation

Inside Airbnb publishes scrapes, not a transaction log. The file we have
is one frame of a moving picture:

- We see **listings that existed and were visible to the scraper on 2025-09-14**. Delistings, paused listings, and listings the scraper missed are absent without trace.
- Host attributes (`host_response_rate`, `host_is_superhost`, etc.) are last-write-wins at scrape time. A host who lost superhost status the day before the scrape is recorded as non-superhost; the historical period during which they earned reviews under that status is lost.
- Calendar entries are forward-looking from the snapshot, not historical. We cannot reconstruct what availability looked like on 2024-09-14.
- Inside Airbnb's scrape cadence is irregular (every 1–3 months for most cities). Adjacent snapshots would let us measure churn; with a single snapshot we cannot.

**What this snapshot cannot answer.** Anything about how the market or any listing evolved before 2025-09-14, anything about which listings entered or exited the market, and anything about pricing dynamics on dates before the snapshot.

---

## 2. Availability ambiguity

The single most consequential limitation in the entire dataset, formalised as assumption A-002.

- The `calendar.available` field has two values: `t` (available) and `f` (unavailable). 60.3% of the 35.4M calendar rows are `f`.
- `f` can mean any of: booked, host-blocked, paused listing, minimum-stay rule excluded the date, listing capped at fewer days than the calendar window, or scraper saw an inconsistent state.
- Inside Airbnb's own [methodology page](https://insideairbnb.com/behind-the-data/) acknowledges this and uses the proxy `occupancy ≈ 1 - availability_rate × (1 - blocked_rate_estimate)`. We make a simpler, more honest choice: report **availability rate** directly and label any occupancy figure as an upper-bound proxy.

**What this snapshot cannot answer.** Anything about actual bookings. Anything about utilisation. Anything about demand at a per-date granularity. Any hypothesis that conditions on "booked" rather than "unavailable for any reason".

---

## 3. Revenue limitation

Even setting the availability ambiguity aside, revenue work in this
snapshot is structurally limited:

- **`calendar.price` and `calendar.adjusted_price` are 100% null** across all 35,357,974 rows (the central finding from Step 5). Per-date pricing is not available at all.
- The listing-level `price` field is itself 36% null. That removes 35,000+ listings from any price-based analysis.
- Inside Airbnb's pre-computed `estimated_revenue_l365d` is also 36% null (same listings as `price`) and inherits all of the booked-vs-blocked ambiguity above.
- For the 64% of listings with non-null price, the only revenue proxy we can compute is `listing_price × unavailable_day_count`. This multiplies a single snapshot-day price across 12 months at which the actual price could have varied by ±50% or more.

**What this snapshot cannot answer.** Total revenue per listing, per host, per neighbourhood, or per market with any defensible confidence. Hypothesis H5 from the brief (weekend vs weekday pricing) is impossible to test from calendar data.

**What we will say.** Revenue figures, where produced, are labelled "estimated revenue (upper-bound proxy)" with the methodology shown alongside.

---

## 4. Missingness (and its non-random structure)

Missingness in this snapshot is not random. It clusters around specific
cohorts:

| Field | Null % | Likely concentrated in |
|---|---|---|
| `license` | 100% | All listings (scraping or policy issue) |
| `calendar_updated` | 100% | All listings (deprecated field) |
| `neighbourhood_group_cleansed` | 100% | All listings (London has no sub-borough grouping) |
| `calendar.price` / `adjusted_price` | 100% | All calendar rows |
| `price` | 36% | Likely inactive, paused, or speculative listings |
| `estimated_revenue_l365d` | 36% | Same listings as `price` null |
| `host_neighbourhood` | 53% | Hosts who didn't fill in their profile |
| `host_response_rate` / `acceptance_rate` | ~30% | Hosts who received no messages in the rolling window |
| `bedrooms` | ~36% | Listings created after Airbnb made the field optional |
| `review_scores_*` | ~25% | The 24,122 listings with zero reviews |

Two of these are structural (review fields null for review-less listings,
bedrooms null where the field is optional). The rest are scraping or
policy artifacts.

**What this snapshot cannot answer.** Whether the listings missing `price` and `revenue` data are systematically different from those with prices — without knowing why they're missing, we can't tell. Until we examine the null cohort against neighbourhood and room-type distributions in Phase 2.1, any claim made on the non-null sample is provisional.

---

## 5. Scraping artifacts

The dataset reflects what a scraper saw, with all the messiness that
implies:

- **Currency symbol mismatch.** Prices are stored as text with a `$` prefix even though London is GBP-denominated. The currency is implicit in the city, not the field. Phase 2.2 hard-codes `currency_code = GBP` for London — this is correct, but a cross-city pipeline must do the same and *not* trust the `$`.
- **Stay-rule sentinels.** `maximum_nights = 2,147,483,647` (= 2³¹ − 1) appears in both listings and calendar files as a sentinel for "no maximum". Without explicit handling, mean and median statistics on stay rules are dominated by these sentinels.
- **Encoding stragglers.** `comments` text in reviews contains embedded newlines, smart quotes, emoji, and at least one CJK character set. UTF-8 throughout is required; cp1252 reading will fail.
- **Duplicate review templates.** 3.5% of review comments are exact-duplicate strings — generic "Great stay" / "Highly recommend" platform templates, or copy-pasted reviews. These survive raw row-count duplicate checks (they have unique `review.id`) but inflate any text-frequency signal.
- **Pandas auto-typing surprises.** Calendar `price` loads as `float64` despite being entirely null — pandas had no string evidence to force `object` dtype. Cross-checks on dtype alone are unreliable; null counts must be inspected.
- **Long-tail categorical mess.** `property_type` has 91 distinct values (Step 6), most appearing only a handful of times. Normalisation into a coarse bucket (`apartment / house / hotel / unique / other`) is mandatory before any modelling.

---

## 6. Geographic limitations

- **Coordinate precision.** Inside Airbnb deliberately rounds listing coordinates to obscure the exact address. The reported `(latitude, longitude)` is within ~150 m of the real location, not the real location itself.
- **Distance-based analysis is fuzzy by design.** Distance-from-landmark or proximity-based features will inherit ~150 m noise. This is acceptable for neighbourhood-level work and not acceptable for "nearest tube station" granularity.
- **Borough boundaries are the finest geography available.** London has 33 boroughs in this dataset. Sub-borough segmentation (e.g. Shoreditch, Notting Hill) is not available without external boundary data.
- **No `neighbourhood_group`.** `neighbourhood_group_cleansed` is null for all London rows. The dataset's two-level geography model degenerates to one level for London.
- **Geographic coverage is dense in inner boroughs and thin in outer boroughs.** This is real market structure, not a data defect, but cross-borough comparisons need population or housing-stock denominators to avoid misleading conclusions.
- **CRS is WGS 84 (EPSG:4326).** Distance calculations on raw degrees are wrong outside the equator; for area and distance work the GeoJSON must be reprojected to a London-appropriate projected CRS (e.g. EPSG:27700, OSGB36 British National Grid).

---

## 7. Implications for scope

These limitations rule out several questions that look reasonable at
first glance:

- ❌ Per-date dynamic pricing — calendar prices are null.
- ❌ Verified revenue per host — only a proxy is computable.
- ❌ Historical price trajectory — single snapshot.
- ❌ Listing churn (entries and exits) — single snapshot.
- ❌ Regulatory compliance analysis — licence field is 100% null.
- ❌ Sub-borough geography — only borough granularity is available.

And constrain how the following must be framed:

- ⚠️ Occupancy → reported as availability rate, with occupancy proxy as
  an explicit upper bound.
- ⚠️ Revenue → reported as estimated revenue with methodology stated.
- ⚠️ Price → restricted to the 64% with non-null price, with the null
  cohort profiled separately.
- ⚠️ Cross-listing comparisons → weighted by review count to avoid
  one-review noise.

What remains in scope (and where the assessment's best storytelling
lives):

- ✓ Supply structure — listings per borough, room-type mix, host
  concentration.
- ✓ Price distributions — by borough and room type, on the 64% sample.
- ✓ Review volume and seasonality — 15 years of review history is
  unusually rich.
- ✓ Spatial patterns — at borough granularity, supported by the GeoJSON.
- ✓ Host behaviour profiling — superhost vs casual, single-listing vs
  multi-listing.
- ✓ NLP on reviews — 2.1M review texts, mostly English, with clear
  thematic structure.
