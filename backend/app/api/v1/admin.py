from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin
from app.utils.cache import cache_delete_pattern

router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/ingest/{source}")
async def trigger_ingestion(source: str):
    from app.tasks.ingestion_tasks import run_ingestion
    task = run_ingestion.delay(source)
    return {"task_id": task.id, "source": source, "status": "queued"}


@router.post("/ml/retrain")
async def trigger_retrain():
    from app.tasks.ml_tasks import retrain_model
    task = retrain_model.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/ml/predict-all")
async def trigger_predict_all():
    from app.tasks.ml_tasks import run_batch_predict
    task = run_batch_predict.delay()
    # Invalidate model-info cache so fresh version is returned next call
    await cache_delete_pattern("model:info")
    return {"task_id": task.id, "status": "queued"}


@router.post("/ml/osm-enrich")
async def trigger_osm_enrich(suburb_ids: list[int] | None = None):
    """Queue an OSM enrichment run for all or specific suburbs."""
    from app.tasks.ml_tasks import enrich_osm
    task = enrich_osm.delay(suburb_ids)
    # Invalidate suburb caches (OSM data feeds into suburb summaries)
    await cache_delete_pattern("suburbs:*")
    return {"task_id": task.id, "suburb_ids": suburb_ids, "status": "queued"}


@router.get("/ingestion-runs")
async def list_ingestion_runs(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, desc
    from app.db.models.ingestion_log import IngestionRun
    result = await db.execute(
        select(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(limit)
    )
    runs = result.scalars().all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "status": r.status,
            "records_fetched": r.records_fetched,
            "records_inserted": r.records_inserted,
            "records_updated": r.records_updated,
            "error_message": r.error_message,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
        }
        for r in runs
    ]


@router.delete("/cache")
async def clear_cache(pattern: str = Query(default="*")):
    """Clear Redis cache keys matching a glob pattern. Default clears all."""
    await cache_delete_pattern(pattern)
    return {"status": "ok", "pattern": pattern}
