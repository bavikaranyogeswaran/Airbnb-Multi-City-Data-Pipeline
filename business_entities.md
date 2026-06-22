# Business Entities

City: **London** · Snapshot: **2025-09-14**

This document defines the business entities the Inside Airbnb dataset
represents, where each entity lives in the source files, the cardinality
observed in this snapshot, and the kinds of questions a stakeholder
asks about each one. Counts are sourced from [`dataset_inventory.csv`](dataset_inventory.csv)
and [`key_integrity.md`](key_integrity.md).

## Quick reference

| Entity | Identifier | Source | Count (London 2025-09-14) |
|---|---|---|---|
| Listing | `listings.id` | `listings.csv.gz` | 96,871 |
| Host | `listings.host_id` (denormalised) | `listings.csv.gz` | 55,646 distinct |
| Calendar record | `(listing_id, date)` | `calendar.csv.gz` | 35,357,974 |
| Review | `reviews.id` | `reviews.csv.gz` | 2,097,996 |
| Reviewer | `reviews.reviewer_id` (denormalised) | `reviews.csv.gz` | 1,768,660 distinct |
| Neighbourhood | `neighbourhood` | `neighbourhoods.csv` + `.geojson` | 33 (London boroughs) |

---

## 1. Listing

**Definition.** A rentable accommodation advertised on Airbnb at the snapshot moment. A listing is the unit of supply, the unit at which prices, reviews, and availability accumulate, and the join key for everything analytical in this project.

**Identifier.** `listings.id` (integer, unique, no nulls — confirmed in Step 8).

**Source.** `listings.csv.gz` is the canonical source. The summary `listings.csv` is a slim subset with column-name drift and is not used downstream.

**Cardinality this snapshot.** 96,871 listings. Forward-looking calendar fully covers all of them. 72,749 of them (75.1%) have at least one review; 24,122 (24.9%) have none.

**Stakeholder questions this entity answers:**
- How many listings does each borough have, and how does median price differ across them?
- What share of listings is entire-home vs private-room?
- Which listings sit in the top-decile price bucket and what do they have in common?
- How many listings are unavailable for the next 30 days? 365 days?
- Which listings haven't been reviewed in 12+ months — and is that a quality signal or an inactivity signal?

**Caveats.** A listing exists in the snapshot if Inside Airbnb's scraper saw it on 2025-09-14. Delistings, paused listings, and listings outside the scraper's reach are not in the file. The `price` field is null for 36% of listings, which makes price-based analyses partial by construction.

---

## 2. Host

**Definition.** A person or organisation managing one or more listings. Hosts are the unit of supply behaviour: pricing strategy, response speed, portfolio size, professional-vs-casual classification.

**Identifier.** `listings.host_id`. There is no separate host file — host attributes (`host_since`, `host_response_rate`, `host_is_superhost`, etc.) are denormalised inside `listings.csv.gz`. A `dim_host` will be derived in Phase 2.4 by extracting distinct `host_id` rows.

**Cardinality this snapshot.** 55,646 distinct hosts across 96,871 listings → mean 1.74 listings/host. The distribution will be heavy-tailed: the median host has 1 listing; the right tail contains professional multi-listing operators.

**Stakeholder questions this entity answers:**
- How concentrated is the London market — what share of supply is controlled by hosts with 5+ listings?
- Do superhosts charge more or less than non-superhosts after controlling for room type and borough?
- How does host tenure (`host_since` to snapshot) correlate with review velocity and price?
- What proportion of hosts respond within an hour, and does response time predict review scores?

**Caveats.** Host attributes are last-write-wins on the snapshot date — host bios, response rates, and superhost status can change between scrapes, so any longitudinal claim needs multiple snapshots, not just this one. A host with multiple listings appears in multiple rows but their host fields will be identical across those rows.

---

## 3. Calendar record

**Definition.** A daily status for a listing — was it bookable, what was the host's posted nightly price, and what stay rules applied to that specific date.

**Identifier.** Composite `(listing_id, date)`. Confirmed unique in Step 8 — 0 duplicates across 35.4M rows.

**Source.** `calendar.csv.gz`.

**Cardinality this snapshot.** 35,357,974 records ≈ 96,871 listings × 365 days. Date range is ~12 months forward from the snapshot.

**Stakeholder questions this entity answers:**
- What fraction of next-90-day inventory is available — and how does that compare to next-30 and next-365?
- Do weekend prices command a premium? *(Cannot be answered from this snapshot — see caveat.)*
- How does inventory utilisation vary by borough or room type?
- Are minimum-night requirements clustering around event dates (e.g. major holidays)?

**Critical caveats.**
- **`available = "f"` is not a confirmed booking.** It means the date is not bookable as of the snapshot — could be blocked by the host, a stay-rule exclusion, or a paused listing. This is assumption A-002 and underpins every occupancy and revenue claim.
- **`price` and `adjusted_price` are 100% null in this snapshot** (A-005). All per-date pricing analyses are off the table; we fall back to listing-level `price` × unavailable-day counts.

---

## 4. Review

**Definition.** A guest-generated text record associated with a listing after a stay. Reviews are the dataset's only demand-side signal and the only unstructured-text source for NLP work.

**Identifier.** `reviews.id` (integer, unique).

**Source.** `reviews.csv.gz` (with `comments`). The summary `reviews.csv` is just `(listing_id, date)` without text and is not used downstream.

**Cardinality this snapshot.** 2,097,996 reviews. 0 orphan reviews — every review's `listing_id` exists in listings. Earliest review date 2010-08-18; ~14.5 years of history.

**Stakeholder questions this entity answers:**
- Which neighbourhoods generate the highest review volume per listing — i.e. which are the most-used?
- What's the seasonality of review activity — peak months, COVID-era dips, recovery shape?
- Which themes recur in low-score reviews vs high-score reviews?
- How quickly do new listings accumulate their first 10 reviews — i.e. cold-start dynamics?

**Caveats.** A review is a noisy demand proxy: most stays do not generate a review. Cross-listing comparisons of review counts conflate listing tenure with popularity. 3.5% of comment texts are exact duplicates of other comments (likely templates or platform-generated text), and these will be flagged in Phase 2.1.

---

## 5. Reviewer

**Definition.** The guest who left a review. There is no first-class reviewer entity in the source — `reviewer_id` and `reviewer_name` are columns on `reviews.csv.gz` only.

**Identifier.** `reviewer_id`.

**Cardinality this snapshot.** 1,768,660 distinct reviewer IDs across 2,097,996 reviews → mean ≈ 1.19 reviews per reviewer. Most reviewers leave one review; a small tail leaves many (frequent travellers or testers).

**Stakeholder questions this entity answers:**
- Are any listings disproportionately driven by repeat reviewers (potential review-stuffing signal)?
- What's the geographic spread of reviewer names — a soft proxy for international vs domestic guests, though name-based inference is unreliable.

**Caveats.** No first-class reviewer dimension is built; reviewer attributes stay denormalised on `fact_reviews`. Reviewer name is free text and not a reliable demographic proxy.

---

## 6. Neighbourhood

**Definition.** A geographic market grouping used for comparison and analysis. In London, this is the **borough** (the 33 administrative subdivisions).

**Identifier.** `neighbourhood` (text, unique — confirmed in Step 8).

**Source.** `neighbourhoods.csv` (33 rows, name + null group) and `neighbourhoods.geojson` (33 MultiPolygon features). Names match across both files. Every listing's `neighbourhood_cleansed` is one of these 33.

**Stakeholder questions this entity answers:**
- Which boroughs are the largest by listing supply, by review volume, by host count?
- Where are prices growing or compressing relative to the London median?
- What is the per-square-kilometre listing density of each borough (joining the GeoJSON for area)?
- Which boroughs over-index on entire homes vs private rooms — and what does that say about the local guest mix?

**Caveats.** London does **not** populate `neighbourhood_group` — the field is null in all 33 rows. Cross-city pipelines must permit this without erroring. For finer-grained geography than boroughs, the only option is to spatial-join listings' (lat, lon) against external boundary data, which is out of scope for Phase 1.

---

## Entity-relationship summary

```
Neighbourhood (33)
   ▲
   │ neighbourhood_cleansed
   │
Host (55,646)  ────┐
   ▲              │ host_id
   │              ▼
   └─────► Listing (96,871) ──┬──► Calendar record (35.4M)   one-to-many (~365/listing)
                              │
                              └──► Review (2.1M) ────► Reviewer (1.77M)
                                                        (no first-class table)
```

Three derived dimensions will be built in Phase 2.4 — `dim_host`, `dim_listing`, `dim_neighbourhood` — alongside `dim_date` for the calendar grain.
