"""
Model explainability utilities.

Provides two approaches:
  1. Permutation importance  — model-agnostic, works with any sklearn pipeline
  2. SHAP                    — richer but requires the 'shap' package (optional)

Both functions return a sorted DataFrame ready to save as CSV or serve via API.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

ROOT = Path(__file__).parent.parent.parent
MODEL_RESULTS = ROOT / "reports" / "model_results"


def permutation_importance_df(
    model,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    n_repeats: int = 10,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Compute permutation importance on the test set.

    Importance is measured as increase in MAE when a feature is shuffled.
    Higher values = more important feature.

    Parameters
    ----------
    model :       fitted sklearn Pipeline or estimator
    X_test :      test feature DataFrame (original column names, not transformed)
    y_test :      test log-price target array
    n_repeats :   number of shuffle repeats per feature
    random_state: reproducibility seed
    """
    result = permutation_importance(
        model,
        X_test,
        y_test,
        scoring="neg_mean_absolute_error",
        n_repeats=n_repeats,
        random_state=random_state,
        n_jobs=-1,
    )

    feature_names = (
        list(X_test.columns)
        if hasattr(X_test, "columns")
        else [f"feature_{i}" for i in range(X_test.shape[1])]
    )

    return (
        pd.DataFrame({
            "feature": feature_names,
            "importance_mean": result["importances_mean"],
            "importance_std": result["importances_std"],
        })
        .sort_values("importance_mean", ascending=False)
        .reset_index(drop=True)
    )


def shap_importance_df(
    model,
    X_sample: pd.DataFrame,
    max_samples: int = 500,
) -> pd.DataFrame:
    """
    Compute global SHAP feature importance (mean |SHAP value| per feature).

    Uses TreeExplainer for tree-based models (fast), falls back to
    KernelExplainer for linear models (slower).

    Requires: pip install shap

    Parameters
    ----------
    model :       fitted sklearn Pipeline — the final step must be a tree or linear model
    X_sample :    feature DataFrame (will be capped at max_samples rows for speed)
    max_samples : row limit for SHAP computation to keep runtime manageable
    """
    try:
        import shap
    except ImportError:
        return pd.DataFrame({
            "feature": [],
            "mean_abs_shap": [],
            "note": [],
        })

    sample = X_sample.sample(min(max_samples, len(X_sample)), random_state=42)

    # Transform features through the pipeline preprocessor so the final
    # estimator receives the encoded input SHAP expects
    final_estimator = model.named_steps.get("model") or model[-1]
    preprocessor = model.named_steps.get("preprocessor")

    if preprocessor is not None:
        X_transformed = np.asarray(preprocessor.transform(sample))
        # Recover feature names after one-hot encoding if possible
        try:
            feature_names = preprocessor.get_feature_names_out()
        except Exception:
            feature_names = [f"f{i}" for i in range(X_transformed.shape[1])]
    else:
        X_transformed = np.asarray(sample.to_numpy())
        feature_names = list(sample.columns)

    try:
        explainer = shap.TreeExplainer(final_estimator)
        shap_values = explainer.shap_values(X_transformed)
    except Exception:
        # Fallback for non-tree models (Ridge etc.)
        background = shap.sample(X_transformed, min(100, len(X_transformed)))
        explainer = shap.KernelExplainer(final_estimator.predict, background)
        shap_values = explainer.shap_values(X_transformed, nsamples=100)

    return (
        pd.DataFrame({
            "feature": feature_names,
            "mean_abs_shap": np.abs(shap_values).mean(axis=0),
        })
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )


def save_importance(
    df: pd.DataFrame,
    city: str,
    method: str = "permutation",
) -> Path:
    """Save a feature importance DataFrame to reports/model_results/."""
    MODEL_RESULTS.mkdir(parents=True, exist_ok=True)
    out = MODEL_RESULTS / f"feature_importance_{method}_{city}.csv"
    df.to_csv(out, index=False)
    return out
