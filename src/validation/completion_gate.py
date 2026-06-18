"""Single-city completion gate checker (Section 26 of assessment plan).

Runs all 13 checklist items for a given city and produces:
  - A structured list of check results (pass / warn / fail)
  - reports/completion_gate_<city>.md

Call run(city) to execute checks programmatically.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]

# ── Expected artifact lists ────────────────────────────────────────────────────

EXPECTED_PARQUET = [
    "listings_clean.parquet",
    "reviews_clean.parquet",
    "calendar_clean.parquet",
    "neighbourhoods_clean.parquet",
    "listing_master.parquet",
    "warehouse.duckdb",
]

EXPECTED_REJECTED = [
    "rejected_listings.parquet",
    "rejected_reviews.parquet",
    "rejected_calendar.parquet",
]

EXPECTED_SQL = [f"{i:02d}_" for i in range(1, 6)]   # at least 5 SQL files

EXPECTED_WAREHOUSE_TABLES = {
    "dim_city", "dim_neighbourhood", "dim_host",
    "dim_listing", "dim_date",
    "fact_calendar", "fact_reviews", "fact_listing_snapshot",
}

EXPECTED_REPORT_DOCS = [
    "engineering_decisions.md",
    "assumptions_log.md",
    "eda_findings.md",
]

# ── Check helpers ─────────────────────────────────────────────────────────────

def _check(name: str, status: str, detail: str) -> dict:
    return {"check": name, "status": status, "detail": detail}

def _pass(name: str, detail: str) -> dict:
    return _check(name, "PASS", detail)

def _fail(name: str, detail: str) -> dict:
    return _check(name, "FAIL", detail)

def _warn(name: str, detail: str) -> dict:
    return _check(name, "WARN", detail)


# ── Individual checks (1-13) ─────────────────────────────────────────────────

def check_1_raw_download(city: str) -> dict:
    """Raw CSV/GZ files exist in data/raw/<city>/."""
    raw = ROOT / "data" / "raw" / city
    expected = ["listings.csv.gz", "reviews.csv.gz", "calendar.csv.gz",
                "neighbourhoods.csv", "neighbourhoods.geojson"]
    missing = [f for f in expected if not (raw / f).exists()]
    if missing:
        return _fail("raw_download", f"Missing: {missing}")
    sizes = {f: round((raw / f).stat().st_size / 1024 / 1024, 1)
             for f in expected}
    return _pass("raw_download",
                 f"All {len(expected)} raw files present. "
                 + ", ".join(f"{k}: {v}MB" for k, v in sizes.items()))


def check_2_no_hardcoded_city(city: str) -> dict:
    """No city name is hardcoded as a *path segment* in cleaning/ or transformation/.

    Acceptable usage (all excluded from flagging):
      - Function/method parameter defaults: def run(city: str = "london")
      - Argparse defaults: add_argument("--city", default="london")
      - FastAPI Query defaults: Query("london")
      - Pure comments
    Not acceptable: literal path segment  e.g.  / "london" / ...
    """
    # Match only when the city name is used as a path segment (joined with / or \\)
    path_segment = re.compile(
        r'[/\\]\s*["\']' + re.escape(city) + r'["\']'      # prefix: / "london"
        r'|["\']' + re.escape(city) + r'["\'].*[/\\]'      # suffix: "london" /
    )
    suspect: list[str] = []
    scan_dirs = [ROOT / "src" / "cleaning", ROOT / "src" / "transformation"]
    for d in scan_dirs:
        for py in d.glob("*.py"):
            for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if path_segment.search(line):
                    rel = py.relative_to(ROOT)
                    suspect.append(f"{rel}:{lineno}: {stripped[:80]}")

    if suspect:
        return _fail("no_hardcoded_city",
                     f"{len(suspect)} hardcoded city path segment(s):\n  "
                     + "\n  ".join(suspect[:5]))
    return _pass("no_hardcoded_city",
                 "No hardcoded city path segments in cleaning/ or transformation/")


def check_3_profiles_generated(city: str) -> dict:
    """Profiling report documents exist in reports/."""
    reports_dir = ROOT / "reports"
    profile_docs = [
        "key_integrity.md", "outliers_summary.md",
        "duplicates_summary.md", "data_limitations.md",
    ]
    missing = [d for d in profile_docs if not (reports_dir / d).exists()]
    present = [d for d in profile_docs if (reports_dir / d).exists()]
    if missing:
        return _warn("profiles_generated",
                     f"{len(present)}/{len(profile_docs)} profile docs present. "
                     f"Missing: {missing}")
    return _pass("profiles_generated",
                 f"All {len(profile_docs)} profile documents present in reports/")


def check_4_silver_parquet(city: str) -> dict:
    """Silver Parquet outputs exist in data/processed/<city>/."""
    proc = ROOT / "data" / "processed" / city
    missing = [f for f in EXPECTED_PARQUET if not (proc / f).exists()]
    if missing:
        return _fail("silver_parquet", f"Missing: {missing}")
    sizes = {f: round((proc / f).stat().st_size / 1024 / 1024, 1)
             for f in EXPECTED_PARQUET if (proc / f).exists()}
    return _pass("silver_parquet",
                 f"All {len(EXPECTED_PARQUET)} processed files present. "
                 + ", ".join(f"{k}: {v}MB" for k, v in list(sizes.items())[:4]) + "...")


def check_5_rejected_records(city: str) -> dict:
    """Rejected-record parquet files exist (may be empty)."""
    proc = ROOT / "data" / "processed" / city
    missing = [f for f in EXPECTED_REJECTED if not (proc / f).exists()]
    if missing:
        return _fail("rejected_records", f"Missing rejection files: {missing}")
    sizes = {f: (proc / f).stat().st_size for f in EXPECTED_REJECTED}
    return _pass("rejected_records",
                 f"All 3 rejection files present. "
                 + ", ".join(f"{k}: {v}B" for k, v in sizes.items()))


def check_6_duckdb_builds(city: str) -> dict:
    """DuckDB warehouse exists and contains all expected tables."""
    db_path = ROOT / "data" / "processed" / city / "warehouse.duckdb"
    if not db_path.exists():
        return _fail("duckdb_builds", "warehouse.duckdb not found")
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
        conn.close()
        present = {r[0] for r in rows}
        missing = EXPECTED_WAREHOUSE_TABLES - present
        if missing:
            return _fail("duckdb_builds", f"Missing tables: {missing}")
        size_mb = round(db_path.stat().st_size / 1024 / 1024, 1)
        return _pass("duckdb_builds",
                     f"warehouse.duckdb ({size_mb}MB) — all {len(EXPECTED_WAREHOUSE_TABLES)} "
                     f"tables present: {sorted(present)}")
    except Exception as e:
        return _fail("duckdb_builds", f"Could not open warehouse: {e}")


def check_7_sql_queries(city: str) -> dict:
    """SQL files exist in sql/ and execute against the warehouse."""
    sql_dir = ROOT / "sql"
    sql_files = sorted(sql_dir.glob("*.sql"))
    if not sql_files:
        return _fail("sql_queries", "No .sql files found in sql/")

    db_path = ROOT / "data" / "processed" / city / "warehouse.duckdb"
    if not db_path.exists():
        return _warn("sql_queries",
                     f"{len(sql_files)} SQL files present but warehouse not built yet")

    failed: list[str] = []
    conn = duckdb.connect(str(db_path), read_only=True)
    for f in sql_files:
        try:
            conn.execute(f.read_text(encoding="utf-8")).fetchall()
        except Exception as e:
            failed.append(f"{f.name}: {e}")
    conn.close()

    if failed:
        return _fail("sql_queries",
                     f"{len(failed)}/{len(sql_files)} queries failed:\n  "
                     + "\n  ".join(failed))
    return _pass("sql_queries",
                 f"All {len(sql_files)} SQL queries execute successfully: "
                 + ", ".join(f.name for f in sql_files))


def check_8_eda_notebook(city: str) -> dict:
    """EDA notebook (03_*) has been executed (all code cells have outputs)."""
    import json
    nb_dir = ROOT / "notebooks"
    candidates = sorted(nb_dir.glob("03_*.ipynb"))
    if not candidates:
        return _fail("eda_notebook", "03_exploratory_data_analysis.ipynb not found")
    nb_path = candidates[0]
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    executed = [c for c in code_cells if c.get("execution_count") is not None]
    if len(executed) < len(code_cells):
        return _fail("eda_notebook",
                     f"Only {len(executed)}/{len(code_cells)} code cells have been executed")
    return _pass("eda_notebook",
                 f"{nb_path.name}: all {len(code_cells)} code cells executed "
                 f"(execution_count set)")


def check_9_stats_notebook(city: str) -> dict:
    """Statistical analysis notebook (04_*) has been executed."""
    import json
    nb_dir = ROOT / "notebooks"
    candidates = sorted(nb_dir.glob("04_*.ipynb"))
    if not candidates:
        return _fail("stats_notebook", "04_statistical_analysis.ipynb not found")
    nb_path = candidates[0]
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    executed = [c for c in code_cells if c.get("execution_count") is not None]
    if len(executed) < len(code_cells):
        return _fail("stats_notebook",
                     f"Only {len(executed)}/{len(code_cells)} code cells executed")
    return _pass("stats_notebook",
                 f"{nb_path.name}: all {len(code_cells)} code cells executed")


def check_10_api_endpoints(city: str) -> dict:
    """API app imports cleanly and TestClient returns 200 on health + analytics."""
    try:
        from fastapi.testclient import TestClient
        from src.api.app import app

        client = TestClient(app)
        h = client.get("/health")
        if h.status_code != 200:
            return _fail("api_endpoints", f"/health returned {h.status_code}")
        a = client.get("/analytics")
        if a.status_code != 200:
            return _fail("api_endpoints", f"/analytics returned {a.status_code}")
        # Spot-check a data endpoint
        r = client.get("/analytics/listings/price-by-room-type")
        if r.status_code != 200:
            return _warn("api_endpoints",
                         f"/health OK but /analytics/listings/price-by-room-type "
                         f"returned {r.status_code} — artifacts may not be built")
        return _pass("api_endpoints",
                     f"health=200, analytics index=200, "
                     f"price-by-room-type={r.status_code} ({len(r.json())} rows)")
    except Exception as e:
        return _fail("api_endpoints", f"{type(e).__name__}: {e}")


def check_11_tests_pass(city: str) -> dict:
    """pytest suite passes with no failures."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    output = (result.stdout + result.stderr).strip()
    # Parse summary line — pytest -q prints e.g. "94 passed, 2 warnings in 2.89s"
    m_pass = re.search(r"(\d+) passed", output)
    m_fail = re.search(r"(\d+) failed", output)
    n_passed = int(m_pass.group(1)) if m_pass else 0
    n_failed = int(m_fail.group(1)) if m_fail else 0

    # Find the "X passed" summary line specifically
    summary_line = next(
        (ln for ln in reversed(output.splitlines()) if "passed" in ln or "failed" in ln),
        output.splitlines()[-1] if output.splitlines() else "(no output)",
    )
    if result.returncode != 0 or n_failed > 0:
        return _fail("tests_pass",
                     f"{n_failed} failures. Summary: {summary_line}")
    return _pass("tests_pass",
                 f"{n_passed} tests passed, 0 failures. ({summary_line})")


def check_12_readme_commands(city: str) -> dict:
    """README.md exists and contains the minimum required commands."""
    readme = ROOT / "README.md"
    if not readme.exists():
        return _fail("readme_commands", "README.md not found")
    text = readme.read_text(encoding="utf-8")
    required = ["uvicorn", "pytest", "pip install"]
    missing = [cmd for cmd in required if cmd not in text]
    if missing:
        return _warn("readme_commands",
                     f"README exists but missing commands: {missing}")
    wc = len(text.split())
    return _pass("readme_commands",
                 f"README.md present ({wc} words), contains: {required}")


def check_13_decision_logs(city: str) -> dict:
    """Engineering decision and assumption logs exist and are non-empty."""
    reports = ROOT / "reports"
    missing, present = [], []
    for doc in EXPECTED_REPORT_DOCS:
        p = reports / doc
        if not p.exists():
            missing.append(doc)
        elif p.stat().st_size < 100:
            missing.append(f"{doc} (nearly empty)")
        else:
            present.append(f"{doc} ({round(p.stat().st_size/1024,1)}KB)")
    if missing:
        return _warn("decision_logs",
                     f"Present: {present}. Missing/empty: {missing}")
    return _pass("decision_logs", f"All decision docs present: {present}")


# ── Orchestrator ──────────────────────────────────────────────────────────────

CHECKS = [
    check_1_raw_download,
    check_2_no_hardcoded_city,
    check_3_profiles_generated,
    check_4_silver_parquet,
    check_5_rejected_records,
    check_6_duckdb_builds,
    check_7_sql_queries,
    check_8_eda_notebook,
    check_9_stats_notebook,
    check_10_api_endpoints,
    check_11_tests_pass,
    check_12_readme_commands,
    check_13_decision_logs,
]


def run(city: str = "london") -> dict:
    """Run all 13 completion gate checks and return a results dict."""
    results = [fn(city) for fn in CHECKS]
    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    gate_open = (failed == 0)

    report = _render_markdown(city, results, passed, warned, failed, gate_open)
    out_path = ROOT / "reports" / f"completion_gate_{city}.md"
    out_path.write_text(report, encoding="utf-8")

    return {
        "city":       city,
        "gate_open":  gate_open,
        "passed":     passed,
        "warned":     warned,
        "failed":     failed,
        "checks":     results,
        "report_path": str(out_path.relative_to(ROOT)),
    }


# ── Markdown renderer ─────────────────────────────────────────────────────────

def _render_markdown(city, results, passed, warned, failed, gate_open) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    gate_label = "OPEN — ready to scale" if gate_open else "CLOSED — fix failures first"
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}

    lines = [
        f"# Single-City Completion Gate — {city.title()}",
        f"",
        f"**Generated:** {ts}  ",
        f"**Gate status:** {gate_label}  ",
        f"**Results:** {passed} PASS · {warned} WARN · {failed} FAIL",
        f"",
        f"| # | Check | Status | Detail |",
        f"|---|-------|--------|--------|",
    ]
    for i, r in enumerate(results, 1):
        ic = icon.get(r["status"], "?")
        detail = r["detail"].replace("\n", " ").replace("|", "\\|")[:120]
        lines.append(f"| {i} | {r['check']} | {ic} {r['status']} | {detail} |")

    lines += [
        f"",
        f"## Details",
        f"",
    ]
    for i, r in enumerate(results, 1):
        lines += [
            f"### {i}. {r['check']}",
            f"**Status:** {icon.get(r['status'],'?')} {r['status']}",
            f"",
            f"```",
            r["detail"],
            f"```",
            f"",
        ]

    if gate_open:
        lines += [
            f"---",
            f"",
            f"> All checks passed (WARN is acceptable). Proceed to Section 27: "
            f"Scale from One City to Six Cities.",
        ]
    else:
        fail_names = [r["check"] for r in results if r["status"] == "FAIL"]
        lines += [
            f"---",
            f"",
            f"> **Gate is CLOSED.** Fix {len(fail_names)} failing check(s) before scaling: "
            f"{fail_names}",
        ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != "checks"}, indent=2))
    print(f"\nGate: {'OPEN' if result['gate_open'] else 'CLOSED'}")
    icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}
    for r in result["checks"]:
        print(f"  {icon.get(r['status'], '[?]')} {r['check']}: {r['detail'][:80]}")
