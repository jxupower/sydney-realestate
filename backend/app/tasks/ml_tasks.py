"""ML Celery tasks — stubbed for Phase 1, implemented in Phase 2."""

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="ml.retrain", bind=True, time_limit=3600)
def retrain_model(self) -> dict:
    """Retrain the XGBoost valuation model on all sold properties."""
    logger.info("ML retrain task started", task_id=self.request.id)
    # Full implementation in Phase 2 (app/ml/trainer.py)
    return {"status": "not_implemented", "message": "ML pipeline coming in Phase 2"}


@celery_app.task(name="ml.predict_all", bind=True, time_limit=1800)
def run_batch_predict(self) -> dict:
    """Run batch prediction for all active for-sale listings."""
    logger.info("Batch predict task started", task_id=self.request.id)
    # Full implementation in Phase 2 (app/ml/predictor.py)
    return {"status": "not_implemented", "message": "ML pipeline coming in Phase 2"}
