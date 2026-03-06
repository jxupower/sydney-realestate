"""ML Celery tasks."""

import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="ml.retrain", bind=True, time_limit=3600, max_retries=2)
def retrain_model(self) -> dict:
    """Retrain the XGBoost valuation model on all sold properties."""
    logger.info("ML retrain task started", task_id=self.request.id)
    try:
        from app.ml.trainer import run_training
        result = asyncio.get_event_loop().run_until_complete(run_training())
        logger.info("ML retrain complete", result=result, task_id=self.request.id)
        return result
    except Exception as exc:
        logger.error("ML retrain failed", error=str(exc), task_id=self.request.id)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="ml.predict_all", bind=True, time_limit=1800, max_retries=2)
def run_batch_predict(self) -> dict:
    """Run batch prediction for all active for-sale listings."""
    logger.info("Batch predict task started", task_id=self.request.id)
    try:
        from app.ml.predictor import run_batch_predict as _predict
        result = asyncio.get_event_loop().run_until_complete(_predict())
        logger.info("Batch predict complete", result=result, task_id=self.request.id)
        return result
    except Exception as exc:
        logger.error("Batch predict failed", error=str(exc), task_id=self.request.id)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="ingestion.osm_enrich", bind=True, time_limit=7200)
def enrich_osm(self, suburb_ids: list[int] | None = None) -> dict:
    """Refresh OSM amenity data for all (or specific) suburbs."""
    logger.info("OSM enrichment task started", task_id=self.request.id)
    try:
        from app.ingestion.osm_enricher import enrich_suburbs
        result = asyncio.get_event_loop().run_until_complete(enrich_suburbs(suburb_ids))
        logger.info("OSM enrichment complete", result=result, task_id=self.request.id)
        return result
    except Exception as exc:
        logger.error("OSM enrichment failed", error=str(exc), task_id=self.request.id)
        raise
