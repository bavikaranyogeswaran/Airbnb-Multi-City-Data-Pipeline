# Data Lineage

Cities: **London** (2025-09-14) · **Amsterdam** (2025-09-11) · **Madrid** (2025-09-14) · **Berlin** (2025-09-23)

The lineage below describes the canonical transformation chain. It applies identically to all four cities — substitute `london` with the relevant city code in every path. Row counts shown are for London; other cities differ in scale but not structure.

Tracks every output back to the source file it was derived from, plus the function or SQL that performed the transformation. Use this when a warehouse value looks wrong and you need to find the upstream cause.

---

## 1. Listings lineage

```
Inside Airbnb listings.csv.gz
   │ src.ingestion.download.run               (HTTP GET + sha256 + manifest)
   ▼
data/raw/london/listings.csv.gz                                    (79 cols, 96,871 rows)
   │ src.profiling.extended_profile.run       (column stats + top-N)
   │ src.profiling.duplicates.run             (exact + fuzzy listing blocking)
   │ src.profiling.outliers.run               (IQR + 17 domain rules)
   ▼
reports/extended_profile.json
reports/duplicates_summary.md, reports/duplicate_listings.csv
reports/outliers_iqr.csv, reports/outliers_domain.csv
   │
   │ src.cleaning.listings.run                (drop 11 cols, parse price/dates/bools,
   │                                            normalize room_type, bucket property_type,
   │                                            parse bathrooms_text, derive
   │                                            is_de_facto_inactive)
   ▼
data/processed/london/listings_clean.parquet                       (75 cols, 96,871 rows)
data/processed/london/rejected_listings.parquet                    (0 rows)
   │
   │ src.transformation.listing_master.run    (DuckDB JOIN: reviews + calendar +
   │                                            neighbourhood summaries; derive
   │                                            host_tenure_years, price_per_bedroom,
   │                                            revenue_proxy_gbp, is_active_supply)
   ▼
data/processed/london/listing_master.parquet                       (~96 cols, 96,871 rows)
   │
   │ src.loading.warehouse.build_dimensions   (dim_listing surrogate ← source_listing_id)
   │ src.loading.warehouse.build_facts        (fact_listing_snapshot grain: listing × snapshot)
   ▼
warehouse.duckdb · dim_listing                                     (96,871 rows)
warehouse.duckdb · fact_listing_snapshot                           (96,871 rows)
```

---

## 2. Calendar lineage

```
Inside Airbnb calendar.csv.gz
   │ src.ingestion.download.run
   ▼
data/raw/london/calendar.csv.gz                                    (7 cols, 35,357,974 rows)
   │ src.cleaning.calendar.run                (drop 100%-null price + adjusted_price,
   │                                            parse date + available, cap_sentinel_intmax
   │                                            on stay-rule fields)                 [A-005, A-018]
   ▼
data/processed/london/calendar_clean.parquet                       (5 cols, 35,357,974 rows)
   │
   │ src.transformation.calendar_summary.run  (DuckDB: per-listing
   │                                            availability_rate, occupancy_proxy,
   │                                            weekend/weekday split)               [A-002]
   ▼
data/processed/london/calendar_summary.parquet                     (96,871 rows)
   │
   │ src.loading.warehouse.build_facts        (date_key derived as yyyymmdd)
   ▼
warehouse.duckdb · fact_calendar                                   (35,357,974 rows)
```

---

## 3. Reviews lineage

```
Inside Airbnb reviews.csv.gz
   │ src.ingestion.download.run
   ▼
data/raw/london/reviews.csv.gz                                     (6 cols, 2,097,996 rows)
   │ src.cleaning.reviews.run                 (parse date + trim text;
   │                                            derive comment_length and
   │                                            comment_is_duplicate)                [A-030]
   ▼
data/processed/london/reviews_clean.parquet                        (8 cols, 2,097,996 rows)
   │
   │ src.transformation.review_summary.run    (DuckDB: per-listing review_count_calc,
   │                                            first/last, last-12-mo and last-30-day
   │                                            counts, unique reviewer count)
   ▼
data/processed/london/review_summary.parquet                       (72,749 rows)
   │
   │ src.loading.warehouse.build_facts        (date_key + listing_key derived)
   ▼
warehouse.duckdb · fact_reviews                                    (2,097,996 rows)
```

---

## 4. Neighbourhood lineage

```
Inside Airbnb neighbourhoods.csv  +  neighbourhoods.geojson
   │ src.ingestion.download.run
   ▼
data/raw/london/neighbourhoods.csv                                 (2 cols, 33 rows)
data/raw/london/neighbourhoods.geojson                             (33 features, MultiPolygon)
   │ src.cleaning.neighbourhoods.run          (drop neighbourhood_group [A-028];
   │                                            reproject to EPSG:27700 for area_km2 [A-029];
   │                                            extract centroid)
   ▼
data/processed/london/neighbourhoods_clean.parquet                 (5 cols, 33 rows)
data/processed/london/neighbourhoods_geo.parquet                   (geometry-only, 33 rows)
   │
   │ src.transformation.neighbourhood_summary.run  (DuckDB: borough aggregates +
   │                                                 listing density)
   ▼
data/processed/london/neighbourhood_summary.parquet                (33 rows)
   │
   │ src.loading.warehouse.build_dimensions   (dim_neighbourhood surrogate key)
   ▼
warehouse.duckdb · dim_neighbourhood                               (33 rows)
```

---

## 5. Host lineage (derived, not a source file)

```
listings.csv.gz [host_* columns, denormalised]
   │ src.loading.warehouse.build_dimensions   (GROUP BY host_id; ANY_VALUE for
   │                                            stable host attributes; SCD-2
   │                                            placeholders valid_from / valid_to /
   │                                            is_current)
   ▼
warehouse.duckdb · dim_host                                        (55,646 rows)
```

---

## 6. Cross-cutting outputs

```
warehouse.duckdb  ─────────────────┐
   │                               │
   ▼                               ▼
sql/01..05_*.sql                  pipeline_run + pipeline_stage_run +
   (5 analytical SQL files,        dataset_version
   served via /warehouse/queries)  (metadata tables for run history
                                   and incremental detection)
```

```
reports/data_quality_report.html
   ↑ src.validation.quality_report.run
   ↑ inventory + schema + integrity + duplicates + outliers (joined)
```

---

## 7. EDA and statistical analysis lineage

```
data/processed/{city}/listing_master.parquet
data/processed/{city}/calendar_clean.parquet
data/processed/{city}/reviews_clean.parquet
   │ src.analytics.run_eda.run(city)
   │   • haversine distance from city centre → distance bands
   │   • host segment classification (solo / multi / professional)
   │   • availability band summary
   │   • OLS regression: log_price ~ room_type + accommodates + bedrooms
   │                                  + review_scores_rating + superhost
   │                                  + neighbourhood_cleansed   [HC3]
   │   • hypothesis tests H1–H5 (Welch t, Mann-Whitney U, Kruskal-Wallis)
   ▼
reports/tables/{city}/                         (22 CSV files)
  numerical_summary.csv
  price_by_room_type.csv
  price_by_neighbourhood.csv
  host_segment_summary.csv
  availability_band_summary.csv
  neighbourhood_density.csv
  price_by_distance_band.csv
  room_type_by_neighbourhood.csv
  monthly_availability.csv
  weekday_weekend_availability.csv
  minimum_nights_monthly.csv
  monthly_review_volume.csv
  host_tenure_summary.csv
  response_rate_summary.csv
  market_concentration.csv
  high_review_low_score_listings.csv
  review_subdimension_summary.csv
  review_summary.csv
  temporal_summary.csv
  hypothesis_test_results.csv
  regression_coefficients.csv
  regression_summary.csv
```

```
reports/tables/{city}/ + reports/model_results/
   │ src.llm.context_builder.*
   ▼
Groq API (llama-3.3-70b-versatile)
   │ src.llm.client.generate
   ▼
reports/llm_summaries/{city}_{type}.md         (cached narrative summaries)
reports/llm_summaries/cross_city.md
```

---

## 8. Run + metadata

Every orchestrated run is recorded in three tables inside `warehouse.duckdb`:

- `pipeline_run` — one row per orchestrator invocation (run_id, city, snapshot_date, status, ok/error counts, elapsed)
- `pipeline_stage_run` — one row per (run, stage, step) with started_at / finished_at / elapsed / summary_json
- `dataset_version` — one row per (city, snapshot_date) once a full run succeeds; the manifest SHA-256 anchors the version

The orchestrator skips re-running a snapshot already in `dataset_version` unless `force=true`. This is the incremental detection hook for future snapshots — when 2025-12-XX arrives, the gate opens automatically.
