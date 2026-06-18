# Duplicate Findings

City: **amsterdam** · Snapshot: **2025-09-11**

## 1. Exact row duplicates (per file)

| File | Rows | Exact dup rows |
|---|---:|---:|
| `listings.csv.gz` | 10,480 | 0 |
| `calendar.csv.gz` | 3,825,200 | 0 |
| `reviews.csv.gz` | 501,084 | 0 |
| `listings.csv` | 10,480 | 0 |
| `reviews.csv` | 501,084 | 17,612 |
| `neighbourhoods.csv` | 22 | 0 |

## 2. Fuzzy listing duplicates

- Rows in candidate-dup blocks: **20**
- Blocking key: `(neighbourhood_cleansed, host_id, round(latitude, 3), round(longitude, 3), normalised(name))`
- Action: flagged in `duplicate_listings.csv`, **not** deleted (A-030 principle extended to listings).

## 3. Review comment templates

- Reviews whose comment text matches at least one other review: **17,394**
- Distinct duplicate-text templates: **2,577**
- Top 20 templates by occurrence written to `duplicate_review_comments.csv`.
- Action: flagged for NLP deduplication (A-030); raw `fact_reviews` keeps all rows.
