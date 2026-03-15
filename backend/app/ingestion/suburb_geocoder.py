"""Suburb geocoder — backfills latitude/longitude for suburbs via Nominatim (OpenStreetMap).

Nominatim usage policy:
  - Max 1 request per second (we use 1.5s base delay to be safe)
  - User-Agent header must identify the application
  - No API key required

Usage:
    python -m app.ingestion.coordinator --source geocode_suburbs
"""

import asyncio
from typing import Optional

import httpx
import structlog

from app.db.models.suburb import Suburb
from app.repositories.suburb_repo import SuburbRepository
from sqlalchemy import select

logger = structlog.get_logger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_REQUEST_DELAY = 1.5   # seconds between requests — above Nominatim's 1 req/sec limit
_RETRY_DELAY = 60.0    # seconds to wait on 429 before retrying
_MAX_RETRIES = 3
_USER_AGENT = "SydneyRealEstateApp/1.0 (sydney-re-investment-app)"


async def _geocode_suburb(client: httpx.AsyncClient, name: str) -> Optional[tuple[float, float]]:
    """Query Nominatim for the centroid of a NSW suburb. Returns (lat, lng) or None.
    Retries up to _MAX_RETRIES times on 429 with a long backoff.
    """
    for attempt in range(_MAX_RETRIES):
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
            if resp.status_code == 429:
                wait = _RETRY_DELAY * (attempt + 1)
                logger.warning(
                    "Nominatim rate limited — waiting before retry",
                    suburb=name,
                    wait_seconds=wait,
                    attempt=attempt + 1,
                )
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
            return None  # valid response but no match
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.warning("Nominatim geocode failed", suburb=name, error=str(e))
            return None
    return None


async def geocode_all_suburbs(db) -> dict:
    """Geocode all suburbs that have NULL latitude/longitude.

    Only processes Greater Sydney metro suburbs (postcodes 2000–2239) —
    NSW Sales data spans all of NSW but rural suburbs will never appear on
    the Sydney-bounded map.

    Updates suburb rows via SuburbRepository.upsert() which supports
    latitude/longitude kwargs. Returns {"geocoded": int, "failed": int}.
    """
    result = await db.execute(
        select(Suburb).where(
            Suburb.latitude.is_(None),
            Suburb.postcode >= "2000",
            Suburb.postcode <= "2239",
        )
    )
    suburbs = result.scalars().all()

    if not suburbs:
        logger.info("Suburb geocoder: all Sydney suburbs already have coordinates")
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
