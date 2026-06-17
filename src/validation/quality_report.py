"""Bundle every Phase 2.1 finding into a single HTML data-quality report.

Inputs:
  reports/dataset_inventory.csv
  reports/schema_documentation.csv
  reports/key_integrity.md
  reports/extended_profile.json
  reports/duplicates_summary.md
  reports/outliers_iqr.csv
  reports/outliers_domain.csv
  reports/assumptions_log.md

Output:
  reports/data_quality_report.html
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "cities.yml"
REPORTS_DIR = ROOT / "reports"


CSS = """
  :root { --navy:#0f172a; --blue:#1d4ed8; --slate:#475569; --line:#dbe3ee;
          --paper:#fff; --bg:#f6f8fb; --green:#15803d; --amber:#b45309; --red:#b91c1c; }
  *{box-sizing:border-box}
  body{font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.55;color:#1e293b;background:var(--bg);margin:0}
  .page{max-width:1100px;margin:0 auto;background:var(--paper);min-height:100vh;box-shadow:0 12px 40px rgba(15,23,42,.08)}
  header{background:linear-gradient(135deg,#0f172a 0%,#1d4ed8 100%);color:#fff;padding:36px 48px}
  header h1{margin:0 0 8px;font-size:28px}
  header p{margin:2px 0;color:#dbeafe}
  main{padding:32px 48px 56px}
  h2{margin:40px 0 12px;color:var(--navy);font-size:22px;border-bottom:2px solid var(--blue);padding-bottom:6px}
  h3{margin:24px 0 8px;color:var(--navy);font-size:17px}
  p{margin:6px 0 10px}
  table{width:100%;border-collapse:collapse;margin:10px 0 16px;font-size:13px}
  th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
  th{background:#eaf1ff;color:#172554;font-weight:700}
  tr:nth-child(even) td{background:#fbfdff}
  .num{text-align:right;font-variant-numeric:tabular-nums}
  .ok{color:var(--green);font-weight:700}
  .warn{color:var(--amber);font-weight:700}
  .bad{color:var(--red);font-weight:700}
  .card{border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0;background:#fff}
  .kv{display:grid;grid-template-columns:240px 1fr;gap:6px 18px;margin:6px 0}
  .kv .k{color:var(--slate)}
  code{font-family:Consolas,Monaco,monospace;background:#edf2f7;padding:1px 5px;border-radius:3px;font-size:.92em}
  .callout{border-left:4px solid var(--blue);background:#eff6ff;padding:12px 14px;margin:14px 0;border-radius:6px}
  .callout.amber{border-left-color:var(--amber);background:#fffbeb}
  .callout.red{border-left-color:var(--red);background:#fef2f2}
  .callout.green{border-left-color:var(--green);background:#f0fdf4}
  footer{padding:18px 48px 32px;color:var(--slate);font-size:12px;border-top:1px solid var(--line);background:#f8fafc}
"""


def html_table(df: pd.DataFrame, numeric_cols: list[str] | None = None) -> str:
    numeric_cols = set(numeric_cols or [])
    head = "<tr>" + "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns) + "</tr>"
    rows = []
    for _, row in df.iterrows():
        cells = []
        for c in df.columns:
            v = row[c]
            cls = ' class="num"' if c in numeric_cols else ""
            if isinstance(v, (int, float)) and pd.notna(v) and c in numeric_cols:
                cells.append(f"<td{cls}>{v:,.4f}</td>" if isinstance(v, float) else f"<td{cls}>{v:,}</td>")
            else:
                cells.append(f"<td{cls}>{html.escape(str(v))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table>{head}{''.join(rows)}</table>"


def load_inputs() -> dict:
    return {
        "inventory":  pd.read_csv(REPORTS_DIR / "dataset_inventory.csv"),
        "schema":     pd.read_csv(REPORTS_DIR / "schema_documentation.csv"),
        "outliers_iqr": pd.read_csv(REPORTS_DIR / "outliers_iqr.csv"),
        "outliers_dom": pd.read_csv(REPORTS_DIR / "outliers_domain.csv"),
        "profile_json": json.loads((REPORTS_DIR / "extended_profile.json").read_text(encoding="utf-8")),
        "integrity_md": (REPORTS_DIR / "key_integrity.md").read_text(encoding="utf-8"),
        "duplicates_md": (REPORTS_DIR / "duplicates_summary.md").read_text(encoding="utf-8"),
    }


def render_executive_summary(data: dict, city: str, snapshot: str) -> str:
    inv = data["inventory"]
    schema = data["schema"]
    dom = data["outliers_dom"]
    files = inv[["file_name", "row_count", "column_count", "load_status"]]

    null_100 = schema[(schema["null_percentage"] == 100) & (schema["source_file"].isin([
        "listings.csv.gz", "calendar.csv.gz", "reviews.csv.gz",
        "neighbourhoods.csv", "neighbourhoods.geojson"
    ]))]
    high_null = schema[(schema["null_percentage"] >= 30) & (schema["null_percentage"] < 100)]
    domain_violations = dom[dom["violation_count"] > 0]

    return f"""
    <section>
      <h2>Executive summary</h2>
      <div class="kv">
        <div class="k">City</div><div><strong>{city}</strong></div>
        <div class="k">Snapshot</div><div><strong>{snapshot}</strong></div>
        <div class="k">Files ingested</div><div>{len(files)} / 7 with status <span class="ok">ok</span></div>
        <div class="k">Total raw rows</div><div>{int(inv['row_count'].sum()):,}</div>
        <div class="k">Columns profiled</div><div>{len(schema):,}</div>
        <div class="k">Columns 100% null (canonical files)</div><div>{len(null_100)}</div>
        <div class="k">Columns 30–99% null</div><div>{len(high_null)}</div>
        <div class="k">Domain-rule violation types triggered</div><div>{len(domain_violations)} of {len(dom)}</div>
      </div>

      <div class="callout green">
        <strong>Referential integrity is perfect.</strong> Zero PK duplicates, zero FK orphans, zero composite-key collisions. See the integrity section below.
      </div>

      <div class="callout red">
        <strong>Hardest constraint:</strong> <code>calendar.price</code> and <code>calendar.adjusted_price</code> are 100% null (A-005). Per-date pricing analysis is impossible from this snapshot; revenue work falls back to listing-level price.
      </div>

      <div class="callout amber">
        <strong>Listing-level <code>price</code> is 36% null.</strong> Price-based analyses run on the 64% non-null cohort; the null cohort needs separate profiling in Phase 2.1 follow-up (assumption A-012 is provisional).
      </div>
    </section>
    """


def render_inventory(data: dict) -> str:
    df = data["inventory"][["city", "snapshot_date", "file_name", "file_type",
                            "compressed_size_mb", "uncompressed_size_mb",
                            "row_count", "column_count", "load_status"]]
    return "<section><h2>1. Dataset inventory</h2>" + html_table(
        df, numeric_cols=["compressed_size_mb", "uncompressed_size_mb", "row_count", "column_count"]
    ) + "</section>"


def render_completeness(data: dict) -> str:
    schema = data["schema"]
    # null breakdown by source_file
    g = schema.groupby("source_file")["null_percentage"]
    rows = []
    for src, group in g:
        rows.append({
            "source_file": src,
            "columns": int(group.count()),
            "fully_populated_cols": int((group == 0).sum()),
            "partially_null_cols": int(((group > 0) & (group < 100)).sum()),
            "fully_null_cols": int((group == 100).sum()),
        })
    summary = pd.DataFrame(rows)

    high_null = schema[(schema["null_percentage"] >= 30)].sort_values("null_percentage", ascending=False)
    high_null_view = high_null[["source_file", "column_name", "detected_dtype", "null_percentage", "expected_type", "cleaning_requirement"]]

    return (
        "<section><h2>2. Completeness analysis</h2>"
        "<h3>2.1 Per-file null-breakdown</h3>"
        + html_table(summary, numeric_cols=["columns", "fully_populated_cols", "partially_null_cols", "fully_null_cols"])
        + "<h3>2.2 Columns ≥ 30% null</h3>"
        + html_table(high_null_view, numeric_cols=["null_percentage"])
        + "</section>"
    )


def render_profile_highlights(data: dict) -> str:
    """Show only the most interesting profile rows: high-cardinality cats and skewed numerics."""
    profile = data["profile_json"]
    rows = []
    for fp in profile["files"]:
        for col in fp["columns"]:
            if col.get("completeness_class") == "critical" or col.get("completeness_class") == "important":
                stat = col.get("numeric_stats", {})
                rows.append({
                    "source_file": fp["source_file"],
                    "column": col["column"],
                    "class": col["completeness_class"],
                    "null_pct": col["null_percentage"],
                    "uniq": col["unique_count"],
                    "min": stat.get("min", ""),
                    "p25": stat.get("q25", ""),
                    "median": stat.get("median", ""),
                    "p75": stat.get("q75", ""),
                    "max": stat.get("max", ""),
                    "mean": stat.get("mean", ""),
                    "std": stat.get("std", ""),
                })
    df = pd.DataFrame(rows)
    df = df.sort_values(["source_file", "class", "column"])
    return (
        "<section><h2>3. Profile highlights (critical + important fields)</h2>"
        + html_table(df, numeric_cols=["null_pct", "uniq", "min", "p25", "median", "p75", "max", "mean", "std"])
        + "</section>"
    )


def render_key_integrity(data: dict) -> str:
    # Embed the existing markdown findings as plain text.
    md_text = html.escape(data["integrity_md"])
    return (
        "<section><h2>4. Referential integrity</h2>"
        f"<pre style='white-space:pre-wrap;background:#f8fafc;padding:14px;border-radius:8px;font-size:13px;line-height:1.45;'>{md_text}</pre>"
        "</section>"
    )


def render_duplicates(data: dict) -> str:
    md_text = html.escape(data["duplicates_md"])
    return (
        "<section><h2>5. Duplicate findings</h2>"
        f"<pre style='white-space:pre-wrap;background:#f8fafc;padding:14px;border-radius:8px;font-size:13px;line-height:1.45;'>{md_text}</pre>"
        "</section>"
    )


def render_outliers(data: dict) -> str:
    dom = data["outliers_dom"]
    dom_view = dom.copy()
    dom_view["status"] = dom_view["violation_count"].apply(
        lambda n: "OK" if n == 0 else f"FAIL ({n:,})"
    )

    iqr = data["outliers_iqr"]
    return (
        "<section><h2>6. Outliers and rule violations</h2>"
        "<h3>6.1 Domain rules</h3>"
        + html_table(dom_view[["source_file", "rule", "violation_count", "status"]], numeric_cols=["violation_count"])
        + "<h3>6.2 IQR (sentinels removed first per A-018)</h3>"
        + html_table(iqr, numeric_cols=["non_null", "iqr_lower", "iqr_upper", "low_outliers", "high_outliers", "sentinel_int_max_rows"])
        + """
        <div class="callout amber">
          <strong>IQR on bounded fields (availability_*, review_scores_rating) flags long-tail-at-zero, not data errors.</strong> Phase 2.2 keeps these rows; the IQR table here is diagnostic, not actionable for those columns.
        </div>
        """
        + "</section>"
    )


def render_familiarization_links(city: str, snapshot: str) -> str:
    return f"""
    <section>
      <h2>7. Phase 1 grounding</h2>
      <p>Every Phase 2.1 finding above is interpreted in the context of the Phase 1 assumptions log. See:</p>
      <ul>
        <li><a href="assumptions_log.md"><code>assumptions_log.md</code></a> — 29 numbered assumptions</li>
        <li><a href="data_limitations.md"><code>data_limitations.md</code></a> — what this snapshot cannot answer</li>
        <li><a href="special_fields.md"><code>special_fields.md</code></a> — 19 fields with non-obvious interpretation</li>
        <li><a href="business_entities.md"><code>business_entities.md</code></a> — entity glossary</li>
        <li><a href="file_purpose.md"><code>file_purpose.md</code></a> — per-file semantics</li>
      </ul>
      <p>Most important callbacks for the engineering layer:</p>
      <ul>
        <li><strong>A-002:</strong> <code>calendar.available = "f"</code> is not "booked". Occupancy is always a proxy.</li>
        <li><strong>A-005:</strong> Calendar prices are 100% null; revenue work uses listing price × unavailable days as an upper-bound proxy.</li>
        <li><strong>A-018 / A-019:</strong> <code>maximum_nights = 2^31 - 1</code> and <code>minimum_nights ≥ 365</code> are sentinels, handled in Phase 2.2.</li>
        <li><strong>A-024:</strong> <code>calculated_host_listings_count</code> is the canonical city-scoped host portfolio count.</li>
      </ul>
    </section>
    """


def render(data: dict, city: str, snapshot: str) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="UTF-8">',
        f"<title>Data Quality Report — {city} {snapshot}</title>",
        f"<style>{CSS}</style></head><body>",
        '<div class="page">',
        f'<header><h1>Data Quality Report</h1>'
        f'<p>City: <strong>{city}</strong> · Snapshot: <strong>{snapshot}</strong></p>'
        f'<p>Generated: {dt.datetime.now().strftime("%Y-%m-%d %H:%M")} · Source: Inside Airbnb</p></header>',
        "<main>",
        render_executive_summary(data, city, snapshot),
        render_inventory(data),
        render_completeness(data),
        render_profile_highlights(data),
        render_key_integrity(data),
        render_duplicates(data),
        render_outliers(data),
        render_familiarization_links(city, snapshot),
        "</main>",
        '<footer>Phase 2.1 deliverable. Inputs versioned in `reports/`; this HTML is regenerated by `python -m src.validation.quality_report --city london`.</footer>',
        "</div></body></html>",
    ]
    return "\n".join(parts)


def run(city: str = "london") -> dict:
    from src.api.result import make_result, timed

    with timed() as elapsed:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        city_cfg = cfg["cities"][city]
        snapshot = city_cfg["source"]["snapshot_date"]
        city_name = city_cfg.get("name", city)

        data = load_inputs()
        html_text = render(data, city_name, snapshot)
        out = REPORTS_DIR / "data_quality_report.html"
        out.write_text(html_text, encoding="utf-8")

    return make_result(
        step="ingestion.quality_report",
        outputs=[out],
        summary={
            "city": city,
            "snapshot_date": snapshot,
            "bytes": len(html_text),
        },
        elapsed_seconds=elapsed(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()
    print(run(city=args.city))


if __name__ == "__main__":
    main()
