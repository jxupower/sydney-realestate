"""ML evaluation metrics — MAE, MAPE, R², per-suburb breakdown.

CLI usage:
    python -m app.ml.evaluation [--artifact path/to/model.joblib]
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)


# ── Core metrics ──────────────────────────────────────────────────────────────

def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0


def metrics_dict(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae_cents": mae(y_true, y_pred),
        "mae_dollars": mae(y_true, y_pred) / 100,
        "mape_pct": mape(y_true, y_pred),
        "r2": r2(y_true, y_pred),
        "n": len(y_true),
    }


def print_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    suburb_labels: pd.Series | None = None,
) -> None:
    m = metrics_dict(y_true, y_pred)
    print("\n=== Model Evaluation ===")
    print(f"  Samples : {m['n']:,}")
    print(f"  MAE     : ${m['mae_dollars']:,.0f}")
    print(f"  MAPE    : {m['mape_pct']:.2f}%")
    print(f"  R²      : {m['r2']:.4f}")

    if suburb_labels is not None:
        print("\n--- Per-suburb MAPE (top 20 worst) ---")
        df = pd.DataFrame({"true": y_true, "pred": y_pred, "suburb": suburb_labels})
        grouped = df.groupby("suburb").apply(
            lambda g: pd.Series({
                "mape": mape(g["true"].values, g["pred"].values),
                "n": len(g),
            }),
            include_groups=False,
        )
        worst = grouped[grouped["n"] >= 5].nlargest(20, "mape")
        for suburb, row in worst.iterrows():
            print(f"  {suburb:<30s}  MAPE={row['mape']:5.1f}%  n={int(row['n'])}")
    print()


# ── CLI entry point ───────────────────────────────────────────────────────────

async def _run_evaluation(artifact_path: Path | None) -> None:
    from app.ml.features import FeatureBuilder
    from app.ml.model import ValuationModel
    from app.ml.trainer import _latest_artifact
    from app.db.session import AsyncSessionLocal

    configure_logging()

    path = artifact_path or _latest_artifact()
    if path is None or not path.exists():
        logger.error("No model artifact found. Run trainer first.")
        return

    model = ValuationModel.load(path)
    logger.info("Loaded model", artifact=str(path))

    async with AsyncSessionLocal() as db:
        fb = FeatureBuilder(db)
        df = await fb.build_for_training()

    if df.empty or "target_price_cents" not in df.columns:
        logger.error("No training data available.")
        return

    df = df.dropna(subset=["target_price_cents"])
    y_true = df["target_price_cents"].values.astype(float)
    y_pred = model.predict_df(df)

    suburb_col = df.get("address_suburb") if hasattr(df, "get") else None
    print_report(y_true, y_pred, suburb_labels=suburb_col)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(_run_evaluation(args.artifact))
