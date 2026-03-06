"""Batch predictor — loads active listings, predicts fair value, computes SHAP.

Writes one MLValuation row per property (upserts by property_id + model_version).

CLI usage:
    python -m app.ml.predictor
    python -m app.ml.predictor --artifact path/to/xgb_20250601.joblib
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import shap
import structlog
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.ml.features import FeatureBuilder, ALL_FEATURE_COLS
from app.ml.model import ValuationModel
from app.ml.trainer import _latest_artifact, ARTIFACTS_DIR
from app.db.models.valuation import MLValuation
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)

BATCH_SIZE = 200          # process N properties at a time
CONFIDENCE_Z = 1.645      # ~90% CI (z for 1-sided 95%)


def _model_version(artifact_path: Path) -> str:
    return artifact_path.stem  # e.g. "xgb_20250601_030000"


def _compute_confidence_interval(
    pred_cents: float, shap_values: np.ndarray
) -> tuple[int, int]:
    """Rough CI: ±1.645 * std(|shap_values|) scaled to prediction."""
    std = float(np.std(np.abs(shap_values))) if len(shap_values) else pred_cents * 0.05
    margin = CONFIDENCE_Z * std
    return int(max(0, pred_cents - margin)), int(pred_cents + margin)


def _underval_score(predicted_cents: float, list_price_cents: int | None) -> float | None:
    if not list_price_cents or list_price_cents <= 0:
        return None
    return round((predicted_cents - list_price_cents) / predicted_cents * 100, 2)


async def run_batch_predict(artifact_path: Path | None = None) -> dict:
    """Main entry point. Returns summary dict."""
    configure_logging()

    from app.db.session import AsyncSessionLocal

    # Resolve artifact
    path = artifact_path or _latest_artifact()
    if path is None or not path.exists():
        logger.error("No model artifact found. Run trainer first.")
        return {"status": "failed", "reason": "no_artifact"}

    model = ValuationModel.load(path)
    version = _model_version(path)
    logger.info("Loaded model", version=version, artifact=str(path))

    # Build SHAP explainer once (uses raw XGBoost booster)
    xgb_booster = model.xgb_regressor.get_booster()
    explainer = shap.TreeExplainer(xgb_booster)
    feature_names = model.get_feature_names()

    async with AsyncSessionLocal() as db:
        fb = FeatureBuilder(db)
        df = await fb.build_for_prediction()

        if df.empty:
            logger.info("No active for-sale properties found.")
            return {"status": "completed", "predicted": 0}

        logger.info("Predicting", properties=len(df))

        # Process in batches to control memory usage
        written = 0
        for start in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[start:start + BATCH_SIZE].copy()
            X = batch[ALL_FEATURE_COLS]

            # Preprocess → transformed matrix for SHAP
            X_t = model.transform(X)
            preds = model.xgb_regressor.predict(X_t)
            shap_vals = explainer.shap_values(X_t)  # shape: (n, features)

            for i, row in enumerate(batch.itertuples()):
                pred_cents = float(preds[i])
                sv = shap_vals[i].tolist() if hasattr(shap_vals, "__len__") else []
                shap_dict = dict(zip(feature_names, sv))

                ci_low, ci_high = _compute_confidence_interval(pred_cents, np.array(sv))
                underval = _underval_score(pred_cents, getattr(row, "list_price_cents", None))

                stmt = (
                    pg_insert(MLValuation)
                    .values(
                        property_id=row.id,
                        model_version=version,
                        predicted_value_cents=int(pred_cents),
                        confidence_interval_low=ci_low,
                        confidence_interval_high=ci_high,
                        underval_score_pct=underval,
                        feature_importances=shap_dict,
                        predicted_at=datetime.now(timezone.utc),
                    )
                    .on_conflict_do_update(
                        constraint="uq_valuation_property_version",
                        set_={
                            "predicted_value_cents": int(pred_cents),
                            "confidence_interval_low": ci_low,
                            "confidence_interval_high": ci_high,
                            "underval_score_pct": underval,
                            "feature_importances": shap_dict,
                            "predicted_at": datetime.now(timezone.utc),
                        },
                    )
                )
                await db.execute(stmt)
                written += 1

            await db.commit()
            logger.info("Batch committed", progress=f"{start + len(batch)}/{len(df)}")

    logger.info("Batch prediction complete", written=written, version=version)
    return {"status": "completed", "predicted": written, "model_version": version}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run batch ML predictions")
    parser.add_argument("--artifact", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(run_batch_predict(args.artifact))
