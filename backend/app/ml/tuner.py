"""Optuna hyperparameter tuning for the XGBoost valuation model.

Runs an Optuna study that searches the XGBoost parameter space, evaluates
each trial with MAPE on the time-based holdout set, then saves the best
model artifact.

CLI usage:
    python -m app.ml.tuner
    python -m app.ml.tuner --trials 100
    python -m app.ml.tuner --trials 200 --timeout 7200
    python -m app.ml.tuner --cutoff 2025-01-01 --trials 50
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date

import numpy as np
import optuna
import pandas as pd
import structlog

from app.ml.features import FeatureBuilder, ALL_FEATURE_COLS
from app.ml.model import ValuationModel
from app.ml.trainer import (
    ARTIFACTS_DIR,
    DEFAULT_CUTOFF,
    MIN_TRAINING_ROWS,
    _artifact_path,
    _split_by_date,
)
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)

# Silence Optuna's verbose per-trial logging; progress is shown via structlog
optuna.logging.set_verbosity(optuna.logging.WARNING)


def _objective(
    trial: optuna.Trial,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> float:
    """Optuna objective — returns MAPE on the validation set (lower = better)."""
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 200, 1000),
        "max_depth": trial.suggest_int("max_depth", 3, 9),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "gamma": trial.suggest_float("gamma", 0.0, 5.0),
    }

    model = ValuationModel(xgb_params=params)
    model.fit(X_train, y_train, X_val=X_val, y_val=y_val)
    y_pred = model.predict_df(X_val)

    # MAPE — guard against zero-value targets
    mape = float(
        np.mean(np.abs((y_val.values - y_pred) / np.maximum(y_val.values, 1))) * 100
    )
    return mape


async def run_tuning(
    n_trials: int = 50,
    timeout: int | None = None,
    cutoff: date = DEFAULT_CUTOFF,
) -> dict:
    """Run the Optuna study and save the winning model artifact.

    Args:
        n_trials:  Max number of Optuna trials.
        timeout:   Hard wall-clock limit in seconds (None = unlimited).
        cutoff:    Time-based train/test split date.

    Returns:
        Dict with status, best_mape, best_params, artifact path, n_trials.
    """
    configure_logging()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    from app.db.session import AsyncSessionLocal

    logger.info("Loading training data for tuning...")
    async with AsyncSessionLocal() as db:
        fb = FeatureBuilder(db)
        df = await fb.build_for_training()

    df = df.dropna(subset=["target_price_cents"])
    logger.info("Training data loaded", rows=len(df))

    if len(df) < MIN_TRAINING_ROWS:
        logger.error("Insufficient data for tuning", rows=len(df))
        return {"status": "failed", "reason": "insufficient_data", "rows": len(df)}

    train_df, test_df = _split_by_date(df, cutoff)

    if len(train_df) < MIN_TRAINING_ROWS:
        logger.warning("Falling back to random 80/20 split (not enough pre-cutoff data)")
        from sklearn.model_selection import train_test_split
        train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

    X_train = train_df[ALL_FEATURE_COLS].copy()
    y_train = train_df["target_price_cents"].astype(float)
    X_val = test_df[ALL_FEATURE_COLS].copy()
    y_val = test_df["target_price_cents"].astype(float)

    logger.info(
        "Starting Optuna study",
        trials=n_trials,
        timeout=timeout,
        train_rows=len(X_train),
        val_rows=len(X_val),
    )

    study = optuna.create_study(
        direction="minimize",
        study_name="xgb_valuation",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    completed_trials: list[int] = []

    def _log_callback(study: optuna.Study, trial: optuna.Trial) -> None:
        completed_trials.append(trial.number)
        if len(completed_trials) % 10 == 0:
            logger.info(
                "Optuna progress",
                completed=len(completed_trials),
                best_mape=f"{study.best_value:.2f}%",
            )

    study.optimize(
        lambda trial: _objective(trial, X_train, y_train, X_val, y_val),
        n_trials=n_trials,
        timeout=timeout,
        callbacks=[_log_callback],
        show_progress_bar=False,
    )

    best_params = study.best_params
    best_mape = study.best_value
    best_trial_num = study.best_trial.number

    logger.info(
        "Optuna study complete",
        trials_run=len(study.trials),
        best_mape=f"{best_mape:.2f}%",
        best_trial=best_trial_num,
        best_params=best_params,
    )

    # Train final model with the best params and save artifact
    final_model = ValuationModel(xgb_params=best_params)
    final_model.fit(X_train, y_train, X_val=X_val, y_val=y_val)

    artifact = _artifact_path(version=f"optuna_t{best_trial_num}")
    final_model.save(artifact)
    logger.info("Best model artifact saved", path=str(artifact))

    return {
        "status": "completed",
        "best_mape": best_mape,
        "best_params": best_params,
        "artifact": str(artifact),
        "n_trials": len(study.trials),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optuna hyperparameter tuning for XGBoost")
    parser.add_argument(
        "--trials", type=int, default=50, help="Number of Optuna trials (default: 50)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Max seconds to run the study (default: unlimited)",
    )
    parser.add_argument(
        "--cutoff",
        type=date.fromisoformat,
        default=DEFAULT_CUTOFF,
        help="ISO date — train on sold_at < this date",
    )
    args = parser.parse_args()
    asyncio.run(run_tuning(n_trials=args.trials, timeout=args.timeout, cutoff=args.cutoff))
