"""OSM Overpass API enricher — populates osm_amenities per suburb.

Queries the public Overpass API for transport, schools, shops, and parks
within bounding boxes around each Sydney suburb.

CLI usage:
    python -m app.ingestion.osm_enricher
    python -m app.ingestion.osm_enricher --suburb-id 42
"""
from __future__ import annotations

import argparse
import asyncio
import math
import time
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.suburb import Suburb
from app.db.models.osm import OsmAmenities
from app.db.session import AsyncSessionLocal
from app.utils.geo import haversine_km
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_DELAY = 1.5     # seconds between requests (polite use of public instance)
TIMEOUT = 30            # seconds
RADIUS_DEG_APPROX = 0.022   # ~2.5km in degrees (used for bounding box padding)


# ── Overpass query helpers ────────────────────────────────────────────────────

def _bbox(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Return (south, west, north, east) bounding box for a radius around a point."""
    delta_lat = radius_km / 111.0
    delta_lng = radius_km / (111.0 * math.cos(math.radians(lat)))
    return lat - delta_lat, lng - delta_lng, lat + delta_lat, lng + delta_lng


def _overpass_query(lat: float, lng: float) -> str:
    """Build a single Overpass QL query covering all needed amenity types."""
    s, w, n, e = _bbox(lat, lng, 3.0)  # 3km bbox for OSM query
    bbox_str = f"{s:.6f},{w:.6f},{n:.6f},{e:.6f}"

    return f"""
[out:json][timeout:{TIMEOUT}];
(
  node["railway"="station"]({bbox_str});
  node["railway"="halt"]({bbox_str});
  node["public_transport"="stop_position"]["bus"="yes"]({bbox_str});
  node["highway"="bus_stop"]({bbox_str});
  node["amenity"="school"]["isced:level"~"1"]({bbox_str});
  node["amenity"="school"]["school:level"~"primary"]({bbox_str});
  node["amenity"="school"]["isced:level"~"2|3"]({bbox_str});
  node["amenity"="school"]["school:level"~"secondary"]({bbox_str});
  node["shop"="supermarket"]({bbox_str});
  node["shop"="convenience"]({bbox_str});
  leisure["leisure"="park"]({bbox_str});
  way["leisure"="park"]({bbox_str});
);
out center;
""".strip()


# ── Feature extraction ────────────────────────────────────────────────────────

def _extract_features(
    elements: list[dict[str, Any]],
    suburb_lat: float,
    suburb_lng: float,
) -> dict:
    """Compute distance/count features from raw Overpass elements."""

    train_dists: list[float] = []
    bus_dists: list[float] = []
    primary_cnt = 0
    secondary_cnt = 0
    supermarket_cnt = 0
    park_cnt = 0

    for el in elements:
        # Resolve lat/lng — nodes have them directly; ways have a "center" key
        if el["type"] == "node":
            elat, elng = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            elat, elng = center.get("lat"), center.get("lon")

        if elat is None or elng is None:
            continue

        dist = haversine_km(suburb_lat, suburb_lng, elat, elng)
        tags = el.get("tags", {})
        railway = tags.get("railway", "")
        highway = tags.get("highway", "")
        pt = tags.get("public_transport", "")
        bus = tags.get("bus", "")
        amenity = tags.get("amenity", "")
        shop = tags.get("shop", "")
        leisure = tags.get("leisure", "")
        isced = tags.get("isced:level", "") + tags.get("school:level", "")

        if railway in ("station", "halt"):
            train_dists.append(dist)
        elif highway == "bus_stop" or (pt == "stop_position" and bus == "yes"):
            bus_dists.append(dist)
        elif amenity == "school":
            if "1" in isced or "primary" in isced.lower():
                if dist <= 2.0:
                    primary_cnt += 1
            if any(x in isced for x in ("2", "3")) or "secondary" in isced.lower():
                if dist <= 3.0:
                    secondary_cnt += 1
        elif shop in ("supermarket", "convenience"):
            if dist <= 1.0:
                supermarket_cnt += 1
        elif leisure == "park":
            if dist <= 1.0:
                park_cnt += 1

    nearest_train = min(train_dists) if train_dists else None
    train_2km = sum(1 for d in train_dists if d <= 2.0)
    nearest_bus = min(bus_dists) if bus_dists else None
    bus_500m = sum(1 for d in bus_dists if d <= 0.5)

    # Walkability score: composite 0–100
    walkability = _compute_walkability(
        nearest_train, nearest_bus, bus_500m, primary_cnt, supermarket_cnt, park_cnt
    )

    return {
        "nearest_train_km": round(nearest_train, 3) if nearest_train is not None else None,
        "train_stations_2km": train_2km,
        "nearest_bus_stop_km": round(nearest_bus, 3) if nearest_bus is not None else None,
        "bus_stops_500m": bus_500m,
        "primary_schools_2km": primary_cnt,
        "secondary_schools_3km": secondary_cnt,
        "supermarkets_1km": supermarket_cnt,
        "parks_1km": park_cnt,
        "walkability_score": walkability,
    }


def _compute_walkability(
    nearest_train: float | None,
    nearest_bus: float | None,
    bus_500m: int,
    primary_cnt: int,
    supermarket_cnt: int,
    park_cnt: int,
) -> int:
    """Composite walkability 0–100."""
    score = 0

    # Transport (40 pts)
    if nearest_train is not None:
        if nearest_train < 0.5:
            score += 30
        elif nearest_train < 1.0:
            score += 20
        elif nearest_train < 2.0:
            score += 10
    if bus_500m >= 3:
        score += 10
    elif bus_500m >= 1:
        score += 5

    # Schools (20 pts)
    if primary_cnt >= 2:
        score += 20
    elif primary_cnt == 1:
        score += 10

    # Shops (20 pts)
    if supermarket_cnt >= 2:
        score += 20
    elif supermarket_cnt == 1:
        score += 10

    # Parks (20 pts)
    if park_cnt >= 3:
        score += 20
    elif park_cnt >= 1:
        score += 10

    return min(score, 100)


# ── HTTP client ───────────────────────────────────────────────────────────────

async def _fetch_overpass(client: httpx.AsyncClient, query: str) -> list[dict]:
    try:
        resp = await client.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("elements", [])
    except httpx.HTTPStatusError as e:
        logger.warning("Overpass HTTP error", status=e.response.status_code)
        return []
    except Exception as e:
        logger.warning("Overpass request failed", error=str(e))
        return []


# ── Main enricher ─────────────────────────────────────────────────────────────

async def enrich_suburbs(suburb_ids: list[int] | None = None) -> dict:
    """Fetch OSM data for all (or specific) suburbs and upsert OsmAmenities."""
    configure_logging()

    async with AsyncSessionLocal() as db:
        stmt = select(Suburb).where(
            Suburb.latitude.is_not(None),
            Suburb.longitude.is_not(None),
        )
        if suburb_ids:
            stmt = stmt.where(Suburb.id.in_(suburb_ids))

        result = await db.execute(stmt)
        suburbs = result.scalars().all()

    if not suburbs:
        logger.info("No suburbs to enrich")
        return {"enriched": 0}

    logger.info("Enriching suburbs", count=len(suburbs))
    enriched = 0
    errors = 0

    async with httpx.AsyncClient(headers={"User-Agent": "SydneyRE-Enricher/1.0"}) as client:
        for suburb in suburbs:
            try:
                query = _overpass_query(suburb.latitude, suburb.longitude)
                elements = await _fetch_overpass(client, query)
                features = _extract_features(elements, suburb.latitude, suburb.longitude)
                features["suburb_id"] = suburb.id

                async with AsyncSessionLocal() as db:
                    stmt = (
                        pg_insert(OsmAmenities)
                        .values(**features)
                        .on_conflict_do_update(
                            constraint="uq_osm_suburb",
                            set_={k: v for k, v in features.items() if k != "suburb_id"},
                        )
                    )
                    await db.execute(stmt)
                    await db.commit()

                enriched += 1
                logger.info(
                    "Suburb enriched",
                    suburb=suburb.name,
                    walkability=features["walkability_score"],
                    train_km=features["nearest_train_km"],
                )

            except Exception as e:
                errors += 1
                logger.error("Suburb enrichment failed", suburb=suburb.name, error=str(e))

            # Polite delay
            await asyncio.sleep(REQUEST_DELAY)

    logger.info("OSM enrichment complete", enriched=enriched, errors=errors)
    return {"enriched": enriched, "errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich suburbs with OSM amenity data")
    parser.add_argument("--suburb-id", type=int, nargs="*", dest="suburb_ids")
    args = parser.parse_args()
    asyncio.run(enrich_suburbs(suburb_ids=args.suburb_ids))
