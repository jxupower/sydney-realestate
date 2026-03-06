"""ValuationModel — XGBoost + sklearn Pipeline wrapper.

The pipeline:
  ColumnTransformer
    ├── num: SimpleImputer(median) → StandardScaler
    └── cat: SimpleImputer(constant='unknown') → OneHotEncoder(handle_unknown='ignore')
  └── XGBRegressor

Usage:
    model = ValuationModel()
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    model.save(path)

    loaded = ValuationModel.load(path)
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from app.ml.features import CAT_COLS, NUM_COLS

# ── Default hyperparameters ───────────────────────────────────────────────────

DEFAULT_XGB_PARAMS = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",   # fast histogram method
    "early_stopping_rounds": 30,
    "eval_metric": "mae",
}


class ValuationModel:
    """Wraps the full sklearn Pipeline + XGBoost regressor."""

    def __init__(self, xgb_params: dict | None = None):
        params = {**DEFAULT_XGB_PARAMS, **(xgb_params or {})}
        self.pipeline = self._build_pipeline(params)
        self._is_fitted = False

    # ── Pipeline factory ─────────────────────────────────────────────────────

    @staticmethod
    def _build_pipeline(xgb_params: dict) -> Pipeline:
        num_transformer = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])
        cat_transformer = Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])
        preprocessor = ColumnTransformer(
            transformers=[
                ("num", num_transformer, NUM_COLS),
                ("cat", cat_transformer, CAT_COLS),
            ],
            remainder="drop",
        )

        # Strip early_stopping_rounds from pipeline params — it must be passed
        # to fit() via eval_set, not the constructor, for the wrapped estimator.
        fit_params = {k: v for k, v in xgb_params.items()
                      if k != "early_stopping_rounds"}
        early_stop = xgb_params.get("early_stopping_rounds")

        regressor = XGBRegressor(**fit_params)
        # Store for use in fit()
        regressor._early_stopping_rounds = early_stop

        return Pipeline([
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ])

    # ── Fit / predict ─────────────────────────────────────────────────────────

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame | None = None,
        y_val: pd.Series | None = None,
    ) -> "ValuationModel":
        """Fit the pipeline. Passes eval_set to XGBoost if validation data provided."""
        regressor: XGBRegressor = self.pipeline.named_steps["regressor"]
        preprocessor = self.pipeline.named_steps["preprocessor"]

        if X_val is not None and y_val is not None:
            # Fit preprocessor first so we can transform val set
            preprocessor.fit(X_train)
            X_train_t = preprocessor.transform(X_train)
            X_val_t = preprocessor.transform(X_val)

            early_stop = getattr(regressor, "_early_stopping_rounds", None)
            fit_kwargs = {"eval_set": [(X_val_t, y_val.values)]}
            if early_stop:
                fit_kwargs["early_stopping_rounds"] = early_stop

            regressor.fit(X_train_t, y_train.values, **fit_kwargs)
            self._is_fitted = True
        else:
            self.pipeline.fit(X_train, y_train.values)
            self._is_fitted = True

        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Model has not been fitted yet.")
        return self.pipeline.predict(X)

    def predict_df(self, df: pd.DataFrame) -> np.ndarray:
        """Predict from a full feature DataFrame (handles missing cols gracefully)."""
        X = df[CAT_COLS + NUM_COLS].copy()
        return self.predict(X)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> "ValuationModel":
        model = joblib.load(path)
        if not isinstance(model, cls):
            raise TypeError(f"Loaded object is {type(model)}, expected ValuationModel")
        return model

    # ── Preprocessor accessor (needed by SHAP) ────────────────────────────────

    @property
    def preprocessor(self) -> ColumnTransformer:
        return self.pipeline.named_steps["preprocessor"]

    @property
    def xgb_regressor(self) -> XGBRegressor:
        return self.pipeline.named_steps["regressor"]

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Return preprocessed feature matrix (for SHAP TreeExplainer)."""
        return self.preprocessor.transform(X)

    def get_feature_names(self) -> list[str]:
        """Return feature names after preprocessing (for SHAP labelling)."""
        return list(self.preprocessor.get_feature_names_out())
