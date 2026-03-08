"""Seed the database with realistic synthetic Sydney property data for testing.

Generates ~150 properties spread across inner/middle/outer Sydney suburbs,
with coordinates, prices, bedrooms, etc. so the full pipeline (API, map,
ML predictor) can be exercised without a live data source.

CLI:
    python -m app.ingestion.seed_data
    python -m app.ingestion.seed_data --clear   # wipe seed data first
"""

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone

import structlog

from app.db.session import AsyncSessionLocal
from app.db.models.property import Property
from app.repositories.property_repo import PropertyRepository
from app.repositories.suburb_repo import SuburbRepository
from app.utils.logger import configure_logging

logger = structlog.get_logger(__name__)

# (suburb, postcode, centre_lat, centre_lng, median_price_aud)
_SUBURBS = [
    # Inner East
    ("Bondi",           "2026", -33.8915, 151.2767, 2_200_000),
    ("Bondi Beach",     "2026", -33.8907, 151.2740, 2_500_000),
    ("Coogee",          "2034", -33.9222, 151.2595, 1_950_000),
    ("Randwick",        "2031", -33.9143, 151.2405, 1_750_000),
    ("Surry Hills",     "2010", -33.8868, 151.2097, 1_400_000),
    ("Paddington",      "2021", -33.8837, 151.2285, 2_100_000),
    ("Newtown",         "2042", -33.8979, 151.1797, 1_350_000),
    ("Glebe",           "2037", -33.8796, 151.1869, 1_450_000),
    # Inner West
    ("Leichhardt",      "2040", -33.8835, 151.1568, 1_550_000),
    ("Balmain",         "2041", -33.8607, 151.1787, 1_950_000),
    ("Rozelle",         "2039", -33.8643, 151.1726, 1_700_000),
    ("Annandale",       "2038", -33.8834, 151.1684, 1_600_000),
    ("Marrickville",    "2204", -33.9108, 151.1579, 1_300_000),
    ("Dulwich Hill",    "2203", -33.9062, 151.1432, 1_200_000),
    # Lower North Shore
    ("Mosman",          "2088", -33.8293, 151.2441, 3_200_000),
    ("Cremorne",        "2090", -33.8357, 151.2271, 2_200_000),
    ("Neutral Bay",     "2089", -33.8375, 151.2183, 1_900_000),
    ("North Sydney",    "2060", -33.8398, 151.2074, 1_400_000),
    ("Kirribilli",      "2061", -33.8486, 151.2142, 2_100_000),
    ("Milsons Point",   "2061", -33.8454, 151.2112, 2_000_000),
    # Upper North Shore
    ("Chatswood",       "2067", -33.7965, 151.1817, 1_800_000),
    ("Lane Cove",       "2066", -33.8154, 151.1672, 1_750_000),
    ("Killara",         "2071", -33.7722, 151.1660, 2_800_000),
    ("Gordon",          "2072", -33.7576, 151.1533, 2_600_000),
    ("Pymble",          "2073", -33.7489, 151.1430, 2_400_000),
    # Northern Beaches
    ("Manly",           "2095", -33.7969, 151.2877, 2_600_000),
    ("Dee Why",         "2099", -33.7510, 151.2864, 1_600_000),
    ("Brookvale",       "2100", -33.7658, 151.2624, 1_200_000),
    ("Mona Vale",       "2103", -33.6788, 151.3012, 1_900_000),
    ("Narrabeen",       "2101", -33.7203, 151.2997, 1_700_000),
    # Eastern Suburbs
    ("Double Bay",      "2028", -33.8764, 151.2440, 4_000_000),
    ("Rose Bay",        "2029", -33.8749, 151.2594, 3_500_000),
    ("Vaucluse",        "2030", -33.8574, 151.2769, 4_500_000),
    ("Watsons Bay",     "2030", -33.8421, 151.2833, 4_200_000),
    ("Edgecliff",       "2027", -33.8780, 151.2345, 1_600_000),
    # Sutherland Shire
    ("Cronulla",        "2230", -34.0574, 151.1528, 1_750_000),
    ("Miranda",         "2228", -34.0356, 151.1017, 1_100_000),
    ("Sutherland",      "2232", -34.0316, 151.0573, 1_050_000),
    # Western Sydney
    ("Parramatta",      "2150", -33.8148, 151.0017, 900_000),
    ("Westmead",        "2145", -33.8080, 150.9872, 850_000),
    ("Auburn",          "2144", -33.8494, 151.0322, 780_000),
    ("Merrylands",      "2160", -33.8354, 150.9882, 820_000),
    ("Penrith",         "2750", -33.7511, 150.6942, 750_000),
    # South Sydney
    ("Hurstville",      "2220", -33.9658, 151.1019, 1_100_000),
    ("Kogarah",         "2217", -33.9638, 151.1342, 1_050_000),
    ("Rockdale",        "2216", -33.9517, 151.1369, 980_000),
    ("Arncliffe",       "2205", -33.9407, 151.1480, 950_000),
    # Hills District
    ("Castle Hill",     "2154", -33.7307, 151.0040, 1_400_000),
    ("Baulkham Hills",  "2153", -33.7607, 150.9900, 1_350_000),
    ("Kellyville",      "2155", -33.7088, 150.9642, 1_250_000),
]

_PROPERTY_TYPES = ["house", "house", "house", "apartment", "apartment", "townhouse"]
_STREET_NAMES = [
    "Ocean", "Park", "Hill", "Garden", "Rose", "Bay", "Lake", "River",
    "Forest", "Valley", "Beach", "Cliff", "View", "Ridge", "Grove",
    "Maple", "Cedar", "Willow", "Elm", "Pine", "Harbour", "Pacific",
]
_STREET_TYPES = ["Street", "Road", "Avenue", "Place", "Crescent", "Drive", "Lane", "Court"]
_AGENTS = [
    ("James Wilson", "Ray White Sydney"),
    ("Sarah Chen", "McGrath Estate Agents"),
    ("Michael O'Brien", "LJ Hooker"),
    ("Emma Thompson", "Domain Property"),
    ("David Park", "Barry Plant"),
    ("Lisa Nguyen", "Harcourts"),
    ("Robert Smith", "Richardson & Wrench"),
    ("Anna Kowalski", "Belle Property"),
]

random.seed(42)  # reproducible results


def _jitter(centre: float, spread: float = 0.015) -> float:
    return centre + random.uniform(-spread, spread)


def _street_address(n: int) -> str:
    return (
        f"{random.randint(1, 120)} "
        f"{random.choice(_STREET_NAMES)} "
        f"{random.choice(_STREET_TYPES)}"
    )


def _price_cents(median: int) -> int:
    """Return a list price within ±30% of the suburb median."""
    factor = random.uniform(0.70, 1.30)
    # Round to nearest $5,000
    raw = int(median * factor)
    return (raw // 5_000) * 5_000 * 100  # convert to cents


def _base_property(idx: int, suburb_row: tuple, status: str) -> dict:
    """Build a property dict for the given status ('for_sale' or 'sold')."""
    suburb, postcode, clat, clng, median = suburb_row
    ptype = random.choice(_PROPERTY_TYPES)
    beds = random.randint(1, 5) if ptype == "apartment" else random.randint(2, 6)
    baths = max(1, beds - random.randint(0, 2))
    cars = random.randint(0, 2) if ptype == "apartment" else random.randint(1, 3)

    list_price = _price_cents(median)
    guide_low = int(list_price * 0.95)
    guide_high = int(list_price * 1.05)

    listed_days_ago = random.randint(30, 730)  # listed 1 month–2 years ago
    listed_at = datetime.now(timezone.utc) - timedelta(days=listed_days_ago)

    sold_at = None
    sold_price = None
    if status == "sold":
        sold_days_ago = random.randint(1, listed_days_ago - 7)
        sold_at = datetime.now(timezone.utc) - timedelta(days=sold_days_ago)
        # Sold price: ±10% of list price (market noise)
        sold_price = int(list_price * random.uniform(0.90, 1.10))

    lat = _jitter(clat)
    lng = _jitter(clng)
    street = _street_address(idx)
    agent_name, agency_name = random.choice(_AGENTS)

    land_sqm = None
    floor_sqm = None
    if ptype == "house":
        land_sqm = float(random.randint(300, 1200))
        floor_sqm = float(random.randint(120, 450))
    elif ptype == "townhouse":
        land_sqm = float(random.randint(150, 400))
        floor_sqm = float(random.randint(100, 250))
    else:
        floor_sqm = float(random.randint(50, 160))

    year_built = random.choice([None, None, random.randint(1960, 2023)])

    external_id = f"seed_{status[0]}_{idx:05d}"
    url = (
        f"https://example-seed.com/property/"
        f"{suburb.lower().replace(' ', '-')}-{postcode}-{status[0]}-{idx}"
    )

    features = []
    if random.random() > 0.6:
        features.append("aircon")
    if ptype == "house" and random.random() > 0.7:
        features.append("pool")
    if random.random() > 0.5:
        features.append("dishwasher")
    if ptype != "apartment" and random.random() > 0.6:
        features.append("alfresco")

    return {
        "external_id": external_id,
        "source": "seed",
        "url": url,
        "status": status,
        "property_type": ptype,
        "address_street": street,
        "address_suburb": suburb,
        "address_postcode": postcode,
        "latitude": round(lat, 6),
        "longitude": round(lng, 6),
        "bedrooms": beds,
        "bathrooms": baths,
        "car_spaces": cars,
        "land_size_sqm": land_sqm,
        "floor_area_sqm": floor_sqm,
        "year_built": year_built,
        "list_price": list_price,
        "price_guide_low": guide_low,
        "price_guide_high": guide_high,
        "listed_at": listed_at,
        "sold_at": sold_at,
        "sold_price": sold_price,
        "agent_name": agent_name,
        "agency_name": agency_name,
        "description": (
            f"Stunning {ptype} in the heart of {suburb}. "
            f"Featuring {beds} bedrooms, {baths} bathrooms"
            + (f", {cars} car spaces" if cars else "")
            + ". Excellent lifestyle location with easy access to transport and shops."
        ),
        "features": features,
        "raw_json": {"seeded": True},
    }


async def seed(clear: bool = False) -> dict:
    configure_logging()

    async with AsyncSessionLocal() as db:
        if clear:
            from sqlalchemy import delete
            await db.execute(delete(Property).where(Property.source == "seed"))
            await db.commit()
            logger.info("Cleared existing seed data")

        repo = PropertyRepository(db)
        suburb_repo = SuburbRepository(db)
        inserted = updated = 0
        idx = 0

        for suburb_row in _SUBURBS:
            suburb, postcode, clat, clng, _ = suburb_row

            suburb_obj, _ = await suburb_repo.upsert(
                name=suburb,
                postcode=postcode,
                latitude=clat,
                longitude=clng,
            )

            # ~4 sold properties per suburb (training data for ML)
            for _ in range(random.randint(3, 5)):
                idx += 1
                data = _base_property(idx, suburb_row, "sold")
                data["suburb_id"] = suburb_obj.id
                _, was_inserted = await repo.upsert(data)
                inserted += int(was_inserted)
                updated += int(not was_inserted)

            # ~3 for-sale properties per suburb (prediction targets)
            for _ in range(random.randint(2, 4)):
                idx += 1
                data = _base_property(idx, suburb_row, "for_sale")
                data["suburb_id"] = suburb_obj.id
                _, was_inserted = await repo.upsert(data)
                inserted += int(was_inserted)
                updated += int(not was_inserted)

        await db.commit()
        logger.info("Seed complete", inserted=inserted, updated=updated, total=idx)
        return {"inserted": inserted, "updated": updated, "total": idx}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the DB with synthetic Sydney properties")
    parser.add_argument("--clear", action="store_true", help="Delete existing seed rows first")
    args = parser.parse_args()
    asyncio.run(seed(clear=args.clear))
