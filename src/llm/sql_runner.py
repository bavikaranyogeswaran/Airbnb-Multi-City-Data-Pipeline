"""
Validate and execute LLM-generated SQL against a city's DuckDB warehouse.

Responsibilities:
  1. Strip markdown fences the LLM may have added despite instructions
  2. Reject any statement that is not a SELECT / WITH…SELECT
  3. Reject statements containing mutation keywords (INSERT, DROP, etc.)
  4. Append LIMIT 50 when the query has no LIMIT clause
  5. Run the statement against the warehouse in read-only mode
  6. Return (clean_sql, rows) where rows is a list[dict]

Callers receive a ValueError for unsafe SQL and a RuntimeError for
execution failures — both carry a human-readable message safe to surface
to the API caller.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"

_MAX_ROWS = 50

# Keywords that must never appear in user-supplied SQL
_BANNED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|TRUNCATE|ALTER|REPLACE|MERGE|UPSERT|ATTACH|DETACH|COPY|EXPORT|IMPORT)\b",
    re.IGNORECASE,
)

# A valid statement starts with SELECT or WITH (CTE)
_ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


def _strip_fences(raw: str) -> str:
    """Remove ```sql … ``` or ``` … ``` wrappers the LLM may have added."""
    raw = raw.strip()
    # Remove opening fence (```sql or ```)
    raw = re.sub(r"^```(?:sql)?\s*\n?", "", raw, flags=re.IGNORECASE)
    # Remove closing fence
    raw = re.sub(r"\n?```\s*$", "", raw)
    return raw.strip()


def _ensure_limit(sql: str) -> str:
    """Append LIMIT 50 if no LIMIT clause is already present."""
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        sql = sql.rstrip().rstrip(";")
        sql = f"{sql}\nLIMIT {_MAX_ROWS}"
    return sql


def validate(raw_sql: str) -> str:
    """
    Sanitise and validate LLM-generated SQL.

    Returns the cleaned SQL string ready for execution.
    Raises ValueError with a descriptive message if the SQL is unsafe.
    """
    sql = _strip_fences(raw_sql)

    if not sql:
        raise ValueError("The model returned an empty SQL statement.")

    if not _ALLOWED_START.match(sql):
        first = sql.split()[0] if sql.split() else "(empty)"
        raise ValueError(
            f"Only SELECT or WITH statements are permitted. "
            f"The model generated a statement starting with '{first}'."
        )

    match = _BANNED.search(sql)
    if match:
        raise ValueError(
            f"Unsafe keyword '{match.group().upper()}' detected in generated SQL. "
            "Only read-only SELECT statements are allowed."
        )

    return _ensure_limit(sql)


def run(sql: str, city: str) -> list[dict]:
    """
    Execute *already-validated* SQL against the city's warehouse.

    Returns results as a list of dicts (column name → value).
    Raises FileNotFoundError if the warehouse does not exist.
    Raises RuntimeError if DuckDB reports an execution error.
    """
    db_path = DATA / city / "warehouse.duckdb"
    if not db_path.exists():
        raise FileNotFoundError(
            f"Warehouse not found for '{city}'. "
            "Run the pipeline load stage first."
        )

    try:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rel = con.execute(sql)
            columns = [desc[0] for desc in rel.description]
            rows = rel.fetchall()
        finally:
            con.close()
    except duckdb.Error as exc:
        raise RuntimeError(f"DuckDB execution error: {exc}") from exc

    return [dict(zip(columns, row)) for row in rows]


def validate_and_run(raw_sql: str, city: str) -> tuple[str, list[dict]]:
    """
    Convenience wrapper: validate then execute.

    Returns (clean_sql, rows).
    Raises ValueError (bad SQL) or RuntimeError (DuckDB error) or
    FileNotFoundError (missing warehouse).
    """
    clean = validate(raw_sql)
    rows = run(clean, city)
    return clean, rows
