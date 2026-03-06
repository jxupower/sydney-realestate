"""Seed the suburbs table from sydney_suburbs.json.

Run: python -m app.seeds.seed_suburbs
"""
import asyncio
import json
from pathlib import Path

import structlog

from app.db.session import AsyncSessionLocal
from app.repositories.suburb_repo import SuburbRepository
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)


async def seed():
    configure_logging()
    data_file = Path(__file__).parent / "sydney_suburbs.json"
    suburbs = json.loads(data_file.read_text())

    async with AsyncSessionLocal() as db:
        repo = SuburbRepository(db)
        inserted = updated = 0
        for s in suburbs:
            _, was_inserted = await repo.upsert(
                name=s["name"],
                postcode=s["postcode"],
                lga=s.get("lga"),
                latitude=s.get("latitude"),
                longitude=s.get("longitude"),
                state="NSW",
            )
            if was_inserted:
                inserted += 1
            else:
                updated += 1
        await db.commit()

    logger.info("Suburb seed complete", inserted=inserted, updated=updated)


if __name__ == "__main__":
    asyncio.run(seed())
