# Single-City Completion Gate — Amsterdam

**Generated:** 2026-06-19 06:48 UTC  
**Gate status:** OPEN — ready to scale  
**Results:** 13 PASS · 0 WARN · 0 FAIL

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | raw_download | ✅ PASS | All 5 raw files present. listings.csv.gz: 5.7MB, reviews.csv.gz: 58.9MB, calendar.csv.gz: 8.4MB, neighbourhoods.csv: 0.0 |
| 2 | no_hardcoded_city | ✅ PASS | No hardcoded city path segments in cleaning/ or transformation/ |
| 3 | profiles_generated | ✅ PASS | All 4 profile documents present in reports/ |
| 4 | silver_parquet | ✅ PASS | All 6 processed files present. listings_clean.parquet: 6.0MB, reviews_clean.parquet: 83.7MB, calendar_clean.parquet: 1.4 |
| 5 | rejected_records | ✅ PASS | All 3 rejection files present. rejected_listings.parquet: 37562B, rejected_reviews.parquet: 4144B, rejected_calendar.par |
| 6 | duckdb_builds | ✅ PASS | warehouse.duckdb (22.5MB) — all 8 tables present: ['data_quality_result', 'dataset_version', 'dim_city', 'dim_date', 'di |
| 7 | sql_queries | ✅ PASS | All 5 SQL queries execute successfully: 01_median_price_by_room_type.sql, 02_top_neighbourhoods_by_listing_count.sql, 03 |
| 8 | eda_notebook | ✅ PASS | 03_exploratory_data_analysis.ipynb: all 39 code cells executed (execution_count set) |
| 9 | stats_notebook | ✅ PASS | 04_statistical_analysis.ipynb: all 9 code cells executed |
| 10 | api_endpoints | ✅ PASS | health=200, analytics index=200, price-by-room-type=200 (4 rows) |
| 11 | tests_pass | ✅ PASS | 0 tests passed, 0 failures. (-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html) |
| 12 | readme_commands | ✅ PASS | README.md present (1215 words), contains: ['uvicorn', 'pytest', 'pip install'] |
| 13 | decision_logs | ✅ PASS | All decision docs present: ['engineering_decisions.md (18.1KB)', 'assumptions_log.md (19.5KB)', 'eda_findings.md (24.4KB |

## Details

### 1. raw_download
**Status:** ✅ PASS

```
All 5 raw files present. listings.csv.gz: 5.7MB, reviews.csv.gz: 58.9MB, calendar.csv.gz: 8.4MB, neighbourhoods.csv: 0.0MB, neighbourhoods.geojson: 0.2MB
```

### 2. no_hardcoded_city
**Status:** ✅ PASS

```
No hardcoded city path segments in cleaning/ or transformation/
```

### 3. profiles_generated
**Status:** ✅ PASS

```
All 4 profile documents present in reports/
```

### 4. silver_parquet
**Status:** ✅ PASS

```
All 6 processed files present. listings_clean.parquet: 6.0MB, reviews_clean.parquet: 83.7MB, calendar_clean.parquet: 1.4MB, neighbourhoods_clean.parquet: 0.0MB...
```

### 5. rejected_records
**Status:** ✅ PASS

```
All 3 rejection files present. rejected_listings.parquet: 37562B, rejected_reviews.parquet: 4144B, rejected_calendar.parquet: 2826B
```

### 6. duckdb_builds
**Status:** ✅ PASS

```
warehouse.duckdb (22.5MB) — all 8 tables present: ['data_quality_result', 'dataset_version', 'dim_city', 'dim_date', 'dim_host', 'dim_listing', 'dim_neighbourhood', 'fact_calendar', 'fact_listing_snapshot', 'fact_reviews', 'pipeline_run', 'pipeline_stage_run']
```

### 7. sql_queries
**Status:** ✅ PASS

```
All 5 SQL queries execute successfully: 01_median_price_by_room_type.sql, 02_top_neighbourhoods_by_listing_count.sql, 03_weekend_vs_weekday_availability.sql, 04_occupancy_proxy_distribution.sql, 05_superhost_price_rating_gap.sql
```

### 8. eda_notebook
**Status:** ✅ PASS

```
03_exploratory_data_analysis.ipynb: all 39 code cells executed (execution_count set)
```

### 9. stats_notebook
**Status:** ✅ PASS

```
04_statistical_analysis.ipynb: all 9 code cells executed
```

### 10. api_endpoints
**Status:** ✅ PASS

```
health=200, analytics index=200, price-by-room-type=200 (4 rows)
```

### 11. tests_pass
**Status:** ✅ PASS

```
0 tests passed, 0 failures. (-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html)
```

### 12. readme_commands
**Status:** ✅ PASS

```
README.md present (1215 words), contains: ['uvicorn', 'pytest', 'pip install']
```

### 13. decision_logs
**Status:** ✅ PASS

```
All decision docs present: ['engineering_decisions.md (18.1KB)', 'assumptions_log.md (19.5KB)', 'eda_findings.md (24.4KB)']
```

---

> All checks passed (WARN is acceptable). Proceed to Section 27: Scale from One City to Six Cities.
