# Airbnb Assessment — London Pipeline

Inside Airbnb data pipeline for the Experne'c Talent Assessment.
**FastAPI is the canonical interface.** Every phase step is exposed as
an endpoint; CLI wrappers (`python -m src.X.Y`) still exist and call the
same functions.

City: **London** · Snapshot: **2025-09-14** · Source: https://insideairbnb.com/get-the-data/

## Layout

```
config/    city configuration (URLs, snapshot dates)
data/      raw / staging / processed / quality_reports (gitignored)
src/
  api/         FastAPI application + routes
  ingestion/   downloader + manifest
  profiling/   inventory, schema, key_integrity, extended_profile, duplicates, outliers, enrich_schema
  cleaning/    (Phase 2.2)
  validation/  quality_report + (Phase 2.6) pytest data-quality assertions
  transformation/  (Phase 2.3)
  loading/         (Phase 2.4)
sql/       analytical SQL against the DuckDB warehouse (Phase 2.4)
tests/     pytest data-quality assertions
notebooks/ exploration and familiarization
reports/   generated profiling and quality reports
logs/      pipeline run logs (gitignored)
```

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the API

```
uvicorn src.api.app:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Endpoint map

### Meta
- `GET /index`, `GET /health`

### Cities (`src/api/routes/cities.py`)
- `GET /cities` — list configured cities
- `GET /cities/{code}` — full city config

### Dataset Familiarization (`src/api/routes/familiarization.py`)
Reads:
- `GET /familiarization/inventory` (JSON)
- `GET /familiarization/file-purpose` (Markdown)
- `GET /familiarization/notebook` (metadata)
- `GET /familiarization/schema` (JSON)
- `GET /familiarization/key-integrity` (Markdown)
- `GET /familiarization/business-entities` (Markdown)
- `GET /familiarization/special-fields` (Markdown)
- `GET /familiarization/limitations` (Markdown)
- `GET /familiarization/assumptions` (Markdown)

Triggers (in-process, sync):
- `POST /familiarization/inventory:rebuild?city=london`
- `POST /familiarization/schema:rebuild?city=london`
- `POST /familiarization/schema:annotate`
- `POST /familiarization/key-integrity:rebuild`

### Ingestion & Profiling (`src/api/routes/ingestion.py`)
Reads:
- `GET /ingestion/manifest` (CSV→JSON)
- `GET /ingestion/profile` (JSON)
- `GET /ingestion/duplicates` (Markdown), `/duplicates/listings`, `/duplicates/review-templates`
- `GET /ingestion/outliers` (Markdown), `/outliers/iqr`, `/outliers/domain`
- `GET /ingestion/quality-report` (HTML)

Triggers:
- `POST /ingestion/ingest?city=london&force=false`
- `POST /ingestion/profile:run?city=london`
- `POST /ingestion/duplicates:run?city=london`
- `POST /ingestion/outliers:run?city=london`
- `POST /ingestion/quality-report:rebuild?city=london`
- `POST /ingestion/all?city=london` — chain everything

## How adding a new step works

Every pipeline step ships as three things:

1. **A `run()` function** in `src/<area>/<step>.py` returning the standard `make_result()` dict shape.
2. **A thin CLI wrapper** (`main()` in the same file) for shell users.
3. **A FastAPI endpoint** in `src/api/routes/phaseN.py` that calls `run()` directly.

The CLI and the API endpoint always call the same function — there is one truth.

## Convention going forward

- Each new engineering layer gets a semantically-named route module: `cleaning.py`, `enrichment.py`, `warehouse.py`, `orchestration.py`, `quality.py`. **No `phase*.py` filenames.**
- No new shell-only scripts; every new step ships with a FastAPI endpoint.
- Long-running triggers stay sync for now; if any exceeds 5 minutes we'll switch to FastAPI BackgroundTasks per-route.
