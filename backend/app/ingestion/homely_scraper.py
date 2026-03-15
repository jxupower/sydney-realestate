"""Homely.com.au scraper.

Scrapes Sydney for-sale listings by extracting the __NEXT_DATA__ JSON embedded
in each page's HTML. Homely uses Next.js SSR, so all listing data is available
in the initial HTML without JavaScript execution.

Listing data path: props.pageProps.ssrData.listings

URL structure:
  Page 1: /for-sale/sydney-nsw-2000/real-estate
  Page N: /for-sale/sydney-nsw-2000/real-estate/page-{N}

Rate limiting: 1.5s delay between page requests (polite crawling).
Pagination: stops when the listings array is empty or page exceeds MAX_PAGES.
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from bs4 import BeautifulSoup

from app.ingestion.base import BaseIngester, RawProperty

logger = structlog.get_logger(__name__)

_BASE_URL = "https://www.homely.com.au"
_SEARCH_BASE = f"{_BASE_URL}/for-sale/sydney-nsw-2000/real-estate"
_MAX_PAGES = 37   # Homely shows ~37 pages for Sydney (25 listings/page)
_PAGE_DELAY = 1.5  # seconds between requests


def _extract_next_data(html: str) -> Optional[dict]:
    """Extract and parse the __NEXT_DATA__ JSON from the page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_price(text: str) -> Optional[int]:
    """Extract price in AUD cents from a price string like '$1,250,000' or '$1.25M'."""
    if not text:
        return None
    t = text.lower().replace(",", "").strip()
    m = re.search(r"[\d.]+", t)
    if not m:
        return None
    val = float(m.group())
    if "m" in t:
        val *= 1_000_000
    elif "k" in t:
        val *= 1_000
    if val < 10_000:  # not a real price
        return None
    return int(val * 100)


def _parse_suburb_postcode(long_address: str) -> tuple[Optional[str], Optional[str]]:
    """Extract suburb and postcode from a long address like '12 Main St, Parramatta NSW 2150'."""
    m = re.search(r",\s*([A-Za-z\s]+?)\s+NSW\s+(\d{4})", long_address or "")
    if m:
        return m.group(1).strip().title(), m.group(2)
    m2 = re.search(r"(\d{4})\s*$", long_address or "")
    if m2:
        before = long_address[: m2.start()].rstrip(",. ").strip()
        parts = before.rsplit(",", 1)
        suburb_raw = parts[-1].strip() if parts else before
        return suburb_raw.title() or None, m2.group(1)
    return None, None


def _parse_property_type(listing: dict) -> str:
    title = (listing.get("title") or "").lower()
    uri = (listing.get("uri") or "").lower()
    combined = title + " " + uri
    if any(k in combined for k in ["townhouse", "town-house", "town house"]):
        return "townhouse"
    if any(k in combined for k in ["apartment", "unit", "flat"]):
        return "apartment"
    if any(k in combined for k in ["land", "vacant"]):
        return "land"
    # Homely also provides a listingType field in some variants
    listing_type = (listing.get("listingType") or "").lower()
    if "apartment" in listing_type or "unit" in listing_type:
        return "apartment"
    if "townhouse" in listing_type:
        return "townhouse"
    return "house"


class HomelyScraper(BaseIngester):
    """Scrapes Homely.com.au for active Sydney for-sale listings via __NEXT_DATA__ JSON."""

    async def fetch(self) -> list[RawProperty]:
        results: list[RawProperty] = []
        seen_ids: set[str] = set()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
        }

        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
            for page in range(1, _MAX_PAGES + 1):
                url = _SEARCH_BASE if page == 1 else f"{_SEARCH_BASE}/page-{page}"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    logger.warning("Homely fetch error", page=page, error=str(e))
                    break

                data = _extract_next_data(resp.text)
                if not data:
                    logger.warning("Homely: no __NEXT_DATA__ found", page=page)
                    break

                try:
                    listings = (
                        data["props"]["pageProps"]["ssrData"]["listings"]
                    )
                except (KeyError, TypeError):
                    logger.warning("Homely: unexpected __NEXT_DATA__ structure", page=page)
                    break

                if not listings:
                    logger.info("Homely: no more listings", page=page)
                    break

                page_count = 0
                for listing in listings:
                    raw = self._parse_listing(listing)
                    if raw and raw.external_id not in seen_ids:
                        seen_ids.add(raw.external_id)
                        results.append(raw)
                        page_count += 1

                logger.info("Homely page scraped", page=page, listings=page_count, total=len(results))
                await asyncio.sleep(_PAGE_DELAY)

        logger.info("Homely scrape complete", total=len(results))
        return results

    def _parse_listing(self, listing: dict) -> Optional[RawProperty]:
        try:
            listing_id = str(listing.get("id", ""))
            if not listing_id:
                return None

            # canonicalUri is always present and includes the listing ID — use it for URL
            canonical = listing.get("canonicalUri") or ""
            url = f"{_BASE_URL}{canonical}" if canonical else f"{_BASE_URL}/homes/{listing_id}"
            external_id = listing_id  # Homely numeric ID is stable

            # Address
            address = listing.get("address") or {}
            long_address = address.get("longAddress") or ""
            street = address.get("streetAddress") or None
            suburb, postcode = _parse_suburb_postcode(long_address)

            # Price
            price_details = listing.get("priceDetails") or {}
            price_text = price_details.get("longDescription") or price_details.get("shortDescription") or ""
            list_price = _parse_price(price_text)

            # Features
            features = listing.get("features") or {}
            bedrooms = features.get("bedrooms")
            bathrooms = features.get("bathrooms")
            car_spaces = features.get("cars")

            # Location — Homely provides real coordinates under location.latLong
            location = listing.get("location") or {}
            lat_long = location.get("latLong") or {}
            latitude = lat_long.get("latitude")
            longitude = lat_long.get("longitude")

            # Image — media is a dict with a "photos" list
            media = listing.get("media") or {}
            photos = media.get("photos") or [] if isinstance(media, dict) else []
            images = []
            if photos:
                img_url = photos[0].get("webDefaultURI") or photos[0].get("webHeroURI")
                if img_url:
                    images = [img_url]

            # Agent / agency — under contactDetails
            contact = listing.get("contactDetails") or {}
            agents = contact.get("agents") or []
            agent_name = agents[0].get("name") if agents else None
            office = contact.get("office") or {}
            agency_name = office.get("name") if office else None

            property_type = _parse_property_type(listing)

            return RawProperty(
                external_id=external_id,
                source="homely",
                url=url,
                status="for_sale",
                property_type=property_type,
                address_street=street,
                address_suburb=suburb,
                address_postcode=postcode,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                car_spaces=car_spaces,
                list_price=list_price,
                latitude=latitude,
                longitude=longitude,
                images=images,
                agent_name=agent_name,
                agency_name=agency_name,
                raw_json={"scraped_at": datetime.now(timezone.utc).isoformat()},
            )

        except Exception as e:
            logger.warning("Homely: failed to parse listing", error=str(e))
            return None
