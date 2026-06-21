"""Great Expectations validation runner.

Creates an ephemeral (in-memory) GE context — no project directory,
no YAML files, no GE Cloud — and validates the three core processed
parquets against the expectation suites defined in ge_suite.py.

Outputs
-------
  reports/ge_validation/{city}_results.json   — full per-expectation detail
  reports/ge_validation/{city}_summary.json   — counts only (for the API)

The run() function is called by the FastAPI quality endpoint and can also
be invoked from the CLI:

    python -m src.validation.ge_runner --city london
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import great_expectations as gx
import pandas as pd

from src.validation.ge_suite import (
    calendar_clean_expectations,
    listing_master_expectations,
    reviews_clean_expectations,
)

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_BASE = ROOT / "data" / "processed"
GE_REPORTS_DIR = ROOT / "reports" / "ge_validation"

# Map of (asset_name, parquet_filename, expectation_factory)
_DATASETS: list[tuple[str, str, callable]] = [
    ("listing_master",  "listing_master.parquet",  listing_master_expectations),
    ("calendar_clean",  "calendar_clean.parquet",  calendar_clean_expectations),
    ("reviews_clean",   "reviews_clean.parquet",   reviews_clean_expectations),
]


def _serialize_result(r) -> dict:
    """Extract the fields we care about from an ExpectationValidationResult."""
    return {
        "expectation_type": r.expectation_config.type,
        "kwargs": r.expectation_config.kwargs,
        "success": bool(r.success),
        "observed_value": str(r.result.get("observed_value", ""))
        if r.result
        else None,
        "element_count": r.result.get("element_count") if r.result else None,
        "unexpected_count": r.result.get("unexpected_count") if r.result else None,
        "unexpected_percent": round(r.result.get("unexpected_percent", 0) or 0, 4)
        if r.result
        else None,
    }


def run(city: str = "london") -> dict:
    """Run GE validation for all three parquets and return a summary."""
    from src.api.result import make_result, timed

    GE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    city_dir = PROCESSED_BASE / city

    all_results: dict[str, dict] = {}
    total_passed = total_failed = 0

    with timed() as elapsed:
        for asset_name, parquet_file, expectation_factory in _DATASETS:
            parquet_path = city_dir / parquet_file
            if not parquet_path.exists():
                all_results[asset_name] = {
                    "status": "skipped",
                    "reason": f"{parquet_file} not found for city={city}",
                    "passed": 0,
                    "failed": 0,
                    "expectations": [],
                }
                continue

            df = pd.read_parquet(parquet_path)
            asset_result = _validate_dataframe(
                asset_name=asset_name,
                df=df,
                expectations=expectation_factory(),
            )
            all_results[asset_name] = asset_result
            total_passed += asset_result["passed"]
            total_failed += asset_result["failed"]

    def _default(obj):
        if isinstance(obj, (dt.date, dt.datetime)):
            return obj.isoformat()
        return str(obj)

    # Write full results JSON
    full_output = {
        "city": city,
        "ge_version": gx.__version__,
        "validated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "datasets": all_results,
    }
    results_path = GE_REPORTS_DIR / f"{city}_results.json"
    results_path.write_text(json.dumps(full_output, indent=2, default=_default), encoding="utf-8")

    # Write compact summary JSON
    summary = {
        "city": city,
        "validated_at": full_output["validated_at"],
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_expectations": total_passed + total_failed,
        "overall_success": total_failed == 0,
        "by_dataset": {
            name: {
                "passed": d["passed"],
                "failed": d["failed"],
                "success": d.get("success", False),
            }
            for name, d in all_results.items()
        },
        "results_file": str(results_path.relative_to(ROOT)),
    }
    summary_path = GE_REPORTS_DIR / f"{city}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return make_result(
        step="quality.ge_validate",
        outputs=[results_path, summary_path],
        summary=summary,
        elapsed_seconds=elapsed(),
        status="ok" if total_failed == 0 else "error",
        error=f"{total_failed} expectations failed" if total_failed else None,
    )


def _validate_dataframe(
    asset_name: str,
    df: pd.DataFrame,
    expectations: list,
) -> dict:
    """Create an ephemeral GE context, run a suite, return a result dict."""
    context = gx.get_context(mode="ephemeral")

    datasource = context.data_sources.add_pandas(f"{asset_name}_ds")
    asset = datasource.add_dataframe_asset(asset_name)
    batch_def = asset.add_batch_definition_whole_dataframe(f"{asset_name}_bd")

    suite_name = f"{asset_name}_suite"
    suite = gx.ExpectationSuite(name=suite_name)
    for exp in expectations:
        suite.add_expectation(exp)
    suite = context.suites.add(suite)

    validation_def = context.validation_definitions.add(
        gx.ValidationDefinition(
            name=f"{asset_name}_vd",
            data=batch_def,
            suite=suite,
        )
    )

    result = validation_def.run(batch_parameters={"dataframe": df})

    serialized = [_serialize_result(r) for r in result.results]
    passed = sum(1 for r in serialized if r["success"])
    failed = len(serialized) - passed

    return {
        "success": bool(result.success),
        "passed": passed,
        "failed": failed,
        "total": len(serialized),
        "expectations": serialized,
        "failed_expectations": [
            e["expectation_type"] for e in serialized if not e["success"]
        ],
    }


def get_latest_summary(city: str) -> dict | None:
    """Return the most recently written summary JSON, or None."""
    path = GE_REPORTS_DIR / f"{city}_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_full_results(city: str) -> dict | None:
    """Return the full per-expectation results JSON, or None."""
    path = GE_REPORTS_DIR / f"{city}_results.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="london")
    args = parser.parse_args()
    result = run(city=args.city)
    summary = result.get("summary", {})
    print(f"GE validation: {summary.get('total_passed')} passed, "
          f"{summary.get('total_failed')} failed")


if __name__ == "__main__":
    main()
