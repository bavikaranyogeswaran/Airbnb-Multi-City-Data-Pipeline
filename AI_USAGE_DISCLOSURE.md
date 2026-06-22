# AI Usage Disclosure

**Appendix A — Assessment Section 10.1 Compliance**
Expernetic Talent Assessment · Data Engineer Intern · June 2026

---

## A.1 AI Tools Used

| Tool | Model / Version | Purpose |
|---|---|---|
| **Claude Code** | claude-sonnet-4-6 (Anthropic) | Primary AI coding assistant — used across all phases of the project |
| **Groq API** | llama-3.3-70b-versatile | In-product LLM integration: narrative summaries + Text-to-SQL (§9 feature, not a development aid) |

No other AI tools (ChatGPT, Gemini, GitHub Copilot, Cursor, etc.) were used during this assignment.

---

## A.2 AI-Assisted Sections

The following table identifies every part of the submission that involved Claude Code assistance and the nature of that assistance.

| Component | AI Involvement | Human Involvement |
|---|---|---|
| **Data ingestion pipeline** (`src/ingestion/`) | Scaffolded boilerplate; city-agnostic download and extraction pattern | Designed idempotency strategy; chose manifest format; tested against live URLs |
| **Data cleaning** (`src/cleaning/`) | Generated price parsing, date standardisation, null-handling stubs | Reviewed all rejection rules; adjusted thresholds against actual data distributions |
| **DuckDB star schema** (`sql/`, `src/loading/`) | Drafted initial dimension/fact table DDL | Redesigned schema after reviewing column semantics; added SCD-2 placeholders on `dim_host` |
| **Feature engineering** (`src/features/`) | Generated ML feature matrix and clustering feature extraction code | Selected features based on domain knowledge; validated against correlation analysis |
| **ML pipeline** (`src/models/train_price_model.py`, `evaluate.py`, `explain.py`) | Scaffolded LightGBM pipeline with `GroupShuffleSplit`; SHAP integration | Chose grouped split (host_id) after identifying leakage risk; interpreted SHAP outputs manually |
| **K-Means clustering** (`src/models/cluster_listings.py`, `cluster_hosts.py`) | Generated elbow sweep and silhouette scoring loops | Manually reviewed cluster profiles; wrote all segment names and business interpretations |
| **EDA + statistical analysis** (`src/analytics/run_eda.py`) | Generated Mann-Whitney / Kruskal-Wallis test harness | Selected hypotheses; checked test assumptions; wrote all business interpretations |
| **LLM integration** (`src/llm/`) | Scaffolded Groq client, prompt templates, schema inspector, SQL runner | Designed prompt structure; added read-only guard; tested SQL generation across edge cases |
| **FastAPI service** (`src/api/`) | Generated router stubs and Pydantic models | Designed endpoint taxonomy; added imputation logic; debugged DuckDB concurrency constraint |
| **React dashboard** (`dashboard/`) | Generated page scaffolding, Recharts integration, Leaflet choropleth setup | Designed information architecture (8 pages); wrote all chart labels and business commentary |
| **pytest data quality suite** (`tests/`) | Generated test stubs | Wrote domain-specific assertions; tuned pass thresholds against real data |
| **Docker + Compose** (`Dockerfile.*`, `docker-compose.yml`) | Generated Dockerfile and Compose config | Resolved nginx reverse-proxy routing; diagnosed uvicorn single-worker DuckDB constraint |
| **PDF report** (`scripts/generate_report.py`) | Generated reportlab document structure | Wrote all section content, business interpretations, and findings narratives |
| **PPTX presentation** (`scripts/generate_presentation.py`) | Generated python-pptx layout code | Designed slide structure; wrote all narrative text; chose data to highlight per slide |
| **Architecture diagram** (`reports/architecture.svg`, `reports/architecture.html`) | Generated SVG/HTML layout | Reviewed for accuracy; stripped unnecessary detail; verified against actual system |
| **README.md** | Assisted with structure and endpoint documentation | Wrote all business context, NYC edge case note, and all non-trivial prose |
| **Engineering decisions log** (`reports/engineering_decisions.md`) | Assisted with formatting | Wrote all decision rationale from direct experience of the trade-offs |
| **Assumptions log** (`reports/assumptions_log.md`) | Assisted with structuring A-001–A-036 entries | Identified all assumptions from direct data exploration |

---

## A.3 Key Prompts Used

The following prompts are representative of the interactions that shaped significant parts of the submission. Full conversation history is available in the local Claude Code session logs.

### A.3.1 Pipeline Architecture

> "Design a city-agnostic ingestion pipeline for Inside Airbnb data. It should download listings.csv.gz, calendar.csv.gz, and reviews.csv.gz for any city specified in a YAML config file, extract them, and produce a data quality report. The pipeline must be idempotent — re-running should not re-download if files already exist."

*Outcome:* Produced the initial `src/ingestion/` structure. The YAML config approach (`config/cities.yml`) and manifest file format were accepted as proposed. The retry logic was modified to use exponential backoff rather than the simple `time.sleep` stub generated.

### A.3.2 DuckDB Star Schema

> "Design a star schema for Airbnb listings data suitable for analytical queries. Tables should support: price analysis by neighbourhood and room type, host portfolio analysis, temporal review trends, and occupancy estimation from calendar data. Implement it in DuckDB."

*Outcome:* Initial schema had 3 dimensions and 2 facts. Reviewed against the actual data and added `dim_neighbourhood`, expanded `fact_calendar` to include price columns, and added SCD-2 fields (`valid_from`, `valid_to`, `is_current`) to `dim_host` which the AI had not included.

### A.3.3 ML Pipeline — Grouped Split

> "Train a LightGBM price prediction model on Airbnb listings. Use log1p(price) as the target. Prevent data leakage where the same host's listings appear in both train and test. Apply SHAP for feature importance."

*Outcome:* The `GroupShuffleSplit(groups=host_id)` approach was proposed and accepted. The TargetEncoder for neighbourhood was added after reviewing that one-hot encoding produced 300+ sparse columns. The cross-city transfer experiment (train on London, evaluate on Amsterdam) was designed independently after noticing the TargetEncoder would fail across markets.

### A.3.4 LLM Text-to-SQL Safety

> "Build a Text-to-SQL endpoint that takes a natural language question, generates a DuckDB SELECT statement using Groq, executes it, and returns the result with a plain-English explanation. Add a guard that prevents any non-SELECT statement from executing."

*Outcome:* The read-only guard (`if not sql.strip().upper().startswith('SELECT')`) was in the generated output. Added schema-aware prompt injection (actual table names and column types from the warehouse) independently — the initial prompt template used a generic schema description that would not generalise across cities.

### A.3.5 Statistical Analysis

> "Run Mann-Whitney U tests for H1 (entire home vs private room prices) and H2 (superhost vs non-superhost review scores). Report test statistic, p-value, and a narrative effect size label. Use alpha = 0.05."

*Outcome:* Generated the test harness. Effect size labels ("Large", "Small") were narrative only — the rubric requirement for Cohen's d and eta-squared was identified independently by reading §5.2 of the assessment. This gap remains partial.

### A.3.6 FastAPI Routing

> "I have 10 different analytical modules (ingestion, cleaning, warehouse, EDA, ML, clustering, LLM, quality, orchestration, familiarization). Design a FastAPI application with separate routers for each. The DuckDB warehouse can only handle one connection at a time — address this."

*Outcome:* Router structure accepted as generated. The single-writer DuckDB constraint prompted `uvicorn --workers 1` guidance which was added to README and Docker config. The `--reload` flag removal in production was caught independently.

---

## A.4 Output Validation

| Validation Method | Applied To |
|---|---|
| **Manual code review** — read every generated function before accepting | All `src/` modules |
| **Unit tests** — 13/13 pytest checks pass against real data | Ingestion, cleaning, warehouse |
| **Live API testing** — every endpoint hit via `/docs` Swagger UI or curl | All 50+ FastAPI endpoints |
| **Data sanity checks** — medians, row counts, and distributions verified against raw CSV values | EDA CSVs, ML predictions, clustering profiles |
| **Cross-city consistency** — same pipeline re-run for Amsterdam, Madrid, Berlin; outputs compared | Full pipeline |
| **EC2 deployment** — full stack deployed and tested at live URL | Docker Compose, nginx, FastAPI, React |
| **PDF + PPTX** — generated files opened and reviewed page by page | `airbnb_intel_report.pdf`, `presentation.pptx` |

---

## A.5 Modifications Made to AI-Generated Output

| Component | Original AI Output | Modification Made |
|---|---|---|
| `GroupShuffleSplit` | Used `train_test_split` (random) | Replaced with group-based split on `host_id` to prevent leakage |
| `dim_host` schema | No temporal tracking | Added `valid_from`, `valid_to`, `is_current` SCD-2 columns |
| DuckDB concurrency | No worker limit mentioned | Added `--workers 1` constraint and documented reason |
| LLM prompt template | Generic schema description | Replaced with live schema injection from `schema_inspector.py` |
| Cluster segment names | Auto-generated generic labels | Replaced all labels with interpretable business names (e.g. "Passive Listers", "High-Turnover City Lets") |
| `superhost_rate` formatting | Displayed as fraction (0.161) | Multiplied by 100 throughout API responses and dashboard |
| Print statements (Windows) | Used emoji characters (✅, →) | Replaced with ASCII to fix `cp1252` encoding errors on Windows |
| Hypothesis test effect sizes | Narrative label only | Identified Cohen's d / eta-squared gap; documented as partial deliverable |
| `TargetEncoder` cross-city | Not flagged as issue | Designed and documented cross-city transfer experiment independently |

---

## A.6 Cases Where AI Suggestions Were Rejected or Substantially Modified

| Suggestion | Reason Rejected |
|---|---|
| **Using `git add -A` in commit guidance** | Risk of accidentally committing `.env` / API keys — rejected in favour of explicit file staging |
| **Caching LLM responses in Redis** | Over-engineered for a single-server deployment — replaced with simple disk cache (JSON files in `reports/llm_summaries/`) |
| **DBSCAN for listing clustering** | DBSCAN requires careful epsilon tuning per city and produces noise points that complicate interpretation — K-Means with elbow sweep chosen instead for consistency across 4 cities |
| **Feature correlation matrix as live endpoint** | Computing a 36×36 Pearson matrix per API request is unnecessarily expensive — pre-computation approach designed but not yet implemented |
| **`--reload` flag in production Dockerfile** | AI generated `uvicorn ... --reload` in the Docker entrypoint — removed as file-watching is inappropriate in a container |
| **Separate DuckDB file per pipeline run** | AI suggested timestamped warehouse files for versioning — rejected because it breaks all read endpoints; single `warehouse.duckdb` per city with idempotent build retained |
| **`streamlit` as the dashboard framework** | `requirements.txt` includes Streamlit but it was superseded by a full React + Vite + Tailwind dashboard for richer interactivity and production suitability |

---

*This disclosure was prepared in accordance with Section 10 of the Expernetic Talent Assessment brief. All AI-generated code was reviewed, tested, and validated before inclusion in the submission.*
