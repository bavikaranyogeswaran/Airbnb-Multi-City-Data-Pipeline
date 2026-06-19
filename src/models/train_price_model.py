"""
Train and evaluate price prediction models for a given city.

Three model families: Ridge (linear), Random Forest (tree), LightGBM (boosting).
Split strategy: GroupShuffleSplit by host_id — same host cannot appear in both
                train and test sets (prevents host-leakage inflation).
Cross-validation: GroupKFold(5) with a custom scorer that back-transforms
                  log-price predictions to original currency before computing MAE.

Outputs (all in reports/model_results/):
  price_model_comparison_{city}.csv
  cross_validation_results_{city}.csv
  residuals_{city}.csv

Saved model:
  models/{city}_price_model.joblib
  models/{city}_model_metadata.json
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import (
    GroupKFold,
    GroupShuffleSplit,
    cross_validate,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data" / "processed"
MODEL_RESULTS = ROOT / "reports" / "model_results"
MODELS_DIR = ROOT / "models"

# These must match the column names produced by listing_features.py
NUMERIC_FEATURES: list[str] = [
    "accommodates", "bedrooms", "beds", "bathroom_count",
    "minimum_nights", "host_tenure_years", "host_response_rate",
    "latitude", "longitude", "availability_365",
    "review_scores_rating", "review_scores_cleanliness",
    "review_scores_location", "reviews_per_month_calc",
    "calculated_host_listings_count", "number_of_reviews",
    "beds_per_guest",
    "host_is_superhost", "instant_bookable", "bathroom_is_shared",
    "has_wifi", "has_kitchen", "has_air_conditioning", "has_washer",
    "has_parking", "has_pool", "has_workspace", "has_gym",
    "has_elevator", "has_tv", "has_bathtub", "has_dishwasher",
    "amenity_count",
]

# Low cardinality (4–5 unique values) → OneHotEncoder
OHE_FEATURES: list[str] = ["room_type", "property_type_bucket"]

# High cardinality (33 London / 22 Amsterdam) → TargetEncoder fitted per CV fold.
# TargetEncoder must live inside the sklearn Pipeline so it only sees training-fold
# targets during cross-validation — computing target means on the full dataset before
# splitting would leak validation-set price information into the features.
TARGET_ENC_FEATURES: list[str] = ["neighbourhood_cleansed"]


def _currency_mae_scorer(estimator, X, y_log):
    """
    Custom CV scorer: predict in log-space, back-transform to currency,
    then compute MAE. This gives CV scores in the same unit as test metrics.
    """
    log_pred = estimator.predict(X)
    return -mean_absolute_error(np.expm1(y_log), np.expm1(log_pred))


def _get_lgbm():
    """Return LightGBM if installed, else fall back to HistGradientBoosting."""
    try:
        from lightgbm import LGBMRegressor
        return LGBMRegressor(
            n_estimators=500,
            learning_rate=0.05,
            num_leaves=63,
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor
        return HistGradientBoostingRegressor(
            max_iter=500,
            learning_rate=0.05,
            max_leaf_nodes=63,
            min_samples_leaf=20,
            random_state=42,
        )


def _build_preprocessor(
    num_cols: list[str],
    ohe_cols: list[str],
    target_enc_cols: list[str],
) -> ColumnTransformer:
    numeric_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    ohe_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    # TargetEncoder replaces each neighbourhood with its mean log-price from the
    # training fold. It handles unseen categories via global mean shrinkage.
    target_enc_pipe = TargetEncoder(target_type="continuous")

    transformers: list = [("numeric", numeric_pipe, num_cols)]
    if ohe_cols:
        transformers.append(("ohe_cat", ohe_pipe, ohe_cols))
    if target_enc_cols:
        transformers.append(("target_enc", target_enc_pipe, target_enc_cols))

    return ColumnTransformer(transformers, remainder="drop")


def _compute_test_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    label: str,
) -> dict:
    mae_val = float(np.mean(np.abs(actual - predicted)))
    rmse_val = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    mask = actual > 0
    mape_val = float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r2_val = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    within20 = float(np.mean(np.abs(actual - predicted) / actual.clip(1e-9) <= 0.2) * 100)
    return {
        "model": label,
        "test_mae": round(mae_val, 2),
        "test_rmse": round(rmse_val, 2),
        "test_mape": round(mape_val, 2),
        "test_r2": round(r2_val, 4),
        "within_20pct": round(within20, 1),
    }


def train(city: str = "london") -> dict:
    """
    Full training pipeline for one city.

    1. Load feature_matrix.parquet (built by listing_features.py)
    2. GroupShuffleSplit 80/20 by host_id
    3. Build sklearn pipelines for Ridge, Random Forest, LightGBM
    4. Cross-validate all three on the training set (GroupKFold-5)
    5. Evaluate the best model on the hold-out test set
    6. Save model artifacts and result CSVs
    """
    MODEL_RESULTS.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    src = DATA / city / "feature_matrix.parquet"
    if not src.exists():
        return {
            "status": "error",
            "message": f"feature_matrix.parquet not found for {city}. "
                       "Run listing_features.py first.",
        }

    df = pd.read_parquet(src)

    # Resolve columns that actually exist in this city's feature matrix
    num_cols = [c for c in NUMERIC_FEATURES if c in df.columns]
    ohe_cols = [c for c in OHE_FEATURES if c in df.columns]
    target_enc_cols = [c for c in TARGET_ENC_FEATURES if c in df.columns]
    feature_cols = num_cols + ohe_cols + target_enc_cols

    X = df[feature_cols]
    y = df["log_price"].to_numpy()
    price_actual = df["price_numeric"].to_numpy()
    groups = (
        df["host_id"].to_numpy() if "host_id" in df.columns else np.zeros(len(df))
    )

    # Split: same host cannot appear in both train and test
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    g_train = groups[train_idx]
    price_test = price_actual[test_idx]

    # --- Naive baselines (no ML) ---
    global_median = np.median(np.expm1(y_train))
    median_pred = np.full(len(price_test), global_median)

    rt_col_present = "room_type" in X_train.columns
    if rt_col_present:
        rt_medians = (
            pd.DataFrame({"rt": X_train["room_type"].values, "lp": y_train})
            .groupby("rt")["lp"]
            .median()
        )
        default_log_price = float(np.log1p(global_median))
        rt_pred = np.array([
            np.expm1(
                float(rt_medians[rt]) if rt in rt_medians.index else default_log_price
            )
            for rt in X_test["room_type"].values
        ])
    else:
        rt_pred = median_pred

    comparison_rows = [
        _compute_test_metrics(price_test, median_pred, "Global median baseline"),
        _compute_test_metrics(price_test, rt_pred, "Room-type median baseline"),
    ]

    # --- Model pipelines ---
    models_def = {
        "Ridge": Pipeline([
            ("preprocessor", _build_preprocessor(num_cols, ohe_cols, target_enc_cols)),
            ("model", Ridge(alpha=10.0)),
        ]),
        "Random Forest": Pipeline([
            ("preprocessor", _build_preprocessor(num_cols, ohe_cols, target_enc_cols)),
            ("model", RandomForestRegressor(
                n_estimators=300,
                min_samples_leaf=3,
                random_state=42,
                n_jobs=-1,
            )),
        ]),
        "Gradient Boosting": Pipeline([
            ("preprocessor", _build_preprocessor(num_cols, ohe_cols, target_enc_cols)),
            ("model", _get_lgbm()),
        ]),
    }

    cv = GroupKFold(n_splits=5)
    currency_scorer = _currency_mae_scorer  # callable (estimator, X, y) — no make_scorer wrapper
    cv_records = []
    best_name, best_mae, best_pipeline = None, float("inf"), None

    for name, pipeline in models_def.items():
        cv_res = cross_validate(
            pipeline,
            X_train,
            y_train,
            cv=cv,
            groups=g_train,
            scoring={"currency_mae": currency_scorer, "r2": "r2"},
            return_train_score=True,
        )

        cv_mae = -cv_res["test_currency_mae"].mean()
        cv_mae_std = cv_res["test_currency_mae"].std()
        cv_r2 = cv_res["test_r2"].mean()
        train_mae = -cv_res["train_currency_mae"].mean()

        cv_records.append({
            "model": name,
            "cv_mae_mean": round(cv_mae, 2),
            "cv_mae_std": round(cv_mae_std, 2),
            "cv_r2_mean": round(cv_r2, 4),
            "train_mae_mean": round(train_mae, 2),
            "overfit_gap": round(train_mae - cv_mae, 2),
        })

        # Full train-set fit for test evaluation
        pipeline.fit(X_train, y_train)
        price_pred = np.expm1(np.asarray(pipeline.predict(X_test)))
        metrics = _compute_test_metrics(price_test, price_pred, name)
        comparison_rows.append(metrics)

        if metrics["test_mae"] < best_mae:
            best_mae = metrics["test_mae"]
            best_name = name
            best_pipeline = pipeline

    # --- Save comparison tables ---
    pd.DataFrame(comparison_rows).to_csv(
        MODEL_RESULTS / f"price_model_comparison_{city}.csv", index=False
    )
    pd.DataFrame(cv_records).to_csv(
        MODEL_RESULTS / f"cross_validation_results_{city}.csv", index=False
    )

    # --- Residuals for the best model ---
    assert best_pipeline is not None, "no model was selected during training"
    price_pred_best = np.expm1(np.asarray(best_pipeline.predict(X_test)))
    residuals_df = pd.DataFrame({
        "actual_price": price_test,
        "predicted_price": price_pred_best.round(2),
        "residual": (price_test - price_pred_best).round(2),
        "absolute_error": np.abs(price_test - price_pred_best).round(2),
        "pct_error": (
            np.abs(price_test - price_pred_best) / price_test.clip(1e-9) * 100
        ).round(2),
    })
    for col in ["room_type", "neighbourhood_cleansed", "property_type_bucket"]:
        if col in X_test.columns:
            residuals_df[col] = X_test[col].values
    residuals_df.to_csv(MODEL_RESULTS / f"residuals_{city}.csv", index=False)

    # --- Save model and metadata ---
    model_path = MODELS_DIR / f"{city}_price_model.joblib"
    joblib.dump(best_pipeline, model_path)

    metadata = {
        "city": city,
        "best_model": best_name,
        "test_mae": best_mae,
        "feature_count": len(feature_cols),
        "feature_names": feature_cols,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "numeric_features": num_cols,
        "ohe_features": ohe_cols,
        "target_enc_features": target_enc_cols,
    }
    with open(MODELS_DIR / f"{city}_model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    return {
        "status": "ok",
        "city": city,
        "best_model": best_name,
        "best_test_mae": round(best_mae, 2),
        "model_path": str(model_path),
        "comparison_csv": str(MODEL_RESULTS / f"price_model_comparison_{city}.csv"),
        "cv_csv": str(MODEL_RESULTS / f"cross_validation_results_{city}.csv"),
        "residuals_csv": str(MODEL_RESULTS / f"residuals_{city}.csv"),
    }


def run(city: str = "london") -> dict:
    return train(city)


if __name__ == "__main__":
    import sys

    city = sys.argv[1] if len(sys.argv) > 1 else "london"
    result = run(city)
    print(json.dumps(result, indent=2))
