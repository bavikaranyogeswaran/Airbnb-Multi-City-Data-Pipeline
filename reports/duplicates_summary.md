# Duplicate Findings

City: **madrid** · Snapshot: **2025-09-14**

## 1. Exact row duplicates (per file)

| File | Rows | Exact dup rows |
|---|---:|---:|
| `listings.csv.gz` | 25,000 | 0 |
| `calendar.csv.gz` | 9,125,007 | 0 |
| `reviews.csv.gz` | 1,275,992 | 0 |
| `listings.csv` | 25,000 | 0 |
| `reviews.csv` | 1,275,992 | 6,617 |
| `neighbourhoods.csv` | 128 | 0 |

## 2. Fuzzy listing duplicates

- Rows in candidate-dup blocks: **641**
- Blocking key: `(neighbourhood_cleansed, host_id, round(latitude, 3), round(longitude, 3), normalised(name))`
- Action: flagged in `duplicate_listings.csv`, **not** deleted (A-030 principle extended to listings).

## 3. Review comment templates

- Reviews whose comment text matches at least one other review: **83,733**
- Distinct duplicate-text templates: **9,260**
- Top 20 templates by occurrence written to `duplicate_review_comments.csv`.
- Action: flagged for NLP deduplication (A-030); raw `fact_reviews` keeps all rows.
