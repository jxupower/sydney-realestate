"""OnTheHouse.com.au scraper.

Scrapes suburb search results pages using httpx + BeautifulSoup.
Provides supplementary listing data (AVM estimates, last sale, council/zoning)
to complement Domain API listings.

NOTE: If selectors stop working, inspect the live site HTML and update
      the _CSS_* constants below.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from bs4 import BeautifulSoup

from app.ingestion.base import BaseIngester, RawProperty
from app.ingestion.domain_api import SYDNEY_POSTCODES
from app.utils.geo import is_within_search_radius

logger = structlog.get_logger(__name__)

_BASE_URL = "https://www.onthehouse.com.au"
_SEARCH_URL = f"{_BASE_URL}/search"

# CSS selectors — update here if the site's markup changes
_CSS_LISTING_CARD = (
    "div[data-testid='listing-card'], "
    "article.listing-card, "
    "div.property-card, "
    "div.search-result"
)
_CSS_ADDRESS = (
    "[data-testid='listing-address'], "
    ".listing-address, "
    "h2.address, "
    "span.property-address"
)
_CSS_PRICE = (
    "[data-testid='listing-price'], "
    ".listing-price, "
    "span.price, "
    "p.property-price"
)
_CSS_BEDS = (
    "[data-testid='beds'], "
    "span[title='Bedrooms'], "
    ".listing-beds, "
    "li.beds"
)
_CSS_BATHS = (
    "[data-testid='baths'], "
    "span[title='Bathrooms'], "
    ".listing-baths, "
    "li.baths"
)
_CSS_CARS = (
    "[data-testid='cars'], "
    "span[title='Car spaces'], "
    ".listing-cars, "
    "li.cars"
)
_CSS_LAND = (
    "[data-testid='land-size'], "
    ".land-size, "
    "li.land, "
    "span.land-area"
)
_CSS_LINK = (
    "a[data-testid='listing-link'], "
    "a.listing-link, "
    "a.property-link, "
    "a[href*='/property/']"
)
_CSS_PAGINATION_NEXT = (
    "a[data-testid='pagination-next'], "
    "a.pagination-next, "
    "a[rel='next'], "
    "button[aria-label='Next page']"
)
_CSS_TYPE = (
    "[data-testid='property-type'], "
    ".property-type, "
    "span.listing-type"
)

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
}

# Scrape every 3rd postcode to reduce load (~50 postcodes out of ~150)
_POSTCODE_SAMPLE_STEP = 3
_MAX_PAGES_PER_POSTCODE = 5
_DELAY_BETWEEN_REQUESTS = 2.0   # seconds — be polite to the server
_DELAY_ON_RATE_LIMIT = 30.0


# ─── Parsing helpers ─────────────────────────────────────────────────────────

def _parse_price(text: str) -> Optional[int]:
    """Return price in cents from '$1,250,000' style strings."""
    cleaned = re.sub(r"[^\d]", "", text)
    if cleaned:
        try:
            return int(cleaned) * 100
        except ValueError:
            pass
    return None


def _parse_area(text: str) -> Optional[float]:
    """Return area in sqm from '450 m²' or '0.45 ha' strings."""
    t = text.strip().lower()
    m2 = re.search(r"([\d,.]+)\s*m", t)
    if m2:
        try:
            return float(m2.group(1).replace(",", ""))
        except ValueError:
            pass
    ha = re.search(r"([\d,.]+)\s*ha", t)
    if ha:
        try:
            return float(ha.group(1).replace(",", "")) * 10_000
        except ValueError:
            pass
    return None


def _parse_int(text: str) -> Optional[int]:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _extract_id(url: str) -> str:
    """Derive a stable external_id from the listing URL path."""
    path = url.split("?")[0].lower().strip("/")
    return re.sub(r"[^a-z0-9_-]", "_", path)[-80:]


def _property_type_from_url(url: str) -> str:
    u = url.lower()
    if any(k in u for k in ("apartment", "unit", "flat")):
        return "apartment"
    if "townhouse" in u:
        return "townhouse"
    if any(k in u for k in ("land", "vacant")):
        return "land"
    return "house"


# ─── Ingester ────────────────────────────────────────────────────────────────

class OnTheHouseScraper(BaseIngester):
    """Scrape OnTheHouse.com.au for supplementary for-sale listing data."""

    def is_available(self) -> bool:
        return True  # no API key required

    async def fetch(self) -> list[RawProperty]:
        results: list[RawProperty] = []
        postcodes = SYDNEY_POSTCODES[::_POSTCODE_SAMPLE_STEP]

        async with httpx.AsyncClient(
            headers=_REQUEST_HEADERS,
            timeout=30,
            follow_redirects=True,
        ) as client:
            for postcode in postcodes:
                try:
                    batch = await self._scrape_postcode(client, postcode)
                    results.extend(batch)
                    logger.debug("Scraped postcode", postcode=postcode, count=len(batch))
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        logger.warning("OnTheHouse rate limited — waiting", postcode=postcode)
                        await asyncio.sleep(_DELAY_ON_RATE_LIMIT)
                    else:
                        logger.error(
                            "OnTheHouse HTTP error",
                            postcode=postcode,
                            status=exc.response.status_code,
                        )
                except Exception as exc:
                    logger.error(
                        "OnTheHouse unexpected error",
                        postcode=postcode,
                        error=str(exc),
                    )
                finally:
                    await asyncio.sleep(_DELAY_BETWEEN_REQUESTS)

        logger.info("OnTheHouse scrape complete", total=len(results))
        return results

    async def _scrape_postcode(
        self, client: httpx.AsyncClient, postcode: str
    ) -> list[RawProperty]:
        results: list[RawProperty] = []
        page = 1

        while page <= _MAX_PAGES_PER_POSTCODE:
            resp = await client.get(
                _SEARCH_URL,
                params={"q": f"NSW {postcode}", "type": "sale", "page": page},
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(_CSS_LISTING_CARD)
            if not cards:
                break

            for card in cards:
                raw = self._parse_card(card)
                if raw and is_within_search_radius(raw.latitude, raw.longitude):
                    results.append(raw)

            if not soup.select_one(_CSS_PAGINATION_NEXT):
                break

            page += 1
            await asyncio.sleep(_DELAY_BETWEEN_REQUESTS)

        return results

    def _parse_card(self, card: BeautifulSoup) -> Optional[RawProperty]:
        try:
            link_el = card.select_one(_CSS_LINK)
            if not link_el or not link_el.get("href"):
                return None

            href = str(link_el["href"])
            url = href if href.startswith("http") else f"{_BASE_URL}{href}"
            external_id = f"oth_{_extract_id(url)}"

            # Address
            addr_el = card.select_one(_CSS_ADDRESS)
            address_full = addr_el.get_text(separator=" ", strip=True) if addr_el else ""

            street: Optional[str] = None
            suburb: Optional[str] = None
            postcode: Optional[str] = None

            if address_full:
                parts = [p.strip() for p in address_full.split(",")]
                if len(parts) >= 2:
                    street = parts[0]
                    loc = parts[-1]  # "SuburbName NSW 2060"
                    pc_m = re.search(r"\b(\d{4})\b", loc)
                    if pc_m:
                        postcode = pc_m.group(1)
                    suburb_raw = re.sub(
                        r"\b(NSW|VIC|QLD|WA|SA|ACT|TAS|NT)\b.*", "", loc
                    ).strip()
                    suburb = suburb_raw or None

            # Price
            price_el = card.select_one(_CSS_PRICE)
            list_price = _parse_price(price_el.get_text()) if price_el else None

            # Property type
            type_el = card.select_one(_CSS_TYPE)
            if type_el:
                raw_type = type_el.get_text(strip=True).lower()
                if "apartment" in raw_type or "unit" in raw_type:
                    ptype = "apartment"
                elif "townhouse" in raw_type:
                    ptype = "townhouse"
                elif "land" in raw_type:
                    ptype = "land"
                else:
                    ptype = "house"
            else:
                ptype = _property_type_from_url(url)

            # Features
            beds_el = card.select_one(_CSS_BEDS)
            baths_el = card.select_one(_CSS_BATHS)
            cars_el = card.select_one(_CSS_CARS)
            land_el = card.select_one(_CSS_LAND)

            return RawProperty(
                external_id=external_id,
                source="onthehouse",
                url=url,
                status="for_sale",
                property_type=ptype,
                address_street=street,
                address_suburb=suburb,
                address_postcode=postcode,
                # latitude/longitude not available from list page; will be None
                bedrooms=_parse_int(beds_el.get_text()) if beds_el else None,
                bathrooms=_parse_int(baths_el.get_text()) if baths_el else None,
                car_spaces=_parse_int(cars_el.get_text()) if cars_el else None,
                land_size_sqm=_parse_area(land_el.get_text()) if land_el else None,
                list_price=list_price,
                listed_at=datetime.now(timezone.utc),
                raw_json={
                    "url": url,
                    "address": address_full,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        except Exception as exc:
            logger.debug("Failed to parse OnTheHouse card", error=str(exc))
            return None
