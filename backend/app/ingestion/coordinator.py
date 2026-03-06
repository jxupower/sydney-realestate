"""Ingestion coordinator — orchestrates all ingesters and writes to the database.

CLI usage:
    python -m app.ingestion.coordinator --source domain_api
    python -m app.ingestion.coordinator --source valuer_general
    python -m app.ingestion.coordinator --source nsw_sales
    python -m app.ingestion.coordinator --source all
"""

import argparse
import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models.ingestion_log import IngestionRun
from app.ingestion.base import RawProperty
from app.repositories.property_repo import PropertyRepository
from app.repositories.suburb_repo import SuburbRepository
from app.utils.geo import is_within_search_radius
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)

VALID_SOURCES = ["domain_api", "valuer_general", "nsw_sales", "all"]


async def _run_domain(db: AsyncSession, run: IngestionRun) -> tuple[int, int]:
    from app.ingestion.domain_api import DomainApiIngester
    ingester = DomainApiIngester()
    if not ingester.is_available():
        logger.warning("Domain API credentials not configured — skipping")
        return 0, 0

    raw_items = await ingester.fetch()
    run.records_fetched = len(raw_items)

    repo = PropertyRepository(db)
    suburb_repo = SuburbRepository(db)
    inserted = updated = 0

    for raw in raw_items:
        if not is_within_search_radius(raw.latitude, raw.longitude):
            continue

        # Resolve suburb FK
        suburb_id = None
        if raw.address_suburb and raw.address_postcode:
            suburb, _ = await suburb_repo.upsert(
                name=raw.address_suburb,
                postcode=raw.address_postcode,
                latitude=raw.latitude,
                longitude=raw.longitude,
            )
            suburb_id = suburb.id

        data = raw.to_db_dict()
        data["suburb_id"] = suburb_id

        prop, was_inserted = await repo.upsert(data)

        # Save images if new
        if was_inserted and raw.images:
            from app.db.models.property import PropertyImage
            for idx, img_url in enumerate(raw.images[:10]):  # cap at 10 images
                db.add(PropertyImage(property_id=prop.id, url=img_url, display_order=idx))

        if was_inserted:
            inserted += 1
        else:
            updated += 1

    await db.commit()
    logger.info("Domain ingestion complete", inserted=inserted, updated=updated)
    return inserted, updated


async def _run_valuer_general(db: AsyncSession, run: IngestionRun) -> tuple[int, int]:
    from app.ingestion.valuer_general import load_all_vg_csvs
    from app.db.models.valuer_general import ValuerGeneralRecord
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    records = load_all_vg_csvs()
    run.records_fetched = len(records)

    inserted = 0
    for rec in records:
        if not rec.get("lot_plan") or not rec.get("base_date"):
            continue
        stmt = (
            pg_insert(ValuerGeneralRecord)
            .values(**rec)
            .on_conflict_do_update(
                constraint="uq_vg_lot_plan_date",
                set_={k: v for k, v in rec.items() if k not in ("lot_plan", "base_date")},
            )
        )
        await db.execute(stmt)
        inserted += 1

    await db.commit()
    logger.info("VG import complete", records=inserted)
    return inserted, 0


async def _run_nsw_sales(db: AsyncSession, run: IngestionRun) -> tuple[int, int]:
    """Match NSW Sales records to existing properties and update sold_price/sold_at."""
    from app.ingestion.nsw_sales import load_all_nsw_sales
    from sqlalchemy import select, and_, update
    from app.db.models.property import Property

    records = load_all_nsw_sales()
    run.records_fetched = len(records)
    updated = 0

    for rec in records:
        if not rec.get("address_street") or not rec.get("address_suburb"):
            continue
        result = await db.execute(
            select(Property).where(
                and_(
                    Property.address_street.ilike(f"%{rec['address_street']}%"),
                    Property.address_suburb.ilike(rec["address_suburb"]),
                )
            ).limit(1)
        )
        prop = result.scalar_one_or_none()
        if prop and rec.get("sold_price_cents"):
            prop.sold_price = rec["sold_price_cents"]
            prop.sold_at = rec.get("sold_at")
            prop.status = "sold"
            if rec.get("land_size_sqm") and not prop.land_size_sqm:
                prop.land_size_sqm = rec["land_size_sqm"]
            updated += 1

    await db.commit()
    logger.info("NSW Sales update complete", updated=updated)
    return 0, updated


async def run_ingestion(source: str) -> dict:
    """Main entry point. Called by Celery tasks and CLI."""
    configure_logging()

    async with AsyncSessionLocal() as db:
        run = IngestionRun(source=source, status="running", started_at=datetime.now(timezone.utc))
        db.add(run)
        await db.flush()

        try:
            if source == "domain_api":
                inserted, updated = await _run_domain(db, run)
            elif source == "valuer_general":
                inserted, updated = await _run_valuer_general(db, run)
            elif source == "nsw_sales":
                inserted, updated = await _run_nsw_sales(db, run)
            elif source == "all":
                i1, u1 = await _run_domain(db, run)
                i2, u2 = await _run_valuer_general(db, run)
                i3, u3 = await _run_nsw_sales(db, run)
                inserted, updated = i1 + i2 + i3, u1 + u2 + u3
            else:
                raise ValueError(f"Unknown source: {source}. Valid: {VALID_SOURCES}")

            run.status = "completed"
            run.records_inserted = inserted
            run.records_updated = updated
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"status": "completed", "inserted": inserted, "updated": updated}

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.error("Ingestion failed", source=source, error=str(e))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run data ingestion")
    parser.add_argument(
        "--source",
        choices=VALID_SOURCES,
        required=True,
        help="Which data source to ingest",
    )
    args = parser.parse_args()
    asyncio.run(run_ingestion(args.source))
