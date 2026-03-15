"""Ingestion coordinator — orchestrates all ingesters and writes to the database.

CLI usage:
    python -m app.ingestion.coordinator --source domain_api
    python -m app.ingestion.coordinator --source homely
    python -m app.ingestion.coordinator --source onthehouse
    python -m app.ingestion.coordinator --source valuer_general
    python -m app.ingestion.coordinator --source nsw_sales
    python -m app.ingestion.coordinator --source fuzzy_vg_match
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

VALID_SOURCES = [
    "domain_api", "homely", "onthehouse", "valuer_general", "nsw_sales",
    "fuzzy_vg_match", "geocode_suburbs", "clear_seed", "all",
]


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


async def _run_onthehouse(db: AsyncSession, run: IngestionRun) -> tuple[int, int]:
    import hashlib
    import random
    from app.ingestion.onthehouse_scraper import OnTheHouseScraper

    ingester = OnTheHouseScraper()
    raw_items = await ingester.fetch()
    run.records_fetched = (run.records_fetched or 0) + len(raw_items)

    repo = PropertyRepository(db)
    suburb_repo = SuburbRepository(db)
    inserted = updated = 0

    for raw in raw_items:
        suburb_id = None
        suburb = None
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

        # OTH list pages don't provide lat/lng — fall back to suburb centroid + jitter
        # so properties appear as map markers. Jitter is deterministic (md5 seed) so
        # re-running the same URL always pins to the same spot.
        if not data.get("latitude") and suburb and suburb.latitude:
            seed = int(hashlib.md5(raw.url.encode()).hexdigest()[:8], 16)
            rng = random.Random(seed)
            data["latitude"] = suburb.latitude + rng.uniform(-0.005, 0.005)
            data["longitude"] = suburb.longitude + rng.uniform(-0.005, 0.005)

        _, was_inserted = await repo.upsert(data)
        if was_inserted:
            inserted += 1
        else:
            updated += 1

    await db.commit()
    logger.info("OnTheHouse ingestion complete", inserted=inserted, updated=updated)
    return inserted, updated


async def _run_homely(db: AsyncSession, run: IngestionRun) -> tuple[int, int]:
    from app.ingestion.homely_scraper import HomelyScraper

    ingester = HomelyScraper()
    raw_items = await ingester.fetch()
    run.records_fetched = (run.records_fetched or 0) + len(raw_items)

    repo = PropertyRepository(db)
    suburb_repo = SuburbRepository(db)
    inserted = updated = 0

    for raw in raw_items:
        if not is_within_search_radius(raw.latitude, raw.longitude):
            # Homely may not provide lat/lng — allow None through (suburb-only records)
            if raw.latitude is not None or raw.longitude is not None:
                continue

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

        _, was_inserted = await repo.upsert(data)
        if was_inserted:
            inserted += 1
        else:
            updated += 1

    await db.commit()
    logger.info("Homely ingestion complete", inserted=inserted, updated=updated)
    return inserted, updated


async def _run_clear_seed(db: AsyncSession) -> tuple[int, int]:
    """Delete all seed/synthetic properties and their dependents (ml_valuations, watchlist)."""
    from sqlalchemy import text

    logger.info("Clearing seed/synthetic data from database")
    await db.execute(text(
        "DELETE FROM ml_valuations WHERE property_id IN "
        "(SELECT id FROM properties WHERE source IN ('seed', 'synthetic'))"
    ))
    await db.execute(text(
        "DELETE FROM watchlist WHERE property_id IN "
        "(SELECT id FROM properties WHERE source IN ('seed', 'synthetic'))"
    ))
    result = await db.execute(text(
        "DELETE FROM properties WHERE source IN ('seed', 'synthetic') RETURNING id"
    ))
    deleted = len(result.fetchall())
    await db.commit()
    logger.info("Seed data cleared", deleted=deleted)
    return deleted, 0


async def _run_geocode_suburbs(db: AsyncSession) -> tuple[int, int]:
    """Geocode all suburbs with NULL lat/lng via Nominatim."""
    from app.ingestion.suburb_geocoder import geocode_all_suburbs

    result = await geocode_all_suburbs(db)
    return result["geocoded"], result["failed"]


async def _run_fuzzy_vg_match() -> tuple[int, int]:
    from app.ingestion.vg_matcher import run_vg_matching

    result = await run_vg_matching()
    return result["matched"], 0


async def _run_nsw_sales(db: AsyncSession, run: IngestionRun) -> tuple[int, int]:
    """Ingest NSW Property Sales data as ML training records.

    Each sale is upserted by (source='nsw_sales', external_id) derived from the
    VG district+property+sale_counter key — making ingestion fully idempotent.
    Re-running with the same ZIPs will update existing rows rather than duplicating.
    """
    from app.ingestion.nsw_sales import load_all_nsw_sales

    records = load_all_nsw_sales()
    run.records_fetched = len(records)
    inserted = updated = 0

    repo = PropertyRepository(db)
    suburb_repo = SuburbRepository(db)

    for rec in records:
        if not rec.get("address_suburb"):
            continue

        # Build stable external_id from VG identifiers (DAT) or address+date (CSV)
        source_key = rec.get("_source_key")
        if source_key:
            external_id = f"vg_{source_key}"
        else:
            sold_date = rec.get("sold_at")
            date_str = sold_date.strftime("%Y%m%d") if sold_date else "unknown"
            street_slug = (rec.get("address_street") or "").replace(" ", "_")[:40]
            postcode = rec.get("address_postcode") or "0000"
            external_id = f"nsw_{postcode}_{street_slug}_{date_str}"

        url = f"nsw_sales://{external_id}"
        postcode = rec.get("address_postcode") or "0000"
        is_strata = rec.get("strata", False)
        property_type = "apartment" if is_strata else "house"

        suburb_id = None
        if rec.get("address_suburb") and postcode:
            suburb, _ = await suburb_repo.upsert(
                name=rec["address_suburb"],
                postcode=postcode,
            )
            suburb_id = suburb.id

        data = {
            "external_id": external_id,
            "source": "nsw_sales",
            "url": url,
            "status": "sold",
            "property_type": property_type,
            "address_street": rec.get("address_street"),
            "address_suburb": rec.get("address_suburb"),
            "address_postcode": postcode,
            "suburb_id": suburb_id,
            "land_size_sqm": rec.get("land_size_sqm"),
            "sold_price": rec.get("sold_price_cents"),
            "sold_at": rec.get("sold_at"),
        }

        _, was_inserted = await repo.upsert(data)
        if was_inserted:
            inserted += 1
        else:
            updated += 1

        # Commit periodically to keep memory bounded on large imports
        if (inserted + updated) % 1000 == 0:
            await db.commit()
            logger.info(
                "NSW Sales progress",
                inserted=inserted,
                updated=updated,
                total_processed=inserted + updated,
            )

    await db.commit()
    logger.info("NSW Sales ingestion complete", inserted=inserted, updated=updated)
    return inserted, updated


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
            elif source == "homely":
                inserted, updated = await _run_homely(db, run)
            elif source == "onthehouse":
                inserted, updated = await _run_onthehouse(db, run)
            elif source == "valuer_general":
                inserted, updated = await _run_valuer_general(db, run)
            elif source == "nsw_sales":
                inserted, updated = await _run_nsw_sales(db, run)
            elif source == "fuzzy_vg_match":
                inserted, updated = await _run_fuzzy_vg_match()
            elif source == "clear_seed":
                inserted, updated = await _run_clear_seed(db)
            elif source == "geocode_suburbs":
                inserted, updated = await _run_geocode_suburbs(db)
            elif source == "all":
                i1, u1 = await _run_domain(db, run)
                i2, u2 = await _run_homely(db, run)
                i3, u3 = await _run_onthehouse(db, run)
                i4, u4 = await _run_valuer_general(db, run)
                i5, u5 = await _run_nsw_sales(db, run)
                i6, u6 = await _run_fuzzy_vg_match()
                inserted, updated = i1+i2+i3+i4+i5+i6, u1+u2+u3+u4+u5+u6
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
