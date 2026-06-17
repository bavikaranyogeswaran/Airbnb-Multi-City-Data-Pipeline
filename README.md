# Airbnb Assessment

Inside Airbnb data pipeline for the Experne'c Talent Assessment.
Starts with London and scales via `config/cities.yml`.

## Layout

```
config/    city configuration (URLs, snapshot dates)
data/      raw / staging / processed / quality_reports  (gitignored)
src/       ingestion, profiling, cleaning, validation, transformation, loading
sql/       analytical SQL against the DuckDB warehouse
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

## Run (once implemented)

```
python -m src.pipeline --city london --snapshot-date 2025-09-14 --stage all
```

## Selected snapshot

London, United Kingdom · `2025-09-14` · source: https://insideairbnb.com/get-the-data/
