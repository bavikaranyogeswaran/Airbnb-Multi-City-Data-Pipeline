# Fields Requiring Special Interpretation

City: **London** · Snapshot: **2025-09-14**

This file lists every column whose surface meaning is misleading or
incomplete. For each one we record what the field looks like, what it
actually means, what we will assume, and how that assumption flows into
downstream metrics. The assumptions listed here are the basis for
[`assumptions_log.md`](assumptions_log.md) (Step 12).

---

## 1. `calendar.available`

**Surface meaning.** Whether the listing is available on that date (`t` = available, `f` = unavailable).

**Real ambiguity.** `f` means *not bookable at the moment of the scrape*. It does **not** confirm a booking. It could mean any of:
- The host blocked the date manually (off-platform stay, personal use, maintenance).
- A minimum-stay rule applied to that date excludes a guest selecting it.
- The listing was paused.
- The date was outside the host's allowed booking window.

**Our interpretation.** Treat `f` as "unavailable for any reason". Compute an `occupancy_proxy = 1 - availability_rate` and label it explicitly as a proxy, never as actual occupancy.

**Impact.** Every revenue, occupancy, and demand metric derived from `available` is a proxy. Stakeholders must be told this explicitly in the report. Numbers will overstate actual bookings whenever hosts use blocking heavily — common in higher-end inventory.

---

## 2. `calendar.price` and `calendar.adjusted_price`

**Surface meaning.** Host's posted nightly price for that date, optionally adjusted by Inside Airbnb.

**Real ambiguity.** Both columns are **100% null in this snapshot** ([`01_dataset_familiarization.ipynb`](../notebooks/01_dataset_familiarization.ipynb) finding). Inside Airbnb stopped publishing per-date calendar prices for London at some point before 2025-09-14.

**Our interpretation.** Treat the calendar as availability-only data. Use the listing-level `price` for any pricing analysis. Where revenue is required, fall back to listing `price` × unavailable-day count, with the explicit caveat that this multiplies a snapshot price across days at which the actual price could have varied considerably.

**Impact.** All seasonal price analysis (weekend vs weekday, holiday lift, dynamic pricing) is impossible from this snapshot. Hypothesis H5 from the assessment brief (weekend vs weekday pricing) cannot be tested as originally framed.

---

## 3. `listings.price`

**Surface meaning.** Nightly price.

**Real ambiguity.**
- 36% null in this snapshot — even the listing-level pricing source of truth is partial.
- Stored as text (`$70.00` format) — needs currency strip and numeric cast.
- One value per listing, but Airbnb prices are dynamic — this is a single observation at scrape time, not a representative figure.
- Currency is implicit. For London the assumption is GBP, but the symbol shown in the file is `$` (a scraping artefact). Cross-city pipelines must use the city's currency, not the file symbol.

**Our interpretation.** After cleaning, treat `price` as GBP per night at the snapshot moment, with a 36% null cohort excluded from price-based analyses (not imputed). Document the null cohort's characteristics separately to check whether nulls are concentrated in any neighbourhood or room type.

**Impact.** Median/mean price by neighbourhood is computed on a 64% sample. Any model trained on price must either drop those rows or use a missingness indicator.

---

## 4. `listings.adjusted_price` (when present in other cities)

Not present in London 2025-09-14 listings file. Present in calendar (null). Flagged here only as a reminder that cross-city pipelines must check whether this column exists per file before referencing it.

---

## 5. `listings.availability_30` / `60` / `90` / `365`

**Surface meaning.** Days available in the next 30/60/90/365 days from the snapshot.

**Real ambiguity.** Carries the same "blocked ≠ booked" problem as `calendar.available`. Also, the four windows are not independent — they nest — so they cannot be combined as features without inflating signal.

**Our interpretation.** Use `availability_365` as the primary supply metric. Use the shorter windows only for short-horizon liquidity questions. Cross-check against a fresh recomputation from `calendar.csv.gz` rows in Phase 2.3 (the listing-level field may lag the calendar in some snapshots).

**Impact.** Listings with `availability_365 = 0` are sometimes interpreted as "fully booked" — wrong; they are "fully unavailable for whatever reason". Listings with `availability_365 = 365` are usually paused or speculative listings, not necessarily empty inventory.

---

## 6. `listings.has_availability`

**Surface meaning.** Whether the listing has any availability.

**Real ambiguity.** Boolean derived from the calendar; in this snapshot a listing with `availability_365 > 0` should have `has_availability = t`, but Inside Airbnb's derivation rule can produce edge cases (e.g. all-blocked but technically active).

**Our interpretation.** Trust `has_availability = f` as "no calendar capacity, treat as effectively inactive supply". Treat `t` as "has any future bookable date" — not a quality signal.

**Impact.** When ranking active vs dormant inventory, use this flag rather than recomputing.

---

## 7. `listings.minimum_nights`, `maximum_nights`, and their six derivatives

**Surface meaning.** Stay-rule constraints. The two base fields are the listing-default rules; the six derivatives (`*_minimum_*`, `*_maximum_*`) summarise how those rules vary across the next-365-day calendar.

**Real ambiguity.**
- `maximum_nights` frequently contains the sentinel value `2,147,483,647` (`2^31 − 1`, INT_MAX) meaning "no maximum". Treating it as an integer max corrupts statistics.
- `minimum_nights` of 365 or 1,125 is a host's hack to make a listing nominally active without accepting bookings — effectively a "do not book" signal.

**Our interpretation.** Replace `maximum_nights >= 2^30` with NULL (Phase 2.2 `cap_sentinel_intmax`). Keep `minimum_nights` raw but compute a derived `is_de_facto_inactive = minimum_nights >= 365` flag for analysis.

**Impact.** Without sentinel handling, the average max-nights statistic in London is ~2.1 billion — obviously useless. With sentinel handling, it becomes interpretable.

---

## 8. `listings.license`

**Surface meaning.** Short-term rental licence number.

**Real ambiguity.** **100% null in this snapshot.** London's STR licensing data is not reaching Inside Airbnb for this period.

**Our interpretation.** Drop the column from the clean layer. Regulatory analysis is out of scope for this snapshot. Document the absence in [`data_limitations.md`](data_limitations.md) so a reader doesn't expect compliance findings.

**Impact.** None of the assessment's regulatory/legal questions can be answered for London 2025-09-14.

---

## 9. `listings.instant_bookable`

**Surface meaning.** Whether guests can book the listing without manual host approval.

**Real ambiguity.** Encoded as `t`/`f` text. A pause or block can co-exist with `instant_bookable = t` — the field describes the booking flow, not current availability.

**Our interpretation.** Standard boolean parse. Use as a behavioural feature (host's willingness to delegate approval) — not as an availability signal.

---

## 10. `listings.host_is_superhost`

**Surface meaning.** Superhost programme membership.

**Real ambiguity.**
- **Point-in-time, not historical.** A listing's superhost status as of 2025-09-14 says nothing about whether it was superhost when reviews were earned.
- Superhost is re-evaluated quarterly; the snapshot catches whichever phase of that cycle the host was in.

**Our interpretation.** Standard boolean parse. When comparing review scores by superhost status, frame as "current superhost status" — do not imply causality from past reviews to current status.

**Impact.** Hypothesis H2 in the assessment brief (superhosts achieve higher review scores) needs careful framing — the direction of causality is mixed because the programme rewards already-high scores.

---

## 11. `listings.host_response_rate` and `listings.host_acceptance_rate`

**Surface meaning.** Fractions of incoming guest messages / booking requests that the host responds to / accepts.

**Real ambiguity.**
- Stored as text with `%` suffix (`"88%"`).
- Computed over a rolling window Airbnb doesn't disclose to Inside Airbnb — could be 30 days, 90 days, etc.
- Null for hosts who received zero messages / requests in the window — meaning "no signal", not "0%".

**Our interpretation.** Strip `%`, divide by 100, store as 0.0–1.0 float. Treat NULL as missing-not-zero. For modelling, a `host_response_rate_is_known` indicator should accompany the numeric column.

---

## 12. `listings.review_scores_rating`

**Surface meaning.** Aggregate review score 0–5.

**Real ambiguity.**
- Null for the 24,122 listings with zero reviews (Step 6 finding).
- Inflated baseline — Airbnb's average review score is ~4.7. Below-4 is a strong negative signal; above-4.8 is the norm.

**Our interpretation.** Keep nulls explicit. When computing borough-level rating averages, weight by review count (otherwise newer listings with one 5-star review distort the picture).

**Impact.** Naive averaging treats a 1-review listing and a 200-review listing identically — wrong.

---

## 13. `listings.reviews_per_month`

**Surface meaning.** Inside Airbnb's derived review velocity.

**Real ambiguity.** Computed by Inside Airbnb, not Airbnb. The denominator (months since first review) is sensitive to the snapshot date and doesn't penalise long inactive gaps. A listing with one review in 2010 and one in 2025 has the same denominator-effective tenure as one with reviews every month.

**Our interpretation.** Don't trust this field. Recompute in Phase 2.3 as `reviews_in_last_12_months / 12` for a more useful demand proxy.

---

## 14. `listings.estimated_occupancy_l365d` and `listings.estimated_revenue_l365d`

**Surface meaning.** Inside Airbnb's own estimates of nights occupied and revenue in the last 365 days.

**Real ambiguity.** Use the same blocked-vs-booked assumption as `calendar.available`. These are proxies built on a proxy. In particular, `estimated_revenue_l365d` assumes the current listing price applied across the full year — but prices change.

**Our interpretation.** Keep for reference and reporting, but compute our own occupancy and revenue proxies in Phase 2.3 from raw calendar data so methodology is transparent.

**Impact.** Where IA's estimate disagrees with ours by more than a threshold, surface it — diverging estimates are an interesting finding in themselves.

---

## 15. The three host listings counts

`listings.host_listings_count`, `listings.host_total_listings_count`, and `listings.calculated_host_listings_count` look near-identical but mean different things.

**Surface meaning.** Number of listings managed by this host.

**Real ambiguity.**
- `host_listings_count` — what the host self-reports on their profile. Can be stale, can include inactive listings.
- `host_total_listings_count` — Airbnb's platform-counted total across all geographies.
- `calculated_host_listings_count` — Inside Airbnb's count *for this city only*, computed by counting rows.

**Our interpretation.** Use `calculated_host_listings_count` for any analysis scoped to London. Use the others only for cross-checking and to derive `is_multi_city_host = host_total_listings_count > calculated_host_listings_count`.

**Impact.** A host with 30 listings worldwide and 2 in London should not be classified as a "professional London operator" — only the calculated count avoids this confusion.

---

## 16. `listings.bedrooms` vs `listings.beds`

**Surface meaning.** Bedroom count and bed count.

**Real ambiguity.**
- Bedrooms = rooms designed for sleeping; beds = total beds (including sofa beds).
- `bedrooms` is null for ~36% of listings — Airbnb made it optional at some point.
- Studios should have `bedrooms = 0` but sometimes have `bedrooms = 1`.

**Our interpretation.** Keep both nullable; do not impute bedrooms. Use `accommodates` as the most reliable capacity field. Derive `price_per_bedroom` only on the 64% with non-null bedrooms ≥ 1.

---

## 17. `listings.bathrooms` and `listings.bathrooms_text`

**Surface meaning.** Bathroom count.

**Real ambiguity.** `bathrooms` is numeric but loses the **private vs shared** distinction encoded in `bathrooms_text` (e.g. `"1.5 shared baths"` collapses to `1.5`).

**Our interpretation.** Parse `bathrooms_text` to extract both the numeric count and a `bathroom_is_shared` flag. Drop the numeric `bathrooms` column once parsed — it's redundant and lossy.

---

## 18. `listings.neighbourhood` vs `listings.neighbourhood_cleansed`

**Surface meaning.** Both name the listing's neighbourhood.

**Real ambiguity.** `neighbourhood` is the host-entered free-text version — 57% null, often inconsistent capitalisation, sometimes off-by-one (host claims a neighbouring borough). `neighbourhood_cleansed` is Inside Airbnb's spatial-join result against the borough GeoJSON.

**Our interpretation.** Use `neighbourhood_cleansed` as the canonical join key. Drop the raw `neighbourhood` from the analytical model after profiling it. Note in the report when the two disagree — it's an interesting hosts-vs-geography signal.

---

## 19. `listings.last_scraped` and `listings.calendar_last_scraped`

**Surface meaning.** Dates indicating when the listing row and its calendar were scraped.

**Real ambiguity.** Usually within a day of each other but not always identical — the calendar can be scraped a day after the listing or vice versa. For most analyses both are ~`snapshot_date`, but consistency cannot be assumed.

**Our interpretation.** Parse both as dates. Use `snapshot_date` from `config/cities.yml` as the authoritative anchor for derived features (e.g. host tenure); use the scrape fields only when freshness matters at sub-day granularity (rare).

---

## Cross-cutting note

All of the above lead to one principle: **prefer derived columns that we compute ourselves over Inside Airbnb's pre-derived columns** wherever the derivation is transparent and cheap. The pre-derived fields are convenient but encode assumptions we want to make ourselves.
