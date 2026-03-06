from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.valuation_repo import ValuationRepository

router = APIRouter()


@router.get("/model-info")
async def model_info(db: AsyncSession = Depends(get_db)):
    """Return current active model version and training metrics."""
    repo = ValuationRepository(db)
    return await repo.get_active_model_info()


@router.post("/predict")
async def predict_hypothetical(body: dict, db: AsyncSession = Depends(get_db)):
    """On-demand valuation for a hypothetical property dict (for what-if queries)."""
    # Deferred to Phase 2 when ML model is ready
    return {"detail": "ML model not yet trained — available in Phase 2"}
