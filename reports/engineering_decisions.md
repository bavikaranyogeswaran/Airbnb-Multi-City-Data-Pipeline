# Engineering Decision Log

Every non-trivial engineering choice the pipeline depends on is recorded
here using the template the assessment plan prescribes:

> Decision ID · Problem · Options considered · Selected option · Reason · Trade-offs · Future improvement

Decisions are listed by area; numbering is stable so external documents
can reference `D-NNN`.

---

## Storage and processing

### D-001 · Analytical engine: DuckDB
- **Problem.** Need a SQL engine that supports the 35M-row calendar facts + dim/fact joins on a developer laptop.
- **Options considered.** PostgreSQL, SQLite, DuckDB, ClickHouse-local.
- **Selected.** DuckDB.
- **Reason.** Columnar, vectorized, zero-config, reads Parquet directly with no copy, supports `MEDIAN`/`NTILE`/window functions used by the analytical SQL. Composite-key uniqueness on 35M rows runs in 0.8 s during the quality tests.
- **Trade-offs.** Single-node only; not suitable for concurrent writes from many clients. The SCD-2 columns on `dim_host` are placeholders — a multi-writer scenario would need stronger transactional guarantees than the current single-process pipeline.
- **Future.** Lift-and-shift to PostgreSQL or BigQuery for production multi-writer workloads. The Parquet layer is the portable interface.

### D-002 · Storage format: Parquet for the cleaned + enriched layer
- **Problem.** 35.4M-row calendar + 2.1M reviews need to round-trip cheaply across pipeline steps.
- **Options considered.** CSV, Parquet, native DuckDB tables, Arrow IPC files.
- **Selected.** Parquet (compressed columnar).
- **Reason.** Calendar lands at **14.6 MB on disk for 35M rows** (vs ~1.2 GB CSV) due to dictionary encoding of repeated dates and listing IDs. DuckDB reads Parquet directly with predicate pushdown.
- **Trade-offs.** Per-row appends are awkward (full rewrite). The incremental design accepts this — daily/weekly partitions are planned when a 2nd snapshot lands.
- **Future.** Partition `fact_calendar` parquet by `year=/month=/` once an automated cadence exists.

### D-003 · One warehouse file per city
- **Problem.** Where do metadata + dims + facts live as snapshots accumulate?
- **Options considered.** Single global warehouse, one DB per city, one DB per (city, snapshot).
- **Selected.** One `warehouse.duckdb` per city; metadata tables live alongside dims/facts.
- **Reason.** Keeps the cross-table joins local, eliminates cross-database planner overhead, and the file is portable to S3/object storage.
- **Trade-offs.** Cross-city queries require a federation step (DuckDB's `ATTACH` works but adds complexity).
- **Future.** A wrapper `analytics.duckdb` that ATTACHes each city DB for cross-city analytics.

---

## Pipeline architecture

### D-004 · FastAPI as the canonical interface
- **Problem.** Every step needs to be runnable by both shell users and downstream services without code duplication.
- **Options considered.** CLI-only, Prefect/Airflow orchestrator, REST API, GraphQL.
- **Selected.** FastAPI + thin CLI wrappers; each pipeline step is a `run()` function called identically from either surface.
- **Reason.** OpenAPI docs come for free, the API surface mirrors phase structure (`/familiarization`, `/ingestion`, `/cleaning`, …), and structured JSON responses replace stdout-parsing for downstream automation.
- **Trade-offs.** Adds an HTTP framework dependency. Long-running steps (calendar profile ~30 s, full pipeline ~3.5 min) block the request; an async/`BackgroundTasks` migration is queued for when any single step crosses 5 min.
- **Future.** Switch the orchestrator's `run` endpoint to FastAPI BackgroundTasks with a polling pattern.

### D-005 · Trigger endpoints call `run()` in-process, not via subprocess
- **Problem.** How should an HTTP trigger invoke the underlying worker?
- **Options considered.** `subprocess.run("python -m src.X.Y …")`, in-process function call, Celery worker queue.
- **Selected.** In-process call to a shared `run(city)` function; the CLI `main()` and the FastAPI endpoint both call it.
- **Reason.** Single source of truth, structured return value (not stdout parsing), exceptions surface as proper HTTP errors. No extra process-startup cost.
- **Trade-offs.** A bad step can crash the API server's worker thread (mitigated by FastAPI's per-request error boundary). No process isolation.
- **Future.** If we need isolation for untrusted operations, swap to Celery without changing the route signatures.

### D-006 · Single-stage orchestrator vs full workflow engine
- **Problem.** Need stage sequencing, retries, idempotency, metadata persistence, logging.
- **Options considered.** Prefect, Airflow, Dagster, a bespoke orchestrator.
- **Selected.** Bespoke `src/orchestration/pipeline.py` with explicit `STAGE_STEPS` table.
- **Reason.** The assessment is one-week, one-city; an external orchestrator would dominate the codebase. The chosen design is ~150 lines and exposes everything the plan calls for: stages, logging, idempotency, retries (in network step), metadata.
- **Trade-offs.** No distributed execution, no dependency DAG visualisation, no out-of-the-box scheduling. The compromise is acceptable for a single-worker pipeline.
- **Future.** Wrap the existing `pipeline.run()` in a Prefect flow when scheduling / parallelism is required.

### D-007 · Idempotency via `dataset_version` table + manifest SHA-256
- **Problem.** Re-running the full pipeline on the same snapshot wastes 3+ minutes.
- **Options considered.** Filesystem mtime checks, content hashes per file, full warehouse state hash, registry table.
- **Selected.** A `dataset_version` registry keyed by `(city, snapshot_date)` with the ingestion manifest's SHA-256.
- **Reason.** Cheap to query, survives manifest edits (hash changes), and `force=true` is a one-arg override.
- **Trade-offs.** Only catches snapshot-level changes; a corrupt parquet that still hashes the same passes the gate. Mitigated by the pytest quality suite running on every full pipeline.
- **Future.** Per-table content hashes for finer-grained invalidation.

---

## Data modelling

### D-008 · Star schema with SCD-2 placeholders on `dim_host`
- **Problem.** Host attributes (`host_is_superhost`, `host_response_rate`) change between snapshots.
- **Options considered.** SCD-0 (overwrite), SCD-1 (always-current), SCD-2 (versioned rows), event sourcing.
- **Selected.** SCD-2 column layout (`valid_from`, `valid_to`, `is_current`) populated SCD-1-style for the single snapshot.
- **Reason.** Schema is forward-compatible without runtime overhead; loading a 2nd snapshot only requires updating the close logic, not adding columns.
- **Trade-offs.** Today there is exactly one current row per host; users could be confused if they expect history.
- **Future.** Implement the SCD-2 close step when the 2nd snapshot arrives.

### D-009 · Surrogate keys via `ROW_NUMBER()` on stable orderings
- **Problem.** Cross-city joins need stable surrogate keys; source IDs can clash across cities.
- **Options considered.** Source IDs as natural keys, ROW_NUMBER surrogates, UUIDs.
- **Selected.** Integer surrogates from `ROW_NUMBER() OVER (ORDER BY <stable_column>)` for the dim tables.
- **Reason.** Compact, indexable, joinable. The "stable order" guarantees the same key emerges on each rebuild within a city.
- **Trade-offs.** A new neighbourhood inserted between two existing ones could renumber later rows. Acceptable because the source data set is fixed within a snapshot.
- **Future.** Hash-based deterministic surrogates if cross-snapshot key stability becomes important.

### D-010 · `dim_date` covers 2008-01-01 → 2027-01-01 (19 years)
- **Problem.** Calendar dates reach 2026; review dates reach back to 2009-12-21.
- **Options considered.** Tight bounds (calendar window), generous bounds (1970-2100), match observed data.
- **Selected.** 2008-2027 with a deliberate 2-year buffer on each side.
- **Reason.** The earlier pytest run caught a real bug — initial `dim_date` started 2010-01-01 and `test_reviews_quality.py::test_referential_integrity_to_dim_date` failed. The 2-year buffer prevents future review-date drift from regressing this check.
- **Trade-offs.** `dim_date` carries 6,941 unused rows. Negligible at this scale.
- **Future.** Auto-detect required bounds from source data ranges at build time.

### D-011 · Five-bucket `property_type` coarsening
- **Problem.** Source `property_type` has 91 distinct values, heavy long tail.
- **Options considered.** Use raw type as-is, top-N + "other", coarse bucketing, learned clustering.
- **Selected.** Five buckets (`apartment / house / hotel / unique / other`) **with the raw value retained alongside** as `property_type`.
- **Reason.** Most stakeholder questions group by the coarse bucket; raw value stays for drill-down. Bucketing rules are explicit and reviewable in `src/cleaning/transforms.py::bucket_property_type`.
- **Trade-offs.** A new exotic property type ("ice hotel"?) falls into "other" until the rule list is updated.
- **Future.** Periodically inspect the `other` cohort and promote sub-buckets.

---

## Cleaning rules

### D-012 · INT_MAX sentinels → NULL for stay-rule fields
- **Problem.** `maximum_nights = 2,147,483,647` (= 2³¹−1) appears in 4,708 calendar rows; treating it as a real maximum corrupts stats (mean → ~2 billion).
- **Options considered.** Keep raw, cap at a high but plausible value (e.g. 365 × 5), replace with NULL.
- **Selected.** Replace any value `≥ 2³⁰` with NULL via `cap_sentinel_intmax`.
- **Reason.** Honest: the value means "host did not specify". NULL is the correct semantic representation.
- **Trade-offs.** Downstream aggregates must handle NULL explicitly; we use `AVG(maximum_nights) FILTER (WHERE maximum_nights IS NOT NULL)` patterns.
- **Future.** None — this is the right answer for sentinel values.

### D-013 · Listings with null `price` are excluded, not imputed
- **Problem.** 36.04% of listings have a null `price`.
- **Options considered.** Drop the listings, impute (median by room+borough), impute (regression), keep NULL and exclude from price analyses.
- **Selected.** Keep NULL, exclude from price-based analyses, document the cohort.
- **Reason.** 36% is too large a missing cohort to impute defensibly without first understanding *why* they are missing. The current `data_quality_report.html` documents the cohort; future Phase 2.1 follow-up can profile it.
- **Trade-offs.** Price analyses run on 64% of supply; conclusions need that caveat in the final report.
- **Future.** Profile the null-price cohort against neighbourhood and room-type distributions; revisit imputation if MAR is plausible.

### D-014 · `bathrooms_text` is canonical over numeric `bathrooms`
- **Problem.** Source numeric `bathrooms` field loses the private-vs-shared encoding.
- **Options considered.** Use numeric as-is, derive only the count from text, derive both count and shared flag.
- **Selected.** Parse `bathrooms_text` into `(bathroom_count, bathroom_is_shared)`; drop the redundant numeric column.
- **Reason.** Lossless transform. Regex fallback on "half" handles textual variants ("half bath").
- **Trade-offs.** Adds two columns to dim_listing. Cheap.
- **Future.** None — clean separation.

### D-015 · Currency code read from `config/cities.yml`, not hard-coded
- **Problem.** Source price field is stored as `$X.XX` for all cities regardless of local currency — a scraping artefact. Initial implementation hard-coded `"GBP"` in the cleaning layer.
- **Options considered.** Trust the dollar symbol, hard-code per file, read from a central config.
- **Selected.** `clean(df, currency_code)` receives the value from `cities.yml` via `run(city)`. London → `GBP`, Amsterdam → `EUR`. The default argument (`"GBP"`) preserves backward compatibility for unit tests that call `clean(df)` directly.
- **Reason.** Single source of truth in config; adding a third city requires only a new `currency_code` entry in `cities.yml`, no code change.
- **Trade-offs.** The three derived column names (`revenue_proxy_gbp`, `price_per_bedroom_gbp`, `neighbourhood_median_price_gbp`) still carry the `_gbp` suffix — see D-022.
- **Future.** Cross-city analysis layer will FX-convert at query time using the stored `currency_code` column.

---

## Quality and testing

### D-016 · Pytest with a custom plugin, not Great Expectations
- **Problem.** Need persistable data-quality results with row-level test logic.
- **Options considered.** Great Expectations, dbt tests, custom pytest + plugin, soda-core.
- **Selected.** Pytest + `_ResultCollector` plugin that captures `pytest_runtest_logreport` and persists to `data_quality_result`.
- **Reason.** No second tool to install, no opaque YAML grammar, every test is a one-screen Python function with full DuckDB access. Results table fits the same warehouse the data lives in.
- **Trade-offs.** Loses GE's built-in expectation library; we wrote 31 explicit checks instead. For *this* scope it's the right call.
- **Future.** Adopt Great Expectations if the rule count grows past ~100 and we need profile-driven expectation discovery.

### D-017 · Heuristic `rule_category` classification, not metadata-driven
- **Problem.** When showing past test runs, group tests by what kind of rule they check (uniqueness, range, referential, …).
- **Options considered.** Decorator-based metadata, separate metadata file, name-based heuristic.
- **Selected.** Regex-based classification of test function names in `quality_tests.py::_RULE_CATEGORIES`.
- **Reason.** Zero per-test overhead. New tests get categorised correctly as long as they follow the existing naming convention.
- **Trade-offs.** A poorly-named test ends up in `other`. The classification is documentation, not behaviour.
- **Future.** Add a `@pytest.mark.rule_category("…")` decorator if classification becomes load-bearing.

---

## Spatial

### D-018 · EPSG:27700 (British National Grid) for area + distance
- **Problem.** Raw GeoJSON is WGS 84 (degrees); using `geometry.area` on lat/lon produces wrong numbers at London latitudes (~37 % cosine distortion).
- **Options considered.** Web Mercator (EPSG:3857), Robinson, British National Grid (EPSG:27700), UK national grid variants.
- **Selected.** EPSG:27700 for projected work; WGS 84 for storage and centroid display.
- **Reason.** OSGB36 is the canonical projection for UK measurements; `dim_neighbourhood.area_km2` sums to 1,573 km² which matches Greater London's documented area.
- **Trade-offs.** Cross-city pipelines need a per-city projection lookup (already configurable via `config/cities.yml`'s `timezone`/`country_code` keys — a `projected_crs` key is the obvious extension).
- **Future.** Add `projected_crs` to `config/cities.yml`; default to a city-appropriate CRS automatically.

---

## Things deliberately deferred

These show up here because *not* doing them is itself a decision.

### D-022 · `_gbp` suffix retained on derived price columns
- **Problem.** Three columns in `listing_master.parquet` carry a `_gbp` suffix (`revenue_proxy_gbp`, `price_per_bedroom_gbp`, `neighbourhood_median_price_gbp`). After adding Amsterdam the suffix is misleading — Amsterdam values are in EUR.
- **Options considered.**
  - **A.** Rename columns to currency-neutral names (e.g. `revenue_proxy`, `price_per_bedroom`, `neighbourhood_median_price`) and rebuild both city datasets.
  - **B.** Leave column names unchanged; document the mismatch here; rely on the `currency_code` column as the authoritative currency indicator.
- **Selected.** Option B — leave names unchanged.
- **Reason.** The column schema must be identical across cities so that cross-city analytics code, the EDA notebooks, and the warehouse SQL can reference stable column names. Renaming now while EDA artefacts and downstream CSVs already reference `revenue_proxy_gbp` would create churn with no analytical benefit. The `currency_code` column (`"GBP"` or `"EUR"`) is the correct place to read currency — the suffix is purely cosmetic.
- **Trade-offs.** Anyone reading the parquet column name in isolation sees `_gbp` regardless of city. A code comment in `listing_master.py` flags this.
- **Future.** On the next schema version bump (e.g. when a third currency is added), rename to `_local_currency` suffix and update all references in one coordinated change.

---

## Things deliberately deferred

### D-019 · No Docker container shipped
- **Reason.** Adds environment-management overhead for what is currently a single-developer pipeline. The README's `pip install -r requirements.txt` works as documented.
- **Future.** Containerise when a CI environment needs a reproducible build (likely Phase 2.1 of a real deployment).

### D-020 · No dbt
- **Reason.** dbt's value (lineage, testing, materialisation) is duplicated by `src/loading/warehouse.py` + `src/validation/quality_tests.py` + `reports/lineage.md` at a smaller code footprint. dbt would dominate the project size.
- **Future.** Migrate the analytical SQL to dbt models if the SQL count grows past ~20 or if non-engineers need to contribute models.

### D-021 · No streaming / CDC
- **Reason.** Inside Airbnb publishes monthly-cadence snapshots. CDC has no source signal here.
- **Future.** Out of scope for this dataset.

---

## Decision index

| ID | Topic | Status |
|---|---|---|
| D-001 | DuckDB analytical engine | accepted |
| D-002 | Parquet storage | accepted |
| D-003 | One warehouse file per city | accepted |
| D-004 | FastAPI canonical interface | accepted |
| D-005 | In-process triggers | accepted |
| D-006 | Bespoke orchestrator | accepted |
| D-007 | Idempotency via dataset_version + SHA-256 | accepted |
| D-008 | SCD-2 placeholders on dim_host | accepted (forward-compatible) |
| D-009 | ROW_NUMBER surrogate keys | accepted |
| D-010 | dim_date 2008–2027 | accepted |
| D-011 | property_type 5-bucket coarsening | provisional |
| D-012 | INT_MAX sentinel → NULL | accepted |
| D-013 | Null `price` excluded, not imputed | provisional |
| D-014 | bathrooms_text canonical | accepted |
| D-015 | Currency code from cities.yml (not hard-coded) | accepted |
| D-022 | `_gbp` suffix retained on derived price columns | accepted (cosmetic, see note) |
| D-016 | Pytest + custom plugin | accepted |
| D-017 | Heuristic rule_category | accepted |
| D-018 | EPSG:27700 for projected geometry | accepted |
| D-019 | No Docker | deferred |
| D-020 | No dbt | deferred |
| D-021 | No streaming / CDC | n/a for this source |
