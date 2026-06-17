# Duplicate Findings

City: **london** · Snapshot: **2025-09-14**

## 1. Exact row duplicates (per file)

| File | Rows | Exact dup rows |
|---|---:|---:|
| `listings.csv.gz` | 96,871 | 0 |
| `calendar.csv.gz` | 35,357,974 | 0 |
| `reviews.csv.gz` | 2,097,996 | 0 |
| `listings.csv` | 96,871 | 0 |
| `reviews.csv` | 2,097,996 | 12,743 |
| `neighbourhoods.csv` | 33 | 0 |

## 2. Fuzzy listing duplicates

- Rows in candidate-dup blocks: **836**
- Blocking key: `(neighbourhood_cleansed, host_id, round(latitude, 3), round(longitude, 3), normalised(name))`
- Action: flagged in `duplicate_listings.csv`, **not** deleted (A-030 principle extended to listings).

## 3. Review comment templates

- Reviews whose comment text matches at least one other review: **90,428**
- Distinct duplicate-text templates: **11,787**
- Top 20 templates by occurrence written to `duplicate_review_comments.csv`.
- Action: flagged for NLP deduplication (A-030); raw `fact_reviews` keeps all rows.
