# Airbnb Assessment — Multi-City Pipeline

Inside Airbnb data pipeline for the Experne'c Talent Assessment.
**FastAPI is the canonical interface.** Every pipeline step is exposed as an endpoint;
CLI wrappers (`python -m src.X.Y`) still exist and call the same functions.

## Cities

| City | Snapshot | Listings | Currency |
|---|---|---|---|
| London | 2025-09-14 | 96,871 | GBP |
| Amsterdam | 2025-09-11 | 10,480 | EUR |

Source: https://insideairbnb.com/get-the-data/

## Layout

```
config/    city configuration (cities.yml — URLs, snapshot dates, currency codes)
data/      raw / staging / processed / quality_reports (gitignored)
  processed/
    london/    warehouse.duckdb, listing_master.parquet, cleaned parquets
    amsterdam/ warehouse.duckdb, listing_master.parquet, cleaned parquets
src/
  api/             FastAPI application + route modules
  ingestion/       downloader + manifest
  profiling/       inventory, schema, key_integrity, duplicates, outliers
  cleaning/        listings, calendar, reviews, neighbourhoods
  transformation/  listing_master enrichment
  loading/         DuckDB star schema loader
  validation/      data quality checks
sql/       analytical SQL against the DuckDB warehouse
tests/     pytest data-quality suite (128 tests, both cities)
notebooks/ London EDA and statistical analysis notebooks
reports/
  tables/          London EDA artifacts (22 CSVs)
  tables/amsterdam Amsterdam EDA artifacts (22 CSVs)
  tables/city_comparison_summary.csv
  tables/room_type_city_comparison.csv
  eda_findings.md, assumptions_log.md, engineering_decisions.md, lineage.md
logs/      pipeline run logs (gitignored)
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the API

```bash
uvicorn src.api.app:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Running the Pipeline for a City

```bash
# Full pipeline (ingest → profile → clean → transform → load)
POST /orchestration/run?city=london&stages=all
POST /orchestration/run?city=amsterdam&stages=all

# Run tests for both cities
python -m pytest tests/ -v
```

---

## Endpoint Map

All endpoints that accept a `city` query parameter support `london` and `amsterdam`.
The default is always `city=london` for backwards compatibility.

### Meta
- `GET /index` — full endpoint directory
- `GET /health` — liveness check

### Cities (`src/api/routes/cities.py`)
- `GET /cities` — list all configured cities
- `GET /cities/{code}` — full config for one city (URLs, snapshot date, currency)

### Analytics — EDA & Statistical Results (`src/api/routes/analytics.py`)

All analytics endpoints are read-only. Run the pipeline first to generate the parquet files and EDA artifacts.

**Listings**
- `GET /analytics/listings/numerical-summary?city=london` — descriptive stats for all numeric columns
- `GET /analytics/listings/price-by-room-type?city=amsterdam` — price metrics per room type
- `GET /analytics/listings/price-by-neighbourhood?city=london&top_n=20` — price metrics per neighbourhood, sorted by median
- `GET /analytics/listings/availability-bands?city=amsterdam` — listings grouped by annual availability band
- `GET /analytics/listings/search?city=london&room_type=Entire+home/apt&max_price=200&limit=20` — live parquet filter via DuckDB
- `GET /analytics/listings/{listing_id}?city=amsterdam` — full detail for one listing

**Hosts**
- `GET /analytics/hosts/segments?city=london` — solo / multi-listing / professional host split
- `GET /analytics/hosts/tenure?city=amsterdam` — host registration year distribution
- `GET /analytics/hosts/response-rates?city=london` — response rate bucket distribution

**Market**
- `GET /analytics/market/concentration?city=amsterdam` — Gini coefficient and top-N host share

**Geographic**
- `GET /analytics/geographic/density?city=london` — listing count and median price per neighbourhood
- `GET /analytics/geographic/price-by-distance?city=amsterdam` — median price by distance band from city centre
- `GET /analytics/geographic/room-type-mix?city=london` — room-type share per neighbourhood

**Temporal**
- `GET /analytics/temporal/availability?city=amsterdam` — monthly availability rate across the year
- `GET /analytics/temporal/reviews?city=london` — monthly review volume (booking demand proxy)
- `GET /analytics/temporal/minimum-nights?city=amsterdam` — monthly minimum-nights trends
- `GET /analytics/temporal/weekday-vs-weekend?city=london` — weekday vs weekend availability
- `GET /analytics/temporal/seasonal?city=amsterdam` — seasonal availability and review summary

**Reviews**
- `GET /analytics/reviews/summary?city=london` — review score summary statistics
- `GET /analytics/reviews/subdimensions?city=amsterdam` — cleanliness, location, communication medians by room type
- `GET /analytics/reviews/anomalies?city=london&limit=50` — high-review-count / low-score listings

**Statistical Analysis**
- `GET /analytics/stats/hypothesis-tests?city=amsterdam` — all five hypothesis test results (H1–H5)
- `GET /analytics/stats/regression/coefficients?city=london` — OLS coefficients with 95% CI
- `GET /analytics/stats/regression/summary?city=amsterdam` — model-level metrics (R², F-stat, n)

**Cross-City Comparisons** (no `city` param — always both cities)
- `GET /analytics/comparison/cities` — London vs Amsterdam key metric comparison
- `GET /analytics/comparison/room-types` — room-type share comparison across both cities

**Reports**
- `GET /analytics/reports/eda-findings` — full EDA findings report (Markdown)

### Quality Checks (`src/api/routes/quality.py`)
- `GET /quality/runs?city=london&limit=20` — past test runs with pass/fail counts
- `GET /quality/runs/{run_id}?city=amsterdam` — per-test detail for one run
- `GET /quality/latest?city=london` — most recent run results
- `POST /quality/run?city=amsterdam` — execute the full test suite (sync, ~2s)

### Pipeline Orchestration (`src/api/routes/orchestration.py`)
Stages: `ingest → profile → clean → transform → load`. Idempotent — repeat runs are skipped unless `force=true`.

- `GET /orchestration/runs?city=london&limit=20` — recent pipeline runs
- `GET /orchestration/runs/{run_id}?city=amsterdam` — stage-level breakdown for one run
- `GET /orchestration/dataset-versions?city=london` — registered snapshots with manifest SHA-256
- `GET /orchestration/lineage` — source → warehouse data lineage (Markdown)
- `POST /orchestration/run?city=amsterdam&stages=all&force=false` — full pipeline
- `POST /orchestration/run?city=london&stages=clean,transform` — subset of stages
- `POST /orchestration/run?city=amsterdam&stages=all&force=true` — re-run even if registered

### Warehouse / Star Schema (`src/api/routes/warehouse.py`)
Each city has its own DuckDB warehouse at `data/processed/{city}/warehouse.duckdb`.
Schema: 5 dimension tables (`dim_city`, `dim_neighbourhood`, `dim_host`, `dim_listing`, `dim_date`) + 3 fact tables (`fact_calendar`, `fact_reviews`, `fact_listing_snapshot`).

- `GET /warehouse/tables?city=amsterdam` — list tables with row counts
- `GET /warehouse/queries` — list available SQL queries
- `GET /warehouse/queries/{name}?city=london` — run a named query
- `GET /warehouse/queries/{name}/sql` — return the raw SQL text
- `POST /warehouse/dimensions:run?city=amsterdam`
- `POST /warehouse/facts:run?city=london`
- `POST /warehouse/build?city=amsterdam` — dimensions then facts

### Enrichment & Joining (`src/api/routes/enrichment.py`)
- `GET /enrichment/manifest?city=london` — all cleaned + enriched parquet inventory
- `GET /enrichment/review-summary?city=amsterdam&n=5`
- `GET /enrichment/calendar-summary?city=london&n=5`
- `GET /enrichment/neighbourhood-summary?city=amsterdam` — neighbourhoods with density
- `GET /enrichment/listing-master?city=london&n=5`
- `GET /enrichment/top-neighbourhoods?by=median_price_gbp&n=10`
- `POST /enrichment/all?city=amsterdam` — chain all enrichment steps in dependency order

### Cleaning & Standardization (`src/api/routes/cleaning.py`)
- `GET /cleaning/manifest?city=london` — cleaned-parquet inventory (paths, sizes, row counts)
- `GET /cleaning/listings?city=amsterdam&n=5` — head preview of cleaned listings
- `GET /cleaning/calendar?city=london&n=5` — head preview of cleaned calendar
- `GET /cleaning/reviews?city=amsterdam&n=5` — head preview of cleaned reviews
- `GET /cleaning/neighbourhoods?city=london` — all cleaned neighbourhoods with centroid and area
- `POST /cleaning/all?city=amsterdam` — neighbourhoods → listings → calendar → reviews

### Ingestion & Profiling (`src/api/routes/ingestion.py`)
- `GET /ingestion/manifest` — file manifest (CSV→JSON)
- `GET /ingestion/profile` — extended profile (JSON)
- `GET /ingestion/duplicates` — duplicate analysis (Markdown)
- `GET /ingestion/outliers` — outlier report (Markdown)
- `GET /ingestion/quality-report` — full quality report (HTML)
- `POST /ingestion/all?city=amsterdam` — chain ingest → profile → duplicates → outliers → report

### Dataset Familiarization (`src/api/routes/familiarization.py`)
- `GET /familiarization/file-purpose` — what each source file contains
- `GET /familiarization/schema` — column names, types, and sample values
- `GET /familiarization/key-integrity` — primary/foreign key relationships
- `GET /familiarization/business-entities` — domain description (listing, host, review)
- `GET /familiarization/special-fields` — columns requiring special interpretation
- `GET /familiarization/limitations` — dataset coverage gaps and scraping artifacts
- `GET /familiarization/assumptions` — documented field assumptions (A-001–A-036)

---

## How Adding a New Step Works

Every pipeline step ships as three things:

1. **A `run()` function** in `src/<area>/<step>.py` returning a standard `make_result()` dict.
2. **A thin CLI wrapper** (`main()` in the same file) for shell users.
3. **A FastAPI endpoint** in `src/api/routes/<area>.py` that calls `run()` directly.

The CLI and the API always call the same function — there is one source of truth.

## Adding a New City

1. Add an entry to `config/cities.yml` with the download URL, snapshot date, and currency code.
2. Run `POST /orchestration/run?city=<new_city>&stages=all` — the pipeline handles the rest.
3. Run `POST /quality/run?city=<new_city>` to validate.
4. Generate EDA tables by running the analytics generation script for the new city.
5. All analytics endpoints automatically serve the new city via `?city=<new_city>`.

## Conventions

- Route modules are named by domain: `cleaning.py`, `enrichment.py`, `warehouse.py`, `orchestration.py`, `quality.py`, `analytics.py`. No `phase*.py` filenames.
- No new shell-only scripts — every step ships with a FastAPI endpoint.
- `currency_code` per city comes from `cities.yml`, not hardcoded anywhere.
- London EDA tables live in `reports/tables/`; other cities use `reports/tables/<city>/`.
