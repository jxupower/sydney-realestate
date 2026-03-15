"""XGBoost training pipeline.

Workflow:
  1. Load all sold properties via FeatureBuilder
  2. Time-based train/test split (no data leakage)
  3. Fit ValuationModel pipeline
  4. Evaluate on holdout set
  5. Save artifact to ml/artifacts/xgb_{date}.joblib

CLI usage:
    python -m app.ml.trainer
    python -m app.ml.trainer --cutoff 2025-01-01 --no-eval
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from app.ml.features import FeatureBuilder, CAT_COLS, NUM_COLS, ALL_FEATURE_COLS
from app.ml.model import ValuationModel
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

# Default time split: train on everything before this date, test on after
DEFAULT_CUTOFF = date(2025, 6, 1)
MIN_TRAINING_ROWS = 100


def _latest_artifact() -> Path | None:
    """Return the most recent .joblib artifact, or None."""
    files = sorted(ARTIFACTS_DIR.glob("xgb_*.joblib"))
    return files[-1] if files else None


def _artifact_path(version: str | None = None) -> Path:
    tag = version or datetime.now().strftime("%Y%m%d_%H%M%S")
    return ARTIFACTS_DIR / f"xgb_{tag}.joblib"


def _split_by_date(
    df: pd.DataFrame, cutoff: date
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Time-based split. sold_at must be present."""
    if "sold_at" not in df.columns:
        raise ValueError("DataFrame must contain 'sold_at' column for time-based split.")

    df = df.copy()
    df["sold_at"] = pd.to_datetime(df["sold_at"], errors="coerce")
    train_mask = df["sold_at"].dt.date < cutoff
    return df[train_mask].copy(), df[~train_mask].copy()


async def run_training(
    cutoff: date = DEFAULT_CUTOFF,
    run_eval: bool = True,
    xgb_params: dict | None = None,
) -> dict:
    """Main training entry point. Returns metrics dict."""
    configure_logging()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    from app.db.session import AsyncSessionLocal

    from datetime import timedelta
    sold_since = cutoff.replace(year=cutoff.year - 5)
    logger.info("Loading training data from database...", sold_since=str(sold_since), cutoff=str(cutoff))
    async with AsyncSessionLocal() as db:
        fb = FeatureBuilder(db)
        df = await fb.build_for_training(sold_since=sold_since)

    if df.empty:
        logger.error("No training data found. Ingest sold properties first.")
        return {"status": "failed", "reason": "no_data"}

    df = df.dropna(subset=["target_price_cents"])
    logger.info("Training data loaded", rows=len(df))

    if len(df) < MIN_TRAINING_ROWS:
        logger.error(
            "Insufficient training data",
            rows=len(df),
            required=MIN_TRAINING_ROWS,
        )
        return {"status": "failed", "reason": "insufficient_data", "rows": len(df)}

    # Time-based split
    train_df, test_df = _split_by_date(df, cutoff)
    logger.info(
        "Train/test split",
        train=len(train_df),
        test=len(test_df),
        cutoff=str(cutoff),
    )

    if len(train_df) < MIN_TRAINING_ROWS:
        # Fall back to random 80/20 if not enough data before cutoff
        logger.warning("Falling back to random 80/20 split")
        from sklearn.model_selection import train_test_split
        train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

    X_train = train_df[ALL_FEATURE_COLS].copy()
    y_train = train_df["target_price_cents"].astype(float)
    X_val = test_df[ALL_FEATURE_COLS].copy()
    y_val = test_df["target_price_cents"].astype(float)

    # Train
    logger.info("Fitting model...")
    model = ValuationModel(xgb_params=xgb_params)
    model.fit(X_train, y_train, X_val=X_val, y_val=y_val)

    # Save
    artifact = _artifact_path()
    model.save(artifact)
    logger.info("Model saved", path=str(artifact))

    result: dict = {
        "status": "completed",
        "artifact": str(artifact),
        "train_rows": len(train_df),
        "test_rows": len(test_df),
    }

    # Evaluate
    if run_eval and len(test_df) > 0:
        from app.ml.evaluation import metrics_dict, print_report

        y_pred = model.predict_df(X_val)
        m = metrics_dict(y_val.values, y_pred)
        result.update(m)

        logger.info(
            "Evaluation complete",
            mae_dollars=f"${m['mae_dollars']:,.0f}",
            mape=f"{m['mape_pct']:.2f}%",
            r2=f"{m['r2']:.4f}",
        )
        print_report(y_val.values, y_pred)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the XGBoost valuation model")
    parser.add_argument(
        "--cutoff",
        type=date.fromisoformat,
        default=DEFAULT_CUTOFF,
        help="ISO date — train on sold_at < this date (default: 2025-06-01)",
    )
    parser.add_argument(
        "--no-eval",
        dest="run_eval",
        action="store_false",
        help="Skip evaluation on holdout set",
    )
    args = parser.parse_args()
    asyncio.run(run_training(cutoff=args.cutoff, run_eval=args.run_eval))
