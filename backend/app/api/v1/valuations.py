from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.valuation_repo import ValuationRepository
from app.utils.cache import cache_get, cache_set

router = APIRouter()

_TTL_MODEL_INFO = 60   # 1 min


@router.get("/model-info")
async def model_info(db: AsyncSession = Depends(get_db)):
    """Return current active model version."""
    cached = await cache_get("model:info")
    if cached is not None:
        return cached

    repo = ValuationRepository(db)
    result = await repo.get_active_model_info()
    await cache_set("model:info", result, ttl_seconds=_TTL_MODEL_INFO)
    return result


@router.post("/predict")
async def predict_hypothetical(body: dict, db: AsyncSession = Depends(get_db)):
    """On-demand single-property valuation using the current model artifact.

    Accepts a property dict with the same fields as the feature builder.
    Returns predicted_value_dollars and underval_score_pct if list_price provided.
    """
    from pathlib import Path
    from app.ml.trainer import _latest_artifact
    from app.ml.model import ValuationModel
    from app.ml.features import ALL_FEATURE_COLS, CAT_COLS, NUM_COLS
    import pandas as pd

    artifact = _latest_artifact()
    if artifact is None or not artifact.exists():
        return {"detail": "No trained model available yet. Run /admin/ml/retrain first."}

    model = ValuationModel.load(artifact)

    # Build a single-row DataFrame from the body dict
    row = {col: body.get(col) for col in ALL_FEATURE_COLS}
    df = pd.DataFrame([row])
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    pred_cents = float(model.predict_df(df)[0])
    list_price_cents = body.get("list_price_cents")
    underval = None
    if list_price_cents:
        underval = round((pred_cents - list_price_cents) / pred_cents * 100, 2)

    return {
        "predicted_value_dollars": int(pred_cents // 100),
        "predicted_value_cents": int(pred_cents),
        "underval_score_pct": underval,
        "model_version": artifact.stem,
    }
