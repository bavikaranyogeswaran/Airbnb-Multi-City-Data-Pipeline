# Key Integrity Report

City: **London** · Snapshot: **2025-09-14**

All checks below are read-only. No duplicates were dropped, no orphans deleted. Phase 2 will decide whether to quarantine or repair each finding.

## 1. Listings primary key

- **Row count:** 96,871
- **`id` is unique ✓:** True
- **`id` null count:** 0
- **`host_id` null count:** 0
- **Distinct hosts:** 55,646
- **Distinct neighbourhoods (cleansed):** 33
- **Listings with null neighbourhood_cleansed:** 0

## 2. Reviews primary key + FK

- **Row count:** 2,097,996
- **`id` is unique ✓:** True
- **`id` duplicate row count:** 0
- **Distinct `listing_id` referenced:** 72,749
- **Orphan review rows (listing_id not in listings):** 0
- **Distinct orphan listing_ids:** 0
- **Orphan rate:** 0.0%

## 3. Calendar composite key + FK

- **Row count:** 35,357,974
- **`(listing_id, date)` duplicate count ✓:** 0
- **Distinct `listing_id` in calendar:** 96,871
- **Orphan calendar rows (listing_id not in listings):** 0
- **Distinct orphan listing_ids:** 0
- **Listings present in listings.csv.gz but absent from calendar:** 0
- **Orphan rate:** 0.0%

## 4. Neighbourhoods reference integrity

- **CSV row count:** 33
- **CSV PK (`neighbourhood`) unique ✓:** True
- **GeoJSON feature count:** 33
- **CSV ↔ GeoJSON name parity ✓:** True
- **listings.neighbourhood_cleansed values not in neighbourhoods.csv ✓:** none

## 5. Summary table

| Check | Result |
|---|---|
| listings.id unique | ✓ |
| reviews.id unique | ✓ |
| calendar (listing_id, date) unique | ✓ |
| reviews orphan rows | 0 (0.0%) |
| calendar orphan rows | 0 (0.0%) |
| neighbourhoods CSV ↔ GeoJSON parity | ✓ |
| listings → neighbourhoods FK clean | ✓ |

## 6. Decisions deferred to Phase 2

- Whether to drop orphan reviews / orphan calendar rows or to keep them with a `_orphan` flag.
- How to handle listings that appear in `listings.csv.gz` but not in `calendar.csv.gz`.
- How to treat listings whose `neighbourhood_cleansed` does not match the borough CSV (point-in-polygon repair via GeoPandas, or quarantine).