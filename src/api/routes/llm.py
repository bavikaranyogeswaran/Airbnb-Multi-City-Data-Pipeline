"""LLM-powered natural-language summary endpoints.

All endpoints call Groq (llama-3.3-70b-versatile by default) and cache
results to reports/llm_summaries/. A ?refresh=true query param bypasses
the cache and triggers a fresh API call.

Requires GROQ_API_KEY to be set in the environment.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.llm.client import DEFAULT_MODEL, call_once, generate
from src.llm.context_builder import (
    build_city_context,
    build_cluster_context,
    build_cross_city_context,
    build_host_context,
    build_model_context,
)
from src.llm.prompts import SQL_SYSTEM, SYSTEM, VALID_TYPES, render_explanation, render_sql
from src.llm import schema_inspector, sql_runner

router = APIRouter(prefix="/analytics/llm", tags=["llm"])

_CITY_BUILDERS = {
    "city":     build_city_context,
    "model":    build_model_context,
    "clusters": build_cluster_context,
    "hosts":    build_host_context,
}


def _run(
    summary_type: str,
    city: str | None,
    model: str,
    refresh: bool,
) -> dict:
    """Shared logic: build context → call generate → return response dict."""
    try:
        if summary_type == "cross_city":
            context = build_cross_city_context()
        else:
            if city is None:
                raise HTTPException(status_code=422, detail="city is required for this summary type")
            builder = _CITY_BUILDERS[summary_type]
            context = builder(city)

        text, cached = generate(
            context=context,
            summary_type=summary_type,
            city=city,
            model=model,
            refresh=refresh,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "city":    city,
        "type":    summary_type,
        "model":   model,
        "cached":  cached,
        "summary": text,
    }


# ── City-scoped summaries ──────────────────────────────────────────────────────

@router.get(
    "/summary",
    summary="LLM narrative for one city (city / model / clusters / hosts)",
)
def city_summary(
    city: str = Query("london", description="City code: london | amsterdam | madrid | berlin"),
    type: str = Query("city",   description="Summary type: city | model | clusters | hosts"),
    model: str = Query(DEFAULT_MODEL, description="Groq model ID"),
    refresh: bool = Query(False, description="Bypass cache and regenerate"),
) -> dict:
    """
    Generate a natural-language summary for one city.

    - **type=city** — market overview: size, prices, room mix, availability
    - **type=model** — price model performance: accuracy, feature drivers, bias
    - **type=clusters** — listing segment narrative across price tiers
    - **type=hosts** — host population characterisation by behaviour

    Results are cached to disk. Use `refresh=true` to force a new API call.
    """
    if type not in VALID_TYPES - {"cross_city"}:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type '{type}'. Choose from: city, model, clusters, hosts",
        )
    return _run(type, city, model, refresh)


# ── Cross-city comparison ──────────────────────────────────────────────────────

@router.get(
    "/cross-city",
    summary="LLM comparison narrative across all four cities",
)
def cross_city_summary(
    model: str = Query(DEFAULT_MODEL, description="Groq model ID"),
    refresh: bool = Query(False, description="Bypass cache and regenerate"),
) -> dict:
    """
    Generate a natural-language comparative analysis of London, Amsterdam,
    Madrid, and Berlin — covering price levels, supply structure, and
    ML model accuracy.

    Result is cached to reports/llm_summaries/cross_city.md.
    """
    return _run("cross_city", None, model, refresh)


# ── Cache management ───────────────────────────────────────────────────────────

@router.get(
    "/cache",
    summary="List all cached LLM summaries",
)
def list_cache() -> dict:
    """
    Return all cached summary files in reports/llm_summaries/,
    with their size in bytes and modification timestamp.
    """
    from src.llm.client import CACHE_DIR
    import datetime

    files = sorted(CACHE_DIR.glob("*.md"))
    entries = [
        {
            "file":     f.name,
            "bytes":    f.stat().st_size,
            "modified": datetime.datetime.fromtimestamp(
                f.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for f in files
    ]
    return {"cache_dir": str(CACHE_DIR), "count": len(entries), "files": entries}


# ── Text-to-SQL Q&A ───────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    city: str = "london"
    question: str
    model: str = DEFAULT_MODEL


@router.post(
    "/ask",
    summary="Natural-language Q&A — translates a question to SQL and explains the result",
)
def ask(body: AskRequest) -> dict:
    """
    Ask a natural-language question about one city's Airbnb data.

    **Flow:**
    1. Retrieve the warehouse schema for the requested city
    2. Call Groq to translate the question into a DuckDB SELECT statement
    3. Validate the SQL (only SELECT/WITH allowed; no mutation keywords)
    4. Execute the SQL against the DuckDB warehouse (read-only, max 50 rows)
    5. Call Groq again to explain the results in plain English

    **Response fields:**
    - `sql` — the exact statement that was executed
    - `rows` — up to 50 result rows as a list of objects
    - `row_count` — total rows returned
    - `explanation` — 2-3 sentence plain-English narrative of the findings
    """
    raw_sql: str | None = None

    try:
        schema_text = schema_inspector.get_schema(body.city)

        sql_prompt = render_sql(body.question, schema_text)
        raw_sql = call_once(SQL_SYSTEM, sql_prompt, body.model)

        clean_sql, rows = sql_runner.validate_and_run(raw_sql, body.city)

        exp_prompt = render_explanation(body.question, clean_sql, rows)
        explanation = call_once(SYSTEM, exp_prompt, body.model)

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": str(exc), "generated_sql": raw_sql},
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": str(exc), "generated_sql": raw_sql},
        )

    return {
        "city":        body.city,
        "question":    body.question,
        "model":       body.model,
        "sql":         clean_sql,
        "row_count":   len(rows),
        "rows":        rows,
        "explanation": explanation,
    }
