"""
Evaluation metric helpers for price prediction models.

All metrics operate on original-currency price arrays (not log-scale).
Back-transform with np.expm1() before calling these functions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean absolute error in original currency."""
    return float(np.mean(np.abs(actual - predicted)))


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Root mean squared error in original currency."""
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean absolute percentage error (0–100 scale). Excludes zero-price rows."""
    mask = actual > 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def r2(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Coefficient of determination (R²)."""
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def within_pct(actual: np.ndarray, predicted: np.ndarray, threshold: float = 20.0) -> float:
    """
    Percentage of predictions within ±threshold% of the actual price.
    Business-friendly: "X% of listings priced within 20% of actual."
    """
    ratio = np.abs(actual - predicted) / actual.clip(min=1e-9)
    return float(np.mean(ratio <= threshold / 100) * 100)


def evaluate_all(
    actual: np.ndarray,
    predicted: np.ndarray,
    label: str = "model",
) -> dict:
    """
    Compute all evaluation metrics for one model and return as a dict.

    Parameters
    ----------
    actual :    true prices in original currency (after np.expm1)
    predicted : model predictions in original currency (after np.expm1)
    label :     model name for the 'model' column in the comparison table
    """
    return {
        "model": label,
        "mae": round(mae(actual, predicted), 2),
        "rmse": round(rmse(actual, predicted), 2),
        "mape": round(mape(actual, predicted), 2),
        "r2": round(r2(actual, predicted), 4),
        "within_20pct": round(within_pct(actual, predicted, 20.0), 1),
    }


def build_comparison_table(results: list[dict]) -> pd.DataFrame:
    """Convert a list of evaluate_all() dicts into a formatted comparison DataFrame."""
    return pd.DataFrame(results).set_index("model")


def subgroup_metrics(
    residuals_df: pd.DataFrame,
    group_col: str,
) -> pd.DataFrame:
    """
    Compute MAE and median residual for each value in group_col.

    Parameters
    ----------
    residuals_df : DataFrame with columns actual_price, predicted_price,
                   residual, absolute_error, and the grouping column.
    group_col :    column to group by (e.g. 'room_type', 'neighbourhood_cleansed').
    """
    if group_col not in residuals_df.columns:
        raise ValueError(f"Column '{group_col}' not found in residuals DataFrame.")

    return (
        residuals_df.groupby(group_col)
        .agg(
            sample_size=("absolute_error", "count"),
            mae=("absolute_error", "mean"),
            median_residual=("residual", "median"),
            pct_over_predicted=(
                "residual",
                lambda x: round((x < 0).mean() * 100, 1),
            ),
        )
        .round(2)
        .sort_values("mae", ascending=False)
        .reset_index()
    )
