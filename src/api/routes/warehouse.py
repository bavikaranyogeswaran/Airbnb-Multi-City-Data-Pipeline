"""Data Modeling / Warehouse endpoints.

Star schema lives in `data/processed/<city>/warehouse.duckdb`. SQL
query files are auto-discovered from `sql/` (any `NN_*.sql` is
exposed under its filename stem).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query

from src.loading import warehouse as wh

from ..paths import ROOT

router = APIRouter(prefix="/warehouse", tags=["warehouse"])

SQL_DIR = ROOT / "sql"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-]+$")


def _resolve_sql(name: str):
    """Map a query name to its .sql file, with strict allowlist semantics."""
    if not _SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail="Invalid query name.")
    candidates = list(SQL_DIR.glob(f"{name}.sql")) + list(SQL_DIR.glob(f"*_{name}.sql"))
    candidates += list(SQL_DIR.glob(f"{name}_*.sql"))
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
    if not seen:
        raise HTTPException(status_code=404, detail=f"No SQL file matches '{name}'.")
    return seen[0]


@router.get("", summary="Warehouse index — all available endpoints")
def warehouse_index() -> dict:
    return {
        "area": "Data Modeling / Star-Schema Warehouse",
        "reads": {
            "tables":  "GET  /warehouse/tables?city=london",
            "queries": "GET  /warehouse/queries",
            "query":   "GET  /warehouse/queries/{name}?city=london",
            "sql":     "GET  /warehouse/queries/{name}/sql",
        },
        "triggers": {
            "dimensions":  "POST /warehouse/dimensions:run?city=london",
            "facts":       "POST /warehouse/facts:run?city=london",
            "build_all":   "POST /warehouse/build?city=london",
        },
    }


@router.get("/tables", summary="List warehouse tables with row counts")
def get_tables(city: str = Query("london")) -> list[dict]:
    try:
        return wh.list_tables(city)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.get("/queries", summary="List available analytical SQL queries")
def list_queries() -> list[dict]:
    return [
        {"name": p.stem, "path": str(p.relative_to(ROOT))}
        for p in sorted(SQL_DIR.glob("*.sql"))
    ]


@router.get("/queries/{name}", summary="Run a named SQL query and return rows")
def run_named_query(name: str, city: str = Query("london")) -> list[dict]:
    sql_path = _resolve_sql(name)
    sql_text = sql_path.read_text(encoding="utf-8")
    try:
        return wh.run_query(city, sql_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.get("/queries/{name}/sql", summary="Get the raw SQL text of a named query")
def get_named_sql(name: str) -> dict:
    sql_path = _resolve_sql(name)
    return {"name": sql_path.stem, "path": str(sql_path.relative_to(ROOT)),
            "sql": sql_path.read_text(encoding="utf-8")}


# ---------- triggers ----------

@router.post("/dimensions:run", summary="Build/rebuild every dim_ table")
def trigger_dimensions(city: str = Query("london")) -> dict:
    return wh.build_dimensions(city)


@router.post("/facts:run", summary="Build/rebuild every fact_ table")
def trigger_facts(city: str = Query("london")) -> dict:
    return wh.build_facts(city)


@router.post("/build", summary="Dimensions first, then facts")
def trigger_build(city: str = Query("london")) -> list[dict]:
    return wh.build_all(city)
