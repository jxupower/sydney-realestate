import asyncio

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="ingestion.run", bind=True, max_retries=3)
def run_ingestion(self, source: str) -> dict:
    """Run a named ingestion source. Retries up to 3 times on failure."""
    from app.ingestion.coordinator import run_ingestion as _run

    logger.info("Starting ingestion task", source=source, task_id=self.request.id)
    try:
        result = asyncio.run(_run(source))
        logger.info("Ingestion task complete", source=source, result=result)
        return result
    except Exception as exc:
        logger.error("Ingestion task failed", source=source, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
