"""Suburb geocoder — backfills latitude/longitude for suburbs via Nominatim (OpenStreetMap).

Nominatim usage policy:
  - Max 1 request per second (we use 1.1s delay to be safe)
  - User-Agent header must identify the application
  - No API key required

Usage:
    python -m app.ingestion.coordinator --source geocode_suburbs
"""

import asyncio
from typing import Optional

import httpx
import structlog

from app.db.session import AsyncSessionLocal
from app.db.models.suburb import Suburb
from app.repositories.suburb_repo import SuburbRepository
from sqlalchemy import select

logger = structlog.get_logger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_REQUEST_DELAY = 1.1  # seconds — Nominatim 1 req/sec policy
_USER_AGENT = "SydneyRealEstateApp/1.0"


async def _geocode_suburb(client: httpx.AsyncClient, name: str) -> Optional[tuple[float, float]]:
    """Query Nominatim for the centroid of a NSW suburb. Returns (lat, lng) or None."""
    try:
        resp = await client.get(
            _NOMINATIM_URL,
            params={
                "q": f"{name} NSW Australia",
                "format": "json",
                "limit": 1,
                "countrycodes": "au",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning("Nominatim geocode failed", suburb=name, error=str(e))
    return None


async def geocode_all_suburbs(db) -> dict:
    """Geocode all suburbs that have NULL latitude/longitude.

    Updates suburb rows via SuburbRepository.upsert() which already supports
    latitude/longitude kwargs. Returns {"geocoded": int, "failed": int}.
    """
    result = await db.execute(
        select(Suburb).where(Suburb.latitude.is_(None))
    )
    suburbs = result.scalars().all()

    if not suburbs:
        logger.info("Suburb geocoder: all suburbs already have coordinates")
        return {"geocoded": 0, "failed": 0}

    logger.info("Suburb geocoder starting", total=len(suburbs))
    geocoded = 0
    failed = 0

    repo = SuburbRepository(db)

    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
        for suburb in suburbs:
            coords = await _geocode_suburb(client, suburb.name)
            if coords:
                lat, lng = coords
                # upsert updates existing row's kwargs (latitude, longitude)
                await repo.upsert(
                    name=suburb.name,
                    postcode=suburb.postcode,
                    latitude=lat,
                    longitude=lng,
                )
                logger.debug("Geocoded suburb", name=suburb.name, lat=lat, lng=lng)
                geocoded += 1
            else:
                logger.warning("Failed to geocode suburb", name=suburb.name, postcode=suburb.postcode)
                failed += 1

            await asyncio.sleep(_REQUEST_DELAY)

            # Commit in batches to avoid holding a long transaction
            if (geocoded + failed) % 50 == 0:
                await db.commit()
                logger.info(
                    "Suburb geocoder progress",
                    geocoded=geocoded,
                    failed=failed,
                    remaining=len(suburbs) - geocoded - failed,
                )

    await db.commit()
    logger.info("Suburb geocoder complete", geocoded=geocoded, failed=failed)
    return {"geocoded": geocoded, "failed": failed}
