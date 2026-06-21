# Inside Airbnb — Multi-City Data Pipeline

**Experne'c Talent Assessment · Data Engineer Intern**

FastAPI-first pipeline covering ingestion → cleaning → enrichment → warehouse → EDA → ML pricing models → K-Means market segmentation for London, Amsterdam, Madrid, and Berlin.

**FastAPI is the canonical interface.** Every pipeline step is exposed as an HTTP endpoint. CLI wrappers (`python -m src.X.Y`) exist for shell users and call the same functions.

---

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt

uvicorn src.api.app:app --reload --port 8000
```

Interactive docs: **http://localhost:8000/docs**

---

## Cities

| City | Snapshot | Raw listings | Filtered (price > 0) | Unique hosts | Currency |
|---|---|---|---|---|---|
| London | 2025-09-14 | 96,871 | 61,963 | 55,646 | GBP |
| Amsterdam | 2025-09-11 | 10,480 | 5,874 | 9,201 | EUR |
| Madrid | 2025-09-14 | 25,000 | 18,953 | 10,453 | EUR |
| Berlin | 2025-09-23 | 14,274 | 9,264 | 9,464 | EUR |

Source: https://insideairbnb.com/get-the-data/

> **Note — New York City (2025-12-04):** NYC was evaluated as a 5th city but all 36,261 listings had null prices. Airbnb stopped exposing nightly prices in NYC scrapes following enforcement of New York City Local Law 18 (September 2023), which heavily restricted short-term rentals. Ingest and warehouse steps completed successfully; ML and clustering were skipped due to the absence of a price signal.

---

## Key Results

### Price Prediction

| City | Best Model | Test MAE | R² (log) | Within 20% |
|---|---|---|---|---|
| London | LightGBM | £77.47 | 0.690 | 49.6% |
| Amsterdam | LightGBM | €80.68 | 0.617 | 54.1% |
| Madrid | Random Forest | €46.85 | — | — |
| Berlin | LightGBM | €46.44 | — | — |

- Train/test split: **GroupShuffleSplit by host_id** — same host cannot appear in both splits
- Target: **log1p(price)** — back-transformed to currency for MAE reporting
- Madrid and Berlin achieve lower MAE than Amsterdam despite fewer training rows — smaller, more homogeneous markets are inherently easier to predict
- Known bias: luxury listings (>£500 / >€700) are systematically **underpredicted** — regression-to-mean effect from log-price target

**Cross-city transfer (London model → Amsterdam):** MAE degraded from €81 to €175, R²(log) from +0.617 to −2.058. Root cause: TargetEncoder trained on London neighbourhoods maps all 22 Amsterdam neighbourhoods to the London global mean. Per-city retraining is required.

### Market Segmentation (K-Means — auto-detected k)

**London** (k=5)

| Cluster | Segment Name | % of city | Median £ |
|---|---|---|---|
| 3 | Outer City Budget Rooms | 22.3% | £67 |
| 1 | High-Turnover City Lets | 14.5% | £96 |
| 4 | New & Unreviewed Listings | 2.7% | £121 |
| 2 | Standard City Apartments | 33.5% | £134 |
| 0 | Premium Spacious Apartments | 26.9% | £262 |

**Amsterdam** (k=5)

| Cluster | Segment Name | % of city | Median € |
|---|---|---|---|
| 3 | High-Turnover Private Rooms | 17.0% | €147 |
| 2 | Part-Time City Apartments | 30.2% | €187 |
| 4 | New & Unreviewed Listings | 3.1% | €195 |
| 1 | Well-Available City Apartments | 20.8% | €241 |
| 0 | Premium Spacious Apartments | 28.9% | €333 |

**Madrid** (k=8)

| Cluster | Segment Name | % of city | Median € |
|---|---|---|---|
| 4 | Budget Rooms | 12.2% | €58 |
| 3 | Economy Apartments | 10.4% | €62 |
| 1 | New & Unreviewed Listings | 2.6% | €95 |
| 6 | High-Turnover City Lets | 17.2% | €105 |
| 7 | Part-Time City Apartments | 14.4% | €108 |
| 0 | Luxury Listings | 21.6% | €120 |
| 5 | Premium Spacious Apartments | 7.4% | €150 |
| 2 | Premium Spacious Apartments (large) | 14.3% | €225 |

**Berlin** (k=8)

| Cluster | Segment Name | % of city | Median € |
|---|---|---|---|
| 5 | Well-Available City Apartments | 22.8% | €72 |
| 4 | Economy Apartments | 7.3% | €85 |
| 6 | Part-Time City Apartments | 18.6% | €89 |
| 1 | High-Turnover City Lets | 15.2% | €98 |
| 2 | New & Unreviewed Listings | 1.4% | €100 |
| 3 | Luxury Listings | 15.4% | €125 |
| 0 | Premium Spacious Apartments | 12.2% | €195 |
| 7 | Premium Spacious Apartments (large) | 7.3% | €250 |

All four cities produce the same core archetypes — budget/economy tiers, high-turnover lets, new/unreviewed fringe, mid-market apartments, premium spacious — confirming the segment structure is universal. Madrid and Berlin auto-selected k=8 vs k=5 for London/Amsterdam, reflecting more granular price tiers in mid-sized markets.

### Host Segmentation (K-Means on host portfolios)

| City | k | Segment Name | Hosts | % | Key signal |
|---|---|---|---|---|---|
| London | 3 | Passive Listers | 6,788 | 12.2% | 53% response, 24% acceptance — disengaged |
| London | 3 | Professional Superhosts | 9,925 | 17.8% | 79% superhost, 4+ listings, actively booked |
| London | 3 | Occasional Hosts | 38,933 | 70.0% | Responsive, part-time (81 avail days/year) |
| Amsterdam | 2 | Active Superhost Operators | 1,270 | 13.8% | 65% superhost, 2.83 reviews/month |
| Amsterdam | 2 | Part-Time Apartment Hosts | 7,931 | 86.2% | 97% entire home, rarely booked |
| Madrid | 5 | Passive Listers | 665 | 6.4% | 19% response, 22% acceptance — disengaged |
| Madrid | 5 | Active Superhost Operators | 2,408 | 23.0% | 97% superhost, 2.88 reviews/month |
| Madrid | 5 | Premium Hosts | 4,113 | 39.3% | 98% entire home, responsive non-superhosts |
| Madrid | 5 | Occasional Hosts | 3,113 | 29.8% | Low availability, mostly private rooms |
| Madrid | 5 | Luxury Hosts | 154 | 1.5% | 24+ listings, professional operators |
| Berlin | 3 | Passive Listers | 1,044 | 11.0% | 60% response, 29% acceptance — disengaged |
| Berlin | 3 | Occasional Hosts | 5,658 | 59.8% | Responsive, very low availability (69 days) |
| Berlin | 3 | Professional Superhosts | 2,762 | 29.2% | 68% superhost, 1.83 reviews/month |

Silhouette scores — listings: London 0.151, Amsterdam 0.155, Madrid 0.150, Berlin 0.172. Hosts: London 0.266, Amsterdam 0.366, Berlin 0.235, Madrid 0.171. Hosts cluster more naturally than listings in all cities. **Passive Listers appear in every city** — a universal platform health signal.

---

## Project Layout

```
config/
  cities.yml                city configs — URLs, snapshot dates, currencies

data/                       (gitignored — regenerated by pipeline)
  raw/                      downloaded CSV files
  processed/
    london/
      listing_master.parquet    71 enriched features
      feature_matrix.parquet    36 ML features (scaled/encoded)
      clustering_features.parquet  9 K-Means features
      clustering_labels.parquet    listing → cluster assignments
      warehouse.duckdb          star-schema warehouse
    amsterdam/                same structure

models/
  london_price_model.joblib       trained LightGBM pipeline
  amsterdam_price_model.joblib
  london_kmeans.joblib            K-Means artifact (scaler + model + metadata)
  amsterdam_kmeans.joblib
  london_model_metadata.json      35-key model card
  amsterdam_model_metadata.json

reports/
  tables/                   London EDA CSVs (22 files)
  tables/amsterdam/         Amsterdam EDA CSVs (22 files)
  model_results/            ML + clustering outputs (all cities)
    full_model_comparison_{city}.csv
    feature_importance_permutation_{city}.csv
    feature_importance_shap_{city}.csv
    residuals_enriched_{city}.csv
    neighbourhood_error_analysis_{city}.csv
    room_type_error_analysis_{city}.csv
    price_band_error_analysis_{city}.csv
    cross_city_transfer_results.csv
    elbow_scores_{city}.csv
    clustering_profile_{city}.csv
  eda_findings.md
  assumptions_log.md
  engineering_decisions.md

src/
  api/
    app.py                  FastAPI application (v1.0.0)
    routes/
      analytics.py          EDA results + ML predict + Clustering endpoints
      cities.py
      cleaning.py
      enrichment.py
      familiarization.py
      ingestion.py
      orchestration.py
      quality.py
      warehouse.py

  features/
    listing_features.py     Build 36-feature ML matrix (Step 6)
    clustering_features.py  Build 9-feature clustering matrix (Step 19)

  models/
    train_price_model.py    LightGBM training pipeline (Step 7)
    evaluate_model.py       Full evaluation — MAE, RMSE, MAPE, R², within-20% (Step 8)
    explain_model.py        SHAP + permutation importance (Step 10)
    residual_analysis.py    Deep residual breakdown by segment (Step 9)
    cross_city_transfer.py  Transfer London model → Amsterdam (Phase 2)
    cluster_listings.py     Elbow sweep + K-Means fit (Step 20)
    cluster_profiles.py     Cluster profiling and segment naming (Step 21)

  ingestion/  cleaning/  transformation/  loading/  validation/
    (core pipeline — unchanged from Phase 1)

notebooks/
  london_eda.ipynb
  amsterdam_eda.ipynb

sql/                        named DuckDB queries
tests/                      128 data-quality tests (pytest)
```

---

## Full Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt
# Key packages: fastapi uvicorn lightgbm scikit-learn shap duckdb pandas pyarrow joblib pydantic
```

---

## Running the Pipeline

### Step 1 — Ingest, clean, enrich, and load (all cities)

```bash
# Via API (recommended)
curl -X POST "http://localhost:8000/orchestration/run?city=london&stages=all"
curl -X POST "http://localhost:8000/orchestration/run?city=amsterdam&stages=all"
curl -X POST "http://localhost:8000/orchestration/run?city=madrid&stages=all"
curl -X POST "http://localhost:8000/orchestration/run?city=berlin&stages=all"

# Via CLI
python -m src.orchestration.pipeline london
python -m src.orchestration.pipeline amsterdam
python -m src.orchestration.pipeline madrid
python -m src.orchestration.pipeline berlin
```

### Step 2 — Run data quality tests

```bash
python -m pytest tests/ -v
# Tests run against all configured cities
```

### Step 3 — Build ML feature matrices

```bash
python -m src.features.listing_features london
python -m src.features.listing_features amsterdam
python -m src.features.listing_features madrid
python -m src.features.listing_features berlin
```

### Step 4 — Train pricing models

```bash
python -m src.models.train_price_model london
python -m src.models.train_price_model amsterdam
python -m src.models.train_price_model madrid
python -m src.models.train_price_model berlin
```

### Step 5 — Evaluate and explain models

```bash
python -m src.models.evaluate_model london
python -m src.models.explain_model london    # SHAP + permutation importance
python -m src.models.residual_analysis london
# Repeat for amsterdam, madrid, berlin

python -m src.models.cross_city_transfer     # London model → Amsterdam
```

### Step 6 — Build listing clustering features and run K-Means

```bash
# k is auto-detected (knee heuristic + silhouette); London/Amsterdam → k=5, Madrid/Berlin → k=8
python -m src.features.clustering_features london
python -m src.models.cluster_listings london
python -m src.models.cluster_profiles london
# Repeat for amsterdam, madrid, berlin
```

### Step 7 — Build host clustering features and run K-Means

```bash
# k auto-detected: London=3, Amsterdam=2, Madrid=5, Berlin=3
python -m src.features.host_features london
python -m src.models.cluster_hosts london
python -m src.models.host_cluster_profiles london
# Repeat for amsterdam, madrid, berlin
```

Everything above is also triggerable via the API — see the endpoint map below.

---

## Endpoint Map

All endpoints that accept a `city` query parameter support `london`, `amsterdam`, `madrid`, and `berlin`. Default is always `city=london`.

### Meta

- `GET /index` — full service directory with all router prefixes
- `GET /health` — liveness check
- `GET /completion-gate?city=london` — 13-item pipeline completion checklist

### Cities

- `GET /cities` — list configured cities
- `GET /cities/{code}` — full config for one city (URL, snapshot date, currency)

---

### EDA & Statistical Analysis (`/analytics`)

All analytics read endpoints serve pre-computed CSVs/JSON. Run the pipeline first.

**Listings**
- `GET /analytics/listings/numerical-summary?city=london`
- `GET /analytics/listings/price-by-room-type?city=amsterdam`
- `GET /analytics/listings/price-by-neighbourhood?city=london&top_n=20`
- `GET /analytics/listings/availability-bands?city=amsterdam`
- `GET /analytics/listings/search?city=london&room_type=entire_home&max_price=200&limit=20` — live DuckDB filter
- `GET /analytics/listings/{listing_id}?city=amsterdam`

**Hosts**
- `GET /analytics/hosts/segments?city=london` — solo / multi / professional split
- `GET /analytics/hosts/tenure?city=amsterdam`
- `GET /analytics/hosts/response-rates?city=london`

**Market**
- `GET /analytics/market/concentration?city=amsterdam` — Gini coefficient + top-N host share

**Geographic**
- `GET /analytics/geographic/density?city=london`
- `GET /analytics/geographic/price-by-distance?city=amsterdam`
- `GET /analytics/geographic/room-type-mix?city=london`

**Temporal**
- `GET /analytics/temporal/availability?city=amsterdam`
- `GET /analytics/temporal/reviews?city=london`
- `GET /analytics/temporal/minimum-nights?city=amsterdam`
- `GET /analytics/temporal/weekday-vs-weekend?city=london`
- `GET /analytics/temporal/seasonal?city=amsterdam`

**Reviews**
- `GET /analytics/reviews/summary?city=london`
- `GET /analytics/reviews/subdimensions?city=amsterdam`
- `GET /analytics/reviews/anomalies?city=london&limit=50`

**Statistical Analysis**
- `GET /analytics/stats/hypothesis-tests?city=amsterdam` — H1–H5 test results
- `GET /analytics/stats/regression/coefficients?city=london`
- `GET /analytics/stats/regression/summary?city=amsterdam`

**Cross-City Comparisons** (no `city` param — always both cities)
- `GET /analytics/comparison/cities`
- `GET /analytics/comparison/room-types`

**Reports**
- `GET /analytics/reports/eda-findings` — full EDA findings (Markdown)

---

### ML — Price Prediction (`/analytics/ml`)

**Read endpoints** — serve pre-computed artifacts:

- `GET /analytics/ml/model-card?city=london` — 35-key model card (metrics, hyperparameters, feature list, bias findings, artifact paths)
- `GET /analytics/ml/model-comparison?city=london` — all models vs baselines (MAE, MAPE, R², within-20%)
- `GET /analytics/ml/cv-results?city=london` — 5-fold grouped CV results
- `GET /analytics/ml/feature-importance?city=london&method=permutation&top_n=20` — permutation or SHAP importance
- `GET /analytics/ml/residuals?city=london&limit=500` — test-set residuals (filterable by room_type, neighbourhood, price_band)
- `GET /analytics/ml/residuals/by-segment?city=london&segment=neighbourhood` — aggregated MAE per segment (neighbourhood | room_type | price_band | property_type | host_segment)

**Live inference:**

- `POST /analytics/ml/predict` — live LightGBM price prediction

  Required fields: `accommodates`, `room_type`, `neighbourhood_cleansed`
  All other fields optional (pipeline median-imputes missing values)

  ```json
  {
    "city": "london",
    "accommodates": 2,
    "room_type": "entire_home",
    "neighbourhood_cleansed": "Camden",
    "bedrooms": 1,
    "availability_365": 200,
    "review_scores_rating": 4.7,
    "amenity_count": 30
  }
  ```

  Returns: `predicted_price_gbp`, `model_used`, `city`, `warning` (if luxury or hotel_room)

---

### Clustering — Market Segmentation (`/analytics/clustering`)

**Read endpoints:**

- `GET /analytics/clustering/profile?city=london` — 5-cluster profile table (cluster_name, n, pct_of_city, median_price, feature stats, room-type breakdown)
- `GET /analytics/clustering/elbow?city=london` — k=2..10 elbow sweep (inertia + silhouette per k)
- `GET /analytics/clustering/labels?city=london&cluster=2&room_type=entire_home&limit=100` — paginated listing → cluster assignments (filterable by cluster ID, room_type, neighbourhood)

**Live cluster assignment:**

- `POST /analytics/clustering/assign` — assign a new listing to a market segment

  Only `city` is required. Missing features are imputed from training medians.

  ```json
  {
    "city": "london",
    "price_numeric": 150.0,
    "latitude": 51.508,
    "longitude": -0.128,
    "accommodates": 2,
    "bedrooms": 1,
    "availability_365": 180,
    "review_scores_rating": 4.8,
    "reviews_per_month_calc": 1.2,
    "amenity_count": 25
  }
  ```

  Returns: `cluster_id`, `cluster_name`, `city`, `imputed_features` (list of features filled from training medians), `features_used` (full feature vector sent to the model)

  Derived inputs accepted:
  - `price_numeric` → `log_price` (log1p applied internally)
  - `latitude` + `longitude` → `distance_to_centre_km` (haversine to Trafalgar Square / Dam Square)

---

### Host Segmentation (`/analytics/clustering/host-*`)

K-Means clustering at the **host level** — one row per host aggregated across their entire portfolio. Features capture portfolio size, tenure, responsiveness, pricing, availability, and property-type mix.

**Named segments:**

| City | Cluster | Name | Hosts | % | Key signal |
|---|---|---|---|---|---|
| London | 0 | Passive Listers | 6,788 | 12.2% | Response 53%, acceptance 24% — listed but disengaged |
| London | 1 | Professional Superhosts | 9,925 | 17.8% | 79% superhost, 4+ listings, 1.47 reviews/month |
| London | 2 | Occasional Hosts | 38,933 | 70.0% | 0% superhost, 99% response, only 81 avail days/year |
| Amsterdam | 0 | Active Superhost Operators | 1,270 | 13.8% | 65% superhost, 2.83 reviews/month, 24% entire home |
| Amsterdam | 1 | Part-Time Apartment Hosts | 7,931 | 86.2% | 97% entire home, 71 avail days, €225 median price |

**Read endpoints:**

- `GET /analytics/clustering/host-profile?city=london` — host cluster profiles (segment name, n, pct_of_city, median_avg_price, pct_superhost, mean response/acceptance rates, availability, reviews/month)
- `GET /analytics/clustering/host-elbow?city=london` — k=2..8 elbow sweep for hosts
- `GET /analytics/clustering/host-labels?city=london&cluster=1&limit=100` — paginated host → cluster assignments, filterable by cluster ID

**Live host cluster assignment:**

- `POST /analytics/clustering/host-assign` — assign a host profile to a segment

  Only `city` is required. All 13 host features are optional — missing values are imputed from training medians.

  `host_response_rate` and `host_acceptance_rate` are **0–1 fractions** (e.g. `0.95`, not `95`). `pct_entire_home` is **0–100**.

  ```json
  {
    "city": "london",
    "listing_count": 5,
    "host_is_superhost": 1,
    "host_response_rate": 0.99,
    "host_acceptance_rate": 0.92,
    "avg_price": 160.0,
    "avg_availability_365": 180.0,
    "avg_review_scores_rating": 4.85,
    "avg_reviews_per_month": 1.8,
    "pct_entire_home": 60.0
  }
  ```

  Returns: `cluster_id`, `cluster_name`, `city`, `imputed_features`, `features_used`

---

### Warehouse / Star Schema (`/warehouse`)

Each city has its own DuckDB warehouse at `data/processed/{city}/warehouse.duckdb`.
Schema: 5 dimension tables + 3 fact tables.

- `GET /warehouse/tables?city=amsterdam` — table list with row counts
- `GET /warehouse/queries` — available named SQL queries
- `GET /warehouse/queries/{name}?city=london` — run a named query
- `GET /warehouse/queries/{name}/sql` — return the raw SQL
- `POST /warehouse/build?city=amsterdam` — build dimensions then facts

### Quality Checks (`/quality`)

- `GET /quality/latest?city=london` — most recent test run results
- `GET /quality/runs?city=london&limit=20` — run history
- `POST /quality/run?city=amsterdam` — execute full test suite (~2s)

### Orchestration (`/orchestration`)

Stages: `ingest → profile → clean → transform → load`. Idempotent by default.

- `POST /orchestration/run?city=london&stages=all` — full pipeline
- `POST /orchestration/run?city=london&stages=clean,transform` — subset
- `POST /orchestration/run?city=amsterdam&stages=all&force=true` — re-run
- `GET /orchestration/runs?city=london` — run history
- `GET /orchestration/lineage` — source → warehouse lineage (Markdown)

### Enrichment (`/enrichment`)

- `GET /enrichment/listing-master?city=london&n=5`
- `POST /enrichment/all?city=amsterdam` — chain all enrichment steps

### Cleaning (`/cleaning`)

- `GET /cleaning/listings?city=amsterdam&n=5`
- `POST /cleaning/all?city=amsterdam`

### Ingestion & Profiling (`/ingestion`)

- `GET /ingestion/manifest` — file manifest
- `GET /ingestion/quality-report` — full quality report (HTML)
- `POST /ingestion/all?city=amsterdam`

### Dataset Familiarization (`/familiarization`)

- `GET /familiarization/schema` — column names, types, sample values
- `GET /familiarization/assumptions` — 36 documented field assumptions (A-001–A-036)
- `GET /familiarization/limitations` — coverage gaps and scraping artifacts

---

## Architecture Notes

### One source of truth

Every pipeline step is a Python module with a `run()` function. Both the FastAPI endpoint and the CLI wrapper call `run()` — there is no duplicated logic.

### City parameterisation

All paths, currency codes, and snapshot dates come from `config/cities.yml`. Nothing is hardcoded per city inside the code. Adding a third city requires only a new entry in that file.

### ML pipeline

- **Target**: `log1p(price_numeric)` — log-price stabilises the heavy right skew and reduces luxury-listing leverage
- **Preprocessing**: `TargetEncoder` on `neighbourhood_cleansed` + `room_type`, `StandardScaler` on numeric features, median imputation for missing values — all inside a single `sklearn.Pipeline`
- **Grouped split**: `GroupShuffleSplit(groups=host_id)` ensures a host's listings never appear in both train and test sets
- **Explainability**: SHAP via `TreeExplainer` on the final estimator after preprocessing; permutation importance on the full pipeline with 15 repeats

### Listing clustering pipeline

- **Features**: 9 features — `log_price`, `accommodates`, `bedrooms`, `minimum_nights`, `availability_365`, `review_scores_rating`, `reviews_per_month_calc`, `distance_to_centre_km`, `amenity_count`
- **Pre-transform**: `log1p` applied to `minimum_nights`, `bedrooms`, `reviews_per_month_calc` before `StandardScaler`
- **k selection**: elbow sweep k=2..10; k=5 chosen for both cities (no hard elbow; maps to five interpretable market tiers)
- **Segment naming**: priority-ordered rule system on aggregated cluster statistics, with price-rank fallback

### Host clustering pipeline

- **Unit of analysis**: one row per host (aggregated from `listing_master.parquet`)
- **Features**: 13 features — `listing_count`, `host_tenure_years`, `host_response_rate`, `host_acceptance_rate`, `host_is_superhost`, `avg_price`, `avg_availability_365`, `avg_review_scores_rating`, `avg_reviews_per_month`, `avg_accommodates`, `avg_minimum_nights`, `pct_entire_home`, `neighbourhood_count`
- **Pre-transform**: `log1p` applied to `listing_count`, `avg_price`, `avg_minimum_nights` before `StandardScaler` (all three are strongly right-skewed)
- **k selection**: elbow sweep k=2..8; London k=3 (silhouette peak 0.266), Amsterdam k=2 (silhouette peak 0.366)
- **Imputation**: `host_response_rate` (~57% NA in London) and `host_acceptance_rate` (~50% NA) imputed with column medians — hosts with no recorded rate have never responded

---

## Adding a New City

1. Add an entry to `config/cities.yml`:
   ```yaml
   paris:
     listings_url: https://data.insideairbnb.com/...
     snapshot_date: "2025-09-01"
     currency_code: EUR
   ```
2. Run `POST /orchestration/run?city=paris&stages=all`
3. Run `POST /quality/run?city=paris`
4. Run `python -m src.features.listing_features paris` → train model → cluster
5. All `/analytics/*?city=paris` endpoints automatically serve the new city
